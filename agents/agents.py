"""Agentes especializados: un modelo por rol, no un prompt genérico.

Antes de este módulo había tres prompts sueltos (wallet, contrato,
investigación) repartidos por el código. El problema no era que fueran
débiles: es que un modelo pequeño rinde mucho más con una tarea estrecha y
unas reglas tajantes que con instrucciones genéricas. Aquí cada agente es una
entidad con:

  - su prompt de sistema, escrito para su tarea y con sus prohibiciones
  - su modelo (una tarea de clasificar no necesita un modelo de 7B)
  - su temperatura y su presupuesto de tokens
  - su validador propio, encima del filtro global de seguridad

Todos heredan el filtro de `agents.llm`: ninguna salida se publica sin pasar
la validación de accordionés, invenciones y coherencia con el score.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import os

from . import llm

MODELO_RAPIDO = "phi4-mini"        # 3,3s · 2,5 GB · supera el filtro siempre (medido)
MODELO_LIGERO = "llama3.2:3b"      # 3,5s · 2,0 GB · el más ligero que aguanta
MODELO_Fuerte = "qwen2.5:7b"

# El nodo de chat redacta sobre datos reales: es el único que se justifica con
# el modelo grande. Se cambia por entorno sin tocar código (phi4-mini va 3x más
# rápido y se inventa cifras; qwen2.5:3b es el punto medio).
MODELO_CHAT = os.getenv("CHAINMIND_MODELO_CHAT", MODELO_Fuerte)       # 7,5s · 4,7 GB · para lo que exige criterio

# Regla común a todos. Va en cada prompt porque un modelo de 3B no arrastra el
# contexto: si no se repite, no lo cumple.
BASE = (
    "Eres un agente de ChainMind, un sistema de análisis on-chain.\n"
    "REGLAS INNEGOCIABLES:\n"
    "- No afirmes ni insinúes responsabilidad penal ni intención deliberada.\n"
    "- No uses palabras como delito, fraude, culpable ni money laundering.\n"
    "- No inventes datos: solo menciona lo que está en el contexto que te dan.\n"
    "- Una heurística es una señal para investigar, nunca un veredicto.\n"
    "- Responde siempre en español y termina recordando que hay que confirmar\n"
    "  on-chain antes de actuar."
)


@dataclass
class Agent:
    name: str
    role: str
    system: str
    model: str = MODELO_RAPIDO
    temperature: float = 0.2
    max_tokens: int = 420
    # Rechazos propios del rol, por encima del filtro global. Se aplican a
    # frases concretas: lo que las activa se elimina, y si no queda texto
    # utilizable el agente cae a su respuesta determinista.
    veta: tuple[str, ...] = ()
    # Palabras que el agente no debe usar nunca en su salida.
    prohibido: tuple[str, ...] = ()
    ejemplos: str = ""
    tools: tuple[str, ...] = field(default_factory=tuple)

    def prompt(self) -> str:
        partes = [self.system.strip(), BASE]
        if self.tools:
            partes.append("Tienes acceso a estas herramientas del sistema:\n" +
                          "\n".join(f"- {t}" for t in self.tools))
        if self.ejemplos:
            partes.append(self.ejemplos)
        return "\n\n".join(partes)

    def validar(self, texto: str) -> str | None:
        """Motivo del rechazo propio del agente, o None si lo permite."""
        for p in self.prohibido:
            if re.search(p, texto, re.I):
                return f"{self.name}:prohibido:{p}"
        for p in self.veta:
            for oracion in re.split(r"(?<=[.!?…])\s+", texto.replace("\n", " ")):
                if re.search(p, oracion, re.I):
                    return f"{self.name}:veta:{p}"
        return None


EXPLICACION = Agent(
    name="explicacion",
    role="Explica el score de riesgo de una wallet en lenguaje claro",
    system=(
        "Tu tarea: explicar qué significa el patrón de una wallet y qué conviene verificar.\n"
        "Estructura: qué muestra el perfil, qué significa el score, qué límites tiene.\n"
        "No repitas el JSON: extrae lo relevante."
    ),
    model=MODELO_RAPIDO,
    temperature=0.2,
    # Un LLM pequeño tiende aIRES a "es una wallet activa y diversificada": eso
    # no es un hallazgo. Se le pide nombrar la señal concreta.
    veta=(
        r"\bwallet (?:muy )?activa\b", r"\bactividad (?:muy )?intensa\b",
        r"\bperfil (?:muy )?diversificad\w*", r"\bgran número de transacciones\b",
    ),
    ejemplos=(
        "Ejemplo de cómo responder:\n"
        "«El 62/100 viene de tres señales concretas: muchas contrapartes en poco tiempo, "
        "ráfagas de actividad y una cuenta joven. Vale la pena mirar si esas contrapartes "
        "se repiten. El score no dice que haya un problema: dice que hay algo que mirar.»"
    ),
)

RIESGO = Agent(
    name="riesgo",
    role="Explica por qué una transacción o contrato puntúa como puntúa",
    system=(
        "Tu tarea: justificar la puntuación de riesgo de una transacción o un contrato.\n"
        "Enumera solo los factores que se te pasan y di qué comprobaría cada uno.\n"
        "Si no hay factores, dilo en una frase y no inventes ninguno."
    ),
    model=MODELO_RAPIDO,
    temperature=0.15,
    veta=(r"\bprobablemente\b", r"\bseguramente\b", r"\bcasi seguro que\b"),
)

CONTRATOS = Agent(
    name="contratos",
    role="Traduce hallazgos de Slither y bytecode a lenguaje humano",
    system=(
        "Tu tarea: explicar a quien va a interactuar con el contrato qué permisos tiene, "
        "qué debería comprobar y qué limitaciones tiene este análisis.\n"
        "Explica SOLO los hallazgos listados. No añadas riesgos que no estén."
    ),
    model=MODELO_LIGERO,
    temperature=0.15,
    # Inventar una vulnerabilidad es el fallo más grave aquí: da miedo falso.
    veta=(r"\bvulnerabilidad\b", r"\bexploit\w*", r"\bhack\w*", r"\bcritical\b"),
    ejemplos=(
        "Ejemplo: «El contrato permite cambiar de implementación (proxy), así que el "
        "código que ves hoy puede cambiar mañana. Lo que hay que auditar es la "
        "implementación, no el proxy.»"
    ),
)

INVESTIGACION = Agent(
    name="investigacion",
    role="Lee el trazado de fondos y dice qué mirar después",
    system=(
        "Tu tarea: describir un grafo de transacciones y decir qué patrón muestra.\n"
        "Una coincidencia con la watchlist es un punto de partida, no una conclusión.\n"
        "Di siempre que el trazado solo cubre las transacciones disponibles."
    ),
    model=MODELO_RAPIDO,
    temperature=0.15,
    veta=(r"\b(?:lavado|blanqueo) de (?:fondos|-capital)\b",),
)

ANOMALIAS = Agent(
    name="anomalias",
    role="Explica qué significa una anomalía estadística y cuánto pesarla",
    system=(
        "Tu tarea: explicar una anomalía detectada por el modelo de outlier.\n"
        "Distingue siempre entre 'raro' y 'malicioso': una cosa no implica la otra."
    ),
    model=MODELO_LIGERO,
    temperature=0.15,
    veta=(r"\b Deliberadamente\b", r"\baislado para (?:blanquear|robar|estafar)\b"),
)

CENTINELA = Agent(
    name="centinela",
    role="Redacta la alerta que sale del vigilante 24/7",
    system=(
        "Tu tarea: una frase de alerta para un Telegram, con el valor y la señal concreta.\n"
        "Máximo 2 frases. Sin recommandaciones largas."
    ),
    model=MODELO_RAPIDO,
    temperature=0.1,
    max_tokens=160,
    veta=(r"\bdelito\b", r"\bintenta\b",),
)

CHAT = Agent(
    name="chat",
    role="Nodo de chat con acceso a todo ChainMind",
    system=(
        "Tu tarea: responder preguntas sobre blockchains usando las herramientas.\n"
        "Primero decide si necesitas una herramienta. Si la necesitas, pide exactamente una "
        "y espera el resultado antes de responder.\n"
        "Si no necesitas datos, responde directamente y sé breve.\n"
        "Nunca inventes el resultado de una herramienta: si no la has llamado, no tienes datos."
    ),
    model=MODELO_CHAT,  # redactar sobre diez filas de datos y describir un
                           # gráfico sí exige criterio; si no está instalado
                           # cae al del proveedor (ver llm.modelo_disponible)
    temperature=0.2,
    max_tokens=760,
    tools=(
        "wallet(address, chain) — perfil, score, señales y explicación de una wallet",
        "contrato(address, chain) — permisos, proxy y hallazgos de un contrato",
        "rastreo(address, max_depth, direction) — por dónde ha pasado el dinero",
        "top_wallets(chain, bloques, top) — qué dirección se ha movido más, con serie por bloque",
        "comparar(addresses, chain) — dos o más wallets en la misma tabla",
        "resumen(chain, bloques) — actividad de la cadena, con serie por bloque",
        "feed(chain) — actividad reciente y alertas del centinela",
        "estado() — proveedores de IA, centinela, guard y calidad de datos",
        "watchlist() — direcciones vigiladas y su motivo",
    ),
    veta=(r"\bes (?:una )?dirección (?:sancionada|ilegal)\b",),
)

REGISTRY: dict[str, Agent] = {
    a.name: a for a in (
        EXPLICACION, RIESGO, CONTRATOS, INVESTIGACION, ANOMALIAS, CENTINELA, CHAT,
    )
}


def verificar_cifras(texto: str, score: int | None = None) -> str | None:
    """Comprueba que el texto no contradiga las cifras que le pasamos.

    Un modelo de 3B inventa: dice "128.078 transacciones" cuando el dato era
    1.420, o afirma que una fuente "no ha sido verificada" cuando sí lo está.
    Aquí solo se miran las dos cifras que más se falsean: el score sobre 100 y
    una cadena de verificaciones explícita. Es una red de seguridad, no una
    garantía: el resto de números dependen de la_context que se le pasó.
    """
    if not texto:
        return None
    if score is not None:
        for m in re.finditer(r"(\d{1,3})\s*/\s*100", texto):
            if int(m.group(1)) != int(score):
                return f"cifra: score dicho {m.group(1)}/100 pero el real es {score}/100"
    if re.search(r"\bno (?:ha )?sido verificad\w*|\bno verificad\w*|\bsin verificar\b", texto, re.I):
        if re.search(r"\bverificad[oa]\b|\bverified\b", texto, re.I) and \
           re.search(r"\bno (?:ha )?sido verificad\w*|\bno verificad\w*", texto, re.I):
            return "cifra: se contradice sobre la verificación del código"
    return None


def get(name: str) -> Agent:
    agente = REGISTRY.get(name)
    if agente is None:
        raise KeyError(f"agente desconocido: {name}")
    return agente


def describe() -> list[dict]:
    """Inventario de agentes: lo consume /status y la interfaz."""
    return [
        {
            "nombre": a.name,
            "rol": a.role,
            "modelo": a.model,
            "temperatura": a.temperature,
            "tokens_max": a.max_tokens,
            "herramientas": list(a.tools),
            "reglas_propias": len(a.veta) + len(a.prohibido),
        }
        for a in REGISTRY.values()
    ]


def run(nombre: str, user: str, fallback: str, *, score: int | None = None,
        model: str | None = None, temperature: float | None = None,
        max_tokens: int | None = None) -> dict:
    """Ejecuta un agente. Devuelve siempre texto usable más su trazabilidad.

    `fallback` es la respuesta determinista del agente: se devuelve si no hay
    modelo, si el modelo falla, si la salida no supera el filtro global o si
    viola las reglas propias de su rol.
    """
    agente = get(nombre)
    pedido = model or agente.model
    # Si el modelo del agente no está instalado, se usa el del proveedor en vez
    # de dejar el nodo entero en modo determinista.
    elegido = pedido if llm.modelo_disponible(pedido) else None
    res = llm.complete(
        agente.prompt(), user,
        max_tokens=max_tokens or agente.max_tokens,
        temperature=agente.temperature if temperature is None else temperature,
        purpose=agente.name,
        model=elegido,
    )
    if not res.get("ok"):
        return {"text": fallback, "agente": agente.name, "source": "determinista",
                "motivo": res.get("error", "sin proveedor"), "modelo": agente.model}
    limpio, motivo = llm.validate_explanation(res["text"], score, truncado=res.get("truncado", False))
    if limpio is None:
        return {"text": fallback, "agente": agente.name, "source": "determinista",
                "motivo": f"filtro:{motivo}", "modelo": res.get("model"),
                "latency_s": res.get("latency_s")}
    violacion = agente.validar(limpio)
    if violacion:
        return {"text": fallback, "agente": agente.name, "source": "determinista",
                "motivo": violacion, "modelo": res.get("model"), "latency_s": res.get("latency_s")}
    cifra = verificar_cifras(limpio, score)
    if cifra:
        return {"text": fallback, "agente": agente.name, "source": "determinista",
                "motivo": cifra, "modelo": res.get("model"), "latency_s": res.get("latency_s")}
    return {
        "text": limpio, "agente": agente.name, "source": "llm", "motivo": "ok",
        "provider": res.get("provider"), "modelo": res.get("model"),
        "latency_s": res.get("latency_s"), "tokens_in": res.get("tokens_in"),
        "tokens_out": res.get("tokens_out"), "cached": res.get("cached", False),
    }
