# AGENTS.md

Contexto para cualquier agente que trabaje en este repositorio.

## Qué es ChainMind

Centro de inteligencia on-chain: siete agentes especializados que analizan
wallets y contratos (Ethereum y Base), vigilan la red en background, y
explican el resultado en lenguaje llano. Todo corre **en local**: el LLM es
Ollama (`phi4-mini` por defecto) y no hay claves de nube ni coste por token.

- `agents/` — lógica de análisis, agentes, LLM, centinela, Obsidian, watchlist
- `backend/app/` — API FastAPI (bind por defecto `127.0.0.1`, puerto 8000)
- `frontend/` — Next.js 14 (App Router, puerto 3000)
- `scripts/` — verificaciones ejecutables; úsalas antes de dar algo por bueno

## Verificación: obligatorio antes de decir que algo funciona

Este proyecto tiene verificadores propios porque hay partes que se rompen en
silencio (los sprites pixel-art, por ejemplo: una fila de 11 columnas no rompe
la página, rompe el dibujo). Antes de afirmar que algo está hecho:

```bash
python -m pytest agents/tests backend/tests -q   # 325 tests
python scripts/verificar_sprites.py              # anchuras de los sprites
python scripts/verificar_movimiento.py           # ciclo de los robots
python scripts/verificar_sala.py                 # que la sala se renderiza
cd frontend && npm run build                     # compilación
```

Si algo falla, se arregla o se dice. No se marca como terminado sin pasar.

## ECC instalado

Hay [ECC](https://github.com/affaan-m/ECC) (perfil `developer`, **sin hooks**)
instalado en `~/.config/opencode`, así que está disponible en este y en futuros
proyectos. Aporta 100 comandos, 56 skills y 25 agentes. Útil aquí sobre todo
`verification-loop` y `tdd-workflow`.

```bash
node ~/.config/opencode/ecc/scripts/ecc.js doctor        # estado
node ~/.config/opencode/ecc/scripts/ecc.js list-installed
node ~/.config/opencode/ecc/scripts/ecc.js uninstall      # revertir
```

**Las skills y comandos se cargan al abrir una sesión nueva**: dentro de una
sesión ya iniciada no aparecen como comandos nuevos. La copia del repo está en
`~/.config/opencode/ecc` y ahí se pueden leer directamente.

Se instaló sin hooks a propósito: los hooks ejecutan código en cada sesión y
modifican el comportamiento del agente sin pedir permiso. Si los quieres, es
`node scripts/ecc.js install --profile developer --target opencode --enable-hooks`.

## El chat

`agents/chat.py` decide en tres capas, y el orden importa:

1. **Tabla de intenciones** (sin IA): detecta dirección, red e intención.
2. **Herramientas reales**: `wallet`, `contrato`, `rastreo`, `top_wallets`,
   `comparar`, `resumen`, `feed`, `estado`, `watchlist`. Los datos los calcula
   el código, nunca el modelo.
3. **Enrutado por IA** (solo si las dos anteriores no resuelven): el modelo
   elige herramienta del catálogo y devuelve JSON. Sus argumentos se sanean
   (`_sanea_args`) y el nombre se resuelve contra el registro
   (`_coincide_herramienta`, tolera erratas). Si algo no cuadra, se cae al
   determinista.

Reglas que no hay que romper aquí:

- El `nombre` de `herramientas_publicas()` **es** la clave de `HERRAMIENTAS`.
  Si divergen, el modelo pide cosas que no existen.
- Las herramientas de agregado devuelven `serie` (una fila por bloque) y
  `ranking`. `frontend/components/ChatGrafico.tsx` los dibuja; el prompt de
  redacción solo nombra el gráfico que existe de verdad.
- Al modelo se le manda `_contexto_herramienta()`, no el dict crudo: el volcado
  se truncaba y la serie se perdía, y el modelo acababa diciendo que no había
  volumen.

## Las bases de datos en esta maquina

Docker **no se puede instalar aqui**: es Windows Server 2022 en EC2, sin gestor
de paquetes y sin virtualizacion anidada, y Docker Desktop no soporta Windows
Server. Postgres y Neo4j van instalados de forma nativa, con los mismos
nombres de usuario y contrasena que usa `docker-compose.yml`, para que los
defaults de `app/db/` sirvan sin variables de entorno:

- PostgreSQL 16.10 nativo, servicio `postgresql-x64-16`, puerto 5432,
  rol/base `chainmind` / `chainmind_dev`, schema creado con `db/postgres/init.sql`
- Neo4j 5.26.0 community en `C:\neo4j-community-5.26.0`, servicio `Neo4j`,
  puertos 7687 (bolt) y 7474 (http), contrasena fijada con
  `neo4j-admin dbms set-initial-password`, constraints de `db/neo4j/init.cypher`
- Java 21 (Temurin) en `C:\jdk-21.0.12.1+1`: Neo4j 5.26 no lo trae embebido
  y lo necesita en el PATH para `cypher-shell`

```bash
python scripts/verificar_bases.py      # estado real de ambas, no el "ok" de la API
psql -U chainmind -h 127.0.0.1 -d chainmind -c "SELECT count(*) FROM wallets"
```

Ojo con dos cosas que ya vale:

- **`TRANSACTED_WITH` no existe.** Solo se escriben `SENT` y `TO`
  (`backend/app/db/neo4j_driver.py:26`). Preguntar por ese tipo de relacion
  devuelve 0 siempre, tenga la base datos o no; Neo4j avisa con
  `UnknownRelationshipTypeWarning`.
- **El indexer sigue sin escribir nada.** `indexer/src/main.ts` solo hace
  `ctx.log.info`; `raw_transactions` esta a 0 aunque la base este levantada.

## Reglas del proyecto

- **No borrar trabajo existente.** Si algo se queda obsoleto, se avisa y se
  decide; no se borra por su cuenta.
- Un commit por fase, con el estilo del historial (`feat(scope):`, `fix(scope):`).
- Los secretos nunca se commitean: `data/` está en `.gitignore` y las claves
  se guardan hasheadas (SHA-256).
- La API es local por diseño. Si se expone en la red, el CORS deja de ser
  comodín (`CHAINMIND_CORS_ORIGINS`) y `/status` y `/anomaly/latest` exigen
  `X-API-Key`. No revertir eso a `*` sin revisar el análisis de seguridad.
