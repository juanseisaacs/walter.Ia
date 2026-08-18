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
from tutor.storage import RepositorioSQLite


def main() -> int:
    p = argparse.ArgumentParser(description="Genera los reportes semanales al papá.")
    p.add_argument("--seco", action="store_true", help="Solo listar, sin generar")
    p.add_argument("--dias", type=int, default=cfg.DIAS_PERIODO_REPORTE)
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

    generados, rechazados = generar_reportes_pendientes(repo, grafo, cliente, ahora, args.dias)

    print(f"\n  Generados: {len(generados)}")
    for r in generados:
        print(f"    · {r.nino_id} · {r.metricas.sesiones} sesión(es) · {len(r.contenido)} car.")

    if rechazados:
        # No es un detalle: significa que el modelo escribió un número que no
        # está en los datos. El reporte NO se guardó.
        print(f"\n  ⚠ Rechazados por la verificación: {len(rechazados)}")
        for e in rechazados:
            print(f"    · {e.nino_id}: {'; '.join(e.problemas)}")
        return 1

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
