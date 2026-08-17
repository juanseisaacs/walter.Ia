"""Genera el banco de ejercicios. Herramienta de construcción, no agente.

Corre una vez (y después solo para nodos nuevos o variantes temáticas).

    python -m scripts.build_exercise_bank --grado 2 --cantidad 10
    python -m scripts.build_exercise_bank --grado 2 --tema futbol
    python -m scripts.build_exercise_bank --habilidad mat.suma.con_reagrupacion

LO IMPORTANTE NO ES GENERAR: ES VALIDAR.

Un ejercicio solo entra al banco si el CÓDIGO verificó que la cuenta da la
respuesta declarada. Un "¡correcto!" a 7+5=13 destruye la confianza del papá
para siempre — y el modelo se equivoca en aritmética.
"""

from __future__ import annotations

import argparse
import ast
import operator
import sys
from uuid import uuid4

from dotenv import load_dotenv
from pydantic import BaseModel

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from tutor import config as cfg  # noqa: E402
from tutor.curriculum import cargar_grafo  # noqa: E402
from tutor.models import Ejercicio, Habilidad, TextoLocalizado  # noqa: E402
from tutor.pipeline import ClienteLLM, cliente_por_defecto  # noqa: E402
from tutor.storage import RepositorioSQLite  # noqa: E402
from tutor.voice import cargar_prompt  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Validación — la parte que importa
# ─────────────────────────────────────────────────────────────────────────────

_OPERADORES = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def evaluar_cuenta(expresion: str) -> float | None:
    """Evalúa aritmética simple de forma segura.

    Se camina el AST y solo se permiten números y las cuatro operaciones.
    NO se usa `eval`: la expresión viene de un modelo, y un modelo puede
    devolver cualquier cosa.
    """

    def _nodo(n: ast.AST) -> float:
        if isinstance(n, ast.Constant) and isinstance(n.value, int | float):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _OPERADORES:
            return _OPERADORES[type(n.op)](_nodo(n.left), _nodo(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPERADORES:
            return _OPERADORES[type(n.op)](_nodo(n.operand))
        raise ValueError(f"Operación no permitida: {ast.dump(n)}")

    try:
        return _nodo(ast.parse(expresion.strip(), mode="eval").body)
    except Exception:
        return None


def validar(enunciado: str, respuesta: str, operacion: str | None) -> str | None:
    """Devuelve el motivo del rechazo, o None si el ejercicio pasa."""
    if not enunciado.strip():
        return "enunciado vacío"
    if not respuesta.strip():
        return "respuesta vacía"
    if len(enunciado) > 220:
        return "demasiado largo para escuchar de una vez"

    if not operacion:
        return None  # habilidades sin cuenta: no hay nada que verificar

    calculado = evaluar_cuenta(operacion)
    if calculado is None:
        return f"la cuenta '{operacion}' no se pudo evaluar"

    try:
        declarado = float(respuesta.replace(",", "."))
    except ValueError:
        return f"la respuesta '{respuesta}' no es un número pero hay cuenta"

    if abs(calculado - declarado) > 1e-9:
        return f"LA CUENTA NO CIERRA: {operacion} = {calculado:g}, pero dice {declarado:g}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Generación
# ─────────────────────────────────────────────────────────────────────────────


class _EjercicioCrudo(BaseModel):
    enunciado: str
    respuesta: str
    operacion: str | None = None


class _Tanda(BaseModel):
    ejercicios: list[_EjercicioCrudo]


def generar(
    habilidad: Habilidad, cantidad: int, tema: str | None, cliente: ClienteLLM
) -> tuple[list[Ejercicio], list[str]]:
    """Genera y valida. Devuelve (aceptados, motivos de rechazo)."""
    contexto = [
        f"Habilidad: {habilidad.nombre.es}",
        f"Qué debe poder hacer el niño: {habilidad.descripcion.es}",
        f"Grado de referencia: {habilidad.grado_sugerido}",
        f"Cantidad: {cantidad}",
    ]
    if tema:
        contexto.append(f"Tema para ambientar: {tema}")

    tanda = cliente.extraer(
        cfg.MODELO_GENERADOR,
        cargar_prompt("exercise_generator"),
        "\n".join(contexto),
        _Tanda,
    )

    aceptados, rechazos = [], []
    for crudo in tanda.ejercicios:
        motivo = validar(crudo.enunciado, crudo.respuesta, crudo.operacion)
        if motivo:
            rechazos.append(f"{crudo.enunciado[:50]}... -> {motivo}")
            continue
        aceptados.append(
            Ejercicio(
                id=f"ej_{uuid4().hex[:12]}",
                habilidad_id=habilidad.id,
                enunciado=TextoLocalizado(es=crudo.enunciado.strip()),
                respuesta=crudo.respuesta.strip(),
                tema=tema,
                validado=True,  # solo llega acá lo que pasó la validación
            )
        )
    return aceptados, rechazos


# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description="Genera el banco de ejercicios")
    p.add_argument("--grado", type=int, help="Generar para todas las habilidades del grado")
    p.add_argument("--habilidad", help="Generar solo para una habilidad")
    p.add_argument("--cantidad", type=int, default=10, help="Por habilidad (default 10)")
    p.add_argument("--tema", help="Variante temática: futbol, dinosaurios...")
    p.add_argument("--seco", action="store_true", help="No guardar, solo mostrar")
    args = p.parse_args()

    grafo = cargar_grafo()
    if args.habilidad:
        objetivo = [grafo.habilidad(args.habilidad)]
    elif args.grado:
        objetivo = grafo.por_grado(args.grado)
    else:
        print("Indicá --grado o --habilidad")
        return 1

    cliente = cliente_por_defecto()
    if type(cliente).__name__ == "ClienteFalso":
        print("\n  Falta ANTHROPIC_API_KEY en .env\n")
        return 1

    repo = RepositorioSQLite(cfg.DB, cfg.DATOS)

    print("=" * 72)
    print(f"  BANCO DE EJERCICIOS — {len(objetivo)} habilidades × {args.cantidad}")
    if args.tema:
        print(f"  Tema: {args.tema}")
    print("=" * 72)

    total_ok = total_rechazo = 0
    for habilidad in objetivo:
        aceptados, rechazos = generar(habilidad, args.cantidad, args.tema, cliente)
        total_ok += len(aceptados)
        total_rechazo += len(rechazos)

        marca = "ok " if not rechazos else "!! "
        print(f"\n  [{marca}] {habilidad.nombre.es:34} {len(aceptados)} aceptados")
        for motivo in rechazos:
            print(f"          RECHAZADO: {motivo}")
        if aceptados:
            print(f'          ej: "{aceptados[0].enunciado.es}" -> {aceptados[0].respuesta}')

        if not args.seco and aceptados:
            repo.guardar_ejercicios(aceptados)

    print("\n" + "=" * 72)
    print(f"  Aceptados: {total_ok}   Rechazados: {total_rechazo}")
    if total_rechazo:
        print("\n  Los rechazados NUNCA llegan a un niño. Para eso está el validador.")
    if args.seco:
        print("\n  (modo seco: no se guardó nada)")
    print("=" * 72 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
