"""Los 4 tools del tutor en vivo.

Módulo PURO — sin red. Todo se resuelve en memoria.
REGLA: ningún tool puede hacer una llamada de red. Ver ARCHITECTURE.md §9.

FASE 4 implementa:

  check_answer(habilidad_id, respuesta_niño, ejercicio) -> bool
      ~5ms. CÓDIGO DETERMINÍSTICO, jamás un modelo.
      Un "¡correcto!" a 7+5=13 destruye la confianza del papá para siempre.
      Para nodos con verificable_en_codigo=false (comprensión, redacción) el
      juicio vuelve al modelo, pero eso es la excepción explícita.

  get_next_problem(habilidad_id) -> Ejercicio
      ~0ms. Saca de la lista precargada al inicio de la sesión.
      NO consulta el banco durante la sesión.

  request_camera(motivo) -> None
      Pide ver el cuaderno o la tarea. Central en modo Pedido.

  escalate_safety(motivo, evidencia) -> None
      Segundo camino independiente a la alarma, además del Vigilante.
      Dos caminos = defensa en profundidad.

DESCARTADOS A PROPÓSITO:
  · record_observation → el Analista lo extrae después, sin costo de latencia
  · end_session        → la sesión termina sola (tiempo o cierre natural)
"""
