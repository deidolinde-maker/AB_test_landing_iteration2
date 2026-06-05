from __future__ import annotations
from pathlib import Path

import pytest

from components.address_form import AddressForm
from helpers.ab_cookie import (
    assert_ab_cookie_value,
    assert_ab_cookie_not_changed,
    get_ab_cookie,
    get_ym_uid_cookie,
    set_ab_cookie,
    wait_ab_cookie,
)
from helpers.allure_attachments import attach_json, attach_png_file, attach_text
from helpers.application_json_store import utc_now_iso
from helpers.console_recorder import ConsoleRecorder
from helpers.network_recorder import NetworkRecorder
from pages.landing_page import LandingPage


def _is_form_required_for_url(site_config, form_config, url_type: str) -> bool:
    required_by_url = getattr(site_config, "required_forms_by_url_type", {}) or {}
    if url_type in required_by_url:
        required_forms = required_by_url.get(url_type) or []
        return form_config.name in required_forms
    return not form_config.optional


def _should_append_application_record(submit_success: bool) -> bool:
    return bool(submit_success)


def run_search_case(
    *,
    case,
    page,
    context,
    site_config,
    form_config,
    tmp_path: Path,
    verify_search_payload: bool = False,
    application_json_store=None,
    fail_on_missing_ym_uid: bool = False,
) -> None:
    recorder = NetworkRecorder(page, case_id=case.case_id, variant=case.variant)
    console = ConsoleRecorder(page)
    landing = LandingPage(page, site_config)
    form = AddressForm(page, form_config)
    target_url = site_config.urls[case.url_type]
    selected_street = ""
    selected_house = ""
    url_before_city_change = None
    url_after_city_change = None
    url_after_submit = None
    submit_time = None
    submit_success = False
    success_criterion = "not_submitted"
    error_payload = None
    artifacts: dict = {}

    attach_json(
        "case_context",
        {
            "case_id": case.case_id,
            "site": case.site,
            "url_type": case.url_type,
            "form": case.form,
            "variant": case.variant,
            "dataset": case.dataset,
            "region": case.region,
            "expected_street": case.expected_street,
            "expected_house": case.expected_house,
            "expected_id": case.expected_id,
            "expected_id_type": case.expected_id_type,
            "expected_lead_form_type": case.expected_lead_form_type,
            "expected_order_site": case.expected_order_site,
        },
    )

    try:
        set_ab_cookie(context, target_url, case.variant)
        recorder.start()
        console.start()

        landing.open(case.url_type)
        assert_ab_cookie_value(context, case.variant)
        ym_uid = get_ym_uid_cookie(context)
        if fail_on_missing_ym_uid and not ym_uid:
            raise AssertionError(
                "Step: Сохранение cookie для ручной проверки Метрики\n"
                "Expected: cookie _ym_uid is present\n"
                "Actual: cookie _ym_uid is missing"
            )

        form.open()
        if not form.is_present():
            is_required = _is_form_required_for_url(site_config, form_config, case.url_type)
            if not is_required:
                pytest.skip(
                    f"Optional form '{form_config.name}' is not present for case {case.pytest_id}"
                )
            pytest.fail(f"Required form '{form_config.name}' is not present for case {case.pytest_id}")

        initial_url = landing.get_current_url()
        url_before_city_change = initial_url
        expected_region_for_url = site_config.expected_regions.get(case.url_type)
        should_change_region = expected_region_for_url != case.region
        if should_change_region and form.can_change_city():
            form.change_city_inside_form(case.region)
            current_url = landing.get_current_url()
            url_after_city_change = current_url
            assert current_url == initial_url, (
                f"Step: Change region inside form\nExpected URL: {initial_url}\nActual URL: {current_url}"
            )
        else:
            url_after_city_change = initial_url

        form.fill_street(case.street_query)
        form.wait_street_suggest()
        form.assert_street_in_suggest(case.expected_street)
        form.select_street(
            case.expected_street,
            preferred_region=case.region,
            allow_domodedovo_oblast_alias=(case.variant == "B"),
        )
        selected_street = case.expected_street

        form.fill_house(case.house_query)
        form.wait_house_suggest()
        form.assert_house_in_suggest(case.expected_house)
        form.select_house(case.expected_house)
        selected_house = case.expected_house

        # Hidden ID fields can be populated asynchronously right after house selection.
        # Poll for a short period to reduce false negatives from UI timing races.
        actual_id = None
        for _ in range(12):
            actual_id = form.get_selected_house_id()
            if actual_id:
                break
            page.wait_for_timeout(150)
        assert str(actual_id) == str(case.expected_id), (
            f"Step: Validate selected address ID\nExpected: {case.expected_id}\nActual: {actual_id}"
        )

        if verify_search_payload:
            recorder.assert_b_search_payload(
                expected_id=case.expected_id,
                expected_street=case.expected_street,
                expected_house=case.expected_house,
                expected_region_id=case.region_id,
                expected_locality_id=case.expected_locality_id,
                expected_locality_name=case.expected_locality_name,
            )

        form.fill_phone(case.phone)
        actual_phone = form.get_phone_value()
        expected_digits = "".join(ch for ch in case.phone if ch.isdigit())
        digits_actual = "".join(ch for ch in actual_phone if ch.isdigit())
        # Phone fields on landing are masked; some layouts keep country code and trim one trailing digit.
        # For iteration 2 submit flow we accept strict full match and a relaxed masked-tail match.
        phone_is_applied = (
            expected_digits in digits_actual
            or digits_actual.endswith(expected_digits)
            or (
                len(expected_digits) > 1
                and len(digits_actual) >= (len(expected_digits) - 1)
                and digits_actual.endswith(expected_digits[1:])
            )
        )
        assert phone_is_applied, (
            "Step: Ввод номера телефона\n"
            f"Expected: phone {case.phone} is applied\n"
            f"Actual: phone field value = {actual_phone}"
        )
        assert form.is_submit_enabled(), (
            "Step: Подготовка к отправке заявки\n"
            "Expected: submit button is enabled\n"
            "Actual: submit button is disabled or missing"
        )

        submit_time = utc_now_iso()
        form.submit()
        page.wait_for_timeout(1200)
        try:
            page.wait_for_url(
                lambda url: any(marker in str(url) for marker in (case.success_url_markers or [])),
                timeout=20000,
            )
        except Exception:
            pass
        url_after_submit = landing.get_current_url()
        for marker in case.success_url_markers or []:
            if marker in url_after_submit:
                submit_success = True
                success_criterion = marker
                break
        assert submit_success, (
            "Step: Отправка заявки после клика на кнопку отправки\n"
            "Error code: submit_success_marker_not_found\n"
            f"Expected: URL after submit contains one of {case.success_url_markers}\n"
            f"Actual: URL after submit = {url_after_submit}"
        )
    except Exception as exc:
        url_after_submit = landing.get_current_url()
        if success_criterion == "not_submitted":
            success_criterion = "scenario_failed_before_success_marker"
        error_code = _classify_error(exc)
        if "submit_success_marker_not_found" in str(exc):
            success_criterion = "submit_success_marker_not_found"
        error_payload = {
            "error_code": error_code,
            "failed_step": _failed_step_from_exception(exc),
            "expected": "Сценарий отправки заявки выполняется до success URL marker",
            "actual": str(exc),
        }
        screenshot_path = tmp_path / f"{case.case_id}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        artifacts["screenshot"] = str(screenshot_path)
        attach_png_file(screenshot_path, "failure_screenshot")
        try:
            form_dom = form.get_form_dom_snapshot()
            if form_dom:
                attach_text("form_dom_snapshot", form_dom)
        except Exception:
            pass
        try:
            debug_state = form.collect_debug_state()
            if debug_state:
                attach_json("form_debug_state", debug_state)
        except Exception:
            pass
        raise
    finally:
        console.stop()
        recorder.stop()
        attach_json("cookies", context.cookies())
        attach_json("network_events", [event.__dict__ for event in recorder.events])
        if case.variant == "B":
            attach_json("network_b_endpoint_summary", recorder.build_b_endpoint_summary())
        attach_json("console_errors", console.errors)
        attach_json(
            "ab_tracking",
            {
                "ab_cookie": get_ab_cookie(context),
                "ym_uid": get_ym_uid_cookie(context),
            },
        )
        storage_path = tmp_path / f"{case.case_id}_storage_state.json"
        context.storage_state(path=str(storage_path))
        attach_text("storage_state_path", str(storage_path))
        artifacts.setdefault("storage_state", str(storage_path))
        submit_event = recorder.latest_submit_event()
        submit_network = None
        if submit_event is not None:
            submit_network = {
                "request_url": submit_event.url,
                "method": submit_event.method,
                "status": submit_event.status,
                "request_snippet": submit_event.request_snippet,
                "response_snippet": submit_event.response_snippet,
            }
        if application_json_store is not None:
            record = {
                "case_id": case.case_id,
                "site": case.site,
                "start_url": target_url,
                "measurement_url": target_url,
                "url_type": case.url_type,
                "url_before_city_change": url_before_city_change,
                "url_after_city_change": url_after_city_change,
                "url_after_submit": url_after_submit,
                "variant": case.variant,
                "testNewAddressPoisk_cookie": get_ab_cookie(context),
                "ym_uid": get_ym_uid_cookie(context),
                "form_key": case.form,
                "form_title": case.form_title,
                "expected_lead_form_type": case.expected_lead_form_type,
                "expected_order_site": case.expected_order_site,
                "address_version": case.address_version,
                "region_id": case.region_id,
                "region_selected_in_form": case.region,
                "expected_id_type": case.expected_id_type,
                "expected_id": case.expected_id,
                "street_query": case.street_query,
                "selected_street": selected_street,
                "house_query": case.house_query,
                "selected_house": selected_house,
                "phone": case.phone,
                "submit_time": submit_time,
                "url_success_markers": case.success_url_markers or [],
                "submit_success": submit_success,
                "success_criterion": success_criterion,
                "submit_network": submit_network,
                "artifacts": artifacts,
                "error": error_payload,
            }
            attach_json("application_record", record)
            if _should_append_application_record(submit_success):
                application_json_store.append(record)
                attach_json("applications_json_snapshot", application_json_store.read())
            else:
                attach_text(
                    "applications_json_skip_reason",
                    "Record is not appended because submit_success is false.",
                )


def _classify_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "_ym_uid" in text:
        return "ym_uid_missing"
    if "required form" in text or "форма" in text and "откры" in text:
        return "form_open_timeout"
    if "change region" in text or "смен" in text and "url" in text:
        return "url_changed_after_city_change"
    if "expected street in suggest" in text:
        return "street_not_found_in_suggest"
    if "expected house in suggest" in text:
        return "house_not_found_in_suggest"
    if "validate selected address id" in text:
        return "selected_address_id_mismatch"
    if "search_payload_mismatch" in text or "validate b search payload" in text:
        return "search_payload_mismatch"
    if "ввод номера телефона" in text or "phone" in text:
        return "phone_fill_failed"
    if "подготовка к отправке заявки" in text or "submit button" in text:
        return "submit_button_disabled"
    if "url after submit" in text or "success marker" in text:
        return "submit_success_marker_not_found"
    if "json" in text and "run_id" in text:
        return "application_json_run_id_mismatch"
    return "submit_application_scenario_failed"


def _failed_step_from_exception(exc: Exception) -> str:
    text = str(exc)
    if "Step:" in text:
        return text.split("Step:", 1)[1].splitlines()[0].strip()
    return "Выполнение submit-сценария iteration 2"


def run_regional_navigation_case(
    *,
    navigation_case,
    page,
    context,
    site_config,
    form_config,
    addresses_raw: list[dict],
    tmp_path: Path,
) -> None:
    target_url = site_config.urls[navigation_case.start_url_type]
    set_ab_cookie(context, target_url, navigation_case.variant)

    chain = site_config.regional_navigation_chain
    url_type_by_url = {url.rstrip("/"): url_type for url_type, url in site_config.urls.items()}
    by_region: dict[str, dict] = {}
    for raw in addresses_raw:
        if raw["variant"] != navigation_case.variant:
            continue
        by_region[raw["region"]] = raw

    landing = LandingPage(page, site_config)
    form = AddressForm(page, form_config)

    landing.open(navigation_case.start_url_type)
    initial_variant = wait_ab_cookie(context)
    assert initial_variant == navigation_case.variant, (
        f"Step: Start regional navigation\nExpected variant: {navigation_case.variant}\nActual: {initial_variant}"
    )

    for idx, step in enumerate(chain):
        expected_url = step.get("expected_url")
        expected_region = step.get("expected_region")
        step_name = step.get("step", f"step_{idx}")
        step_url_type = step.get("url_type")
        if not step_url_type and expected_url:
            step_url_type = url_type_by_url.get(expected_url.rstrip("/"))
        if not step_url_type:
            step_url_type = navigation_case.start_url_type

        if idx > 0 and expected_url:
            try:
                landing.select_region_from_page_navigation(expected_region or "")
            except Exception:
                page.goto(expected_url, wait_until="domcontentloaded")

        if expected_url:
            landing.assert_url_is_expected(expected_url)

        if expected_region:
            body_text = page.locator("body").inner_text().lower()
            assert expected_region.lower() in body_text, (
                f"Step: {step_name} region check\nExpected region text: {expected_region}\nActual page did not contain it"
            )

        # Skip search on initial no-region step.
        if idx == 0:
            assert_ab_cookie_not_changed(context, navigation_case.variant)
            continue

        # Find address fixture for this region or region alias.
        address_case = by_region.get(expected_region or "")
        if address_case is None and (expected_region or "").lower() == "домодедово":
            address_case = by_region.get("Домодедово")
        if address_case is None and (expected_region or "").lower() == "москва":
            address_case = by_region.get("Москва")
        if address_case is None and (expected_region or "").lower() == "балашиха":
            address_case = by_region.get("Балашиха")
        if address_case is None:
            # If we don't have exact mapped data for step region, continue with chain validation.
            assert_ab_cookie_not_changed(context, navigation_case.variant)
            continue

        form.open()
        if not form.is_present():
            is_required = _is_form_required_for_url(site_config, form_config, step_url_type)
            if not is_required:
                continue
            pytest.fail(f"Required form '{form_config.name}' is not present on regional step {step_name}")

        form.fill_street(address_case["street_query"])
        form.wait_street_suggest()
        form.assert_street_in_suggest(address_case["expected_street"])
        form.select_street(
            address_case["expected_street"],
            preferred_region=address_case["region"],
            allow_domodedovo_oblast_alias=(navigation_case.variant == "B"),
        )

        form.fill_house(address_case["house_query"])
        form.wait_house_suggest()
        form.assert_house_in_suggest(address_case["expected_house"])
        form.select_house(address_case["expected_house"])

        actual_id = form.get_selected_house_id()
        assert str(actual_id) == str(address_case["expected_id"]), (
            f"Step: {step_name} id check\nExpected ID: {address_case['expected_id']}\nActual ID: {actual_id}"
        )
        assert_ab_cookie_not_changed(context, navigation_case.variant)

    attach_json(
        "regional_navigation_summary",
        {
            "site": navigation_case.site,
            "variant": navigation_case.variant,
            "steps": [step.get("step") for step in chain],
        },
    )


def run_negative_search_case(
    *,
    case,
    page,
    context,
    site_config,
    form_config,
    tmp_path: Path,
) -> None:
    recorder = NetworkRecorder(page, case_id=case.case_id, variant=case.variant)
    console = ConsoleRecorder(page)
    landing = LandingPage(page, site_config)
    form = AddressForm(page, form_config)
    target_url = site_config.urls[case.url_type]

    try:
        set_ab_cookie(context, target_url, case.variant)
        recorder.start()
        console.start()

        landing.open(case.url_type)
        assert_ab_cookie_value(context, case.variant)

        form.open()
        if not form.is_present():
            is_required = _is_form_required_for_url(site_config, form_config, case.url_type)
            if not is_required:
                pytest.skip(
                    f"Optional form '{form_config.name}' is not present for case {case.pytest_id}"
                )
            pytest.fail(f"Required form '{form_config.name}' is not present for case {case.pytest_id}")

        form.fill_street(case.street_query)
        form.wait_street_suggest()
        street_found_for_forbidden_region = form.try_select_street(
            case.expected_street,
            preferred_region=case.region,
        )
        if not street_found_for_forbidden_region:
            return

        # Isolation check must be done on full address scope.
        # Street alone can legitimately exist in other data sources; failure is when
        # the forbidden house is also selectable for this street+region pair.
        form.fill_house(case.house_query)
        form.wait_house_suggest()
        form.assert_house_not_in_suggest(case.expected_house)
    except Exception:
        screenshot_path = tmp_path / f"{case.case_id}_negative.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        attach_png_file(screenshot_path, "failure_screenshot_negative")
        try:
            debug_state = form.collect_debug_state()
            if debug_state:
                attach_json("form_debug_state_negative", debug_state)
        except Exception:
            pass
        raise
    finally:
        console.stop()
        recorder.stop()
        attach_json("cookies", context.cookies())
        attach_json("network_events", [event.__dict__ for event in recorder.events])
        if case.variant == "B":
            attach_json("network_b_endpoint_summary", recorder.build_b_endpoint_summary())
        attach_json("console_errors", console.errors)
