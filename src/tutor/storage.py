"""Persistencia — "el mesero".

Todo acceso a datos pasa por la interfaz `Repositorio`. El resto de la app nunca
sabe si los datos vienen de un archivo, de SQLite o de un servidor.

El día que haya servidor (necesario para las tiendas), se escribe una nueva
implementación de esta interfaz y no se toca nada más.

Reparto de responsabilidades — ver ARCHITECTURE.md §8:
  · SQLite (data/tutor.db) → ficha del niño, sesiones. Escritura concurrente.
  · Archivos JSON          → transcripciones, reportes. Append-only.
  · knowledge/ (git)       → currículum y prompts. NO pasa por acá.

La interfaz se mantiene chica: los métodos que se usan, no un ORM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from .models import Ejercicio, Nino, ReporteParaPapa, Sesion


class Repositorio(ABC):
    """Contrato de persistencia. Fase 3 implementa; fase 0 solo define."""

    # ── Niños ────────────────────────────────────────────────────────────────

    @abstractmethod
    def obtener_nino(self, nino_id: str) -> Nino | None: ...

    @abstractmethod
    def guardar_nino(self, nino: Nino) -> None:
        """Guarda la ficha completa (ambas mitades).

        Debe ser atómico: la sesión en vivo y el pipeline offline escriben la
        misma ficha. Sin atomicidad se pierde historial de aprendizaje en
        silencio — la razón por la que esto es SQLite y no un JSON.
        """

    # ── Sesiones ─────────────────────────────────────────────────────────────

    @abstractmethod
    def crear_sesion(self, sesion: Sesion) -> None: ...

    @abstractmethod
    def obtener_sesion(self, sesion_id: str) -> Sesion | None: ...

    @abstractmethod
    def actualizar_sesion(self, sesion: Sesion) -> None:
        """Se llama también A MITAD de sesión, no solo al final.

        Si cae el modelo de voz, el estado guardado permite reanudar sin que el
        niño pierda su trabajo.
        """

    @abstractmethod
    def sesiones_sin_analizar(self) -> list[Sesion]:
        """Cola del Analista.

        IDEMPOTENCIA: filtra por `analizada == False`. Una sesión nunca se
        procesa dos veces (evita doble conteo de dominio).
        """

    @abstractmethod
    def sesiones_de(self, nino_id: str, desde: datetime, hasta: datetime) -> list[Sesion]:
        """Insumo del reporte semanal."""

    # ── Banco de ejercicios ──────────────────────────────────────────────────

    @abstractmethod
    def ejercicios_de(
        self, habilidad_id: str, limite: int = 15, tema: str | None = None
    ) -> list[Ejercicio]:
        """Precarga al INICIO de la sesión, nunca durante.

        Durante la sesión, `get_next_problem` saca de memoria: ~0ms.
        Solo devuelve ejercicios con `validado == True`.
        """

    @abstractmethod
    def guardar_ejercicios(self, ejercicios: list[Ejercicio]) -> None:
        """Escribe el banco. Lo llama scripts/build_exercise_bank.py."""

    # ── Transcripciones (archivos) ───────────────────────────────────────────

    @abstractmethod
    def guardar_transcripcion(self, sesion_id: str, contenido: str) -> None: ...

    @abstractmethod
    def obtener_transcripcion(self, sesion_id: str) -> str | None:
        """Insumo del Analista. Puede no existir si ya pasó la retención."""

    @abstractmethod
    def borrar_transcripciones_anteriores_a(self, fecha: datetime) -> int:
        """Política de retención de datos de menores (Ley 1581 CO / COPPA US).

        El activo es la ficha estructurada, no la conversación cruda. Una vez que
        el Analista extrajo las señales, la transcripción ya cumplió su función.

        Devuelve cuántas borró.
        """

    # ── Reportes ─────────────────────────────────────────────────────────────

    @abstractmethod
    def guardar_reporte(self, reporte: ReporteParaPapa) -> None: ...


class RepositorioSQLite(Repositorio):
    """Implementación por defecto: SQLite + archivos JSON.

    SQLite NO es un servidor — es un archivo. Sin proceso, sin Docker, sin
    connection string. Se copia, se versiona, se borra como cualquier archivo.

    Fase 3 implementa estos métodos.
    """

    def __init__(self, ruta_db: Path, ruta_datos: Path) -> None:
        self.ruta_db = ruta_db
        self.ruta_datos = ruta_datos

    # Fase 3: implementar. El contrato de arriba es la especificación.
    def obtener_nino(self, nino_id: str) -> Nino | None:
        raise NotImplementedError

    def guardar_nino(self, nino: Nino) -> None:
        raise NotImplementedError

    def crear_sesion(self, sesion: Sesion) -> None:
        raise NotImplementedError

    def obtener_sesion(self, sesion_id: str) -> Sesion | None:
        raise NotImplementedError

    def actualizar_sesion(self, sesion: Sesion) -> None:
        raise NotImplementedError

    def sesiones_sin_analizar(self) -> list[Sesion]:
        raise NotImplementedError

    def sesiones_de(self, nino_id: str, desde: datetime, hasta: datetime) -> list[Sesion]:
        raise NotImplementedError

    def ejercicios_de(
        self, habilidad_id: str, limite: int = 15, tema: str | None = None
    ) -> list[Ejercicio]:
        raise NotImplementedError

    def guardar_ejercicios(self, ejercicios: list[Ejercicio]) -> None:
        raise NotImplementedError

    def guardar_transcripcion(self, sesion_id: str, contenido: str) -> None:
        raise NotImplementedError

    def obtener_transcripcion(self, sesion_id: str) -> str | None:
        raise NotImplementedError

    def borrar_transcripciones_anteriores_a(self, fecha: datetime) -> int:
        raise NotImplementedError

    def guardar_reporte(self, reporte: ReporteParaPapa) -> None:
        raise NotImplementedError
