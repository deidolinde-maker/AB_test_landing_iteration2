import pytest

from components.address_form import AddressForm
from helpers.ab_cookie import assert_ab_cookie_value, set_ab_cookie
from pages.landing_page import LandingPage

pytestmark = [pytest.mark.e2e, pytest.mark.smoke, pytest.mark.form_open_smoke]


def test_form_open_smoke(case, page, context, site_config_map, form_config_map):
    site_config = site_config_map[case.site]
    form_config = form_config_map[case.form]
    landing = LandingPage(page, site_config)
    form = AddressForm(page, form_config)

    target_url = site_config.urls[case.url_type]
    set_ab_cookie(context, target_url, case.variant)
    landing.open(case.url_type)
    assert_ab_cookie_value(context, case.variant)

    form.open()
    assert form.is_present(), (
        f"Required form is not present for smoke open check: "
        f"site={case.site}, url_type={case.url_type}, form={case.form}, variant={case.variant}"
    )
