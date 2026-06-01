import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.submit_success_marker_smoke]


def _detect_success_marker(url: str, markers: list[str]) -> str | None:
    for marker in markers:
        if marker in url:
            return marker
    return None


def test_submit_success_marker_smoke(loaded_config):
    markers = list(loaded_config.success_url_markers)
    assert markers == ["/tilda/form1/submitted", "/thanks", "/thank_you_page"]

    assert _detect_success_marker("https://example.test/thanks", markers) == "/thanks"
    assert (
        _detect_success_marker("https://example.test/tilda/form1/submitted?ok=1", markers)
        == "/tilda/form1/submitted"
    )
    assert _detect_success_marker("https://example.test/lead/sent", markers) is None
