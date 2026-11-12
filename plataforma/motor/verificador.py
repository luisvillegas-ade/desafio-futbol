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


def dominio_base(host: str) -> str:
    partes = host.split(".")
    return ".".join(partes[-2:]) if len(partes) >= 2 else host


class Verificador:
    def __init__(self, cliente):
        st, partido = cliente.get("/partido")
        if st != 200:
            raise RuntimeError(f"No se pudo leer /partido: {st}")
        self.partido = partido
        self.cliente = cliente
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
