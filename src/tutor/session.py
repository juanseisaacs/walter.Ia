"""Orquestador de la sesión en vivo.

Es el único lugar donde se coordinan tutor, tools, vigilante y persistencia.

FASE 5 implementa:

  abrir_sesion(nino_id, modo) -> Sesion
      ANTES de que el niño hable, todo el trabajo pesado:
        1. cargar la ficha del niño
        2. pedirle a pedagogy la siguiente habilidad
        3. PRECARGAR ejercicios en memoria (config.EJERCICIOS_A_PRECARGAR)
        4. armar el prompt de sesión — FLACO: persona + playbook +
           resumen compacto + nodo actual. Nunca el currículum entero.
        5. conectar el cliente de voz
      Durante la sesión no se piensa: se ejecuta.

  correr(sesion)
      El loop de turnos. Reglas inviolables:
        · el VIGILANTE corre EN PARALELO — jamás bloquea la respuesta
        · el prefiltro en código corre turno a turno, a 0ms
        · el vigilante LLM clasifica ventanas de config.VENTANA_VIGILANTE turnos
        · ninguna llamada de red salvo el modelo de voz
        · se chequean los presupuestos de config (tiempo y tokens)
        · el estado se guarda A MITAD de sesión, no solo al final

  elegir_modo(nino) -> ModoSesion
      Explícito al abrir: "¿seguimos donde quedamos o tenés tarea?"

  reanudar(sesion_id)
      Retoma una sesión INTERRUMPIDA sin que el niño pierda su trabajo.

  cerrar_sesion(sesion)
      Guarda transcripción y estado. Encola para el Analista.
"""
