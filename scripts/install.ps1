[CmdletBinding()]
param(
    [switch]$RunTests
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            $pythonCommand = 'py'
            $pythonArgs = @('-3')
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            $pythonCommand = 'python'
            $pythonArgs = @()
        } else {
            throw 'Python 3.11+ was not found. Install 64-bit Python and run this script again.'
        }
        & $pythonCommand @pythonArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) and sys.maxsize > 2**32 else 1)'
        if ($LASTEXITCODE -ne 0) { throw '64-bit Python 3.11+ is required.' }
        & $pythonCommand @pythonArgs -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv.' }
    }

    & $venvPython -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) and sys.maxsize > 2**32 else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Existing .venv requires 64-bit Python 3.11+. Use a fresh checkout.' }
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Failed to update pip. Check your network connection.' }
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the pip output above.' }
    & $venvPython scripts/check_install.py
    if ($LASTEXITCODE -ne 0) { throw 'Installation smoke check failed.' }

    if ($RunTests) {
        $previousQtPlatform = $env:QT_QPA_PLATFORM
        try {
            $env:QT_QPA_PLATFORM = 'offscreen'
            & $venvPython -m pytest -q
            if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
        } finally {
            $env:QT_QPA_PLATFORM = $previousQtPlatform
        }
    }
    Write-Output 'Petri-Dish-Processor installation verified. Start with: .\.venv\Scripts\python.exe app.py'
} finally {
    Pop-Location
}
