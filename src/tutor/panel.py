"""Panel del papá — HTML renderizado en el servidor.

Por qué server-rendered y no un SPA ni un agente que genera la página:
el panel es la superficie de VERIFICACIÓN (criterio #4 de YC). Tiene que ser
estable, repetible y con números que salen del código contra la fuente — no una
página distinta cada visita. El backend ya vive 24/7, así que esto es casi gratis.

Módulo PURO: entra data ya resuelta, sale un string de HTML. No toca red ni DB.
El que junta los datos es `api.py`; acá solo se dibujan.
"""

from __future__ import annotations

from datetime import datetime
from html import escape


def render_error(mensaje: str) -> str:
    """Página de error legible para el papá — no un JSON 401 en la cara."""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Acceso al panel</title>
<style>
  body {{ margin:0; min-height:100vh; display:grid; place-items:center;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    background:#f7f7f5; color:#1a1a1a; }}
  @media (prefers-color-scheme: dark) {{ body {{ background:#16161a; color:#f0f0f2; }} }}
  .caja {{ max-width:380px; text-align:center; padding:32px; }}
  p {{ color:#6b6b6b; }}
</style></head>
<body><div class="caja">
  <h1>Un momento</h1>
  <p>{escape(mensaje)}</p>
</div></body></html>"""


def _lista(items: list[str], vacio: str) -> str:
    if not items:
        return f'<p class="vacio">{escape(vacio)}</p>'
    return '<ul class="skills">' + "".join(f"<li>{escape(x)}</li>" for x in items) + "</ul>"


def _chips(items: list[str]) -> str:
    return "".join(f'<span class="chip">{escape(x)}</span>' for x in items)


def render_panel(
    *,
    nombre: str,
    grado_escolar: int,
    grado_de_trabajo: int,
    adelanto_grados: int,
    ya_domina: list[str],
    esta_trabajando: list[str],
    intereses: list[str],
    contexto_escolar: str | None = None,
    sesiones_total: int = 0,
    sesiones_auditadas: int,
    metodo_sostenido: float | None,
    dias: int,
    reporte_narrativo: str | None = None,
    sugerencia_para_casa: str | None = None,
    generado_en: datetime | None = None,
) -> str:
    """Arma el panel completo. `metodo_sostenido` es None si todavía no hay
    sesiones auditadas con veredicto (no se inventa un 100%)."""
    generado_en = generado_en or datetime.now()

    # El dato estrella: va adelantado. Es de lo más potente que lee un papá.
    if adelanto_grados >= 1:
        badge = (
            f'<span class="badge adelanto">Va {adelanto_grados} '
            f'{"grado" if adelanto_grados == 1 else "grados"} adelantado</span>'
        )
    elif adelanto_grados <= -1:
        badge = '<span class="badge apoyo">Reforzando bases</span>'
    else:
        badge = '<span class="badge">En su grado</span>'

    # La respuesta a "¿cómo sé que no le da las respuestas?".
    if metodo_sostenido is None:
        metodo_html = (
            '<p class="metodo-num">—</p>'
            '<p class="metodo-txt">Todavía no hay sesiones auditadas en este período.</p>'
        )
    else:
        metodo_html = (
            f'<p class="metodo-num">{round(metodo_sostenido * 100)}%</p>'
            '<p class="metodo-txt">de las sesiones el tutor guió con preguntas '
            "sin darle la respuesta. Lo revisa un auditor independiente, sesión a sesión.</p>"
        )

    narrativo = ""
    if reporte_narrativo:
        parrafos = "".join(
            f"<p>{escape(p.strip())}</p>" for p in reporte_narrativo.split("\n") if p.strip()
        )
        # La sugerencia va en su propio bloque: es lo único de la página que le
        # pide algo al papá, y mezclada en la prosa se pierde.
        sugerencia = (
            '<div class="para-casa"><strong>Para esta semana:</strong> '
            f"{escape(sugerencia_para_casa)}</div>"
            if sugerencia_para_casa
            else ""
        )
        narrativo = f"""
        <section class="card narrativo">
          <h2>El resumen de la semana</h2>
          {parrafos}
          {sugerencia}
        </section>"""

    intereses_html = ""
    if intereses:
        intereses_html = f"""
        <section class="card">
          <h2>Lo que su tutor ya sabe de {escape(nombre)}</h2>
          <p class="sub">El tutor lo conoce y usa esto para engancharlo. Crece sesión a sesión.</p>
          <div class="chips">{_chips(intereses)}</div>
        </section>"""

    # El 20% del colegio. Se muestra aparte de los intereses porque responde otra
    # pregunta del papá: no "¿lo conoce?" sino "¿está alineado con la clase?".
    # Solo aparece cuando hay algo — un recuadro vacío promete lo que no hay.
    colegio_html = ""
    if contexto_escolar:
        colegio_html = f"""
        <section class="card">
          <h2>Lo que sabe del colegio de {escape(nombre)}</h2>
          <p class="sub">Sale de lo que {escape(nombre)} le ha contado en las sesiones.
          Le sirve al tutor para acompañar lo que está viendo en clase.</p>
          <p>{escape(contexto_escolar)}</p>
        </section>"""

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cómo va {escape(nombre)}</title>
<style>
  :root {{
    --bg: #f7f7f5; --card: #ffffff; --tinta: #1a1a1a; --tenue: #6b6b6b;
    --linea: #e8e8e4; --verde: #2f8f5b; --acento: #3b5bdb; --dorado: #b8860b;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #16161a; --card: #1f1f26; --tinta: #f0f0f2; --tenue: #a0a0a8;
      --linea: #2d2d36; --verde: #48d68a; --acento: #7c93f0; --dorado: #e0b84a;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--tinta);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.55; -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 640px; margin: 0 auto; padding: 32px 20px 64px; }}
  header h1 {{ font-size: 1.7rem; margin: 0 0 4px; }}
  header .fecha {{ color: var(--tenue); font-size: 0.9rem; margin: 0 0 24px; }}
  .card {{
    background: var(--card); border: 1px solid var(--linea); border-radius: 16px;
    padding: 22px; margin-bottom: 16px;
  }}
  h2 {{ font-size: 1.05rem; margin: 0 0 14px; }}
  .sub {{ color: var(--tenue); font-size: 0.9rem; margin: -8px 0 14px; }}
  .grado-row {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
  .grado-num {{ font-size: 2.4rem; font-weight: 700; line-height: 1; }}
  .grado-lbl {{ color: var(--tenue); font-size: 0.9rem; }}
  .badge {{
    display: inline-block; padding: 6px 12px; border-radius: 999px;
    font-size: 0.85rem; font-weight: 600; background: var(--linea); color: var(--tinta);
  }}
  .badge.adelanto {{ background: color-mix(in srgb, var(--dorado) 20%, transparent); color: var(--dorado); }}
  .badge.apoyo {{ background: color-mix(in srgb, var(--acento) 18%, transparent); color: var(--acento); }}
  .metodo {{ text-align: center; }}
  .metodo-num {{ font-size: 2.6rem; font-weight: 700; margin: 4px 0 2px; color: var(--verde); }}
  .metodo-txt {{ color: var(--tenue); font-size: 0.92rem; margin: 0 auto; max-width: 46ch; }}
  ul.skills {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }}
  ul.skills li {{ padding-left: 26px; position: relative; }}
  ul.skills li::before {{
    content: "✓"; position: absolute; left: 0; color: var(--verde); font-weight: 700;
  }}
  .trabajando ul.skills li::before {{ content: "•"; color: var(--acento); }}
  .vacio {{ color: var(--tenue); font-style: italic; margin: 0; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .chip {{
    background: var(--linea); padding: 6px 12px; border-radius: 999px; font-size: 0.88rem;
  }}
  .narrativo p {{ margin: 0 0 10px; }}
  .para-casa {{
    margin-top: 14px; padding: 14px 16px; border-radius: 12px;
    background: color-mix(in srgb, var(--verde) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--verde) 30%, transparent);
  }}
  .cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 480px) {{ .cols {{ grid-template-columns: 1fr; }} }}
  footer {{ color: var(--tenue); font-size: 0.82rem; text-align: center; margin-top: 24px; }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Cómo va {escape(nombre)}</h1>
      <p class="fecha">Actualizado el {generado_en:%d/%m/%Y}</p>
    </header>

    <section class="card">
      <div class="grado-row">
        <div>
          <div class="grado-num">{grado_de_trabajo}°</div>
          <div class="grado-lbl">nivel al que trabaja hoy</div>
        </div>
        <div style="margin-left:auto">{badge}</div>
      </div>
      <p class="sub" style="margin-top:14px;margin-bottom:0">
        Cursa {grado_escolar}° grado. Acá no hay techo: si puede más, se le ofrece más.
      </p>
    </section>

    <section class="card metodo">
      <h2>¿Le está dando las respuestas?</h2>
      {metodo_html}
    </section>
    {narrativo}

    <div class="cols">
      <section class="card">
        <h2>Ya lo domina</h2>
        {_lista(ya_domina, "Todavía nada firme — apenas arranca.")}
      </section>
      <section class="card trabajando">
        <h2>Está practicando</h2>
        {_lista(esta_trabajando, "Nada en curso ahora mismo.")}
      </section>
    </div>
    {intereses_html}
    {colegio_html}

    <section class="card">
      <h2>Actividad</h2>
      <p style="margin:0">
        <strong>{sesiones_total}</strong> {"sesión" if sesiones_total == 1 else "sesiones"}
        en los últimos {dias} días · <strong>{sesiones_auditadas}</strong> auditadas por el método.
      </p>
    </section>

    <footer>
      Estos números salen de lo que {escape(nombre)} hizo, verificados en código.
      Ningún dato acá es una impresión ni lo inventa un modelo.
    </footer>
  </div>
</body>
</html>"""
