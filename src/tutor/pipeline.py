"""Agentes offline. Latencia irrelevante por definición.

Cada agente es tres cosas: un prompt en knowledge/prompts/, un esquema de
salida, y una llamada. No hay loop agéntico ni tool use acá — son funciones
puras: entra texto, sale JSON. Ver ARCHITECTURE.md §2.

Los prompts son DATOS: cambiar el comportamiento de un agente edita un .md, no
este archivo.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, TypeVar

from pydantic import BaseModel

from . import config as cfg
from .curriculum import GrafoHabilidades
from .models import (
    AnalisisSesion,
    AuditoriaCumplimiento,
    EvaluacionSeguridad,
    MetricasReporte,
    Nino,
    NivelSeguridad,
    Observacion,
    PerfilPersonal,
    ReporteParaPapa,
    Sesion,
    TipoObservacion,
)
from .pedagogy import (
    actualizar_dominio,
    adelanto,
    esta_dominada,
    grado_de_trabajo,
)
from .storage import Repositorio
from .voice import cargar_prompt

T = TypeVar("T", bound=BaseModel)

MAX_ITEMS_PERFIL = 6
"""Tope por lista de la ficha personal. Consolidar, no acumular: una ficha con
cien intereses no describe a nadie."""


# ─────────────────────────────────────────────────────────────────────────────
# Frontera con el modelo
# ─────────────────────────────────────────────────────────────────────────────


class ClienteLLM(ABC):
    """Aislado para poder testear sin API key y sin red."""

    @abstractmethod
    def extraer(self, modelo: str, sistema: str, mensaje: str, formato: type[T]) -> T:
        """Salida estructurada, validada contra el esquema."""

    @abstractmethod
    def redactar(self, modelo: str, sistema: str, mensaje: str) -> str:
        """Prosa libre."""


class ClienteAnthropic(ClienteLLM):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ValueError("Falta ANTHROPIC_API_KEY")
        self._cliente = None

    def _obtener(self):
        if self._cliente is None:
            import anthropic  # import perezoso: los módulos puros no lo cargan

            self._cliente = anthropic.Anthropic(api_key=self._api_key)
        return self._cliente

    def extraer(self, modelo: str, sistema: str, mensaje: str, formato: type[T]) -> T:
        respuesta = self._obtener().messages.parse(
            model=modelo,
            max_tokens=4096,
            system=sistema,
            messages=[{"role": "user", "content": mensaje}],
            output_format=formato,
        )
        if respuesta.parsed_output is None:
            raise RuntimeError(f"El modelo no devolvió {formato.__name__} válido")
        return respuesta.parsed_output

    def redactar(self, modelo: str, sistema: str, mensaje: str) -> str:
        respuesta = self._obtener().messages.create(
            model=modelo,
            max_tokens=4096,
            system=sistema,
            messages=[{"role": "user", "content": mensaje}],
        )
        return "".join(b.text for b in respuesta.content if b.type == "text")


class ClienteFalso(ClienteLLM):
    """Devuelve respuestas guionadas. Para tests y para desarrollar sin llave."""

    def __init__(
        self, estructurado: BaseModel | None = None, texto: str = "Reporte de prueba."
    ) -> None:
        self.estructurado = estructurado
        self.texto = texto
        self.llamadas: list[dict] = []

    def extraer(self, modelo: str, sistema: str, mensaje: str, formato: type[T]) -> T:
        self.llamadas.append({"modelo": modelo, "sistema": sistema, "mensaje": mensaje})
        if self.estructurado is None:
            raise RuntimeError("ClienteFalso sin respuesta configurada")
        return self.estructurado  # type: ignore[return-value]

    def redactar(self, modelo: str, sistema: str, mensaje: str) -> str:
        self.llamadas.append({"modelo": modelo, "sistema": sistema, "mensaje": mensaje})
        return self.texto


def cliente_por_defecto() -> ClienteLLM:
    """Anthropic si hay llave; falso si no. Permite desarrollar sin API key."""
    return ClienteAnthropic() if os.getenv("ANTHROPIC_API_KEY") else ClienteFalso()


# ─────────────────────────────────────────────────────────────────────────────
# Agente: Analista de sesión  (100% de las sesiones)
# ─────────────────────────────────────────────────────────────────────────────


class _SalidaAnalista(BaseModel):
    """Lo que se le pide al modelo. `AnalisisSesion` agrega el id de sesión."""

    observaciones: list[Observacion] = []
    perfil_sugerido: PerfilPersonal | None = None
    cumplimiento: AuditoriaCumplimiento
    resumen: str | None = None


def _contexto_habilidades(sesion: Sesion, grafo: GrafoHabilidades | None) -> str:
    """Las habilidades trabajadas, con nombre, para que el Analista pueda ATAR
    cada observación académica a un id.

    La transcripción no contiene ids de nodo; sin esta lista el modelo devuelve
    `habilidad_id=None` y `aplicar_analisis` descarta la observación en silencio.
    Es DATO (cambia por sesión), por eso va en el mensaje y no en el prompt.
    """
    if grafo is None or not sesion.habilidades_trabajadas:
        return ""
    lineas = [
        f"- {hid}: {grafo.habilidad(hid).nombre.es}"
        for hid in sesion.habilidades_trabajadas
        if grafo.existe(hid)
    ]
    if not lineas:
        return ""
    return (
        "\n\n--- HABILIDADES TRABAJADAS EN ESTA SESIÓN ---\n"
        "Toda observación académica (acierto, error, pista_necesaria, dominio) DEBE\n"
        "llevar el habilidad_id de una de estas. Las de perfil (frustracion, interes)\n"
        "van sin habilidad_id.\n" + "\n".join(lineas)
    )


def analizar_sesion(
    sesion: Sesion,
    transcripcion: str,
    cliente: ClienteLLM | None = None,
    grafo: GrafoHabilidades | None = None,
) -> AnalisisSesion:
    """Una llamada, dos preguntas sobre la misma transcripción.

    Fusionar señales del niño con auditoría del tutor subió la cobertura del
    método socrático de un muestreo del 10% al 100%, al mismo costo.

    `grafo` habilita atar cada observación académica a un `habilidad_id`: sin él
    las señales del niño no llegan nunca a la tabla `dominio`.

    IDEMPOTENCIA: el llamador filtra por `analizada == False`. Esta función no
    conoce ese estado — no la llames dos veces sobre la misma sesión.
    """
    cliente = cliente or cliente_por_defecto()
    mensaje = (
        f"Sesión {sesion.id} (modo {sesion.modo.value}).\n\n"
        f"--- TRANSCRIPCIÓN ---\n{transcripcion}"
        f"{_contexto_habilidades(sesion, grafo)}"
    )
    salida = cliente.extraer(
        cfg.MODELO_ANALISTA,
        cargar_prompt("session_analyst"),
        mensaje,
        _SalidaAnalista,
    )
    return AnalisisSesion(sesion_id=sesion.id, **salida.model_dump())


def _consolidar(previos: list[str], nuevos: list[str]) -> list[str]:
    """Suma sin duplicar y con techo. Consolidar, no acumular."""
    vistos = {p.lower().strip(): p for p in previos}
    for n in nuevos:
        if (clave := n.lower().strip()) and clave not in vistos:
            vistos[clave] = n
    return list(vistos.values())[:MAX_ITEMS_PERFIL]


def aplicar_analisis(
    nino: Nino, analisis: AnalisisSesion, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> Nino:
    """Cierra el circuito adaptativo: lo observado entra en la ficha.

    La mitad académica la recalcula `pedagogy` (código determinístico).
    La mitad personal se consolida.
    """
    ahora = ahora or datetime.now()
    actualizado = nino.model_copy(deep=True)

    # ── Mitad académica ──
    exitos = {TipoObservacion.ACIERTO, TipoObservacion.DOMINIO}
    for obs in analisis.observaciones:
        if obs.habilidad_id is None or not grafo.existe(obs.habilidad_id):
            continue
        if obs.tipo not in exitos and obs.tipo != TipoObservacion.ERROR:
            continue

        registro = actualizado.dominio.get(obs.habilidad_id)
        if registro is None:
            from .models import RegistroDominio

            registro = RegistroDominio(habilidad_id=obs.habilidad_id)

        pistas = sum(
            1
            for o in analisis.observaciones
            if o.habilidad_id == obs.habilidad_id
            and o.tipo == TipoObservacion.PISTA_NECESARIA
        )
        actualizado.dominio[obs.habilidad_id] = actualizar_dominio(
            registro, acerto=obs.tipo in exitos, pistas_usadas=pistas, ahora=ahora
        )

    # ── Mitad personal ──
    if (sugerido := analisis.perfil_sugerido) is not None:
        p = actualizado.perfil
        p.intereses = _consolidar(p.intereses, sugerido.intereses)
        p.motivadores = _consolidar(p.motivadores, sugerido.motivadores)
        p.frustraciones = _consolidar(p.frustraciones, sugerido.frustraciones)
        if sugerido.estilo_comunicacion:
            p.estilo_comunicacion = sugerido.estilo_comunicacion
        if sugerido.notas:
            p.notas = sugerido.notas

    # Cada sesión el tutor lo conoce un poco más.
    actualizado.perfil.madurez_vinculo += 1
    return actualizado


# ─────────────────────────────────────────────────────────────────────────────
# Procesador de la cola: cierra el circuito de punta a punta
# ─────────────────────────────────────────────────────────────────────────────
# `session.cerrar()` sólo ENCOLA (deja `analizada=False`). Acá se drena la cola:
# por cada sesión, el Analista lee la transcripción y `aplicar_analisis` escribe
# el dominio. Sin este eslabón la tabla `dominio` nunca crece y el planificador
# vuelve a arrancar a ciegas cada día. Es offline: la latencia da igual (§2).


def procesar_sesion(
    repo: Repositorio,
    grafo: GrafoHabilidades,
    sesion: Sesion,
    cliente: ClienteLLM | None = None,
    ahora: datetime | None = None,
) -> bool:
    """Analiza UNA sesión y persiste lo aprendido. Devuelve si la sacó de la cola.

    IDEMPOTENCIA: si ya está analizada, no hace nada. El circuito se cierra en dos
    escrituras atómicas — la ficha del niño y el flag de la sesión.

    La saca de la cola aunque no haya nada que analizar (niño borrado, o la
    transcripción ya pasó la retención): reintentar no cambiaría el resultado y
    una sesión sin insumo la reprocesaría en cada corrida para siempre.
    """
    if sesion.analizada:
        return False

    nino = repo.obtener_nino(sesion.nino_id)
    transcripcion = repo.obtener_transcripcion(sesion.id)

    if nino is not None and transcripcion:
        analisis = analizar_sesion(sesion, transcripcion, cliente, grafo)
        repo.guardar_nino(aplicar_analisis(nino, analisis, grafo, ahora))
        # El veredicto del método queda persistido para el panel del papá: es la
        # evidencia durable de "no le doy las respuestas", y sobrevive al borrado
        # de la transcripción (son booleanos, no la charla cruda).
        repo.guardar_auditoria(sesion.id, analisis.cumplimiento)

    sesion.analizada = True
    repo.actualizar_sesion(sesion)
    return True


def procesar_pendientes(
    repo: Repositorio,
    grafo: GrafoHabilidades,
    cliente: ClienteLLM | None = None,
    ahora: datetime | None = None,
) -> int:
    """Drena la cola del Analista. Devuelve cuántas sesiones procesó.

    Self-healing: recoge todo lo que quedó pendiente (una corrida sin llave, un
    cierre que no disparó el fondo). Lo usa el backfill y sirve de tarea periódica.
    """
    cliente = cliente or cliente_por_defecto()
    procesadas = 0
    for sesion in repo.sesiones_sin_analizar():
        if procesar_sesion(repo, grafo, sesion, cliente, ahora):
            procesadas += 1
    return procesadas


# ─────────────────────────────────────────────────────────────────────────────
# Agente: Vigilante  (en vivo, en paralelo)
# ─────────────────────────────────────────────────────────────────────────────


def evaluar_seguridad(
    turnos: list[tuple[str, str]], cliente: ClienteLLM | None = None
) -> EvaluacionSeguridad:
    """Clasifica una ventana de turnos. Contexto limpio: sin persona, sin
    historia, sin relación afectiva — por eso no es manipulable.

    Se invoca desde session.py EN PARALELO. Si falla, el tutor sigue hablando:
    la seguridad no puede ser un cuello de botella.
    """
    cliente = cliente or cliente_por_defecto()
    ventana = "\n".join(f"{quien}: {texto}" for quien, texto in turnos)
    try:
        return cliente.extraer(
            cfg.MODELO_VIGILANTE,
            cargar_prompt("vigilante"),
            f"--- VENTANA ---\n{ventana}",
            EvaluacionSeguridad,
        )
    except Exception:
        # Falla cerrada hacia lo seguro: no bloquea, pero tampoco afirma que
        # todo está bien cuando no pudo mirar.
        return EvaluacionSeguridad(
            nivel=NivelSeguridad.ATENCION,
            categoria="vigilante_no_disponible",
            requiere_escalamiento=False,
        )


def vigilante_para_sesion(cliente: ClienteLLM | None = None):
    """Adapta `evaluar_seguridad` a la firma que espera `session.Orquestador`."""

    def evaluar(turnos) -> EvaluacionSeguridad:
        return evaluar_seguridad([(t.quien, t.texto) for t in turnos], cliente)

    return evaluar


# ─────────────────────────────────────────────────────────────────────────────
# Agente: Compañero del Papá
# ─────────────────────────────────────────────────────────────────────────────


def calcular_metricas(
    nino: Nino,
    sesiones: list[Sesion],
    analisis: list[AnalisisSesion],
    grafo: GrafoHabilidades,
    ahora: datetime | None = None,
) -> MetricasReporte:
    """Los HECHOS, en código. El agente redacta a partir de esto y no puede
    afirmar nada que no esté acá."""
    ahora = ahora or datetime.now()

    minutos = sum(
        int((s.fin - s.inicio).total_seconds() // 60) for s in sesiones if s.fin is not None
    )
    cumplidas = sum(
        1 for a in analisis if not a.cumplimiento.regalo_la_respuesta
    )

    dominadas, en_progreso = [], []
    for hid, registro in nino.dominio.items():
        if not grafo.existe(hid):
            continue
        nombre = grafo.habilidad(hid).nombre.es
        (dominadas if esta_dominada(registro, ahora) else en_progreso).append(nombre)

    return MetricasReporte(
        sesiones=len(sesiones),
        minutos_totales=minutos,
        habilidades_dominadas=sorted(dominadas),
        habilidades_en_progreso=sorted(en_progreso),
        cumplimiento_metodo=(cumplidas / len(analisis)) if analisis else 1.0,
        grado_de_trabajo=grado_de_trabajo(nino, grafo, ahora),
        adelanto_grados=adelanto(nino, grafo, ahora),
    )


def generar_reporte(
    nino: Nino,
    metricas: MetricasReporte,
    desde: datetime,
    hasta: datetime,
    cliente: ClienteLLM | None = None,
) -> ReporteParaPapa:
    """Modo reporte del Compañero del Papá. Solo redacta: los hechos ya vienen."""
    cliente = cliente or cliente_por_defecto()

    contexto = [
        f"Niño: {nino.nombre}, {nino.edad} años, {nino.grado}° grado.",
        f"Sesiones en el período: {metricas.sesiones}",
        f"Minutos totales: {metricas.minutos_totales}",
        f"Ya domina: {', '.join(metricas.habilidades_dominadas) or 'nada todavía'}",
        f"Está trabajando: {', '.join(metricas.habilidades_en_progreso) or '—'}",
        f"Método socrático sostenido en: {metricas.cumplimiento_metodo:.0%} de las sesiones",
        f"Grado de trabajo real: {metricas.grado_de_trabajo}°",
        f"Adelanto sobre su grado: {metricas.adelanto_grados:+d}",
    ]
    if nino.perfil.intereses:
        contexto.append(f"Le interesa: {', '.join(nino.perfil.intereses)}")

    contenido = cliente.redactar(
        cfg.MODELO_COMPANERO_PAPA,
        cargar_prompt("parent_companion"),
        "--- DATOS DEL PERÍODO ---\n" + "\n".join(contexto),
    )
    return ReporteParaPapa(
        nino_id=nino.id, desde=desde, hasta=hasta, metricas=metricas, contenido=contenido
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agente: Compañero del Papá — modo entrevista (onboarding)
# ─────────────────────────────────────────────────────────────────────────────
# Resuelve el arranque en frío: sin esto, la primera sesión es a ciegas.
#
# Dos piezas con responsabilidades separadas:
#   · el EXTRACTOR decide si ya alcanza (completitud)
#   · el CONVERSADOR decide qué preguntar (tono)
# Así ninguna tiene que hacer bien las dos cosas a la vez.


class FichaInicial(BaseModel):
    """Lo que se saca de la entrevista. Todo opcional: se llena de a poco."""

    email_papa: str | None = None
    nombre_nino: str | None = None
    edad: int | None = None
    grado: int | None = None

    intereses: list[str] = []
    dificultades: list[str] = []
    motivadores: list[str] = []
    estilo_comunicacion: str | None = None
    notas: str | None = None

    OBLIGATORIOS: ClassVar[tuple[str, ...]] = ("email_papa", "nombre_nino", "edad", "grado")

    def falta(self) -> list[str]:
        """Sin estos cuatro el sistema no arranca — y una alerta no le llega
        a nadie."""
        return [campo for campo in self.OBLIGATORIOS if getattr(self, campo) is None]

    @property
    def completa(self) -> bool:
        return not self.falta()


def _historial_a_texto(historial: list[tuple[str, str]]) -> str:
    return "\n".join(f"{quien}: {texto}" for quien, texto in historial)


def extraer_ficha(
    historial: list[tuple[str, str]], cliente: ClienteLLM | None = None
) -> FichaInicial:
    """Lee la conversación y saca los datos. No inventa: lo que no se dijo
    queda en None."""
    cliente = cliente or cliente_por_defecto()
    return cliente.extraer(
        cfg.MODELO_ANALISTA,  # extracción estructurada: alcanza con el barato
        "Extraés datos de una conversación entre un asesor y el padre de un "
        "niño de primaria. Solo lo que se dijo explícitamente: si un dato no "
        "aparece, dejalo vacío. No infieras ni completes.",
        f"--- CONVERSACIÓN ---\n{_historial_a_texto(historial)}",
        FichaInicial,
    )


def siguiente_pregunta(
    historial: list[tuple[str, str]],
    ficha: FichaInicial,
    cliente: ClienteLLM | None = None,
) -> str:
    """El turno del entrevistador. Sonnet: acá la calidez es el producto."""
    cliente = cliente or cliente_por_defecto()

    if ficha.completa:
        pendiente = (
            "Ya tenés todo lo necesario. Cerrá la conversación: decile en dos "
            "frases qué entendiste de su hijo, con lo que él te contó, y que ya "
            "pueden empezar. No preguntes nada más."
        )
    else:
        pendiente = "Todavía te falta: " + ", ".join(ficha.falta()) + ". Una pregunta por vez."

    conversacion = _historial_a_texto(historial) if historial else "(todavía no empezó)"
    return cliente.redactar(
        cfg.MODELO_COMPANERO_PAPA,
        cargar_prompt("parent_interview"),
        f"--- CONVERSACIÓN HASTA AHORA ---\n{conversacion}\n\n--- ESTADO ---\n{pendiente}",
    )


def crear_nino_desde_ficha(ficha: FichaInicial, nino_id: str) -> Nino:
    """Convierte la entrevista en la ficha del niño.

    La mitad académica arranca vacía a propósito: lo que el papá cree que su
    hijo sabe no es dato. El dominio se mide en las primeras sesiones — por eso
    las primeras son exploratorias.
    """
    if not ficha.completa:
        raise ValueError(f"Faltan datos obligatorios: {', '.join(ficha.falta())}")

    return Nino(
        id=nino_id,
        nombre=ficha.nombre_nino,
        edad=ficha.edad,
        grado=ficha.grado,
        email_papa=ficha.email_papa,
        perfil=PerfilPersonal(
            intereses=ficha.intereses[:MAX_ITEMS_PERFIL],
            motivadores=ficha.motivadores[:MAX_ITEMS_PERFIL],
            frustraciones=ficha.dificultades[:MAX_ITEMS_PERFIL],
            estilo_comunicacion=ficha.estilo_comunicacion,
            notas=ficha.notas,
            madurez_vinculo=0,  # el tutor todavía no lo conoce: se lo contaron
        ),
        creado_en=datetime.now(),
    )


def verificar_reporte(reporte: ReporteParaPapa) -> list[str]:
    """CÓDIGO, no modelo. Chequea que los números del texto coincidan con la
    fuente. Devuelve los problemas encontrados (vacío = todo bien).

    Un reporte inflado es peor que ninguno: el papá habla con su hijo y se da
    cuenta. Y ahí perdió lo único que compró.
    """
    problemas = []
    texto = reporte.contenido
    m = reporte.metricas

    import re

    numeros = {int(n) for n in re.findall(r"\b\d+\b", texto)}

    # Un número de sesiones distinto al real, escrito en el texto, es inventado.
    plausibles = {
        m.sesiones,
        m.minutos_totales,
        m.grado_de_trabajo,
        len(m.habilidades_dominadas),
        len(m.habilidades_en_progreso),
        round(m.cumplimiento_metodo * 100),
        reporte.desde.day,
        reporte.hasta.day,
    }
    for n in numeros:
        if n not in plausibles and n > 1:
            problemas.append(f"número '{n}' no aparece en las métricas")

    if m.adelanto_grados >= 1 and "adelant" not in texto.lower():
        problemas.append("va adelantado y el reporte no lo menciona")

    return problemas
