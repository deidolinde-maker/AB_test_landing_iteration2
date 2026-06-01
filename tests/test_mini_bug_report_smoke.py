from types import SimpleNamespace

import pytest

import conftest

pytestmark = [pytest.mark.smoke, pytest.mark.mini_bug_report_smoke]


def test_mini_bug_report_smoke_render_failed_case():
    case = SimpleNamespace(
        case_id="smoke_case",
        site="mts_internet_online",
        url_type="no_region",
        form="checkaddress",
        variant="B",
        dataset="submit_applications",
        expected_street="Липовый парк",
        expected_house="2",
        expected_id=1067,
        expected_id_type="house_id",
        street_query="Липовый парк",
        house_query="2",
        phone="9999999999",
        expected_lead_form_type="forma_proverit'_adress",
    )
    item = SimpleNamespace(nodeid="tests/test_dummy.py::test_case", name="test_case", funcargs={"case": case})
    report = SimpleNamespace(failed=True, passed=False, skipped=False, longreprtext="AssertionError: expected streets request")

    text_report = conftest._render_case_mini_report(item, report)
    json_report = conftest._render_case_mini_report_json(item, report)

    assert "smoke_case" in text_report
    assert "Ожидаемый результат" in text_report
    assert json_report["case_id"] == "smoke_case"
    assert json_report["error_code"] == "pytest_failure"
    assert json_report["variant"] == "B"
