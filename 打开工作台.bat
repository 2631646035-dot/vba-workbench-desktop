@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\start_workbench.ps1"
if errorlevel 1 pause
