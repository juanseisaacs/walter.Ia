"""Adaptador del modelo de voz en tiempo real.

Este archivo existe SOLO para que cambiar de proveedor de voz toque un archivo y
nada más. Es el borde donde una frontera se paga sola.

FASE 5 implementa:

  class ClienteVoz(ABC)
      conectar(prompt_sistema, tools)
      enviar_audio(chunk)
      recibir()                     → texto | tool_call | fin_de_turno
      cerrar()

  class ClienteGeminiLive(ClienteVoz)
      Implementación por defecto.

  class ClienteFalso(ClienteVoz)
      Para tests y evals: reproduce guiones sin gastar API ni tiempo real.
      Sin esto, testear session.py cuesta dinero y es lento.

DEGRADACIÓN (ARCHITECTURE.md §12): si la conexión cae hay un niño de 7 años
sentado ahí. El adaptador debe distinguir corte recuperable de fallo definitivo
y avisarle a session.py para que responda con calidez y guarde el estado.
"""
