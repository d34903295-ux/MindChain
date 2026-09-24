"""Escapado de Markdown compartido.

Regla: se escapa SOLO lo que viene de la cadena (direcciones, hashes, etiquetas
de una watchlist remota, timestamps). El texto que compone el Explanation Agent
es nuestro y se escribe limpio: si no, el reporte sale con `\\(Ethereum\\)` y
`labels: \\['eoa'\\]`, que es ruido, no seguridad.
"""

_ESCAPES = (
    ("\\", "\\\\"),
    ("|", "\\|"),
    ("#", "\\#"),
    ("*", "\\*"),
    ("_", "\\_"),
    ("`", "\\`"),
    ("[", "\\["),
    ("]", "\\]"),
    ("(", "\\("),
    (")", "\\)"),
    ("<", "&lt;"),
    (">", "&gt;"),
)


def escape_md(value, limit: int = 300) -> str:
    """Escapa un valor procedente de la cadena para usarlo en Markdown."""
    s = "" if value is None else str(value)
    for a, b in _ESCAPES:
        s = s.replace(a, b)
    return s[:limit]


def safe_label(value, limit: int = 60) -> str:
    """Etiqueta de watchlist: texto libre de terceros, sin saltos de línea."""
    s = escape_md(value, limit).replace("\r", " ").replace("\n", " ")
    return s.strip()
