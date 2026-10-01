$ErrorActionPreference="Stop"
$Root=Resolve-Path "$PSScriptRoot\.."; Set-Location $Root
if (!(Test-Path .env)) { Copy-Item .env.example .env }
$backend=Start-Process -PassThru -NoNewWindow powershell -ArgumentList "-NoExit","-Command","cd '$Root\backend'; & '$Root\.venv\Scripts\uvicorn.exe' app.main:app --reload --host 0.0.0.0 --port 8000"
$frontend=Start-Process -PassThru -NoNewWindow powershell -ArgumentList "-NoExit","-Command","cd '$Root\frontend'; npm run dev"
Write-Host "Backend PID $($backend.Id), frontend PID $($frontend.Id). Ctrl+C in both child terminals to stop."
