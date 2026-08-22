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
from .pedagogy import habilidades_disponibles, resumen_para_prompt, siguiente_habilidad
from .storage import Repositorio
from .tools import BancoDeSesion
from .voice import (
    ConfiguracionSesion,
    DeteccionFinTurno,
    EmisorDeTokens,
    construir_instruccion_sistema,
    deteccion_para_edad,
    instruccion_de_apertura,
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
GRACIA_CLIENTE_VIVO_SEG = 90
"""Sin señales por más de esto, se asume que del otro lado ya no hay nadie.

Holgado a propósito: el precio de equivocarse es asimétrico. Dejar viva una
sesión de más cuesta un lugar del cupo; cerrar una que el niño está usando le
corta la conversación y borra lo que dijo."""

VENTANA_SESIONES_HUERFANAS_DIAS = 1
"""Hasta dónde mirar atrás buscando sesiones que quedaron ACTIVA.

Una sesión activa de ayer no es una sesión: es basura que dejó un backend que
se cayó. Un día alcanza para barrerla sin recorrer la historia entera del niño
en cada arranque."""


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

    apertura: str = ""
    """El turno que el navegador manda apenas conecta, para que hable el TUTOR.

    Es una instrucción interna, no algo que el niño oiga: el modelo la lee y
    contesta en audio con su saludo. Distinta el primer día (se presenta) que
    los siguientes (lo saluda por su nombre y propone por dónde seguir).

    Viaja desde acá y no está escrita en el navegador por la misma razón que el
    resto del prompt: cambiar cómo saluda el tutor no puede pedir un build del
    front. El texto vive en `knowledge/prompts/apertura*.md`."""

    max_tokens: int = cfg.MAX_TOKENS_SESION
    """El techo de gasto, que hasta ahora solo conocía el backend.

    Se verificaba al ABRIR y nunca durante: una sesión podía pasarse y nadie la
    paraba. El navegador es el único que ve el consumo en vivo (Gemini se lo
    manda en cada mensaje), así que es el único que puede cortar a tiempo —
    pero no puede respetar un límite que no conoce."""

    avisar_tokens: int = int(cfg.MAX_TOKENS_SESION * 0.9)
    """Desde acá se le pide al tutor que vaya cerrando.

    Cortar seco a un niño a mitad de una explicación es la peor forma de
    terminar. Con el 10% que queda alcanza para despedirse bien."""

    max_minutos: int = cfg.MAX_MINUTOS_SESION
    """El otro techo, que estaba en la misma situación que el de tokens.

    `excedio_duracion()` existía desde la fase 5, con test propio, y no la
    llamaba NADIE: ni la API, ni el navegador. Un tope que nadie consulta no es
    un tope. Va acá por la misma razón que `max_tokens` — el navegador es el que
    puede cerrar a tiempo, y no puede respetar un límite que no conoce."""

    avisar_minutos: int = int(cfg.MAX_MINUTOS_SESION * 0.9)
    """Mismo criterio que `avisar_tokens`: primero avisar, después cortar."""


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
        self._ultima_actividad: dict[str, datetime] = {}

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

        self._cerrar_sesiones_activas(nino_id, ahora)
        self._verificar_presupuesto(nino_id, ahora)

        objetivo = siguiente_habilidad(nino, self.grafo, ahora)
        if objetivo is None:
            raise ErrorSesion(
                "El niño domina todo el grafo alcanzable. Hay que extender el currículum."
            )

        ejercicios = self._precargar(nino, objetivo, ahora)

        sesion = Sesion(
            id=f"ses_{uuid4().hex[:12]}", nino_id=nino_id, modo=modo, inicio=ahora
        )
        self.repo.crear_sesion(sesion)

        # El banco se arma ANTES del prompt: el tutor tiene que saber qué temas
        # tiene en la mano, o no puede ofrecerlos ni pedirlos, y termina
        # inventando ejercicios.
        banco = BancoDeSesion(ejercicios, principal=objetivo.id)

        # `madurez_vinculo` sube en cada sesión analizada: en cero significa que
        # todavía no se conocen. Decide dos cosas distintas — qué instrucciones
        # lleva el prompt, y con qué frase abre la boca el tutor.
        primer_encuentro = nino.perfil.madurez_vinculo == 0

        configuracion = ConfiguracionSesion(
            instruccion_sistema=construir_instruccion_sistema(
                resumen_para_prompt(nino, self.grafo, ahora),
                modo.value,
                nino.idioma,
                temas=self._temas_para_prompt(banco),
                tema_principal=objetivo.id,
                primer_encuentro=primer_encuentro,
            ),
            deteccion=deteccion_para_edad(nino.edad),
        )
        token = self.emisor.emitir(configuracion)

        self._bancos[sesion.id] = banco
        self._turnos[sesion.id] = []
        self._alertas[sesion.id] = []
        self._reportado_desde_recarga[sesion.id] = 0
        self._ultima_actividad[sesion.id] = ahora

        return SesionAbierta(
            sesion_id=sesion.id,
            token=token.token,
            modelo=token.modelo,
            deteccion=configuracion.deteccion,
            habilidad_id=objetivo.id,
            habilidad_nombre=objetivo.nombre.es,
            ejercicios=ejercicios,
            apertura=instruccion_de_apertura(primer_encuentro),
        )

    def _precargar(
        self, nino: Nino, objetivo: Habilidad, ahora: datetime | None = None
    ) -> list[Ejercicio]:
        """Ejercicios a memoria: la habilidad del día MÁS las vecinas.

        Las vecinas son la frontera del niño — lo que ya puede aprender. Van
        pocas de cada una y sirven para una sola cosa: que cuando diga "mejor
        hagamos restas" el tutor tenga restas de verdad a mano.

        Hasta el 18/08 se precargaba solo el objetivo. El niño pidió cambiar de
        tema, el tutor no tenía nada, improvisó, y esa sesión no escribió
        dominio (ver `BancoDeSesion`). Los ejercicios de resta existían en la
        base; nunca se cargaron.

        Sigue siendo trabajo previo: al abrir se sabe todo lo que se va a
        necesitar y durante la sesión no se consulta la base (§9).
        """
        ejercicios = self._de_una_habilidad(nino, objetivo.id, cfg.EJERCICIOS_A_PRECARGAR)

        vistos = {e.id for e in ejercicios}
        for vecina in habilidades_disponibles(nino, self.grafo, ahora):
            if vecina.id == objetivo.id:
                continue
            nuevos = [
                e
                for e in self._de_una_habilidad(nino, vecina.id, cfg.EJERCICIOS_POR_VECINA)
                if e.id not in vistos
            ]
            ejercicios += nuevos
            vistos.update(e.id for e in nuevos)

        return ejercicios

    def _temas_para_prompt(self, banco: BancoDeSesion) -> list[tuple[str, str]]:
        """(id, nombre humano) de lo que el banco tiene cargado.

        El id es la llave con la que el tutor pide; el nombre es lo que puede
        decir en voz alta. Un nodo que no esté en el grafo se descarta en vez de
        llegar al prompt con el id crudo — el niño no tiene por qué oír
        `mat.resta.sin_desagrupacion`.
        """
        temas = []
        for hid in banco.temas:
            if self.grafo.existe(hid):
                temas.append((hid, self.grafo.habilidad(hid).nombre.es))
        return temas

    def _de_una_habilidad(self, nino: Nino, habilidad_id: str, cuantos: int) -> list[Ejercicio]:
        """Se prefieren los temáticos si sabemos qué le gusta.

        Acá es donde el banco genérico se vuelve personal: el ejercicio está
        validado en código, pero el que llega es el que habla de dinosaurios.
        """
        tema = nino.perfil.intereses[0] if nino.perfil.intereses else None
        ejercicios: list[Ejercicio] = []
        if tema:
            ejercicios = self.repo.ejercicios_de(habilidad_id, cuantos, tema=tema)
        if len(ejercicios) < cuantos:
            faltan = cuantos - len(ejercicios)
            vistos = {e.id for e in ejercicios}
            ejercicios += [
                e for e in self.repo.ejercicios_de(habilidad_id, faltan) if e.id not in vistos
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
        self._ultima_actividad[sesion_id] = datetime.now()
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

    def recargar_ejercicios(
        self, sesion_id: str, ahora: datetime | None = None
    ) -> list[Ejercicio]:
        """Solo recarga si hubo reporte desde la última vez.

        Un cliente que deja de reportar se queda sin ejercicios. No es
        vigilancia: el reporte es parte de cómo funciona.
        """
        if sesion_id not in self._bancos:
            raise ErrorSesion(f"Sesión '{sesion_id}' no está abierta")
        if self._reportado_desde_recarga.get(sesion_id, 0) == 0:
            raise ErrorSesion("No hay turnos nuevos reportados desde la última recarga.")

        # El techo de duración, aplicado donde el candado #2 ya obliga a pasar.
        # No corta la charla a mitad de una frase —eso sería lo peor para el
        # niño— pero deja de darle material: sin ejercicios nuevos, la sesión
        # termina. Es la misma lógica del candado #2 con el reporte.
        if self.excedio_duracion(sesion_id, ahora):
            raise ErrorSesion(
                f"La sesión pasó los {cfg.MAX_MINUTOS_SESION} minutos: no se recarga más."
            )

        sesion = self.repo.obtener_sesion(sesion_id)
        nino = self.repo.obtener_nino(sesion.nino_id)
        objetivo = siguiente_habilidad(nino, self.grafo)
        nuevos = self._precargar(nino, objetivo) if objetivo else []

        self._bancos[sesion_id] = BancoDeSesion(
            nuevos, principal=objetivo.id if objetivo else None
        )
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

    def _cerrar_sesiones_activas(self, nino_id: str, ahora: datetime) -> list[str]:
        """Un niño no puede tener dos sesiones de voz a la vez.

        El candado vive acá y no en el navegador porque el navegador tiene
        demasiadas puertas: recargar la página, el hot-reload de Vite, dos
        pestañas abiertas, un doble clic. Cada una abre una conexión Live nueva
        y las viejas siguen hablando por los mismos parlantes — el niño oye dos
        tutores encima y el audio se traba. Se taparon de a una hasta que quedó
        claro que el candado estaba del lado que no controlamos.

        Lo vimos en la prueba del 18/08: tres POST /api/sesiones seguidos y una
        sola sesión con turnos. Las otras dos nunca se cerraron.

        **Gana la última.** Cerrar la previa y no rechazar la nueva: si se
        rechazara, recargar la página dejaría al niño sin poder empezar hasta
        que venciera algo que él no ve. Se marcan INTERRUMPIDA porque eso es lo
        que fueron — se les cayó el canal, aunque el motivo sea otra pestaña.

        `cerrar()` no encola al Analista (eso lo hace la API), así que limpiar
        una sesión fantasma no le manda basura.
        """
        desde = ahora - timedelta(days=VENTANA_SESIONES_HUERFANAS_DIAS)
        cerradas = []
        for previa in self.repo.sesiones_de(nino_id, desde, ahora):
            if previa.estado != EstadoSesion.ACTIVA:
                continue
            if self._tiene_cliente_vivo(previa.id, ahora):
                continue
            self.cerrar(previa.id, ahora=ahora, interrumpida=True)
            cerradas.append(previa.id)
        return cerradas

    def _tiene_cliente_vivo(self, sesion_id: str, ahora: datetime) -> bool:
        """¿Hay alguien del otro lado usando esta sesión ahora mismo?

        La primera versión del candado no preguntaba esto y cerraba cualquier
        sesión ACTIVA. El 18/08 a las 17:50 eso dejó a un niño hablando 99
        segundos contra una sesión muerta: 32 POST de turnos con 404, y
        `get_next_problem` también en 404, así que el tutor no pudo entregar un
        solo ejercicio y volvió a improvisar. La transcripción entera se perdió.

        El arreglo era pasarse de conservador. Dos sesiones vivas a la vez
        molestan y el lock entre pestañas ya las cubre; matar la que el niño
        está usando rompe la sesión completa y se lleva lo que dijo.

        Sin registro en memoria = sesión de un proceso anterior. Ahí no hay
        cliente que proteger: el navegador que la abrió ya no existe.
        """
        visto = self._ultima_actividad.get(sesion_id)
        if visto is None:
            return False
        return (ahora - visto) < timedelta(seconds=GRACIA_CLIENTE_VIVO_SEG)

    def _transcribir(self, sesion_id: str) -> str:
        return "\n".join(
            f"{t.quien}: {t.texto}" for t in self._turnos.get(sesion_id, [])
        )

    def _olvidar(self, sesion_id: str) -> None:
        for estado in (
            self._bancos,
            self._turnos,
            self._alertas,
            self._reportado_desde_recarga,
            self._ultima_actividad,
        ):
            estado.pop(sesion_id, None)
