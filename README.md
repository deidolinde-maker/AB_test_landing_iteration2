# AB_test_landing_iteration2

Автотесты второй итерации A/B-теста `testNewAddressPoisk` для лендинга МТС Интернет.

Цель iteration 2: пройти пользовательский сценарий до отправки заявки, сохранить результат в общий JSON для iteration 3 и приложить диагностические артефакты в Allure.

## Что проверяет проект

- принудительный запуск variant `A` и `B` через cookie `testNewAddressPoisk`;
- открытие 4 URL: `no_region`, `moscow_subdomain`, `balashikha_folder`, `domodedovo_folder`;
- обязательные формы `checkaddress`, `connection`, `profit`;
- смену региона внутри формы без изменения URL;
- выбор улицы и дома из саджеста;
- ввод телефона `9999999999`;
- submit формы;
- успешную отправку по URL markers `/tilda/form1/submitted`, `/thanks`, `/thank_you_page`;
- запись только успешных submit-сценариев в JSON (`submit_success == true`);
- Allure artifacts: cookies, `_ym_uid`, network, console, screenshot/video, application record;
- mini bug report в Markdown и JSON при ошибке.

## Матрица

Основной dataset: `submit_applications`.

```text
4 URL x 3 forms x 2 variants = 24 pytest test items
```

Дополнительные диагностические dataset-ы:

- `form_open_smoke` — проверка открытия обязательных форм без submit;
- `json_store_smoke` — smoke проверка JSON-хранилища;
- `submit_success_marker_smoke` — smoke проверка success URL markers;
- `mini_bug_report_smoke` — smoke проверка генерации mini bug report.

Формат `case_id`:

```text
{site}__{url_type}__{form_key}__{variant}__{address_case_id}
```

Пример:

```text
mts_internet_online__moscow_subdomain__checkaddress__B__B_moscow_lipovy_park
```

## JSON для iteration 3

Путь по умолчанию:

```text
/var/lib/jenkins/shared/testNewAddressPoisk/testNewAddressPoisk_orders_data.json
```

Переопределение:

```bash
--applications-json-path=/custom/path.json
TESTNEWADDRESSPOISK_APPLICATIONS_JSON=/custom/path.json
```

JSON защищён lock-файлом и дописывается атомарно для совместимости с `pytest-xdist` и несколькими pytest-процессами одного Jenkins build.

## Локальный запуск

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Прогон всей submit-матрицы:

```bash
pytest -q -s tests/test_search_variant_a.py tests/test_search_variant_b.py \
  --run-e2e \
  --site mts_internet_online \
  --dataset submit_applications \
  --url-type all \
  --variant all \
  --form all \
  --applications-json-path ./artifacts/testNewAddressPoisk_orders_data.json \
  --alluredir artifacts/allure-results
```

Точечный кейс:

```bash
pytest -q -s tests/test_search_variant_b.py::test_search_variant_b \
  --run-e2e \
  --site mts_internet_online \
  --url-type moscow_subdomain \
  --variant B \
  --form checkaddress \
  --case-id mts_internet_online__moscow_subdomain__checkaddress__B__B_moscow_lipovy_park \
  --applications-json-path ./artifacts/testNewAddressPoisk_orders_data.json
```

## CLI-фильтры

- `--site`: `mts_internet_online`;
- `--dataset`: `submit_applications`;
- `--url-type`: `all|no_region|moscow_subdomain|balashikha_folder|domodedovo_folder`;
- `--variant`: `all|A|B`;
- `--form`: `all|checkaddress|connection|profit`;
- `--case-id`: полный `case_id` или `all`;
- `--applications-json-path`: путь общего JSON;
- `--run-id`: id запуска;
- `--build-number`: номер Jenkins build;
- `--fail-on-missing-ym-uid`: `true|false`;
- `--video-mode`: `off|on_failure|always`.

`domain_without_region` поддерживается как входной alias для старых команд, но канонический ключ iteration 2 — `no_region`.

## Jenkins

Pipeline описан в `Jenkinsfile`.

Основные режимы:

- `dataset_suite` — один dataset `submit_applications`;
- `form_matrix` — прогон submit-матрицы по URL/form/variant;
- `single_case` — запуск по CLI-фильтрам.

## Артефакты

- Allure results: `artifacts/allure-results/...`;
- summaries: `artifacts/reports/...`;
- mini bug report Markdown: `artifacts/reports/cases/<pytest_nodeid>.md`;
- mini bug report JSON: `artifacts/reports/cases/<pytest_nodeid>.json`;
- applications JSON: путь из `--applications-json-path` или runtime config.
