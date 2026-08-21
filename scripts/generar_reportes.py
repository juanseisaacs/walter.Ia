"""Genera el reporte semanal al papá para todos los niños que lo necesiten.

`generar_reporte()` sabía redactar desde la fase 3, pero nadie lo llamaba: el
panel tenía la sección "El resumen de la semana" y nunca aparecía. Esta es la
tarea que faltaba.

    python -m scripts.generar_reportes          # genera lo que corresponda
    python -m scripts.generar_reportes --seco   # solo dice qué haría

Pensado para correr una vez por día (cron / Programador de tareas). Es
idempotente: un niño con reporte vigente se saltea, así que correrlo de más no
le manda dos resúmenes al papá. Necesita ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from tutor import config as cfg
from tutor.curriculum import cargar_grafo
from tutor.pipeline import (
    cliente_por_defecto,
    generar_reportes_pendientes,
    reporte_vigente,
)
from tutor.notificaciones import aviso_de_reporte, notificador_por_defecto
from tutor.storage import RepositorioSQLite

VIDA_ENLACE_REPORTE = timedelta(days=7)
"""El enlace del correo dura lo que el período que resume.

Los de la API duran 24 horas porque el papá los pide y los usa enseguida. Este
llega solo, un domingo, y se abre cuando el papá tiene un rato — que puede ser
el miércoles."""


def _avisar(repo: RepositorioSQLite, generados: list) -> int:
    """Manda el correo con el enlace al panel. Devuelve cuántos salieron.

    Sin esto el reporte se generaba, se verificaba, se guardaba... y se quedaba
    esperando a que el papá entrara al panel por su cuenta. Un reporte que hay
    que ir a buscar no construye confianza, que es justo para lo que existe.

    Recién se pudo conectar cuando los enlaces se movieron a la base: este es
    otro proceso, y con el dict en memoria de la API no había forma de emitir
    uno que funcionara.
    """
    notificador = notificador_por_defecto()
    enviados = 0

    for reporte in generados:
        nino = repo.obtener_nino(reporte.nino_id)
        if nino is None or not nino.email_papa:
            # No se inventa un destinatario. Sin correo el reporte igual quedó
            # guardado y el panel lo muestra.
            print(f"    · {reporte.nino_id}: sin email del papá, no se envía")
            continue

        token = secrets.token_urlsafe(32)
        repo.crear_enlace(token, nino.id, datetime.now() + VIDA_ENLACE_REPORTE)
        enlace = f"{cfg.URL_PANEL}/panel/{nino.id}?token={token}"

        # Dos líneas, no el reporte entero: lo que el niño dijo se lee en el
        # panel, con contexto. Un fragmento suelto en un correo desinforma.
        adelanto = reporte.contenido.strip().splitlines()[0][:200]

        try:
            notificador.enviar(aviso_de_reporte(nino.email_papa, nino.nombre, adelanto, enlace))
            enviados += 1
        except Exception as e:
            # Que falle un correo no puede tumbar los demás: cada papá que sí
            # tiene reporte tiene que recibirlo.
            print(f"    · {nino.nombre}: no se pudo enviar — {e}")

    return enviados


def main() -> int:
    p = argparse.ArgumentParser(description="Genera los reportes semanales al papá.")
    p.add_argument("--seco", action="store_true", help="Solo listar, sin generar")
    p.add_argument("--dias", type=int, default=cfg.DIAS_PERIODO_REPORTE)
    p.add_argument(
        "--sin-avisar",
        action="store_true",
        help="Genera y guarda el reporte, pero no le avisa al papá",
    )
    args = p.parse_args()

    repo = RepositorioSQLite(cfg.DB, cfg.DATOS)
    grafo = cargar_grafo()
    ahora = datetime.now()

    print("=" * 72)
    print(f"  REPORTES AL PAPÁ — período de {args.dias} días")
    print("=" * 72)

    pendientes = []
    for nino_id in repo.ids_de_ninos():
        nino = repo.obtener_nino(nino_id)
        if reporte_vigente(repo, nino_id, ahora, args.dias):
            print(f"  {nino.nombre} ({nino_id}): ya tiene reporte vigente")
        elif not repo.sesiones_de(nino_id, ahora - timedelta(days=args.dias), ahora):
            print(f"  {nino.nombre} ({nino_id}): sin sesiones en el período")
        else:
            print(f"  {nino.nombre} ({nino_id}): PENDIENTE")
            pendientes.append(nino_id)

    if not pendientes:
        print("\n  Nada que generar.\n")
        return 0

    if args.seco:
        print("\n  (modo seco: no se tocó nada)\n")
        return 0

    cliente = cliente_por_defecto()
    if type(cliente).__name__ == "ClienteFalso":
        print("\n  Falta ANTHROPIC_API_KEY en .env — no se puede redactar.\n")
        return 1

    generados, fallidos = generar_reportes_pendientes(repo, grafo, cliente, ahora, args.dias)

    print(f"\n  Generados: {len(generados)}")
    for r in generados:
        print(f"    · {r.nino_id} · {r.metricas.sesiones} sesión(es) · {len(r.contenido)} car.")

    # `_avisar` estaba escrita entera desde que los enlaces se movieron a la
    # base — y `main` no la llamaba. El reporte se generaba, se verificaba, se
    # guardaba, y esperaba a que el papá entrara al panel por su cuenta. Un
    # reporte que hay que ir a buscar no construye confianza, que es para lo
    # único que existe.
    if generados and not args.sin_avisar:
        enviados = _avisar(repo, generados)
        print(f"\n  Avisados: {enviados} de {len(generados)}")
    elif generados:
        print("\n  (--sin-avisar: los reportes quedaron guardados, nadie recibió correo)")

    if fallidos:
        # No es un detalle: cada uno es un papá que esta semana no recibe nada.
        # Puede ser un número inventado (y entonces el reporte NO se guardó) o el
        # modelo devolviendo basura. Las dos cosas hay que verlas.
        print(f"\n  ⚠ Sin reporte: {len(fallidos)}")
        for f in fallidos:
            print(f"    · {f.nino_id}: {f.motivo}")
        return 1

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
