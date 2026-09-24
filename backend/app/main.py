import asyncio
import contextlib
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.analyze import router as analyze_router
from app.routers.contract import router as contract_router
from app.routers.anomaly import router as anomaly_router
from app.routers.report import router as report_router
from app.routers.qr import router as qr_router
from app.routers.feed import router as feed_router
from app.routers.status import router as status_router
from app.routers.obsidian import router as obsidian_router

app = FastAPI(title="ChainMind API", version="0.9.0-sentinel")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(analyze_router)
app.include_router(contract_router)
app.include_router(anomaly_router)
app.include_router(report_router)
app.include_router(qr_router)
app.include_router(feed_router)
app.include_router(status_router)
app.include_router(obsidian_router)


@app.on_event("startup")
def _startup():
    """Arranca el centinela de vigilancia si está habilitado."""
    import sys, pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
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
