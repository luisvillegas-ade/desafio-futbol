"""Generación de HTML server-side para la consola judicial y transparencia."""
import hashlib
import html
import json

CSS = """
:root{--pjn-navy:#002b49;--pjn-navy-dark:#001f35;--pjn-blue:#005a9c;--pjn-sky:#e8f1f8;
--pjn-bg:#f4f6f8;--pjn-surface:#fff;--pjn-border:#d1d5db;--pjn-text:#1f2937;
--pjn-text-muted:#6b7280;--pjn-accent-gold:#c59b27;--pjn-badge-red:#b91c1c;
--pjn-badge-green:#15803d}
*{box-sizing:border-box}
body{font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;margin:0;
background:var(--pjn-bg);color:var(--pjn-text);font-size:14px;line-height:1.45}
a{color:var(--pjn-blue);text-decoration:none}
a:hover{text-decoration:underline}
.top-banner{background:var(--pjn-navy-dark);color:#94a3b8;font-size:11px;font-weight:600;
letter-spacing:.5px;padding:4px 24px;border-bottom:1px solid rgba(255,255,255,.1)}
.top-inner,.header-content,.pagebar-inner{display:flex;justify-content:space-between;
align-items:center;max-width:1200px;margin:0 auto;gap:12px;flex-wrap:wrap}
.pjn-header{background:var(--pjn-navy);color:#fff;padding:12px 24px;
border-bottom:3px solid var(--pjn-accent-gold);position:sticky;top:0;z-index:10}
.branding{display:flex;align-items:center;gap:12px}
.branding h1{font-size:16px;margin:0;font-weight:700;color:#fff;letter-spacing:.2px}
.branding p{font-size:12px;margin:2px 0 0;color:#cbd5e1}
.escudo{font-size:26px;color:var(--pjn-accent-gold);line-height:1}
.user-session{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:13px;color:#e2e8f0}
.user-session a{color:#fff;font-weight:600}
.user-name{font-weight:700;color:#fff}
.status-pill{display:inline-block;padding:3px 10px;border-radius:3px;font-size:11px;
font-weight:700;letter-spacing:.4px}
.de-turno{background:var(--pjn-badge-green);color:#fff}
.fuera-turno{background:var(--pjn-badge-red);color:#fff}
.pagebar{background:var(--pjn-surface);border-bottom:1px solid var(--pjn-border);padding:10px 24px}
.pagebar h2{margin:0;font-size:15px;font-weight:700;color:var(--pjn-navy);
text-transform:uppercase;letter-spacing:.3px}
.pagebar .nav{font-size:13px}
main{padding:20px 24px;max-width:1200px;margin:auto}
h2,h3{font-weight:700;color:var(--pjn-navy)}
h3{font-size:14px;text-transform:uppercase;letter-spacing:.3px;margin:22px 0 8px;
padding-bottom:4px;border-bottom:2px solid var(--pjn-sky)}
.card{background:var(--pjn-surface);border:1px solid var(--pjn-border);border-radius:4px;
padding:16px 18px;margin-bottom:16px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:11px;
font-weight:700;white-space:nowrap;text-transform:uppercase;letter-spacing:.3px;
border:1px solid transparent;background:#f3f4f6;color:#374151}
.b-detectado,.b-cerrado,.b-vencida,.b-desestimado{background:#f3f4f6;color:#4b5563;border-color:#d1d5db}
.b-elevado,.b-recibida,.b-recibido{background:#fef3c7;color:#92400e;border-color:#fcd34d}
.b-aprobado{background:var(--pjn-sky);color:var(--pjn-blue);border-color:#b6d4ea}
.b-en_ejecucion,.b-aplicada,.b-orden_levantada{background:#dcfce7;color:var(--pjn-badge-green);border-color:#86efac}
.b-archivado,.b-fallida{background:#fee2e2;color:var(--pjn-badge-red);border-color:#fca5a5}
.b-levantada{background:#ede9fe;color:#5b21b6;border-color:#c4b5fd}
.peritaje{background:var(--pjn-surface);border:1px solid var(--pjn-border);
border-left:4px solid var(--pjn-blue);padding:10px 14px;margin:10px 0;font-size:13px}
.info-bar{background:var(--pjn-sky);border:1px solid #b6d4ea;border-left:4px solid var(--pjn-navy);
padding:10px 14px;margin-bottom:16px;font-size:13px}
.muted{color:var(--pjn-text-muted);font-size:12px}
button{background:var(--pjn-blue);color:#fff;border:1px solid var(--pjn-blue);border-radius:3px;
padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s;
margin:2px 4px 2px 0;font-family:inherit}
button:hover{background:var(--pjn-navy);border-color:var(--pjn-navy)}
button:disabled{opacity:.6;cursor:wait}
button.peligro{background:var(--pjn-badge-red);border-color:var(--pjn-badge-red)}
button.peligro:hover{background:#991b1b}
button.sec{background:#fff;color:var(--pjn-navy);border-color:var(--pjn-border)}
button.sec:hover{background:var(--pjn-sky)}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--pjn-surface);
border:1px solid var(--pjn-border)}
td,th{padding:8px 10px;border-bottom:1px solid var(--pjn-border);text-align:left;vertical-align:top}
th{background:var(--pjn-sky);color:var(--pjn-navy);font-size:11px;font-weight:700;
text-transform:uppercase;letter-spacing:.4px;border-bottom:2px solid #b6d4ea}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:#f8fafc}
input{padding:9px 11px;border-radius:3px;border:1px solid var(--pjn-border);background:#fff;
color:var(--pjn-text);width:100%;max-width:420px;font-size:14px;font-family:inherit}
input:focus{outline:2px solid var(--pjn-blue);outline-offset:-1px;border-color:var(--pjn-blue)}
label{display:block;font-size:12px;font-weight:700;color:var(--pjn-navy);margin-bottom:4px;
text-transform:uppercase;letter-spacing:.3px}
.mono{font-family:ui-monospace,Consolas,"Courier New",monospace;font-size:12px}
.aviso{background:#fef2f2;border:1px solid #fca5a5;border-left:4px solid var(--pjn-badge-red);
color:#7f1d1d;padding:10px 14px;margin-bottom:12px}
.ok{background:#f0fdf4;border:1px solid #86efac;border-left:4px solid var(--pjn-badge-green);
color:#14532d;padding:12px 14px;margin-bottom:12px}
.caratula-pjn{background:var(--pjn-surface);border:1px solid var(--pjn-border);margin-bottom:16px}
.caratula-head{background:var(--pjn-navy);color:#fff;padding:8px 14px;display:flex;
justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;
border-bottom:2px solid var(--pjn-accent-gold)}
.nro-expte{font-family:ui-monospace,Consolas,monospace;font-weight:700;font-size:14px}
.tipo-medida{font-size:11px;font-weight:700;letter-spacing:.5px;color:#f5d98b}
.caratula-body .row{padding:8px 14px;border-bottom:1px solid #eef0f3;font-size:13px}
.caratula-body .row:last-child{border-bottom:0}
.caratula-body .row>b:first-child{color:var(--pjn-navy);display:inline-block;min-width:190px}
.alerta-tercero{border:1px solid #fca5a5;border-left:5px solid var(--pjn-badge-red);background:#fff}
.alerta-tercero .alerta-head{background:#fef2f2;color:var(--pjn-badge-red);padding:8px 14px;
font-weight:700;font-size:13px;letter-spacing:.3px;display:flex;justify-content:space-between;
flex-wrap:wrap;gap:8px}
.plazo{font-family:ui-monospace,Consolas,monospace;font-weight:700}
.plazo.vencido{color:var(--pjn-badge-red)}
.sicre-pasos{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:14px 0}
.sicre-pasos div{background:var(--pjn-surface);border:1px solid var(--pjn-border);
border-top:3px solid var(--pjn-accent-gold);padding:10px 12px;font-size:12px}
.sicre-pasos b{display:block;color:var(--pjn-navy);font-size:13px;margin-bottom:2px}
.comprobante{border:1px dashed var(--pjn-navy);background:#fff;padding:14px 16px;margin:12px 0}
.comprobante .cut{font-family:ui-monospace,Consolas,monospace;font-size:20px;font-weight:700;
color:var(--pjn-navy);letter-spacing:.5px}
footer{max-width:1200px;margin:10px auto 24px;padding:0 24px;color:var(--pjn-text-muted);font-size:11px}
@media(max-width:700px){.caratula-body .row>b:first-child{display:block;min-width:0}
.top-inner span+span{display:none}main{padding:14px}.pjn-header{position:static}
table{display:block;overflow-x:auto}}
"""

ESTADOS = {"detectado", "elevado", "aprobado", "en_ejecucion", "cerrado", "archivado"}

PLAZO_SICRE_MIN = 15


def _e(x) -> str:
    return html.escape(str(x))


_JUZGADOS = None


def _juzgado_de(juez_id) -> str:
    """Nombre del juzgado del juez (datos/juzgados.json), para la carátula."""
    global _JUZGADOS
    if _JUZGADOS is None:
        _JUZGADOS = {}
        try:
            from ..config import DATOS_DIR
            datos = json.loads((DATOS_DIR / "juzgados.json").read_text("utf-8"))
            for jz in datos.get("juzgados", []):
                for j in jz.get("jueces", []):
                    _JUZGADOS[j["id"]] = (jz.get("nombre", ""), j.get("nombre", ""))
        except Exception:
            pass
    return _JUZGADOS.get(juez_id, ("", ""))


def pagina(titulo: str, cuerpo: str, extra_head: str = "",
           refresh: bool = True) -> str:
    meta = "<meta http-equiv=refresh content=4>" if refresh else ""
    return (f"<!doctype html><html lang=es><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"{meta}"
            f"<title>{_e(titulo)} · DEOB</title><style>{CSS}</style>{extra_head}</head>"
            f"<body>{cuerpo}<footer>Poder Judicial de la Nación · DEOB — "
            f"Diligenciamiento Electrónico de Órdenes de Bloqueo · "
            f"Prototipo Hackathon Argentina Space 2026 · datos ficticios"
            f"</footer></body></html>")


def header(titulo: str, derecha: str = "", nav: str = "") -> str:
    """Franja institucional PJN + header azul + barra de título de página."""
    return (
        "<div class=top-banner><div class=top-inner>"
        "<span>PODER JUDICIAL DE LA NACIÓN ARGENTINA</span>"
        "<span class=ambiente>SISTEMA FEDERAL DE MEDIDAS CAUTELARES EN VIVO · "
        "LEX100 / DEOB</span></div></div>"
        "<header class=pjn-header><div class=header-content>"
        "<div class=branding><div class=escudo>⚖</div><div>"
        "<h1>DEOB — Diligenciamiento Electrónico de Órdenes de Bloqueo</h1>"
        "<p>Fuero Federal Penal · Ciberdelincuencia y Propiedad Intelectual</p>"
        f"</div></div><div class=user-session>{derecha}</div></div></header>"
        f"<div class=pagebar><div class=pagebar-inner><h2>{_e(titulo)}</h2>"
        f"<div class=nav>{nav}</div></div></div>")


def login(error: str = "") -> str:
    err = f"<div class=aviso>{_e(error)}</div>" if error else ""
    return pagina("Ingreso judicial", header(
        "Ingreso al sistema",
        nav="<a href='/transparencia'>Registro público</a> · "
            "<a href='/reclamar'>SICRE — Reclamo de terceros</a>") + f"""
<main><div class=card style="max-width:400px;margin:40px auto;border-top:3px solid var(--pjn-navy)">
<h2 style="margin-top:0;font-size:16px">Identificación del usuario judicial</h2>{err}
<form method=post action=/login>
<p><label for=u>Usuario</label><input id=u name=usuario autofocus></p>
<p><label for=p>Contraseña</label><input id=p name=password type=password></p>
<p><button type=submit style="width:100%;padding:10px">Ingresar</button></p>
</form><div class=info-bar style="margin:0"><span class=mono>Usuarios demo (clave: demo)<br>
jueces: laura · martin — firman solo de turno<br>
tramitación: secretario · operador — pases, revisión, informes<br>
admin — visión completa del sistema</span></div>
</div></main>""", refresh=False)


def _sesion_html(nombre: str, rol: str, pill: str, links: str) -> str:
    return (f"<span class=user-name>{_e(nombre)}</span>"
            f"<span style='color:#94a3b8'>({_e(rol)})</span>{pill}"
            f"<span>{links}</span>")


def _plazo_sicre(minuto_reclamo, minuto_actual) -> str:
    try:
        resta = float(minuto_reclamo) + PLAZO_SICRE_MIN - float(minuto_actual)
    except (TypeError, ValueError):
        return ""
    if resta <= 0:
        return "<span class='plazo vencido'>PLAZO VENCIDO</span>"
    return f"<span class=plazo>{resta:.1f} min</span>"


MSGS = {
    "fuera-turno": "No está de turno: solo el juez de turno puede firmar.",
    "ya-despachado": "Ese expediente ya fue despachado o archivado.",
    "rol": "Su rol no permite firmar medidas.",
}

_UNA_VEZ = ("onsubmit=\"var b=this.querySelector('button');"
            "if(b.disabled)return false;b.disabled=true;"
            "b.innerText='Procesando…'\"")


def _flash(msg: str) -> str:
    txt = MSGS.get(msg, msg)
    return f"<div class=aviso>{_e(txt)}</div>" if txt else ""


def bandeja(expedientes, juez: dict, turno_txt: str, minuto: float,
            reclamos_pend=(), puede_firmar: bool = False, msg: str = "") -> str:
    filas = ""
    for e in expedientes:
        est = e["estado"]
        dep = e["dependencia"] if "dependencia" in e.keys() else "pericia"
        dep = dep or "pericia"
        botones = ""
        if puede_firmar and est in ("detectado", "elevado") and dep == "juzgado":
            botones = (f"<form method=post action='/exp/{_e(e['id'])}/aprobar' {_UNA_VEZ} style='display:inline'>"
                       f"<button>Aprobar y mandar bloqueo urgente</button></form> "
                       f"<form method=post action='/exp/{_e(e['id'])}/forzar-ip' {_UNA_VEZ} style='display:inline'>"
                       f"<button class=sec>Aprobar forzando IP</button></form> "
                       f"<form method=post action='/exp/{_e(e['id'])}/rechazar' {_UNA_VEZ} style='display:inline'>"
                       f"<button class=peligro>Rechazar</button></form>")
        filas += (f"<tr><td><a href='/exp/{_e(e['id'])}' class=mono>{_e(e['id'])}</a> "
                  f"<span class=mono>fase {e['fase_n']}</span></td>"
                  f"<td class=mono>{_e(e['host_stream'])}<br>{_e(e['ip_servidor'])}</td>"
                  f"<td>{_e(e['tipo_bloqueo_recomendado'] or '')}</td>"
                  f"<td><span class='badge b-{est}'>{est}</span><br>"
                  f"<span class=muted>{_e(dep)}</span></td>"
                  f"<td class=mono>{e['creado_min']:.1f}</td><td>{botones}</td></tr>")
    if not filas:
        filas = "<tr><td colspan=6>Sin expedientes todavía.</td></tr>"
    rol_txt = juez.get("rol", "")
    if juez.get("rol") == "juez" and not puede_firmar:
        estado_firma = ("<span class='status-pill fuera-turno'>FUERA DE TURNO · "
                        "SOLO LECTURA</span>")
    elif puede_firmar:
        estado_firma = "<span class='status-pill de-turno'>DE TURNO · PUEDE FIRMAR</span>"
    else:
        estado_firma = ""
    pendientes = ""
    if reclamos_pend:
        def _btn_r(r):
            if not puede_firmar:
                return "<span class=muted>esperando juez de turno</span>"
            return (f"<form method=post action='/reclamo/{_e(r['id'])}"
                    f"/hacer-lugar' {_UNA_VEZ} style='display:inline'>"
                    f"<button>Hacer lugar: sustituir medida</button></form>")
        filas_r = "".join(
            f"<tr><td class=mono>{_e(r['id'])}</td>"
            f"<td class=mono>{_e(r['dominio'])}</td><td>{_e(r['proveedor'])}</td>"
            f"<td>{_e(r['mensaje'])}</td><td class=mono>{r['minuto']:.1f}</td>"
            f"<td>{_plazo_sicre(r['minuto'], minuto)}</td>"
            f"<td>{_btn_r(r)}</td></tr>" for r in reclamos_pend)
        pendientes = (f"<div class='card alerta-tercero' style='padding:0'>"
                      f"<div class=alerta-head><span>⚠ SICRE — TERCERO AFECTADO "
                      f"POR MEDIDA CAUTELAR ({len(reclamos_pend)})</span>"
                      f"<span>Plazo de resolución: {PLAZO_SICRE_MIN} min · "
                      f"Incidente de Tercería</span></div>"
                      f"<div style='padding:10px 14px'><p class=muted style='margin:0 0 8px'>"
                      f"Hacer lugar levanta la medida que afecta al tercero y la "
                      f"<b>sustituye</b> por un bloqueo quirúrgico por dominio: el "
                      f"stream infractor sigue bloqueado.</p>"
                      f"<table><tr><th>Reclamo</th><th>Dominio afectado</th>"
                      f"<th>Proveedor</th><th>Motivo</th><th>Min</th><th>Plazo restante</th><th></th>"
                      f"</tr>{filas_r}</table></div></div>")
    pend_n = (sum(1 for e in expedientes
                  if e["estado"] in ("detectado", "elevado")
                  and (e["dependencia"] or "pericia") == "juzgado")
              + len(reclamos_pend))
    banner = ""
    if pend_n and puede_firmar:
        banner = (f"<div class=aviso><b>⚠ {pend_n} actuación(es) esperando su "
                  f"firma.</b> Atajo de teclado: <span class=mono>A</span> "
                  f"aprueba la primera de la lista.</div>")
    n_exp = pend_n - len(reclamos_pend)
    if n_exp > 1 and puede_firmar:
        banner += (f"<form method=post action='/exp/aprobar-todo' {_UNA_VEZ} "
                   f"style='margin:8px 0'><button>Aprobar todo según "
                   f"peritaje ({n_exp} expedientes)</button></form>")
    script = f"""<script>
(function(){{
  var n={pend_n}, prev=+(sessionStorage.getItem('pend')||0);
  if(n>prev){{
    try{{var c=new (window.AudioContext||window.webkitAudioContext)();
    var o=c.createOscillator(),g=c.createGain();o.connect(g);g.connect(c.destination);
    o.frequency.value=880;g.gain.value=.08;o.start();setTimeout(function(){{o.stop()}},200);}}catch(e){{}}
  }}
  document.title=(n?'('+n+') PENDIENTE — ':'')+'Consola Judicial';
  sessionStorage.setItem('pend',n);
  document.addEventListener('keydown',function(e){{
    if(e.key!=='a'&&e.key!=='A')return;
    if(/INPUT|TEXTAREA/.test(e.target.tagName))return;
    var b=document.querySelector("form[action$='/aprobar'] button")||
         document.querySelector("form[action$='/hacer-lugar'] button");
    if(b)b.click();
  }});
}})();
</script>"""
    return pagina("Bandeja del juez", header(
        "Bandeja de expedientes — Medidas cautelares urgentes",
        _sesion_html(juez['nombre'], rol_txt, estado_firma,
                     "<a href='/salir'>Salir</a>"),
        "<a href='/monitor'>Monitor en vivo</a> · "
        "<a href='/transparencia'>Registro público</a> · "
        "<a href='/reclamar'>SICRE</a>") + f"""
<main>{_flash(msg)}{banner}
<div class=info-bar>Minuto de partido <b>{minuto:.1f}</b> · { _e(turno_txt) }
<br><span class=muted>Supervisión continua: la plataforma
detecta y eleva sola — lo que aparece aquí con botones es lo único que espera su
firma. El atajo <b>A</b> aprueba lo primero de la lista.</span></div>
{pendientes}
<table><tr><th>Expediente</th><th>Stream</th><th>Medida sugerida</th>
<th>Estado / dependencia</th><th>Min</th><th></th></tr>{filas}</table>
{script}
</main>""")


def _acciones(exp: dict, sesion: dict, puede_firmar: bool = False) -> str:
    """Barra de movimientos según rol y dependencia del expediente."""
    dep = exp.get("dependencia") or "pericia"
    rol = sesion.get("rol")
    eid = _e(exp["id"])

    def btn(accion, txt, cls=""):
        return (f"<form method=post action='/exp/{eid}/{accion}' {_UNA_VEZ} "
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
            out.append("<span class=muted>medida en ejecución</span>")
    if rol == "juez":
        if dep == "juzgado" and exp["estado"] in ("detectado", "elevado"):
            if puede_firmar:
                out.append(btn("aprobar", "Aprobar y librar cautelar"))
                out.append(btn("forzar-ip", "Aprobar forzando IP", "sec"))
                out.append(btn("rechazar", "Rechazar", "peligro"))
            else:
                out.append("<span class='badge b-fallida'>FUERA DE TURNO — "
                           "no puede firmar</span>")
        out.append(btn("pase-secretaria", "Devolver a Secretaría", "sec"))
    if rol in ("operador", "secretario", "juez", "admin"):
        out.append(btn("revision", "Iniciar revisión (re-peritaje)", "sec"))
    if rol in ("secretario", "juez", "admin") and dep == "despacho":
        out.append(btn("archivar", "Archivar definitivamente", "peligro"))
    out.append(f"<a href='/exp/{eid}/informe'><button type=button class=sec>"
               f"Emitir informe</button></a>")
    return " ".join(out)


def detalle(exp, evidencias, actuaciones, ordenes, reclamos_rows=(),
            sesion=None, puede_firmar: bool = False, msg: str = "",
            integro=None) -> str:
    def _promo(ev):
        canales = json.loads(ev["promocion"] or "[]")
        if not canales:
            return ""
        txt = ", ".join(
            f"{_e(c.get('red'))}: <a href='{_e(c.get('url'))}' "
            f"class=mono>{_e(c.get('url'))}</a> (min {_e(c.get('minuto'))})"
            for c in canales)
        return f"<br>Difundido en: {txt}"

    def _cap(ev):
        try:
            m = json.loads(ev["captura_meta"] or "{}")
        except Exception:
            m = {}
        if not m:
            return ""
        return (f"<br>Captura: {_e(m.get('formato') or '?')} · "
                f"{_e(m.get('duracion_seg') or '?')} s · página "
                f"<span class=mono>{_e(m.get('pagina') or '?')}</span>")

    def _porque():
        host = exp.get("host_stream") or ""
        tipo = exp.get("tipo_bloqueo_recomendado") or "dominio"
        doms = []
        riesgo = False
        for x in evidencias:
            try:
                d = json.loads(x["dominios_en_ip"] or "[]")
            except Exception:
                d = []
            if len(d) > len(doms):
                doms = d
            riesgo = riesgo or bool(x["riesgo_colateral_detectado"])
        from ..motor.verificador import dominio_base
        ajenos = [d for d in doms if dominio_base(d) != dominio_base(host)]
        if riesgo:
            base = (f"La IP aloja {len(doms)} dominio(s) y {len(ajenos)} son "
                    f"ajenos al operador del stream → hosting compartido: un "
                    f"bloqueo por IP causaría daño colateral. El peritaje "
                    f"recomendó bloqueo por <b>dominio</b>, quirúrgico.")
            if tipo == "ip":
                base += (" El juez resolvió <b>forzar bloqueo por IP</b> "
                         "asumiendo el daño colateral — los sitios afectados "
                         "pueden reclamar y el juzgado resuelve con "
                         "levantamiento + reemplazo por dominio.")
            return base
        if doms:
            return (f"La IP solo aloja {len(doms)} dominio(s) del mismo "
                    f"operador → IP dedicada al stream: bloqueo por <b>IP</b>, "
                    f"máxima efectividad sin daño colateral.")
        return ("Sin registros de DNS pasivo para la IP → se ordena por "
                "<b>dominio</b> (nunca produce daño colateral).")

    ev = "".join(
        f"<div class=peritaje>Detección <b>{_e(x['deteccion_id'])}</b> min {x['minuto']} · "
        f"marca <span class=mono>{_e(x['marca_extraida'])}</span> · "
        f"SHA-256 captura <span class=mono>{_e(x['captura_sha256'][:20])}…</span>"
        f"{_cap(x)}{_promo(x)}<br>"
        f"DNS pasivo: {_e(x['dominios_en_ip'])}</div>" for x in evidencias)
    sello = ""
    if integro is not None:
        sello = (f" <span class='badge b-aplicada'>✓ cadena íntegra</span>"
                 if integro else
                 f" <span class='badge b-fallida'>✗ CADENA ALTERADA</span>")
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
    asignado = exp.get("juez_asignado") or "—"
    aprobada = (f"{_e(exp['aprobada_por'])} (min {_e(exp['aprobada_min'])})"
                if exp.get("aprobada_por") else "—")
    jz_nombre, juez_nombre = _juzgado_de(exp.get("juez_asignado"))
    juzgado = (f"{_e(jz_nombre)} · {_e(juez_nombre)}" if jz_nombre
               else f"<span class=mono>{_e(asignado)}</span>")
    return pagina(f"Expediente {exp['id']}", header(
        f"Expediente {exp['id']} — Incidente de medida cautelar",
        nav="<a href='/'>← Volver a la bandeja</a>") + f"""
<main>{_flash(msg)}
<div class=caratula-pjn>
<div class=caratula-head><span class=nro-expte>{_e(exp['id'])}</span>
<span class=tipo-medida>INCIDENTE DE MEDIDA CAUTELAR URGENTE · FASE {_e(exp['fase_n'])}</span></div>
<div class=caratula-body>
<div class=row><b>Autos:</b> «{_e(exp['stream_id'])}» s/ INFRACCIÓN LEY 11.723 (TRANSMISIÓN NO AUTORIZADA)</div>
<div class=row><b>Juzgado:</b> {juzgado}</div>
<div class=row><b>Objetivo identificado:</b> <span class=mono>{_e(exp['host_stream'])}</span> (IP: <span class=mono>{_e(exp['ip_servidor'])}</span> · ASN {_e(exp['asn'])})</div>
<div class=row><b>Dictamen pericial automatizado:</b> {_porque()}</div>
<div class=row><b>Medida sugerida:</b> {_e(exp['tipo_bloqueo_recomendado'])} ·
<b style="min-width:0">Estado:</b> <span class='badge b-{_e(exp['estado'])}'>{_e(exp['estado'])}</span> ·
<b style="min-width:0">Dependencia:</b> <span class='badge b-detectado'>{_e(dep)}</span>{sello}</div>
<div class=row><b>Aprobada por:</b> <span class=mono>{aprobada}</span></div>
</div></div>
<div class=card>{_acciones(exp, sesion or {}, puede_firmar)}</div>
<h3>Peritaje técnico — evidencia</h3>{ev}
<h3>Órdenes libradas a proveedores</h3>
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
        "Registro público de transparencia — Medidas cautelares",
        "<a href='/'>Consola judicial</a>",
        "<a href='/monitor'>Monitor en vivo</a> · "
        "<a href='/reclamar'>SICRE — ¿Su sitio fue afectado?</a>") + f"""
<main><div class=info-bar>Minuto de partido <b>{minuto:.1f}</b>. Las órdenes por IP vencen
automáticamente al finalizar el partido. Si su sitio legítimo quedó afectado,
inicie un reclamo gratuito en <a href='/reclamar'>SICRE</a>.</div>
<table><tr><th>Orden</th><th>Proveedor</th><th>Objetivo</th><th>Estado</th>
<th>Juez</th><th>Vence</th></tr>{filas}</table></main>""")


def reclamos(reclamos_rows) -> str:
    filas = "".join(
        f"<tr><td class=mono>{_e(r['id'])}</td><td class=mono>{_e(r['dominio'])}</td>"
        f"<td>{_e(r['proveedor'])}</td><td>{_e(r['mensaje'])}</td>"
        f"<td><span class='badge b-{_e(r['estado'])}'>{_e(r['estado'])}</span></td></tr>"
        for r in reclamos_rows)
    return (f"<div class=card><h3 style='margin-top:0'>Reclamos de terceros (SICRE)</h3>"
            f"<table><tr><th>ID</th><th>Dominio</th><th>Proveedor</th><th>Mensaje</th>"
            f"<th>Estado</th></tr>{filas or '<tr><td colspan=5>Sin reclamos.</td></tr>'}"
            f"</table></div>")


def dumps_pretty(obj) -> str:
    return html.escape(json.dumps(obj, ensure_ascii=False, indent=2))


CSS_INFORME = """
body{font-family:Georgia,'Times New Roman',serif;color:#111;background:#fff;
margin:0;padding:32px;max-width:820px;margin:auto;font-size:13px;line-height:1.5}
h1{font-size:17px;text-align:center;margin:0;color:#002b49}
.caratula{border-bottom:3px double #c59b27;padding-bottom:10px}
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


def informe(exp, evidencias, actuaciones, ordenes, reclamos_rows,
            integro=None) -> str:
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
            f"<p style='letter-spacing:1px;font-weight:bold'>PODER JUDICIAL DE LA NACIÓN</p>"
            f"<p>Fuero Federal Penal · Ciberdelincuencia y Propiedad Intelectual</p>"
            f"<h1 style='margin-top:10px'>INFORME DE EXPEDIENTE ELECTRÓNICO</h1>"
            f"<p><b>{_e(exp['id'])}</b> — «{_e(exp['stream_id'])}» s/ MEDIDA "
            f"CAUTELAR URGENTE (fase {exp['fase_n']})</p>"
            f"<p>DEOB — Diligenciamiento Electrónico de Órdenes de Bloqueo · "
            f"dependencia actual: {_e(dep)} · estado: {_e(exp['estado'])}</p>"
            + (f"<p><b>Integridad de la cadena de custodia:</b> "
               f"{'✓ VERIFICADA' if integro else '✗ ALTERADA'}</p>"
               if integro is not None else "")
            + "</div>"
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
            f"sha256(hash_prev|expediente_id|n|tipo|detalle|minuto|"
            f"timestamp_iso) con la anterior; evidencias y órdenes llevan "
            f"huella SHA-256 citada en la cadena. "
            f"Recomputar: python -m plataforma.auditoria.verificar_cadena.</p>"
            f"</body></html>")


def reclamar(exito=None, error="", dominio: str = "", mensaje: str = "",
             minuto=None) -> str:
    """SICRE — Sistema Integral de Consulta y Reclamo Electrónico (público)."""
    aviso = ""
    if exito is not None:
        minuto_txt = f"{float(minuto):.3f}" if minuto is not None else ""
        huella = hashlib.sha256(
            f"{dominio}|{mensaje}|{minuto_txt}".encode("utf-8")).hexdigest()
        cut = f"REC-2026-{huella[:6].upper()}"
        if exito:
            estado = (f"<div class=ok style='margin:0 0 10px'><b>Reclamo admitido.</b> "
                      f"Se localizaron <b>{exito}</b> medida(s) cautelar(es) que "
                      f"afectan a <span class=mono>{_e(dominio)}</span>. Su reclamo "
                      f"fue incorporado al expediente como <b>Incidente de "
                      f"Tercería</b> y elevado al juez de turno, que debe resolver "
                      f"en un plazo máximo de {PLAZO_SICRE_MIN} minutos.</div>")
        else:
            estado = ("<div class=info-bar style='margin:0 0 10px'><b>Reclamo "
                      "registrado y desestimado:</b> ninguna medida cautelar "
                      "vigente afecta ese dominio. Si el problema persiste, "
                      "consulte con su proveedor de internet.</div>")
        aviso = (f"<div class=comprobante>{estado}"
                 f"<div class=muted>CÓDIGO ÚNICO DE TRÁMITE (CUT)</div>"
                 f"<div class=cut>{cut}</div>"
                 f"<div class=muted style='margin-top:8px'>Huella SHA-256 del reclamo "
                 f"(dominio|motivo|minuto {_e(minuto_txt)})</div>"
                 f"<div class=mono style='word-break:break-all'>{huella}</div>"
                 f"<p class=muted style='margin:10px 0 0'>Siga el estado de la orden "
                 f"en tiempo real en el <a href='/transparencia'>registro público</a> "
                 f"o el <a href='/monitor'>monitor</a>. Conserve este comprobante.</p>"
                 f"</div>")
    err = f"<div class=aviso>{_e(error)}</div>" if error else ""
    return pagina("SICRE — Reclamo de tercero afectado", header(
        "SICRE — Sistema Integral de Consulta y Reclamo Electrónico",
        "<a href='/'>Consola judicial</a>",
        "<a href='/transparencia'>Registro público</a> · "
        "<a href='/monitor'>Monitor en vivo</a>") + f"""
<main style="max-width:860px">
<div class=info-bar><b>Vía de Tutela Sumaria para Terceros Afectados</b> · Ley 19.549
(informalismo y gratuidad) · debido proceso constitucional.<br>
<span class=muted>Sin abogado · sin tasa de justicia · resolución en {PLAZO_SICRE_MIN} minutos.</span></div>
<div class=sicre-pasos>
<div><b>1. Ingreso simple</b>Indique el dominio de su sitio y el motivo en un renglón.</div>
<div><b>2. Trazador de afectación</b>Se cruza el dominio con las medidas vigentes en los 4 proveedores.</div>
<div><b>3. Alerta al juez</b>El juzgado de turno recibe una alerta de tercero afectado.</div>
<div><b>4. Sustitución de medida</b>Se levanta el bloqueo por IP y se sustituye por uno por dominio: el infractor sigue bloqueado.</div>
</div>
{err}{aviso}
<div class=card style="border-top:3px solid var(--pjn-navy)">
<h2 style="margin-top:0;font-size:16px">Iniciar reclamo</h2>
<form method=post action=/reclamar>
<p><label for=d>Dominio afectado</label><input id=d name=dominio placeholder="midominio.test" required></p>
<p><label for=m>Motivo</label><input id=m name=mensaje placeholder="Ej.: mi tienda no carga desde hace 10 minutos"></p>
<p><button type=submit>Presentar reclamo</button></p>
</form></div></main>""", refresh=False)
