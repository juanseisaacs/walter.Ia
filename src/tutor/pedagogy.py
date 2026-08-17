"""El cerebro: dominio, olvido, qué enseñar y cómo dar pistas.

Módulo PURO — sin red, sin I/O. Se testea en milisegundos.

Acá vive la pedagogía, en CÓDIGO. Todo lo que hay en este archivo podría haber
sido un agente LLM y deliberadamente no lo es: es cálculo, no criterio. Gratis,
instantáneo, predecible, auditable.

FASE 2 implementa:

  actualizar_dominio(registro, observaciones) -> RegistroDominio
      Recalcula el nivel a partir de aciertos, errores y pistas necesitadas.

  aplicar_decaimiento(registro, ahora) -> RegistroDominio
      El nivel baja con el tiempo sin práctica. Repaso espaciado.
      Un sistema que asume que el niño nunca olvida es falso y se nota rápido.

  siguiente_habilidad(nino, grafo) -> Habilidad | None
      EL PLANIFICADOR. Busca nodos cuyos prerrequisitos estén dominados y este
      no. Esto NO es un agente: con los mismos datos da siempre lo mismo.

  habilidades_para_repasar(nino, grafo, ahora) -> list[Habilidad]
      Nodos cuyo dominio decayó por debajo del umbral.

  siguiente_pista(habilidad, intentos_previos) -> NivelPista
      La escalera socrática. Escala de pregunta abierta → pista conceptual →
      pista concreta. NUNCA llega a la respuesta.

  resumen_para_prompt(nino) -> str
      Comprime la ficha a un párrafo. El prompt de sesión se mantiene flaco —
      nunca la historia completa.
"""
