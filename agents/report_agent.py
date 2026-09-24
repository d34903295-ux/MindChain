"""Report Agent (Fase 4): reporte descargable en Markdown del caso."""
import datetime

NL = chr(10)

def _money(v):
    try:
        return "$" + format(float(v), ",.2f")
    except Exception:
        return str(v)

def build_case_markdown(wallet_report, trace, contract_report=None, anomalies=None):
    p = wallet_report.get("profile", {})
    L = []
    L.append("# ChainMind — Reporte de caso")
    L.append("")
    L.append("Fecha (UTC): " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M"))
    L.append("Wallet: " + str(wallet_report.get("address", "")) + " (" + str(wallet_report.get("chain", "ethereum")) + ")")
    L.append("Fuente: " + str(wallet_report.get("source", "?")) + " · " + str(wallet_report.get("elapsed_s", "?")) + "s")
    L.append("")
    L.append("## 1. Resumen ejecutivo")
    L.append(wallet_report.get("explanation", ""))
    L.append("")
    L.append("## 2. Perfil")
    for k in ["tx_count", "age_days", "first_seen", "last_seen", "activity", "freq_tx_day",
              "balance_usd", "counterparties_sample", "in_usd_sample", "out_usd_sample",
              "bot_like", "timezone_note", "labels"]:
        L.append("- " + k + ": " + str(p.get(k, "—")))
    L.append("")
    L.append("## 3. Riesgo: " + str(wallet_report.get("risk_score", 0)) + "/100")
    facs = wallet_report.get("risk_factors", []) or []
    L.append("Factores: " + ("ninguno" if not facs else ", ".join(facs)))
    L.append("")
    L.append("## 4. Trazado de fondos (" + str(trace.get("n_paths", 0)) + " rutas, " + str(trace.get("n_nodes", 0)) + " nodos)")
    for i, path in enumerate(trace.get("paths", [])[:20], 1):
        L.append(str(i) + ". " + (" -> ".join(path)))
    if not trace.get("paths"):
        L.append("Sin rutas: la muestra de transacciones no contiene saltos desde esta wallet.")
    L.append("")
    L.append("Aristas (muestra, máx 25):")
    for e in trace.get("edges", [])[:25]:
        L.append("- " + e["from"][:12] + ".. -> " + e["to"][:12] + ".. · " + _money(e.get("value_usd")) + " · " + str(e.get("hash", ""))[:18] + ".. · " + str(e.get("time", "")))
    L.append("")
    if contract_report:
        L.append("## 5. Contrato relacionado")
        L.append("Score contrato: " + str(contract_report.get("risk_score", "?")) + " · permisos: " + ", ".join(contract_report.get("permissions", []) or ["ninguno"]))
        L.append("")
    if anomalies:
        L.append("## 6. Anomalías (24h)")
        for a in anomalies:
            L.append("- " + a.get("address", "") + " score " + str(a.get("anomaly_score", "")) + " (" + str(a.get("top_feature", "")) + ")")
        L.append("")
    L.append("---")
    L.append("Descargo: análisis heurístico automatizado, no constituye acusación. Verificar on-chain antes de actuar.")
    return NL.join(L)

def write_report(address, markdown, outdir="reports"):
    import pathlib
    d = pathlib.Path(outdir)
    d.mkdir(parents=True, exist_ok=True)
    day = datetime.date.today().isoformat()
    name = "case-" + str(address)[:12] + "-" + day + ".md"
    p = d / name
    p.write_text(markdown, encoding="utf-8")
    return str(p)
