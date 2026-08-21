# Pendiente — retomar acá

_Última poda: 2026-08-20, cierre del día._

> Este archivo se **poda**, no solo se agrega. El 20/08 tenía 25 secciones y
> ocho de los pendientes marcados en rojo ya estaban hechos hacía días — leerlo
> daba la sensación de una montaña que no existía. Un pendiente resuelto que
> sigue escrito acá no es memoria: es ruido, y el ruido esconde lo que sí falta.

---

## ✅ Dónde estamos parados

El circuito completo cierra **y está probado con voz real**: el niño habla, el
tutor usa el banco, `check_answer` verifica, el Analista escribe el dominio, el
planificador de mañana arranca con la evidencia de hoy, el reporte lo cuenta y
el papá lo lee en el panel. Más la cámara, la pizarra y la hoja de dibujo.

- **359 tests** de Python · **60** del front · **evals 45/45**
- **35 sesiones de voz reales**, la más larga de 9 minutos
- **13 habilidades** de matemáticas con triple anclaje · **417 ejercicios**
- 4 niños en la base, todos de prueba

---

## 🔴 Lo único que mueve la aguja

**Cinco niños que no seamos nosotros, una semana.**

El cuello de botella dejó de ser técnico hace días. Falta evidencia de que
alguien lo usa y vuelve, y eso no se simula ni se construye:

1. **¿Vuelve un niño sin que se lo pidan?** Es el dato que ningún competidor
   tiene y que ninguna feature reemplaza.
2. **¿Aprende?** Todo el sistema mide dominio y nadie verificó que ese número
   corresponda a aprendizaje real. Un pre/post simple lo responde.
3. **¿Aguanta 20 minutos?** Un niño de 7 se distrae, contesta con monosílabos y
   se levanta. El único usuario ha sido RBH, que quiere que funcione.

⚠️ Construir features antes de esto es sumar superficie sobre una hipótesis sin
validar.

---

## 🟡 Lo que decide RBH — nadie más puede

**1. El método de lectura.** Silábico, fonético, global o mixto. Esa elección
define el grafo entero de lectura: el orden de los nodos, qué es prerrequisito
de qué, cómo se ve un ejercicio. **Destraba los dos tercios del producto que hoy
no existen** — el producto promete lectura, escritura y aritmética, y solo hay
aritmética. Ojo: los DBA de Lenguaje del MEN **no descomponen la
decodificación**, así que esos nodos van a ser criterio nuestro, declarado como
propio (`FUENTES.md` §2.3).

**2. Diálogos modelo.** Cinco o seis conversaciones de ejemplo: el niño dice
esto, el tutor debería responder así, y esto otro sería inaceptable. Cada una se
vuelve un test. Es lo que convierte "me parece que va bien" en algo medible, y
lo que haría que "antes cantaba mejor" deje de ser suerte. Hay material de sobra
en las sesiones reales.

**3. Cuánto pregunta el onboarding**, y si el del papá es por texto o por voz.
El motor no sabe qué le llega: cambiarlo es la pantalla, no la arquitectura. Va
**después** del método de lectura — la entrevista pregunta distinto según cómo
vayamos a enseñar a leer.

### Aplazados con costo escrito (`ARCHITECTURE.md` §19)

- **Pruebas Saber 3° y 5°.** El argumento más fuerte frente a un papá
  colombiano. El límite lo pone la propia fuente: sin simulacros, sin ansiedad.
- **Abrir las cinco áreas.** Cuesta el patrón de `id`, el enum `Materia`, un
  YAML por área, el banco y las 4 suites de evals. Y los DBA de las áreas nuevas
  **no están verificados**: la única fuente que los tenía estaba corrida un
  grado (`FUENTES.md` §2.6). Abrir un área empieza por bajar su PDF del MEN.

---

## 🟢 Lo que puedo hacer yo, sin esperar a nadie

- **41 nodos de matemáticas para cubrir 1° a 5°** — ya investigados y propuestos
  en `FUENTES.md` §7.1, con su anclaje. Es transcribirlos.
- **Los nodos base de lectura**, en cuanto esté decidido el método (§7.2).
- **Corregir los trazos feos.** Los 60 glifos de `trazos.ts` se escribieron sin
  ver el render. Con que RBH mire `/pizarra` → "Ver todos los trazos" y diga
  cuáles están torcidos, se arreglan: es una línea por carácter.
- **Limpiar la base.** Hay dos Felipe (el onboarding corrió dos veces) y datos
  de prueba mezclados.

---

## ⚪ Abierto, sin urgencia

### De la Constitución (adoptada el 18/08, ver `ARCHITECTURE.md` §18)

- **La excepción de fe declarada** (§7). Hoy **toda** pregunta religiosa se
  devuelve a la familia. Implementarla pide tres cosas en orden: campo declarado
  por el padre —nunca inferido del niño—, pregunta en el onboarding, y revisión
  legal. `test_la_seguridad_no_implementa_la_excepcion_de_fe_declarada` falla el
  día que alguien lo haga: está puesto para que la decisión se tome mirando.
- **Confianza por dominio** (§3.3.6). Un niño puede sentirse capaz en fútbol y
  derrotado en matemáticas. `RegistroDominio.nivel` es competencia medida, no
  confianza sentida: son dos números distintos. ⚠️ Cuando se implemente nace en
  `None` y llega en `None` hasta el prompt — la lección de la fase 6.
- **Aviso suave al papá por tema de familia** (§7.4, §8.6): religión,
  sexualidad, política, noticias difíciles. No es un riesgo, es un aviso — un
  evento distinto de `escalate_safety`.
- **Que el Vigilante no escale travesuras.** El tutor ya distingue riesgo de
  travesura; falta confirmar que el Vigilante y el reporte tampoco conviertan
  una confesión menor en un evento. Vale un caso en `evals/safety/`.
- **Documento legal dedicado** — consentimientos, niveles de alerta,
  bifurcación intrafamiliar, retención, COPPA / Ley 1581. Es el pendiente #1 de
  la propia Constitución.
- **Diálogos modelo Nivel 1** (abuso, autolesión) — la Constitución es explícita
  en que se escriben **con el psicólogo infantil, nunca antes**.

### La cámara abre una puerta a la trampa

Con cámara el niño puede mostrar el ejercicio y esperar que el tutor lo resuelva.
Es la misma línea de siempre —ayudar ≠ hacer— por un camino nuevo: decir el
problema ya es trabajo, enfocar la cámara no. Tres formas sin cubrir: la página
entera de la tarea, la hoja de respuestas, y la foto en vez del intento.

Faltan las reglas propias de la cámara: ante varios ejercicios, elegir UNO y
preguntar por dónde empezaría; no leer en voz alta un enunciado que el niño
puede leer; y que **una foto no cuente como intento** en la escalera.

### Lo demás, chico

- **El techo de tokens no corta durante la sesión**, solo al abrir.
- **Nadie manda el reporte por mail.** Se genera y se guarda;
  `aviso_de_reporte()` existe y nadie lo dispara.
- **La verificación del reporte solo mira números.** Una afirmación cualitativa
  sin respaldo pasa. Verificarlo pediría un segundo modelo, y la regla del
  proyecto es que la verificación es código.
- **7 errores de lint preexistentes** (líneas largas, un `l` ambiguo).

### Medido y descartado

❌ **Prompt caching en los agentes offline.** El mínimo cacheable son 1024
tokens y los cuatro prompts están por debajo (medido el 18/08). Solo
`method_auditor` calificaría, y el ahorro son céntimos al mes. Se vuelve a mirar
si algún prompt offline crece mucho.

---

## Cerrado desde el 18/08 — por qué este archivo encogió

| Era un 🔴 | Qué pasó |
|---|---|
| El modo Pedido no se puede activar | Hay botón "Traigo una tarea" en la pantalla del niño |
| `request_camera` es un stub | Funciona: leyó las letras de una gorra y contó cinco dedos |
| No existe la primera sesión del niño | `primer_encuentro.es.md`, condicionado a `madurez_vinculo == 0` |
| El prompt está a 208 caracteres del techo | Adelgazado 7,3 KB moviendo el porqué a `knowledge/product/`; techos bajados a 36.000 y 35.000 |
| Falta una sesión de voz real | 35 sesiones reales |
| Referencias DBA provisionales | Triple anclaje, auditado nodo por nodo (`FUENTES.md` §2.5) |
| Enlaces mágicos en memoria | En la base desde el 18/08 |
| Frases cortadas, VAD sin calibrar | Silencio 1500 → 900 ms, oído más sensible, y barge-in local en el navegador |
| El dominio llevaba seis sesiones congelado | El tutor usa el banco; `habilidades_trabajadas` se llena |
| Un acierto se leyó como error | `Veredicto.NO_SE_ENTENDIO`; el playbook repregunta en vez de corregir |
| "Se siente lento" | Era `vite dev`. La API monta el build; el onboarding pasó de 7,2 s a 3,6 s por turno |
| La sesión larga se descartaba entera | La extracción pasó a tool use: el JSON dejó de llegar cortado |
| El tutor no sabía qué le contó el niño de sí mismo | `PerfilPersonal.datos_suyos` |
