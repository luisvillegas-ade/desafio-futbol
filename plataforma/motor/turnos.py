"""Turnos judiciales y protocolo de firma segura.

Regla clave del simulador: `juez_de_turno` se evalúa cuando el proveedor RECIBE
la orden, no cuando se firma. `esperar_firma_segura` bloquea la firma dentro del
margen previo al cambio de turno y espera al juez entrante, así ninguna orden
llega firmada por quien ya no está de turno.

IMPORTANTE: los reintentos (Cumbre) vuelven a pasar por acá — una orden que
falla al minuto 51 se reenvía firmada por el juez del NUEVO turno.
"""
import json

from .. import config


class Turnos:
    def __init__(self, reloj):
        datos = json.loads((config.DATOS_DIR / "juzgados.json").read_text(encoding="utf-8"))
        self.turnos = sorted(datos["turnos"], key=lambda t: t["desde_min"])
        self.jueces = {j["id"]: (jz, j)
                       for jz in datos["juzgados"] for j in jz["jueces"]}
        self.reloj = reloj

    def de_turno(self, minuto: float):
        """Devuelve (turno, juzgado, juez) que cubre `minuto`, o (None,None,None)."""
        for t in self.turnos:
            if t["desde_min"] <= minuto < t["hasta_min"]:
                jz, j = self.jueces[t["juez_id"]]
                return t, jz, j
        return None, None, None

    def juez_seguro(self, minuto: float = None,
                    margen: float = config.MARGEN_TURNO_MIN):
        """Quién podría firmar ahora sin riesgo de quedar fuera de turno.

        Devuelve (turno, juzgado, juez): el juez de turno si falta más que
        `margen` para el fin de su turno; si ya está dentro del buffer, el
        juez ENTRANTE (es el único cuya firma llegará vigente al proveedor);
        (None, None, None) si no hay nadie ahora ni después.
        """
        ahora = self.reloj.ahora() if minuto is None else minuto
        t, jz, j = self.de_turno(ahora)
        if t and ahora < t["hasta_min"] - margen:
            return t, jz, j
        proximos = [x["desde_min"] for x in self.turnos
                    if x["desde_min"] > ahora]
        if proximos:
            return self.de_turno(min(proximos) + 1e-6)
        return None, None, None

    def juez_por_id(self, juez_id: str):
        """(juzgado, juez) para un id de juez, o (None, None)."""
        return self.jueces.get(juez_id, (None, None))

    def esperar_firma_segura(self, margen: float = config.MARGEN_TURNO_MIN):
        """Espera hasta que sea seguro firmar y devuelve (turno, juzgado, juez).

        Si falta menos de `margen` para el fin del turno, duerme hasta el borde
        y firma ya con el juez entrante.
        """
        while True:
            ahora = self.reloj.ahora()
            t, jz, j = self.de_turno(ahora)
            if t and ahora < t["hasta_min"] - margen:
                return t, jz, j
            if t:
                falta = t["hasta_min"] - ahora
            else:
                proximos = [x["desde_min"] for x in self.turnos if x["desde_min"] > ahora]
                if not proximos:
                    return None, None, None  # pasado el último turno
                falta = min(proximos) - ahora
            self.reloj.dormir_minutos(max(falta, 0.02))
