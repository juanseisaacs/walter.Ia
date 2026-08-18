"""Drena la cola del Analista: analiza las sesiones cerradas que quedaron sin procesar.

El cierre de sesión ya dispara el Analista en segundo plano (api.cerrar_sesion),
pero este script recoge lo que quedó atrás: sesiones cerradas antes de que el
eslabón existiera, o cerradas sin ANTHROPIC_API_KEY en el entorno.

    python -m scripts.procesar_pendientes          # drena todo
    python -m scripts.procesar_pendientes --seco   # solo lista, no toca nada

Es idempotente: una sesión ya analizada nunca se vuelve a contar (evita el doble
conteo de dominio). Necesita ANTHROPIC_API_KEY: sin el Analista no hay nada que
aplicar.
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from tutor import config as cfg
from tutor.curriculum import cargar_grafo
from tutor.pipeline import cliente_por_defecto, procesar_pendientes
from tutor.storage import RepositorioSQLite


def main() -> int:
    p = argparse.ArgumentParser(description="Analiza las sesiones pendientes.")
    p.add_argument("--seco", action="store_true", help="Solo listar, sin analizar")
    args = p.parse_args()

    repo = RepositorioSQLite(cfg.DB, cfg.DATOS)
    pendientes = repo.sesiones_sin_analizar()

    print("=" * 72)
    print(f"  COLA DEL ANALISTA — {len(pendientes)} sesión(es) sin procesar")
    print("=" * 72)
    for s in pendientes:
        print(f"  {s.id}  niño={s.nino_id}  cerró={s.fin}  {s.habilidades_trabajadas}")

    if not pendientes:
        print("\n  Nada que hacer: la cola está vacía.\n")
        return 0

    if args.seco:
        print("\n  (modo seco: no se tocó nada)\n")
        return 0

    cliente = cliente_por_defecto()
    if type(cliente).__name__ == "ClienteFalso":
        print("\n  Falta ANTHROPIC_API_KEY en .env — el Analista no puede correr.\n")
        return 1

    procesadas = procesar_pendientes(repo, cargar_grafo(), cliente)
    print(f"\n  Procesadas: {procesadas}. La tabla `dominio` ya refleja lo trabajado.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
