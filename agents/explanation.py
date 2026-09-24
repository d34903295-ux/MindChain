"""Explanation Agent (Fase 1): ÚNICA pieza que llama al LLM (Claude).
Sin API key -> plantilla determinista (tests/offline). Con key -> Anthropic Messages API.
"""
import os, json, urllib.request

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

def _fallback(profile: dict, score: int, factors: list[str]) -> str:
    a = profile.get("address"); n = profile.get("tx_count", 0); age = profile.get("age_days")
    lvl = "bajo" if score < 30 else ("medio" if score < 70 else "alto")
    base = (f"Wallet {a} (Ethereum): {n} txs lifetime, antigüedad {age} días, "
            f"actividad {profile.get('activity')}, balance ${profile.get('balance_usd',0):,.2f}. "
            f"Riesgo {lvl} ({score}/100).")
    if not factors: return base + " Sin señales de riesgo en heurísticas actuales."
    detalle = {"wallet_nueva_pocas_txs": "poco historial: tratar con cautela hasta tener más actividad",
        "interaccion_mezclador_conocido": "paso por mezclador: dificulta trazabilidad, eleva riesgo",
        "concentracion_unica_fuente": "fondos desde una sola fuente: posible dependencia/fondeo directo",
        "patron_bot_alta_frecuencia": "patrón 24h uniforme de alta frecuencia: comportamiento automatizado",
        "dormante_reactivada": "wallet dormida reactivada: revisar motivo del retorno",
        "balance_alto_wallet_joven": "balance alto con corta edad: verificar origen de fondos" }
    return base + " Factores: " + "; ".join(detalle.get(f, f) for f in factors) + "."

def explain(profile: dict, score: int, factors: list[str]) -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return _fallback(profile, score, factors)
    try:
        payload = {"model": MODEL, "max_tokens": 300,
            "system": "Eres analista on-chain. Explica riesgo de forma neutra, sin acusar delitos. Español claro.",
            "messages": [{"role": "user", "content":
                f"Wallet {profile.get('address')} Ethereum. Perfil: {json.dumps(profile)[:1500]}. Score {score}/100. Factores: {factors}. Explica en 4-6 líneas qué significa y qué verificar."}]}
        req = urllib.request.Request("https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
        parts = d.get("content", [])
        txt = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        return txt or _fallback(profile, score, factors)
    except Exception:
        return _fallback(profile, score, factors)
