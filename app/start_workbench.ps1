param([switch]$PrepareOnly)
. (Join-Path $PSScriptRoot 'workbench_common.ps1')
try {
    $python = Get-WorkbenchPython
    if ($PrepareOnly) { Write-Host 'Environment ready.'; exit 0 }
    $pythonw = Join-Path (Split-Path $python -Parent) 'pythonw.exe'
    $entry = Join-Path $PSScriptRoot 'launch_workbench.py'
    $process = Start-Process -FilePath $pythonw -ArgumentList ('"' + $entry + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    Start-Sleep -Milliseconds 900
    if ($process.HasExited -and $process.ExitCode -ne 0) { throw 'The application could not start. See app\logs\startup.log.' }
    exit 0
} catch {
    Write-Host ('Startup failed: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
