. (Join-Path $PSScriptRoot 'workbench_common.ps1')
try {
    $python = Get-WorkbenchPython
    $pythonw = Join-Path (Split-Path $python -Parent) 'pythonw.exe'
    $desktop = [Environment]::GetFolderPath('Desktop')
    $name = 'VBA' + [char]0x5DE5 + [char]0x4F5C + [char]0x53F0 + '.lnk'
    $target = Join-Path $desktop $name
    $shell = New-Object -ComObject WScript.Shell
    $hotkey = 'CTRL+ALT+V'
    foreach ($file in (Get-ChildItem -LiteralPath $desktop -Filter '*.lnk')) {
        if ($file.FullName -ne $target -and $shell.CreateShortcut($file.FullName).Hotkey -eq $hotkey) {
            $hotkey = ''; Write-Host 'Ctrl+Alt+V is already assigned. Set another shortcut key in Properties.'; break
        }
    }
    if (Test-Path -LiteralPath $target) {
        $backup = Join-Path $PSScriptRoot 'logs'
        $null = New-Item -ItemType Directory -Path $backup -Force
        Copy-Item -LiteralPath $target -Destination (Join-Path $backup ('previous_shortcut_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.lnk'))
    }
    $shortcut = $shell.CreateShortcut($target)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = '"' + (Join-Path $PSScriptRoot 'launch_workbench.py') + '"'
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.IconLocation = (Join-Path $PSScriptRoot 'assets\workbench_shortcut_v1.ico') + ',0'
    $shortcut.Description = 'VBA Workbench'
    $shortcut.Hotkey = $hotkey
    $shortcut.Save()
    Write-Host ('Desktop shortcut created: ' + $target)
    Write-Host ('Shortcut key: ' + $hotkey)
    exit 0
} catch {
    Write-Host ('Could not create shortcut: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
