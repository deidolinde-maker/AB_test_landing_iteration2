param(
    [string]$Site = "mts_internet_online",
    [string]$UrlType = "all",
    [string]$Variant = "all",
    [string]$Form = "all",
    [string]$Pytest = "pytest",
    [string[]]$PytestExtraArgs = @(),
    [string]$Python = "python",
    [bool]$FailOnTestFailures = $true,
    [string]$RunTag = "",
    [string]$DatasetFilter = "all",
    [string]$CaseId = "all",
    [string]$RunId = "",
    [string]$BuildNumber = "",
    [string]$ApplicationsJsonPath = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RunTag)) {
    if ($env:BUILD_NUMBER) {
        $RunTag = "build_$($env:BUILD_NUMBER)"
    } else {
        $RunTag = (Get-Date -Format "yyyyMMdd_HHmmss")
    }
}
if ([string]::IsNullOrWhiteSpace($RunId)) {
    if ($env:BUILD_TAG) {
        $RunId = $env:BUILD_TAG
    } else {
        $RunId = "testNewAddressPoisk_$RunTag"
    }
}
if ([string]::IsNullOrWhiteSpace($BuildNumber)) {
    if ($env:BUILD_NUMBER) {
        $BuildNumber = $env:BUILD_NUMBER
    } else {
        $BuildNumber = "local"
    }
}

$datasets = @(
    @{
        Name = "submit_applications"
        Tests = @(
            "tests/test_search_variant_a.py::test_search_variant_a",
            "tests/test_search_variant_b.py::test_search_variant_b"
        )
    }
)

$failedRuns = @()
$baseDir = "artifacts/allure-results/$Site/datasets/$RunTag"

foreach ($dataset in $datasets) {
    $datasetName = $dataset.Name
    if ($DatasetFilter -ne "all" -and $datasetName -ne $DatasetFilter) {
        continue
    }
    $allureDir = "$baseDir/$datasetName"
    New-Item -ItemType Directory -Path $allureDir -Force | Out-Null

    Write-Host ""
    Write-Host "=== RUN dataset=$datasetName site=$Site run_tag=$RunTag ==="

    $args = @(
        "-q",
        "-s"
    )
    if ($PytestExtraArgs.Count -gt 0) {
        $args += $PytestExtraArgs
    }
    $args += $dataset.Tests
    $args += @(
        "--run-e2e",
        "--site", $Site,
        "--dataset", $datasetName,
        "--url-type", $UrlType,
        "--variant", $Variant,
        "--form", $Form,
        "--case-id", $CaseId,
        "--run-id", $RunId,
        "--build-number", $BuildNumber,
        "--alluredir", $allureDir
    )
    if (-not [string]::IsNullOrWhiteSpace($ApplicationsJsonPath)) {
        $args += @("--applications-json-path", $ApplicationsJsonPath)
    }

    & $Pytest @args
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        $failedRuns += "dataset=$datasetName exit_code=$exitCode"
        Write-Host "RUN FAILED: dataset=$datasetName exit_code=$exitCode"
    }
}

Write-Host ""
Write-Host "Dataset suite run completed. run_tag=$RunTag"

$summaryOut = "artifacts/reports/$Site/datasets/$RunTag/dataset_suite_summary.md"
Write-Host "Building dataset summary -> $summaryOut"
& $Python scripts/summarize_dataset_suite.py `
    --site $Site `
    --run-tag $RunTag `
    --output $summaryOut

$summaryExitCode = $LASTEXITCODE
if ($summaryExitCode -ne 0) {
    Write-Host "Dataset summary build failed with exit code $summaryExitCode"
    exit $summaryExitCode
}

if ($failedRuns.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed dataset runs:"
    $failedRuns | ForEach-Object { Write-Host " - $_" }
    if ($FailOnTestFailures) {
        exit 1
    }
}

exit 0
