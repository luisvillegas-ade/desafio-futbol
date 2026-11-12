"""Reloj del partido: cachea /estado y extrapola el minuto entre polls.

El minuto de partido avanza según `--acelerar` del simulador; extrapolar evita
depender del polling para decisiones sensibles al tiempo (buffer de turno).
"""
import threading
import time


class Reloj:
    def __init__(self):
        self._lock = threading.Lock()
        self._min = 0.0
        self._t = time.monotonic()
        self._acel = 1.0
        self.fin_min = 105.0
        self.jueces_turno = []
        self.finalizado = False

    def actualizar(self, estado: dict) -> None:
        with self._lock:
            self._min = float(estado["minuto_actual"])
            self._t = time.monotonic()
            self._acel = float(estado.get("acelerar") or 1.0)
            self.fin_min = float(estado["fin_min"])
            self.jueces_turno = estado.get("jueces_de_turno", [])
            self.finalizado = bool(estado.get("finalizado"))

    def ahora(self) -> float:
        with self._lock:
            return self._min + (time.monotonic() - self._t) * self._acel / 60.0

    def dormir_minutos(self, minutos: float) -> None:
        """Duerme el equivalente real a `minutos` de partido."""
        with self._lock:
            seg = minutos * 60.0 / max(self._acel, 1e-9)
        time.sleep(max(0.02, seg))
