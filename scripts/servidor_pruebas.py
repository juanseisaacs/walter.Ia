"""Levanta el backend con los topes soltados, para probar sin quedarse sin cupo.

    python -m scripts.servidor_pruebas

Existe porque pasarle las variables por el shell NO funciona de forma
confiable en Windows: `MAX_SESIONES_DIA=100 python -m uvicorn ...` en Git Bash
no propaga el valor a un .exe, y `export` tampoco sobrevive al lanzamiento en
segundo plano. El síntoma es peor que el problema — el servidor arranca igual,
sin avisar, con los topes de producción — y se pierde un rato entendiendo por
qué la API contesta 429 cuando el cupo "está en 100".

Acá las variables se ponen ANTES de importar `tutor.config`, que es lo único
que importa: config las lee una vez, al importarse.

NUNCA en producción. Los topes existen para proteger al niño y al margen: sin
techo diario, un bucle del cliente puede gastar el mes entero en una tarde.
"""

from __future__ import annotations

import os
import sys

# Antes de cualquier import de tutor.*: config lee el entorno al importarse.
os.environ.setdefault("MAX_SESIONES_DIA", "100")
os.environ.setdefault("MAX_TOKENS_SESION", "400000")

import uvicorn  # noqa: E402

from tutor import config as cfg  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    print("=" * 62)
    print("  SERVIDOR DE PRUEBAS — topes soltados, no usar en producción")
    print("=" * 62)
    print(f"  sesiones por día : {cfg.MAX_SESIONES_DIA}")
    print(f"  tokens por sesión: {cfg.MAX_TOKENS_SESION:,}")
    print(f"  prompt del tutor : {cfg.PROMPTS}")
    print("=" * 62)
    uvicorn.run("tutor.api:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
