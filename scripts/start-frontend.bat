@echo off
REM Inicia el frontend de ChainMind (Next.js) en 127.0.0.1:3000
REM Usa build de produccion: el watcher de Next dev es inestable en esta ruta de Windows.
cd /d "%~dp0..\frontend"
if not exist ".next\BUILD_ID" (
  echo [ChainMind] Generando build de produccion...
  call "C:\Program Files\nodejs\npm.cmd" run build
)
call "C:\Program Files\nodejs\npm.cmd" run start -- -H 127.0.0.1 -p 3000
