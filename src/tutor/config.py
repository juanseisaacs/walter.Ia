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

DATOS = RAIZ / "data"
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
MAX_TOKENS_SESION = 150_000
MAX_SESIONES_DIA = 3
MAX_COSTO_MES_USD_POR_NINO = 8.0


# ─────────────────────────────────────────────────────────────────────────────
# Retención de datos de menores  (Ley 1581 CO / COPPA US)
# ─────────────────────────────────────────────────────────────────────────────
# El activo es la ficha estructurada, NO la conversación cruda. Una vez que el
# Analista extrajo las señales, la transcripción ya cumplió su función.

DIAS_RETENCION_TRANSCRIPCION = 30


# ─────────────────────────────────────────────────────────────────────────────
# Reporte al papá
# ─────────────────────────────────────────────────────────────────────────────

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

SILENCIO_FIN_TURNO_MS = 1200
"""Cuánto silencio esperar para decidir que el niño terminó de hablar.

Los niños hacen pausas largas mientras piensan. Cortarlos ahí es lo peor que
puede pasar en método socrático. A calibrar por edad."""


# ─────────────────────────────────────────────────────────────────────────────
# Auditoría
# ─────────────────────────────────────────────────────────────────────────────

AUDITAR_PORCENTAJE_SESIONES = 1.0
"""100%. El Analista ya lee todas las transcripciones; auditar el método sale
casi gratis y permite decirle al papá 'se cumplió en las 12 sesiones del mes'
en vez de 'en la muestra que revisamos'."""
