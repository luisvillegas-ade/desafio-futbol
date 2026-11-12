"""Monitor en tiempo real — estética TUI / retro-terminal (modo oscuro).

`/monitor` sirve la página shell; `/monitor/datos` devuelve un JSON con los
fragmentos HTML ya renderizados y la página los inyecta cada ~1s.

Layout tipo Bento Grid: barra de estado arriba, bitácora de reglas a la
izquierda, grafo de orquestación en el centro, log de sesión abajo.
Cada caja usa títulos incrustados estilo fieldset, esquinas rectas y bordes
finos — como htop/btop pero judicial.
"""
import html
import json

from .. import db
from ..auditoria.verificar_cadena import verificar

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0A0A0A;color:#E4E4E7;
font-family:'JetBrains Mono','Fira Code',Consolas,'Courier New',monospace;
font-size:12px;line-height:1.45}
a{color:#38BDF8;text-decoration:none}
.grid{display:grid;gap:8px;padding:8px;grid-template-columns:290px 1fr;
grid-template-rows:auto 1fr auto;height:100vh}
.hdr{grid-column:1/3}
fieldset{border:1px solid #27272A;background:#111113;margin:0;padding:8px;
border-radius:0;min-width:0;overflow:hidden}
legend{padding:0 6px;color:#71717A;font-size:11px;letter-spacing:.5px}
.coral{color:#F87171}.cyan{color:#38BDF8}.mint{color:#4ADE80}
.amber{color:#FB923C}.dim{color:#71717A}.rojo{color:#F87171}
table{width:100%;border-collapse:collapse;font-size:11px}
td,th{padding:3px 6px;border-bottom:1px solid #1b1b1e;text-align:left;
vertical-align:top;white-space:nowrap}
th{color:#71717A;font-weight:400}
.pill{display:inline-block;border:1px solid #27272A;padding:0 5px;margin:1px 2px;
font-size:11px;white-space:nowrap}
.p-cyan{border-color:#0c4a6e;color:#38BDF8}
.p-coral{border-color:#7f1d1d;color:#F87171}
.p-mint{border-color:#14532d;color:#4ADE80}
.p-amber{border-color:#7c2d12;color:#FB923C}
.p-dim{border-color:#27272A;color:#71717A}
.barra{color:#4ADE80;letter-spacing:1px}
.nodo{border:1px solid #27272A;background:#111113;padding:6px 10px}
.nodo.b-cor{border-color:#7f1d1d}
.nodo.b-cyan{border-color:#0c4a6e}
.bajada{width:1px;height:14px;background:#27272A;margin:0 auto}
.puente{border-top:1px solid #27272A;margin:0 auto;width:70%}
.ramas{display:flex;gap:8px;justify-content:space-evenly}
.rama{flex:1;display:flex;flex-direction:column;align-items:center}
.rama .bajada{height:10px}
.flecha{color:#27272A;font-size:10px;line-height:1}
.kv{display:flex;justify-content:space-between;gap:8px;white-space:nowrap}
.log-td{white-space:normal}
.scroll{overflow-y:auto;max-height:100%}
"""

AGENTE = {
    "deteccion": "deteccion", "deteccion_descartada": "deteccion",
    "peritaje": "peritaje", "dictamen": "juez", "despacho": "despacho",
    "confirmacion": "isps", "reclamo": "ccc-reclamos",
    "levantamiento": "ccc-reclamos", "plataforma_iniciada": "sistema",
    "cambio_turno": "plazos",
}

CLASE_ESTADO = {"aplicada": "p-mint", "recibida": "p-amber",
                "fallida": "p-coral", "levantada": "p-dim",
                "vencida": "p-dim"}


def _e(x) -> str:
    return html.escape(str(x))


def barra(pct: float, ancho: int = 22) -> str:
    pct = max(0.0, min(1.0, pct))
    n = int(round(pct * ancho))
    return "█" * n + "░" * (ancho - n)


def dot(estado: str) -> str:
    c = {"running": "cyan", "verifying": "amber", "done": "mint",
         "idle": "dim", "error": "rojo"}.get(estado, "dim")
    return f"<span class={c}>●</span> <span class=dim>{estado}</span>"


def _conteos():
    return {r["tipo"]: r["c"] for r in db.q(
        "SELECT tipo, COUNT(*) c FROM actuaciones GROUP BY tipo")}


def frag_header(reloj, turnos, modo) -> str:
    ahora, fin = reloj.ahora(), reloj.fin_min
    t, jz, j = turnos.de_turno(ahora)
    exps = db.q("SELECT estado, COUNT(*) c FROM expedientes GROUP BY estado")
    n_exp = sum(r["c"] for r in exps)
    en_ejec = sum(r["c"] for r in exps if r["estado"] == "en_ejecucion")
    n_ord_act = db.q1("SELECT COUNT(*) c FROM ordenes WHERE estado IN "
                      "('recibida','aplicada')")["c"]
    n_rec = db.q1("SELECT COUNT(*) c FROM reclamos")["c"]
    acts = db.q("SELECT expediente_id,n,tipo,detalle,minuto,hash_prev,"
                "hash_actual FROM actuaciones ORDER BY id")
    ok_cadena, _ = verificar(acts)
    estado = ("<span class=mint>■ FINALIZADO</span>" if reloj.finalizado
              else "<span class=mint>● EN VIVO</span>")
    cadena = ("<span class=mint>✓ ÍNTEGRA</span>" if ok_cadena
              else "<span class=rojo>✗ TAMPERADA</span>")
    turno = (f"{_e(j['id'])} →{t['hasta_min']:g}" if t else "—")
    p = ahora / fin if fin else 0
    return (f"{estado} &nbsp;motor cautelar v1 · modo {_e(modo)}"
            f" &nbsp;|&nbsp; PARTIDO min {ahora:.1f}/{fin:.0f} "
            f"<span class=barra>{barra(p, 24)}</span>"
            f" &nbsp;|&nbsp; turno <span class=cyan>{turno}</span>"
            f" &nbsp;|&nbsp; expedientes {en_ejec}/{n_exp} · órdenes activas "
            f"{n_ord_act} · reclamos {n_rec}"
            f" &nbsp;|&nbsp; cadena {cadena}")


def frag_bitacora() -> str:
    c = _conteos()
    filas = "".join(
        f"<div class=kv><span>{_e(k)}</span><span class=cyan>{v}</span></div>"
        for k, v in sorted(c.items(), key=lambda x: -x[1]))
    ult = db.q("SELECT expediente_id,n,tipo,detalle,minuto FROM actuaciones "
               "ORDER BY id DESC LIMIT 14")
    log = "".join(
        f"<div class=kv><span class=dim>{a['minuto']:6.1f}</span>"
        f"<span class='pill p-dim'>F°{a['n']}</span>"
        f"<span title=\"{_e(a['detalle'])}\">{_e(a['tipo'])}</span></div>"
        f"<div class=dim style='padding:0 6px 4px 6px;font-size:11px'>"
        f"{_e(a['detalle'][:64])}</div>"
        for a in reversed(ult))
    return (f"<div class=dim>REGLAS APLICADAS (actuaciones)</div>{filas}"
            f"<hr style='border:0;border-top:1px solid #27272A;margin:8px 0'>"
            f"<div class=dim>ÚLTIMAS FOJAS</div>{log}")


def _isps():
    filas = db.q(
        "SELECT proveedor_id, estado, COUNT(*) c FROM ordenes "
        "GROUP BY proveedor_id, estado")
    por = {}
    for r in filas:
        por.setdefault(r["proveedor_id"], {})[r["estado"]] = r["c"]
    return por


def frag_grafo(reloj, turnos, modo, poller) -> str:
    ahora, fin = reloj.ahora(), reloj.fin_min
    t, jz, j = turnos.de_turno(ahora)

    exps = db.q("SELECT estado, COUNT(*) c FROM expedientes GROUP BY estado")
    n_exp = sum(r["c"] for r in exps)
    en_ejec = sum(r["c"] for r in exps
                  if r["estado"] in ("en_ejecucion", "aprobado", "cerrado"))
    c = _conteos()
    n_det = c.get("deteccion", 0) + c.get("deteccion_descartada", 0)
    cola = poller.cola.qsize() if poller else 0
    n_ord = db.q1("SELECT COUNT(*) c FROM ordenes")["c"]
    n_apl = db.q1("SELECT COUNT(*) c FROM ordenes WHERE estado='aplicada'")["c"]
    n_rec = db.q1("SELECT COUNT(*) c FROM reclamos")["c"]

    # --- nodo orquestador (coral) ---
    p_bloq = en_ejec / n_exp if n_exp else 0
    orch = (f"<div class='nodo b-cor'><div class=coral>"
            f"JUEZ / MOTOR CENTRAL — coordinación cautelar</div>"
            f"<div class=dim>modo {_e(modo)} · cobertura cautelar</div>"
            f"<div><span class=barra>{barra(p_bloq, 34)}</span> "
            f"{p_bloq * 100:.0f}% ({en_ejec}/{n_exp} exps en ejecución)</div>"
            f"</div>")

    # --- agente detección (cyan) ---
    est_det = "done" if reloj.finalizado else "running"
    p_det = n_det / (n_det + cola) if n_det + cola else 0
    a_det = (f"<div class='nodo b-cyan'><span class='pill p-cyan'>detección</span>"
             f" {dot(est_det)}"
             f"<div class=dim>señales clasificadas {n_det} · cola {cola}</div>"
             f"<div><span class=barra>{barra(p_det, 24)}</span></div></div>")

    # --- agente peritaje (cyan) ---
    est_per = "done" if reloj.finalizado else ("running" if n_det else "idle")
    p_per = en_ejec / n_exp if n_exp else 0
    a_per = (f"<div class='nodo b-cyan'><span class='pill p-cyan'>peritaje</span>"
             f" {dot(est_per)}"
             f"<div class=dim>marca+DNS pasivo · {c.get('peritaje', 0)} dictámenes</div>"
             f"<div><span class=barra>{barra(p_per, 24)}</span></div></div>")

    # --- agente plazos/turnos (cyan) ---
    if t:
        buffer = ahora >= t["hasta_min"] - 0.6
        est_pl = "done" if reloj.finalizado else (
            "verifying" if buffer else "running")
        dur = t["hasta_min"] - t["desde_min"]
        p_pl = (ahora - t["desde_min"]) / dur if dur else 0
        txt_pl = (f"{_e(j['id'])}<br>hasta min {t['hasta_min']:g}"
                  + (" · BUFFER" if buffer else ""))
    else:
        est_pl, p_pl, txt_pl = "idle", 0, "—"
    a_pl = (f"<div class='nodo b-cyan'><span class='pill p-cyan'>plazos/turnos</span>"
            f" {dot(est_pl)}<div class=dim>{txt_pl}</div>"
            f"<div><span class=barra>{barra(p_pl, 24)}</span></div></div>")

    # --- síntesis: despacho a ISPs (coral) ---
    isps = _isps()
    pills = []
    for prov in ("aurora", "andina", "cumbre", "valle"):
        st = isps.get(prov, {})
        txt = " ".join(f"{v}{k[0]}" for k, v in sorted(st.items())) or "—"
        cls = "p-mint" if st.get("aplicada") else (
            "p-amber" if st.get("recibida") else "p-dim")
        pills.append(f"<span class='pill {cls}'>[{prov}] {txt}</span>")
    pend = db.q1("SELECT COUNT(*) c FROM ordenes WHERE estado='recibida'")["c"]
    est_syn = ("done" if reloj.finalizado and not pend else
               "verifying" if pend else "running")
    sin = (f"<div class='nodo b-cor'><div class=coral>"
           f"SÍNTESIS — despacho a proveedores</div> {dot(est_syn)}"
           f"<div>{''.join(pills)}</div>"
           f"<div class=dim>aplicadas {n_apl}/{n_ord} · pendientes {pend} · "
           f"reclamos {n_rec}</div></div>")

    return (f"{orch}<div class=bajada></div><div class=puente></div>"
            f"<div class=ramas>"
            f"<div class=rama><div class=bajada></div><div class=flecha>▼</div>{a_det}</div>"
            f"<div class=rama><div class=bajada></div><div class=flecha>▼</div>{a_per}</div>"
            f"<div class=rama><div class=bajada></div><div class=flecha>▼</div>{a_pl}</div>"
            f"</div><div class=puente style='margin-top:8px'></div>"
            f"<div class=bajada></div><div class=flecha>▼</div>{sin}")


def frag_log() -> str:
    acts = db.q("SELECT expediente_id,n,tipo,detalle,minuto,hash_actual "
                "FROM actuaciones ORDER BY id DESC LIMIT 30")
    filas = "".join(
        f"<tr><td class=dim>{a['minuto']:6.2f}</td>"
        f"<td><span class='pill p-cyan'>[{AGENTE.get(a['tipo'], 'sistema')}]</span></td>"
        f"<td>{_e(a['tipo'])}</td>"
        f"<td class=dim>{_e(a['expediente_id'] or 'SISTEMA')} F°{a['n']}</td>"
        f"<td class='log-td dim'>{_e(a['detalle'])}</td>"
        f"<td class=dim>{_e(a['hash_actual'][:10])}</td></tr>"
        for a in acts)
    return (f"<table><tr><th>min</th><th>agente</th><th>acción</th>"
            f"<th>expediente/foja</th><th>detalle</th><th>hash</th></tr>"
            f"{filas}</table>")


def fragmentos(reloj, turnos, modo, poller) -> dict:
    return {
        "hdr": frag_header(reloj, turnos, modo),
        "bitacora": frag_bitacora(),
        "grafo": frag_grafo(reloj, turnos, modo, poller),
        "log": frag_log(),
    }


def pagina() -> str:
    return f"""<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>monitor — plataforma cautelar</title><style>{CSS}</style></head>
<body><div class=grid>
<fieldset class=hdr><legend>estado del sistema</legend><div id=hdr>…</div></fieldset>
<fieldset class=scroll><legend>bitácora · reglas procesales</legend><div id=bitacora>…</div></fieldset>
<fieldset class=scroll><legend>orquestación cautelar</legend><div id=grafo>…</div></fieldset>
<fieldset class=hdr scroll><legend>session log</legend><div id=log>…</div></fieldset>
</div><script>
async function tick(){{
  try{{
    const r = await fetch('/monitor/datos');
    const d = await r.json();
    for (const k in d) {{
      const e = document.getElementById(k);
      if (e) e.innerHTML = d[k];
    }}
  }} catch(e) {{}}
  setTimeout(tick, 800);
}}
tick();
</script></body></html>"""


def datos_json(reloj, turnos, modo, poller) -> bytes:
    return json.dumps(fragmentos(reloj, turnos, modo, poller),
                      ensure_ascii=False).encode("utf-8")
