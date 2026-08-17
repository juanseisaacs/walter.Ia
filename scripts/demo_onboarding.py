"""Demo: la entrevista de onboarding, con la API real.

El papá está simulado (respuestas guionadas) pero el entrevistador es real:
elige qué preguntar, con qué tono, y decide cuándo ya tiene suficiente.

    python -m scripts.demo_onboarding

Consume API (Sonnet + Haiku). Cuesta centavos.
"""

import sys

from dotenv import load_dotenv

# La consola de Windows usa cp1252 por defecto y revienta con acentos.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from tutor.pipeline import (  # noqa: E402
    cliente_por_defecto,
    crear_nino_desde_ficha,
    extraer_ficha,
    siguiente_pregunta,
)

# Un papá típico: da datos de a poco, se va por las ramas, no dice todo junto.
RESPUESTAS_DEL_PAPA = [
    "Hola! Le compre esto a mi hijo, se llama Juan",
    "Tiene 7, esta en segundo grado",
    "Le cuesta concentrarse, se aburre rapido con la tarea. Pero es re vivo",
    "Le encanta el futbol, y los dinosaurios. Y le gusta competir, si le pones "
    "un reloj se pone las pilas",
    "Si, mejor directo. Si le das muchas vueltas se pierde",
    "ana.martinez@ejemplo.com",
]


def main() -> None:
    cliente = cliente_por_defecto()
    if type(cliente).__name__ == "ClienteFalso":
        print("\n  Falta ANTHROPIC_API_KEY en .env\n")
        return

    print("=" * 72)
    print("  ENTREVISTA DE ONBOARDING")
    print("=" * 72)

    historial: list[tuple[str, str]] = []
    ficha = None

    for respuesta_papa in RESPUESTAS_DEL_PAPA:
        ficha = extraer_ficha(historial, cliente) if historial else None
        if ficha and ficha.completa:
            break

        from tutor.pipeline import FichaInicial

        pregunta = siguiente_pregunta(historial, ficha or FichaInicial(), cliente)
        print(f"\n  TUTOR: {pregunta.strip()}")
        historial.append(("asesor", pregunta))

        print(f"\n  PAPA:  {respuesta_papa}")
        historial.append(("papa", respuesta_papa))

    ficha = extraer_ficha(historial, cliente)

    print("\n" + "-" * 72)
    print("  LO QUE ENTENDIO")
    print("-" * 72)
    print(f"   Mail:      {ficha.email_papa}")
    print(f"   Nino:      {ficha.nombre_nino}, {ficha.edad} anos, {ficha.grado} grado")
    print(f"   Intereses: {', '.join(ficha.intereses) or '-'}")
    print(f"   Le cuesta: {', '.join(ficha.dificultades) or '-'}")
    print(f"   Lo motiva: {', '.join(ficha.motivadores) or '-'}")
    print(f"   Estilo:    {ficha.estilo_comunicacion or '-'}")

    if not ficha.completa:
        print(f"\n   INCOMPLETA, falta: {', '.join(ficha.falta())}\n")
        return

    cierre = siguiente_pregunta(historial, ficha, cliente)
    print(f"\n  TUTOR: {cierre.strip()}")

    nino = crear_nino_desde_ficha(ficha, "n1")
    print("\n" + "-" * 72)
    print("  FICHA CREADA")
    print("-" * 72)
    print(f"   {nino.nombre} | alertas a: {nino.email_papa}")
    print(f"   Dominio academico: {len(nino.dominio)} habilidades  <- arranca vacio")
    print(f"   Madurez del vinculo: {nino.perfil.madurez_vinculo}   <- se lo contaron\n")


if __name__ == "__main__":
    main()
