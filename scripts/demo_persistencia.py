"""Demo: el ciclo completo con persistencia real.

Prueba que el aprendizaje del niño sobrevive a que se apague el programa —que es
todo el punto de la memoria longitudinal (criterio #3 de YC).

    python -m scripts.demo_persistencia
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from tutor.curriculum import cargar_grafo
from tutor.models import EstadoSesion, ModoSesion, Nino, RegistroDominio, Sesion
from tutor.pedagogy import (
    actualizar_dominio,
    adelanto,
    esta_dominada,
    resumen_para_prompt,
    siguiente_habilidad,
)
from tutor.storage import RepositorioSQLite


def sesion_de_tutoria(repo, grafo, nino_id: str, sesion_id: str, cuando: datetime) -> None:
    """Una sesión completa: abrir, practicar, cerrar, persistir."""
    nino = repo.obtener_nino(nino_id)

    objetivo = siguiente_habilidad(nino, grafo, cuando)
    if objetivo is None:
        print("   (ya domina todo el grafo)")
        return

    sesion = Sesion(id=sesion_id, nino_id=nino_id, modo=ModoSesion.GUIADO, inicio=cuando)
    repo.crear_sesion(sesion)

    registro = nino.dominio.get(objetivo.id) or RegistroDominio(habilidad_id=objetivo.id)
    for _ in range(7):
        registro = actualizar_dominio(registro, acerto=True, ahora=cuando)
    nino.dominio[objetivo.id] = registro

    sesion.estado = EstadoSesion.COMPLETADA
    sesion.fin = cuando + timedelta(minutes=25)
    sesion.habilidades_trabajadas = [objetivo.id]
    sesion.tokens_consumidos = 3800

    repo.guardar_nino(nino)
    repo.actualizar_sesion(sesion)
    repo.guardar_transcripcion(sesion_id, f"Tutor y nino trabajaron {objetivo.nombre.es}.")

    marca = "DOMINADA" if esta_dominada(registro, cuando) else "en progreso"
    print(f"   {cuando:%d/%m}  {objetivo.nombre.es:34} [{marca}]")


def main() -> None:
    grafo = cargar_grafo()

    with tempfile.TemporaryDirectory() as tmp:
        datos = Path(tmp)
        cuando = datetime(2026, 8, 17, 16, 0)

        print("=" * 70)
        print("  PRIMERA CORRIDA DEL PROGRAMA")
        print("=" * 70 + "\n")

        repo = RepositorioSQLite(datos / "tutor.db", datos)
        repo.guardar_nino(Nino(id="n1", nombre="Sofia", edad=7, grado=2, creado_en=cuando))
        print("   Sofia dada de alta. Arranca de cero.\n")

        for i in range(8):
            sesion_de_tutoria(repo, grafo, "n1", f"s{i}", cuando)
            cuando += timedelta(days=3)

        print("\n   Cola del Analista: "
              f"{len(repo.sesiones_sin_analizar())} sesiones sin procesar")

        print("\n" + "=" * 70)
        print("  SE APAGA EL PROGRAMA")
        print("=" * 70)
        del repo

        print("\n" + "=" * 70)
        print("  SEGUNDA CORRIDA — se abre la misma base")
        print("=" * 70 + "\n")

        repo = RepositorioSQLite(datos / "tutor.db", datos)
        sofia = repo.obtener_nino("n1")

        dominadas = [h for h, r in sofia.dominio.items() if esta_dominada(r, cuando)]
        print(f"   Sofia sigue ahi: {sofia.nombre}, {sofia.edad} anos")
        print(f"   Habilidades dominadas: {len(dominadas)}")
        print(f"   Adelanto sobre su grado: +{adelanto(sofia, grafo, cuando)}")

        proximo = siguiente_habilidad(sofia, grafo, cuando)
        print(f"   Retoma exactamente donde quedo: {proximo.nombre.es}")

        print("\n   Lo que ve el tutor al reabrir:\n")
        for linea in resumen_para_prompt(sofia, grafo, cuando).splitlines():
            print(f"      {linea}")

        print("\n" + "-" * 70)
        print("  RETENCION DE DATOS DE MENORES")
        print("-" * 70 + "\n")

        antes = len(list(repo.ruta_transcripciones.glob("*.txt")))
        borradas = repo.borrar_transcripciones_anteriores_a(cuando - timedelta(days=15))
        despues = len(list(repo.ruta_transcripciones.glob("*.txt")))

        print(f"   Transcripciones antes:   {antes}")
        print(f"   Borradas (>15 dias):     {borradas}")
        print(f"   Quedan:                  {despues}")

        sofia = repo.obtener_nino("n1")
        intactas = len([h for h, r in sofia.dominio.items() if esta_dominada(r, cuando)])
        print(f"\n   Habilidades dominadas tras el borrado: {intactas}  <- la ficha NO se toca")
        print("   Se borro la conversacion, no lo aprendido.\n")


if __name__ == "__main__":
    main()
