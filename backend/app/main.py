from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.analyze import router as analyze_router
from app.routers.contract import router as contract_router
from app.routers.anomaly import router as anomaly_router

app = FastAPI(title="ChainMind API", version="0.3.0-fase3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(analyze_router)
app.include_router(contract_router)
app.include_router(anomaly_router)

@app.get("/health")
def health():
    return {"status": "ok", "fase": 3}

@app.get("/")
def root():
    return {"service": "chainmind-backend", "docs": "/docs"}
