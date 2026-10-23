# Builds dist\TaskForge.exe. Usage: powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -q -r requirements.txt pyinstaller pillow
python tools\make_icon.py
python -m PyInstaller --noconfirm --clean --onefile --windowed --name TaskForge `
  --icon assets\taskforge.ico --version-file tools\version_info.txt run.py
Write-Host "Built: $PSScriptRoot\dist\TaskForge.exe"
