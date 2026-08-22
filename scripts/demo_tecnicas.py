"""El motor de técnicas, sesión a sesión, con un niño simulado.

    python -m scripts.demo_tecnicas

No gasta cuota ni toca la base: simula doce sesiones y muestra qué técnica
elegiría el sistema en cada una y por qué.

Existe porque en este repo las demos encuentran lo que los tests no ven. La
calibración del olvido estuvo diez veces mal con toda la suite en verde, y lo
destapó correr una simulación con datos realistas (`BITACORA.md`, fase 2). Un
motor que decide sobre un niño tiene el mismo riesgo: cada regla puede estar
bien y el comportamiento completo ser absurdo — cambiar de método cada sesión,
o no cambiar nunca.

Lo que hay que mirar acá no es si funciona, es si el ritmo es **razonable para
un papá**: cuántas sesiones aguanta una técnica que no sirve antes de que el
sistema lo note.
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tutor.tecnicas import (  # noqa: E402
    GANANCIA_MINIMA,
    SESIONES_PARA_JUZGAR,
    cargar_biblioteca,
    elegir,
    medir,
)

HABILIDAD = "mat.suma.sin_reagrupacion"


def simular(nombre: str, cuanto_mueve: dict[str, float], sesiones: int = 12) -> None:
    """Un niño al que cada técnica le rinde distinto. `cuanto_mueve` es lo que
    subiría el dominio por sesión con cada una — eso es lo que el motor NO sabe
    y tiene que descubrir probando."""
    biblioteca = cargar_biblioteca()
    historial: list[tuple[str | None, float, float]] = []
    activa: str | None = None
    dominio = 0.25

    print(f"\n{'═' * 78}")
    print(f"  {nombre}")
    rinde = " · ".join(f"{k}={v:+.2f}" for k, v in cuanto_mueve.items())
    print(f"  lo que el motor NO sabe: {rinde}")
    print("═" * 78)
    print(f"  {'ses':>3}  {'técnica':22} {'dominio':>14}  por qué")
    print(f"  {'─' * 3}  {'─' * 22} {'─' * 14}  {'─' * 30}")

    for n in range(1, sesiones + 1):
        decision = elegir(biblioteca, HABILIDAD, medir(historial), activa)
        antes = dominio
        # El dominio sube lo que esa técnica le rinde a ESTE niño, con techo en 1.
        dominio = min(1.0, dominio + cuanto_mueve.get(decision.tecnica_id, 0.0))
        historial.append((decision.tecnica_id, antes, dominio))
        activa = decision.tecnica_id

        marca = "←" if decision.es_nueva else " "
        print(
            f"  {n:>3}  {decision.tecnica_id:22} "
            f"{antes:.2f} → {dominio:.2f} {marca}  {decision.porque}"
        )

    resumen = medir(historial)
    print(f"\n  Dominio final: {dominio:.2f}  (arrancó en 0.25)")
    print("  Lo que quedó medido de cada técnica:")
    for tid, intento in sorted(resumen.items(), key=lambda kv: -kv[1].ganancia):
        veredicto = "sirve" if intento.funciono else "no sirve"
        print(
            f"    {tid:22} {intento.ganancia:+.2f} en "
            f"{intento.sesiones} sesión(es) — {veredicto}"
        )


def main() -> int:
    print("=" * 78)
    print("  MOTOR DE TÉCNICAS — simulación, sin tocar la base ni gastar cuota")
    print("=" * 78)
    print(f"  Se juzga a las {SESIONES_PARA_JUZGAR} sesiones · sirve si movió ≥ {GANANCIA_MINIMA}")

    # A este le entra por lo concreto y rebota con la estructura. Es el caso que
    # el motor existe para encontrar.
    simular(
        "Un niño al que solo le entra por lo concreto",
        {"concreto_primero": 0.09, "estructura_primero": 0.00,
         "el_explica": 0.01, "modelo_resuelto": 0.02,
         "su_mundo": 0.01, "numero_puro": 0.00},
    )

    # A este le da igual el método: cualquiera le rinde. El motor no debería
    # andar cambiándolo de técnica sin motivo.
    simular(
        "Un niño al que le da igual el método",
        {t.id: 0.06 for t in cargar_biblioteca()},
    )

    # Y el caso incómodo: ninguna le sirve. El motor no puede fingir que sí.
    simular(
        "Un niño al que ninguna le mueve la aguja",
        {t.id: 0.005 for t in cargar_biblioteca()},
    )

    print("\n" + "=" * 78)
    print("  Qué mirar acá:")
    print("   · ¿Cuántas sesiones aguanta una técnica que no sirve? Eso lo siente el papá.")
    print("   · ¿Cambia de método sin motivo cuando ya encontró uno que anda?")
    print("   · Con el tercer niño, ¿el sistema insiste con algo que no funciona,")
    print("     o al menos deja de dar vueltas? Ninguna respuesta es obviamente")
    print("     la correcta — es una decisión de producto, y hay que verla.")
    print("=" * 78 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
