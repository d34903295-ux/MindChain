"""Obsidian vault sync: ChainMind escribe notas y lee las anotaciones del analista.

Por qué esta integración y no un "dump" de Markdown:

1. No destruye trabajo humano. Todo lo que escribimos va entre marcadores
   `<!-- chainmind:start -->` / `<!-- chainmind:end -->` y en un bloque de
   frontmatter propio. Si editas la nota a mano, se conserva.
2. El vault es la memoria del analista. Las etiquetas y notas que escribas
   (`cm_status`, `cm_owner`, etc.) se leen de vuelta y se muestran en ChainMind.
3. Convierte el vault en un grafo real: las wallets, contratos y alertas se
   enlazan con wikilinks, así que el Graph view de Obsidian tiene sentido.

Vault por defecto: el que declara Obsidian en %APPDATA%/obsidian/obsidian.json,
o la variable CHAINMIND_OBSIDIAN_VAULT.
"""
import datetime
import json
import os
import pathlib
import re
import time

import yaml

from .explanation import _factor_text, flag_text

ROOT_DIRNAME = "ChainMind"
START = "<!-- chainmind:start -->"
END = "<!-- chainmind:end -->"
SCHEMA_VERSION = 1
# Campos que gestiona ChainMind en el frontmatter (el resto es del usuario)
CM_FIELDS = ("cm_schema", "cm_address", "cm_chain", "cm_kind", "cm_risk_score",
             "cm_risk_level", "cm_factors", "cm_sample_confidence", "cm_tx_count",
             "cm_age_days", "cm_activity", "cm_source", "cm_last_analyzed", "cm_tags")

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


# --------------------------------------------------------------------- vault
def detect_vault() -> str | None:
    """Vault explícito > configuración de Obsidian > None."""
    env = os.getenv("CHAINMIND_OBSIDIAN_VAULT", "").strip()
    if env:
        return env
    cfg = pathlib.Path(os.getenv("APPDATA", "")) / "obsidian" / "obsidian.json"
    try:
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            vaults = data.get("vaults") or {}
            for info in vaults.values():
                path = info.get("path")
                if path and pathlib.Path(path).is_dir():
                    return path
    except Exception:
        return None
    return None


def vault_root() -> pathlib.Path | None:
    v = detect_vault()
    if not v:
        return None
    root = pathlib.Path(v) / ROOT_DIRNAME
    return root


def safe_name(value: str, maxlen: int = 60) -> str:
    """Nombre de archivo seguro: nada de rutas, separadores ni `..`."""
    s = SAFE_NAME.sub("-", str(value))
    s = s.replace("..", ".").replace(".", "", 2) if s.startswith("..") else s
    s = re.sub(r"\.{2,}", ".", s).strip("-.")
    return (s[:maxlen] or "sin-nombre")


def status() -> dict:
    root = vault_root()
    configured = bool(os.getenv("CHAINMIND_OBSIDIAN_VAULT", "").strip())
    detected = detect_vault()
    out = {
        "configured": configured,
        "vault_detected": detected,
        "root": str(root) if root else None,
        "exists": bool(root and root.is_dir()),
        "auto_export": os.getenv("CHAINMIND_OBSIDIAN_AUTO", "0") == "1",
        "notes": {},
    }
    if root and root.is_dir():
        for sub in ("wallets", "contracts", "alerts", "daily"):
            d = root / sub
            out["notes"][sub] = len(list(d.glob("*.md"))) if d.is_dir() else 0
    return out


# ---------------------------------------------------------------- frontmatter
def split_note(text: str) -> tuple[dict, str]:
    """Separa frontmatter YAML y cuerpo. Devuelve ({}, texto) si no hay."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return {}, text
    try:
        meta = yaml.safe_load(parts[0][3:].strip()) or {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    return meta, parts[1].lstrip("\n")


def dump_frontmatter(meta: dict) -> str:
    clean = {k: v for k, v in meta.items() if v is not None}
    body = yaml.safe_dump(clean, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{body}---\n\n"


def merge_block(existing: str, generated: str) -> str:
    """Reemplaza solo nuestro bloque; conserva lo que el usuario escribió fuera.

    Determinista: el espacio en blanco se normaliza para que reescribir la misma
    nota produzca un archivo idéntico. Sin esto, cada sync generaba un salto de
    línea nuevo y Obsidian reindexaba el vault entero.
    """
    if START in existing and END in existing:
        i = existing.index(START)
        j = existing.index(END) + len(END)
        before = existing[:i].rstrip()
        after = existing[j:].lstrip("\n").rstrip()
    else:
        before = existing.rstrip()
        after = ""
    parts = [before, f"{START}\n{generated.strip()}\n{END}"]
    if after:
        parts.append(after)
    return "\n\n".join(p for p in parts if p) + "\n"


def write_note(path: pathlib.Path, meta: dict, block: str) -> dict:
    """Escribe la nota solo si cambió. Nunca toca notas fuera de la raíz ChainMind."""
    root = vault_root()
    if root is None:
        return {"written": False, "reason": "sin-vault-configurado"}
    try:
        path = path.resolve()
        root_res = root.resolve()
        if root_res not in path.parents:
            return {"written": False, "reason": "ruta-fuera-del-vault"}
    except Exception as e:
        return {"written": False, "reason": str(e)[:60]}

    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    old_meta, old_body = split_note(old)
    merged = dict(old_meta)
    for k in CM_FIELDS:
        merged.pop(k, None)
    merged.update({k: v for k, v in meta.items() if v is not None})

    new_text = dump_frontmatter(merged) + merge_block(old_body, block)
    if old == new_text:
        return {"written": False, "reason": "sin-cambios", "path": str(path)}

    # Churn control: si lo único que cambia es la hora, no reescribimos.
    # Si no, cada sync provocaría una reindexación del vault en Obsidian.
    if old and _same_except_timestamp(old_meta, merged) and old_body.strip() == merge_block(old_body, block).strip():
        old_ts = old_meta.get("cm_last_analyzed")
        if isinstance(old_ts, str) and (time.time() - _parse_ts(old_ts)) < FRESH_SECONDS:
            return {"written": False, "reason": "sin-cambios-salvo-hora", "path": str(path)}

    path.write_text(new_text, encoding="utf-8")
    return {"written": True, "path": str(path), "bytes": len(new_text.encode("utf-8"))}


FRESH_SECONDS = 1800  # 30 min: tras eso sí refrescamos la hora


def _parse_ts(value: str) -> float:
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=datetime.timezone.utc).timestamp()
    except Exception:
        return 0.0


def _same_except_timestamp(a: dict, b: dict) -> bool:
    ca = {k: v for k, v in (a or {}).items() if k != "cm_last_analyzed"}
    cb = {k: v for k, v in (b or {}).items() if k != "cm_last_analyzed"}
    return ca == cb


# ------------------------------------------------------------------- entities
def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _level(score) -> str:
    if score is None:
        return "no-evaluable"
    return "bajo" if score < 30 else ("medio" if score < 70 else "alto")


def _body(lines: list[str]) -> str:
    return "\n".join(lines)


def sync_wallet(wallet_report: dict, extra: dict | None = None) -> dict:
    """Crea/actualiza la nota de una wallet. `wallet_report` es la respuesta de /analyze-wallet."""
    root = vault_root()
    if root is None:
        return {"written": False, "reason": "sin-vault-configurado"}
    addr = str(wallet_report.get("address", ""))
    p = wallet_report.get("profile", {}) or {}
    score = wallet_report.get("risk_score")
    note = root / "wallets" / f"{safe_name(addr)}.md"
    facts = [
        f"**Score de riesgo:** {score if score is not None else 'n/d'}/100 ({_level(score)})",
        f"**Cadena:** {wallet_report.get('chain', 'ethereum')}",
        f"**Explicación:** {wallet_report.get('explanation', '')}",
        "",
        "## Señales",
    ]
    factors = wallet_report.get("risk_factors") or []
    facts += [f"- {_factor_text(f)}" for f in factors] or ["- Sin factores de riesgo"]
    facts += [
        "",
        "## Perfil",
        f"- Transacciones históricas: {p.get('tx_count') if p.get('tx_count') is not None else 'n/d'}",
        f"- Antigüedad: {p.get('age_days') if p.get('age_days') is not None else 'n/d'} días",
        f"- Actividad: {p.get('activity', 'n/d')}",
        f"- Balance: ${float(p.get('balance_usd') or 0):,.2f}",
        f"- Muestra analizada: {p.get('sample_size', 0)} tx (confianza {p.get('sample_confidence', 'n/d')})",
        f"- Contrapartes (muestra): {p.get('counterparties_sample', 0)}",
        f"- Etiquetas: {', '.join(p.get('labels') or []) or '—'}",
        "",
    ]
    ann = read_annotations(addr)
    if ann:
        facts += ["## Anotaciones del analista", *[f"- {k}: {v}" for k, v in ann.items()], ""]
    if extra:
        facts += ["## Contexto", *[f"- {k}: {v}" for k, v in extra.items()], ""]
    facts += ["---", f"Actualizado por ChainMind · fuente {wallet_report.get('source', '?')} · "
              f"{wallet_report.get('elapsed_s', '?')}s. Análisis heurístico, no veredicto."]

    meta = {
        "cm_schema": SCHEMA_VERSION,
        "cm_address": addr,
        "cm_chain": wallet_report.get("chain", "ethereum"),
        "cm_kind": "wallet",
        "cm_risk_score": score,
        "cm_risk_level": _level(score),
        "cm_factors": factors,
        "cm_sample_confidence": p.get("sample_confidence"),
        "cm_tx_count": p.get("tx_count"),
        "cm_age_days": p.get("age_days"),
        "cm_activity": p.get("activity"),
        "cm_source": wallet_report.get("source"),
        "cm_last_analyzed": _now(),
        "tags": ["chainmind", f"chainmind/{wallet_report.get('chain', 'ethereum')}",
                 f"riesgo/{_level(score)}"],
    }
    return write_note(note, meta, _body(facts))


def sync_contract(contract_report: dict) -> dict:
    root = vault_root()
    if root is None:
        return {"written": False, "reason": "sin-vault-configurado"}
    addr = str(contract_report.get("address", ""))
    note = root / "contracts" / f"{safe_name(addr)}.md"
    score = contract_report.get("risk_score")
    perms = contract_report.get("permissions") or []
    lines = [
        f"**Score de contrato:** {score if score is not None else 'n/d'}/100 ({_level(score)})",
        f"**Cadena:** {contract_report.get('chain', 'ethereum')}",
        f"**Verificado:** {contract_report.get('verified')}",
        f"**Proxy:** {contract_report.get('is_proxy')} (método: {contract_report.get('proxy_detection', 'n/d')})",
        f"**Bytecode:** {contract_report.get('code_size_bytes', 'n/d')} bytes",
        "",
        f"**Explicación:** {contract_report.get('explanation', '')}",
        "",
        "## Permisos y hallazgos",
    ]
    lines += [f"- {r.get('id')} (+{r.get('weight')}) [{r.get('origin')}] {r.get('message')}"
              for r in (contract_report.get("risks") or [])] or ["- Sin hallazgos"]
    if not perms:
        lines += ["", "Sin permisos peligrosos detectados."]
    lines += ["", f"Wallets relacionadas: ve [[{safe_name(addr)}]] o la nota de la wallet analizada."]
    meta = {
        "cm_schema": SCHEMA_VERSION,
        "cm_address": addr,
        "cm_chain": contract_report.get("chain", "ethereum"),
        "cm_kind": "contract",
        "cm_risk_score": score,
        "cm_risk_level": _level(score),
        "cm_factors": perms,
        "cm_source": contract_report.get("source_origin"),
        "cm_last_analyzed": _now(),
        "tags": ["chainmind", f"chainmind/{contract_report.get('chain', 'ethereum')}", "contrato"],
    }
    return write_note(note, meta, _body(lines))


def ensure_wallet_stub(address: str, reason: str = "") -> dict:
    """Crea una nota mínima si la wallet aún no tiene informe.

    Sin esto, los wikilinks de las alertas apuntan a notas inexistentes y el
    grafo del vault queda desconectado.
    """
    root = vault_root()
    if root is None:
        return {"written": False, "reason": "sin-vault-configurado"}
    note = root / "wallets" / f"{safe_name(address)}.md"
    if note.exists():
        return {"written": False, "reason": "ya-existe"}
    lines = [
        "**Estado:** pendiente de análisis",
        f"**Origen:** {reason}" if reason else "",
        "",
        "Ejecuta un análisis de esta wallet en ChainMind para completar el informe.",
    ]
    meta = {"cm_schema": SCHEMA_VERSION, "cm_address": address, "cm_kind": "wallet",
            "cm_risk_level": "sin-analizar", "cm_last_analyzed": _now(),
            "tags": ["chainmind", "pendiente"]}
    return write_note(note, meta, _body([l for l in lines if l]))


def sync_alert(tx: dict, chain: str = "ethereum") -> dict:
    """Una alerta del watcher se convierte en nota enlazada a la wallet de origen."""
    root = vault_root()
    if root is None:
        return {"written": False, "reason": "sin-vault-configurado"}
    sender = str(tx.get("from", ""))
    h = str(tx.get("hash", ""))[:18] or "alerta"
    note = root / "alerts" / f"{safe_name(h)}.md"
    ensure_wallet_stub(sender, "origen de una alerta del vigilante")
    flags = tx.get("flags") or []
    body = _body([
        f"**Origen:** [[{safe_name(sender)}]]",
        f"**Destino:** {tx.get('to') or 'nuevo contrato'}",
        f"**Valor:** {tx.get('value_eth', 0)} ETH",
        f"**Score:** {tx.get('score', 0)}/100",
        f"**Señales:** {', '.join(flag_text(f) for f in flags) or '—'}",
        f"**Hash:** `{h}`",
        "",
        f"Cadena: {chain} · bloque {tx.get('block', 'n/d')}",
    ])
    meta = {
        "cm_schema": SCHEMA_VERSION,
        "cm_kind": "alert",
        "cm_address": sender,
        "cm_chain": chain,
        "cm_risk_score": tx.get("score"),
        "cm_factors": flags,
        "cm_last_analyzed": _now(),
        "tags": ["chainmind", "alerta"],
    }
    return write_note(note, meta, body)


def _daily_state_path(day: str) -> pathlib.Path:
    """Acumulador del día. Vive fuera del vault: es estado interno, no nota."""
    root = pathlib.Path(__file__).resolve().parent.parent / "reports"
    return root / f"daily-{day}.json"


def _load_daily_state(day: str) -> dict:
    path = _daily_state_path(day)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("chains"), dict):
            return data
    except Exception:
        pass
    return {"day": day, "sweeps": 0, "updated_at": None, "chains": {}}


def _save_daily_state(state: dict) -> None:
    path = _daily_state_path(state["day"])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def accumulate_sweep(feed: dict) -> dict:
    """Acumula un barrido del watcher en el resumen del día.

    El digest se llama "diario" pero antes se sobrescribía en cada barrido:
    con el centinela cada 60 s la nota solo mostraba el último minuto. Aquí se
    mergea por hash (idempotente) y se cuentan barridos, alertas y volumen,
    así que la nota cuenta el día completo aunque el proceso se reinicie.
    """
    day = datetime.date.today().isoformat()
    state = _load_daily_state(day)
    chain = str(feed.get("chain") or "desconocida")
    c = state["chains"].setdefault(chain, {
        "sweeps": 0, "txs": 0, "alerts": 0, "volume_eth": 0.0,
        "latest": None, "median_eth": None, "mad_eth": None,
        "baseline_samples": 0, "detectors": [], "alerts_seen": [], "top": [],
    })
    c["sweeps"] += 1
    c["txs"] += int(feed.get("n_txs") or 0)
    c["alerts"] += int(feed.get("n_alerts") or 0)
    c["detectors"] = list(feed.get("detectors") or c.get("detectors") or [])
    c["volume_eth"] = round(c.get("volume_eth", 0.0) + sum(float(t.get("value_eth") or 0) for t in (feed.get("txs") or [])), 4)
    c["latest"] = max(int(c.get("latest") or 0), int(feed.get("latest") or 0))
    if feed.get("median_eth") is not None:
        c["median_eth"] = feed.get("median_eth")
        c["mad_eth"] = feed.get("mad_eth")
        c["baseline_samples"] = feed.get("baseline_samples") or 0
    vistos = {a["hash"] for a in c["alerts_seen"]}
    for t in (feed.get("alerts") or []):
        h = str(t.get("hash") or "")
        if h and h in vistos:
            continue
        vistos.add(h)
        c["alerts_seen"].append({
            "hash": h, "from": t.get("from"), "value_eth": t.get("value_eth"),
            "score": t.get("score"), "flags": t.get("flags") or [], "block": t.get("block"),
        })
    c["alerts_seen"] = sorted(c["alerts_seen"], key=lambda a: (a.get("score") or 0), reverse=True)[:50]
    top = {str(t.get("hash")): t for t in c["top"] if t.get("hash")}
    for t in (feed.get("txs") or []):
        top.setdefault(str(t.get("hash")), {
            "from": t.get("from"), "to": t.get("to"),
            "value_eth": t.get("value_eth"), "score": t.get("score"),
        })
    c["top"] = sorted(top.values(), key=lambda t: float(t.get("value_eth") or 0), reverse=True)[:10]
    state["sweeps"] += 1
    state["updated_at"] = _now()
    _save_daily_state(state)
    return state


def sync_daily_digest(feed: dict) -> dict:
    """Resumen diario acumulado: todas las alertas del día, no solo el último barrido."""
    root = vault_root()
    if root is None:
        return {"written": False, "reason": "sin-vault-configurado"}
    day = datetime.date.today().isoformat()
    state = accumulate_sweep(feed)
    chains = state["chains"]
    total_alerts = sum(len(c.get("alerts_seen") or []) for c in chains.values())
    note = root / "daily" / f"{day}.md"
    plural = "alerta distinta" if total_alerts == 1 else "alertas distintas"
    lines = [
        f"## Resumen {day}",
        f"{state['sweeps']} barridos · {sum(c['txs'] for c in chains.values())} transacciones analizadas · "
        f"{total_alerts} {plural}",
        "",
        "## Por red",
    ]
    for name, c in sorted(chains.items()):
        n_alertas = len(c.get("alerts_seen") or [])
        lines.append(
            f"- **{name}**: bloque {c.get('latest')} · {c['sweeps']} barridos · {c['txs']} tx · "
            f"{n_alertas} {'alerta' if n_alertas == 1 else 'alertas'} · volumen {c.get('volume_eth', 0)} ETH"
            + (f" · mediana {c['median_eth']} ETH (MAD {c.get('mad_eth')}, base {c.get('baseline_samples')})"
               if c.get("median_eth") is not None else "")
            + (f" · detectores: {', '.join(c.get('detectors') or [])}" if c.get("detectors") else "")
        )
    lines += ["", "## Alertas del día"]
    alerts = [a for c in chains.values() for a in (c.get("alerts_seen") or [])]
    lines += [
        f"- [[{safe_name(a.get('from'))}]] · {a.get('value_eth')} ETH · score {a.get('score')} · "
        f"{', '.join(flag_text(f) for f in (a.get('flags') or [])) or '—'}"
        for a in sorted(alerts, key=lambda a: (a.get("score") or 0), reverse=True)[:20]
    ] or ["- Sin alertas registradas hoy"]
    lines += ["", "## Movimientos destacados"]
    top = [t for c in chains.values() for t in (c.get("top") or [])]
    lines += [
        f"- [[{safe_name(t.get('from'))}]] → {t.get('to') or '∅ contrato'} · {t.get('value_eth')} ETH · score {t.get('score')}"
        for t in sorted(top, key=lambda t: float(t.get("value_eth") or 0), reverse=True)[:10]
    ] or ["- Sin movimientos destacados"]
    lines += ["", "---", f"Actualizado automáticamente por el centinela. Última pasada: {state.get('updated_at')}."]
    meta = {"cm_schema": SCHEMA_VERSION, "cm_kind": "daily", "cm_last_analyzed": _now(),
            "cm_tx_count": sum(c["txs"] for c in chains.values()),
            "tags": ["chainmind", "diario"]}
    return write_note(note, meta, _body(lines))


def build_index() -> dict:
    """MOC: índice navegable del vault."""
    root = vault_root()
    if root is None:
        return {"written": False, "reason": "sin-vault-configurado"}
    note = root / "index.md"
    wallets = sorted((root / "wallets").glob("*.md")) if (root / "wallets").is_dir() else []
    contracts = sorted((root / "contracts").glob("*.md")) if (root / "contracts").is_dir() else []
    dailies = sorted((root / "daily").glob("*.md"), reverse=True) if (root / "daily").is_dir() else []
    lines = [
        "# ChainMind — Centro de inteligencia",
        "",
        "Este vault es alimentado por los agentes de ChainMind (Ethereum y Base).",
        "Lo que escribas **fuera** de los bloques `chainmind` se conserva y se lee de vuelta.",
        "",
        "## Carpetas",
        "- `wallets/` — un informe por wallet, con score, señales y perfil",
        "- `contracts/` — auditoría de bytecode y permisos",
        "- `alerts/` — alertas del vigilante en vivo",
        "- `daily/` — resumen diario de la red",
        "",
        f"## Wallets ({len(wallets)})",
    ]
    lines += [f"- [[{w.stem}]]" for w in wallets[:50]] or ["- (ninguna todavía)"]
    lines += ["", f"## Contratos ({len(contracts)})"]
    lines += [f"- [[{c.stem}]]" for c in contracts[:50]] or ["- (ninguno todavía)"]
    lines += ["", "## Días recientes"]
    lines += [f"- [[{d.stem}]]" for d in dailies[:10]] or ["- (ninguno todavía)"]
    lines += ["", "---", f"Actualizado {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    meta = {"cm_schema": SCHEMA_VERSION, "cm_kind": "index", "cm_last_analyzed": _now(),
            "tags": ["chainmind", "moc"]}
    return write_note(note, meta, _body(lines))


# ------------------------------------------------------------- anotaciones
def read_annotations(address: str) -> dict:
    """Lee lo que el analista añadió en el frontmatter (campos `cm_` del usuario).

    No confundimos nuestros campos de análisis con los del usuario: solo se
    devuelve lo que no es nuestro (p. ej. cm_status, cm_owner, cm_notas).
    """
    root = vault_root()
    if root is None:
        return {}
    note = root / "wallets" / f"{safe_name(address)}.md"
    if not note.exists():
        return {}
    meta, _ = split_note(note.read_text(encoding="utf-8"))
    return {k: v for k, v in meta.items()
            if k.startswith("cm_") and k not in CM_FIELDS and v not in (None, "")}
