"""Monitor en tiempo real — una sola pantalla, sin scroll.

`/monitor` sirve la página shell; `/monitor/datos` devuelve fragmentos HTML
que la página inyecta cada ~0,9 s. Layout tipo btop/bento: header, leyenda,
sidebar (bitácora), grafo de orquestación compacto en el centro, session
log abajo y status bar. Todo cabe en el viewport (`100vh`, overflow hidden;
solo el log y la bitácora scrollean por dentro).
"""
import html
import json

from .. import db
from ..auditoria.verificar_cadena import verificar

CSS = """
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{background:#0A0A0A;color:#E4E4E7;overflow:hidden;
font-family:'JetBrains Mono','Fira Code',Consolas,'Courier New',monospace;
font-size:11px;line-height:1.4}
a{color:#38BDF8;text-decoration:none}
.grid{display:grid;gap:6px;padding:6px;height:100vh;
grid-template-columns:250px 1fr;
grid-template-rows:auto auto minmax(0,1fr) minmax(110px,26vh) auto;
grid-template-areas:"hdr hdr" "legend legend" "side center" "log log"
 "status status"}
fieldset{border:1px solid #27272A;background:#111113;margin:0;padding:5px 8px;
border-radius:0;min-width:0;min-height:0;overflow:hidden}
legend{padding:0 5px;color:#71717A;font-size:10px;letter-spacing:.6px}
.coral{color:#F87171}.cyan{color:#38BDF8}.mint{color:#4ADE80}
.amber{color:#FB923C}.violet{color:#C084FC}.dim{color:#71717A}
table{width:100%;border-collapse:collapse;font-size:10.5px}
td,th{padding:2px 6px;border-bottom:1px solid #1b1b1e;text-align:left;
vertical-align:top;white-space:nowrap}
td.d{white-space:normal;color:#71717A}
th{color:#71717A;font-weight:400}
.pill{display:inline-block;border:1px solid #27272A;padding:0 4px;margin:0 2px 1px 0;
font-size:10px;white-space:nowrap}
.p-cyan{border-color:#155e75;color:#38BDF8}
.p-coral{border-color:#7f1d1d;color:#F87171}
.p-mint{border-color:#14532d;color:#4ADE80}
.p-amber{border-color:#7c2d12;color:#FB923C}
.p-violet{border-color:#4c1d95;color:#C084FC}
.p-dim{border-color:#27272A;color:#71717A}
.barra{color:#4ADE80;letter-spacing:1px}
.barra-c{color:#38BDF8;letter-spacing:1px}
.barwrap{display:inline-block;height:9px;background:#161618;
border:1px solid #27272A;vertical-align:middle}
.barfill{display:block;height:100%}
.nodo{border:1px solid #27272A;background:#161618;padding:4px 8px}
.nodo.b-cor{border-color:#7f1d1d}
.nodo.b-cyan{border-color:#155e75}
.nodo.b-mint{border-color:#14532d}
.link{display:flex;align-items:center;gap:6px;color:#3f3f46;padding:1px 0}
.link .ln{flex:1;border-top:1px dotted #3f3f46}
.link .tx{color:#52525b;font-size:10px;white-space:nowrap}
.ramas{display:flex;gap:6px}
.ramas .nodo{flex:1}
.deps{display:flex;gap:6px;margin-top:2px}
.dep{flex:1;border:1px solid #27272A;background:#161618;padding:3px 6px;
min-width:0}
.dep .dh{color:#71717A;font-size:10px;border-bottom:1px solid #27272A;
padding-bottom:2px;margin-bottom:3px;display:flex;justify-content:space-between}
.chip{display:block;font-size:10px;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis;padding:1px 0}
.chip .st{float:right}
.kv{display:flex;justify-content:space-between;gap:6px;white-space:nowrap}
.scroll{overflow-y:auto}
.tiny{font-size:10px}
"""

AGENTE = {
    "deteccion": "deteccion", "deteccion_descartada": "deteccion",
    "peritaje": "peritaje", "revision": "peritaje", "dictamen": "juez",
    "pase": "mesa", "despacho": "despacho", "confirmacion": "isps",
    "reclamo": "reclamos", "levantamiento": "reclamos",
    "plataforma_iniciada": "sistema", "cambio_turno": "plazos",
    "vencimiento": "plazos", "reintento": "despacho",
}

CLASE_ESTADO = {"aplicada": "p-mint", "recibida": "p-amber",
                "fallida": "p-coral", "levantada": "p-dim",
                "vencida": "p-dim"}


def _e(x) -> str:
    return html.escape(str(x))


def barra(pct: float, ancho: int = 18) -> str:
    pct = max(0.0, min(1.0, pct))
    n = int(round(pct * ancho))
    return "█" * n + "░" * (ancho - n)


def barcss(pct: float, px: int = 110, color: str = "#4ADE80") -> str:
    pct = max(0.0, min(1.0, pct))
    return (f"<span class=barwrap style='width:{px}px'><span class=barfill "
            f"style='width:{pct * 100:.0f}%;background:{color}'></span></span>")


def dot(estado: str) -> str:
    c = {"running": "cyan", "verifying": "amber", "done": "mint",
         "idle": "dim", "error": "coral"}.get(estado, "dim")
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
    cadena = ("<span class=mint>✓ cadena íntegra</span>" if ok_cadena
              else "<span class=coral>✗ TAMPERADA</span>")
    turno = (f"{_e(j['id'])} →{t['hasta_min']:g}" if t else "—")
    p = ahora / fin if fin else 0
    return (f"{estado} <b>PLATAFORMA CAUTELAR</b> · modo {_e(modo)}"
            f" · PARTIDO {barcss(p, 90, '#38BDF8')} "
            f"{ahora:.0f}/{fin:.0f}′"
            f" · turno <span class=cyan>{turno}</span>"
            f" · exp {en_ejec}/{n_exp} en ejec. · órdenes {n_ord_act} · "
            f"reclamos {n_rec} · {cadena}")


def frag_legend() -> str:
    return ("<span class='pill p-coral'>■</span> <span class=dim>juez / motor</span> "
            "<span class='pill p-cyan'>■</span> <span class=dim>agentes del motor</span> "
            "<span class='pill p-mint'>■</span> <span class=dim>aplicado / íntegro</span> "
            "<span class='pill p-amber'>■</span> <span class=dim>en trámite</span> "
            "<span class='pill p-violet'>■</span> <span class=dim>reclamos</span>")


def frag_bitacora() -> str:
    c = _conteos()
    filas = "".join(
        f"<div class=kv><span class=dim>{_e(k)}</span>"
        f"<span class=cyan>{v}</span></div>"
        for k, v in sorted(c.items(), key=lambda x: -x[1]))
    ult = db.q("SELECT n,tipo,detalle,minuto FROM actuaciones "
               "ORDER BY id DESC LIMIT 40")
    log = "".join(
        f"<div class=kv><span class=dim>{a['minuto']:5.1f}</span>"
        f"<span class='pill p-dim'>F°{a['n']}</span>"
        f"<span>{_e(a['tipo'])}</span></div>"
        f"<div class=dim tiny style='padding:0 0 3px 8px'>"
        f"{_e(a['detalle'][:58])}</div>"
        for a in ult)
    return (f"<div class=dim tiny>MOVIMIENTOS</div>{filas}"
            f"<hr style='border:0;border-top:1px solid #27272A;margin:5px 0'>"
            f"<div class=dim tiny>ÚLTIMAS FOJAS</div>{log}")


def _isps():
    filas = db.q(
        "SELECT proveedor_id, estado, COUNT(*) c FROM ordenes "
        "GROUP BY proveedor_id, estado")
    por = {}
    for r in filas:
        por.setdefault(r["proveedor_id"], {})[r["estado"]] = r["c"]
    return por


def _nodo_agente(nombre, estado, linea, pct) -> str:
    return (f"<div class='nodo b-cyan'><span class='pill p-cyan'>"
            f"[{_e(nombre)}]</span> {dot(estado)}"
            f"<div class=dim tiny>{linea}</div>"
            f"{barcss(pct, 90, '#38BDF8')}</div>")


def frag_grafo(reloj, turnos, modo, poller) -> str:
    ahora, fin = reloj.ahora(), reloj.fin_min
    t, jz, j = turnos.de_turno(ahora)

    exps = db.q("SELECT estado, COUNT(*) c FROM expedientes GROUP BY estado")
    n_exp = sum(r["c"] for r in exps)
    en_ejec = sum(r["c"] for r in exps
                  if r["estado"] in ("en_ejecucion", "aprobado", "cerrado"))
    pend_firma = sum(r["c"] for r in exps
                     if r["estado"] in ("detectado", "elevado"))
    c = _conteos()
    n_det = c.get("deteccion", 0) + c.get("deteccion_descartada", 0)
    cola = poller.cola.qsize() if poller else 0
    n_ord = db.q1("SELECT COUNT(*) c FROM ordenes")["c"]
    n_apl = db.q1("SELECT COUNT(*) c FROM ordenes WHERE estado='aplicada'")["c"]
    n_rec = db.q1("SELECT COUNT(*) c FROM reclamos")["c"]
    fin_run = reloj.finalizado

    # orquestador (coral)
    p_bloq = en_ejec / n_exp if n_exp else 0
    orch = (f"<div class='nodo b-cor'><span class=coral><b>JUEZ / MOTOR "
            f"CENTRAL</b> — coordinación cautelar · modo {_e(modo)}</span> "
            f"<span class=dim>cobertura</span> "
            f"{barcss(p_bloq, 150, '#4ADE80')} "
            f"{p_bloq * 100:.0f}% ({en_ejec}/{n_exp})"
            + (f" <span class='pill p-amber'>{pend_firma} esperando firma"
               f"</span>" if pend_firma else "")
            + "</div>")

    a_det = _nodo_agente(
        "deteccion",
        "done" if fin_run else "running",
        f"clasificadas {n_det} · cola {cola}",
        n_det / (n_det + cola) if n_det + cola else 0)
    a_per = _nodo_agente(
        "peritaje",
        "done" if fin_run else ("running" if n_det else "idle"),
        f"marca+DNS · {c.get('peritaje', 0)} dict.",
        en_ejec / n_exp if n_exp else 0)
    if t:
        buffer = ahora >= t["hasta_min"] - 0.6
        est_pl = "done" if fin_run else ("verifying" if buffer else "running")
        dur = t["hasta_min"] - t["desde_min"]
        p_pl = (ahora - t["desde_min"]) / dur if dur else 0
        txt_pl = f"{_e(j['id'])} →{t['hasta_min']:g}" + \
                 ("·BUFFER" if buffer else "")
    else:
        est_pl, p_pl, txt_pl = "idle", 0, "—"
    a_pl = _nodo_agente("plazos/turnos", est_pl, txt_pl, p_pl)

    isps = _isps()
    pills = []
    for prov in ("aurora", "andina", "cumbre", "valle"):
        st = isps.get(prov, {})
        txt = " ".join(f"{v}{k[0]}" for k, v in sorted(st.items())) or "—"
        cls = "p-mint" if st.get("aplicada") else (
            "p-amber" if st.get("recibida") else "p-dim")
        pills.append(f"<span class='pill {cls}'>[{prov}] {txt}</span>")
    pend = db.q1("SELECT COUNT(*) c FROM ordenes WHERE estado='recibida'")["c"]
    est_syn = ("done" if fin_run and not pend else
               "verifying" if pend else "running")
    sin = (f"<div class='nodo b-cor'><span class=coral><b>CONSOLIDACIÓN — "
           f"despacho a ISPs</b></span> {dot(est_syn)} "
           f"{''.join(pills)}<span class=dim tiny> aplicadas {n_apl}/{n_ord}"
           f" · pend {pend} · reclamos {n_rec}</span></div>")

    con = ("<div class=link><span class=ln></span>"
           "<span class=tx>▼</span><span class=ln></span></div>")

    # circuito procesal: expedientes por dependencia (kanban en vivo)
    DEPS = ("pericia", "secretaria", "juzgado", "despacho", "archivo")
    CLASE_EST = {"detectado": "dim", "elevado": "amber",
                 "aprobado": "cyan", "en_ejecucion": "mint",
                 "rechazado": "coral", "archivado": "dim", "cerrado": "dim"}
    filas_dep = db.q("SELECT id, fase_n, estado, dependencia FROM expedientes "
                     "ORDER BY creado_min")
    cols = {d: [] for d in DEPS}
    for e in filas_dep:
        d = e["dependencia"] or "pericia"
        if d not in cols:
            d = "pericia"
        cls = CLASE_EST.get(e["estado"], "dim")
        cols[d].append(
            f"<span class=chip><span class='pill p-{cls}'>"
            f"{_e(e['id'][9:])}·f{e['fase_n']}</span>"
            f"<span class='st dim'>{_e(e['estado'])}</span></span>")
    kanban = "<div class=deps>" + "".join(
        f"<div class=dep><div class=dh><span>{d}</span>"
        f"<span class=cyan>{len(cols[d])}</span></div>"
        + ("".join(cols[d][:6]) +
           (f"<span class='chip dim'>+{len(cols[d]) - 6} más</span>"
            if len(cols[d]) > 6 else "")
           or "<span class='chip dim'>—</span>")
        + "</div>" for d in DEPS) + "</div>"

    return (f"{orch}"
            f"<div class=link><span class=ln></span>"
            f"<span class=tx>delegra peritaje · agentes en paralelo ▼</span>"
            f"<span class=ln></span></div>"
            f"<div class=ramas>{a_det}{a_per}{a_pl}</div>"
            f"<div class=link><span class=ln></span>"
            f"<span class=tx>▲ consolidación de órdenes</span>"
            f"<span class=ln></span></div>"
            f"{sin}"
            f"<div class=link><span class=ln></span>"
            f"<span class=tx>circuito del expediente — pases entre "
            f"dependencias</span><span class=ln></span></div>"
            f"{kanban}")


def frag_log() -> str:
    acts = db.q("SELECT expediente_id,n,tipo,detalle,minuto "
                "FROM actuaciones ORDER BY id DESC LIMIT 30")
    filas = "".join(
        f"<tr><td class=dim>{a['minuto']:6.2f}</td>"
        f"<td><span class='pill p-cyan'>[{AGENTE.get(a['tipo'], 'sistema')}]"
        f"</span></td>"
        f"<td>{_e(a['tipo'])}</td>"
        f"<td class=dim>{_e(a['expediente_id'] or 'SISTEMA')} F°{a['n']}</td>"
        f"<td class=d>{_e(a['detalle'])}</td></tr>"
        for a in acts)
    return (f"<table><tr><th>min</th><th>agente</th><th>movimiento</th>"
            f"<th>exp/foja</th><th>detalle</th></tr>{filas}</table>")


def frag_status(reloj) -> str:
    n_act = db.q1("SELECT COUNT(*) c FROM actuaciones")["c"]
    ult = db.q1("SELECT n,tipo FROM actuaciones ORDER BY id DESC LIMIT 1")
    ult_txt = f"última F°{ult['n']} {_e(ult['tipo'])}" if ult else "—"
    return (f"<span class=dim>custodia:</span> {n_act} actuaciones · "
            f"{ult_txt} · <span class=dim>superficies públicas:</span> "
            f"<a href='/transparencia'>/transparencia</a> · "
            f"<a href='/reclamar'>/reclamar</a> · "
            f"<a href='/'>bandeja</a>")


def fragmentos(reloj, turnos, modo, poller) -> dict:
    return {
        "hdr": frag_header(reloj, turnos, modo),
        "legend": frag_legend(),
        "bitacora": frag_bitacora(),
        "grafo": frag_grafo(reloj, turnos, modo, poller),
        "log": frag_log(),
        "status": frag_status(reloj),
    }


def pagina() -> str:
    return f"""<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>monitor — plataforma cautelar</title><style>{CSS}</style></head>
<body><div class=grid>
<fieldset style="grid-area:hdr"><legend>estado del sistema</legend>
<div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
<div id=hdr style="min-width:0;overflow:hidden;text-overflow:ellipsis">…</div>
<div style="white-space:nowrap"><a href='/'><b>← consola</b></a> ·
<a href='/transparencia'>transparencia</a> · <a href='/reclamar'>reclamar</a>
</div></div></fieldset>
<fieldset style="grid-area:legend"><legend>leyenda</legend><div id=legend>…</div></fieldset>
<fieldset class=scroll style="grid-area:side"><legend>bitácora · reglas procesales</legend><div id=bitacora>…</div></fieldset>
<fieldset style="grid-area:center"><legend>orquestación cautelar — circuito en vivo</legend><div id=grafo>…</div></fieldset>
<fieldset class=scroll style="grid-area:log"><legend>session log — cadena de custodia en vivo</legend><div id=log>…</div></fieldset>
<fieldset style="grid-area:status"><legend>status</legend><div id=status>…</div></fieldset>
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
  setTimeout(tick, 900);
}}
tick();
</script></body></html>"""


def datos_json(reloj, turnos, modo, poller) -> bytes:
    return json.dumps(fragmentos(reloj, turnos, modo, poller),
                      ensure_ascii=False).encode("utf-8")
