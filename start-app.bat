@echo off
rem Football Value Analytics - start backend + public tunnel.
rem The public URL appears in the "tunnel" window (https://....trycloudflare.com).
rem NOTE: the URL changes on every start (free quick tunnel).

cd /d "%~dp0backend"
start "FVA backend" .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
timeout /t 5 /nobreak >nul
start "FVA tunnel" "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8000
echo.
echo Backend: http://localhost:8000
echo Public URL: see the "FVA tunnel" window (https://....trycloudflare.com)
pause
