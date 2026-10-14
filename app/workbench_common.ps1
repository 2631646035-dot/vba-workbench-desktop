$ErrorActionPreference = 'Stop'
function Get-WorkbenchPython {
    $root = $PSScriptRoot
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        $base = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*\WindowsApps\*' } | Select-Object -First 1
        $basePath = if ($base) { $base.Source } else { $null }
        if (-not $basePath) {
            $py = Get-Command py.exe -ErrorAction SilentlyContinue
            if ($py) { $basePath = (& $py.Source -3 -c 'import sys; print(sys.executable)' | Select-Object -Last 1) }
        }
        if (-not $basePath -or -not (Test-Path -LiteralPath $basePath)) { throw 'Python was not found. Install Python 3.12 with Add Python to PATH enabled.' }
        Write-Host 'Preparing the local application environment...'
        & $basePath -m venv --system-site-packages (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
    }
    & $python -c "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ['PySide6','yaml','openpyxl','requests','keyring']) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Installing missing dependencies. Keep this window open until setup finishes.'
        $logs = Join-Path $root 'logs'
        $null = New-Item -ItemType Directory -Path $logs -Force
        & $python -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements.txt') 2>&1 | Tee-Object -FilePath (Join-Path $logs 'setup.log') | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. See app\logs\setup.log.' }
    }
    & $python -c 'import PySide6, yaml, openpyxl, requests, keyring'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency validation failed.' }
    return $python
}
