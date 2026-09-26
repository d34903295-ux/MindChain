"""Alertas Telegram (Fase 5). Best-effort: nunca rompe el análisis.
Config: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID.
"""
import os, json, urllib.request

RISK_THRESHOLD = int(os.getenv("TELEGRAM_RISK_THRESHOLD", "70"))

def _post(url, payload, timeout=8):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json", "User-Agent": "ChainMind/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def send_telegram(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return {"sent": False, "reason": "sin-config"}
    try:
        _post("https://api.telegram.org/bot" + token + "/sendMessage",
              {"chat_id": chat, "text": text[:3500]})
        return {"sent": True, "reason": "ok"}
    except Exception as e:
        return {"sent": False, "reason": str(e)[:200]}

def alert_if_risky(kind, address, chain, score, factors):
    if score is None:
        # Abstención (muestra insuficiente): no es un error, es "no evaluable".
        # Sin esta guarda, int(None) caía en el except y la razón que se
        # reportaba era "error-interno", que no es lo que pasó.
        return {"sent": False, "reason": "sin-score-no-evaluable"}
    try:
        if int(score) < RISK_THRESHOLD:
            return {"sent": False, "reason": "bajo-umbral"}
        msg = ("ChainMind alerta [" + kind + "] " + chain + " " + address
               + " score " + str(score) + "/100: " + ", ".join(factors or []))
        return send_telegram(msg)
    except Exception:
        return {"sent": False, "reason": "error-interno"}
