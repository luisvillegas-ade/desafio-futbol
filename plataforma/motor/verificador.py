"""Verificador pericial: marca de agua, licenciatarios y DNS pasivo.

Reglas duras (verificadas contra verificar.py y verdad_practica.json):

- Marca de licenciatario en dominio AUTORIZADO      -> transmisión legal, descartar.
- Marca de licenciatario en dominio NO autorizado   -> PIRATA (retransmisión ilegal).
- Marca oficial en cualquier dominio                -> PIRATA.
- Sin marca / marca de otro torneo                  -> descartar (falso positivo).

- "Dominio ajeno" = distinto dominio registrable (últimas 2 etiquetas).
  `espejo.pelotaya.test` comparte base con `s3.pelotaya.test` -> mismo operador.
- Si /dns-pasivo no tiene registros de la IP (404)   -> orden por dominio
  (el verificador no exige el tipo recomendado: un bloqueo por dominio cuenta
  igual para la fase y jamás produce daño colateral).
"""


SUFIJOS_COMPUESTOS = {
    # segundos niveles reservados donde el dominio registrable tiene 3 etiquetas
    "com.ar", "net.ar", "org.ar", "gob.ar", "gov.ar", "edu.ar", "mil.ar",
    "int.ar", "tur.ar", "musica.ar",
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.br", "com.mx", "com.co", "com.cl", "com.pe", "com.uy", "com.py",
    "com.bo", "com.ec", "com.ve", "com.au",
}


def dominio_base(host: str) -> str:
    """Dominio registrable del host (maneja TLDs compuestos tipo .com.ar)."""
    partes = host.lower().strip(".").split(".")
    if len(partes) >= 3 and ".".join(partes[-2:]) in SUFIJOS_COMPUESTOS:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:]) if len(partes) >= 2 else host


class Verificador:
    def __init__(self, cliente):
        self.cliente = cliente
        # reintenta hasta ~30 s: el sim puede no estar escuchando aún
        import time as _t
        espera = 0.5
        while True:
            st, partido = cliente.get("/partido")
            if st == 200:
                break
            if espera > 32:
                raise RuntimeError(f"No se pudo leer /partido: {st}")
            _t.sleep(espera)
            espera *= 2
        self.partido = partido
        self.prefijos = [p["prefijo"] for p in partido["marcas_de_agua_validas"]]
        self.licenciatarios = partido.get("licenciatarios", [])
        self.fin_min = float(partido["fin_min"])

    def clasificar(self, det: dict) -> str:
        """'pirata' | 'legal_licenciatario' | 'descartada'"""
        marca = det.get("marca_de_agua_extraida") or ""
        host = det["host_stream"]
        for lic in self.licenciatarios:
            if marca.startswith(lic["prefijo_marca"]):
                autorizado = any(host == d or host.endswith("." + d)
                                 for d in lic["dominios_autorizados"])
                return "legal_licenciatario" if autorizado else "pirata"
        if any(marca.startswith(p) for p in self.prefijos):
            return "pirata"
        return "descartada"

    def analizar_colateral(self, det: dict):
        """Devuelve (tipo, objetivo, dominios_vistos, dominios_ajenos)."""
        host, ip = det["host_stream"], det["ip_servidor"]
        st, resp = self.cliente.get(f"/dns-pasivo?ip={ip}")
        if st != 200:
            return "dominio", host, [], ["<sin registros de DNS pasivo>"]
        dominios = resp.get("dominios", [])
        ajenos = [d for d in dominios if dominio_base(d) != dominio_base(host)]
        if ajenos:
            return "dominio", host, dominios, ajenos
        return "ip", ip, dominios, ajenos
