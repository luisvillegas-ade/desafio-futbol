"""Generación de HTML server-side para la consola judicial y transparencia."""
import html
import json

CSS = """
body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#0f172a;color:#e2e8f0}
a{color:#7dd3fc;text-decoration:none}
a:hover{color:#bae6fd;text-decoration:underline}
header{background:#1e293b;padding:14px 24px;display:flex;justify-content:space-between;
align-items:center;border-bottom:1px solid #334155;position:sticky;top:0;z-index:10}
header h1{font-size:18px;margin:0;font-weight:600;letter-spacing:.2px}
header a{margin-left:14px}
main{padding:24px;max-width:1200px;margin:auto}
h2,h3{font-weight:600;color:#f1f5f9}
.card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px 20px;
margin-bottom:18px;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;
font-weight:600;white-space:nowrap}
.b-detectado{background:#475569}.b-elevado{background:#b45309}.b-aprobado{background:#0369a1}
.b-en_ejecucion{background:#15803d}.b-cerrado{background:#334155}.b-archivado{background:#7f1d1d}
.b-recibida{background:#b45309}.b-aplicada{background:#15803d}.b-fallida{background:#b91c1c}
.b-levantada{background:#6d28d9}.b-vencida{background:#334155}
.b-recibido{background:#b45309}.b-orden_levantada{background:#15803d}.b-desestimado{background:#334155}
.peritaje{background:#0b1220;border-left:3px solid #38bdf8;padding:10px 14px;margin:10px 0;
font-size:14px;border-radius:0 8px 8px 0}
button{background:#0369a1;color:#fff;border:0;border-radius:8px;padding:10px 18px;
font-size:14px;font-weight:600;cursor:pointer;transition:background .15s;margin:2px 4px 2px 0}
button:hover{background:#0284c7}
button.peligro{background:#b91c1c}button.peligro:hover{background:#dc2626}
button.sec{background:#475569}button.sec:hover{background:#64748b}
table{width:100%;border-collapse:collapse;font-size:14px;background:#1e293b;
border:1px solid #334155;border-radius:10px;overflow:hidden}
td,th{padding:9px 12px;border-bottom:1px solid #334155;text-align:left}
th{background:#0b1220;color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:#243349}
input{padding:10px 12px;border-radius:8px;border:1px solid #334155;background:#0b1220;
color:#e2e8f0;width:260px;font-size:14px}
input:focus{outline:2px solid #0369a1;border-color:#0369a1}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:13px}
.aviso{background:#7c2d12;padding:10px 14px;border-radius:8px;margin-bottom:12px}
"""

ESTADOS = {"detectado", "elevado", "aprobado", "en_ejecucion", "cerrado", "archivado"}


def _e(x) -> str:
    return html.escape(str(x))


def pagina(titulo: str, cuerpo: str, extra_head: str = "") -> str:
    return (f"<!doctype html><html lang=es><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<meta http-equiv=refresh content=4>"
            f"<title>{_e(titulo)}</title><style>{CSS}</style>{extra_head}</head>"
            f"<body>{cuerpo}</body></html>")


def header(titulo: str, derecha: str = "") -> str:
    return (f"<header><h1>{_e(titulo)}</h1><div>{derecha}</div></header>")


def login(error: str = "") -> str:
    err = f"<div class=aviso>{_e(error)}</div>" if error else ""
    return pagina("Ingreso judicial", header("Plataforma de Bloqueo en Vivo") + f"""
<main><div class=card style="max-width:380px;margin:60px auto">
<h2>Ingreso del juzgado</h2>{err}
<form method=post action=/login>
<p><input name=usuario placeholder=Usuario autofocus></p>
<p><input name=password type=password placeholder=Contraseña></p>
<p><button type=submit style="width:100%">Ingresar</button></p>
</form><p class=mono style="font-size:12px">Usuarios demo (clave: demo)<br>
jueces: laura · martin — firman solo de turno<br>
tramitación: secretario · operador — pases, revisión, informes<br>
admin — visión completa del sistema</p>
</div></main>""")


def bandeja(expedientes, juez: dict, turno_txt: str, minuto: float) -> str:
    es_juez = juez.get("rol") == "juez"
    filas = ""
    for e in expedientes:
        est = e["estado"]
        dep = e["dependencia"] if "dependencia" in e.keys() else "pericia"
        dep = dep or "pericia"
        botones = ""
        if es_juez and est in ("detectado", "elevado") and dep == "juzgado":
            botones = (f"<form method=post action='/exp/{_e(e['id'])}/aprobar' style='display:inline'>"
                       f"<button>Aprobar y mandar bloqueo urgente</button></form> "
                       f"<form method=post action='/exp/{_e(e['id'])}/forzar-ip' style='display:inline'>"
                       f"<button class=sec>Aprobar forzando IP</button></form> "
                       f"<form method=post action='/exp/{_e(e['id'])}/rechazar' style='display:inline'>"
                       f"<button class=peligro>Rechazar</button></form>")
        filas += (f"<tr><td><a href='/exp/{_e(e['id'])}' class=mono>{_e(e['id'])}</a> "
                  f"<span class=mono>fase {e['fase_n']}</span></td>"
                  f"<td class=mono>{_e(e['host_stream'])}<br>{_e(e['ip_servidor'])}</td>"
                  f"<td>{_e(e['tipo_bloqueo_recomendado'] or '')}</td>"
                  f"<td><span class='badge b-{est}'>{est}</span><br>"
                  f"<span class=mono style='font-size:11px;color:#94a3b8'>{_e(dep)}</span></td>"
                  f"<td class=mono>{e['creado_min']:.1f}</td><td>{botones}</td></tr>")
    if not filas:
        filas = "<tr><td colspan=6>Sin expedientes todavía.</td></tr>"
    rol_txt = juez.get("rol", "")
    return pagina("Bandeja del juez", header(
        "Consola Judicial — Bandeja de expedientes",
        f"{_e(juez['nombre'])} ({_e(rol_txt)}) · <a href='/monitor'>Monitor</a> · "
        f"<a href='/transparencia'>Transparencia</a> · "
        f"<a href='/salir'>Salir</a>") + f"""
<main>
<div class=peritaje>Minuto de partido <b>{minuto:.1f}</b> · { _e(turno_txt) }</div>
<table><tr><th>Expediente</th><th>Stream</th><th>Medida sugerida</th>
<th>Estado / dependencia</th><th>Min</th><th></th></tr>{filas}</table>
</main>""")


def _acciones(exp: dict, sesion: dict) -> str:
    """Barra de movimientos según rol y dependencia del expediente."""
    dep = exp.get("dependencia") or "pericia"
    rol = sesion.get("rol")
    eid = _e(exp["id"])

    def btn(accion, txt, cls=""):
        return (f"<form method=post action='/exp/{eid}/{accion}' "
                f"style='display:inline'><button class='{cls}'>{txt}</button></form>")

    out = []
    if rol in ("operador", "secretario", "admin"):
        if dep == "pericia":
            out.append(btn("pase-secretaria", "Pasar a Secretaría"))
            out.append(btn("pase-juzgado", "Elevar a firma (Juzgado)"))
        elif dep == "secretaria":
            out.append(btn("pase-juzgado", "Elevar a firma (Juzgado)"))
            out.append(btn("pase-pericia", "Devolver a Pericia", "sec"))
        elif dep == "juzgado":
            out.append(btn("pase-secretaria", "Devolver a Secretaría", "sec"))
        elif dep == "despacho":
            out.append("<span class=mono>medida en ejecución</span>")
    if rol == "juez":
        if dep == "juzgado" and exp["estado"] in ("detectado", "elevado"):
            out.append(btn("aprobar", "Aprobar y librar cautelar"))
            out.append(btn("forzar-ip", "Aprobar forzando IP", "sec"))
            out.append(btn("rechazar", "Rechazar", "peligro"))
        out.append(btn("pase-secretaria", "Devolver a Secretaría", "sec"))
    if rol in ("operador", "secretario", "juez", "admin"):
        out.append(btn("revision", "Iniciar revisión (re-peritaje)", "sec"))
    if rol in ("operador", "secretario", "juez", "admin") and dep == "despacho":
        out.append(btn("archivar", "Archivar definitivamente", "peligro"))
    out.append(f"<a href='/exp/{eid}/informe'><button type=button class=sec>"
               f"Emitir informe</button></a>")
    return " ".join(out)


def detalle(exp, evidencias, actuaciones, ordenes, reclamos_rows=(),
            sesion=None) -> str:
    def _promo(ev):
        canales = json.loads(ev["promocion"] or "[]")
        if not canales:
            return ""
        txt = ", ".join(f"{_e(c.get('red'))}" for c in canales)
        return f"<br>Difundido en: {txt}"
    ev = "".join(
        f"<div class=peritaje>Detección <b>{_e(x['deteccion_id'])}</b> min {x['minuto']} · "
        f"marca <span class=mono>{_e(x['marca_extraida'])}</span> · "
        f"SHA-256 captura <span class=mono>{_e(x['captura_sha256'][:20])}…</span>{_promo(x)}<br>"
        f"DNS pasivo: {_e(x['dominios_en_ip'])}</div>" for x in evidencias)
    acts = "".join(
        f"<tr><td class=mono>F°{a['n']}</td><td>{_e(a['tipo'])}</td><td>{_e(a['detalle'])}</td>"
        f"<td class=mono>{a['minuto']:.2f}</td><td class=mono>{_e(a['hash_actual'][:14])}…</td></tr>"
        for a in actuaciones)
    ords = "".join(
        f"<tr><td class=mono>{_e(o['orden_id'])}</td><td>{_e(o['proveedor_id'])}</td>"
        f"<td>{_e(o['tipo'])} → {_e(o['objetivo'])}</td>"
        f"<td><span class='badge b-{_e(o['estado'])}'>{_e(o['estado'])}</span></td>"
        f"<td class=mono>{_e(o['juez_id'])}</td></tr>" for o in ordenes)
    rec = reclamos(reclamos_rows) if reclamos_rows else ""
    dep = exp.get("dependencia") or "pericia"
    return pagina(f"Expediente {exp['id']}", header(
        f"{_e(exp['id'])} — «{_e(exp['stream_id'])}» s/ medida cautelar (fase {exp['fase_n']})",
        "<a href='/'>← Bandeja</a>") + f"""
<main>
<div class=card><b>Stream:</b> <span class=mono>{_e(exp['host_stream'])} · {_e(exp['ip_servidor'])} · ASN {_e(exp['asn'])}</span><br>
<b>Medida sugerida:</b> {_e(exp['tipo_bloqueo_recomendado'])} · <b>Estado:</b> {_e(exp['estado'])} ·
<b>Dependencia:</b> <span class='badge b-detectado'>{_e(dep)}</span></div>
<div class=card>{_acciones(exp, sesion or {})}</div>
<h3>Peritaje técnico</h3>{ev}
<h3>Órdenes libradas</h3>
<table><tr><th>Orden</th><th>Proveedor</th><th>Objetivo</th><th>Estado</th><th>Juez</th></tr>{ords}</table>
{rec}
<h3>Actuaciones — cadena de custodia (fojas)</h3>
<table><tr><th>Foja</th><th>Tipo</th><th>Detalle</th><th>Min</th><th>Hash</th></tr>{acts}</table>
</main>""")


def transparencia(ordenes, minuto: float) -> str:
    filas = "".join(
        f"<tr><td class=mono>{_e(o['orden_id'])}</td><td>{_e(o['proveedor_id'])}</td>"
        f"<td>{_e(o['tipo'])} → <span class=mono>{_e(o['objetivo'])}</span></td>"
        f"<td><span class='badge b-{_e(o['estado'])}'>{_e(o['estado'])}</span></td>"
        f"<td class=mono>{_e(o['juez_id'])}</td><td class=mono>min {o['vence_min']}</td></tr>"
        for o in ordenes)
    if not filas:
        filas = "<tr><td colspan=6>Aún no se dictaron medidas cautelares.</td></tr>"
    return pagina("Registro público de transparencia", header(
        "Registro Público de Transparencia — Medidas cautelares",
        "<a href='/monitor'>Monitor</a> · <a href='/'>Consola</a>") + f"""
<main><div class=peritaje>Minuto de partido {minuto:.1f}. Las órdenes por IP vencen
automáticamente al finalizar el partido.</div>
<table><tr><th>Orden</th><th>Proveedor</th><th>Objetivo</th><th>Estado</th>
<th>Juez</th><th>Vence</th></tr>{filas}</table></main>""")


def reclamos(reclamos_rows) -> str:
    filas = "".join(
        f"<tr><td class=mono>{_e(r['id'])}</td><td class=mono>{_e(r['dominio'])}</td>"
        f"<td>{_e(r['proveedor'])}</td><td>{_e(r['mensaje'])}</td>"
        f"<td><span class='badge b-{_e(r['estado'])}'>{_e(r['estado'])}</span></td></tr>"
        for r in reclamos_rows)
    return (f"<div class=card><h3>Reclamos de terceros</h3>"
            f"<table><tr><th>ID</th><th>Dominio</th><th>Proveedor</th><th>Mensaje</th>"
            f"<th>Estado</th></tr>{filas or '<tr><td colspan=5>Sin reclamos.</td></tr>'}"
            f"</table></div>")


def dumps_pretty(obj) -> str:
    return html.escape(json.dumps(obj, ensure_ascii=False, indent=2))


CSS_INFORME = """
body{font-family:Georgia,'Times New Roman',serif;color:#111;background:#fff;
margin:0;padding:32px;max-width:820px;margin:auto;font-size:13px;line-height:1.5}
h1{font-size:17px;text-align:center;margin:0}
h2{font-size:14px;margin:22px 0 6px}
.caratula{text-align:center;margin-bottom:18px}
.caratula p{margin:2px 0;font-size:12px;color:#333}
table{width:100%;border-collapse:collapse;font-size:12px;margin:6px 0}
td,th{border:1px solid #999;padding:4px 8px;text-align:left}
.mono{font-family:Consolas,monospace;font-size:11px}
.firma{margin-top:60px;display:flex;justify-content:space-around}
.firma div{text-align:center;border-top:1px solid #111;padding-top:6px;width:40%}
.nota{font-size:11px;color:#444;margin-top:24px}
@media print{.noprint{display:none}}
"""


def informe(exp, evidencias, actuaciones, ordenes, reclamos_rows) -> str:
    """Informe judicial imprimible del expediente (Ctrl+P → PDF)."""
    ev = "".join(
        f"<tr><td class=mono>{_e(x['deteccion_id'])}</td>"
        f"<td class=mono>{x['minuto']:.2f}</td>"
        f"<td class=mono>{_e(x['marca_extraida'])}</td>"
        f"<td class=mono>{_e(x['captura_sha256'][:24])}…</td></tr>"
        for x in evidencias)
    acts = "".join(
        f"<tr><td class=mono>F°{a['n']}</td><td>{_e(a['tipo'])}</td>"
        f"<td>{_e(a['detalle'])}</td><td class=mono>{a['minuto']:.2f}</td>"
        f"<td class=mono>{_e(a['hash_actual'][:16])}…</td></tr>"
        for a in actuaciones)
    ords = "".join(
        f"<tr><td class=mono>{_e(o['orden_id'])}</td><td>{_e(o['proveedor_id'])}</td>"
        f"<td>{_e(o['tipo'])}</td><td class=mono>{_e(o['objetivo'])}</td>"
        f"<td>{_e(o['estado'])}</td><td class=mono>{_e(o['juez_id'])}</td>"
        f"<td class=mono>{o['vence_min']}</td></tr>" for o in ordenes)
    recs = "".join(
        f"<tr><td class=mono>{_e(r['id'])}</td><td class=mono>{_e(r['dominio'])}</td>"
        f"<td>{_e(r['proveedor'])}</td><td>{_e(r['estado'])}</td></tr>"
        for r in reclamos_rows) or "<tr><td colspan=4>Sin reclamos.</td></tr>"
    dep = exp.get("dependencia") or "pericia"
    return (f"<!doctype html><html lang=es><head><meta charset=utf-8>"
            f"<title>Informe {_e(exp['id'])}</title><style>{CSS_INFORME}</style>"
            f"</head><body>"
            f"<p class=noprint><a href='/exp/{_e(exp['id'])}'>← volver</a> · "
            f"Ctrl+P para imprimir / guardar PDF</p>"
            f"<div class=caratula>"
            f"<h1>INFORME DE EXPEDIENTE ELECTRÓNICO</h1>"
            f"<p><b>{_e(exp['id'])}</b> — «{_e(exp['stream_id'])}» s/ MEDIDA "
            f"CAUTELAR URGENTE (fase {exp['fase_n']})</p>"
            f"<p>Plataforma Federal de Órdenes de Bloqueo en Vivo · "
            f"dependencia actual: {_e(dep)} · estado: {_e(exp['estado'])}</p></div>"
            f"<h2>I. Objeto de la medida</h2>"
            f"<p>Stream infractor: <span class=mono>{_e(exp['host_stream'])} · "
            f"{_e(exp['ip_servidor'])} · ASN {_e(exp['asn'])}</span><br>"
            f"Medida sugerida por el peritaje: <b>{_e(exp['tipo_bloqueo_recomendado'])}</b></p>"
            f"<h2>II. Peritaje técnico (evidencia)</h2>"
            f"<table><tr><th>Detección</th><th>Min</th><th>Marca de agua</th>"
            f"<th>SHA-256 captura</th></tr>{ev}</table>"
            f"<h2>III. Medidas libradas</h2>"
            f"<table><tr><th>Orden</th><th>Proveedor</th><th>Tipo</th>"
            f"<th>Objetivo</th><th>Estado</th><th>Juez</th><th>Vence</th></tr>"
            f"{ords}</table>"
            f"<h2>IV. Reclamos de terceros</h2>"
            f"<table><tr><th>ID</th><th>Dominio</th><th>Proveedor</th>"
            f"<th>Estado</th></tr>{recs}</table>"
            f"<h2>V. Actuaciones (cadena de custodia)</h2>"
            f"<table><tr><th>Foja</th><th>Tipo</th><th>Detalle</th><th>Min</th>"
            f"<th>Hash</th></tr>{acts}</table>"
            f"<div class=firma><div>Funcionario/a</div><div>Juez/a</div></div>"
            f"<p class=nota>Verificable: cada actuación encadena "
            f"sha256(hash_prev|tipo|detalle|minuto) con la anterior. "
            f"Recomputar: python -m plataforma.auditoria.verificar_cadena.</p>"
            f"</body></html>")


def reclamar(exito=None, error="") -> str:
    """Formulario público de reclamo (procedimiento sumario digital)."""
    aviso = ""
    if exito is not None:
        if exito:
            aviso = (f"<div class=card style='border-color:#15803d'>"
                     f"<b>Reclamo recibido.</b> Se localizaron y elevaron "
                     f"<b>{exito}</b> medida(s) que afectaban el dominio. "
                     f"El levantamiento firmado se ejecuta en minutos — seguilo "
                     f"en <a href='/transparencia'>transparencia</a> o "
                     f"<a href='/monitor'>monitor</a>.</div>")
        else:
            aviso = ("<div class=card><b>Reclamo registrado y desestimado:</b> "
                     "ninguna medida cautelar vigente afecta ese dominio.</div>")
    err = f"<div class=aviso>{_e(error)}</div>" if error else ""
    return pagina("Reclamo digital de sitio afectado", header(
        "Reclamo digital — sitio afectado por medida cautelar",
        "<a href='/transparencia'>Transparencia</a> · <a href='/monitor'>Monitor</a>") + f"""
<main><div class=card style="max-width:560px;margin:40px auto">
<h2>Procedimiento sumario de reclamos</h2>
<p class=mono style="font-size:13px">Si su sitio fue afectado por una medida
cautelar de bloqueo, presente aquí el dominio. La plataforma lo eleva al juez
de turno y ordena el levantamiento y su reemplazo por una medida más precisa.</p>
{err}{aviso}
<form method=post action=/reclamar>
<p><input name=dominio placeholder="midominio.test" required></p>
<p><input name=mensaje placeholder="Motivo (ej: mi tienda no carga desde hace 10 min)"></p>
<p><button type=submit>Presentar reclamo</button></p>
</form></div></main>""")
