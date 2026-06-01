#!/usr/bin/env bash
set -euo pipefail

site="mts_internet_online"
url_type="all"
variant="all"
form="all"
pytest_bin="pytest"
python_bin="python"
fail_on_test_failures="true"
run_tag=""
dataset_filter="all"
case_id="all"
run_id="${BUILD_TAG:-}"
build_number="${BUILD_NUMBER:-local}"
applications_json_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) site="$2"; shift 2 ;;
    --url-type) url_type="$2"; shift 2 ;;
    --variant) variant="$2"; shift 2 ;;
    --form) form="$2"; shift 2 ;;
    --pytest) pytest_bin="$2"; shift 2 ;;
    --python) python_bin="$2"; shift 2 ;;
    --fail-on-test-failures) fail_on_test_failures="$2"; shift 2 ;;
    --run-tag) run_tag="$2"; shift 2 ;;
    --dataset-filter) dataset_filter="$2"; shift 2 ;;
    --case-id) case_id="$2"; shift 2 ;;
    --run-id) run_id="$2"; shift 2 ;;
    --build-number) build_number="$2"; shift 2 ;;
    --applications-json-path) applications_json_path="$2"; shift 2 ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

run_pytest() {
  if command -v "${pytest_bin}" >/dev/null 2>&1; then
    "${pytest_bin}" "$@"
    return
  fi
  "${python_bin}" -m pytest "$@"
}

if [[ -z "${run_tag}" ]]; then
  if [[ -n "${BUILD_NUMBER:-}" ]]; then
    run_tag="build_${BUILD_NUMBER}"
  else
    run_tag="$(date +%Y%m%d_%H%M%S)"
  fi
fi
if [[ -z "${run_id}" ]]; then
  run_id="testNewAddressPoisk_${run_tag}"
fi

datasets=(
  "submit_applications|tests/test_search_variant_a.py::test_search_variant_a tests/test_search_variant_b.py::test_search_variant_b"
  "form_open_smoke|tests/test_form_open_smoke.py::test_form_open_smoke"
  "json_store_smoke|tests/test_json_store_smoke.py::test_json_store_smoke_ensure_current_run_and_append"
  "submit_success_marker_smoke|tests/test_submit_success_marker_smoke.py::test_submit_success_marker_smoke"
  "mini_bug_report_smoke|tests/test_mini_bug_report_smoke.py::test_mini_bug_report_smoke_render_failed_case"
  "ab_cookie|tests/test_ab_cookie.py::test_ab_cookie_assigned_on_clean_context tests/test_ab_cookie.py::test_ab_cookie_persists_after_reload"
  "regional_navigation|tests/test_regional_navigation.py::test_regional_navigation_chain"
  "forbidden_region|tests/test_forbidden_region.py::test_forbidden_region_address_not_found"
  "isolation|tests/test_search_isolation.py::test_variant_a_does_not_find_v2_address tests/test_search_isolation.py::test_variant_b_does_not_find_v1_address"
  "adjacent|tests/test_adjacent_search.py::test_adjacent_search"
  "region_change|tests/test_region_change_inside_form.py::test_region_change_inside_form_does_not_change_url"
  "synonyms|tests/test_synonyms.py::test_synonym_search"
)

failed_runs=()
base_dir="artifacts/allure-results/${site}/datasets/${run_tag}"

for row in "${datasets[@]}"; do
  dataset_name="${row%%|*}"
  if [[ "${dataset_filter}" != "all" && "${dataset_name}" != "${dataset_filter}" ]]; then
    continue
  fi
  tests_part="${row#*|}"
  allure_dir="${base_dir}/${dataset_name}"
  mkdir -p "${allure_dir}"

  echo
  echo "=== RUN dataset=${dataset_name} site=${site} run_tag=${run_tag} ==="

  read -r -a tests <<< "${tests_part}"
  args=(
    -q
    -s
  )
  args+=("${tests[@]}")
  args+=(
    --run-e2e
    --site "${site}"
    --dataset "${dataset_name}"
    --url-type "${url_type}"
    --variant "${variant}"
    --form "${form}"
    --case-id "${case_id}"
    --run-id "${run_id}"
    --build-number "${build_number}"
    --alluredir "${allure_dir}"
  )
  if [[ -n "${applications_json_path}" ]]; then
    args+=(--applications-json-path "${applications_json_path}")
  fi

  set +e
  run_pytest "${args[@]}"
  exit_code=$?
  set -e
  if [[ ${exit_code} -ne 0 ]]; then
    failed_runs+=("dataset=${dataset_name} exit_code=${exit_code}")
    echo "RUN FAILED: dataset=${dataset_name} exit_code=${exit_code}"
  fi
done

echo
echo "Dataset suite run completed. run_tag=${run_tag}"

summary_out="artifacts/reports/${site}/datasets/${run_tag}/dataset_suite_summary.md"
echo "Building dataset summary -> ${summary_out}"
"${python_bin}" scripts/summarize_dataset_suite.py \
  --site "${site}" \
  --run-tag "${run_tag}" \
  --output "${summary_out}"

if [[ ${#failed_runs[@]} -gt 0 ]]; then
  echo
  echo "Failed dataset runs:"
  for item in "${failed_runs[@]}"; do
    echo " - ${item}"
  done
  if [[ "${fail_on_test_failures}" == "true" ]]; then
    exit 1
  fi
fi

exit 0
