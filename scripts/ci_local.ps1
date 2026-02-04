param(
    [string[]]$PythonVersions = @("3.10", "3.11"),
    [switch]$UseCurrent
)

$ErrorActionPreference = "Stop"

function Invoke-Ci {
    param(
        [string[]]$PythonCmd,
        [string]$Label
    )

    Write-Host "==> Running CI checks with $Label"

    & $PythonCmd -m pip install --upgrade pip
    & $PythonCmd -m pip install -e ".[dev]"

    & $PythonCmd -m ruff check src tests
    & $PythonCmd -m black --check src tests
    & $PythonCmd -m mypy src
    & $PythonCmd -m pytest --cov=src/bitegraph --cov-report=term-missing --cov-report=xml
}

if ($UseCurrent) {
    Invoke-Ci -PythonCmd @("python") -Label "python (PATH)"
    exit 0
}

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($null -eq $pyLauncher) {
    Write-Warning "py launcher not found; running with python on PATH"
    Invoke-Ci -PythonCmd @("python") -Label "python (PATH)"
    exit 0
}

foreach ($version in $PythonVersions) {
    $cmd = @("py", "-$version")
    try {
        & $cmd -c "import sys" | Out-Null
    } catch {
        Write-Warning "Python $version not found; skipping"
        continue
    }
    Invoke-Ci -PythonCmd $cmd -Label "Python $version"
}
