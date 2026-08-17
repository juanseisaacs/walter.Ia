# "The Primer" — Request for Startups de Y Combinator

**Fuente:** https://www.ycombinator.com/rfs
**Ciclo:** Fall 2026 · Idea #1 de 13
**Autor:** Andrew Miklas

> Este documento no es inspiración: es **restricción de diseño**. Toda decisión
> de arquitectura se traza contra los cuatro criterios de abajo.

---

## El pedido

Tutoría AI **adaptativa** para **niños pequeños**, en **lectura, escritura y
aritmética**, a **escala de consumidor**.

Referencia explícita al Primer de *The Diamond Age* (Neal Stephenson): un libro
interactivo que *"se adapta a ella por completo"* y **se reconfigura a medida que
la niña crece**, con **paciencia ilimitada**, desarrollando pensamiento y
razonamiento — no solo transmitiendo contenido.

**Posicionamiento:** no reemplaza al maestro, lo **complementa**.

**Modelo de negocio:** empieza como compra del padre, con ambición de acompañar
al niño **durante años**.

**Por qué ahora:** los modelos frontera hacen plausible por primera vez la
enseñanza adaptativa de largo horizonte. Históricamente la tutoría uno a uno no
escalaba económicamente.

---

## Los 4 criterios de victoria

YC es explícito: ganar requiere excelencia en las cuatro.

### 1. Curriculum fidelity
Rigor y alineación educativa real. No un temario inventado.

### 2. Safety
Protección seria de menores. No un disclaimer.

### 3. Longitudinal memory
Comprensión sostenida del progreso individual del niño a lo largo del tiempo.

### 4. Parent trust
Credibilidad ante quien toma la decisión de compra.

---

## La advertencia

> *"El cementerio del edtech está lleno de 'ChatGPT para la tarea'."*

IA conversacional genérica envuelta en contenido educativo **fracasa**.

**Cómo nos separamos de eso:** ayudamos con la tarea, **nunca la hacemos**. La
tarea del colegio es materia prima para tutoría socrática — una oportunidad para
que el niño llegue solo a la respuesta.

Si esa línea se cruza aunque sea un poco, somos exactamente lo que YC dice que
fracasa. Por eso la auditoría de cumplimiento del método corre en el **100%** de
las sesiones, y por eso es evidencia que se le muestra al papá.

---

## Trazabilidad

| Criterio | Dónde vive en la arquitectura |
|---|---|
| Curriculum fidelity | Grafo con prerrequisitos + doble anclaje DBA / Core Knowledge + planificador determinístico → `ARCHITECTURE.md` §7 |
| Safety | Vigilante independiente + prefiltro + `escalate_safety` → §3 |
| Longitudinal memory | Ficha en dos mitades + consolidación + decaimiento → §10 |
| Parent trust | Auditoría 100% + reporte verificado + retención mínima → §12 |
