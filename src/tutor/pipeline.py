"""Agentes offline. Latencia irrelevante por definición.

Cada agente es tres cosas: un prompt en knowledge/prompts/, un schema de salida,
y una llamada. No hay loop agéntico ni tool use acá — son funciones puras:
entra texto, sale JSON. Ver ARCHITECTURE.md §2.

Los prompts son DATOS: cambiar el comportamiento de un agente edita un .md,
no este archivo.

FASE 6 implementa:

  analizar_sesion(sesion, transcripcion) -> AnalisisSesion       [Haiku]
      Una sola llamada, dos preguntas sobre la misma transcripción:
        · señales de aprendizaje del NIÑO
        · auditoría de cumplimiento del TUTOR (100% de las sesiones)
      Fusionar ambas subió la auditoría de muestreo 10% a cobertura total.
      IDEMPOTENTE: no procesa una sesión con analizada=True.

  aplicar_analisis(nino, analisis) -> Nino
      La mitad académica la recalcula pedagogy (código).
      La mitad personal se CONSOLIDA, no se acumula.

  evaluar_seguridad(ventana_turnos) -> EvaluacionSeguridad       [Haiku]
      El Vigilante. Contexto limpio, sin persona, sin historia — por eso no es
      manipulable. Se invoca desde session.py EN PARALELO.

  entrevistar_papa(...) -> Nino                                  [Sonnet 5]
      Modo onboarding del Compañero del Papá. Resuelve el arranque en frío.

  generar_reporte(nino, metricas) -> ReporteParaPapa             [Sonnet 5]
      Modo reporte del Compañero del Papá. Los HECHOS se calculan en código y se
      le pasan; el agente solo redacta.
      NO puede afirmar nada fuera de los datos → verificar_reporte() lo chequea.

  verificar_reporte(reporte) -> bool
      CÓDIGO. Confirma que los números del texto coinciden con las métricas.
      Un reporte inflado es peor que ninguno: el papá lo detecta al hablar con
      su hijo.
"""
