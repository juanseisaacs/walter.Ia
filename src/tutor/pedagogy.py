"""El cerebro: dominio, olvido, qué enseñar y cómo dar pistas.

Módulo PURO — sin red, sin I/O. Se testea en milisegundos.

Todo lo que hay acá podría haber sido un agente LLM y deliberadamente no lo es:
es cálculo, no criterio. Gratis, instantáneo, predecible, auditable. Con los
mismos datos da siempre la misma respuesta — y eso se puede explicar a un papá.

DECISIÓN CLAVE — el decaimiento se calcula al LEER, no al escribir:
    Se guarda `nivel` (el valor en la última práctica) y `ultima_practica`.
    El nivel actual es una función pura de esos dos datos más la fecha de hoy.
    La alternativa (un job que decae a todos todas las noches) exige un proceso
    corriendo, se rompe si no corre un día, y no es reproducible.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from enum import IntEnum, StrEnum

from .curriculum import GrafoHabilidades
from .models import Calendario, Habilidad, Materia, Nino, RegistroDominio

# ─────────────────────────────────────────────────────────────────────────────
# Parámetros del modelo de aprendizaje
# ─────────────────────────────────────────────────────────────────────────────

_log = logging.getLogger("tutor.pedagogy")
"""Sin handler propio: quien corre el proceso decide dónde se imprime."""

UMBRAL_DOMINIO = 0.80
"""A partir de acá la habilidad se considera dominada y desbloquea a las que dependen de ella."""

UMBRAL_REPASO = 0.60
"""Por debajo de acá, algo que estuvo dominado necesita repaso."""

TASA_APRENDIZAJE = 0.30
"""Cuánto mueve cada intento el nivel. Media móvil exponencial: lo reciente pesa más."""

VIDA_MEDIA_BASE_DIAS = 12.0
"""Días para olvidar la mitad de algo apenas aprendido y poco practicado.

Calibrado contra la realidad, no contra la curva de Ebbinghaus: esa mide sílabas
sin sentido. Una habilidad entendida y practicada se retiene muchísimo más.
Un chico que aprendió a contar hasta 100 no lo pierde en dos semanas."""

FACTOR_CONSOLIDACION = 6.0
"""Cuánto alarga la vida media el dominio alto. Lo bien aprendido se olvida más lento."""

FACTOR_REPETICION = 0.4
"""Cuánto alarga la vida media haber practicado muchas veces.

Es el principio del repaso espaciado: cada práctica exitosa estira el intervalo
hasta el próximo repaso. Crece logarítmicamente — las primeras repeticiones
consolidan mucho más que la décima."""


# ─────────────────────────────────────────────────────────────────────────────
# Dominio
# ─────────────────────────────────────────────────────────────────────────────


def valor_evidencia(acerto: bool, pistas_usadas: int) -> float:
    """Cuánto vale un intento como evidencia de dominio.

    Acertar con ayuda no es lo mismo que acertar solo. Si no se distingue, un
    niño que necesita tres pistas cada vez figura como que domina el tema.
    """
    if not acerto:
        return 0.0
    if pistas_usadas == 0:
        return 1.0
    if pistas_usadas == 1:
        return 0.70
    return 0.40


def actualizar_dominio(
    registro: RegistroDominio,
    acerto: bool,
    pistas_usadas: int = 0,
    ahora: datetime | None = None,
) -> RegistroDominio:
    """Registra un intento y recalcula el nivel.

    Parte del nivel EFECTIVO (ya decaído), no del guardado: si el niño volvió
    después de un mes, el intento se suma a lo que realmente recordaba.
    """
    ahora = ahora or datetime.now()
    base = nivel_efectivo(registro, ahora)
    evidencia = valor_evidencia(acerto, pistas_usadas)

    nuevo = base * (1 - TASA_APRENDIZAJE) + evidencia * TASA_APRENDIZAJE

    return registro.model_copy(
        update={
            "nivel": max(0.0, min(1.0, nuevo)),
            "intentos": registro.intentos + 1,
            "aciertos": registro.aciertos + (1 if acerto else 0),
            "pistas_necesitadas": registro.pistas_necesitadas + pistas_usadas,
            "primera_practica": registro.primera_practica or ahora,
            "ultima_practica": ahora,
        }
    )


def nivel_efectivo(registro: RegistroDominio, ahora: datetime | None = None) -> float:
    """Nivel de dominio HOY, aplicando olvido.

    Decaimiento exponencial. La vida media depende de dos cosas:
      · qué tan bien se aprendió  (nivel)
      · cuántas veces se practicó (aciertos, logarítmico)

    Lo entendido y repetido se olvida despacio; lo aprendido a medias y visto una
    vez, rápido. Un sistema que asume que el niño nunca olvida es falso y se nota
    rápido; uno que asume que olvida todo en dos semanas, también.
    """
    if registro.ultima_practica is None or registro.nivel <= 0.0:
        return registro.nivel

    ahora = ahora or datetime.now()
    dias = (ahora - registro.ultima_practica).total_seconds() / 86_400
    if dias <= 0:
        return registro.nivel

    consolidacion = 1 + registro.nivel * FACTOR_CONSOLIDACION
    repeticion = 1 + math.log1p(registro.aciertos) * FACTOR_REPETICION
    vida_media = VIDA_MEDIA_BASE_DIAS * consolidacion * repeticion

    return registro.nivel * (0.5 ** (dias / vida_media))


def esta_dominada(registro: RegistroDominio | None, ahora: datetime | None = None) -> bool:
    return registro is not None and nivel_efectivo(registro, ahora) >= UMBRAL_DOMINIO


def necesita_repaso(registro: RegistroDominio, ahora: datetime | None = None) -> bool:
    """Estuvo dominado y decayó. No aplica a lo que nunca se aprendió."""
    if registro.nivel < UMBRAL_DOMINIO:
        return False
    return nivel_efectivo(registro, ahora) < UMBRAL_REPASO


# ─────────────────────────────────────────────────────────────────────────────
# El planificador  (esto NO es un agente)
# ─────────────────────────────────────────────────────────────────────────────


def _registro(nino: Nino, habilidad_id: str) -> RegistroDominio:
    return nino.dominio.get(habilidad_id) or RegistroDominio(habilidad_id=habilidad_id)


def habilidades_para_repasar(
    nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> list[Habilidad]:
    """Lo que se dominó y se está olvidando. Repaso espaciado."""
    pendientes = [
        grafo.habilidad(hid)
        for hid, reg in nino.dominio.items()
        if grafo.existe(hid) and necesita_repaso(reg, ahora)
    ]
    return sorted(pendientes, key=lambda h: nivel_efectivo(_registro(nino, h.id), ahora))


def prerrequisito_satisfecho(
    nino: Nino, prereq_id: str, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> bool:
    """¿Este prerrequisito deja pasar al niño?

    Sí, en dos casos distintos:

    1. **Lo dominó.** Lo medimos y le sale.
    2. **Nunca lo miramos, y es de un grado que ya cursó.** Presunción de
       grado: un chico de 2° ya pasó por 1° en el colegio.

    Por qué existe el caso 2 — y por qué NO se resuelve escribiendo dominio
    inventado en la ficha: "nivel 0 medido" y "sin registro" son cosas
    opuestas, y `esta_dominada(None)` las trataba igual. El resultado era que
    a Juan, de 2°, que llegó pidiendo sumas de dos dígitos, el grafo le
    ofrecía "contar hasta 100" — el nodo raíz — porque no tenía registro de
    nada. (Verificado el 17/08: 0 habilidades con dominio tras 4 sesiones.)

    Eso además tenía un costo escondido y peor: con un ejercicio así de fácil
    enfrente, **el modelo lo ignoraba y se inventaba los suyos**. O sea que la
    laguna del planificador era la que desconectaba todo el motor pedagógico.

    Es una PRESUNCIÓN, no un dato: no se guarda nada en `dominio`. En cuanto
    el niño falle, la evidencia real reemplaza a la presunción y el grafo
    vuelve a mandar. Es lo que hace un profesor el primer día: te trata según
    tu grado, y ajusta cuando te ve trabajar.

    Estrictamente MENOR que su grado, nunca menor o igual: se presume lo que
    el colegio ya cubrió en años anteriores, no lo que está viendo ahora.
    """
    registro = nino.dominio.get(prereq_id)
    if esta_dominada(registro, ahora):
        return True
    if registro is not None:
        return False  # hay evidencia y dice que no. La evidencia manda.
    if not grafo.existe(prereq_id):
        return False
    return grafo.habilidad(prereq_id).grado_sugerido < nino.grado


def habilidades_disponibles(
    nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> list[Habilidad]:
    """La frontera: lo que el niño PUEDE aprender ahora.

    Prerrequisitos satisfechos y esta todavía no. Esto es lo que hace posible
    que el tutor sea adaptativo — una lista lineal no puede responder esta
    pregunta.
    """
    frontera = []
    for h in grafo:
        if esta_dominada(nino.dominio.get(h.id), ahora):
            continue
        if all(prerrequisito_satisfecho(nino, p, grafo, ahora) for p in h.prerequisitos):
            frontera.append(h)
    return frontera


ORDEN_DE_MATERIAS = (Materia.LECTURA, Materia.ESCRITURA, Materia.MATEMATICAS)
"""Con qué materia se arranca cuando ninguna se ha trabajado todavía.

Es el orden con que el propio producto se nombra —«lectura, escritura y
aritmética»—, no un juicio pedagógico inventado acá."""


def orden_de_materias(nino: Nino, grafo: GrafoHabilidades) -> dict[Materia, tuple]:
    """Qué tan abandonada está cada materia. Menor es «va primero».

    El día que entró lectura y escritura, el grafo pasó a tener tres raíces y el
    planificador mandó a TODOS a escritura: el desempate final era `h.id`, y
    «esc.» le gana a «lec.» y a «mat.» en el alfabeto. Un niño de 1° arrancaba
    en `esc.grafia.trazo_de_letras` y no veía un número nunca. No era un empate
    raro: era el caso de todos los días, y la suite seguía verde porque hasta
    ese día el grafo tenía una sola materia. Es la lección del código sin
    llamador otra vez, del otro lado: **un criterio de desempate que nunca
    desempató empieza a decidirlo todo el día que hay con qué empatar.**

    Se ordena por la última práctica: la materia que lleva más tiempo sin
    tocarse va primero. Es una fórmula sobre los datos que ya existen
    —determinista, sin modelo, sin estado nuevo— y hace que la semana cubra las
    tres en vez de repetir una.

    Esto elige la MATERIA. Qué nodo dentro de ella lo sigue decidiendo el
    dominio, igual que antes, y sin techo: nada de acá mira el grado.
    """
    ultima: dict[Materia, datetime] = {}
    for hid, registro in nino.dominio.items():
        if not registro.ultima_practica or hid not in grafo:
            continue
        materia = grafo.habilidad(hid).materia
        if materia not in ultima or registro.ultima_practica > ultima[materia]:
            ultima[materia] = registro.ultima_practica

    orden: dict[Materia, tuple] = {}
    for materia in Materia:
        orden[materia] = (
            (1, ultima[materia].timestamp())
            if materia in ultima
            # Nunca trabajada: va antes que cualquiera que sí, y entre las que
            # nunca se tocaron manda el orden declarado del producto.
            else (0, ORDEN_DE_MATERIAS.index(materia))
        )
    return orden


def siguiente_habilidad(
    nino: Nino,
    grafo: GrafoHabilidades,
    ahora: datetime | None = None,
    con_ejercicios: set[str] | None = None,
) -> Habilidad | None:
    """Qué trabajar ahora. Determinístico: mismos datos, misma respuesta.

    Prioridad:
      1. Repaso — lo olvidado bloquea todo lo que se apoya en ello
      2. Frontera, priorizando el grado del niño y el prerrequisito más firme

    Devuelve None solo si el niño dominó todo el grafo alcanzable.

    `con_ejercicios` son las habilidades que tienen banco. **Una habilidad sin
    ejercicios no se elige**: el tutor abriría la sesión sin nada que darle al
    niño, improvisaría, y nada quedaría atado a un nodo del grafo — así que la
    sesión no escribiría dominio. Ya pasó (`ses_88be006b825f`), y el día que el
    grafo crezca más rápido que el banco vuelve a pasar solo.

    Si NINGUNA de las disponibles tiene banco se devuelve la mejor igual, con un
    aviso: quedarse sin sesión es peor que una sesión improvisada, pero eso hay
    que verlo pasar en vez de que ocurra en silencio.
    """
    if repasos := habilidades_para_repasar(nino, grafo, ahora):
        con_banco = [h for h in repasos if con_ejercicios is None or h.id in con_ejercicios]
        if con_banco:
            return con_banco[0]

    disponibles = habilidades_disponibles(nino, grafo, ahora)
    if not disponibles:
        return None

    if con_ejercicios is not None:
        servibles = [h for h in disponibles if h.id in con_ejercicios]
        if servibles:
            disponibles = servibles
        else:
            _log.warning(
                "ninguna de las %d habilidades disponibles para %s tiene ejercicios: "
                "la sesión va a abrir con el banco vacío y el tutor va a improvisar",
                len(disponibles),
                nino.id,
            )

    # Primero la materia más abandonada; el niño trabaja las tres a lo largo de
    # la semana en vez de repetir la que gane el alfabeto.
    materias = orden_de_materias(nino, grafo)

    def prioridad(h: Habilidad) -> tuple:
        # SIN TECHO: subir de grado no se penaliza nunca. Solo se prefiere no
        # bajar, porque volver atrás sin necesidad aburre. Si el niño llegó a
        # contenido de tres grados más arriba, es porque tiene los
        # prerrequisitos — y entonces se lo gana.
        distancia_grado = max(0, nino.grado - h.grado_sugerido)
        # Con prerrequisitos más firmes, el próximo paso es más seguro
        firmeza = (
            min(nivel_efectivo(_registro(nino, p), ahora) for p in h.prerequisitos)
            if h.prerequisitos
            else 1.0
        )
        # Avance parcial primero: terminar lo empezado antes de abrir un frente nuevo
        avance = nivel_efectivo(_registro(nino, h.id), ahora)
        return (materias[h.materia], distancia_grado, -avance, -firmeza, h.id)

    return min(disponibles, key=prioridad)


# ─────────────────────────────────────────────────────────────────────────────
# Sin techo: dónde está realmente el niño
# ─────────────────────────────────────────────────────────────────────────────
# El grado escolar es una etiqueta administrativa, no un límite. El sistema
# mide dónde está el niño por lo que domina, y lo deja llegar tan lejos como
# pueda. Ver ARCHITECTURE.md §11.


def grado_de_trabajo(nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None) -> int:
    """En qué grado está trabajando el niño DE VERDAD.

    Es el grado más bajo que todavía no domina: lo que tiene enfrente. Un niño
    de 2° que ya dominó todo 2° trabaja en 3°, y así se lo reporta.

    Rige la misma PRESUNCIÓN DE GRADO que usa el planificador (ver
    `prerrequisito_satisfecho`): una habilidad de un grado que el niño ya cursó,
    sobre la que nunca medimos nada, no cuenta acá. No es una laguna — es algo
    que no miramos.

    Sin ese filtro, a Juan (2°, trabajando centenas, sin más evidencia) el
    reporte le decía al papá que *"el nivel en el que está trabajando
    corresponde más a 1° grado que a 2°"*, solo porque quedaban nodos de 1°
    sin registro. Es el pecado inverso al de afirmar un 100% sin auditar:
    afirmar un déficit sin un solo dato que lo sostenga. Y de los dos, este es
    el que asusta a un papá.

    En cuanto hay evidencia real de que algo de un grado anterior no le sale,
    esa habilidad vuelve a contar y el atraso que se reporta es verdadero.
    """
    disponibles = habilidades_disponibles(nino, grafo, ahora)
    medidas = [
        h for h in disponibles if h.grado_sugerido >= nino.grado or h.id in nino.dominio
    ]
    if medidas:
        return min(h.grado_sugerido for h in medidas)
    if disponibles:
        # Solo quedan nodos de grados ya cursados y sin medir: se los presume.
        return nino.grado
    grados = [h.grado_sugerido for h in grafo]
    return max(grados) if grados else nino.grado


def adelanto(nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None) -> int:
    """Grados por encima (+) o por debajo (−) del grado escolar.

    Positivo NO es un problema a corregir: es el producto funcionando.
    """
    return grado_de_trabajo(nino, grafo, ahora) - nino.grado


def va_adelantado(nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None) -> bool:
    """¿Amerita contárselo al papá?

    Es de lo más potente que puede leer: "tu hijo trabaja un grado por encima".
    """
    return adelanto(nino, grafo, ahora) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# La escalera socrática
# ─────────────────────────────────────────────────────────────────────────────


class NivelPista(IntEnum):
    """Escalones de ayuda, de menos a más concreto.

    NO EXISTE UN NIVEL "DAR LA RESPUESTA". Esa es la garantía del producto,
    y está codificada en el tipo: no se puede devolver algo que no existe.

    Si el niño sigue trabado en el último escalón, se resuelve un ejercicio
    PARECIDO juntos — nunca el suyo.
    """

    PREGUNTA_ABIERTA = 0
    """"¿Qué se te ocurre para empezar?" — cero información."""

    PREGUNTA_ORIENTADORA = 1
    """"¿Qué pasa con las unidades?" — dirige la atención, no revela."""

    PISTA_CONCEPTUAL = 2
    """"Acordate de qué pasa cuando las unidades pasan de 9." — recuerda la regla."""

    PISTA_CONCRETA = 3
    """"7 más 5 son 12. ¿Dónde ponés el 1?" — un paso resuelto, no el resultado."""

    EJEMPLO_PARALELO = 4
    """Resolver OTRO ejercicio parecido juntos, y volver al suyo."""


def siguiente_pista(intentos_fallidos: int) -> NivelPista:
    """A qué escalón subir según cuántas veces se trabó.

    Nunca pasa de EJEMPLO_PARALELO: la escalera no llega a la respuesta.
    """
    return NivelPista(min(max(intentos_fallidos, 0), NivelPista.EJEMPLO_PARALELO))


# ─────────────────────────────────────────────────────────────────────────────
# Resumen para el prompt de sesión
# ─────────────────────────────────────────────────────────────────────────────


class MomentoEscolar(StrEnum):
    """En qué parte del año escolar está el niño hoy.

    No se guarda: se calcula de `Nino.calendario` y la fecha. Un dato derivado
    que se persiste es un dato que se puede quedar viejo.
    """

    INICIO = "inicio"
    EN_CURSO = "en_curso"
    RECTA_FINAL = "recta_final"
    RECESO = "receso"


# Frontera de cada tramo como (mes, día) — vale desde esa fecha hasta la
# siguiente. Ordenadas, y la primera arranca el 1 de enero para que cualquier
# fecha del año caiga en algún tramo sin casos especiales de fin de año.
#
# Las 40 semanas lectivas son las mismas en los dos calendarios (Decreto 1850
# de 2002); lo que cambia es dónde empiezan. Ver `base_academica_men.md` §V.3.
_TRAMOS: dict[Calendario, tuple[tuple[tuple[int, int], MomentoEscolar], ...]] = {
    # Enero tardío a noviembre. Receso grande a mitad de año y en diciembre.
    Calendario.A: (
        ((1, 1), MomentoEscolar.RECESO),
        ((1, 16), MomentoEscolar.INICIO),
        ((3, 1), MomentoEscolar.EN_CURSO),
        ((6, 1), MomentoEscolar.RECESO),
        ((7, 16), MomentoEscolar.EN_CURSO),
        ((10, 1), MomentoEscolar.RECTA_FINAL),
        ((12, 1), MomentoEscolar.RECESO),
    ),
    # Agosto a junio. El año escolar cruza el año calendario.
    Calendario.B: (
        ((1, 1), MomentoEscolar.RECESO),
        ((1, 16), MomentoEscolar.EN_CURSO),
        ((5, 1), MomentoEscolar.RECTA_FINAL),
        ((6, 16), MomentoEscolar.RECESO),
        ((8, 16), MomentoEscolar.INICIO),
        ((10, 1), MomentoEscolar.EN_CURSO),
        ((12, 1), MomentoEscolar.RECESO),
    ),
}


def momento_del_ano(calendario: Calendario, fecha: datetime) -> MomentoEscolar:
    """En qué parte del año escolar cae esta fecha. Función pura.

    Es una fórmula, no un juicio: el mismo par (calendario, fecha) da siempre lo
    mismo, y eso se le puede explicar a un papá.

    Deliberadamente NO entra al planificador. `siguiente_habilidad` decide por
    dominio y solo por dominio — si el calendario cambiara qué nodo se ofrece,
    dos niños con la misma ficha recibirían cosas distintas por el día en que
    entraron, y el reporte al papá dejaría de ser reproducible. El momento del
    año cambia el TONO de la sesión (qué se repasa, cuánto se exige), y eso vive
    en el prompt.
    """
    hoy = (fecha.month, fecha.day)
    momento = _TRAMOS[calendario][0][1]
    for desde, tramo in _TRAMOS[calendario]:
        if hoy >= desde:
            momento = tramo
    return momento


GUIA_POR_MOMENTO: dict[MomentoEscolar, str] = {
    MomentoEscolar.INICIO: (
        "Arranca el año escolar: mucho de lo de este grado todavía no lo ha "
        "visto en clase. Repasa lo del año pasado y acompaña lo que traiga."
    ),
    MomentoEscolar.RECTA_FINAL: (
        "Recta final del año escolar. Es momento de cerrar lo que quedó flojo, "
        "no de abrir temas nuevos que no alcanza a asentar."
    ),
    MomentoEscolar.RECESO: (
        "Está en vacaciones. Repaso liviano y por gusto: nada de exigencia de "
        "pensum ni de ponerse al día. Si quiere jugar con un tema, jueguen."
    ),
}
"""Qué cambia en la sesión según el momento del año. `EN_CURSO` no lleva línea:
es el caso normal y no hace falta decirle al tutor que trabaje normal."""


REGISTRO_POR_GRADO: dict[int, str] = {
    1: (
        "Piensa en concreto y su atención es corta. Una idea por turno, frases "
        "cortas, ejemplos con su cuerpo, sus juguetes o su familia. Preguntas de "
        "elección ('¿son más o son menos?'), no abiertas. Nada de definiciones."
    ),
    2: (
        "Ya clasifica y ordena, pero necesita objetos para pensar. Habla siempre "
        "de cosas contables ('imagínate 8 mandarinas'). Pasos numerados. Pídele "
        "que te lo cuente con sus palabras antes de seguir."
    ),
    3: (
        "Su lógica concreta ya está firme: entiende que si 4+3=7 entonces 7-3=4. "
        "Usa problemas de la calle —la tienda, la plata, una receta—. Hazlo "
        "predecir antes de calcular, y pregúntale por qué cree eso."
    ),
    4: (
        "Relaciona varias cosas a la vez. Tablas, esquemas y comparaciones le "
        "sirven. Llévalo a la primera generalización: '¿eso pasa siempre?'. "
        "Aguanta explicaciones más largas que un niño de 2°."
    ),
    5: (
        "Razona sistemáticamente sobre lo concreto y ya ensaya reglas propias, "
        "pero todavía no piensa en abstracto. Retos de varios pasos: que proponga "
        "una conjetura y la compruebe. Sin álgebra formal ni lenguaje abstracto."
    ),
}
"""Cómo piensa el niño en cada grado, y qué hace el tutor con eso.

Etapa de operaciones concretas de Piaget (7-11 años), como la baja el MEN a
primaria colombiana — ver `knowledge/curriculum/base_academica_men.md` §V.5.

Entra UNA línea, la del grado del niño, no la tabla: el prompt se mantiene
flaco (ARCHITECTURE.md §9). Es el complemento pedagógico de lo que
`voice.deteccion_para_edad` ya hace del lado técnico — allá cuánto esperamos a
que termine de hablar, acá cómo le hablamos.

Deliberadamente NO se copió la recomendación de la fuente para 1° ("celebrar
cada intento"): choca de frente con la prohibición de elogio inflado. La misma
fuente lo dice bien tres líneas después —reconocer el proceso, no el acierto— y
eso ya vive en `valores.es.md`. Acá va cómo PIENSA el niño, no cómo se lo trata:
lo segundo no cambia por grado.
"""


MAX_TEXTO_LIBRE = 220
"""Tope de cada campo de texto libre que entra al prompt (`notas`,
`contexto_escolar`).

Las listas del perfil ya venían acotadas por `[:4]` y `[:3]`; estos dos campos
no, y los escribe un modelo. Un Analista que un día devuelve un párrafo de 600
caracteres en cada uno empuja el prompt casi 1 KB, sin que nadie lo pida y sin
que ningún test lo vea. El presupuesto del prompt se defiende en el borde donde
importa, no confiando en que el modelo se porte bien."""


def _recortar(texto: str, limite: int = MAX_TEXTO_LIBRE) -> str:
    """Corta en el último espacio antes del límite, para no partir una palabra."""
    if len(texto) <= limite:
        return texto
    corte = texto.rfind(" ", 0, limite)
    return texto[: corte if corte > limite // 2 else limite].rstrip(" ,;.") + "…"


def resumen_para_prompt(
    nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> str:
    """Comprime la ficha a unas pocas líneas.

    El prompt de sesión se mantiene flaco (ARCHITECTURE.md §9): nunca la
    historia completa, nunca el currículum entero. Solo lo que cambia la
    conducta del tutor en ESTA sesión.
    """
    lineas = [f"{nino.nombre}, {nino.edad} años, {nino.grado}° grado."]

    if (registro := REGISTRO_POR_GRADO.get(nino.grado)) is not None:
        lineas.append(registro)

    momento = momento_del_ano(nino.calendario, ahora or datetime.now())
    if (guia := GUIA_POR_MOMENTO.get(momento)) is not None:
        lineas.append(guia)

    dominadas = [hid for hid, reg in nino.dominio.items() if esta_dominada(reg, ahora)]
    if dominadas:
        lineas.append(f"Ya domina {len(dominadas)} habilidades.")

    if (delta := adelanto(nino, grafo, ahora)) >= 1:
        grados = "grado" if delta == 1 else "grados"
        lineas.append(
            f"VA ADELANTADO: ya trabaja {delta} {grados} por encima del suyo "
            f"(está en {grado_de_trabajo(nino, grafo, ahora)}°). "
            "No lo frenes ni bajes la exigencia — sigue subiendo mientras responda."
        )

    if (objetivo := siguiente_habilidad(nino, grafo, ahora)) is not None:
        lineas.append(f"Hoy: {objetivo.nombre.es} — {objetivo.descripcion.es}")

    if repasos := habilidades_para_repasar(nino, grafo, ahora):
        lineas.append("Conviene repasar: " + ", ".join(h.nombre.es for h in repasos[:3]) + ".")

    p = nino.perfil
    if p.datos_suyos:
        # Primero lo que el niño contó DE ÉL. Es lo que hace que el tutor suene
        # como alguien que lo conoce, y lo primero que el niño va a probar.
        lineas.append("Te contó: " + "; ".join(p.datos_suyos[:5]) + ".")
    if p.intereses:
        lineas.append("Le gusta: " + ", ".join(p.intereses[:4]) + ".")
    if p.motivadores:
        lineas.append("Lo motiva: " + ", ".join(p.motivadores[:3]) + ".")
    if p.frustraciones:
        lineas.append("Lo traba: " + ", ".join(p.frustraciones[:3]) + ".")
    if p.estilo_comunicacion:
        lineas.append(f"Estilo: {p.estilo_comunicacion}.")
    if p.contexto_escolar:
        # El 20% del PEI que no está en ningún estándar. Va después del perfil y
        # antes de las notas porque es contexto de la clase, no del niño.
        lineas.append(f"En el colegio: {_recortar(p.contexto_escolar)}")
    if p.notas:
        lineas.append(_recortar(p.notas))

    # De dónde viene lo que sabe. El tutor tiene una regla dura sobre no decir
    # "me contaron", y en la primera sesión esa regla lo hace mentir: todavía no
    # habló con el niño ni una vez, todo esto se lo dijo el papá en el
    # onboarding. Si el niño contesta "yo nunca te dije eso", el tutor queda
    # como alguien que inventa — que es exactamente lo que la regla quería
    # evitar. La distinción ya existía en el código (`madurez_vinculo=0` al
    # crear desde la ficha); faltaba que llegara al prompt.
    # ¿Hay algo PERSONAL que usar, o solo el grado y el tema del día? La
    # diferencia decide qué se le dice al tutor, y la diferencia importa.
    sabe_algo_de_el = any(
        (p.datos_suyos, p.intereses, p.motivadores, p.frustraciones,
         p.estilo_comunicacion, p.contexto_escolar, p.notas)
    )

    if p.madurez_vinculo == 0 and sabe_algo_de_el:
        lineas.append(
            "PRIMERA VEZ que hablan. Todo lo de arriba te lo contó su papá o su "
            "mamá, no él: no digas que te lo contó él. Úsalo para preguntar, no "
            "para demostrar que ya lo sabes. Si te pregunta cómo lo sabes, dile "
            "la verdad con naturalidad — que su familia te contó para que se "
            "conocieran más rápido."
        )
    elif p.madurez_vinculo == 0:
        # Sin esto el tutor recibía "úsalo para preguntar" y NO TENÍA QUÉ, así
        # que rellenaba el hueco con el ejemplo del prompt: preguntaba por
        # dinosaurios —el ejemplo literal de `tutor_persona.es.md`— a un niño
        # del que no sabía nada. Verificado el 22/08 con dos sesiones reales; y
        # con la ficha poblada preguntó por lo que de verdad le gustaba, así
        # que el problema nunca fue el ejemplo: era el hueco.
        #
        # Es la lección de visión otra vez: lo que no se le dice, se lo inventa.
        lineas.append(
            "PRIMERA VEZ que hablan y NO SABES NADA de él: ni sus gustos, ni a "
            "qué juega, ni qué se le hace fácil. No des por hecho ningún tema — "
            "no le preguntes por dinosaurios, ni fútbol, ni nada que se te "
            "ocurra, porque no te lo contó nadie. Preguntale abierto qué le "
            "gusta hacer y escuchá: eso es lo que hay que averiguar hoy."
        )
    elif p.madurez_vinculo < 3:
        lineas.append("Todavía lo conoces poco: pregunta y explora.")

    return "\n".join(lineas)
