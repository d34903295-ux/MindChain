import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

# `.env` estaba en requirements pero nunca se cargaba: escribirlo no hacía nada.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except Exception:
    pass

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth import requiere_clave, verificar
from app.routers.analyze import router as analyze_router
from app.routers.contract import router as contract_router
from app.routers.anomaly import router as anomaly_router
from app.routers.report import router as report_router
from app.routers.qr import router as qr_router
from app.routers.feed import router as feed_router
from app.routers.status import router as status_router
from app.routers.obsidian import router as obsidian_router
from app.routers.watchlist_router import router as watchlist_router
from app.routers.chat_router import router as chat_router
from app.routers.chat_router import SIN_CLAVE

app = FastAPI(title="ChainMind API", version="0.11.0-agentes")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(analyze_router)
app.include_router(contract_router)
app.include_router(anomaly_router)
app.include_router(report_router)
app.include_router(qr_router)
app.include_router(feed_router)
app.include_router(status_router)
app.include_router(obsidian_router)
app.include_router(watchlist_router)
app.include_router(chat_router)


@app.middleware("http")
async def exigir_clave(request, call_next):
    """Quien venga de fuera necesita una clave propia de ChainMind.

    El panel y los scripts de esta misma máquina no la llevan, así que el
    desarrollo local no se rompe. Las claves de los proveedores de IA no
    tienen nada que ver con esto y nunca se devuelven por la API.
    """
    ruta = request.url.path
    if request.method == "OPTIONS" or ruta in SIN_CLAVE or ruta.startswith("/docs"):
        return await call_next(request)
    host = request.client.host if request.client else ""
    if not requiere_clave(host):
        return await call_next(request)
    registro = verificar(request.headers.get("x-api-key", ""))
    if registro is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=401,
            content={"detail": "falta una clave válida de ChainMind",
                     "como_conseguirla": "desde la máquina donde corre: POST /keys",
                     "cabecera": "X-API-Key: cm_..."},
        )
    respuesta = await call_next(request)
    respuesta.headers["X-ChainMind-Key"] = registro.get("nombre", "")
    return respuesta


@app.on_event("startup")
def _startup():
    """Arranca el centinela de vigilancia si está habilitado."""
    try:
        from agents import sentinel
        sentinel.start()
    except Exception:
        pass


@app.on_event("shutdown")
def _shutdown():
    try:
        from agents import sentinel
        sentinel.stop()
    except Exception:
        pass

@app.get("/health")
def health():
    return {"status": "ok", "fase": 5}

@app.get("/")
def root():
    return {"service": "chainmind-backend", "docs": "/docs"}
