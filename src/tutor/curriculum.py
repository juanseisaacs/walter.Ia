"""El mapa: carga, valida y navega el grafo de habilidades.

Módulo PURO — sin red. Solo lee los YAML del repo.

El grafo es estático y compartido por todos los niños. Las decisiones por niño
viven en pedagogy.py.

FILOSOFÍA DE ERRORES: un grafo inválido no debe poder cargarse. Falla ruidosa y
temprana, al arrancar — no seis meses después con un niño trabado sin
explicación. Por eso el validador rechaza ciclos, prerrequisitos inexistentes e
IDs duplicados, y dice exactamente dónde está el problema.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from .config import CURRICULUM
from .models import Habilidad, Materia


class ErrorGrafo(Exception):
    """El grafo del currículum es inválido. Nunca se carga a medias."""


# ─────────────────────────────────────────────────────────────────────────────
# Carga y validación
# ─────────────────────────────────────────────────────────────────────────────


def _validador_de_esquema(directorio: Path) -> Draft202012Validator:
    esquema = json.loads((directorio / "schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(esquema)


def _leer_archivo(ruta: Path, validador: Draft202012Validator) -> list[Habilidad]:
    """Lee un YAML de currículum y valida cada nodo contra schema.json."""
    contenido = yaml.safe_load(ruta.read_text(encoding="utf-8")) or []

    if not isinstance(contenido, list):
        raise ErrorGrafo(f"{ruta.name}: se esperaba una lista de habilidades")

    habilidades: list[Habilidad] = []
    for i, nodo in enumerate(contenido):
        errores = sorted(validador.iter_errors(nodo), key=lambda e: e.path)
        if errores:
            detalle = "; ".join(
                f"{'.'.join(str(p) for p in e.path) or '(raíz)'}: {e.message}" for e in errores
            )
            nombre = nodo.get("id", f"posición {i}") if isinstance(nodo, dict) else f"posición {i}"
            raise ErrorGrafo(f"{ruta.name} · {nombre} → {detalle}")
        habilidades.append(Habilidad.model_validate(nodo))

    return habilidades


def _detectar_ciclo(habilidades: dict[str, Habilidad]) -> list[str] | None:
    """DFS con tres estados. Devuelve el ciclo encontrado, o None.

    Un ciclo (A necesita B, B necesita A) haría que ningún niño pudiera empezar
    nunca por esa rama. Es un callejón sin salida, no un error cosmético.
    """
    SIN_VISITAR, EN_CAMINO, LISTO = 0, 1, 2
    estado = dict.fromkeys(habilidades, SIN_VISITAR)
    camino: list[str] = []

    def visitar(hid: str) -> list[str] | None:
        estado[hid] = EN_CAMINO
        camino.append(hid)

        for prereq in habilidades[hid].prerequisitos:
            if estado.get(prereq) == EN_CAMINO:
                # Cerramos el ciclo: desde donde apareció hasta acá
                return camino[camino.index(prereq) :] + [prereq]
            if estado.get(prereq) == SIN_VISITAR:
                if ciclo := visitar(prereq):
                    return ciclo

        camino.pop()
        estado[hid] = LISTO
        return None

    for hid in habilidades:
        if estado[hid] == SIN_VISITAR:
            if ciclo := visitar(hid):
                return ciclo
    return None


def _validar_integridad(habilidades: list[Habilidad]) -> dict[str, Habilidad]:
    """IDs únicos, prerrequisitos existentes, sin ciclos."""
    indice: dict[str, Habilidad] = {}
    for h in habilidades:
        if h.id in indice:
            raise ErrorGrafo(f"ID duplicado: '{h.id}'")
        indice[h.id] = h

    for h in habilidades:
        for prereq in h.prerequisitos:
            if prereq not in indice:
                raise ErrorGrafo(f"'{h.id}' declara el prerrequisito '{prereq}', que no existe")

    if ciclo := _detectar_ciclo(indice):
        raise ErrorGrafo("Ciclo de prerrequisitos: " + " → ".join(ciclo))

    return indice


# ─────────────────────────────────────────────────────────────────────────────
# El grafo
# ─────────────────────────────────────────────────────────────────────────────


class GrafoHabilidades:
    """El mapa completo. Inmutable una vez cargado y validado."""

    def __init__(self, habilidades: list[Habilidad]) -> None:
        self._nodos = _validar_integridad(habilidades)

        # Índice inverso: qué habilita cada nodo. Se calcula una vez.
        self._desbloquea: dict[str, list[str]] = {hid: [] for hid in self._nodos}
        for h in habilidades:
            for prereq in h.prerequisitos:
                self._desbloquea[prereq].append(h.id)

    # ── Acceso ───────────────────────────────────────────────────────────────

    def habilidad(self, habilidad_id: str) -> Habilidad:
        if habilidad_id not in self._nodos:
            raise ErrorGrafo(f"No existe la habilidad '{habilidad_id}'")
        return self._nodos[habilidad_id]

    def existe(self, habilidad_id: str) -> bool:
        return habilidad_id in self._nodos

    # ── Navegación ───────────────────────────────────────────────────────────

    def prerequisitos_de(self, habilidad_id: str) -> list[Habilidad]:
        """Dependencias directas: qué hay que dominar antes de esto."""
        return [self._nodos[p] for p in self.habilidad(habilidad_id).prerequisitos]

    def desbloqueadas_por(self, habilidad_id: str) -> list[Habilidad]:
        """Qué habilita dominar esto. La flecha al revés."""
        self.habilidad(habilidad_id)  # valida que exista
        return [self._nodos[h] for h in self._desbloquea[habilidad_id]]

    def raices(self) -> list[Habilidad]:
        """Nodos sin prerrequisitos: por donde puede arrancar un niño nuevo."""
        return [h for h in self._nodos.values() if not h.prerequisitos]

    # ── Filtros ──────────────────────────────────────────────────────────────

    def por_materia(self, materia: Materia) -> list[Habilidad]:
        return [h for h in self._nodos.values() if h.materia == materia]

    def por_grado(self, grado: int) -> list[Habilidad]:
        return [h for h in self._nodos.values() if h.grado_sugerido == grado]

    # ── Protocolo ────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._nodos)

    def __contains__(self, habilidad_id: object) -> bool:
        return habilidad_id in self._nodos

    def __iter__(self):
        return iter(self._nodos.values())


def cargar_grafo(directorio: Path | None = None) -> GrafoHabilidades:
    """Lee todos los *.yaml de knowledge/curriculum/ y arma el grafo.

    Falla ruidosamente si algo está mal. No devuelve un grafo a medias.
    """
    directorio = directorio or CURRICULUM

    if not directorio.is_dir():
        raise ErrorGrafo(f"No existe el directorio de currículum: {directorio}")

    validador = _validador_de_esquema(directorio)

    habilidades: list[Habilidad] = []
    archivos = sorted(directorio.glob("*.yaml")) + sorted(directorio.glob("*.yml"))
    for ruta in archivos:
        habilidades.extend(_leer_archivo(ruta, validador))

    if not habilidades:
        raise ErrorGrafo(f"No se encontró ninguna habilidad en {directorio}")

    return GrafoHabilidades(habilidades)
