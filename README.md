# ChainMind — centro de inteligencia on-chain

Analiza wallets y contratos de Ethereum y Base con datos **reales** leídos de
la cadena, calcula un score de riesgo explicable y expone todo por API y por
web. La IA redacta; **los datos y los números los calcula el código**.

Todo corre en local: el modelo es [Ollama](https://ollama.com), sin claves de
nube y sin sacar datos de tu máquina.

> **Estado honesto**: el análisis on-chain, la API, la web, el chat con gráficos
> y las dos bases de datos funcionan hoy y están probados. El **indexer de
> Subsquid no escribe nada** y la relación `TRANSACTED_WITH` no existe. Está
> detallado más abajo, en [Lo que todavía no funciona](#lo-que-todavía-no-funciona).

---

## Qué sabe hacer

| | |
|---|---|
| **Wallet** | Perfil, score 0-100 con los factores que lo componen, volumen, contrapartes, antigüedad |
| **Contrato** | Bytecode, permisos, proxy, verificación en Blockscout |
| **Chat** | Preguntas en lenguaje llano con **9 herramientas** y **gráficos**: «qué wallet se movió más», resumen de la cadena, comparación entre wallets |
| **Vigilancia** | Centinela que recorre bloques en background y avisa de anomalías |
| **Persistencia** | PostgreSQL (wallets, reports) y Neo4j (grafo de transacciones) |

El chat es lo que más sorprende: escanea bloques de verdad, cuenta los
movimientos por dirección y responde con la más activa, su serie por bloque y
un ranking.

```bash
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"mensaje":"que wallet se movio mas en los ultimos 3 bloques"}'
```

---

## Empezar desde cero

### 1. Requisitos

| | Versión | Nota |
|---|---|---|
| Python | 3.11+ | con `pip` |
| Node.js | 20 | para la web |
| [Ollama](https://ollama.com) | — | opcional: sin él, la IA es texto determinista |
| PostgreSQL | 16 | opcional: sin él, el análisis sigue, solo no se guarda |
| Neo4j | 5.x | opcional: idem, y necesita Java 17+ |

Las tres últimas son **opcionales**: la app está hecha para degradar sin
romperse. Sin base de datos responde igual y lo dice en el campo `persistence`
de la respuesta.

### 2. Dependencias de Python

```bash
python -m pip install -r backend/requirements.txt
python -m pip install "psycopg[binary]==3.1.*" "neo4j==5.22.*" "python-dotenv==1.0.*"
```

La segunda línea **no está en `requirements.txt` a propósito**: son los drivers
de las bases, y sin ellos el import falla antes incluso de intentar conectar.
Si ves `ModuleNotFoundError: psycopg` en el log, es esto.

### 3. Variables de entorno

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Mínimo para que funcione sin claves:

```env
ETH_RPC_URL=https://eth.llamarpc.com
BASE_RPC_URL=https://base.llamarpc.com
```

Sin `ETH_RPC_URL` el sistema usa Blockchair/Blockscout, que no necesitan clave
pero van más lento y se caen más.

### 4. Modelo local (opcional pero recomendado)

```bash
ollama pull qwen2.5:7b
```

`phi4-mini` también sirve y es 3× más rápido, pero mezcla cifras. El nodo de
chat usa el modelo grande porque redactar sobre datos sí lo exige; se cambia
con `CHAINMIND_MODELO_CHAT`.

### 5. Bases de datos (opcionales)

<details>
<summary><b>PostgreSQL 16 y Neo4j 5 para Windows (lo que hay probado aquí)</b></summary>

```powershell
# PostgreSQL: instalar, crear rol y base, y cargar el schema CON ese rol
# (en PG15+ el schema public no da permisos a quien no es dueño: si lo creas
#  como otro usuario, luego no ve ninguna tabla)
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h 127.0.0.1 `
    -c "CREATE ROLE chainmind LOGIN PASSWORD 'chainmind_dev'" `
    -c "CREATE DATABASE chainmind OWNER chainmind"
Get-Content db\postgres\init.sql -Raw | & "C:\Program Files\PostgreSQL\16\bin\psql.exe" `
    -U chainmind -h 127.0.0.1 -d chainmind

# Neo4j: la contraseña se fija ANTES del primer arranque
$env:JAVA_HOME = "C:\jdk-21.0.12.1+1"      # Java 17+ en el PATH; el zip no lo trae
& "C:\neo4j-community-5.26.0\bin\neo4j-admin.bat" dbms set-initial-password chainmind_dev
& "C:\neo4j-community-5.26.0\bin\neo4j.bat" windows-service install
Start-Service Neo4j
Get-Content db\neo4j\init.cypher -Raw | & "C:\neo4j-community-5.26.0\bin\cypher-shell.bat" `
    -u neo4j -p chainmind_dev
```

Credenciales por defecto: `chainmind` / `chainmind_dev`. Son las que espera el
código, por eso no hace falta configurar nada más.

Sobre Docker: `docker-compose.yml` existe y es válido, pero **no funciona en
Windows Server sobre EC2** (Docker Desktop no lo soporta, y WSL2/Hyper-V
necesitan virtualización anidada, que una instancia ya virtualizada no da).
Por eso aquí van instaladas de forma nativa.

</details>

### 6. Arrancar

```bash
# API  → http://localhost:8000  (docs en /docs)
scripts\start-backend.bat

# Web → http://localhost:3000
scripts\start-frontend.bat
```

En Linux/macOS, los mismos comandos sin la extensión: `bash scripts/start-backend.sh`.
El script de la web compila antes de arrancar si no hay build, así que la
primera vez tarda.

### 7. Comprobar que funciona

```bash
curl http://127.0.0.1:8000/health          # {"status":"ok"}
```

Y una consulta de verdad, que devuelve la wallet más activa del último bloque
con su serie:

```bash
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"mensaje":"que wallet se movio mas en los ultimos 3 bloques"}'
```

---

## Verificar que algo está roto

Este proyecto tiene verificadores propios, porque hay fallos que no rompen la
página: rompen el dibujo. Antes de decir que algo funciona:

```bash
python -m pytest agents/tests backend/tests -q   # 325 tests
python scripts/verificar_bases.py                # estado REAL de ambas bases
python scripts/verificar_sprites.py              # los sprites pixel-art
python scripts/verificar_balance_usd.py          # el balance no se pierde
cd frontend && npm run build                     # build limpio (borra .next antes)
```

`verificar_bases.py` no se fía de lo que dice la API: cuenta filas y nodos
directamente. La respuesta del endpoint incluye un campo `persistence` con el
resultado de cada escritura:

```json
"persistence": {
  "postgres": "ok",
  "neo4j": "failed: ServiceUnavailable: Could not perform discovery. No routing servers are available."
}
```

Eso es lo que evita el fallo más feo de todos: un `200 OK` que no dice que nada
se guardó.

---

## Lo que todavía no funciona

Está aquí a propósito, para no perder tiempo buscando lo que no está:

- **El indexer no escribe nada.** `indexer/src/main.ts` recorre bloques pero su
  handler solo hace `ctx.log.info`; no hay `ctx.store.upsert` en ninguna parte,
  ni migraciones generadas. `raw_transactions` está a 0 aunque la base esté
  levantada. Es una plantilla de Subsquid, no un indexer.
- **`TRANSACTED_WITH` no existe.** El grafo solo escribe `SENT` y `TO`
  (`backend/app/db/neo4j_driver.py:26`). Preguntar por ese tipo de relación
  devuelve 0 siempre, tenga datos o no; Neo4j avisa con
  `UnknownRelationshipTypeWarning`.
- **No hay endpoints** de historial, tokens, transfers ni listados de contratos.
  Los 28 que existen están en `http://localhost:8000/docs`.
- **El score se abstiene con muestra pequeña.** Con menos de 8 transacciones devuelve `risk_score: null` y el motivo. Es deliberado: un 0/100 sobre
  una muestra de 2 transacciones es apariencia de análisis.

---

## Despliegue en la web: se recomienda local

**Netlify no es el sitio adecuado para este proyecto**, y la configuración que
hay en `frontend/netlify.toml` está solo por si alguien la quiere probar. El
motivo es de arquitectura, no de Netlify:

1. La web **no tiene datos propios**: todo viene de la API de ChainMind, que
   está pensada para `127.0.0.1`. En Netlify, el navegador pediría a un
   backend que hay que publicar, exponer y proteger.
2. `frontend/lib/api.ts` ya lee `NEXT_PUBLIC_API_URL`, así que la URL es
   configurable, pero eso no resuelve el punto 1.
3. El build **antes estaba roto** y solo pasaba por el caché de `.next`; ya
   está arreglado y compila limpio, pero es un aviso de que la web depende de
   un backend que casi nunca está levantado.

**Recomendación: ejecútalo en local** con los dos scripts de arriba. Es la
forma en que está pensado y probado, y la única donde la API, las bases y la
web están en la misma máquina.

Si aun así lo pruebas en Netlify: base directory `frontend`, y define
`NEXT_PUBLIC_API_URL` en *Site settings → Environment variables*.

---

## API

28 endpoints, todos en `http://localhost:8000/docs`. Los principales:

| Endpoint | Qué hace |
|---|---|
| `POST /analyze-wallet` | Perfil, score, factores y explicación de una wallet |
| `POST /analyze-contract` | Bytecode, permisos y hallazgos de un contrato |
| `POST /investigate` | Rastrea por dónde ha pasado el dinero |
| `POST /chat` | Preguntas en lenguaje llano, con serie temporal y ranking |
| `GET /feed/{chain}` | Actividad y anomalías de los últimos bloques |
| `GET /status` | Qué proveedor de IA está activo, cuánto ha costado, estado del centinela |
| `POST /keys` · `GET /keys` | Claves propias de ChainMind |

### Claves de API

Desde `localhost` no hace falta clave. Desde fuera, sí:

```bash
curl -X POST http://127.0.0.1:8000/keys -H "Content-Type: application/json" \
  -d '{"nombre":"mi-bot"}'          # la clave se muestra UNA vez, se guarda hasheada
curl -H "X-API-Key: cm_..." http://127.0.0.1:8000/analyze-wallet \
  -H "Content-Type: application/json" \
  -d '{"address":"0xd8dA...6045","chain":"ethereum"}'
```

El servidor escucha solo en `127.0.0.1` a propósito. Si lo expones, la clave
deja de ser opcional: ver la sección de seguridad de `AGENTS.md`.

Las claves de **ChainMind** y las de los **proveedores de IA** son cosas
distintas: las primeras autorizan a quien llama, las segundos no se devuelven
por ningún endpoint (hay un test que lo comprueba) y viven en `.env`, que está
en `.gitignore`.

---

## Proveedores de IA

Orden de preferencia: `ollama → anthropic → openai → gemini → groq →
openrouter`, o fuerza uno con `CHAINMIND_LLM_PROVIDER`.

| Proveedor | Variable |
|---|---|
| Ollama (local, sin clave) | — |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google | `GEMINI_API_KEY` |
| Groq / OpenRouter | `GROQ_API_KEY` / `OPENROUTER_API_KEY` |
| Compatible con OpenAI | `CHAINMIND_LLM_BASE_URL` |

**Una respuesta de IA nunca se publica sin validar.** Si no hay proveedor, si
falla, o si el texto no supera el filtro, se devuelve el texto determinista del
agente. El filtro descarta acusaciones, intenciones criminales, invenciones y textos
que contradigan el score.

---

## Estructura

```
/frontend   Next.js 14 (App Router) + React + TS + Tailwind
/backend    FastAPI (Python)
/agents     la lógica: perfil, riesgo, contratos, anomalías, chat, watcher
/indexer    plantilla de Subsquid EVM (hoy no escribe nada)
/db         init.sql de Postgres e init.cypher de Neo4j
/scripts    verificadores ejecutables
/docs, /jobs, /AGENTS.md
```

`AGENTS.md` es el documento para quien trabaje en el código con una IA: reglas
del proyecto, qué verificar antes de dar algo por bueno, cómo está montado el
chat y qué avisos hay.

---

## Licencia

MIT.
