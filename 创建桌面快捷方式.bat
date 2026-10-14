@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\create_shortcut.ps1"
if errorlevel 1 pause
