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


class Habilidad(BaseModel):
    """Un nodo del grafo de habilidades.

    Los prerrequisitos forman un DAG: para trabajar este nodo, los prerrequisitos
    deben estar dominados. El planificador navega esa estructura (en código).
    """

    id: str = Field(description="Llave estable. Nunca se traduce. Ej: mat.suma.con_reagrupacion")
    nombre: TextoLocalizado
    descripcion: TextoLocalizado
    materia: Materia
    grado_sugerido: int = Field(ge=1, le=5)
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

    intereses: list[str] = Field(default_factory=list)
    motivadores: list[str] = Field(default_factory=list, description="Qué lo impulsa")
    frustraciones: list[str] = Field(default_factory=list, description="Qué lo traba o lo apaga")
    estilo_comunicacion: str | None = Field(
        default=None, description="Cómo le gusta que le hablen"
    )
    notas: str | None = Field(default=None, description="Texto consolidado, no un log")

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

    habilidad_id: str | None = None
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
    cumplimiento_metodo: float = Field(
        ge=0.0, le=1.0, description="% de sesiones donde el método socrático se sostuvo"
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
    contenido: str = Field(description="Prosa generada por el agente")
