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

## Criterio salida Fase 0
`docker-compose up` levanta Postgres+Neo4j+backend+indexer y el indexer escribe bloques recientes a Postgres/Neo4j.

> Sin Docker en esta máquina: el scaffold está listo para `docker compose config` + `up` en dev.
