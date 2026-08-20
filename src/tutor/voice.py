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
    sensibilidad_inicio: str = "START_SENSITIVITY_HIGH"
    """Qué tan fácil es que la voz del niño ABRA un turno.

    Estuvo en LOW hasta el 20/08, con esta justificación: *"menos disparos
    falsos, un chico que murmura no abre turno"*. Esa frase describía la
    intención y también el bug — resulta que un niño **contestando** murmura.

    Medido en `ses_c973ffe7b267`: el tutor preguntó cuánto daba 4+4+4+4+4,
    Felipe dijo "veinte" bajito, el turno nunca se abrió y ese audio se
    descartó. En la transcripción no existe. Dos turnos después:

        nino:  "Ya te dije que 20 te dije, ¿no me escuchaste?"
        tutor: "¡Uy, qué pena, no te alcancé a oír!"

    Los dos errores no cuestan lo mismo. Un disparo falso abre un turno vacío y
    el tutor sigue —molesto y recuperable—. Perder la respuesta del niño le
    enseña que no lo escuchan, que es exactamente lo que un tutor no puede
    hacer. Con `padding_inicio_ms` de 300 ms el arranque de la palabra se
    conserva igual.

    Si aparecen turnos vacíos por ruido de fondo, esto vuelve a LOW — pero
    entonces hay que subir el volumen del micrófono, no bajarle el oído al
    tutor."""

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

    Los tres valores viven en `config.SILENCIO_FIN_TURNO_MS`: es la perilla que
    más se va a mover con niños de verdad, y moverla no debería tocar código.
    """
    if edad <= 6:
        return DeteccionFinTurno(silencio_ms=cfg.SILENCIO_FIN_TURNO_MS["hasta_6"])
    if edad <= 8:
        return DeteccionFinTurno(silencio_ms=cfg.SILENCIO_FIN_TURNO_MS["de_7_a_8"])
    return DeteccionFinTurno(silencio_ms=cfg.SILENCIO_FIN_TURNO_MS["desde_9"])


# ─────────────────────────────────────────────────────────────────────────────
# Voz y acento
# ─────────────────────────────────────────────────────────────────────────────

IDIOMA_VOZ = "es-CO"
"""Español de Colombia. Inclina el acento del habla hacia el bogotano.

Ojo: el acento es SOLO la mitad. Las palabras ("listo", "chévere", "un
momentico" vs. "tenés", "dale") salen del prompt, no de acá — el modelo imita
el registro de sus propias instrucciones. Ver tutor_persona.es.md."""

FRASES_ADAPTACION_ARITMETICA = (
    "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho",
    "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis",
    "diecisiete", "dieciocho", "diecinueve", "veinte", "treinta", "cuarenta",
    "cincuenta", "sesenta", "setenta", "ochenta", "noventa", "cien",
    "unidades", "decenas", "centenas",
    # Las centenas dichas enteras: el niño lee el número, no lo deletrea.
    "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos",
    "setecientos", "ochocientos", "novecientos", "mil",
    # Cómo descompone un niño de verdad. Sin estas, "siete de cien, dos de diez,
    # nueve de uno" se transcribió `7102191`: el reconocedor pasó cada palabra a
    # dígito y las pegó, y el tutor corrigió a un niño que había acertado.
    "grupos de cien", "grupos de diez", "grupitos de cien", "grupitos de diez",
    "de cien", "de diez", "de uno", "y sobran",
)
"""Sesga la transcripción hacia las palabras-número. Sin esto, un "dos" dicho por
un niño de 7 años se transcribió como "32" (ses_83af1a57e8c2) — y esa transcripción
es el ÚNICO insumo del Analista: un token mal oído lo congela y devuelve cero
señales. `adaptationPhrases` de AudioTranscriptionConfig existe justo para esto.
Verificado contra la API real (2026-08-18): el servidor Live acepta la config al
conectar. Que efectivamente corrija el "dos"→"32" hay que oírlo con audio real."""

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
# Los 5 tools, en el formato de function calling
# ─────────────────────────────────────────────────────────────────────────────
# El modelo los llama durante la conversación; el navegador reenvía la llamada
# a nuestra API. check_answer NUNCA se reimplementa en el cliente: una sola
# implementación de lo que no puede estar mal.

DECLARACIONES_TOOLS: list[dict] = [
    {
        "name": "check_answer",
        "description": (
            "Verifica si la respuesta del niño es correcta. Úsalo SIEMPRE antes de "
            "decirle si acertó: tú no calculas, esta herramienta calcula. "
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
        "name": "verify_arithmetic",
        "description": (
            "Verifica una cuenta que propusiste tú, fuera del banco de ejercicios. "
            "Úsalo SIEMPRE antes de decir si acertó, si está cerca o si le falta poco: "
            "tú no calculas, esta herramienta calcula. Entiende números en palabras. "
            "Devuelve si acertó y qué tan lejos quedó, nunca el resultado."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operacion": {
                    "type": "string",
                    "description": "La cuenta, con dos números y un signo. Ej: '578 - 34'",
                },
                "respuesta_nino": {
                    "type": "string",
                    "description": "Lo que dijo el niño, tal cual, sin interpretar",
                },
            },
            "required": ["operacion", "respuesta_nino"],
        },
    },
    {
        "name": "get_next_problem",
        "description": (
            "Trae el siguiente ejercicio ya revisado. Sin `habilidad_id` viene "
            "del tema de hoy. Con `habilidad_id` viene de ese tema, para cuando "
            "el niño quiere cambiar. Todo ejercicio que le pongas sale de acá."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "habilidad_id": {
                    "type": "string",
                    "description": (
                        "Tema pedido, tal cual aparece en la lista de ejercicios "
                        "de hoy. Se omite para seguir con el tema de la sesión."
                    ),
                }
            },
        },
    },
    {
        "name": "request_camera",
        "description": (
            "Pide al niño que muestre algo por la cámara: el cuaderno, la tarea, "
            "lo que escribió. Úsalo cuando necesites ver para poder ayudar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string", "description": "Qué necesitas ver"}
            },
            "required": ["motivo"],
        },
    },
    {
        "name": "escalate_safety",
        "description": (
            "Levanta una alerta si el niño dice algo preocupante: que alguien le hace "
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


def _bloque_temas(temas: list[tuple[str, str]], principal: str | None) -> str:
    """Los temas que el banco tiene cargados HOY, con su id.

    Sin esto el tutor no puede ofrecer lo que tiene ni pedirlo por id, y termina
    inventando ejercicios — que es como se pierde el registro del trabajo del
    niño (ver `BancoDeSesion`). Es la única parte del prompt que cambia en cada
    sesión: lo demás es quién es el tutor; esto es qué tiene en la mano.
    """
    lineas = ["# Los ejercicios que tienes hoy", ""]
    for hid, nombre in temas:
        marca = "   ← el de hoy" if hid == principal else ""
        lineas.append(f"- **{nombre}** · `{hid}`{marca}")
    lineas += [
        "",
        "Pides uno y te llega revisado. Sin decir tema, viene del de hoy; "
        "diciendo el tema, viene de ese. Si el niño quiere cambiar a otro de "
        "esta lista, se lo pides por su `código`.",
    ]
    return "\n".join(lineas)


def construir_instruccion_sistema(
    resumen_nino: str,
    modo: str = "guiado",
    idioma: str = cfg.IDIOMA_POR_DEFECTO,
    temas: list[tuple[str, str]] | None = None,
    tema_principal: str | None = None,
    primer_encuentro: bool = False,
) -> str:
    """Persona + método + valores + seguridad + este niño.

    Se mantiene FLACO (ARCHITECTURE.md §9): nunca el currículum entero ni la
    historia completa. Solo lo que cambia la conducta del tutor en esta sesión.

    El orden importa: la persona primero (el modelo imita el registro de lo que
    lee antes), la seguridad al final (lo último pesa más en el conflicto).

    `valores` se derivó de la Constitución (`knowledge/product/`) destilando SOLO
    las viñetas de comportamiento. La doctrina se quedó en el documento: el
    modelo necesita "jamás compares", no el principio que lo justifica.
    """
    partes = [
        f"Te llamas **{cfg.NOMBRE_TUTOR}**. Es tu nombre siempre, en toda sesión.",
        cargar_prompt("tutor_persona", idioma),
        cargar_prompt("socratic_playbook", idioma),
        cargar_prompt("valores", idioma),
        cargar_prompt("safety_policy", idioma),
        f"# Este niño\n\n{resumen_nino}",
    ]

    # El primer encuentro NO es texto permanente, y ese es el patrón que
    # mantiene el prompt flaco: lo que solo aplica a veces, entra solo a veces.
    # Un tutor que en la sesión 40 sigue leyendo cómo presentarse gasta atención
    # en algo que ya pasó, además de gastar espacio.
    if primer_encuentro:
        partes.append(cargar_prompt("primer_encuentro", idioma))

    if temas:
        partes.append(_bloque_temas(temas, tema_principal))

    if modo == "pedido":
        partes.append(
            "# Hoy trae su propia agenda\n\n"
            "El niño viene con una tarea o una duda del colegio. Usa eso como "
            "material: aplicas la MISMA escalera de pistas, más estricta que "
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
            #
            # La ENTRADA (voz del niño) va con idioma fijo y sesgo aritmético: el
            # `{}` vacío dejaba a Gemini autodetectar, y el ruido salía en coreano
            # y "dos" salía "32". Ver FRASES_ADAPTACION_ARITMETICA.
            "inputAudioTranscription": {
                "languageCodes": [self.idioma_voz],
                "adaptationPhrases": list(FRASES_ADAPTACION_ARITMETICA),
            },
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
        self._cliente = None

    def _obtener(self):
        """El cliente se arma UNA vez y se reusa, como el de Anthropic.

        Estaba dentro de `emitir()`: cada apertura de sesión levantaba un cliente
        nuevo, con su handshake TLS y su pool de conexiones desde cero. Eso corre
        justo después de que el niño aprieta el botón y antes de que pueda hablar
        — el peor lugar posible para pagar una conexión.
        """
        if self._cliente is None:
            from google import genai  # import perezoso: los módulos puros no lo cargan

            self._cliente = genai.Client(
                api_key=self._api_key, http_options={"api_version": "v1alpha"}
            )
        return self._cliente

    def emitir(self, configuracion: ConfiguracionSesion) -> TokenEfimero:
        from datetime import datetime, timedelta

        ahora = datetime.now(UTC)

        token = self._obtener().auth_tokens.create(
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
