"""Corredor de evals.

Las suites son los 4 criterios de YC. Al aplicar, la frase no es "creemos que
cumplimos" sino "acá está nuestra suite, organizada en las cuatro dimensiones
que ustedes pidieron, y estos son los resultados".

    python -m evals.runner
    python -m evals.runner --suite parent_trust
    python -m evals.runner --verbose

⚠️ Consume API. Los tests unitarios (`pytest`) no.

Qué se evalúa y qué no:

  · No evaluamos al tutor en vivo — habla en audio y la sesión la abre el
    navegador. Evaluamos al AUDITOR que lo vigila. Si el auditor no detecta una
    violación del método, la garantía que le vendemos al papá no existe.
  · curriculum_fidelity y longitudinal_memory son determinísticos y ya están
    cubiertos por `pytest`: no gastan API.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from tutor.models import AnalisisSesion, ModoSesion, Sesion  # noqa: E402
from tutor.pipeline import (  # noqa: E402
    ClienteLLM,
    analizar_sesion,
    cliente_por_defecto,
    evaluar_seguridad,
)

RAIZ = Path(__file__).parent
SUITES = ("curriculum_fidelity", "safety", "longitudinal_memory", "parent_trust")


@dataclass
class Caso:
    id: str
    suite: str
    turnos: list[tuple[str, str]]
    espera: dict
    descripcion: str = ""


@dataclass
class Resultado:
    caso: Caso
    paso: bool
    obtenido: dict = field(default_factory=dict)
    fallas: list[str] = field(default_factory=list)
    error: str | None = None


# ─────────────────────────────────────────────────────────────────────────────


def cargar_casos(suite: str | None = None) -> list[Caso]:
    casos: list[Caso] = []
    for nombre in SUITES:
        if suite and nombre != suite:
            continue
        for ruta in sorted((RAIZ / nombre).glob("*.yaml")):
            for crudo in yaml.safe_load(ruta.read_text(encoding="utf-8")) or []:
                casos.append(
                    Caso(
                        id=crudo["id"],
                        suite=nombre,
                        turnos=[(t[0], t[1]) for t in crudo["turnos"]],
                        espera=crudo["espera"],
                        descripcion=crudo.get("descripcion", "").strip(),
                    )
                )
    return casos


def _comparar(espera: dict, obtenido: dict) -> list[str]:
    return [
        f"{campo}: esperaba {valor}, obtuvo {obtenido.get(campo)}"
        for campo, valor in espera.items()
        if obtenido.get(campo) != valor
    ]


def correr_caso(caso: Caso, cliente: ClienteLLM) -> Resultado:
    try:
        if caso.suite == "safety":
            e = evaluar_seguridad(caso.turnos, cliente)
            obtenido = {
                "requiere_escalamiento": e.requiere_escalamiento,
                "nivel": e.nivel.value,
            }
        else:
            transcripcion = "\n".join(f"{q}: {t}" for q, t in caso.turnos)
            sesion = Sesion(
                id=caso.id, nino_id="eval", modo=ModoSesion.GUIADO, inicio=_ahora()
            )
            a: AnalisisSesion = analizar_sesion(sesion, transcripcion, cliente)
            obtenido = a.cumplimiento.model_dump()
    except Exception as exc:  # noqa: BLE001
        return Resultado(caso, paso=False, error=f"{type(exc).__name__}: {exc}")

    fallas = _comparar(caso.espera, obtenido)
    return Resultado(caso, paso=not fallas, obtenido=obtenido, fallas=fallas)


def _ahora():
    from datetime import datetime

    return datetime.now()


# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Evals de RBH Tutor")
    parser.add_argument("--suite", choices=SUITES, help="Correr solo una suite")
    parser.add_argument("--verbose", action="store_true", help="Mostrar también los que pasan")
    args = parser.parse_args()

    casos = cargar_casos(args.suite)
    if not casos:
        print("No hay casos para correr.")
        return 0

    cliente = cliente_por_defecto()
    if type(cliente).__name__ == "ClienteFalso":
        print("\n  ⚠️  Falta ANTHROPIC_API_KEY: los evals necesitan API real.\n")
        return 1

    print("=" * 72)
    print(f"  EVALS — {len(casos)} casos")
    print("=" * 72)

    resultados: list[Resultado] = []
    suite_actual = None

    for caso in casos:
        if caso.suite != suite_actual:
            suite_actual = caso.suite
            print(f"\n  {suite_actual.upper()}")

        r = correr_caso(caso, cliente)
        resultados.append(r)

        marca = "  ok  " if r.paso else " FALLA"
        print(f"   [{marca}] {caso.id}")
        if not r.paso or args.verbose:
            if r.error:
                print(f"            error: {r.error}")
            for f in r.fallas:
                print(f"            {f}")
            if r.paso and args.verbose:
                print(f"            {r.obtenido}")

    print("\n" + "=" * 72)
    for nombre in SUITES:
        de_suite = [r for r in resultados if r.caso.suite == nombre]
        if de_suite:
            ok = sum(1 for r in de_suite if r.paso)
            print(f"  {nombre:24} {ok}/{len(de_suite)}")

    total_ok = sum(1 for r in resultados if r.paso)
    print("=" * 72)
    print(f"  TOTAL: {total_ok}/{len(resultados)}")

    if total_ok < len(resultados):
        print("\n  Hay fallas. Si son del método socrático, el diferencial del")
        print("  producto no se está sosteniendo — es lo primero a revisar.\n")
        return 1

    print("\n  Todo en verde.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
