"""Protección de endpoints pesados.

Dos riesgos reales que no estaban cubiertos:

1. `/feed/{chain}?max_blocks=10000` — sin techo, cada pedido dispara miles
   de llamadas RPC y tumba tanto el servidor como las APIs gratuitas.
2. Varias peticiones simultáneas de `/analyze*` — cada una satura la red y
   compite por los mismos cachés; lo útil es una sola a la vez.

El guard es por-workload (no por-IP): así el centinela, la UI y un script
propio siguen pudiendo trabajar en paralelo, pero dos análisis pesados
idénticos no se pisan. Nunca bloquea esperando: si hay cola llena, responde
429 con Retry-After. Eso es honesto y cacheable, mejor que un timeout opaco.
"""
import os
import threading
import time
from collections import defaultdict, deque

MAX_BLOCKS = int(os.getenv("CHAINMIND_MAX_BLOCKS", "5"))
MAX_CONCURRENCY = int(os.getenv("CHAINMIND_MAX_CONCURRENCY", "2"))
QUEUE_MAX = int(os.getenv("CHAINMIND_QUEUE_MAX", "3"))
CACHE_TTL = float(os.getenv("CHAINMIND_DEDUPE_TTL", "20"))

_lock = threading.Lock()
_slots: dict[str, int] = defaultdict(int)
_queue: dict[str, int] = defaultdict(int)
_recent: dict[str, deque] = defaultdict(deque)
_values: dict[str, tuple] = {}


class Busy(Exception):
    """No hay capacidad ahora mismo: la respuesta debe ser 429."""

    def __init__(self, workload: str, queued: int):
        self.workload = workload
        self.queued = queued
        self.retry_after = 2
        super().__init__(f"{workload}: ya hay {queued} peticiones en curso")


class work:
    """Guard de carga para un endpoint caro.

    Uso:
        with work("feed:ethereum", key=since) as slot:
            cached = slot.reuse()
            if cached is not None:
                return cached
            result = scan(...)
            slot.remember(result)
            return result

    Además de limitar la concurrencia, guarda el resultado de la petición
    durante CACHE_TTL: la UI refresca cada 12 s y con TTL de 20 s la mitad
    de los refrescos no vuelven a golpear la red. Reutilizar el resultado
    anterior es correcto aquí porque el feed se reconstruye igual desde caché
    de bloque; para datos que deben ser frescos, no pasar `key`.
    """

    def __init__(self, workload: str, key: str | None = None):
        self.workload = workload
        self.key = f"{workload}:{key}" if key is not None else None
        self._held = False
        self._queued = False

    def reuse(self):
        """Devuelve el resultado anterior si sigue fresco; None si hay que trabajar."""
        if self.key is None:
            return None
        with _lock:
            _recent[self.key] = deque(
                [t for t in _recent[self.key] if time.time() - t < CACHE_TTL], maxlen=8
            )
            if not _recent[self.key]:
                return None
            return _values.get(self.key)

    def remember(self, value):
        if self.key is not None:
            with _lock:
                _values[self.key] = value
                _recent[self.key] = deque([time.time()], maxlen=8)
        return value

    def __enter__(self):
        with _lock:
            if _slots[self.workload] + _queue[self.workload] >= MAX_CONCURRENCY + QUEUE_MAX:
                raise Busy(self.workload, _slots[self.workload] + _queue[self.workload])
            _queue[self.workload] += 1
            self._queued = True
        deadline = time.time() + 30  # si la cola se atasca, se libera igual
        while True:
            with _lock:
                if _slots[self.workload] < MAX_CONCURRENCY:
                    if self._queued:
                        _queue[self.workload] -= 1
                        self._queued = False
                    _slots[self.workload] += 1
                    self._held = True
                    return self
            if time.time() > deadline:
                with _lock:
                    # solo se descuenta lo que este objeto encoló: si otra
                    # instancia ya lo liberó, aquí aparecería un negativo
                    if self._queued:
                        _queue[self.workload] -= 1
                        self._queued = False
                raise Busy(self.workload, _slots[self.workload])
            time.sleep(0.1)

    def __exit__(self, *exc):
        if self._held:
            with _lock:
                _slots[self.workload] -= 1
            self._held = False
        return False


def stats() -> dict:
    with _lock:
        return {
            "max_concurrency": MAX_CONCURRENCY,
            "queue_max": QUEUE_MAX,
            "max_blocks": MAX_BLOCKS,
            "dedupe_ttl_s": CACHE_TTL,
            "in_flight": dict(_slots),
            "queued": dict(_queue),
        }


def reset():
    with _lock:
        _slots.clear()
        _queue.clear()
        _recent.clear()
        _values.clear()
