from helpers.application_json_store import ApplicationJsonStore

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.json_store_smoke]


def test_json_store_smoke_ensure_current_run_and_append(tmp_path):
    path = tmp_path / "applications.json"
    store = ApplicationJsonStore(path, run_id="run_smoke", build_number="123")
    store.ensure_current_run()
    store.append({"case_id": "smoke_case_1", "submit_success": True})

    payload = store.read()
    assert payload["run_id"] == "run_smoke"
    assert payload["build_number"] == "123"
    assert payload["applications"] == [{"case_id": "smoke_case_1", "submit_success": True}]
