"""Chat de ChainMind y gestión de claves de API."""
import pathlib
import sys

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import auth
from agents import chat

router = APIRouter()

# Rutas que nunca exigen clave: son de solo lectura y no devuelven datos de
# ninguna wallet. El resto sí, para que un tercero no pueda usarlas de Horse.
SIN_CLAVE = {
    "/status", "/chains", "/health", "/docs", "/openapi.json", "/",
    "/chat/herramientas", "/anomaly/latest",
}


class ChatRequest(BaseModel):
    mensaje: str = Field(min_length=1, max_length=2000)
    historial: list[dict] = Field(default_factory=list, max_length=12)


def _local(request: Request) -> bool:
    return auth.es_local(request.client.host if request.client else "")


@router.post("/chat")
def chat_endpoint(payload: ChatRequest):
    """Pregunta al sistema. Usa las mismas herramientas que los endpoints."""
    try:
        return chat.responder(payload.mensaje, payload.historial)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"chat falló: {type(e).__name__}")


@router.get("/chat/herramientas")
def chat_tools():
    """Qué puede hacer el chat. Para documentar integraciones."""
    return {"herramientas": chat.herramientas_publicas()}


class KeyRequest(BaseModel):
    nombre: str = Field(default="clave", max_length=40)
    ttl_dias: int | None = Field(default=None, ge=1, le=3650)


@router.post("/keys")
def create_key(payload: KeyRequest, request: Request):
    """Crea una clave de ChainMind. Solo desde localhost: se muestra una vez."""
    if not _local(request):
        raise HTTPException(status_code=403, detail="las claves solo se gestionan desde localhost")
    return auth.crear(payload.nombre, payload.ttl_dias)


@router.get("/keys")
def list_keys(request: Request):
    if not _local(request):
        raise HTTPException(status_code=403, detail="las claves solo se gestionan desde localhost")
    return {"claves": auth.listar()}


@router.delete("/keys/{nombre}")
def revoke_key(nombre: str, request: Request):
    if not _local(request):
        raise HTTPException(status_code=403, detail="las claves solo se gestionan desde localhost")
    return auth.revocar(nombre)
