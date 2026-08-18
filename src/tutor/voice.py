"""Configuración de la sesión de voz y emisión del token efímero.

El audio NO pasa por acá. El navegador conecta directo a Gemini Live; este
módulo arma la configuración y firma el token que la deja atada.
Ver ARCHITECTURE.md §10.

Lo que hace este archivo es, en la práctica, **el candado #1**: la persona, el
playbook socrático y la política de seguridad viajan atados al token, así que el
navegador no puede cambiarlos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from . import config as cfg

# ─────────────────────────────────────────────────────────────────────────────
# Parámetros de audio (verificados — ver ARCHITECTURE.md §10)
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_RATE_ENTRADA = 16_000
"""Lo exige Gemini. Con otro valor no entiende o distorsiona."""

SAMPLE_RATE_SALIDA = 24_000
"""Es lo que devuelve. Reproducirlo a otra frecuencia altera el tono de la voz."""

MIME_ENTRADA = f"audio/pcm;rate={SAMPLE_RATE_ENTRADA}"


# ─────────────────────────────────────────────────────────────────────────────
# Detección de fin de turno — la perilla que importa para niños
# ─────────────────────────────────────────────────────────────────────────────


class DeteccionFinTurno(BaseModel):
    """Cuánto silencio esperar antes de dar por terminado el turno del niño.

    Los defaults del modelo están pensados para adultos. Un chico de 7 años hace
    pausas largas mientras piensa — y cortarle la frase justo cuando está
    razonando es lo peor que puede pasar en método socrático.
    """

    silencio_ms: int = Field(description="Silencio antes de cerrar el turno")
    padding_inicio_ms: int = Field(
        default=300, description="Audio previo que se incluye al detectar voz"
    )
    sensibilidad_inicio: str = "START_SENSITIVITY_LOW"
    """LOW = menos disparos falsos. Un chico que murmura no abre turno."""

    sensibilidad_fin: str = "END_SENSITIVITY_LOW"
    """LOW = más paciencia para cerrar. Es lo que le da tiempo a pensar."""

    def a_dict_gemini(self) -> dict:
        return {
            "automaticActivityDetection": {
                "startOfSpeechSensitivity": self.sensibilidad_inicio,
                "endOfSpeechSensitivity": self.sensibilidad_fin,
                "prefixPaddingMs": self.padding_inicio_ms,
                "silenceDurationMs": self.silencio_ms,
            }
        }


def deteccion_para_edad(edad: int) -> DeteccionFinTurno:
    """Más chico, más paciencia.

    Un nene de 5 recién está armando la frase mientras habla; uno de 10 ya
    responde parecido a un adulto. Un solo valor para todos molesta a los dos
    extremos.
    """
    if edad <= 6:
        return DeteccionFinTurno(silencio_ms=2000)
    if edad <= 8:
        return DeteccionFinTurno(silencio_ms=1500)
    return DeteccionFinTurno(silencio_ms=cfg.SILENCIO_FIN_TURNO_MS)


# ─────────────────────────────────────────────────────────────────────────────
# Voz y acento
# ─────────────────────────────────────────────────────────────────────────────

IDIOMA_VOZ = "es-CO"
"""Español de Colombia. Inclina el acento del habla hacia el bogotano.

Ojo: el acento es SOLO la mitad. Las palabras ("listo", "chévere", "un
momentico" vs. "tenés", "dale") salen del prompt, no de acá — el modelo imita
el registro de sus propias instrucciones. Ver tutor_persona.es.md."""

VOZ_POR_DEFECTO = "Leda"
"""La documentada como juvenil.

Historial de esta constante, porque el oído es el único juez acá:
  · Charon  — grave y adulta. Sonaba a locutor, no a hermano mayor.
  · Puck    — animada, pero al escucharla seguía siendo un adulto.
  · Leda    — juvenil                                        ← actual

Si tampoco convence, las que quedan: Achird (amistosa), Zephyr (brillante),
Aoede (suelta), Sulafat (cálida). Es cambiar esta constante y recargar: nada
más en el sistema depende de cuál sea."""

VOCES_CONOCIDAS = frozenset({
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
})
"""Por qué existe esta lista, si parece redundante:

`auth_tokens.create` acepta CUALQUIER nombre de voz sin chistar — se verificó
el 2026-08-17 mandando "NoExiste123" y devolvió un token válido. El error
recién aparece cuando el navegador intenta conectarse, o sea **con el niño
sentado enfrente**. Preferimos fallar acá, al abrir la sesión."""


# ─────────────────────────────────────────────────────────────────────────────
# Los 4 tools, en el formato de function calling
# ─────────────────────────────────────────────────────────────────────────────
# El modelo los llama durante la conversación; el navegador reenvía la llamada
# a nuestra API. check_answer NUNCA se reimplementa en el cliente: una sola
# implementación de lo que no puede estar mal.

DECLARACIONES_TOOLS: list[dict] = [
    {
        "name": "check_answer",
        "description": (
            "Verifica si la respuesta del niño es correcta. Usalo SIEMPRE antes de "
            "decirle si acertó: vos no calculás, esta herramienta calcula. "
            "Entiende números dichos en palabras."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ejercicio_id": {"type": "string"},
                "respuesta_nino": {
                    "type": "string",
                    "description": "Lo que dijo el niño, tal cual, sin interpretar",
                },
            },
            "required": ["ejercicio_id", "respuesta_nino"],
        },
    },
    {
        "name": "get_next_problem",
        "description": "Trae el siguiente ejercicio para practicar la habilidad de hoy.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "request_camera",
        "description": (
            "Pide al niño que muestre algo por la cámara: el cuaderno, la tarea, "
            "lo que escribió. Usalo cuando necesites ver para poder ayudar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string", "description": "Qué necesitás ver"}
            },
            "required": ["motivo"],
        },
    },
    {
        "name": "escalate_safety",
        "description": (
            "Levantá una alerta si el niño dice algo preocupante: que alguien le hace "
            "daño, que se quiere lastimar, que está solo o en peligro. Ante la duda, "
            "usala. Seguí acompañándolo mientras tanto."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string"},
                "evidencia": {"type": "string", "description": "Cita textual"},
            },
            "required": ["motivo"],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Armado del prompt de sesión
# ─────────────────────────────────────────────────────────────────────────────


def cargar_prompt(nombre: str, idioma: str = cfg.IDIOMA_POR_DEFECTO) -> str:
    """Lee un prompt de knowledge/prompts/.

    Los prompts son DATOS: cambiar el comportamiento del tutor edita un .md,
    no este archivo.
    """
    ruta = cfg.PROMPTS / f"{nombre}.{idioma}.md"
    if not ruta.exists():
        raise FileNotFoundError(f"Falta el prompt: {ruta}")
    return ruta.read_text(encoding="utf-8").strip()


def construir_instruccion_sistema(
    resumen_nino: str, modo: str = "guiado", idioma: str = cfg.IDIOMA_POR_DEFECTO
) -> str:
    """Persona + método + seguridad + este niño.

    Se mantiene FLACO (ARCHITECTURE.md §9): nunca el currículum entero ni la
    historia completa. Solo lo que cambia la conducta del tutor en esta sesión.
    """
    partes = [
        cargar_prompt("tutor_persona", idioma),
        cargar_prompt("socratic_playbook", idioma),
        cargar_prompt("safety_policy", idioma),
        f"# Este niño\n\n{resumen_nino}",
    ]

    if modo == "pedido":
        partes.append(
            "# Hoy trae su propia agenda\n\n"
            "El niño viene con una tarea o una duda del colegio. Usá eso como "
            "material: aplicás la MISMA escalera de pistas, más estricta que "
            "nunca. Ayudarlo con la tarea no es hacerle la tarea."
        )

    return "\n\n---\n\n".join(partes)


# ─────────────────────────────────────────────────────────────────────────────
# Configuración de sesión
# ─────────────────────────────────────────────────────────────────────────────


class ConfiguracionSesion(BaseModel):
    """Todo lo que queda ATADO al token efímero.

    El navegador recibe un token, no una configuración: no puede cambiar la
    persona, el playbook ni la política de seguridad.
    """

    modelo: str = cfg.MODELO_TUTOR_VOZ
    voz: str = VOZ_POR_DEFECTO
    idioma_voz: str = IDIOMA_VOZ
    instruccion_sistema: str
    deteccion: DeteccionFinTurno
    tools: list[dict] = Field(default_factory=lambda: list(DECLARACIONES_TOOLS))

    @field_validator("voz")
    @classmethod
    def _voz_conocida(cls, v: str) -> str:
        if v not in VOCES_CONOCIDAS:
            raise ValueError(
                f"Voz desconocida: {v!r}. Google acepta el token igual y "
                f"revienta al conectar, con el niño esperando. "
                f"Conocidas: {', '.join(sorted(VOCES_CONOCIDAS))}"
            )
        return v

    def a_dict_gemini(self) -> dict:
        """La forma que espera `ai.live.connect(config=...)`."""
        return {
            "responseModalities": ["AUDIO"],
            "systemInstruction": self.instruccion_sistema,
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.voz}},
                "languageCode": self.idioma_voz,
            },
            # Sin estos dos no hay transcripción, y sin transcripción no hay
            # Analista, ni Vigilante, ni auditoría del método.
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
            "realtimeInputConfig": self.deteccion.a_dict_gemini(),
            "tools": [{"functionDeclarations": self.tools}],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Emisión del token
# ─────────────────────────────────────────────────────────────────────────────


class TokenEfimero(BaseModel):
    token: str
    modelo: str
    expira_en_segundos: int


class EmisorDeTokens(ABC):
    """Frontera con Google. Aislada para poder testear sin API key y para poder
    cambiar de proveedor tocando un solo archivo."""

    @abstractmethod
    def emitir(self, configuracion: ConfiguracionSesion) -> TokenEfimero: ...


class EmisorFalso(EmisorDeTokens):
    """Para tests y evals. No toca la red."""

    def __init__(self) -> None:
        self.emitidos: list[ConfiguracionSesion] = []

    def emitir(self, configuracion: ConfiguracionSesion) -> TokenEfimero:
        self.emitidos.append(configuracion)
        return TokenEfimero(
            token=f"falso-{len(self.emitidos)}",
            modelo=configuracion.modelo,
            expira_en_segundos=60,
        )


class EmisorGoogle(EmisorDeTokens):
    """Token efímero real, con la configuración atada.

    `uses=1` y un minuto de ventana: si alguien lo intercepta, tiene un intento
    y sesenta segundos. La API key nunca sale del servidor.

    ⚠️ SIN VERIFICAR con API key real: que `liveConnectConstraints` ate de
    verdad la configuración es el supuesto sobre el que se apoya el candado #1
    (ARCHITECTURE.md §10). Si no lo hiciera, hay que reevaluar el proxy.
    """

    VENTANA_APERTURA_SEG = 60
    VIDA_MAXIMA_SEG = 30 * 60

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Falta GOOGLE_API_KEY")
        self._api_key = api_key

    def emitir(self, configuracion: ConfiguracionSesion) -> TokenEfimero:
        from datetime import datetime, timedelta

        from google import genai  # import perezoso: los módulos puros no lo cargan

        ahora = datetime.now(UTC)
        cliente = genai.Client(api_key=self._api_key, http_options={"api_version": "v1alpha"})

        token = cliente.auth_tokens.create(
            config={
                "uses": 1,
                "new_session_expire_time": (
                    ahora + timedelta(seconds=self.VENTANA_APERTURA_SEG)
                ).isoformat(),
                "expire_time": (ahora + timedelta(seconds=self.VIDA_MAXIMA_SEG)).isoformat(),
                # EL CANDADO: la configuración queda fijada del lado del servidor.
                "live_connect_constraints": {
                    "model": configuracion.modelo,
                    "config": configuracion.a_dict_gemini(),
                },
            }
        )

        return TokenEfimero(
            token=token.name,
            modelo=configuracion.modelo,
            expira_en_segundos=self.VENTANA_APERTURA_SEG,
        )


def emisor_por_defecto() -> EmisorDeTokens:
    """Google si hay API key; falso si no. Permite desarrollar sin llave."""
    import os

    api_key = os.getenv("GOOGLE_API_KEY", "")
    return EmisorGoogle(api_key) if api_key else EmisorFalso()


def ruta_prompts_existentes(idioma: str = cfg.IDIOMA_POR_DEFECTO) -> list[Path]:
    """Para diagnóstico: qué prompts hay cargados."""
    return sorted(cfg.PROMPTS.glob(f"*.{idioma}.md"))
