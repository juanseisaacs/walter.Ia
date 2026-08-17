"""El mapa: carga, valida y navega el grafo de habilidades.

Módulo PURO — sin red, sin I/O externo (solo lee YAML del repo).

El grafo es estático y compartido por todos los niños. Las decisiones por niño
viven en pedagogy.py.

FASE 1 implementa:
  · cargar_grafo()            → lee knowledge/curriculum/*.yaml
  · validar()                 → contra schema.json + detecta CICLOS en el DAG
  · habilidad(id)             → un nodo
  · prerequisitos_de(id)      → dependencias directas
  · desbloqueadas_por(id)     → qué habilita dominar este nodo
  · por_materia_y_grado(...)  → filtro

El validador debe rechazar: ciclos, prerrequisitos inexistentes, IDs duplicados.
Un grafo inválido no debe poder cargarse — falla ruidosamente al arrancar.
"""
