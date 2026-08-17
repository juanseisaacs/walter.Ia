"""Demo: check_answer con respuestas habladas.

El nino HABLA, no escribe. Muestra el principio del tool:
TOLERANTE CON LA FORMA, ESTRICTO CON EL VALOR.

    python -m scripts.demo_verificacion
"""

from tutor.models import Ejercicio, TextoLocalizado
from tutor.tools import Veredicto, check_answer

EJERCICIO = Ejercicio(
    id="e1",
    habilidad_id="mat.suma.con_reagrupacion",
    enunciado=TextoLocalizado(es="Juan tiene 27 figuritas y le regalan 15. Cuantas tiene?"),
    respuesta="42",
    validado=True,
)

RESPUESTAS = [
    "42",
    "es 42",
    "cuarenta y dos",
    "creo que es cuarenta y dos",
    "42 figuritas",
    " 42! ",
    "41",
    "cuarenta y uno",
    "24",
    "no se",
    "42 o 43",
]

SIMBOLO = {
    Veredicto.CORRECTO: "OK   ",
    Veredicto.INCORRECTO: "NO   ",
    Veredicto.REQUIERE_JUICIO: "JUEZ ",
}


def main() -> None:
    print("=" * 66)
    print(f"  {EJERCICIO.enunciado.es}")
    print(f"  Respuesta correcta: {EJERCICIO.respuesta}")
    print("=" * 66 + "\n")

    for dijo in RESPUESTAS:
        r = check_answer(EJERCICIO, dijo)
        entendido = f"-> entendio {r.valor_interpretado}" if r.valor_interpretado else ""
        print(f'  {SIMBOLO[r.veredicto]} el nino dice: {dijo!r:36} {entendido}')

    print("\n  Tolerante con la forma, estricto con el valor.")
    print("  Sin red, sin modelo, ~5ms. La aritmetica no la valida una IA.\n")


if __name__ == "__main__":
    main()
