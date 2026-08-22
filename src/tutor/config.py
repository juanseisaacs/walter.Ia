"""Configuración: rutas, llaves, presupuestos y política de retención.

Los presupuestos y la retención NO son detalles operativos — son decisiones de
arquitectura (ver ARCHITECTURE.md §12). Viven acá para que sean visibles y
cambiables en un solo lugar.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Se carga acá porque config.py lo importa todo lo demás. Sin esto, uvicorn
# arranca sin las llaves y el emisor de tokens cae en el falso — la sesión se
# abre igual, pero el navegador no se puede conectar a Gemini.
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Rutas
# ─────────────────────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parents[2]

KNOWLEDGE = RAIZ / "knowledge"
CURRICULUM = KNOWLEDGE / "curriculum"
PROMPTS = Path(os.environ["PROMPTS_DIR"]) if os.getenv("PROMPTS_DIR") else KNOWLEDGE / "prompts"
"""Los prompts son datos: el directorio se puede apuntar a otro lado para
comparar dos versiones sin tocar código ni perder las actuales.

    $env:PROMPTS_DIR = "knowledge/prompts_ab_flaco"

Sin la variable, los de siempre."""

DATOS = Path(os.environ["DATOS_DIR"]) if os.getenv("DATOS_DIR") else RAIZ / "data"
"""Dónde vive todo lo de runtime: la base, las transcripciones, los reportes.

Mismo patrón que `PROMPTS_DIR`, y por la misma razón — poder apuntar a otro
lado sin tocar código:

    $env:DATOS_DIR = "C:\\tmp\\prueba"

Lo pide la prueba de voz de punta a punta (`scripts.e2e_voz`), que levanta el
backend contra una base desechable. Sin esto, cada corrida dejaría un niño
inventado y una sesión de prueba entre los datos de verdad — que es justo lo
que ya ensuciamos con las 19 sesiones vacías anotadas en `PENDIENTE.md`.

Sin la variable, `data/` de siempre."""

DB = DATOS / "tutor.db"
TRANSCRIPCIONES = DATOS / "transcripts"
REPORTES = DATOS / "reports"


# ─────────────────────────────────────────────────────────────────────────────
# Idioma
# ─────────────────────────────────────────────────────────────────────────────

IDIOMA_POR_DEFECTO = "es"
"""Los prompts se cargan como {nombre}.{idioma}.md"""


NOMBRE_TUTOR = "Walter"
"""Cómo se llama el tutor cuando el niño le pregunta.

No es decoración: sin un nombre fijo el modelo se inventaba uno distinto cada
sesión, y un tutor que ayer se llamaba otra cosa no es el mismo que lo conoce
desde marzo. Eso pega justo donde el producto promete memoria longitudinal.

Vive acá y no en el .md porque es lo primero que va a variar: por país, o el día
que la familia pueda elegirlo. Un solo lugar que cambiar."""


# ─────────────────────────────────────────────────────────────────────────────
# Modelos
# ─────────────────────────────────────────────────────────────────────────────

MODELO_TUTOR_VOZ = os.getenv("MODELO_TUTOR_VOZ", "gemini-3.1-flash-live-preview")
"""Verificado disponible el 2026-08-17 con `client.models.list()`.

Alternativas Live confirmadas en esa misma consulta:
  · gemini-2.5-flash-native-audio-latest        (audio nativo, más expresivo)
  · gemini-2.5-flash-native-audio-preview-12-2025
  · gemini-3.5-live-translate-preview           (traducción, no aplica)

Todas en preview: los IDs pueden cambiar. Si un día devuelve 404, volver a
correr models.list() en vez de adivinar."""
MODELO_ANALISTA = "claude-haiku-4-5"
MODELO_VIGILANTE = "claude-haiku-4-5"
MODELO_COMPANERO_PAPA = "claude-sonnet-5"
MODELO_GENERADOR = "claude-haiku-4-5"


# ─────────────────────────────────────────────────────────────────────────────
# Presupuestos — protegen el margen del negocio
# ─────────────────────────────────────────────────────────────────────────────
# Se cobra suscripción fija; sin techo, el costo por niño es ilimitado.

MAX_MINUTOS_SESION = 45
MAX_COSTO_MES_USD_POR_NINO = 8.0

# Los dos que hay que soltar para probar. Se leen del entorno, pero NO los pases
# por el shell en Windows: `VAR=x python ...` en Git Bash no propaga a un .exe y
# `export` no sobrevive al lanzamiento en segundo plano. El servidor arranca
# igual, sin avisar, con los topes de producción — y se pierde un rato
# entendiendo por qué la API contesta 429 con el cupo "en 100".
# Para probar: `python -m scripts.servidor_pruebas`, que los pone en el proceso.
MAX_TOKENS_SESION = int(os.getenv("MAX_TOKENS_SESION", "150000"))
MAX_SESIONES_DIA = int(os.getenv("MAX_SESIONES_DIA", "3"))


# ─────────────────────────────────────────────────────────────────────────────
# Retención de datos de menores  (Ley 1581 CO / COPPA US)
# ─────────────────────────────────────────────────────────────────────────────
# El activo es la ficha estructurada, NO la conversación cruda. Una vez que el
# Analista extrajo las señales, la transcripción ya cumplió su función.

DIAS_RETENCION_TRANSCRIPCION = 30


# ─────────────────────────────────────────────────────────────────────────────
# Reporte al papá
# ─────────────────────────────────────────────────────────────────────────────

URL_PANEL = os.getenv("URL_PANEL", "http://localhost:8000")
"""Base de los enlaces que van al correo del papá.

Vive en el entorno porque cambia con el despliegue, y un enlace apuntando a
localhost en el correo de un papá es un enlace muerto."""

DIAS_PERIODO_REPORTE = 7
"""Semanal. Más seguido no hay novedad que contar (y un reporte sin novedad
enseña al papá a no abrirlo); más espaciado, el papá se entera tarde de que su
hijo se trabó."""


# ─────────────────────────────────────────────────────────────────────────────
# Latencia y seguridad en vivo
# ─────────────────────────────────────────────────────────────────────────────

EJERCICIOS_A_PRECARGAR = 15
"""De la habilidad del día. En memoria al inicio: get_next_problem es ~0ms."""

EJERCICIOS_POR_VECINA = 4
"""De cada habilidad de la frontera del niño, para cuando cambia de tema.

Pocos a propósito: alcanzan para sostener el desvío sin inflar la precarga.
Si el niño se queda en el tema nuevo, `recargar_ejercicios` trae más."""

VENTANA_VIGILANTE = 4
"""Turnos por ventana. Ventana y no turno suelto: un turno sin contexto es
ambiguo; los patrones preocupantes viven ENTRE turnos."""

SILENCIO_FIN_TURNO_MS: dict[str, int] = {
    "hasta_6": 1200,
    "de_7_a_8": 900,
    "desde_9": 700,
}
"""Cuánto silencio esperar para decidir que el niño terminó de hablar.

**Es el impuesto plano de cada turno.** El niño deja de hablar y no pasa nada
durante este tiempo: recién ahí el modelo empieza a pensar. Se paga igual
después de "hola" que después de una división larga.

Bajado el 20/08 (2000/1500/1200 → 1200/900/700) por dos razones medidas:

1. **La paciencia real la da `END_SENSITIVITY_LOW`, no este número.** Los dos
   estaban al máximo y se sumaban. La sensibilidad baja es la que tolera la
   pausa a mitad de frase —es lo que evita cortar al que está pensando—; este
   temporizador solo pone un piso, y el piso lo pagan todos los turnos.
2. **Si nos adelantamos, no se rompe nada.** El navegador maneja `interrupted`:
   si el niño sigue hablando encima, el tutor corta la reproducción al instante
   (`useTutor.ts`). Equivocarse por rápido cuesta una interrupción; equivocarse
   por lento le costó al niño preguntar *"¿por qué te demoraste tanto?"* en su
   primer turno (sesión `ses_764305b3c3ed`, 20/08).

Sigue siendo más generoso que un default de adulto (500-800 ms) en las tres
bandas. Si el niño se siente cortado mientras piensa, **este es el número que se
sube, y solo este** — no hace falta tocar código."""


# ─────────────────────────────────────────────────────────────────────────────
# Auditoría
# ─────────────────────────────────────────────────────────────────────────────

AUDITAR_PORCENTAJE_SESIONES = 1.0
"""100%. El Analista ya lee todas las transcripciones; auditar el método sale
casi gratis y permite decirle al papá 'se cumplió en las 12 sesiones del mes'
en vez de 'en la muestra que revisamos'."""
