"""Estructuras de datos del sistema.

Este archivo es el contrato: define las formas que viajan entre todas las piezas.
Es puro — sin red, sin I/O, sin lógica de negocio.

Ver ARCHITECTURE.md §10 (ficha del niño) y §7 (grafo de habilidades).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────


class TextoLocalizado(BaseModel):
    """Texto en varios idiomas.

    El campo `en` existe desde el día 1 pero queda vacío hasta la fase de inglés.
    Costo hoy: cero. Refactor mañana: cero.
    """

    es: str
    en: str | None = None


class Materia(StrEnum):
    MATEMATICAS = "matematicas"
    LECTURA = "lectura"
    ESCRITURA = "escritura"


class Calendario(StrEnum):
    """Los dos calendarios escolares que conviven en Colombia.

    Cambian en qué mes empieza y termina el año, y por lo tanto cuándo el niño
    está arrancando, en la recta final o de vacaciones. Las mismas 40 semanas
    lectivas en los dos (Decreto 1850 de 2002).

    `A` es el default porque es el de la mayoría de colegios oficiales y
    privados; `B` es el de bilingües e internacionales.
    """

    A = "A"
    B = "B"


# ─────────────────────────────────────────────────────────────────────────────
# Grafo de habilidades  (el mapa — igual para todos los niños)
# ─────────────────────────────────────────────────────────────────────────────


class Alineacion(BaseModel):
    """Anclaje a estándares curriculares reconocidos.

    El grafo es nuestro; citamos alineación. Esto responde la pregunta
    "¿contra qué está alineado?" — criterio #1 de YC.
    """

    dba_colombia: str | None = None
    core_knowledge: str | None = None

    sin_anclaje: str | None = None
    """POR QUÉ esta habilidad no puede citar un estándar. No es un hueco: es la
    respuesta escrita a "¿contra qué está alineado?" cuando la respuesta honesta
    es "contra nada oficial, y estas son las razones".

    Existe porque los DBA de Lenguaje **no descomponen la decodificación**
    (`FUENTES.md` §2.3): no hay DBA de conciencia fonémica, ni de sílabas
    trabadas, ni de correspondencia grafema-fonema. Y el segundo anclaje que
    usa matemáticas tampoco sirve ahí — Core Knowledge Language Arts es
    fonética INGLESA y no transfiere al español, que es de ortografía
    transparente y tiene otros problemas (la sílaba antes que el fonema, las
    trabadas, la eñe, la tilde).

    Dejar el campo vacío habría sido lo fácil y lo peor: un nodo sin anclaje se
    ve igual que uno al que se le olvidó ponérselo. Con esto, `test_curriculum
    _real_cita_estandares` sigue exigiendo respuesta a TODA habilidad — solo
    que admite esta, que obliga a escribir el motivo."""

    ebc_colombia: str | None = None
    """Estándar Básico de Competencias del MEN (2006), por banda 1°-3° o 4°-5°.

    Es el tercer anclaje, y no es redundante con el DBA: el Estándar dice cosas
    que el DBA no dice y que el grafo necesita — par/impar, múltiplo y divisible
    en 1°-3°; porcentajes, potenciación y radicación en 4°-5°
    (`FUENTES.md` §2.4). Cuando un nodo no tiene DBA que lo respalde pero sí un
    Estándar, este campo es el que evita inventar el anclaje.
    """


class Habilidad(BaseModel):
    """Un nodo del grafo de habilidades.

    Los prerrequisitos forman un DAG: para trabajar este nodo, los prerrequisitos
    deben estar dominados. El planificador navega esa estructura (en código).
    """

    id: str = Field(description="Llave estable. Nunca se traduce. Ej: mat.suma.con_reagrupacion")
    nombre: TextoLocalizado
    descripcion: TextoLocalizado
    materia: Materia
    grado_sugerido: int = Field(ge=1, le=11)
    """Grado de referencia, NO un límite: el planificador decide por dominio.

    El tope es 11 —el último del sistema colombiano— y está para atajar erratas,
    no para contener a nadie. Estuvo en 5 hasta el 18/08, y eso contradecía la
    regla SIN TECHO por un camino que no se veía: no filtraba al niño, pero
    impedía ESCRIBIR el nodo. ARCHITECTURE.md §12 pide que el grafo tenga
    siempre cabeza de pista por encima del grado del niño, y con el máximo en 5
    un chico veloz de 5° se quedaba sin nada que seguir. No mordía porque el
    grafo llega a 3°; iba a morder justo al extenderlo."""
    prerequisitos: list[str] = Field(default_factory=list, description="IDs de otras habilidades")
    alineacion: Alineacion = Field(default_factory=Alineacion)

    verificable_en_codigo: bool = Field(
        default=False,
        description=(
            "Si el código puede verificar la respuesta de forma determinística "
            "(típico en matemáticas). Si es False, `check_answer` devuelve "
            "REQUIERE_JUICIO en vez de inventar un veredicto — comprensión "
            "lectora y redacción no se contestan con una comparación."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ficha del niño  (mitad académica: la escribe el CÓDIGO)
# ─────────────────────────────────────────────────────────────────────────────


class RegistroDominio(BaseModel):
    """Estado de dominio de una habilidad para un niño.

    `nivel` decae con el tiempo sin práctica — ver pedagogy.py. Un sistema que
    asume que el niño nunca olvida es falso y se nota rápido.
    """

    habilidad_id: str
    nivel: float = Field(default=0.0, ge=0.0, le=1.0)
    intentos: int = 0
    aciertos: int = 0
    pistas_necesitadas: int = 0
    primera_practica: datetime | None = None
    ultima_practica: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Ficha del niño  (mitad personal: la escribe el ANALISTA)
# ─────────────────────────────────────────────────────────────────────────────


class PerfilPersonal(BaseModel):
    """Lo que hace que el tutor se sienta un tutor y no un software.

    REGLA: el Analista CONSOLIDA, no acumula. Si ya sabía que le gusta el fútbol
    y hoy lo confirma, refuerza la línea existente — no agrega una nueva.
    Si no, a los 6 meses esto es ilegible.
    """

    datos_suyos: list[str] = Field(default_factory=list)
    """Hechos concretos que el niño contó de sí mismo.

    "color favorito: rojo", "tiene un perro que se llama Kira", "su hermana se
    llama Sara", "juega en el equipo del colegio".

    Existe porque no había dónde ponerlos y se perdían. Felipe preguntó dos
    veces cuál era su color favorito y el tutor no lo sabía —"pero si te lo dije
    en la sesión pasada"—, que es la memoria longitudinal fallando justo donde
    el niño la nota.

    No entran en `intereses` (eso son temas que le gustan, y la lista se llena
    de observaciones pedagógicas) ni en `notas` (un párrafo se resume y un dato
    concreto se pierde en el resumen). Un dato no se sintetiza: se recuerda o no
    se recuerda."""

    intereses: list[str] = Field(default_factory=list)
    motivadores: list[str] = Field(default_factory=list, description="Qué lo impulsa")
    frustraciones: list[str] = Field(default_factory=list, description="Qué lo traba o lo apaga")
    estilo_comunicacion: str | None = Field(
        default=None, description="Cómo le gusta que le hablen"
    )
    notas: str | None = Field(default=None, description="Texto consolidado, no un log")

    contexto_escolar: str | None = Field(
        default=None,
        description=(
            "Qué está viendo en el colegio, según lo que el niño contó: temas, "
            "proyectos, cómo llaman a las materias, qué libro usan. Una línea "
            "consolidada, no un log."
        ),
    )
    """El 20% que ningún estándar nacional trae.

    La ley exige que las áreas obligatorias ocupen mínimo el 80% del plan de
    estudios; el 20% restante lo define cada colegio en su PEI. Nacemos sabiendo
    el 80% —eso es el grafo— y el 20% solo se aprende oyendo al niño.

    Campo propio y no dentro de `notas` por tres razones: el papá lo ve aparte en
    el panel, no compite con lo personal cuando el Analista consolida, y se puede
    mandar al prompt sin arrastrar el resto de la ficha.
    """

    madurez_vinculo: int = Field(
        default=0,
        description="Cuánto conoce el tutor al niño. Bajo → explorador. Alto → va directo.",
    )


class Nino(BaseModel):
    """La ficha completa: las dos mitades.

    Este es el activo del producto. La transcripción cruda no lo es — se borra.
    """

    id: str
    nombre: str
    edad: int = Field(ge=4, le=12)
    grado: int = Field(ge=1, le=5)
    idioma: str = "es"

    calendario: Calendario = Field(
        default=Calendario.A,
        description=(
            "Calendario escolar del colegio. Define en qué momento del año está "
            "el niño hoy — ver `pedagogy.momento_del_ano`."
        ),
    )

    token_acceso: str | None = Field(
        default=None,
        description=(
            "La credencial con la que el niño entra. Viaja en el enlace que el "
            "papá recibe al terminar el onboarding y no vence: es cómo entra "
            "cada día, no una sesión. Sin esto, `POST /api/sesiones` abría "
            "sesión con cualquier `nino_id` que le mandaran — y devolvía un "
            "token de Gemini a quien lo pidiera."
        ),
    )

    email_papa: str | None = Field(
        default=None,
        description=(
            "A dónde llegan el reporte semanal y las alertas de seguridad. "
            "Lo captura el Compañero del Papá en el onboarding — sin esto, una "
            "alerta no le llega a nadie."
        ),
    )

    dominio: dict[str, RegistroDominio] = Field(
        default_factory=dict, description="habilidad_id → registro. Mitad académica."
    )
    perfil: PerfilPersonal = Field(
        default_factory=PerfilPersonal, description="Mitad personal."
    )

    creado_en: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Ejercicios  (banco generado offline, validado en código)
# ─────────────────────────────────────────────────────────────────────────────


class Ejercicio(BaseModel):
    """Un ejercicio del banco.

    `validado` solo es True si el CÓDIGO verificó que la respuesta es correcta.
    Un ejercicio no validado nunca llega a un niño.
    """

    id: str
    habilidad_id: str
    enunciado: TextoLocalizado
    respuesta: str
    tema: str | None = Field(default=None, description="Variante temática: futbol, dinosaurios...")
    validado: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Sesión
# ─────────────────────────────────────────────────────────────────────────────


class ModoSesion(StrEnum):
    GUIADO = "guiado"
    """El planificador elige el tema. Ejercicios del banco."""

    PEDIDO = "pedido"
    """El niño trae su agenda (tarea, duda). Método socrático MÁS estricto."""


class EstadoSesion(StrEnum):
    ACTIVA = "activa"
    COMPLETADA = "completada"
    INTERRUMPIDA = "interrumpida"
    """Cayó el modelo de voz o se perdió conexión. Debe poder reanudarse."""


class Sesion(BaseModel):
    """Una sesión de tutoría.

    `analizada` es la llave de idempotencia: el Analista nunca procesa dos veces
    la misma sesión (evita doble conteo de dominio).
    """

    id: str
    nino_id: str
    modo: ModoSesion
    estado: EstadoSesion = EstadoSesion.ACTIVA

    inicio: datetime
    fin: datetime | None = None

    habilidades_trabajadas: list[str] = Field(default_factory=list)
    tokens_consumidos: int = 0
    analizada: bool = False

    tecnica_id: str | None = None
    """Con qué técnica se enseñó. La elige el backend al abrir, igual que la
    habilidad — ver `tecnicas.py`. `None` en las sesiones anteriores al motor."""

    dominio_inicial: float | None = None
    """Nivel de la habilidad del día al ABRIR la sesión.

    Es la mitad que no se puede reconstruir después: el dominio de hoy está en
    la tabla, pero el de antes de esta sesión ya se perdió. Sin este número no
    hay forma de saber cuánto movió la técnica, que es de lo que se trata todo
    el motor."""


# ─────────────────────────────────────────────────────────────────────────────
# Salida del Analista de sesión  (agente #4)
# ─────────────────────────────────────────────────────────────────────────────


class TipoObservacion(StrEnum):
    ACIERTO = "acierto"
    ERROR = "error"
    PISTA_NECESARIA = "pista_necesaria"
    FRUSTRACION = "frustracion"
    DOMINIO = "dominio"
    INTERES = "interes"


class Observacion(BaseModel):
    """Una señal detectada en la transcripción."""

    habilidad_id: str | None = Field(
        default=None,
        description=(
            "El id de la habilidad, tomado de la lista del mensaje. Requerido en "
            "acierto, error, pista_necesaria y dominio; null en frustracion e interes."
        ),
    )
    tipo: TipoObservacion
    evidencia: str = Field(description="Cita textual que respalda la observación")


class AuditoriaCumplimiento(BaseModel):
    """¿El TUTOR cumplió el método? (no mira al niño, mira al tutor)

    Corre en el 100% de las sesiones. Es la evidencia de que no somos
    "ChatGPT para la tarea" — criterio #4 de YC.
    """

    regalo_la_respuesta: bool
    respeto_escalera_pistas: bool
    detecto_frustracion: bool
    elogio_inflado: bool = Field(
        default=False,
        description=(
            "Línea roja 14: 'eres un genio', 'eres el mejor'. Suena a cariño y "
            "por eso se cuela, pero le enseña al niño que su valor depende de "
            "rendir. Default False: las auditorías viejas no afirman que pasó."
        ),
    )
    afirmo_algo_falso: bool = Field(
        default=False,
        description=(
            "El tutor afirmó algo que no era cierto: sobre la respuesta del "
            "niño (la dio por buena estando mal) o sobre lo que el niño ve en "
            "pantalla (narró un dibujo que no se mostró). "
            "Default False: las auditorías viejas no afirman que pasó."
        ),
    )
    notas: str | None = None


class AnalisisSesion(BaseModel):
    """Salida completa del Analista: las dos preguntas sobre la misma transcripción."""

    sesion_id: str
    observaciones: list[Observacion] = Field(default_factory=list)
    perfil_sugerido: PerfilPersonal | None = Field(
        default=None, description="Actualizaciones consolidadas de la mitad personal"
    )
    cumplimiento: AuditoriaCumplimiento
    resumen: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Vigilante  (agente #3)
# ─────────────────────────────────────────────────────────────────────────────


class NivelSeguridad(StrEnum):
    OK = "ok"
    ATENCION = "atencion"
    ALERTA = "alerta"
    CRITICO = "critico"


class EvaluacionSeguridad(BaseModel):
    """Veredicto del Vigilante sobre una ventana de 3-4 turnos.

    Ventana, no turno suelto: un turno sin contexto es ambiguo, los patrones
    preocupantes viven ENTRE turnos.
    """

    nivel: NivelSeguridad
    categoria: str | None = None
    evidencia: str | None = None
    requiere_escalamiento: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Compañero del Papá  (agente #1)
# ─────────────────────────────────────────────────────────────────────────────


class MetricasReporte(BaseModel):
    """Los hechos, calculados en CÓDIGO.

    El agente redacta a partir de esto y no puede afirmar nada que no esté acá.
    Se verifica en código que los números del texto coincidan.
    """

    sesiones: int
    minutos_totales: int
    habilidades_dominadas: list[str] = Field(default_factory=list)
    habilidades_en_progreso: list[str] = Field(default_factory=list)
    cumplimiento_metodo: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="% de sesiones donde el método socrático se sostuvo. None si "
        "todavía no se auditó ninguna: nunca se midió NO es lo mismo que salió bien.",
    )

    metodo_actual: str | None = Field(
        default=None,
        description=(
            "Cómo se le está enseñando ahora, en palabras del papá. `None` si "
            "todavía no hay ninguna técnica medida — no se afirma nada."
        ),
    )
    metodo_anterior: str | None = Field(
        default=None,
        description="El que se abandonó, si se cambió de método en este período.",
    )
    porque_cambio: str | None = Field(
        default=None,
        description=(
            "La razón del cambio, calculada en código a partir de la ganancia "
            "medida. Es la frase que contesta «¿por qué cambió de método?», y "
            "el reporte NO puede inventarla: llega hecha."
        ),
    )

    grado_de_trabajo: int = Field(
        description="En qué grado está trabajando de verdad, según lo que domina"
    )
    adelanto_grados: int = Field(
        default=0,
        description=(
            "Grados por encima (+) o por debajo (−) del grado escolar. "
            "Positivo se destaca en el reporte: es de lo más potente que puede leer un papá."
        ),
    )


class ReporteParaPapa(BaseModel):
    nino_id: str
    desde: datetime
    hasta: datetime
    metricas: MetricasReporte
    contenido: str = Field(
        description="Prosa generada por el agente. Es lo que AFIRMA sobre el niño, "
        "y lo único que `verificar_reporte` puede chequear contra las métricas."
    )
    sugerencia: str | None = Field(
        default=None,
        description="Una actividad para hacer en casa. Va aparte porque PROPONE "
        "en vez de afirmar: sus números son de la actividad, no del niño.",
    )
