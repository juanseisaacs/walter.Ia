"""Verifica la cadena de veredictos del método, o la siembra la primera vez.

    python -m scripts.verificar_cadena             # ¿está íntegra?
    python -m scripts.verificar_cadena --sembrar   # ancla lo que ya existía

Cada auditoría que el Analista escribe queda anotada en un registro append-only
encadenado por SHA-256 (`data/audits/cadena.jsonl`). Este comando lo recorre y
dice si alguien tocó algo: un veredicto editado, uno borrado, un eslabón metido
en el medio.

Es lo que convierte el *«el método se sostuvo en el 83% de las sesiones»* del
panel en una afirmación **verificable** en vez de una que hay que creernos. Sin
esto, cualquiera con acceso al disco podía mejorar ese número editando un
archivo, y no había forma de notarlo.

No gasta cuota: son hashes y comparaciones de archivos.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from tutor import config as cfg  # noqa: E402
from tutor.cadena import sembrar, ultimo_hash, verificar  # noqa: E402
from tutor.storage import RepositorioSQLite  # noqa: E402


def _sesiones_en_orden(repo: RepositorioSQLite) -> list[str]:
    """Los ids de sesión ordenados por cuándo ocurrieron.

    La cadena es un registro temporal: sembrarla en orden de nombre de archivo
    la volvería una mentira ordenada. El orden sale de `inicio`, que es el dato
    real. Lo que no esté en la base va al final, por nombre — es lo único que se
    puede hacer con una auditoría cuya sesión ya no existe.
    """
    con = sqlite3.connect(cfg.DB)
    try:
        conocidas = {fila[0]: fila[1] for fila in con.execute("SELECT id, inicio FROM sesiones")}
    finally:
        con.close()

    en_disco = [a.stem for a in repo.ruta_auditorias.glob("*.json")]
    return sorted(en_disco, key=lambda s: (s not in conocidas, conocidas.get(s, ""), s))


def main() -> int:
    p = argparse.ArgumentParser(description="Verifica o siembra la cadena de veredictos.")
    p.add_argument("--sembrar", action="store_true", help="Ancla las auditorías que ya existían")
    args = p.parse_args()

    repo = RepositorioSQLite(cfg.DB, cfg.DATOS)

    print("=" * 72)
    print("  CADENA DE VEREDICTOS DEL MÉTODO")
    print("=" * 72)

    if args.sembrar:
        orden = _sesiones_en_orden(repo)
        try:
            anclados = sembrar(repo.ruta_cadena, repo.ruta_auditorias, orden)
        except ValueError as e:
            print(f"\n  No se puede sembrar: {e}")
            print("  La cadena ya está en uso. Sembrar la reescribiría desde cero.\n")
            return 1
        print(f"\n  {anclados} auditoría(s) ancladas, en el orden en que ocurrieron.")
        print("  ⚠ Sembrar deja constancia de lo que HAY HOY. No puede probar")
        print("    que nadie lo tocara antes de este momento.\n")

    v = verificar(repo.ruta_cadena, repo.ruta_auditorias)
    print(f"\n  {v.resumen()}")

    if extremo := ultimo_hash(repo.ruta_cadena):
        print(f"  último hash: {extremo}")
        print("  (publicarlo fuera de este disco es lo que impediría reescribir")
        print("   la cadena entera desde cero; hoy no se publica en ningún lado)")

    if v.sin_anotar:
        print(f"\n  {len(v.sin_anotar)} auditoría(s) sin anclar:")
        for s in v.sin_anotar[:10]:
            print(f"    · {s}")
        if len(v.sin_anotar) > 10:
            print(f"    … y {len(v.sin_anotar) - 10} más")
        print("  Corré con --sembrar si la cadena todavía está vacía.")

    if not v.integra:
        print(f"\n  ✗ {len(v.hallazgos)} ROTURA(S):")
        for h in v.hallazgos:
            print(f"    {h}")
        print("\n  Un veredicto alterado significa que el porcentaje del panel")
        print("  no corresponde a lo que el Analista dictaminó.\n")
        return 1

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
