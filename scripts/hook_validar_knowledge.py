"""Valida `knowledge/` justo después de editarlo. Lo dispara un hook.

    .claude/settings.json → PostToolUse(Edit|Write) → este script

`knowledge/` es el activo del proyecto: el currículum y los prompts se cargan en
runtime y **no los cubre el compilador ni el linter**. Un YAML con un
prerrequisito colgado o un prompt que perdió la regla del elogio inflado no
rompe nada al guardarlo — rompe la sesión del niño, horas después.

Hasta ahora eso lo sostenía el `CLAUDE.md`, que es persuasión. Esto es
obligación: se corre solo, cuesta menos de dos segundos y devuelve el fallo
en el momento, con el archivo todavía fresco.

Lee por stdin el JSON del hook y elige qué suite correr según la ruta editada.
Si la ruta no es de `knowledge/`, sale sin hacer nada y sin ruido.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Qué valida qué. La clave es un patrón sobre la ruta editada, tolerante con
# los dos separadores: en Windows el hook manda `C:\RBH-Tutor\knowledge\...`
# y en Git Bash `/c/RBH-Tutor/knowledge/...`.
SUITES: tuple[tuple[str, str, str], ...] = (
    (
        r"knowledge[/\\]curriculum",
        "tests/test_curriculum.py",
        "el grafo del currículum (ciclos, prerrequisitos colgados, IDs duplicados, "
        "y que el schema JSON y el modelo Pydantic no se hayan separado)",
    ),
    (
        r"knowledge[/\\]prompts",
        "tests/test_voice.py",
        "los prompts del tutor (que el playbook no permita dar la respuesta, que "
        "los valores prohíban el elogio inflado, que la seguridad siga completa)",
    ),
)


def suite_para(ruta: str) -> tuple[str, str] | None:
    """Qué suite le toca a esta ruta. None si no es de `knowledge/`."""
    for patron, suite, que_cubre in SUITES:
        if re.search(patron, ruta, re.IGNORECASE):
            return suite, que_cubre
    return None


class EntradaIlegible(Exception):
    """El hook recibió algo que no es el JSON esperado.

    Tiene su propia excepción, y no un `return ""`, por lo que pasó la primera
    vez que se probó esto: el `except` devolvía cadena vacía, `main()` salía 0,
    y el hook **aprobaba sin haber validado nada**. Exactamente el patrón que
    `BITACORA.md` documenta siete veces — algo dejó de pasar y no había dónde
    enterarse.

    No bloquea el trabajo (un hook roto no puede frenar al que edita), pero
    grita: si esto aparece, el hook lleva sin validar desde vaya a saber cuándo.
    """


def ruta_editada(entrada: str) -> str:
    """El archivo que se acaba de tocar, según el JSON del hook."""
    try:
        datos = json.loads(entrada or "{}")
    except json.JSONDecodeError as e:
        raise EntradaIlegible(str(e)) from e
    if not isinstance(datos, dict):
        raise EntradaIlegible(f"se esperaba un objeto, llegó {type(datos).__name__}")
    return str(
        datos.get("tool_input", {}).get("file_path")
        or datos.get("tool_response", {}).get("filePath")
        or ""
    )


def main() -> int:
    try:
        ruta = ruta_editada(sys.stdin.read())
    except EntradaIlegible as e:
        print(
            json.dumps(
                {
                    "systemMessage": (
                        f"El hook de knowledge/ no pudo leer su entrada ({e}) — "
                        f"NO se validó nada. Revisá scripts/hook_validar_knowledge.py"
                    )
                }
            )
        )
        return 0

    if not ruta:
        return 0

    elegida = suite_para(ruta)
    if elegida is None:
        return 0  # no es de knowledge/: nada que validar

    suite, que_cubre = elegida
    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", suite, "-q", "--no-header"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if resultado.returncode == 0:
        return 0

    # Exit 2 en PostToolUse le devuelve el motivo al modelo, que es lo que hace
    # que el fallo se atienda ahora y no dentro de tres días.
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    f"Al editar {Path(ruta).name} se rompió {que_cubre}.\n\n"
                    f"Corré `pytest {suite}` y arreglalo antes de seguir.\n\n"
                    f"{salida[-2000:]}"
                ),
                "systemMessage": f"knowledge/ quedó inconsistente: falló {suite}",
            }
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
