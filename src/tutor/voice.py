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
        "name": "mostrar_en_pizarra",
        # NON_BLOCKING es la diferencia entre que esto sirva y que estorbe.
        #
        # Un tool normal corta el turno: el modelo se calla, espera la respuesta
        # y arranca de nuevo. Eso es exactamente el silencio del que Felipe se
        # quejó ("¿te fuiste?"). Con esto el tutor SIGUE HABLANDO mientras el
        # tablero se pinta, que es lo que hace un profesor de verdad: escribe y
        # explica a la vez.
        "behavior": "NON_BLOCKING",
        "description": (
            "Escribe en la pizarra que el niño ve al lado tuyo, SIN dejar de "
            "hablar. Es tu tablero: cuando el niño pide ver algo, dibujarlo o "
            "que se lo hagas más visual, se lo muestras acá. "
            "Cómo se traduce lo que el niño pide (son ejemplos de FORMATO, no "
            "cosas para mostrar ahora): si hablan de 2 canastas con 9 manzanas → "
            "grupos=2, por_grupo=9, nombre='canastas'; si escriben 56 más 38 → "
            "operacion a=56 b=38 op='+'; si saltan del 7 al 12 → recta desde=0 "
            "hasta=20 marca=7 salta_a=12; si es una fracción → numerador y "
            "denominador; si es una letra → texto con SOLO esa letra en "
            "`contenido` (una letra o una palabra, nunca una frase). "
            "No la uses para decorar ni en cada turno: si lo que dices se entiende "
            "solo con la voz, no dibujes nada. Tú dices QUÉ mostrar; dónde ponerlo "
            "lo resuelve la pizarra. "
            "Dibujar no reemplaza hablar: cuando muestres algo, DI qué es y qué "
            "hacer con eso. Un tablero que aparece en silencio deja al niño "
            "mirando sin saber para qué — ya pasó. "
            "Habla del CONTENIDO, no del tablero: di 'son 3 cajas de 45' y no "
            "'ahí en la pizarra te lo estoy mostrando' — tú no ves su pantalla, y "
            "afirmarlo te deja mintiendo si algo falló. Si el niño dice que no ve "
            "nada, manda la pizarra otra vez con números más chicos en vez de "
            "pedirle que espere. "
            "MUESTRA UNA SOLA COSA A LA VEZ: cada llamada borra la anterior. Si "
            "quieres que vea VARIAS cosas juntas, van en UNA llamada — dos "
            "fracciones con `comparar_con`, varias palabras con `lista`. Nunca "
            "dos llamadas seguidas: el niño solo alcanza a ver la última. "
            "La herramienta te contesta qué quedó en pantalla, con los colores: "
            "usa ESO para hablarle. No digas 'el pedazo naranja' si no te lo dijo. "
            "Cuando cambien de tema, límpiala: lo de antes se queda ahí y confunde. "
            "Ya pasó — un niño preguntó por qué seguían las macetas en pantalla "
            "cuando hacía rato cantaban una canción."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": [
                        "operacion",
                        "grupos",
                        "recta",
                        "fraccion",
                        "texto",
                        "lista",
                        "limpiar",
                    ],
                    "description": (
                        "operacion: una cuenta en columna · grupos: N grupos de M "
                        "cosas · recta: recta numérica · fraccion: una fracción "
                        "partida · texto: UNA letra o palabra grande, escrita a "
                        "mano · lista: de dos a cuatro palabras, una debajo de "
                        "otra y cada una de un color · limpiar: borra el tablero, "
                        "para cuando cambian de tema y lo de antes ya no viene "
                        "al caso"
                    ),
                },
                "a": {"type": "number", "description": "operacion: primer número"},
                "b": {"type": "number", "description": "operacion: segundo número"},
                "op": {"type": "string", "enum": ["+", "−", "×", "÷"]},
                "resultado": {
                    "type": "number",
                    "description": (
                        "operacion: el resultado. NO lo pongas si el niño todavía "
                        "lo está resolviendo — la cuenta queda abierta para él."
                    ),
                },
                "llevada": {"type": "number", "description": "operacion: la que se lleva"},
                "grupos": {"type": "number", "description": "grupos: cuántos grupos"},
                "por_grupo": {"type": "number", "description": "grupos: cuántos en cada uno"},
                "nombre": {"type": "string", "description": "grupos: 'cajas', 'bolsas'"},
                "desde": {"type": "number", "description": "recta: número inicial"},
                "hasta": {"type": "number", "description": "recta: número final"},
                "marca": {"type": "number", "description": "recta: dónde está parado"},
                "salta_a": {"type": "number", "description": "recta: a dónde salta"},
                "numerador": {"type": "number"},
                "denominador": {"type": "number"},
                "comparar_con": {
                    "type": "object",
                    "description": (
                        "fraccion: la SEGUNDA fracción, al lado, para comparar. "
                        "Para '¿qué es más grande, un medio o un tercio?' va TODO "
                        "en esta sola llamada: numerador=1 denominador=2 y "
                        "comparar_con={numerador:1, denominador:3}. Dos llamadas "
                        "seguidas no muestran dos cosas — la segunda borra a la "
                        "primera. Se dibujan del mismo tamaño y de colores "
                        "distintos: la primera naranja, la segunda azul."
                    ),
                    "properties": {
                        "numerador": {"type": "number"},
                        "denominador": {"type": "number"},
                    },
                },
                "contenido": {"type": "string", "description": "texto: la letra o palabra"},
                "palabras": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "lista: de dos a cuatro palabras cortas para que las vea "
                        "JUNTAS. Si le vas a dar tres ejemplos, van todas acá en "
                        "una sola llamada: tres `texto` seguidos no muestran tres "
                        "palabras, muestran la última."
                    ),
                },
                "senalar": {
                    "type": "string",
                    # `primero` y `segundo` son las dos filas de la cuenta. La
                    # pizarra sabía rodearlas desde siempre y el tutor no podía
                    # pedirlas: faltaban acá. Lo encontró el test de contrato
                    # entre este enum y `Pizarra.caja()` — código que se leía
                    # igual que el vivo y no corría nunca.
                    "enum": [
                        "unidades", "decenas", "centenas", "llevada",
                        "resultado", "primero", "segundo",
                    ],
                    "description": (
                        "Rodea con el marcador la parte que estás nombrando. "
                        "`primero` y `segundo` son las dos filas de la cuenta, "
                        "para cuando dices «mira el número de arriba»"
                    ),
                },
                "tachar": {
                    "type": "string",
                    "enum": ["unidades", "decenas", "centenas", "resultado"],
                    "description": "Tacha lo que quedó mal, para corregirlo a la vista",
                },
            },
            "required": ["tipo"],
        },
    },
    {
        "name": "pedir_dibujo",
        "behavior": "NON_BLOCKING",
        "description": (
            "Abre una hoja en blanco para que el niño dibuje con el dedo o el "
            "mouse, y te la manda cuando termina. Úsala para trazar una letra o "
            "un número, o para que dibuje lo que está pensando. Sigue hablando "
            "mientras la acomoda: la hoja tarda en llenarse."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "consigna": {
                    "type": "string",
                    "description": "Qué le pides que dibuje. Corto. Ej: 'Dibújame la letra ñ'",
                }
            },
            "required": ["consigna"],
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


def instruccion_de_apertura(primer_encuentro: bool = False) -> str:
    """Lo que provoca que el TUTOR hable primero.

    No es parte del prompt de sesión: es un turno que el navegador manda apenas
    conecta, para que el modelo produzca audio sin esperar al niño.

    Hizo falta porque el tutor no abría la conversación **nunca**. Medido el
    22/08 sobre 71 transcripciones reales: el niño habla primero en las 52 que
    tienen contenido, el tutor en 0, y 19 quedaron vacías. Una de cada cuatro
    sesiones moría antes de la primera palabra — el chico abría la app, veía una
    cara que no le decía nada, y se iba.

    Todo lo demás ya estaba: `primer_encuentro.es.md` explica cómo presentarse y
    `session.abrir()` sabe cuándo es el primer día. Lo que faltaba era el
    disparo. Es el patrón de `BITACORA.md` una vez más — contenido escrito, sin
    nadie que lo invoque.

    El texto vive en `knowledge/prompts/`: cambiar cómo saluda el tutor no
    debería tocar Python, y esto es justo lo que se va a querer ajustar.
    """
    return cargar_prompt("apertura_primer_dia" if primer_encuentro else "apertura")


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
        "Pides uno y te llega revisado: sin tema viene el de hoy, con tema "
        "viene de ese. **Si pide uno que no está en la lista, díselo** — es que "
        "todavía le falta el paso previo. Cambiárselo sin avisar lo deja "
        "frustrado creyendo que no entiende.",
    ]
    return "\n".join(lineas)


def construir_instruccion_sistema(
    resumen_nino: str,
    modo: str = "guiado",
    idioma: str = cfg.IDIOMA_POR_DEFECTO,
    temas: list[tuple[str, str]] | None = None,
    tema_principal: str | None = None,
    primer_encuentro: bool = False,
    como_ensena: str | None = None,
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

    # CÓMO enseñar hoy. Va después del playbook —que es el método socrático,
    # innegociable— y antes de los temas: la técnica dice de qué forma explicar,
    # nunca si dar la respuesta. Ver `tecnicas.py`.
    if como_ensena:
        partes.append(como_ensena)

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
