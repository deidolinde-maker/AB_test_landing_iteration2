from __future__ import annotations

import re
import shutil
import uuid
import json
from pathlib import Path

import pytest

from helpers.application_json_store import ApplicationJsonStore
from helpers.config_loader import load_config
from helpers.test_case_factory import main_search_cases, synonym_cases


PYTEST_ID_PATTERN = re.compile(
    r"^[a-z0-9_]+__[a-z0-9_]+__[a-z_]+__[AB]__[A-Za-z0-9_]+(?:__.+)?$"
)


def test_yaml_validation_fails_fast_on_missing_required_key():
    src = Path(__file__).resolve().parents[1] / "config"
    dst = Path.cwd() / f"_tmp_config_copy_{uuid.uuid4().hex}"
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)

    sites_path = dst / "sites.yaml"
    original = sites_path.read_text(encoding="utf-8")
    sites_path.write_text(original.replace("sites:", "sites_broken:", 1), encoding="utf-8")

    try:
        with pytest.raises(ValueError, match="sites.yaml is missing required keys: sites"):
            load_config(dst)
    finally:
        shutil.rmtree(dst, ignore_errors=True)


def test_main_search_case_ids_are_unique_and_stable_format(loaded_config):
    for variant in ("A", "B"):
        cases = main_search_cases(loaded_config, variant)
        ids = [case.pytest_id for case in cases]
        assert len(ids) == 12
        assert len(ids) == len(set(ids))
        assert all(PYTEST_ID_PATTERN.match(case_id) for case_id in ids)
        assert all(case.dataset == "submit_applications" for case in cases)
        assert all(case.phone == "9999999999" for case in cases)


def test_only_required_iteration_two_forms_are_generated(loaded_config):
    cases = main_search_cases(loaded_config, "A") + main_search_cases(loaded_config, "B")
    assert {case.form for case in cases} == {"checkaddress", "connection", "profit"}


def test_application_json_store_initializes_and_appends(tmp_path):
    path = tmp_path / "orders.json"
    store = ApplicationJsonStore(path, run_id="run_1", build_number="42")
    store.initialize()
    store.append({"case_id": "case_1", "submit_success": True})

    payload = store.read()
    assert payload["run_id"] == "run_1"
    assert payload["build_number"] == "42"
    assert payload["source_iteration"] == "iteration_2_applications"
    assert payload["applications"] == [{"case_id": "case_1", "submit_success": True}]


def test_iteration_two_contract_files_are_present_and_parseable():
    root = Path(__file__).resolve().parents[1]
    for rel_path in (
        "schemas/jenkins_applications.schema.json",
        "schemas/mini_bug_report.schema.json",
    ):
        payload = json.loads((root / rel_path).read_text(encoding="utf-8"))
        assert payload["type"] == "object"
        assert payload.get("required")

    template = (root / "templates/mini_bug_report.md.j2").read_text(encoding="utf-8")
    assert "{{ error_code }}" in template
    assert "{{ case_id }}" in template


def test_synonym_dataset_has_cases_for_real_addresses(loaded_config):
    cases = synonym_cases(loaded_config)
    assert cases, "synonym_cases should not be empty for current config"
