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
python -m pytest agents/tests backend/tests -q   # 247 tests
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

## Reglas del proyecto

- **No borrar trabajo existente.** Si algo se queda obsoleto, se avisa y se
  decide; no se borra por su cuenta.
- Un commit por fase, con el estilo del historial (`feat(scope):`, `fix(scope):`).
- Los secretos nunca se commitean: `data/` está en `.gitignore` y las claves
  se guardan hasheadas (SHA-256).
- La API es local por diseño. Si se expone en la red, el CORS deja de ser
  comodín (`CHAINMIND_CORS_ORIGINS`) y `/status` y `/anomaly/latest` exigen
  `X-API-Key`. No revertir eso a `*` sin revisar el análisis de seguridad.
