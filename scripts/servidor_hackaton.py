"""Levanta el backend sin tope de sesiones, para el jurado del hackathon.

    python -m scripts.servidor_hackaton

Es `servidor_pruebas` con los topes mucho más arriba. Existe aparte porque los
dos tienen públicos distintos: el de pruebas protege el bolsillo mientras
nosotros probamos, este acepta que un jurado entre veinte veces en una tarde y
no se lo quiere explicar a nadie a mitad de una demo.

Las variables se ponen ANTES de importar `tutor.config`, que las lee una vez al
importarse. Pasarlas por el shell NO funciona en Windows: `MAX_SESIONES_DIA=100
python -m uvicorn ...` en Git Bash no propaga el valor a un .exe.

NUNCA en producción. El techo diario es lo que evita que un bucle del cliente
gaste el mes entero en una tarde. Acá se quita a propósito y por unos días.

Lo que este script NO suelta, y conviene saber antes de la demo:
  · MAX_MINUTOS_SESION = 45         — una sesión sola no pasa de 45 minutos
  · MAX_COSTO_MES_USD_POR_NINO = 8  — cada ficha tiene su propio techo mensual
Los dos son constantes del código, no del entorno. Con una ficha por invitado,
el segundo actúa como presupuesto separado por persona.
"""

from __future__ import annotations

import os
import sys

# Antes de cualquier import de tutor.*: config lee el entorno al importarse.
os.environ.setdefault("MAX_SESIONES_DIA", "100000")
os.environ.setdefault("MAX_TOKENS_SESION", "1000000")

import uvicorn  # noqa: E402

from tutor import config as cfg  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    print("=" * 62)
    print("  SERVIDOR DEL HACKATON — sin tope diario, no usar en producción")
    print("=" * 62)
    print(f"  sesiones por día : {cfg.MAX_SESIONES_DIA:,}")
    print(f"  tokens por sesión: {cfg.MAX_TOKENS_SESION:,}")
    print(f"  minutos por sesión: {cfg.MAX_MINUTOS_SESION} (tope duro)")
    print(f"  costo mes por niño: US${cfg.MAX_COSTO_MES_USD_POR_NINO} (tope duro)")
    print(f"  prompt del tutor : {cfg.PROMPTS}")
    print("=" * 62)
    uvicorn.run("tutor.api:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
