"""Endpoints HTTP para el frontend (FastAPI).

Frontera deliberada: el backend no sabe qué frontend lo llama. Hoy es una web en
React; mañana es la misma API detrás de una app en las tiendas. Por eso ninguna
lógica vive acá — esto solo traduce HTTP a llamadas de los otros módulos.

FASE 7 implementa:

  Niño
    POST /sesiones                 abrir sesión (devuelve modo y nodo inicial)
    POST /sesiones/{id}/reanudar   retomar una sesión interrumpida
    WS   /sesiones/{id}/voz        canal de audio en tiempo real

  Papá
    POST /onboarding               entrevista inicial
    GET  /ninos/{id}/reporte       último reporte semanal
    GET  /ninos/{id}/progreso      ficha académica resumida
    GET  /ninos/{id}/cumplimiento  evidencia de que el método se sostuvo
    PUT  /ninos/{id}/limites       horarios, temas vedados, tope de sesiones

Los tres últimos son criterio #4 de YC (parent trust): transparencia, evidencia
y control. Un reporte semanal solo no construye confianza.
"""
