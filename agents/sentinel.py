"""Centinela: vigilancia autónoma 24/7.

Por qué existe: el vigilante solo reactionaba cuando alguien abría el panel.
La promesa del producto es "los agentes vigilan solos", así que aquí hay un
proceso en segundo plano que:

  1. lee bloques nuevos por cadena (sin repetir: recuerda el último bloque)
  2. puntúa cada transacción con los agentes
  3. entrega las alertas nuevas por Telegram (una sola vez por hash)
  4. las deja escritas en el vault de Obsidian
  5. expone su estado en /status para poder auditarlo

Reglas duras:
- nunca lanza: cualquier fallo se registra y el ciclo siguiente reintenta
- no spamea: dedupe por hash (agents.watcher) + cooldown por cadena
- apagado por defecto: se activa con CHAINMIND_SENTINEL=1
"""
import os
import threading
import time
import traceback

from . import alerts
from . import obsidian, watcher
from .chains import supported

INTERVAL = int(os.getenv("CHAINMIND_SENTINEL_INTERVAL", "60"))
CHAINS = [c.strip() for c in os.getenv("CHAINMIND_SENTINEL_CHAINS", "ethereum,base").split(",") if c.strip()]
MIN_NEW_ALERTS = int(os.getenv("CHAINMIND_SENTINEL_MIN_ALERTS", "1"))
COOLDOWN_S = int(os.getenv("CHAINMIND_SENTINEL_COOLDOWN", "900"))

state = {
    "enabled": False,
    "running": False,
    "cycles": 0,
    "alerts_found": 0,
    "alerts_delivered": 0,
    "last_block": {},
    "last_run": None,
    "last_error": None,
    "chains": [],
    "started_at": None,
}

_lock = threading.Lock()
_stop = threading.Event()


def is_enabled() -> bool:
    return os.getenv("CHAINMIND_SENTINEL", "0") == "1"


def _notify(tx: dict, chain: str) -> dict:
    """Entrega una alerta: Telegram (si configurado) + Obsidian (si hay vault)."""
    from .explanation import flag_text

    flags = ", ".join(flag_text(f) for f in (tx.get("flags") or [])) or "sin señal detail"
    resumen = (
        f"ChainMind · {chain} · bloque {tx.get('block', 'n/d')}\n"
        f"{tx.get('value_eth', 0)} ETH · score {tx.get('score', 0)}/100\n"
        f"{tx.get('from', '')[:12]}… → {(tx.get('to') or 'nuevo contrato')[:12]}…\n"
        f"{flags}"
    )
    tg = alerts.send_telegram(resumen)
    ob = {}
    try:
        ob = obsidian.sync_alert(tx, chain)
    except Exception as e:
        ob = {"written": False, "reason": str(e)[:60]}
    return {"telegram": tg, "obsidian": bool(ob.get("written")), "summary": resumen}


def run_cycle() -> dict:
    """Un ciclo de vigilancia sobre todas las cadenas configuradas."""
    result = {"chains": {}, "delivered": 0, "new_alerts": 0}
    chains = [c for c in CHAINS if c in supported()]
    for chain in chains:
        try:
            since = state["last_block"].get(chain)
            feed = watcher.scan(chain, since=since, max_blocks=1)
            state["last_block"][chain] = feed.get("latest")
            new_alerts = feed.get("new_alerts") or []
            digest = {}
            try:
                digest = obsidian.sync_daily_digest(feed)
            except Exception as e:
                digest = {"written": False, "reason": str(e)[:60]}
            result["chains"][chain] = {
                "latest": feed.get("latest"),
                "txs": feed.get("n_txs"),
                "alerts": feed.get("n_alerts"),
                "new": len(new_alerts),
                "digest": bool(digest.get("written")),
            }
            if len(new_alerts) >= MIN_NEW_ALERTS:
                last_sent = state.get("_cooldown", {}).get(chain, 0)
                if time.time() - last_sent >= COOLDOWN_S:
                    for tx in new_alerts[:5]:
                        delivery = _notify(tx, chain)
                        result["delivered"] += 1
                        state["alerts_delivered"] += 1
                        if delivery["telegram"].get("sent"):
                            result["new_alerts"] += 1
                    state.setdefault("_cooldown", {})[chain] = time.time()
                else:
                    result["chains"][chain]["cooldown"] = True
        except Exception as e:
            result["chains"][chain] = {"error": str(e)[:120]}
            state["last_error"] = f"{chain}: {str(e)[:140]}"
    return result


def _loop():
    state["started_at"] = time.time()
    while not _stop.is_set():
        started = time.time()
        try:
            # OJO: la existencia del hilo ES la guarda. Usar `running` como
            # condición hacía que start() (que la pone a True) bloquease el ciclo.
            with _lock:
                state["running"] = True
                run_cycle()
                state["cycles"] += 1
                state["last_run"] = time.time()
            state["last_error"] = None
        except Exception:
            state["last_error"] = traceback.format_exc(limit=2)[-200:]
        elapsed = time.time() - started
        _stop.wait(max(5.0, INTERVAL - elapsed))
    state["running"] = False


def start():
    if not is_enabled():
        return {"started": False, "reason": "desactivado (CHAINMIND_SENTINEL != 1)"}
    if state["enabled"]:
        return {"started": False, "reason": "ya-en-ejecucion"}
    state.update({"enabled": True, "running": True, "chains": [c for c in CHAINS if c in supported()]})
    threading.Thread(target=_loop, name="chainmind-sentinel", daemon=True).start()
    return {"started": True, "interval_s": INTERVAL, "chains": state["chains"]}


def stop():
    _stop.set()
    state["enabled"] = False
    return {"stopped": True}


def status() -> dict:
    with _lock:
        snap = {k: v for k, v in state.items() if not k.startswith("_")}
    snap["interval_s"] = INTERVAL
    snap["cooldown_s"] = COOLDOWN_S
    snap["telegram_configured"] = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
    return snap
