@echo off
REM Inicia la API de ChainMind (FastAPI)
REM Bind por defecto: solo esta maquina (127.0.0.1).
REM Para exponerla en la red: set CHAINMIND_BIND=0.0.0.0 antes de lanzar.
REM OJO: al exponerla, la API key deja de ser opcional para quien venga de
REM fuera. El sistema ya la exige (ver backend/app/main.py).
set "BIND=%CHAINMIND_BIND%"
if "%BIND%"=="" set "BIND=127.0.0.1"
cd /d "%~dp0..\backend"
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host %BIND% --port 8000 >> "%TEMP%\chainmind_backend.log" 2>&1
