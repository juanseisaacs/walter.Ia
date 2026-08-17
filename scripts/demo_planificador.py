"""Demo: el cerebro pedagógico en acción, sin gastar un token.

Simula a un niño a lo largo de varias sesiones y unas vacaciones, para ver
funcionar el planificador, el dominio y el olvido.

    python -m scripts.demo_planificador
"""

from datetime import datetime, timedelta

from tutor.curriculum import cargar_grafo
from tutor.models import Nino, RegistroDominio
from tutor.pedagogy import (
    actualizar_dominio,
    esta_dominada,
    habilidades_para_repasar,
    nivel_efectivo,
    resumen_para_prompt,
    siguiente_habilidad,
)


def practicar(nino: Nino, grafo, ahora: datetime, aciertos: int, pistas: int = 0) -> None:
    """Una sesión: el planificador elige, el niño practica."""
    objetivo = siguiente_habilidad(nino, grafo, ahora)
    if objetivo is None:
        print("   (domina todo el grafo alcanzable)")
        return

    registro = nino.dominio.get(objetivo.id) or RegistroDominio(habilidad_id=objetivo.id)
    for _ in range(aciertos):
        registro = actualizar_dominio(registro, acerto=True, pistas_usadas=pistas, ahora=ahora)
    nino.dominio[objetivo.id] = registro

    estado = "DOMINADA" if esta_dominada(registro, ahora) else "en progreso"
    print(f"   {ahora:%d/%m}  {objetivo.nombre.es:34} nivel {registro.nivel:.2f}  [{estado}]")


def main() -> None:
    grafo = cargar_grafo()
    nino = Nino(id="n1", nombre="Juan", edad=7, grado=2)
    ahora = datetime(2026, 8, 17, 16, 0)

    print("=" * 68)
    print("  JUAN — 7 anos, 2do grado, arranca de cero")
    print("=" * 68)
    print("\nSEIS SESIONES (el planificador decide que trabajar):\n")

    for _ in range(6):
        practicar(nino, grafo, ahora, aciertos=7)
        ahora += timedelta(days=3)

    dominadas = sum(1 for r in nino.dominio.values() if esta_dominada(r, ahora))
    print(f"\n   Dominadas: {dominadas} de {len(grafo)} habilidades del grafo")

    print("\n" + "-" * 68)
    print("  PASAN 70 DIAS DE VACACIONES")
    print("-" * 68 + "\n")

    ahora += timedelta(days=70)
    print("   Como decae lo aprendido:\n")
    for hid, registro in list(nino.dominio.items())[:4]:
        nombre = grafo.habilidad(hid).nombre.es
        print(f"   {nombre:34} {registro.nivel:.2f}  ->  {nivel_efectivo(registro, ahora):.2f}")

    repasos = habilidades_para_repasar(nino, grafo, ahora)
    print(f"\n   Necesitan repaso: {len(repasos)}")

    proximo = siguiente_habilidad(nino, grafo, ahora)
    if proximo:
        print(f"   El planificador elige: {proximo.nombre.es}   <- repaso, no avance")

    print("\n" + "-" * 68)
    print("  LO QUE ENTRA AL PROMPT DEL TUTOR")
    print("-" * 68 + "\n")

    nino.perfil.intereses = ["futbol", "dinosaurios"]
    nino.perfil.motivadores = ["competir contra el reloj"]
    nino.perfil.estilo_comunicacion = "directo, sin vueltas"
    nino.perfil.madurez_vinculo = 6

    for linea in resumen_para_prompt(nino, grafo, ahora).splitlines():
        print(f"   {linea}")
    print()


if __name__ == "__main__":
    main()
