"""Report Agent: reporte descargable en Markdown del caso.

Reglas:
- todo texto que viene de la cadena se escapa (un flag o hash con `#`/`|` no
  puede romper la estructura del Markdown ni inyectar enlaces)
- si el score es None (sin datos), el reporte lo dice en vez de inventar 0/100
"""
import datetime

from .md import escape_md, safe_label

NL = chr(10)

FACTOR_TEXT = {
    "wallet_nueva_pocas_txs": "poco historial: tratarla con cautela hasta que acumule actividad",
    "wallet_reciente_poca_actividad": "wallet creada hace poco con pocas operaciones",
    "concentracion_fondos_una_fuente": "casi todo el valor recibido viene de una sola contraparte",
    "patron_convoy_mismo_origen": "varias operaciones seguidas desde la misma contraparte "
                                  "(bridge, exchange o automatización)",
    "patron_bot_alta_frecuencia": "actividad horaria uniforme y muy frecuente",
    "dormante_reactivada": "wallet dormida que vuelve a moverse",
    "balance_alto_wallet_reciente": "balance alto en una wallet reciente",
    "datos_insuficientes_score_provisional": "datos disponibles pocos: score provisional",
    "datos_insuficientes_no_evaluable": "no hay datos suficientes: la wallet no se evalúa",
}


def _esc(v) -> str:
    """Alias histórico. El escapado vive en agents.md (datos de la cadena)."""
    return escape_md(v)


def _money(v) -> str:
    try:
        return "$" + format(float(v), ",.2f")
    except Exception:
        return "n/d"


def _factor(f: str) -> str:
    if f in FACTOR_TEXT:
        return FACTOR_TEXT[f]
    if f.startswith("interaccion_watchlist:"):
        return f"interacción con dirección listada ({safe_label(f.split(':', 1)[1])}) — señal de screening"
    return escape_md(f.replace("_", " "), 80)


def build_case_markdown(wallet_report, trace, contract_report=None, anomalies=None):
    p = wallet_report.get("profile", {})
    score = wallet_report.get("risk_score")
    L = []
    L.append("# ChainMind — Reporte de caso")
    L.append("")
    L.append(f"Fecha (UTC): {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M}")
    L.append(f"Wallet: `{_esc(wallet_report.get('address', ''))}` ({_esc(wallet_report.get('chain', 'ethereum'))})")
    L.append(f"Fuente: {_esc(wallet_report.get('source', '?'))} · {wallet_report.get('elapsed_s', '?')}s")
    dq = wallet_report.get("data_quality") or {}
    if dq.get("errors"):
        L.append(f"Calidad de datos: degradada ({_esc('; '.join(dq['errors'])[:120])})")
    L.append("")

    L.append("## 1. Resumen ejecutivo")
    L.append(str(wallet_report.get("explanation", "")))
    L.append("")

    # Perfil: valores internos van limpios; los que vienen de la cadena, escapados.
    L.append("## 2. Perfil")
    chain_fields = {"first_seen", "last_seen"}
    for k in ["tx_count", "tx_count_reliable", "age_days", "first_seen", "last_seen",
              "activity", "freq_tx_day", "balance_usd", "sample_size", "sample_confidence",
              "counterparties_sample", "in_count_sample", "out_count_sample",
              "in_usd_sample", "out_usd_sample", "bot_like", "timezone_note", "labels"]:
        val = p.get(k)
        shown = "n/d" if val is None else val
        L.append(f"- {k}: {escape_md(shown) if k in chain_fields else shown}")
    L.append("")

    L.append("## 3. Riesgo")
    if score is None:
        L.append("**No evaluable** — no se obtuvieron datos suficientes de la cadena.")
    else:
        L.append(f"Score: **{score}/100**")
    facs = wallet_report.get("risk_factors", []) or []
    L.append("Factores: " + ("ninguno" if not facs else "; ".join(_factor(f) for f in facs)))
    L.append("")

    L.append(f"## 4. Trazado de fondos ({trace.get('n_paths', 0)} rutas, {trace.get('n_nodes', 0)} nodos)")
    L.append(f"Valor total trazado: {_money(trace.get('total_traced_usd'))}")
    for node in trace.get("watchlist_nodes", []) or []:
        L.append(f"- Aviso: `{_esc(node.get('address'))}` aparece en la watchlist ({_esc(node.get('label'))})")
    for i, (path, val) in enumerate(zip(trace.get("paths", [])[:20], trace.get("path_values_usd", [])[:20]), 1):
        L.append(f"{i}. {' → '.join('`'+_esc(n)+'`' for n in path)} ({_money(val)})")
    if not trace.get("paths"):
        L.append("Sin rutas: la muestra de transacciones no contiene saltos desde esta wallet.")
    L.append("")
    L.append("Aristas (muestra, máx. 25):")
    for e in (trace.get("edges", []) or [])[:25]:
        L.append(
            f"- `{_esc(e['from'][:12])}…` → `{_esc(e['to'][:12])}…` · {_money(e.get('value_usd'))} · "
            f"`{_esc(str(e.get('hash', ''))[:18])}…` · {_esc(e.get('time', ''))}"
        )
    L.append("")

    if contract_report:
        L.append("## 5. Contrato relacionado")
        L.append(f"Score contrato: {_esc(contract_report.get('risk_score'))} · "
                 f"proxy: {_esc(contract_report.get('is_proxy'))} · "
                 f"permisos: {_esc(', '.join(contract_report.get('permissions', []) or ['ninguno']))}")
        L.append("")

    if anomalies:
        L.append("## 6. Anomalías (24h)")
        for a in anomalies:
            L.append(f"- `{_esc(a.get('address'))}` score {_esc(a.get('anomaly_score'))} ({_esc(a.get('top_feature'))})")
        L.append("")

    L.append("---")
    L.append("Análisis heurístico automatizado. No constituye acusación ni asesoramiento financiero: "
             "verifica on-chain antes de actuar.")
    return NL.join(L)


def write_report(address, markdown, outdir="reports"):
    import pathlib

    d = pathlib.Path(outdir)
    d.mkdir(parents=True, exist_ok=True)
    day = datetime.date.today().isoformat()
    name = f"case-{str(address)[:12]}-{day}.md"
    p = d / name
    p.write_text(markdown, encoding="utf-8")
    return str(p)
