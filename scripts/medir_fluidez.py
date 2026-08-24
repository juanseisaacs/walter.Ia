"""¿Cuánto se traba la conversación? El número que faltaba.

    python -m scripts.medir_fluidez
    python -m scripts.medir_fluidez --desde ses_567fc061b515

"No está fluida" es la queja más repetida sobre este producto y la única que
nunca tuvo un número detrás. Se discutió tres veces mirando el backend —que
responde en 4 ms— y las tres el problema estaba en otro lado.

Esto lo mide sobre lo único que queda de cada sesión: la transcripción. No mide
latencia (esa vive en la consola del navegador); mide **lo que el niño siente**,
que son tres cosas distintas y se confundían entre sí:

  · CORTADO   el turno del tutor termina a mitad de palabra. Alguien le cortó
              la generación — antes, el eco de su propia voz entrando por el
              micrófono con el VAD en sensibilidad alta.
  · RETOMA    dos turnos seguidos del tutor sin el niño en medio: se cortó y
              volvió a arrancar. Cada uno es una frase que el niño oyó dos veces
              a medias.
  · MUDEZ     `MARCA_DE_MUDEZ`: se quedó callado y hubo que empujarlo.

No necesita API key ni red: lee `data/transcripts/`. Correrlo después de cada
sesión es la forma de saber si un cambio mejoró algo o solo lo movió de lugar.
"""

from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tutor import config as cfg  # noqa: E402

TRANSCRIPTS = cfg.RAIZ / "data" / "transcripts"

# Un turno que no termina en signo de cierre quedó a mitad de frase. Los puntos
# suspensivos cuentan como cierre: el tutor los usa a propósito al dejar algo
# abierto.
CIERRES = '.!?"»)]…'

# Lo que el navegador escribe cuando el tutor se queda callado. Vive en
# `useTutor.ts` (`MARCA_DE_MUDEZ`) y se lee de ahí para que no se desincronice.
def _marca_de_mudez() -> str:
    import re  # noqa: PLC0415

    ts = (cfg.RAIZ / "web" / "src" / "voz" / "useTutor.ts").read_text(encoding="utf-8")
    m = re.search(r'MARCA_DE_MUDEZ\s*=\s*"([^"]*)"', ts)
    return m.group(1) if m else "[el tutor no contestó"


def _turnos(texto: str) -> list[tuple[str, str]]:
    salida = []
    for linea in texto.splitlines():
        if linea.startswith("tutor:"):
            salida.append(("tutor", linea[6:].strip()))
        elif linea.startswith("nino:"):
            salida.append(("nino", linea[5:].strip()))
    return salida


def medir(texto: str, marca_mudez: str) -> dict:
    turnos = _turnos(texto)
    del_tutor = [t for quien, t in turnos if quien == "tutor" and t]

    cortados = [t for t in del_tutor if t and t[-1] not in CIERRES]

    # Dos turnos del tutor seguidos: se cortó y retomó.
    retomas = sum(
        1
        for i in range(1, len(turnos))
        if turnos[i][0] == "tutor" and turnos[i - 1][0] == "tutor"
    )

    mudeces = sum(1 for _, t in turnos if marca_mudez[:20] in t)

    return {
        "turnos": len(del_tutor),
        "cortados": len(cortados),
        "retomas": retomas,
        "mudeces": mudeces,
        "ejemplos": ["…" + t[-34:] for t in cortados[:2]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", help="solo las sesiones desde esta (por id), inclusive")
    args = ap.parse_args()

    if not TRANSCRIPTS.is_dir():
        print(f"\n  No hay transcripciones en {TRANSCRIPTS}\n")
        return 1

    archivos = sorted(TRANSCRIPTS.glob("*.txt"), key=lambda p: p.stat().st_mtime)
    if args.desde:
        desde = [i for i, f in enumerate(archivos) if f.stem == args.desde]
        if not desde:
            print(f"\n  No encuentro {args.desde}\n")
            return 1
        archivos = archivos[desde[0] :]

    marca = _marca_de_mudez()
    print("=" * 78)
    print("  FLUIDEZ — lo que el niño siente, contado sobre las transcripciones")
    print("=" * 78)
    print(f"\n{'sesión':22}{'turnos':>7}{'cortados':>10}{'retomas':>9}{'mudez':>7}")

    total = {"turnos": 0, "cortados": 0, "retomas": 0, "mudeces": 0}
    peores: list[tuple[str, list[str]]] = []
    for f in archivos:
        m = medir(f.read_text(encoding="utf-8"), marca)
        if not m["turnos"]:
            continue
        for k in total:
            total[k] += m[k]
        print(f"{f.stem:22}{m['turnos']:>7}{m['cortados']:>10}{m['retomas']:>9}{m['mudeces']:>7}")
        if m["ejemplos"]:
            peores.append((f.stem, m["ejemplos"]))

    t = max(total["turnos"], 1)
    print("\n" + "-" * 78)
    print(
        f"  {total['cortados']}/{total['turnos']} turnos cortados "
        f"({100 * total['cortados'] / t:.0f}%) · "
        f"{total['retomas']} retomas · {total['mudeces']} mudeces"
    )

    if peores:
        print("\n  Dónde se cortó (últimas):")
        for sesion, ejemplos in peores[-3:]:
            for e in ejemplos:
                print(f"    {sesion}  {e}")

    # 20% era el número del 23/08, antes de retener el audio mientras el tutor
    # habla. Sirve de referencia: si vuelve a subir, algo lo desarmó.
    print("\n  Referencia: 20% de cortes el 23/08 (8 sesiones, antes del arreglo).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
