"""Orquestador de la sesión en vivo.

El audio NO pasa por acá (ver ARCHITECTURE.md §10): el navegador habla directo
con Gemini. Este módulo es el plano de CONTROL — prepara todo antes de que el
niño hable, y recibe lo que pasó mientras hablaba.

Los tres candados del §10 viven acá:
  1. La configuración se ata al token  -> `abrir()`
  2. Reportar es necesario para recargar ejercicios -> `registrar_turnos()`
  3. El presupuesto se chequea al abrir -> `_verificar_presupuesto()`
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel, Field

from . import config as cfg
from .curriculum import GrafoHabilidades
from .models import (
    Ejercicio,
    EstadoSesion,
    EvaluacionSeguridad,
    Habilidad,
    ModoSesion,
    Nino,
    NivelSeguridad,
    Sesion,
)
from .pedagogy import resumen_para_prompt, siguiente_habilidad
from .storage import Repositorio
from .tools import BancoDeSesion
from .voice import (
    ConfiguracionSesion,
    DeteccionFinTurno,
    EmisorDeTokens,
    construir_instruccion_sistema,
    deteccion_para_edad,
)


class ErrorSesion(Exception):
    """No se puede abrir o continuar la sesión."""


class ErrorPresupuesto(ErrorSesion):
    """Se alcanzó un tope de uso. No es un fallo: es el sistema protegiéndose."""


# ─────────────────────────────────────────────────────────────────────────────
# Prefiltro de seguridad — en código, 0ms, corre en CADA turno
# ─────────────────────────────────────────────────────────────────────────────
# Primer nivel de los dos. Cubre lo evidente al instante; el Vigilante (LLM)
# cubre lo sutil, en paralelo y sobre una ventana de turnos.

# OJO: los patrones van SIN ACENTOS — el texto se normaliza antes de comparar.
# Un patrón con tilde nunca engancha. Ya pasó una vez.
_SENALES_CRITICAS = [
    r"\bme (pega|pegan|pego)\b",
    r"\bme (lastim|golpe|grit)\w*",
    r"\bno quiero (vivir|estar aca|estar aqui|seguir)\b",
    r"\bme quiero (morir|matar|lastimar)\b",
    r"\btengo (miedo|hambre)\b",
    r"\bestoy solo\b.*\bnoche\b",
    r"\bno le (digas|cuentes) a nadie\b",
    r"\bes un secreto\b",
    r"\bme toc(a|o|an)\b",
]

_PATRONES = [re.compile(p, re.IGNORECASE) for p in _SENALES_CRITICAS]


def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def prefiltro_seguridad(texto: str) -> str | None:
    """Detección instantánea de señales evidentes. Devuelve el patrón que saltó.

    No reemplaza al Vigilante: lo antecede. Un string match no entiende
    contexto, pero cuesta 0ms y no puede fallar por red.
    """
    limpio = _sin_acentos(texto)
    for patron in _PATRONES:
        if patron.search(limpio):
            return patron.pattern
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Piezas de la sesión
# ─────────────────────────────────────────────────────────────────────────────


class Turno(BaseModel):
    """Un intercambio transcripto. Lo reporta el navegador."""

    quien: str = Field(description="nino | tutor")
    texto: str
    momento: datetime | None = None


class SesionAbierta(BaseModel):
    """Lo que recibe el navegador para conectarse.

    Va el TOKEN, no la configuración: el navegador no puede cambiar la persona,
    el playbook ni la política de seguridad (candado #1).
    """

    sesion_id: str
    token: str
    modelo: str
    deteccion: DeteccionFinTurno
    habilidad_id: str
    habilidad_nombre: str
    ejercicios: list[Ejercicio]


# Firma del Vigilante. Se inyecta para que session.py no dependa de pipeline.py
# ni de la red. En tests se pasa uno falso.
EvaluadorSeguridad = Callable[[list[Turno]], EvaluacionSeguridad]


# ─────────────────────────────────────────────────────────────────────────────
# Orquestador
# ─────────────────────────────────────────────────────────────────────────────


class Orquestador:
    """Abre, alimenta y cierra sesiones. No toca audio."""

    def __init__(
        self,
        repo: Repositorio,
        grafo: GrafoHabilidades,
        emisor: EmisorDeTokens,
        vigilante: EvaluadorSeguridad | None = None,
    ) -> None:
        self.repo = repo
        self.grafo = grafo
        self.emisor = emisor
        self.vigilante = vigilante

        # Estado en memoria de las sesiones vivas.
        self._bancos: dict[str, BancoDeSesion] = {}
        self._turnos: dict[str, list[Turno]] = {}
        self._alertas: dict[str, list[EvaluacionSeguridad]] = {}
        self._reportado_desde_recarga: dict[str, int] = {}

    # ── Abrir ────────────────────────────────────────────────────────────────

    def abrir(
        self, nino_id: str, modo: ModoSesion = ModoSesion.GUIADO, ahora: datetime | None = None
    ) -> SesionAbierta:
        """Todo el trabajo pesado ANTES de que el niño hable.

        Durante la sesión no se piensa: se ejecuta (ARCHITECTURE.md §9).
        """
        ahora = ahora or datetime.now()

        nino = self.repo.obtener_nino(nino_id)
        if nino is None:
            raise ErrorSesion(f"No existe el niño '{nino_id}'")

        self._verificar_presupuesto(nino_id, ahora)

        objetivo = siguiente_habilidad(nino, self.grafo, ahora)
        if objetivo is None:
            raise ErrorSesion(
                "El niño domina todo el grafo alcanzable. Hay que extender el currículum."
            )

        ejercicios = self._precargar(nino, objetivo)

        sesion = Sesion(
            id=f"ses_{uuid4().hex[:12]}", nino_id=nino_id, modo=modo, inicio=ahora
        )
        self.repo.crear_sesion(sesion)

        configuracion = ConfiguracionSesion(
            instruccion_sistema=construir_instruccion_sistema(
                resumen_para_prompt(nino, self.grafo, ahora), modo.value, nino.idioma
            ),
            deteccion=deteccion_para_edad(nino.edad),
        )
        token = self.emisor.emitir(configuracion)

        self._bancos[sesion.id] = BancoDeSesion(ejercicios)
        self._turnos[sesion.id] = []
        self._alertas[sesion.id] = []
        self._reportado_desde_recarga[sesion.id] = 0

        return SesionAbierta(
            sesion_id=sesion.id,
            token=token.token,
            modelo=token.modelo,
            deteccion=configuracion.deteccion,
            habilidad_id=objetivo.id,
            habilidad_nombre=objetivo.nombre.es,
            ejercicios=ejercicios,
        )

    def _precargar(self, nino: Nino, objetivo: Habilidad) -> list[Ejercicio]:
        """Ejercicios a memoria. Se prefieren los temáticos si sabemos qué le gusta."""
        tema = nino.perfil.intereses[0] if nino.perfil.intereses else None
        ejercicios: list[Ejercicio] = []
        if tema:
            ejercicios = self.repo.ejercicios_de(
                objetivo.id, cfg.EJERCICIOS_A_PRECARGAR, tema=tema
            )
        if len(ejercicios) < cfg.EJERCICIOS_A_PRECARGAR:
            faltan = cfg.EJERCICIOS_A_PRECARGAR - len(ejercicios)
            vistos = {e.id for e in ejercicios}
            ejercicios += [
                e for e in self.repo.ejercicios_de(objetivo.id, faltan) if e.id not in vistos
            ]
        return ejercicios

    def _verificar_presupuesto(self, nino_id: str, ahora: datetime) -> None:
        """CANDADO #3. Cada apertura pasa por acá.

        Se cobra suscripción fija: sin techo, el costo por niño es ilimitado.
        """
        inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

        # Solo cuentan las sesiones donde el nino REALMENTE trabajo. Una que se
        # abrio y se corto -sin internet, un boton tocado sin querer- no puede
        # quemarle un cupo del dia a un chico que no aprendio nada.
        usadas = [
            s
            for s in self.repo.sesiones_de(nino_id, inicio_dia, ahora)
            if s.habilidades_trabajadas
        ]

        if len(usadas) >= cfg.MAX_SESIONES_DIA:
            raise ErrorPresupuesto(
                f"Ya hizo {len(usadas)} sesiones hoy (tope: {cfg.MAX_SESIONES_DIA})."
            )

    # ── Durante ──────────────────────────────────────────────────────────────

    def registrar_turnos(self, sesion_id: str, turnos: list[Turno]) -> list[EvaluacionSeguridad]:
        """CANDADO #2. El navegador reporta lo que pasó.

        Persiste a mitad de sesión (si se cae la voz, no se pierde el trabajo) y
        dispara la seguridad. Reportar habilita recargar ejercicios.
        """
        if sesion_id not in self._turnos:
            raise ErrorSesion(f"Sesión '{sesion_id}' no está abierta")

        self._turnos[sesion_id].extend(turnos)
        self._reportado_desde_recarga[sesion_id] += len(turnos)
        self.repo.guardar_transcripcion(sesion_id, self._transcribir(sesion_id))

        alertas: list[EvaluacionSeguridad] = []

        # Nivel 1: prefiltro en código, 0ms, cada turno del niño.
        for turno in turnos:
            if turno.quien != "nino":
                continue
            if (patron := prefiltro_seguridad(turno.texto)) is not None:
                alertas.append(
                    EvaluacionSeguridad(
                        nivel=NivelSeguridad.CRITICO,
                        categoria="prefiltro",
                        evidencia=turno.texto,
                        requiere_escalamiento=True,
                    )
                )
                del patron

        # Nivel 2: Vigilante sobre una VENTANA. Nunca bloquea al tutor: el
        # llamador lo corre en paralelo.
        historial = self._turnos[sesion_id]
        if self.vigilante and len(historial) >= cfg.VENTANA_VIGILANTE:
            ventana = historial[-cfg.VENTANA_VIGILANTE :]
            evaluacion = self.vigilante(ventana)
            if evaluacion.nivel != NivelSeguridad.OK:
                alertas.append(evaluacion)

        self._alertas[sesion_id].extend(alertas)
        return alertas

    def recargar_ejercicios(self, sesion_id: str) -> list[Ejercicio]:
        """Solo recarga si hubo reporte desde la última vez.

        Un cliente que deja de reportar se queda sin ejercicios. No es
        vigilancia: el reporte es parte de cómo funciona.
        """
        if sesion_id not in self._bancos:
            raise ErrorSesion(f"Sesión '{sesion_id}' no está abierta")
        if self._reportado_desde_recarga.get(sesion_id, 0) == 0:
            raise ErrorSesion("No hay turnos nuevos reportados desde la última recarga.")

        sesion = self.repo.obtener_sesion(sesion_id)
        nino = self.repo.obtener_nino(sesion.nino_id)
        objetivo = siguiente_habilidad(nino, self.grafo)
        nuevos = self._precargar(nino, objetivo) if objetivo else []

        self._bancos[sesion_id] = BancoDeSesion(nuevos)
        self._reportado_desde_recarga[sesion_id] = 0
        return nuevos

    def banco(self, sesion_id: str) -> BancoDeSesion:
        if sesion_id not in self._bancos:
            raise ErrorSesion(f"Sesión '{sesion_id}' no está abierta")
        return self._bancos[sesion_id]

    def excedio_duracion(self, sesion_id: str, ahora: datetime | None = None) -> bool:
        sesion = self.repo.obtener_sesion(sesion_id)
        if sesion is None:
            return False
        limite = sesion.inicio + timedelta(minutes=cfg.MAX_MINUTOS_SESION)
        return (ahora or datetime.now()) > limite

    # ── Cerrar ───────────────────────────────────────────────────────────────

    def cerrar(
        self,
        sesion_id: str,
        ahora: datetime | None = None,
        interrumpida: bool = False,
        tokens_consumidos: int = 0,
    ) -> Sesion:
        """Persiste y encola para el Analista. `analizada` queda en False."""
        sesion = self.repo.obtener_sesion(sesion_id)
        if sesion is None:
            raise ErrorSesion(f"No existe la sesión '{sesion_id}'")

        sesion.fin = ahora or datetime.now()
        sesion.estado = EstadoSesion.INTERRUMPIDA if interrumpida else EstadoSesion.COMPLETADA
        sesion.tokens_consumidos = tokens_consumidos

        banco = self._bancos.get(sesion_id)
        if banco and banco.entregados:
            sesion.habilidades_trabajadas = sorted(
                {e.habilidad_id for e in banco.entregados}
            )

        self.repo.guardar_transcripcion(sesion_id, self._transcribir(sesion_id))
        self.repo.actualizar_sesion(sesion)
        self._olvidar(sesion_id)
        return sesion

    def reanudar(self, sesion_id: str) -> SesionAbierta:
        """Retoma una sesión interrumpida sin que el niño pierda su trabajo."""
        sesion = self.repo.obtener_sesion(sesion_id)
        if sesion is None:
            raise ErrorSesion(f"No existe la sesión '{sesion_id}'")
        if sesion.estado != EstadoSesion.INTERRUMPIDA:
            raise ErrorSesion("Solo se reanudan sesiones interrumpidas")

        abierta = self.abrir(sesion.nino_id, sesion.modo)
        sesion.estado = EstadoSesion.COMPLETADA
        self.repo.actualizar_sesion(sesion)
        return abierta

    # ── Internos ─────────────────────────────────────────────────────────────

    def _transcribir(self, sesion_id: str) -> str:
        return "\n".join(
            f"{t.quien}: {t.texto}" for t in self._turnos.get(sesion_id, [])
        )

    def _olvidar(self, sesion_id: str) -> None:
        for estado in (self._bancos, self._turnos, self._alertas, self._reportado_desde_recarga):
            estado.pop(sesion_id, None)
