import pytest

from tests._search_flow import run_search_case

pytestmark = [pytest.mark.e2e, pytest.mark.submit_applications, pytest.mark.variant_b]


def test_search_variant_b(
    case,
    page,
    context,
    tmp_path,
    site_config_map,
    form_config_map,
    application_json_store,
    fail_on_missing_ym_uid,
):
    run_search_case(
        case=case,
        page=page,
        context=context,
        site_config=site_config_map[case.site],
        form_config=form_config_map[case.form],
        tmp_path=tmp_path,
        verify_v2_endpoints=True,
        application_json_store=application_json_store,
        fail_on_missing_ym_uid=fail_on_missing_ym_uid,
    )
