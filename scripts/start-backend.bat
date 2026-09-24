@echo off
REM Inicia la API de ChainMind (FastAPI) en 127.0.0.1:8000
cd /d "%~dp0..\backend"
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> "%TEMP%\chainmind_backend.log" 2>&1
