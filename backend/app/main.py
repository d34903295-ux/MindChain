from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.analyze import router as analyze_router
from app.routers.contract import router as contract_router

app = FastAPI(title="ChainMind API", version="0.2.0-fase2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(analyze_router)
app.include_router(contract_router)

@app.get("/health")
def health():
    return {"status": "ok", "fase": 2}

@app.get("/")
def root():
    return {"service": "chainmind-backend", "docs": "/docs"}
