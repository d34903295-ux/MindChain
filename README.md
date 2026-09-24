# ChainMind — Blockchain Intelligence Multi-Agent System
Fase 0: Setup monorepo + Postgres + Neo4j + Indexer Subsquid EVM

## Estructura
- `/frontend` — Next.js + React + TS + Tailwind + shadcn/ui
- `/backend` — FastAPI (Python)
- `/agents` — LangGraph (Wallet Intelligence, Risk, Explanation)
- `/indexer` — Subsquid EVM template (Ethereum mainnet)
- `/db/postgres/init.sql` — users, wallets, reports, raw_transactions
- `/db/neo4j/init.cypher` — Wallet, Contract, Transaction

## Quickstart
1. Copiar env: `cp .env.example .env` y rellenar `ETH_RPC_URL`
2. Levantar stack: `docker compose up --build`
3. Backend: http://localhost:8000/docs — `GET /health`, `POST /analyze-wallet` (stub Fase 0)
4. Neo4j browser: http://localhost:7474 — user/pass de `.env`
5. Indexer: plantilla Subsquid EVM, ver `/indexer/README.md`

## IA

Los agentes de Explanation, Contract e Investigation usan un LLM real. No hace
falta cuenta: si tienes [Ollama](https://ollama.com) corriendo, ChainMind lo
detecta y usa un modelo local (gratis, sin clave y sin sacar datos de tu
máquina):

```bash
ollama pull qwen2.5:7b    # 7B es el mínimo que responde bien: con 1.5B acusa
```

Para usar un proveedor en la nube basta con poner su clave en `.env`; ChainMind
elige el primero disponible en el orden `ollama → anthropic → openai → gemini →
groq → openrouter`, o el que fuerces con `CHAINMIND_LLM_PROVIDER`.

| Proveedor | Variable | Notas |
|---|---|---|
| Ollama (local) | — | Sin clave. Recomendado para datos sensibles |
| Anthropic | `ANTHROPIC_API_KEY` | Claude |
| OpenAI | `OPENAI_API_KEY` | GPT |
| Google | `GEMINI_API_KEY` | Gemini |
| Groq | `GROQ_API_KEY` | Modelos abiertos, muy rápidos |
| OpenRouter | `OPENROUTER_API_KEY` | Pasarela a muchos modelos |
| Compatible OpenAI | `CHAINMIND_LLM_BASE_URL` | vLLM, LM Studio, Together… |

`GET /status` dice qué proveedor está activo, cuánto ha costado y si está
fallando. Sin proveedor, o si la respuesta del modelo no supera el filtro de
seguridad, los agentes usan siempre su texto determinista: **una respuesta de
IA nunca se publica sin validar**. El filtro descarta acusaciones, intenciones
criminales, invenciones y textos que contradigan el score, y recorta las
respuestas que hayan quedado cortadas a media frase.

## Agentes especializados

Cada agente tiene su prompt, su modelo, su temperatura y sus propias reglas.
Un modelo de 3B rinde mucho mejor con una tarea estrecha que con
instrucciones genéricas.

| Agente | Modelo | De qué se ocupa |
|---|---|---|
| `explicacion` | phi4-mini | Explica el score de una wallet |
| `riesgo` | phi4-mini | Justifica una puntuación |
| `contratos` | llama3.2:3b | Traduce Slither y bytecode |
| `investigacion` | phi4-mini | Lee el trazado de fondos |
| `anomalias` | llama3.2:3b | Explica outliers del Isolation Forest |
| `centinela` | phi4-mini | Redacta la alerta del vigilante |
| `chat` | phi4-mini | Responde con acceso a todo el sistema |

Modelos medidos en esta máquina (`python scripts/bench_models.py`):

| Modelo | Latencia | Filtro |
|---|---|---|
| phi4-mini | 3,3 s | siempre pasa |
| llama3.2:3b | 3,5 s | siempre pasa |
| qwen2.5:3b | 3,0 s | la mitad descartado |
| qwen2.5:7b | 7,5 s | siempre pasa |

## Chat con acceso al sistema

`POST /chat` pregunta al sistema. No simula: usa los mismos agentes y las
mismas fuentes que los endpoints, así que los datos que da son los mismos.

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"mensaje":"analiza 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 en base"}'
```

Entiende: wallets, contratos, rutas de fondos, feed en vivo, estado del
sistema y watchlist. El enrutado lo hace una tabla de patrones, no el modelo
(un LLM de 3B no es fiable decidiendo JSON), así que el chat nunca se queda
colgado: si el modelo falla, responde con el resumen determinista.

## Usarlo desde otras herramientas

Desde la máquina donde corre, genera una clave:

```bash
curl -X POST http://127.0.0.1:8000/keys -H "Content-Type: application/json" \
  -d '{"nombre":"mi-bot"}'
```

La clave se muestra **una única vez** (se guarda hasheada) y se usa así:

```bash
curl -H "X-API-Key: cm_..." http://127.0.0.1:8000/analyze-wallet \
  -H "Content-Type: application/json" \
  -d '{"address":"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045","chain":"ethereum"}'
```

- El panel y los scripts de la propia máquina no necesitan clave.
- Desde fuera (otra IP, contenedor, servicio) sí es obligatoria.
- `GET /keys` y `DELETE /keys/{nombre}` gestionan las claves, siempre desde
  localhost.
- `CHAINMIND_REQUIRE_KEY=1` hace que localhost también pida clave.
- `CHAINMIND_TRUSTED_HOSTS=proxy,host.docker.internal` declara hosts de
  confianza (proxy inverso o red de Docker).

Estas son claves **de ChainMind**, para autorizar a quien llama. Las claves de
los proveedores de IA (Anthropic, OpenAI…) no se devuelven por ningún
endpoint: hay un test que lo comprueba.

## Criterio salida Fase 0
`docker-compose up` levanta Postgres+Neo4j+backend+indexer y el indexer escribe bloques recientes a Postgres/Neo4j.

> Sin Docker en esta máquina: el scaffold está listo para `docker compose config` + `up` en dev.
