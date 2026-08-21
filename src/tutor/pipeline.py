"""Agentes offline. Latencia irrelevante por definición.

Cada agente es tres cosas: un prompt en knowledge/prompts/, un esquema de
salida, y una llamada. No hay loop agéntico ni tool use acá — son funciones
puras: entra texto, sale JSON. Ver ARCHITECTURE.md §2.

Los prompts son DATOS: cambiar el comportamiento de un agente edita un .md, no
este archivo.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections import Counter
from datetime import datetime, timedelta
from enum import StrEnum
from typing import ClassVar, NamedTuple, TypeVar

from pydantic import BaseModel, ValidationError

from . import config as cfg
from .curriculum import GrafoHabilidades
from .models import (
    AnalisisSesion,
    AuditoriaCumplimiento,
    Calendario,
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

_log = logging.getLogger("tutor.pipeline")
"""Sin handler propio: la librería no decide dónde se imprime. Los scripts que
drenan la cola lo configuran; en los tests se captura con `caplog`."""

TEMPERATURA_EXTRACCION = 0.0
"""Extraer no es escribir. El Analista y el Vigilante leen una transcripción y
sacan lo que hay: no hay nada que ganar variando la respuesta, y sí mucho que
perder.

Corría con la temperatura por defecto (1.0) y se notaba: la misma transcripción
daba 0 observaciones en una corrida y 5 en la siguiente — con un eval en rojo y
la sesión del niño sin registrar, según el humor del muestreo. En seguridad es
peor todavía: dos corridas sobre los mismos turnos tienen que decidir lo mismo.

`redactar` NO lleva esto: ahí la prosa para el papá sí se beneficia de variar."""

MAX_TOKENS_EXTRACCION = 16_384
"""El techo de la salida estructurada, no del contexto.

Cuando la respuesta se pasa del techo, el JSON llega cortado a la mitad de una
cadena, Pydantic rechaza la respuesta **entera** y la sesión del niño queda sin
registrar. No hay degradación elegante: o entra todo, o no entra nada.

Se subió dos veces, las dos por verlo romper de verdad: de 4096 (cortó en la
columna 12471) a 8192 (cortó en la 20915, con un extractor que anotaba una señal
por turno). El margen siempre fue más chico de lo que parecía.

Es un agente offline: acá 16k no le cuesta latencia a nadie. Y el tope de
señales del prompt es lo que de verdad mantiene la salida corta — esto es la
red, no el plan."""

TEMPERATURA_PROSA = 1.0
"""Para lo que se lee como carta y no como dato. El reporte al papá viene en dos
campos (afirmaciones + sugerencia), o sea que sale por `extraer` — pero sigue
siendo prosa, y no queremos la misma carta calcada todas las semanas."""

_NOMBRE_TOOL_SALIDA = "responder"
"""La salida estructurada se pide como TOOL USE, no con `messages.parse`.

No es preferencia de estilo: es una diferencia medida, el 20/08, con el mismo
modelo, el mismo prompt y la misma transcripción (`ses_47dfebd9aa43`).

| Camino | Salida | Estabilidad a temperatura 0 |
|---|---|---|
| `messages.parse(output_format=…)` | 38.642 chars, **cortada** | fallaba |
| tool use + `tool_choice` forzado | 2.813 chars · 1.199 tokens | 3 corridas idénticas |

Con `parse` el modelo se iba de largo hasta agotar `max_tokens`, el JSON llegaba
partido a la mitad de una cadena, Pydantic lo rechazaba **entero** y la sesión
del niño quedaba sin registrar. Con tool use el esquema viaja como contrato de
la herramienta y el modelo lo llena y para.

Esto explica además la inestabilidad que se le venía achacando al modelo —
"la misma transcripción daba 0 observaciones en una corrida y 5 en la
siguiente". No era el muestreo: era este camino."""

MAX_ITEMS_PERFIL = 6
"""Tope por lista de la ficha personal. Consolidar, no acumular: una ficha con
cien intereses no describe a nadie."""


# ─────────────────────────────────────────────────────────────────────────────
# Frontera con el modelo
# ─────────────────────────────────────────────────────────────────────────────


class ClienteLLM(ABC):
    """Aislado para poder testear sin API key y sin red."""

    @abstractmethod
    def extraer(
        self,
        modelo: str,
        sistema: str,
        mensaje: str,
        formato: type[T],
        temperatura: float = TEMPERATURA_EXTRACCION,
    ) -> T:
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

    def extraer(
        self,
        modelo: str,
        sistema: str,
        mensaje: str,
        formato: type[T],
        temperatura: float = TEMPERATURA_EXTRACCION,
    ) -> T:
        respuesta = self._obtener().messages.create(
            model=modelo,
            max_tokens=MAX_TOKENS_EXTRACCION,
            temperature=temperatura,
            system=sistema,
            messages=[{"role": "user", "content": mensaje}],
            tools=[
                {
                    "name": _NOMBRE_TOOL_SALIDA,
                    "description": f"Devuelve el resultado como {formato.__name__}.",
                    "input_schema": formato.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": _NOMBRE_TOOL_SALIDA},
        )

        for bloque in respuesta.content:
            if bloque.type == "tool_use":
                return formato.model_validate(bloque.input)

        raise RuntimeError(
            f"El modelo no devolvió {formato.__name__} (stop_reason={respuesta.stop_reason})"
        )

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

    def extraer(
        self,
        modelo: str,
        sistema: str,
        mensaje: str,
        formato: type[T],
        temperatura: float = TEMPERATURA_EXTRACCION,
    ) -> T:
        self.llamadas.append({"modelo": modelo, "sistema": sistema, "mensaje": mensaje})
        if self.estructurado is None:
            raise RuntimeError("ClienteFalso sin respuesta configurada")
        if isinstance(self.estructurado, formato):
            return self.estructurado

        # El guion describe la sesión entera (`_SalidaAnalista`) pero acá se pide
        # una mitad: el Analista hace dos llamadas con formatos distintos. Se
        # recorta el guion en vez de obligar a cada test a escribir dos.
        for valor in vars(self.estructurado).values():
            if isinstance(valor, formato):
                return valor
        campos = self.estructurado.model_dump()
        recorte = {k: v for k, v in campos.items() if k in formato.model_fields}
        try:
            return formato.model_validate(recorte)
        except ValidationError as e:
            raise RuntimeError(
                f"ClienteFalso: el guion {type(self.estructurado).__name__} no "
                f"cubre {formato.__name__}. Configurá una respuesta para ese formato."
            ) from e

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
    """El análisis completo de una sesión. `AnalisisSesion` agrega el id.

    Ya NO se le pide entero al modelo en una sola llamada — se arma juntando
    `_SalidaExtractor` y `AuditoriaCumplimiento`. Sigue existiendo porque es el
    guion que usan los tests para describir una sesión de una sola vez.
    """

    observaciones: list[Observacion] = []
    perfil_sugerido: PerfilPersonal | None = None
    cumplimiento: AuditoriaCumplimiento
    resumen: str | None = None


class _SalidaExtractor(BaseModel):
    """La mitad que mira al NIÑO. Sin la auditoría, a propósito.

    Ver `analizar_sesion` para por qué están separadas.
    """

    observaciones: list[Observacion] = []
    perfil_sugerido: PerfilPersonal | None = None
    resumen: str | None = None


def _contexto_habilidades(sesion: Sesion, grafo: GrafoHabilidades | None) -> str:
    """Las habilidades trabajadas, con nombre, para que el Analista pueda ATAR
    cada observación académica a un id.

    La transcripción no contiene ids de nodo; sin esta lista el modelo devuelve
    `habilidad_id=None` y `aplicar_analisis` descarta la observación en silencio.
    Es DATO (cambia por sesión), por eso va en el mensaje y no en el prompt.

    **Cuando la sesión no pasó por el banco** —el niño llegó con su tarea y el
    tutor la trabajó sin pedir ejercicios— esto devolvía cadena vacía, y el
    modelo se quedaba sin una sola opción real. No devolvía `None`: **se
    inventaba un id plausible**. Verificado el 19/08 con la sesión
    `ses_60f5ee744aca`: el niño resolvió 56+38 llevando una decena y quedó
    grabado como `mat.suma.sin_reagrupacion`, que es justo lo que NO hizo. El id
    existía en el grafo, así que `aplicar_analisis` lo aceptó sin chistar y entró
    a la ficha del niño — camino directo al reporte del papá.

    Por eso, sin banco se ofrece el grafo entero como candidatos. No es lo mismo
    que adivinar: elegir de trece opciones con nombre es una lectura de la
    transcripción; inventar un id de la nada, no. Y sigue estando permitido
    dejarlo en `None` cuando la transcripción no alcanza.
    """
    if grafo is None:
        return ""

    if sesion.habilidades_trabajadas:
        lineas = [
            f"- {hid}: {grafo.habilidad(hid).nombre.es}"
            for hid in sesion.habilidades_trabajadas
            if grafo.existe(hid)
        ]
    else:
        return (
            "\n\n--- ESTA SESIÓN NO USÓ EL BANCO DE EJERCICIOS ---\n"
            "El tutor trabajó algo que trajo el niño: su tarea, una duda. Mira qué\n"
            "practicó de verdad —qué operación hizo, con qué números— y usa el id\n"
            "que le corresponde de esta lista. Es una lectura de la transcripción,\n"
            "no una adivinanza: 56+38 llevando una decena es suma con reagrupación.\n"
            "Deja `habilidad_id` en null solo si la transcripción no alcanza para\n"
            "decidir entre dos.\n"
            + "\n".join(f"- {h.id}: {h.nombre.es}" for h in grafo)
        )

    if not lineas:
        return ""

    # Con una sola habilidad no hay nada que elegir, y decirlo importa: el modelo
    # devolvía las cuatro señales bien tipadas y las cuatro con habilidad_id=None
    # — o sea, la sesión entera descartada por una ambigüedad que no existía.
    cierre = (
        f"\n\nEsta sesión trabajó UNA sola habilidad: toda observación académica "
        f"lleva `{sesion.habilidades_trabajadas[0]}`. No hay otra opción."
        if len(lineas) == 1
        else ""
    )
    return (
        "\n\n--- HABILIDADES TRABAJADAS EN ESTA SESIÓN ---\n"
        "Toda observación académica (acierto, error, pista_necesaria, dominio) DEBE\n"
        "llevar el habilidad_id de una de estas. Las de perfil (frustracion, interes)\n"
        "van sin habilidad_id.\n" + "\n".join(lineas) + cierre
    )


def analizar_sesion(
    sesion: Sesion,
    transcripcion: str,
    cliente: ClienteLLM | None = None,
    grafo: GrafoHabilidades | None = None,
) -> AnalisisSesion:
    """Dos llamadas sobre la misma transcripción: qué hizo el niño, qué hizo el tutor.

    **Por qué son dos y no una.** Estuvieron fusionadas, y medido en evals eso
    costaba caro: las dos mitades competían y la que perdía siempre era la
    extracción. Con el schema fusionado, `curriculum_fidelity` daba

        sin campos extra en la auditoría .......... 4/4
        + un campo trivial ........................ 3/4
        + un campo que exige juicio ............... 0/4

    y el síntoma era `observaciones: []` — o sea, el modelo entregaba la
    auditoría impecable y la sesión del niño sin registrar. Cada cosa que
    quisiéramos auditar de más se pagaba en dominio no anotado.

    Separadas, cada llamada tiene un solo trabajo y un prompt propio. Cuesta el
    doble de llamadas; es un agente offline, no le cuesta latencia a nadie.

    `grafo` habilita atar cada observación académica a un `habilidad_id`: sin él
    las señales del niño no llegan nunca a la tabla `dominio`. El auditor no lo
    necesita — no mira habilidades, mira al tutor.

    IDEMPOTENCIA: el llamador filtra por `analizada == False`. Esta función no
    conoce ese estado — no la llames dos veces sobre la misma sesión.
    """
    cliente = cliente or cliente_por_defecto()
    encabezado = (
        f"Sesión {sesion.id} (modo {sesion.modo.value})."
        f"\n\n--- TRANSCRIPCIÓN ---\n{transcripcion}"
    )

    señales = cliente.extraer(
        cfg.MODELO_ANALISTA,
        cargar_prompt("session_analyst"),
        encabezado + _contexto_habilidades(sesion, grafo),
        _SalidaExtractor,
    )
    cumplimiento = cliente.extraer(
        cfg.MODELO_ANALISTA,
        cargar_prompt("method_auditor"),
        encabezado,
        AuditoriaCumplimiento,
    )
    datos = señales.model_dump()
    datos["observaciones"] = _atar_habilidad_unica(datos["observaciones"], sesion, grafo)
    return AnalisisSesion(sesion_id=sesion.id, cumplimiento=cumplimiento, **datos)


_TIPOS_ACADEMICOS = frozenset(
    {
        TipoObservacion.ACIERTO,
        TipoObservacion.ERROR,
        TipoObservacion.PISTA_NECESARIA,
        TipoObservacion.DOMINIO,
    }
)


def _atar_habilidad_unica(
    observaciones: list[dict], sesion: Sesion, grafo: GrafoHabilidades | None = None
) -> list[dict]:
    """Rellena el `habilidad_id` que el modelo omitió, cuando no hay ambigüedad.

    Si la sesión trabajó UNA sola habilidad, toda señal académica es de esa
    habilidad por construcción — el banco entregó ejercicios de un solo nodo. No
    es inferir: es un dato que el código ya tiene y el modelo estaba adivinando.

    Y adivinaba mal de forma intermitente. Con la misma transcripción y
    temperatura 0, `curriculum_fidelity` daba 4/4, 3/4, 2/4, 3/4 en corridas
    seguidas: el modelo devolvía las señales bien tipadas y con la cita correcta,
    pero la mitad de las veces dejaba `habilidad_id` en null — y una observación
    académica sin id la descarta `aplicar_analisis` en silencio. O sea: el niño
    practicaba y su dominio no subía, según el humor del muestreo.

    Con dos o más habilidades no se toca nada: ahí sí hay algo que decidir, y
    esa decisión es del modelo, que leyó la transcripción.

    Un id INVENTADO se corrige igual que un id ausente, y por la misma razón.
    El modelo devuelve a veces un nodo que no está en el grafo (`mat.sumas_dobles`
    en vez de `mat.suma.llevando`): `aplicar_analisis` lo descartaba igual que al
    null, con la diferencia de que este ni siquiera parecía un hueco. Si la
    sesión trabajó un solo nodo no hay nada que decidir — reescribirlo no es
    adivinar, es usar el dato que el código ya tenía. Pide `grafo` para saber
    qué id es falso; sin grafo se comporta como antes.
    """
    if len(sesion.habilidades_trabajadas) != 1:
        return observaciones
    unica = sesion.habilidades_trabajadas[0]
    if grafo is not None and not grafo.existe(unica):
        return observaciones  # el dato del código tampoco sirve: no se toca nada
    for o in observaciones:
        if o.get("tipo") not in _TIPOS_ACADEMICOS:
            continue
        hid = o.get("habilidad_id")
        if hid is None or (grafo is not None and not grafo.existe(hid)):
            o["habilidad_id"] = unica
    return observaciones


# ─────────────────────────────────────────────────────────────────────────────
# Que el descarte deje rastro
# ─────────────────────────────────────────────────────────────────────────────
# Hasta el 21/08 una señal académica sin `habilidad_id` —o con uno inventado—
# se caía por un `continue` mudo dentro de `aplicar_analisis`. El niño
# practicaba, su dominio no subía, y no había dónde enterarse: ni excepción, ni
# contador, ni línea de log. Se descubrió leyendo la base a mano.
#
# La cura no es adivinar el id que falta (eso sería inventar dato, y el proyecto
# tiene una regla dura en contra). Es que la pérdida SE VEA.


class DestinoSenal(StrEnum):
    """Qué se hizo con una observación del Analista.

    Existe porque tres de estas ramas eran el mismo `continue` anónimo. Ponerle
    nombre a cada salida es lo que convierte una pérdida muda en una contable.
    """

    DOMINIO = "dominio"
    """Movió la tabla `dominio`: acierto, error o dominio con id válido."""

    PISTA = "pista"
    """`pista_necesaria` con id válido. No mueve el nivel por sí sola — se
    cuenta como pistas dentro del cálculo. Entró: no es pérdida."""

    PERFIL = "perfil"
    """Interés o frustración. Va a la ficha personal por otra rama, no acá."""

    SIN_ID = "sin_id"
    """PERDIDA. Académica y el modelo no dijo de qué habilidad."""

    ID_DESCONOCIDO = "id_desconocido"
    """PERDIDA. El id que devolvió el modelo no está en el grafo."""


_MUEVEN_DOMINIO = frozenset(
    {TipoObservacion.ACIERTO, TipoObservacion.DOMINIO, TipoObservacion.ERROR}
)


def _destino(obs: Observacion, grafo: GrafoHabilidades) -> DestinoSenal:
    """La única regla de qué entra a `dominio` y qué no.

    `aplicar_analisis` decide con esto y `clasificar_senales` cuenta con esto:
    una sola fuente, para que el informe no pueda contradecir a lo que el código
    de verdad hizo. Es la lección de la fase 4 —dos definiciones del mismo
    concepto se separan sin que nadie avise— aplicada por adelantado.
    """
    if obs.tipo not in _TIPOS_ACADEMICOS:
        return DestinoSenal.PERFIL
    if obs.habilidad_id is None:
        return DestinoSenal.SIN_ID
    if not grafo.existe(obs.habilidad_id):
        return DestinoSenal.ID_DESCONOCIDO
    return DestinoSenal.DOMINIO if obs.tipo in _MUEVEN_DOMINIO else DestinoSenal.PISTA


class SenalesDeLaSesion(NamedTuple):
    """Qué entró en la ficha y qué se cayó por el camino, en números."""

    dominio: int = 0
    pistas: int = 0
    perfil: int = 0
    sin_id: int = 0
    ids_desconocidos: tuple[str, ...] = ()

    @property
    def aplicadas(self) -> int:
        return self.dominio + self.pistas

    @property
    def perdidas(self) -> int:
        return self.sin_id + len(self.ids_desconocidos)

    def diagnostico(self) -> str:
        """Una línea legible para la consola y el log, sin abrir el código."""
        partes = [f"{self.aplicadas} aplicada(s)"]
        if self.sin_id:
            partes.append(f"{self.sin_id} sin habilidad_id")
        if self.ids_desconocidos:
            partes.append("id inexistente: " + ", ".join(self.ids_desconocidos))
        if self.perfil:
            partes.append(f"{self.perfil} al perfil")
        return " · ".join(partes)


def clasificar_senales(analisis: AnalisisSesion, grafo: GrafoHabilidades) -> SenalesDeLaSesion:
    """Cuenta lo mismo que `aplicar_analisis` va a hacer, antes de hacerlo.

    Función pura: no toca la ficha ni la base. Sirve para avisar en el momento
    y para auditar sesiones viejas sin volver a llamar al modelo.
    """
    destinos = [(_destino(o, grafo), o) for o in analisis.observaciones]
    conteo = Counter(d for d, _ in destinos)
    desconocidos = sorted(
        {o.habilidad_id for d, o in destinos if d is DestinoSenal.ID_DESCONOCIDO and o.habilidad_id}
    )
    return SenalesDeLaSesion(
        dominio=conteo[DestinoSenal.DOMINIO],
        pistas=conteo[DestinoSenal.PISTA],
        perfil=conteo[DestinoSenal.PERFIL],
        sin_id=conteo[DestinoSenal.SIN_ID],
        ids_desconocidos=tuple(desconocidos),
    )


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
    # El filtro vive en `_destino`, no acá: lo que se descarta hay que poder
    # contarlo desde afuera (`clasificar_senales`) sin re-implementar la regla.
    exitos = {TipoObservacion.ACIERTO, TipoObservacion.DOMINIO}
    for obs in analisis.observaciones:
        if _destino(obs, grafo) is not DestinoSenal.DOMINIO:
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
        p.datos_suyos = _consolidar(p.datos_suyos, sugerido.datos_suyos)
        p.intereses = _consolidar(p.intereses, sugerido.intereses)
        p.motivadores = _consolidar(p.motivadores, sugerido.motivadores)
        p.frustraciones = _consolidar(p.frustraciones, sugerido.frustraciones)
        if sugerido.estilo_comunicacion:
            p.estilo_comunicacion = sugerido.estilo_comunicacion
        if sugerido.notas:
            p.notas = sugerido.notas
        if sugerido.contexto_escolar:
            p.contexto_escolar = sugerido.contexto_escolar

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


def _avisar_de_las_senales(sesion: Sesion, senales: SenalesDeLaSesion) -> None:
    """Deja constancia de lo que entró y de lo que se perdió.

    A nivel WARNING lo perdido, a nivel INFO lo normal: quien drena la cola ve
    el detalle, y quien solo mira los avisos ve exactamente los casos en que el
    niño trabajó y su dominio no se movió.

    No lanza ni corta: una señal perdida no es motivo para descartar la sesión
    entera, que es la mitad del análisis que sí sirve.
    """
    nivel = logging.WARNING if senales.perdidas else logging.INFO
    _log.log(nivel, "sesión %s: %s", sesion.id, senales.diagnostico())

    if not sesion.habilidades_trabajadas:
        # El caso de `ses_cdb0b7fae50f`: el niño eligió escribir la w, trabajó
        # nueve turnos y la sesión cerró sin un solo nodo del grafo. El Analista
        # hizo bien en no inventar una habilidad; lo que faltaba era que alguien
        # se enterara de que esos tokens no le llegan al papá en ningún reporte.
        _log.warning(
            "sesión %s: cerró sin habilidades trabajadas — %d tokens sin registro de dominio",
            sesion.id,
            sesion.tokens_consumidos,
        )


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
        _avisar_de_las_senales(sesion, clasificar_senales(analisis, grafo))
        repo.guardar_nino(aplicar_analisis(nino, analisis, grafo, ahora))
        # El veredicto del método queda persistido para el panel del papá: es la
        # evidencia durable de "no le doy las respuestas", y sobrevive al borrado
        # de la transcripción (son booleanos, no la charla cruda).
        repo.guardar_auditoria(sesion.id, analisis.cumplimiento)
    else:
        # También era mudo: la sesión salía de la cola sin dejar constancia de
        # que se fue sin analizar. Se distingue de "analizada y vacía".
        _log.warning(
            "sesión %s: sin insumo (niño borrado o transcripción vencida) — "
            "sale de la cola sin analizar",
            sesion.id,
        )

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
    cumplimientos: list[AuditoriaCumplimiento],
    grafo: GrafoHabilidades,
    ahora: datetime | None = None,
) -> MetricasReporte:
    """Los HECHOS, en código. El agente redacta a partir de esto y no puede
    afirmar nada que no esté acá.

    Recibe los VEREDICTOS, no los análisis completos: el análisis es efímero
    (vive lo que dura la llamada), pero la auditoría queda persistida sesión a
    sesión. Es lo único que sigue disponible una semana después, cuando se
    escribe el reporte.
    """
    ahora = ahora or datetime.now()

    minutos = sum(
        int((s.fin - s.inicio).total_seconds() // 60) for s in sesiones if s.fin is not None
    )
    cumplidas = sum(1 for c in cumplimientos if not c.regalo_la_respuesta)

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
        cumplimiento_metodo=(cumplidas / len(cumplimientos)) if cumplimientos else None,
        grado_de_trabajo=grado_de_trabajo(nino, grafo, ahora),
        adelanto_grados=adelanto(nino, grafo, ahora),
    )


class _SalidaReporte(BaseModel):
    """El reporte llega en DOS campos porque son dos cosas distintas.

    `narrativa` afirma cosas sobre el niño y se verifica en código contra las
    métricas. `sugerencia_para_casa` propone una actividad, y una actividad de
    matemáticas necesariamente lleva números inventados ("este dinosaurio pesaba
    350 kilos") que no están —ni pueden estar— en las métricas.

    Estaban en un solo campo, y la verificación tumbó un reporte real y correcto
    por los números de la sugerencia: el papá se quedaba sin nada por una frase
    que no afirmaba nada sobre su hijo. Separarlos deja la verificación estricta
    donde importa y libre donde corresponde.
    """

    narrativa: str
    sugerencia_para_casa: str


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
        "Método socrático sostenido en: "
        + (
            f"{metricas.cumplimiento_metodo:.0%} de las sesiones"
            if metricas.cumplimiento_metodo is not None
            else "todavía ninguna sesión auditada — NO afirmes nada sobre el método"
        ),
        f"Grado de trabajo real: {metricas.grado_de_trabajo}°",
        f"Adelanto sobre su grado: {metricas.adelanto_grados:+d}",
    ]
    if nino.perfil.intereses:
        contexto.append(f"Le interesa: {', '.join(nino.perfil.intereses)}")

    salida = cliente.extraer(
        cfg.MODELO_COMPANERO_PAPA,
        cargar_prompt("parent_companion"),
        "--- DATOS DEL PERÍODO ---\n" + "\n".join(contexto),
        _SalidaReporte,
        temperatura=TEMPERATURA_PROSA,
    )
    return ReporteParaPapa(
        nino_id=nino.id,
        desde=desde,
        hasta=hasta,
        metricas=metricas,
        contenido=salida.narrativa,
        sugerencia=salida.sugerencia_para_casa,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Quién dispara el reporte
# ─────────────────────────────────────────────────────────────────────────────
# `generar_reporte()` sabe redactar, pero alguien tiene que decidir CUÁNDO. Se
# eligió una tarea periódica y no "al abrir el panel": el papá entra a verificar,
# y meter una llamada a un modelo en el camino de su petición HTTP significa que
# a veces la página tarda diez segundos y a veces no. Peor: el panel dejaría de
# ser estable entre visitas, que es justo lo que lo hace verificable (§4).


class ErrorReporteInventado(Exception):
    """El reporte no pasó la verificación contra la fuente. NO se guarda.

    Un reporte inflado es peor que ninguno: el papá habla con su hijo, se da
    cuenta, y ahí perdió lo único que compró. Preferimos que falte a que mienta.
    """

    def __init__(self, nino_id: str, problemas: list[str]) -> None:
        super().__init__(f"{nino_id}: " + "; ".join(problemas))
        self.nino_id = nino_id
        self.problemas = problemas


class ReporteFallido(NamedTuple):
    """Un niño que se quedó sin reporte, y por qué. Lo lee el que corre la tarea."""

    nino_id: str
    motivo: str


def reporte_vigente(
    repo: Repositorio, nino_id: str, ahora: datetime, dias: int = cfg.DIAS_PERIODO_REPORTE
) -> bool:
    """¿Ya hay un reporte de este período? Es la idempotencia del reporte: dos
    corridas el mismo día no le mandan dos resúmenes al papá."""
    ultimo = repo.ultimo_reporte(nino_id)
    return ultimo is not None and (ahora - ultimo.hasta) < timedelta(days=dias)


def generar_reporte_del_periodo(
    repo: Repositorio,
    grafo: GrafoHabilidades,
    nino_id: str,
    cliente: ClienteLLM | None = None,
    ahora: datetime | None = None,
    dias: int = cfg.DIAS_PERIODO_REPORTE,
) -> ReporteParaPapa | None:
    """Arma el reporte del período y lo guarda. None si no correspondía.

    No corresponde cuando ya hay uno vigente, o cuando el niño no tuvo ninguna
    sesión: un reporte de una semana sin sesiones no tiene nada que contar, y
    pedirle a un modelo que escriba sobre la nada es pedirle que invente.

    El cumplimiento sale de las auditorías PERSISTIDAS, no de un análisis nuevo:
    la transcripción a esta altura puede estar borrada, pero el veredicto no.
    """
    ahora = ahora or datetime.now()
    nino = repo.obtener_nino(nino_id)
    if nino is None or reporte_vigente(repo, nino_id, ahora, dias):
        return None

    desde = ahora - timedelta(days=dias)
    sesiones = repo.sesiones_de(nino_id, desde, ahora)
    if not sesiones:
        return None

    cumplimientos = [v for s in sesiones if (v := repo.obtener_auditoria(s.id)) is not None]
    metricas = calcular_metricas(nino, sesiones, cumplimientos, grafo, ahora)

    reporte = generar_reporte(nino, metricas, desde, ahora, cliente)
    if problemas := verificar_reporte(reporte):
        raise ErrorReporteInventado(nino_id, problemas)

    repo.guardar_reporte(reporte)
    return reporte


def generar_reportes_pendientes(
    repo: Repositorio,
    grafo: GrafoHabilidades,
    cliente: ClienteLLM | None = None,
    ahora: datetime | None = None,
    dias: int = cfg.DIAS_PERIODO_REPORTE,
) -> tuple[list[ReporteParaPapa], list[ReporteFallido]]:
    """Recorre a todos los niños. Devuelve lo generado y lo que falló.

    Ningún niño puede tumbar la corrida de los demás — ni por un reporte que
    miente, ni porque el modelo devolvió basura esa vez (pasó: `messages.parse`
    recibió una respuesta vacía y explotó a mitad de la tarea). Por eso se
    atrapa cualquier excepción, no solo la nuestra.

    Pero no se traga: cada falla se DEVUELVE con su motivo, y el que corre la
    tarea la ve. Una tarea silenciosa que "anduvo bien" mientras nadie recibe
    su reporte es peor que una que falla ruidosamente.
    """
    cliente = cliente or cliente_por_defecto()
    generados: list[ReporteParaPapa] = []
    fallidos: list[ReporteFallido] = []

    for nino_id in repo.ids_de_ninos():
        try:
            if (reporte := generar_reporte_del_periodo(
                repo, grafo, nino_id, cliente, ahora, dias
            )) is not None:
                generados.append(reporte)
        except ErrorReporteInventado as e:
            fallidos.append(ReporteFallido(nino_id, "; ".join(e.problemas)))
        except Exception as e:  # noqa: BLE001
            fallidos.append(ReporteFallido(nino_id, f"{type(e).__name__}: {e}"))
    return generados, fallidos


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
    calendario: Calendario | None = None

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


def primera_pregunta() -> str:
    """El saludo con el que abre la entrevista. Fijo, y por eso instantáneo.

    Se le pedía al modelo con la conversación vacía: sin nada que leer devolvía
    siempre el mismo saludo, y costaba 3,5 s de Sonnet en la primera pantalla
    que ve un papá. El criterio del entrevistador no aporta en un turno donde no
    hay nada que interpretar; entra en el turno 2, cuando ya hay algo que leer.

    Sigue siendo un dato editable sin tocar Python, como el resto de los prompts.
    """
    return cargar_prompt("parent_interview_apertura").strip()


def siguiente_pregunta(
    historial: list[tuple[str, str]],
    ficha: FichaInicial,
    cliente: ClienteLLM | None = None,
) -> str:
    """El turno del entrevistador. Sonnet: acá la calidez es el producto."""
    cliente = cliente or cliente_por_defecto()

    if ficha.completa:
        pendiente = (
            "Ya tienes todo lo necesario. Cierra la conversación: dile en dos "
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
        # Si el papá no lo dijo, el default del modelo es A — el de la mayoría
        # de los colegios del país. No es obligatorio: bloquear el alta por un
        # dato que muchos papás no saben de memoria cuesta más de lo que arregla.
        calendario=ficha.calendario or Calendario.A,
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

    Mira `contenido` y NO `sugerencia`: lo que se afirma sobre el niño se
    verifica, lo que se propone hacer en casa no se puede. Una actividad de
    matemáticas lleva números que son del juego ("pesaba 350 kilos"), no del
    chico — exigirles respaldo en las métricas descartaba reportes correctos.
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
        round(m.cumplimiento_metodo * 100) if m.cumplimiento_metodo is not None else -1,
        reporte.desde.day,
        reporte.hasta.day,
    }
    for n in numeros:
        if n not in plausibles and n > 1:
            problemas.append(f"número '{n}' no aparece en las métricas")

    if m.adelanto_grados >= 1 and "adelant" not in texto.lower():
        problemas.append("va adelantado y el reporte no lo menciona")

    return problemas
