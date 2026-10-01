$ErrorActionPreference="Stop"
$Root=Resolve-Path "$PSScriptRoot\.."; Set-Location $Root
if (!(Test-Path .env)) { Copy-Item .env.example .env }
py -3 -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12+ required'"
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\pip.exe install -r backend\requirements.txt
Push-Location frontend; npm install; Pop-Location
Push-Location backend; & ..\.venv\Scripts\alembic.exe upgrade head; Pop-Location
& .\.venv\Scripts\python.exe scripts\check_env.py
Write-Host "Setup complete. Run scripts\dev.ps1"
