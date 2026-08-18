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
    navegador. Evaluamos a los agentes OFFLINE que lo respaldan: el Analista
    (método, currículum, memoria) y el Vigilante (seguridad).
  · parent_trust    → ¿el Analista detecta cuándo el tutor regaló la respuesta?
  · curriculum_fidelity → ¿el Analista ata la señal a la habilidad correcta?
    (guarda el bug de habilidad_id=None y el congelamiento por transcripción sucia)
  · longitudinal_memory → ¿el Analista arma la ficha del niño sin inventarla?
  · safety          → ¿el Vigilante escala cuando debe y calla cuando no?
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from tutor.curriculum import cargar_grafo  # noqa: E402
from tutor.models import AnalisisSesion, ModoSesion, Sesion  # noqa: E402
from tutor.pipeline import (  # noqa: E402
    ClienteLLM,
    analizar_sesion,
    cliente_por_defecto,
    evaluar_seguridad,
)

RAIZ = Path(__file__).parent
SUITES = ("curriculum_fidelity", "safety", "longitudinal_memory", "parent_trust")

# El Analista ata cada observación académica a un habilidad_id usando la lista de
# habilidades trabajadas; sin el grafo esa atadura no ocurre. Se carga una vez.
GRAFO = cargar_grafo()


@dataclass
class Caso:
    id: str
    suite: str
    turnos: list[tuple[str, str]]
    espera: dict
    descripcion: str = ""
    habilidades: list[str] = field(default_factory=list)


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
                        habilidades=crudo.get("habilidades", []),
                    )
                )
    return casos


def _sin_acentos(texto: str) -> str:
    """Para comparar substrings sin que 'fútbol' vs 'futbol' cause un falso rojo."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _comparar(espera: dict, obtenido: dict) -> list[str]:
    return [
        f"{campo}: esperaba {valor}, obtuvo {obtenido.get(campo)}"
        for campo, valor in espera.items()
        if obtenido.get(campo) != valor
    ]


def correr_caso(caso: Caso, cliente: ClienteLLM) -> Resultado:
    evaluadores = {
        "safety": _eval_safety,
        "parent_trust": _eval_metodo,
        "curriculum_fidelity": _eval_curriculum,
        "longitudinal_memory": _eval_memoria,
    }
    try:
        obtenido, fallas = evaluadores[caso.suite](caso, cliente)
    except Exception as exc:  # noqa: BLE001
        return Resultado(caso, paso=False, error=f"{type(exc).__name__}: {exc}")
    return Resultado(caso, paso=not fallas, obtenido=obtenido, fallas=fallas)


def _analizar(caso: Caso, cliente: ClienteLLM) -> AnalisisSesion:
    """Corre el Analista con el contexto de habilidades trabajadas — sin él, las
    observaciones académicas salen sin habilidad_id y no se pueden validar."""
    transcripcion = "\n".join(f"{q}: {t}" for q, t in caso.turnos)
    sesion = Sesion(
        id=caso.id,
        nino_id="eval",
        modo=ModoSesion.GUIADO,
        inicio=_ahora(),
        habilidades_trabajadas=caso.habilidades,
    )
    return analizar_sesion(sesion, transcripcion, cliente, GRAFO)


def _eval_safety(caso: Caso, cliente: ClienteLLM) -> tuple[dict, list[str]]:
    e = evaluar_seguridad(caso.turnos, cliente)
    obtenido = {"requiere_escalamiento": e.requiere_escalamiento, "nivel": e.nivel.value}
    return obtenido, _comparar(caso.espera, obtenido)


def _eval_metodo(caso: Caso, cliente: ClienteLLM) -> tuple[dict, list[str]]:
    obtenido = _analizar(caso, cliente).cumplimiento.model_dump()
    return obtenido, _comparar(caso.espera, obtenido)


# Tipos de observación que hablan de una habilidad concreta (los que van a `dominio`).
_TIPOS_ACADEMICOS = {
    "contiene_acierto": "acierto",
    "contiene_error": "error",
    "contiene_pista_necesaria": "pista_necesaria",
    "contiene_dominio": "dominio",
}


def _eval_curriculum(caso: Caso, cliente: ClienteLLM) -> tuple[dict, list[str]]:
    """¿Ató la señal a la habilidad correcta? Es la fidelidad al currículum: una
    observación con la habilidad equivocada contamina el planificador."""
    a = _analizar(caso, cliente)
    ids = {o.habilidad_id for o in a.observaciones if o.habilidad_id}
    tipos = {o.tipo.value for o in a.observaciones}
    obtenido = {"habilidades": sorted(ids), "tipos": sorted(tipos)}

    fallas: list[str] = []
    esperado = caso.espera.get("habilidad_id")
    if esperado and esperado not in ids:
        fallas.append(f"habilidad_id: esperaba {esperado} entre {sorted(ids)}")
    for campo, tipo in _TIPOS_ACADEMICOS.items():
        if campo in caso.espera and (tipo in tipos) != caso.espera[campo]:
            fallas.append(f"{campo}: esperaba {caso.espera[campo]}, obtuvo {tipo in tipos}")
    # `acierto` y `dominio` son ambos un logro; el modelo alterna entre ellos según
    # cuán solo lo hizo. Cuando eso da igual, se pide "positivo" y no un tipo exacto.
    if "contiene_positivo" in caso.espera:
        positivo = bool(tipos & {"acierto", "dominio"})
        if positivo != caso.espera["contiene_positivo"]:
            fallas.append(f"contiene_positivo: esperaba {caso.espera['contiene_positivo']}, obtuvo {positivo}")
    return obtenido, fallas


def _eval_memoria(caso: Caso, cliente: ClienteLLM) -> tuple[dict, list[str]]:
    """¿Arma la ficha del niño con lo que sostiene la transcripción, sin inventar?
    Una ficha inflada con datos falsos rompe la confianza del papá igual que una vacía."""
    p = _analizar(caso, cliente).perfil_sugerido
    listas = {
        "interes": [x.lower() for x in (p.intereses if p else [])],
        "motivador": [x.lower() for x in (p.motivadores if p else [])],
        "frustracion": [x.lower() for x in (p.frustraciones if p else [])],
    }
    obtenido = {f"{clave}es": lista for clave, lista in listas.items()}

    fallas: list[str] = []
    for clave, lista in listas.items():
        campo_bool = f"captura_{clave}"
        if campo_bool in caso.espera and bool(lista) != caso.espera[campo_bool]:
            fallas.append(f"{campo_bool}: esperaba {caso.espera[campo_bool]}, obtuvo {bool(lista)}")
        campo_sub = f"{clave}_contiene"
        if campo_sub in caso.espera:
            sub = _sin_acentos(str(caso.espera[campo_sub]).lower())
            if not any(sub in _sin_acentos(x) for x in lista):
                fallas.append(f"{campo_sub}: '{caso.espera[campo_sub]}' no aparece en {lista}")
    return obtenido, fallas


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
