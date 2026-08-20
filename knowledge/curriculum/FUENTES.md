# Fuentes del currículum

Contra qué está anclado el grafo de habilidades, con la referencia y la URL de
cada afirmación. Este documento existe para responder la pregunta de YC —
*"¿contra qué está alineado?"* — sin inventar nada.

**Investigado el 2026-08-18.** Las tres fuentes que el fundador pidió anclar:
el MEN de Colombia, los currículos de homeschooling, y cómo trabaja un tutor
humano de refuerzo.

---

## Cómo leer este documento

Toda afirmación sobre un estándar oficial lleva marca de verificación:

| Marca | Qué significa |
|---|---|
| **[V]** | Verificado contra el documento primario descargado. Se puede citar. |
| **[C]** | Corregido: la referencia que teníamos estaba mal o imprecisa; aquí está la buena. |
| **[?]** | No pude confirmarlo. Va en §6 "No verificado". **No se usa como si fuera dato.** |

La regla dura del proyecto aplica también aquí: *la ausencia de evidencia se
dice, no se completa con un default*. Un hueco declarado sirve; un dato
inventado hace daño río abajo, porque termina en el reporte al papá.

---

## 1. Documentos primarios descargados

Los cinco documentos que sostienen todo lo que sigue. Descargados y leídos el
2026-08-18 (extracción de texto con `pdftotext -layout`).

| # | Documento | Emisor | URL | Tamaño |
|---|---|---|---|---|
| **D1** | Derechos Básicos de Aprendizaje · Matemáticas · **V.2** | MEN + Universidad de Antioquia | `https://www.colombiaaprende.edu.co/sites/default/files/files_public/2026-06/dba_matematicas-min.pdf` | 11.2 MB |
| **D2** | Derechos Básicos de Aprendizaje · Lenguaje · **V.2** | MEN | `https://www.colombiaaprende.edu.co/sites/default/files/files_public/2022-06/DBA_Lenguaje-min.pdf` | 6.0 MB |
| **D3** | Estándares Básicos de Competencias (Lenguaje, Matemáticas, Ciencias, Ciudadanas) | MEN, 2006 | `https://www.colombiaaprende.edu.co/sites/default/files/files_public/2022-06/Estandares_basicos_competencias-min.pdf` | 1.8 MB |
| **D4** | Mathematics Syllabus · Primary One to Six (2021, act. oct. 2025) | Ministry of Education, Singapur | `https://www.moe.gov.sg/api/media/92bff26d-b2b4-4535-b868-b8415c744b91/2021-Primary-Mathematics-Syllabus-P1-to-P6-Updated-October-2025.pdf` | 0.8 MB |
| **D5** | Core Knowledge Sequence · Content and Skill Guidelines K–8 | Core Knowledge Foundation, 2013 | `https://www.coreknowledge.org/wp-content/uploads/2016/09/CKFSequence_Rev.pdf` | 2.6 MB |

Página madre de la colección DBA en Colombia Aprende:
`https://www.colombiaaprende.edu.co/contenidos/coleccion/derechos-basicos-de-aprendizaje`

> **⚠️ Alerta legal sobre D5 (Core Knowledge).** El PDF declara en sus páginas
> preliminares licencia **Creative Commons Attribution-NonCommercial-ShareAlike
> 3.0 Unported**, con la cláusula explícita *"Noncommercial — You may not use
> this work for commercial purposes"* y *"Share Alike"*. Además:
> *"The Core Knowledge Foundation hereby grants permission for individual
> reproduction of the Core Knowledge Sequence **for noncommercial purposes**."*
> Copyright © 2013 Core Knowledge Foundation.
>
> RBH Tutor es un producto comercial. Citar el nombre de un estándar para
> declarar alineación es distinto de derivar contenido de él, pero **el campo
> `core_knowledge` del YAML hoy reproduce títulos de secciones del Sequence**.
> Esto necesita decisión del fundador antes de producción: o se limita a
> referencia nominativa mínima, o se pide licencia a la Core Knowledge
> Foundation, o se reemplaza el segundo anclaje por uno de licencia compatible.
> `CLAUDE.md` ya marcaba esto como pendiente; queda **confirmado que la licencia
> es NC-SA**, que era justo lo que faltaba saber. Ver §6.

---

## 2. Fuente 1 — Ministerio de Educación Nacional (Colombia)

### 2.1 Cómo está organizado el MEN, y por qué importa para el grafo

El MEN tiene **dos** documentos normativos que se complementan, y confundirlos
es la causa de casi todas las referencias imprecisas que teníamos:

- **Estándares Básicos de Competencias (2006, D3)** — organizados por **bandas
  de grados** (1°-3°, 4°-5°, 6°-7°…), no por grado. Dicen *qué debe poder hacer
  el niño al terminar la banda*. Están cortados en cinco pensamientos:
  numérico, espacial, métrico, aleatorio y variacional.
- **Derechos Básicos de Aprendizaje V.2 (D1, D2)** — organizados **grado por
  grado**, numerados. Cada DBA trae "Evidencias de aprendizaje" y un "Ejemplo".

**Para el grafo, la referencia útil es el DBA**, porque está numerado por grado
y por lo tanto es citable sin ambigüedad: *"DBA Matemáticas 2° · #3"*. El
Estándar sirve como marco de banda, no como llave.

Conteo de DBA por grado (verificado contando en D1 y D2):

| Grado | DBA Matemáticas | DBA Lenguaje |
|---|---|---|
| 1° | 10 | 8 |
| 2° | 11 | 8 |
| 3° | 11 | 8 |
| 4° | 11 | 8 |
| 5° | 12 | 8 |

### 2.2 DBA de Matemáticas 1° a 5° [V]

Transcripción del enunciado de cada DBA (D1). El texto es del MEN; se abrevia
donde el enunciado es largo, sin cambiar el sentido.

#### Grado 1° — 10 DBA

| # | Enunciado (MEN) | ¿Aritmética? |
|---|---|---|
| 1 | Identifica los usos de los números (como código, cardinal, medida, ordinal) y las operaciones (suma y resta) en contextos de juego, familiares, económicos, entre otros. | Sí |
| 2 | Utiliza diferentes estrategias para contar, realizar operaciones (suma y resta) y resolver problemas aditivos. | Sí |
| 3 | Utiliza las características posicionales del Sistema de Numeración Decimal (SND) para establecer relaciones entre cantidades y comparar números. | Sí |
| 4 | Reconoce y compara atributos que pueden ser medidos en objetos y eventos (longitud, duración, rapidez, masa, peso, capacidad, cantidad de elementos de una colección). | Medición |
| 5 | Realiza medición de longitudes, capacidades, peso, masa, entre otros; para ello utiliza instrumentos y unidades no estandarizadas y estandarizadas. | Medición |
| 6 | Compara objetos del entorno y establece semejanzas y diferencias empleando características geométricas de las formas bidimensionales y tridimensionales. | Geometría |
| 7 | Describe y representa trayectorias y posiciones de objetos y personas para orientar a otros o a sí mismo en el espacio circundante. | Geometría |
| 8 | Describe cualitativamente situaciones para identificar el cambio y la variación usando gestos, dibujos, diagramas, medios gráficos y simbólicos. | Variacional |
| 9 | **Reconoce el signo igual como una equivalencia entre expresiones con sumas y restas.** | Sí |
| 10 | Clasifica y organiza datos, los representa utilizando tablas de conteo y pictogramas sin escalas, y comunica los resultados. | Datos |

**Evidencias del DBA 1° #2 que importan para el grafo** (texto literal del MEN):
*"Realiza conteos (de uno en uno, de dos en dos, etc.) iniciando en cualquier
número"*; *"Determina la cantidad de elementos de una colección agrupándolos de
1 en 1, de 2 en 2, de 5 en 5"*; *"Describe y resuelve situaciones variadas con
las operaciones de suma y resta en problemas cuya estructura puede ser
a + b = ?, a + ? = c, o ? + b = c"*.

**Evidencias del DBA 1° #3**: *"Realiza composiciones y descomposiciones de
números de dos dígitos en términos de la cantidad de 'dieces' y de 'unos' que
los conforman"*; *"Halla los números correspondientes a tener 'diez más' o 'diez
menos'"*; *"Emplea estrategias de cálculo como 'el paso por el diez'"*.

> **Hallazgo:** el DBA 1° **no pone techo numérico**. No dice "hasta 100". El
> tope de 100 que usa nuestro nodo `mat.numeros.conteo_hasta_100` viene de Core
> Knowledge Grade 1 (*"Write numbers 0 – 100"*) y de Singapur P1 (*"Numbers up
> to 100"*), no del MEN. Es una decisión nuestra, defendible, pero hay que
> saber que es nuestra.

#### Grado 2° — 11 DBA

| # | Enunciado (MEN) | ¿Aritmética? |
|---|---|---|
| 1 | **Interpreta, propone y resuelve problemas aditivos (de composición, transformación y relación) que involucren la cantidad en una colección, la medida de magnitudes (longitud, peso, capacidad y duración de eventos) y problemas multiplicativos sencillos.** | Sí |
| 2 | **Utiliza diferentes estrategias para calcular (agrupar, representar elementos en colecciones, etc.) o estimar el resultado de una suma y resta, multiplicación o reparto equitativo.** | Sí |
| 3 | **Utiliza el Sistema de Numeración Decimal para comparar, ordenar y establecer diferentes relaciones entre dos o más secuencias de números con ayuda de diferentes recursos.** | Sí |
| 4 | Compara y explica características que se pueden medir, en la resolución de problemas relativos a longitud, superficie, velocidad, peso o duración de los eventos. | Medición |
| 5 | Utiliza patrones, unidades e instrumentos convencionales y no convencionales en procesos de medición, cálculo y estimación de magnitudes. | Medición |
| 6 | Clasifica, describe y representa objetos del entorno a partir de sus propiedades geométricas. | Geometría |
| 7 | Describe desplazamientos y referencia la posición de un objeto mediante nociones de horizontalidad, verticalidad, paralelismo y perpendicularidad. | Geometría |
| 8 | **Propone e identifica patrones y utiliza propiedades de los números y de las operaciones para calcular valores desconocidos en expresiones aritméticas.** | Sí |
| 9 | **Opera sobre secuencias numéricas para encontrar números u operaciones faltantes y utiliza las propiedades de las operaciones.** | Sí |
| 10 | Clasifica y organiza datos, los representa utilizando tablas de conteo, pictogramas con escalas y gráficos de puntos. | Datos |
| 11 | Explica, a partir de la experiencia, la posibilidad de ocurrencia o no de un evento cotidiano. | Aleatorio |

> **Hallazgo grande:** el término **"reparto equitativo" aparece literalmente en
> el DBA 2° #2**, junto con "multiplicación". Nuestro nodo
> `mat.division.reparto_equitativo` está etiquetado `grado_sugerido: 3`. El MEN
> lo pone en 2°. No es un error del grafo (la etiqueta no limita), pero sí una
> imprecisión de anclaje.

#### Grado 3° — 11 DBA

| # | Enunciado (MEN) | ¿Aritmética? |
|---|---|---|
| 1 | **Interpreta, formula y resuelve problemas aditivos de composición, transformación y comparación en diferentes contextos; y multiplicativos, directos e inversos, en diferentes contextos.** | Sí |
| 2 | **Propone, desarrolla y justifica estrategias para hacer estimaciones y cálculos con operaciones básicas en la solución de problemas.** | Sí |
| 3 | **Establece comparaciones entre cantidades y expresiones que involucran operaciones y relaciones aditivas y multiplicativas y sus representaciones numéricas.** | Sí (y fracciones) |
| 4 | Describe y argumenta posibles relaciones entre los valores del área y el perímetro de figuras planas. | Métrico |
| 5 | Realiza estimaciones y mediciones de volumen, capacidad, longitud, área, peso de objetos o la duración de eventos. | Medición |
| 6 | Describe y representa formas bidimensionales y tridimensionales de acuerdo con las propiedades geométricas. | Geometría |
| 7 | Formula y resuelve problemas que se relacionan con la posición, la dirección y el movimiento de objetos en el entorno. | Geometría |
| 8 | Describe y representa los aspectos que cambian y permanecen constantes en secuencias y en otras situaciones de variación. | Variacional |
| 9 | **Argumenta sobre situaciones numéricas, geométricas y enunciados verbales en los que aparecen datos desconocidos para definir sus posibles valores según el contexto.** | Sí |
| 10 | Lee e interpreta información contenida en tablas de frecuencia, gráficos de barras y/o pictogramas con escala. | Datos |
| 11 | Plantea y resuelve preguntas sobre la posibilidad de ocurrencia de situaciones aleatorias cotidianas. | Aleatorio |

**Evidencias del DBA 3° #3 — aquí es donde el MEN pone las fracciones de 3°**
(texto literal): *"Utiliza las razones y fracciones como una manera de establecer
comparaciones entre dos cantidades"*; *"Propone ejemplos de cantidades que se
relacionan entre sí según correspondan a una fracción dada"*; *"Utiliza
fracciones para expresar la relación de 'el todo' con algunas de sus 'partes',
asimismo diferencia este tipo de relación de otras como las relaciones de
equivalencia (igualdad) y de orden (mayor que y menor que)"*.

> **Hallazgo:** el DBA de 3° **no menciona las tablas de multiplicar ni la
> memorización de hechos**. Habla de "problemas multiplicativos directos e
> inversos" y de "estrategias de cálculo". La exigencia de memoria hasta 10×10
> viene de Core Knowledge Grade 3 (*"Master basic multiplication facts to
> 10 × 10"*) y de Singapur (tablas de 2·3·4·5·10 en P2 y de 6·7·8·9 en P3). Es
> una decisión pedagógica nuestra, alineada con dos referentes externos, pero
> **no es un requisito literal del MEN**.

#### Grado 4° — 11 DBA

| # | Enunciado (MEN) | ¿Aritmética? |
|---|---|---|
| 1 | **Interpreta las fracciones como razón, relación parte todo, cociente y operador en diferentes contextos.** | Sí |
| 2 | **Describe y justifica diferentes estrategias para representar, operar y hacer estimaciones con números naturales y números racionales (fraccionarios), expresados como fracción o como decimal.** | Sí |
| 3 | **Establece relaciones mayor que, menor que, igual que y relaciones multiplicativas entre números racionales en sus formas de fracción o decimal.** | Sí |
| 4 | Caracteriza y compara atributos medibles de los objetos (densidad, dureza, viscosidad, masa, capacidad de los recipientes, temperatura). | Medición |
| 5 | Elige instrumentos y unidades estandarizadas y no estandarizadas para estimar y medir longitud, área, volumen, capacidad, peso y masa, duración, rapidez, temperatura. | Medición |
| 6 | Identifica, describe y representa figuras bidimensionales y tridimensionales, y establece relaciones entre ellas. | Geometría |
| 7 | Identifica los movimientos realizados a una figura en el plano (rotación, traslación y simetría) y las modificaciones (ampliación-reducción). | Geometría |
| 8 | Identifica, documenta e interpreta variaciones de dependencia entre cantidades en diferentes fenómenos y los representa por medio de gráficas. | Variacional |
| 9 | **Identifica patrones en secuencias (aditivas o multiplicativas) y los utiliza para establecer generalizaciones aritméticas o algebraicas.** | Sí |
| 10 | Recopila y organiza datos en tablas de doble entrada y los representa en gráficos de barras agrupadas o gráficos de líneas. | Datos |
| 11 | Comprende y explica la diferencia entre una situación aleatoria y una determinística. | Aleatorio |

**Evidencia del DBA 4° #2** (literal): *"Utiliza y justifica algoritmos
estandarizados y no estandarizados para realizar operaciones aditivas con
representaciones decimales provenientes de fraccionarios cuyas expresiones
tengan denominador 10, 100, etc."*

#### Grado 5° — 12 DBA

| # | Enunciado (MEN) | ¿Aritmética? |
|---|---|---|
| 1 | **Interpreta y utiliza los números naturales y racionales en su representación fraccionaria para formular y resolver problemas aditivos, multiplicativos y que involucren operaciones de potenciación.** | Sí |
| 2 | **Describe y desarrolla estrategias (algoritmos, propiedades de las operaciones básicas y sus relaciones) para hacer estimaciones y cálculos al solucionar problemas de potenciación.** | Sí |
| 3 | **Compara y ordena números fraccionarios a través de diversas interpretaciones, recursos y representaciones.** | Sí |
| 4 | Justifica relaciones entre superficie y volumen, respecto a dimensiones de figuras y sólidos, y elige las unidades apropiadas. | Métrico |
| 5 | Explica las relaciones entre el perímetro y el área de diferentes figuras. | Métrico |
| 6 | Identifica y describe propiedades que caracterizan un cuerpo en términos de la bidimensionalidad y la tridimensionalidad. | Geometría |
| 7 | Resuelve y propone situaciones en las que es necesario describir y localizar la posición y la trayectoria de un objeto con referencia al plano cartesiano. | Geometría |
| 8 | Describe e interpreta variaciones de dependencia entre cantidades y las representa por medio de gráficas. | Variacional |
| 9 | **Utiliza operaciones no convencionales, encuentra propiedades y resuelve ecuaciones en donde están involucradas.** | Sí |
| 10 | Formula preguntas que requieren comparar dos grupos de datos, para lo cual recolecta, organiza y usa tablas de frecuencia y gráficos. | Datos |
| 11 | Utiliza la media y la mediana para resolver problemas en los que se requiere resumir el comportamiento de un conjunto de datos. | Datos |
| 12 | Predice la posibilidad de ocurrencia de un evento simple a partir de la relación entre los elementos del espacio muestral y los del evento. | Aleatorio |

> **Hallazgo:** el DBA 5° **no menciona porcentajes**. Los Estándares Básicos
> 4°-5° sí (*"Utilizo la notación decimal para expresar fracciones en diferentes
> contextos y relaciono estas dos notaciones con la de los porcentajes"*, D3
> p.83). Si se agrega un nodo de porcentajes, el anclaje correcto es el Estándar,
> no un DBA.

### 2.3 DBA de Lenguaje 1° a 5° [V]

Ocho DBA por grado, con una estructura estable: **1-2** medios de comunicación
y códigos no verbales · **3-4** literatura y producción literaria · **5-6**
escucha/oralidad y comprensión lectora · **7-8** producción oral y producción
escrita.

| # | 1° | 2° | 3° |
|---|---|---|---|
| 1 | Identifica los diferentes medios de comunicación como una posibilidad para informarse, participar y acceder al universo cultural. | Identifica las características de los medios de comunicación masiva a los que tiene acceso. | Comprende las funciones que cumplen los medios de comunicación propios de su contexto. |
| 2 | Relaciona códigos no verbales (movimientos corporales, gestos) con el significado que pueden tomar según el contexto. | Identifica la función que cumplen las señales y símbolos que aparecen en su entorno. | Comprende que algunos escritos y manifestaciones artísticas pueden estar compuestos por texto, sonido e imágenes. |
| 3 | Reconoce en los textos literarios la posibilidad de desarrollar su capacidad creativa y lúdica. | Identifica algunos elementos constitutivos de textos literarios como personajes, espacios y acciones. | Reconoce algunas características de los textos narrativos, tales como el concepto de narrador y estructura narrativa. |
| 4 | Interpreta textos literarios como parte de su iniciación en la comprensión de textos. | Comprende diversos textos literarios a partir de sus propias vivencias. | **Escribe textos literarios coherentes, atendiendo a las características textuales e integrando sus saberes e intereses.** |
| 5 | **Reconoce las temáticas presentes en los mensajes que escucha, a partir de la diferenciación de los sonidos que componen las palabras.** | **Identifica las palabras relevantes de un mensaje y las agrupa en unidades significativas: sonidos en palabras y palabras en oraciones.** | Identifica el papel del emisor y el receptor y sus propósitos comunicativos. |
| 6 | **Interpreta diversos textos a partir de la lectura de palabras sencillas y de las imágenes que contienen.** | Predice y analiza los contenidos y estructuras de diversos tipos de texto, a partir de sus conocimientos previos. | **Interpreta el contenido y la estructura del texto, respondiendo preguntas de orden inferencial y crítico.** |
| 7 | Enuncia textos orales de diferente índole sobre temas de su interés o sugeridos por otros. | Expresa sus ideas atendiendo a las características del contexto comunicativo. | Produce textos orales breves ajustando el volumen, el tono de la voz, los movimientos corporales y los gestos. |
| 8 | **Escribe palabras que le permiten comunicar sus ideas, preferencias y aprendizajes.** | **Produce diferentes tipos de textos para atender a un propósito comunicativo particular.** | **Produce textos verbales y no verbales en los que tiene en cuenta aspectos gramaticales y ortográficos.** |

| # | 4° | 5° |
|---|---|---|
| 1 | Analiza la información presentada por los diferentes medios de comunicación con los cuales interactúa. | Utiliza la información que recibe de los medios de comunicación para participar en espacios discursivos de opinión. |
| 2 | Escribe textos a partir de información dispuesta en imágenes, fotografías, manifestaciones artísticas o conversaciones cotidianas. | Interpreta mensajes directos e indirectos en algunas imágenes, símbolos o gestos. |
| 3 | Crea textos literarios en los que articula lecturas previas e impresiones sobre un tema o situación. | Comprende los roles que asumen los personajes en las obras literarias y su relación con la temática y la época. |
| 4 | Construye textos poéticos, empleando algunas figuras literarias. | Reconoce en la lectura de los distintos géneros literarios diferentes posibilidades de recrear y ampliar su visión de mundo. |
| 5 | Interpreta el tono del discurso de su interlocutor, a partir de las características de la voz, del ritmo, de las pausas y de la entonación. | **Comprende el sentido global de los mensajes, a partir de la relación entre la información explícita e implícita.** |
| 6 | **Organiza la información que encuentra en los textos que lee, utilizando técnicas para el procesamiento de la información que le facilitan la comprensión e interpretación textual.** | **Identifica la intención comunicativa de los textos con los que interactúa a partir del análisis de su contenido y estructura.** |
| 7 | Participa en espacios de discusión en los que adapta sus emisiones a los requerimientos de la situación comunicativa. | Construye textos orales atendiendo a los contextos de uso, a los posibles interlocutores y a las líneas temáticas pertinentes. |
| 8 | **Produce textos atendiendo a elementos como el tipo de público al que va dirigido, el contexto de circulación, sus saberes previos y la diversidad de formatos.** | **Produce textos verbales y no verbales a partir de los planes textuales que elabora según la tipología a desarrollar.** |

> **Hallazgo crítico para `lenguaje.yaml`.** Los DBA de Lenguaje V.2 **no
> descomponen la decodificación**. No hay un DBA de conciencia fonológica, ni de
> sílabas directas/inversas/trabadas, ni de correspondencia grafema-fonema, ni de
> fluidez lectora medida. Lo más cerca que llega el MEN es el **DBA 1° #5**
> ("a partir de la diferenciación de los sonidos que componen las palabras") y el
> **DBA 2° #5** ("sonidos en palabras y palabras en oraciones"). El DBA 1° #6 ya
> asume que el niño lee "palabras sencillas".
>
> Consecuencia directa: **los nodos de decodificación que propongo en §7.2 no
> tienen anclaje DBA, y hay que decirlo en el YAML en vez de inventar uno.** El
> siguiente lugar donde buscar granularidad son las **Mallas de Aprendizaje** del
> MEN (documento piloto, más fino que los DBA) — no alcancé a revisarlas; ver §6.

### 2.4 Estándares Básicos de Competencias — bandas 1°-3° y 4°-5° [V]

Pensamiento numérico, texto literal de D3 (pp. 82-83).

**Al terminar tercer grado:**
- Reconozco significados del número en diferentes contextos (medición, conteo, comparación, codificación, localización entre otros).
- Describo, comparo y cuantifico situaciones con números, en diferentes contextos y con diversas representaciones.
- Describo situaciones que requieren el uso de medidas relativas.
- **Describo situaciones de medición utilizando fracciones comunes.**
- Uso representaciones —principalmente concretas y pictóricas— para explicar el valor de posición en el sistema de numeración decimal.
- Uso representaciones —principalmente concretas y pictóricas— para realizar equivalencias de un número en las diferentes unidades del sistema decimal.
- **Reconozco propiedades de los números (ser par, ser impar, etc.) y relaciones entre ellos (ser mayor que, ser menor que, ser múltiplo de, ser divisible por, etc.).**
- Resuelvo y formulo problemas en situaciones aditivas de composición y de transformación.
- Resuelvo y formulo problemas en situaciones de variación proporcional.
- Uso diversas estrategias de cálculo (especialmente cálculo mental) y de estimación para resolver problemas en situaciones aditivas y multiplicativas.
- Identifico, si a la luz de los datos de un problema, los resultados obtenidos son o no razonables.

**Al terminar quinto grado:**
- Interpreto las fracciones en diferentes contextos: situaciones de medición, relaciones parte todo, cociente, razones y proporciones.
- Identifico y uso medidas relativas en distintos contextos.
- **Utilizo la notación decimal para expresar fracciones en diferentes contextos y relaciono estas dos notaciones con la de los porcentajes.**
- Justifico el valor de posición en el sistema de numeración decimal en relación con el conteo recurrente de unidades.
- Resuelvo y formulo problemas cuya estrategia de solución requiera de las relaciones y propiedades de los números naturales y sus operaciones.
- Resuelvo y formulo problemas en situaciones aditivas de composición, transformación, comparación e igualación.
- Resuelvo y formulo problemas en situaciones de proporcionalidad directa, inversa y producto de medidas.
- **Identifico la potenciación y la radicación en contextos matemáticos y no matemáticos.**
- Modelo situaciones de dependencia mediante la proporcionalidad directa e inversa.
- Uso diversas estrategias de cálculo y de estimación para resolver problemas en situaciones aditivas y multiplicativas.
- Identifico, en el contexto de una situación, la necesidad de un cálculo exacto o aproximado y lo razonable de los resultados obtenidos.
- Justifico regularidades y propiedades de los números, sus relaciones y operaciones.

> El Estándar es más explícito que el DBA en tres cosas que el grafo necesita y
> el DBA no da: **par/impar, múltiplo, divisible** (1°-3°); **porcentajes**
> (4°-5°); **potenciación y radicación** (4°-5°).

### 2.5 Auditoría de las referencias DBA que hay hoy en `matematicas.yaml`

**13 nodos revisados uno por uno contra D1.** Ninguna referencia actual usa el
número del DBA — todas son descripciones libres, que es exactamente lo que las
hace no verificables. El formato que el propio `schema.json` documenta como
ejemplo (`"DBA Matemáticas 2° · #3"`) es el correcto y ninguno lo usa.

| Nodo | `dba_colombia` hoy | Veredicto | Referencia correcta |
|---|---|---|---|
| `mat.numeros.conteo_hasta_100` | "DBA Matemáticas 1° · conteo y secuencia numérica" | **[C]** | `DBA Matemáticas 1° · #2` — el conteo vive en el #2 y sus evidencias. El "hasta 100" **no es del MEN**. |
| `mat.numeros.valor_posicional_decenas` | "DBA Matemáticas 1° · valor posicional" | **[V]** confirmado, impreciso | `DBA Matemáticas 1° · #3` — evidencia literal: composición/descomposición de dos dígitos en "dieces" y "unos". |
| `mat.numeros.valor_posicional_centenas` | "DBA Matemáticas 2° · valor posicional hasta 999" | **[C]** | `DBA Matemáticas 2° · #3`. El tope "999" **no aparece en el DBA**; viene de CK G2 ("numbers to 1,000") y Singapur P2 ("Numbers up to 1000"). |
| `mat.numeros.comparar_ordenar` | "DBA Matemáticas 2° · comparación y orden" | **[V]** confirmado | `DBA Matemáticas 2° · #3` — el enunciado dice literalmente "comparar, ordenar". |
| `mat.suma.sin_reagrupacion` | "DBA Matemáticas 2° · adición" | **[C]** | `DBA Matemáticas 2° · #2` (cálculo) y `#1` (problemas aditivos). **El MEN no distingue con/sin reagrupación**; esa partición es de CK G2. |
| `mat.suma.con_reagrupacion` | "DBA Matemáticas 2° · adición con reagrupación" | **[C]** | `DBA Matemáticas 2° · #2`. Igual que arriba: "reagrupación" es vocabulario de CK, no del DBA. |
| `mat.resta.sin_desagrupacion` | "DBA Matemáticas 2° · sustracción" | **[C]** | `DBA Matemáticas 2° · #2`. |
| `mat.resta.con_desagrupacion` | "DBA Matemáticas 2° · sustracción con desagrupación" | **[C]** | `DBA Matemáticas 2° · #2`. |
| `mat.problemas.suma_resta` | "DBA Matemáticas 2° · problemas de composición y transformación" | **[V]** confirmado, casi literal | `DBA Matemáticas 2° · #1` — el enunciado dice "problemas aditivos (de composición, transformación y **relación**)". Falta "relación" en nuestra descripción. |
| `mat.multiplicacion.grupos_iguales` | "DBA Matemáticas 2° · multiplicación como adición repetida" | **[C]** | `DBA Matemáticas 2° · #1` ("problemas multiplicativos sencillos") y `#2` ("multiplicación o reparto equitativo"). **"Adición repetida" no es texto del MEN.** |
| `mat.multiplicacion.tablas` | "DBA Matemáticas 3° · multiplicación" | **[C]** + **[?]** parcial | `DBA Matemáticas 3° · #1`. **No pude confirmar que el MEN exija memoria hasta 10×10** — el DBA no lo dice. Esa exigencia es CK G3 + Singapur P2/P3. |
| `mat.division.reparto_equitativo` | "DBA Matemáticas 3° · división" | **[C]** | `DBA Matemáticas 3° · #1` ("multiplicativos, directos e inversos"). Nota: **"reparto equitativo" es literal del DBA 2° #2**, un grado antes. |
| `mat.fracciones.medios_tercios_cuartos` | "DBA Matemáticas 3° · fracciones" | **[C]** | `DBA Matemáticas 3° · #3` — sus evidencias son explícitamente de fracción como relación todo-parte, con comparación y orden. |

**Resumen: 3 confirmadas, 10 corregidas, 1 con una parte que no se pudo
verificar** (la memorización 10×10 del nodo `mat.multiplicacion.tablas`).

**Auditoría paralela del campo `core_knowledge`** (contra D5), porque el mismo
problema aparece ahí:

| Nodo | `core_knowledge` hoy | Veredicto |
|---|---|---|
| `mat.numeros.conteo_hasta_100` | "Grade 1 Mathematics — Numbers and number sense" | **[V]** CK G1 §II se llama exactamente "Numbers and Number Sense". |
| `mat.numeros.valor_posicional_decenas` | "Grade 1 — Place value: tens and ones" | **[C]** CK G1 dice *"Recognize place value: ones, tens, **hundreds**"*. CK ya mete centenas en 1°. |
| `mat.numeros.valor_posicional_centenas` | "Grade 2 — Place value: hundreds" | **[C]** CK G2 dice *"ones, tens, hundreds, **thousands**"*. |
| `mat.suma.*` / `mat.resta.*` | "Grade 2 — Addition/Subtraction with(out) regrouping" | **[V]** CK G2 §IV: *"Solve two-digit and three-digit addition problems with and without regrouping"*. Ojo: **CK G1 ya pide dos cifras con y sin reagrupación**. |
| `mat.multiplicacion.grupos_iguales` | "Grade 2 — Multiplication as repeated addition" | **[?]** CK G2 §IV.C se titula *"Introduction to Multiplication"*. La frase "repeated addition" **no aparece** en el Sequence. |
| `mat.multiplicacion.tablas` | "Grade 3 — Multiplication facts" | **[V]** CK G3 §IV.C: *"Master basic multiplication facts to 10 × 10"*. |
| `mat.division.reparto_equitativo` | "Grade 3 — Division as equal sharing" | **[?]** CK G3 §IV.D se titula solo *"Division"* y lo define por la relación inversa con la multiplicación, no por "equal sharing". |
| `mat.fracciones.medios_tercios_cuartos` | "Grade 3 — Simple fractions" | **[C]** CK pone *"Recognize fractions as part of a whole: ½, ⅓, ¼"* en **Grade 1**, y ½ ⅓ ¼ ⅕ ⅙ ⅛ 1/10 en **Grade 2**. En Grade 3 ya son equivalentes, mixtas y decimales. |

---

## 3. Fuente 2 — Programas de homeschooling: la secuencia

Lo que interesa aquí es **el orden y los prerrequisitos**, no el material. Los
cuatro referentes coinciden en una cosa y difieren en otra, y las dos cosas son
información útil.

### 3.1 Singapur — Primary Mathematics (la fuente más granular y verificable) [V]

El syllabus oficial del MOE (D4) es, con diferencia, la fuente más útil para
construir un grafo: viene **numerada, por nivel, por sub-strand**, con topes
numéricos explícitos. Es lo más parecido a un grafo de habilidades ya escrito.

Aritmética, P1 a P5, texto literal abreviado:

| Nivel | Whole Numbers | Adición / Sustracción | Multiplicación / División | Fracciones y decimales |
|---|---|---|---|---|
| **P1** | Numbers up to 100 · place values (tens, ones) · leer y escribir en cifras y en palabras · comparar y ordenar · patrones · ordinales 1st–10th | Conceptos de + y − · uso de `+ − =` · relación entre suma y resta · sumar más de dos números de 1 dígito · **sumar y restar dentro de 100** · algoritmos · cálculo mental dentro de 20 | Conceptos de × y ÷ · uso de `×` · **multiplicar dentro de 40** · **dividir dentro de 20** | — |
| **P2** | Numbers up to 1000 · contar de diez en diez / de cien en cien · place values (hundreds, tens, ones) · comparar y ordenar · **pares e impares** | **Algoritmos de suma y resta hasta 3 dígitos** · cálculo mental con 3 dígitos ± unidades/decenas/centenas | **Tablas de 2, 3, 4, 5 y 10** · uso de `÷` · relación entre × y ÷ · multiplicar y dividir dentro de las tablas | Fracción como parte de un todo · notación · comparar y ordenar unitarias y homogéneas (den. ≤ 12) · **sumar y restar fracciones homogéneas dentro de un entero** |
| **P3** | Numbers up to 10 000 · place values (thousands…) | Algoritmos hasta 4 dígitos · cálculo mental de dos números de 2 dígitos | **Tablas de 6, 7, 8 y 9** · **división con residuo** · algoritmos de × y ÷ hasta 3 dígitos por 1 dígito | **Fracciones equivalentes** · simplificación · comparar y ordenar heterogéneas (den. ≤ 12) · sumar y restar dos fracciones relacionadas |
| **P4** | Numbers up to 100 000 · **redondeo a 10, 100, 1000** · uso de `≈` · **factores y múltiplos**, comunes | — | Algoritmo de × hasta 4 dígitos × 1 dígito y 3 dígitos × 2 dígitos · algoritmo de ÷ hasta 4 dígitos × 1 dígito | **Números mixtos e impropios** · fracción de un conjunto · sumar y restar con den. ≤ 12 y hasta dos denominadores distintos · decimales |
| **P5** | Numbers up to 10 million · ×/÷ por 10, 100, 1000 · **orden de operaciones** · **uso de paréntesis** | — | — | Fracción como división · fracción a decimal · sumar/restar mixtos · **multiplicar fracciones** · decimales ×/÷ por potencias de 10 · **porcentaje** · **tasa (rate)** |

**Lo que Singapur enseña sobre el orden de prerrequisitos:**
1. El concepto de multiplicación y división aparece **en P1**, mucho antes que
   las tablas. El concepto no espera a la memoria.
2. Las tablas se aprenden **partidas en dos tandas** (2·3·4·5·10 en P2, luego
   6·7·8·9 en P3), no de golpe.
3. La fracción como parte-todo aparece **en P2**, no en 3° ni 4°.
4. El algoritmo de suma/resta de 3 dígitos (P2) va **antes** de las tablas
   completas (P3): el eje aditivo y el multiplicativo avanzan en paralelo, no en
   serie.
5. La división con residuo llega **en P3**, junto con la segunda tanda de
   tablas; no antes.
6. Fuentes secundarias describen el método CPA (concreto → pictórico →
   abstracto) y el diseño en espiral, donde cada strand se revisita a más
   profundidad en cada nivel:
   `https://www.singaporemath.com/pages/what-is-singapore-math`

Documentos de scope & sequence de la edición estadounidense (por si el fundador
quiere contrastar ediciones), listados en
`https://www.singaporemath.com/pages/scopes-sequences`:
- `https://singapore-math.s3.us-west-2.amazonaws.com/scopes/PMUS_Scope.pdf`
- `https://singapore-math.s3.us-west-2.amazonaws.com/scopes/PM22_Scope.pdf`
- `https://singapore-math.s3.us-west-2.amazonaws.com/scopes/PMCC_Scope.pdf`

### 3.2 Math-U-See — el argumento a favor del grafo por dominio, no por grado [V parcial]

Math-U-See ordena sus niveles con **letras griegas, deliberadamente, para que no
se lean como grados**: Primer → Alpha → Beta → Gamma → Delta → Epsilon → Zeta →
Pre-Algebra. Es un enfoque de **mastery**: no se avanza hasta dominar.

| Nivel | Foco (según la tienda oficial de Demme Learning y reseñas) |
|---|---|
| Primer | Números, conteo, escritura de numerales, suma y resta básicas, conteo saltado, formas, hora |
| Alpha | **Valor posicional, suma y resta de un dígito** |
| Beta | **Reagrupación** en suma y resta; suma y resta de varios dígitos |
| Gamma | **Multiplicación**: hechos de un dígito y multiplicación de varios dígitos |
| Delta | **División** |
| Epsilon | **Fracciones** |
| Zeta | Decimales y pensamiento algebraico |

Fuentes: `https://store.demmelearning.com/pages/math-u-see` (descripciones de
nivel) · `https://cathyduffyreviews.com/homeschool-reviews-core-curricula/math/math-grades-k-6/math-u-see`
(reseña independiente).

**Lo que aporta al proyecto:** Math-U-See es la validación externa más limpia de
la regla **SIN TECHO** de `ARCHITECTURE.md` §12. Un currículo de homeschooling
respetado y de larga trayectoria decidió explícitamente **borrar la etiqueta de
grado del nombre del nivel** para que nadie confunda edad con dominio. Es
exactamente nuestra tesis, y se puede citar.

**Su secuencia también es una hipótesis fuerte sobre el orden de prerrequisitos:**
*todo* el eje aditivo (Alpha + Beta, incluida la reagrupación) se domina **antes**
de tocar multiplicación (Gamma). Esto **contradice a Singapur**, que introduce el
concepto de multiplicación en P1. Nuestro grafo hoy sigue a Math-U-See
(`mat.multiplicacion.grupos_iguales` tiene `mat.suma.con_reagrupacion` como
prerrequisito). Es defendible, pero es una elección, y conviene que esté escrita
como elección.

### 3.3 Saxon Math — la filosofía, no la secuencia [V parcial]

Saxon se organiza por **desarrollo incremental + repaso en espiral**: cada
concepto se parte en pedazos pequeños, se introduce, y **se vuelve a tocar
distribuido en el tiempo** en vez de agotarse en un bloque. Los niveles de
primaria son Math K, Math 1, Math 2, Math 3, y luego 5/4, 6/5.

Descargué el folleto oficial de scope & sequence K-8 de HMH
(`https://padletuploads.blob.core.windows.net/prod/166043962/23d8c8780962cfae17e09d07f4aeb88f/Saxon_Math_2012_K_8_Scope_and_Sequence_Brochure.pdf`,
2.3 MB) pero es una **matriz de números de lección por tema**, no una secuencia
narrativa: sin los libros de texto al lado, los números no se pueden traducir a
habilidades. **Por eso solo reporto la filosofía, que sí está confirmada, y no
una lista de temas.** Ver §6.

**Lo que aporta al proyecto:** Saxon es el contrapunto de Math-U-See. Uno es
mastery puro (no avanzas sin dominar), el otro es espiral (avanzas y vuelves).
Nuestro `pedagogy.py` ya implementa **las dos cosas a la vez**: el planificador
exige prerrequisitos dominados (mastery, à la Math-U-See) pero el decaimiento de
dominio hace que lo viejo vuelva a subir en la cola (espiral, à la Saxon). Es un
buen argumento para el papá y no lo estábamos contando.

### 3.4 Core Knowledge Sequence — el segundo anclaje que ya usamos [V]

Ya está en el YAML como campo `core_knowledge`. Verificado contra D5 en §2.5.
Su valor: es la única fuente que da **listas de sub-habilidades atómicas**, muy
cerca del tamaño de nodo que necesitamos.

Detalle relevante de la progresión aritmética (literal de D5):

- **Grade 1** — escribir 0–100; contar de 1 en 1, 2 en 2, 5 en 5, 10 en 10; valor posicional *ones, tens, hundreds*; hechos de suma hasta 10+10; **suma y resta de dos cifras con y sin reagrupación**; fracciones ½ ⅓ ¼ como parte de un todo; ecuaciones tipo `___ − 2 = 7`.
- **Grade 2** — escribir hasta 1.000; valor posicional hasta *thousands*; forma expandida; **redondeo a la decena**; par/impar; dominio cronometrado de hechos de suma (2 segundos); suma y resta de 2 y 3 cifras con y sin reagrupación; **introducción a la multiplicación** (signo ×, factor, producto, ×1 a ×5, ×0, ×10); fracciones ½ ⅓ ¼ ⅕ ⅙ ⅛ 1/10.
- **Grade 3** — hasta seis cifras; redondeo a decena y centena; **dominio de hechos de multiplicación hasta 10×10**; multiplicación de hasta 3 cifras × 1 cifra; **división** (dividendo, divisor, cociente; hechos hasta 100÷10; no se divide por 0; división con residuo; comprobar multiplicando); **fracciones equivalentes**, numerador/denominador, números mixtos, comparación con igual denominador, decimales a las centésimas; problemas de dos pasos; paréntesis y orden de operaciones.
- **Grade 4 y Grade 5** — las secciones existen (Numbers and Number Sense; Fractions and Decimals) pero **no las transcribí**. Ver §6.

### 3.5 Dónde coinciden las cuatro fuentes (y dónde no)

**Consenso de orden — esto sí se puede tomar como prerrequisito duro:**

1. Conteo y secuencia numérica → valor posicional.
2. Valor posicional → algoritmo de suma/resta (sin él, "llevar" no significa nada).
3. Suma/resta sin reagrupación → con reagrupación.
4. Concepto de multiplicación (grupos iguales) → hechos memorizados → algoritmo multi-dígito.
5. Multiplicación ↔ división como operaciones inversas: **las cuatro fuentes las enseñan emparejadas**, no separadas por un grado. El MEN es el más explícito: DBA 3° #1, "multiplicativos, **directos e inversos**".
6. División → fracción como cociente / reparto.
7. Fracción parte-todo → fracciones equivalentes → suma y resta de fracciones → decimales → porcentajes.

**Desacuerdos que son decisiones nuestras, no verdades:**

| Punto | Singapur | Core Knowledge | Math-U-See | Nuestro grafo hoy |
|---|---|---|---|---|
| ¿Cuándo el concepto de multiplicación? | P1 | Grade 2 | Gamma (tras todo el eje aditivo) | 2°, tras suma con reagrupación → **sigue a Math-U-See** |
| ¿Cuándo la fracción parte-todo? | P2 | Grade 1 (½ ⅓ ¼) | Epsilon (tras división) | 3°, tras división → **el más tardío de los cuatro** |
| ¿Suma de 2 cifras con reagrupación? | P1 (dentro de 100) | Grade 1 | Beta | 2° → **conservador** |

Los tres desacuerdos apuntan en la misma dirección: **nuestro grafo es más
conservador que los cuatro referentes.** Eso no es un error mientras
`grado_sugerido` no filtre — y no filtra, por §12 de `ARCHITECTURE.md`. Pero sí
importa para el papá, porque `grado_de_trabajo()` compara al niño contra estas
etiquetas: si etiquetamos tarde, el reporte dice que el niño va adelantado
cuando en realidad va a tiempo según Singapur.

---

## 4. Fuente 3 — Cómo estructura un tutor humano un refuerzo de primaria

Aquí la evidencia dura disponible es la de **high-dosage / high-impact
tutoring**, que es tutoría humana estudiada con diseño experimental. Es la mejor
aproximación pública a "qué hace un buen tutor particular", y tiene la ventaja
de venir con números.

### 4.1 Los parámetros del formato [V, fuente secundaria de calidad]

Del **National Student Support Accelerator** (Stanford) y de FutureEd:

- **Frecuencia:** al menos **3 sesiones por semana**. Es el umbral que separa los
  programas con efecto de los que no lo tienen.
- **Duración por sesión:** **30 a 45 minutos**.
- **Tamaño de grupo:** 1:1 a 4:1, y cuanto más chico mejor.
- **Estabilidad del tutor:** el **mismo** tutor con el mismo niño a lo largo del
  tiempo. La relación es un ingrediente, no un adorno.
- **Duración del programa:** un semestre o más.
- **Efecto reportado:** de **3 a 15 meses** de aprendizaje adicional; en
  primaria, entre un cuarto y dos tercios de año escolar en matemáticas.

Fuentes:
- `https://nssa.stanford.edu/tqis/quality-standards` (Tutoring Quality Standards)
- `https://nssa.stanford.edu/` (Framework for High-Impact Tutoring)
- `https://www.future-ed.org/three-keys-to-successful-high-dosage-tutoring/`

### 4.2 Los elementos de la tutoría de alto impacto [V]

Según el marco del NSSA, un programa que funciona tiene: **tiempo sustancial cada
semana**, **relación sostenida** tutor-niño, **monitoreo cercano del conocimiento
y las habilidades del estudiante**, **alineación con el currículo escolar**, y
**supervisión de la calidad de las interacciones**.

### 4.3 Qué diagnostica primero un tutor, y en qué orden ataca

El patrón que reportan tanto NSSA como los programas de high-dosage:

1. **Diagnóstico de prerrequisitos, no de grado.** El tutor no arranca por el
   tema en que va el curso: arranca buscando **el eslabón roto más abajo**. Si un
   niño de 4° falla en fracciones, el tutor primero verifica división, y antes
   tablas, y antes valor posicional. La estrategia estándar es bajar hasta
   encontrar suelo firme y subir desde ahí.
2. **Currículo estructurado + relleno de huecos individuales, a la vez.** La
   recomendación explícita es que el tutor use *"a structured curriculum that
   helps students learn grade-level material **while filling in individual gaps**"*.
   No es "primero lo remedial y después lo de su grado": son las dos cosas en
   paralelo.
3. **Evaluación semanal.** Assessment frecuente para que la tutoría se readapte,
   no una prueba al inicio y otra al final.
4. **Bloques cortos y repetidos** antes que sesiones largas y esporádicas.

### 4.4 Qué significa esto para RBH Tutor

| Práctica del tutor humano | Dónde vive ya en el producto | Estado |
|---|---|---|
| Diagnosticar buscando el prerrequisito roto, no el grado | `pedagogy.py` — planificador por dominio + presunción de grado | **Existe** |
| Currículo estructurado **y** relleno de huecos a la vez | El grafo con prerrequisitos + decaimiento que reencola lo olvidado | **Existe** |
| Monitoreo cercano y frecuente del conocimiento | El Analista al cierre de cada sesión escribiendo dominio | **Existe** |
| Sesiones de 30-45 min, 3 veces por semana | `config.py` (techos de tiempo por sesión) | **No verificado.** Si el techo de sesión está muy por encima de 45 min, estamos diseñando contra la evidencia. |
| Mismo tutor sostenido en el tiempo | La ficha longitudinal — es literalmente el criterio #3 de YC | **Existe, y es citable como diferencial** |

> El único punto donde la evidencia externa podría estar pidiendo un cambio es
> el **techo de tiempo por sesión**. No lo verifiqué contra `config.py` porque
> `src/` está fuera de mi zona de archivos. Queda anotado.

---

## 5. Cobertura: qué del MEN cubre hoy `matematicas.yaml`

De los **55 DBA de matemáticas de 1° a 5°**, el grafo actual (13 nodos) toca:

| Grado | DBA de aritmética (pensamiento numérico) | Cubiertos hoy | Sin cubrir |
|---|---|---|---|
| 1° | #1, #2, #3, #9 | #2, #3 (parcial) | #1, #9 |
| 2° | #1, #2, #3, #8, #9 | #1, #2, #3 (parcial) | #8, #9 |
| 3° | #1, #2, #3, #9 | #1, #3 (parcial) | #2, #9 |
| 4° | #1, #2, #3, #9 | ninguno | los 4 |
| 5° | #1, #2, #3, #9 | ninguno | los 4 |

**El grafo se acaba en 3° y arranca en 1° a media altura.** Los 21 DBA de
aritmética de 1° a 5° están cubiertos aproximadamente a la mitad hasta 3°, y a
cero de 4° en adelante.

Los DBA de medición, geometría, variacional y aleatorio (**34 de los 55**) están
fuera del alcance declarado del producto (*lectura, escritura y aritmética*).
**Eso es una decisión de producto, no un hueco de investigación** — pero conviene
que esté escrita, porque si mañana el reporte al papá dice "alineado a los DBA
del MEN" sin matizar, está afirmando más de lo que sostiene. La formulación
honesta es *"alineado a los DBA de pensamiento numérico del MEN"*.

---

### 2.6 Contraste con `base_academica_men.md` — un corrimiento de grado

**Hecho el 2026-08-19.** Llegó una consolidación secundaria del marco del MEN
(`base_academica_men.md`) que traía sus propias tablas de DBA. Al cruzarlas
contra §2.2 y §2.3 —que son [V] contra D1 y D2— apareció un patrón, no un error
suelto: **los primeros DBA de cada grado están tomados del grado siguiente.**

| Área | En esa fuente | Verificado acá |
|---|---|---|
| Matemáticas | "Interpreta las fracciones como razón…" en **3°** | DBA **4°** #1 |
| Matemáticas | "Interpreta los números **enteros** y racionales…" en **5°** | 5° #1 es "naturales y racionales… potenciación"; los enteros son de 6° |
| Matemáticas | — | El **DBA 3° #1** real ("multiplicativos, directos e inversos") **no figura en esa fuente** |
| Lenguaje | "Identifica las características de los medios de comunicación masiva" en **1°** | DBA **2°** #1 |
| Lenguaje | Mismo patrón en 2°, 3° y 4° | Los dos primeros de cada grado vienen del siguiente |

Matemáticas 4° queda con 10 DBA en vez de 11 — el rastro aritmético del
corrimiento.

**Decisión: los DBA se toman de este documento, nunca de esa fuente.** Sus
tablas de DBA se borraron al guardarla en el repo, para que nadie las use por
error dentro de seis meses.

> Lo que esto deja como método: **la fuente que se cruza contra el primario gana
> siempre, aunque la otra se vea más completa y más ordenada.** Esa fuente traía
> las cinco áreas y esta solo dos, y aun así esta es la que manda. Cubrir más no
> es valer más.

**Lo que sí se validó de esa fuente:** los **EBC** (§2.4) coinciden texto a texto
donde se solapan, y allá están completos para las cuatro áreas y las cinco
franjas de pensamiento, no solo la numérica. Es lo que hizo viable el tercer
anclaje `ebc_colombia`.

---

## 6. No verificado

Lo que busqué y **no** pude confirmar. Esto es información, no un hueco.

1. **Rangos de fluidez lectora (palabras por minuto) del MEN de Colombia.**
   Circulan muy ampliamente los valores 45 / 78 / 92 / 110 / 135 / 149 ppm para
   1° a 6°. **No encontré ninguna fuente oficial colombiana que los respalde**;
   la evidencia apunta a que provienen de los *Estándares Nacionales de Habilidad
   Lectora* de la **SEP de México**. Busqué en el Plan Nacional de Lectura,
   Escritura y Oralidad y en documentación del Programa Todos a Aprender sin
   encontrar tabla oficial del MEN. **No usar estos números como si fueran
   colombianos.** Si se necesita un umbral de fluidez para un nodo, hay que
   decidirlo como criterio propio y declararlo como propio.

2. **Mallas de Aprendizaje del MEN.** Existen (documento piloto, por grado, más
   granular que los DBA) y son el lugar natural donde estaría la descomposición
   de la decodificación lectora que a los DBA de Lenguaje les falta. Encontré
   copias de terceros (p. ej. `https://eduteka.icesi.edu.co/pdfdir/MATEMATICAS-GRADO-1.pdf`)
   pero **no localicé el documento en un dominio oficial del MEN**, y no lo leí.
   Es el siguiente paso más rentable de esta investigación.

3. **Scope & sequence detallado de Math-U-See.** La URL oficial
   `https://demmelearning.com/math-u-see/scope-and-sequence/` devuelve **404**, y
   la reseña de Cathy Duffy devuelve **403** a la herramienta de fetch. Lo que
   reporto de Math-U-See (**orden de niveles y foco de cada uno**) está
   confirmado por la tienda oficial y por resúmenes de reseñas; el **detalle
   lección por lección no**.

4. **Secuencia temática de Saxon Math.** Descargué el folleto oficial K-8, pero
   es una matriz de números de lección sin los libros al lado. Reporto solo la
   filosofía (incremental + espiral), que sí está confirmada. **No reporto una
   lista de temas de Saxon porque no la pude leer, no porque no exista.**

5. **Core Knowledge Sequence — Grade 4 y Grade 5 en detalle.** Verifiqué Grade 1,
   2 y 3 línea por línea. De Grade 4 y 5 confirmé que las secciones existen pero
   **no transcribí su contenido**. Por eso los nodos de 4° y 5° que propongo en
   §7 van **sin campo `core_knowledge`**, a propósito.

6. **Licencia de Core Knowledge: confirmada, y es un problema.** No es un "no
   verificado" — es un "verificado y salió mal". **CC BY-NC-SA 3.0**, uso **no
   comercial**, con ShareAlike. Ver la alerta en §1. Necesita decisión del
   fundador antes de producción.

7. **Versión de los DBA.** El PDF de matemáticas se descargó desde una ruta
   `2026-06` y se identifica internamente como **V.2**; el de lenguaje desde
   `2022-06`, también **V.2**. **No confirmé si el MEN publicó una V.3.** El
   propio documento dice que las versiones *"permanecen abiertas a los aportes de
   la comunidad educativa"*, así que conviene revisar antes de producción.

8. **DBA de Transición (grado 0).** No los revisé. Si el producto llega a
   preescolar, falta esa banda.

9. **`config.py` y el techo de tiempo por sesión** contra la evidencia de 30-45
   minutos (§4.4). Fuera de mi zona de archivos; no lo miré.

---

## 7. Recomendación

### 7.0 Dos cosas de estructura, antes de los nodos

**(a) El formato de `dba_colombia` tiene que ser el número.** El propio
`schema.json` ya documenta el formato correcto en su `description`
(`"DBA Matemáticas 2° · #3"`) y **ninguno de los 13 nodos lo usa**. Una
descripción libre no es verificable; un número sí. Propuesta de formato:

```yaml
dba_colombia: "DBA Matemáticas 2° · #2"                            # anclaje único
dba_colombia: "DBA Matemáticas 2° · #1, #2"                        # el nodo cruza dos DBA
dba_colombia: "Estándares Básicos 4°-5° · pensamiento numérico"    # solo hay Estándar
# campo ausente                                                    # no hay anclaje — y se dice
```

Y una regla que se puede testear: *si `dba_colombia` existe, tiene que casar con*
`^(DBA (Matemáticas|Lenguaje) [1-5]° · #\d+(, #\d+)*|Estándares Básicos .+)$`.
Eso convierte la fidelidad curricular en algo que un test verifica, no algo que
alguien recuerda.

**(b) `schema.json` le pone techo al SIN TECHO.** El campo `grado_sugerido`
declara `"maximum": 5`. `ARCHITECTURE.md` §12 dice: *"el grafo tiene que tener
siempre cabeza de pista por encima del grado del niño. Un grafo que termina en 5°
le pone un techo real a un chico de 5° veloz."* Hoy el schema **impide** escribir
esa cabeza de pista: un nodo de 6° es inválido. Es una contradicción real entre
el schema y la arquitectura, y aparece justo cuando el grafo se extienda a 5°,
que es lo que este documento propone. **No la arreglo aquí** (el schema está
fuera de mi zona), pero queda registrada.

### 7.1 Nodos que faltan en `matematicas.yaml` para cubrir 1°-5°

**41 nodos propuestos.** IDs siguiendo la convención existente
(`mat.<dominio>.<habilidad>`, snake_case, todos casan con el patrón del schema).
Todos son de pensamiento numérico: no propongo geometría, medición ni
estadística, porque están fuera del alcance declarado del producto.

`V?` = `verificable_en_codigo`.

#### Grado 1° — cimientos que hoy no existen (9 nodos)

| ID propuesto | Nombre | Prerrequisitos | `dba_colombia` | V? |
|---|---|---|---|---|
| `mat.numeros.conteo_hasta_20` | Contar hasta 20 | — | `DBA Matemáticas 1° · #2` | sí |
| `mat.numeros.ordinales` | Primero, segundo, tercero | `mat.numeros.conteo_hasta_20` | `DBA Matemáticas 1° · #1` | sí |
| `mat.numeros.conteo_saltado` | Contar de 2 en 2, de 5 en 5 y de 10 en 10 | `mat.numeros.conteo_hasta_100` | `DBA Matemáticas 1° · #2` (evidencia literal) | sí |
| `mat.numeros.recta_numerica` | Ubicar números en la recta | `mat.numeros.conteo_hasta_100` | `DBA Matemáticas 1° · #3` | sí |
| `mat.suma.hechos_hasta_10` | Sumas básicas hasta 10 | `mat.numeros.conteo_hasta_20` | `DBA Matemáticas 1° · #2` | sí |
| `mat.suma.hechos_hasta_20` | Sumas básicas hasta 20 | `mat.suma.hechos_hasta_10` | `DBA Matemáticas 1° · #2` | sí |
| `mat.resta.hechos_basicos` | Restas básicas hasta 20 | `mat.suma.hechos_hasta_20` | `DBA Matemáticas 1° · #2` | sí |
| `mat.numeros.signo_igual` | El signo igual es equivalencia, no "aquí va la respuesta" | `mat.resta.hechos_basicos` | `DBA Matemáticas 1° · #9` | sí |
| `mat.problemas.incognita_en_cualquier_lugar` | Problemas tipo `a + ? = c` y `? + b = c` | `mat.numeros.signo_igual` | `DBA Matemáticas 1° · #2` (evidencia literal) | sí |

> `mat.numeros.signo_igual` merece mención aparte. El DBA 1° #9 existe como DBA
> completo y ataca **el error conceptual más común de toda la aritmética de
> primaria**: leer `=` como "escribe el resultado" en vez de "las dos cosas valen
> lo mismo". Un niño con ese error resuelve `4 + ? = 9` poniendo 13. Es
> exactamente el tipo de nodo que un tutor socrático puede desarmar con preguntas
> y que un ejercicio verificable en código detecta sin ambigüedad. Hoy no está en
> el grafo.

#### Grado 2° (7 nodos)

| ID propuesto | Nombre | Prerrequisitos | `dba_colombia` | V? |
|---|---|---|---|---|
| `mat.numeros.par_impar` | Pares e impares | `mat.numeros.conteo_saltado` | `Estándares Básicos 1°-3° · pensamiento numérico` | sí |
| `mat.numeros.redondeo_decena` | Redondear a la decena | `mat.numeros.comparar_ordenar` | **[?]** sin DBA directo; CK Grade 2 | sí |
| `mat.suma.tres_cifras` | Suma de tres cifras | `mat.suma.con_reagrupacion`, `mat.numeros.valor_posicional_centenas` | `DBA Matemáticas 2° · #2` | sí |
| `mat.resta.tres_cifras` | Resta de tres cifras | `mat.resta.con_desagrupacion`, `mat.numeros.valor_posicional_centenas` | `DBA Matemáticas 2° · #2` | sí |
| `mat.suma.calculo_mental` | Cálculo mental de sumas y restas | `mat.suma.con_reagrupacion` | `DBA Matemáticas 2° · #2` | sí |
| `mat.numeros.valor_desconocido` | Encontrar el número que falta en una expresión | `mat.numeros.signo_igual`, `mat.suma.con_reagrupacion` | `DBA Matemáticas 2° · #8, #9` | sí |
| `mat.multiplicacion.tablas_2_5_10` | Tablas del 2, del 5 y del 10 | `mat.multiplicacion.grupos_iguales` | `DBA Matemáticas 2° · #2` · Singapur P2 | sí |

> **Ajuste recomendado a un nodo existente.** `mat.division.reparto_equitativo`
> tiene hoy `grado_sugerido: 3` y exige `mat.multiplicacion.tablas` completo. El
> MEN lo nombra literalmente en el **DBA 2° #2**. Recomiendo bajarlo a
> `grado_sugerido: 2` y cambiar su prerrequisito a `mat.multiplicacion.tablas_2_5_10`:
> exigir las diez tablas para entender qué es repartir es pedir demasiado, y
> contradice el consenso de §3.5 punto 5 (multiplicación y división se enseñan
> emparejadas).

#### Grado 3° (8 nodos)

| ID propuesto | Nombre | Prerrequisitos | `dba_colombia` | V? |
|---|---|---|---|---|
| `mat.numeros.valor_posicional_millares` | Unidades de mil | `mat.numeros.valor_posicional_centenas` | `DBA Matemáticas 3° · #3` · Singapur P3 | sí |
| `mat.numeros.redondeo_centena` | Redondear a la centena | `mat.numeros.redondeo_decena`, `mat.numeros.valor_posicional_millares` | **[?]** sin DBA directo; CK Grade 3 | sí |
| `mat.multiplicacion.por_una_cifra` | Multiplicar por una cifra llevando | `mat.multiplicacion.tablas`, `mat.numeros.valor_posicional_centenas` | `DBA Matemáticas 3° · #1, #2` | sí |
| `mat.division.exacta_por_una_cifra` | Dividir por una cifra sin residuo | `mat.division.reparto_equitativo`, `mat.multiplicacion.tablas` | `DBA Matemáticas 3° · #1` | sí |
| `mat.division.con_residuo` | Dividir con residuo | `mat.division.exacta_por_una_cifra` | `DBA Matemáticas 3° · #1` · Singapur P3 | sí |
| `mat.fracciones.notacion` | Numerador y denominador | `mat.fracciones.medios_tercios_cuartos` | `DBA Matemáticas 3° · #3` | sí |
| `mat.fracciones.equivalentes` | Fracciones que valen lo mismo | `mat.fracciones.notacion` | `DBA Matemáticas 3° · #3` | sí |
| `mat.problemas.dos_pasos` | Problemas de dos operaciones | `mat.problemas.suma_resta`, `mat.multiplicacion.por_una_cifra` | `DBA Matemáticas 3° · #1, #9` | sí |

#### Grado 4° (9 nodos)

| ID propuesto | Nombre | Prerrequisitos | `dba_colombia` | V? |
|---|---|---|---|---|
| `mat.numeros.hasta_cien_mil` | Números hasta cien mil | `mat.numeros.valor_posicional_millares` | `DBA Matemáticas 4° · #2` · Singapur P4 | sí |
| `mat.numeros.multiplos` | Múltiplos de un número | `mat.multiplicacion.tablas` | `Estándares Básicos 1°-3° · pensamiento numérico` (literal: "ser múltiplo de") | sí |
| `mat.numeros.factores` | Factores y divisibilidad | `mat.division.exacta_por_una_cifra`, `mat.numeros.multiplos` | `Estándares Básicos 1°-3°` ("ser divisible por") · Singapur P4 | sí |
| `mat.multiplicacion.por_dos_cifras` | Multiplicar por dos cifras | `mat.multiplicacion.por_una_cifra` | `DBA Matemáticas 4° · #2` · Singapur P4 | sí |
| `mat.division.por_una_cifra_larga` | División larga por una cifra | `mat.division.con_residuo` | `DBA Matemáticas 4° · #2` · Singapur P4 | sí |
| `mat.fracciones.impropias_y_mixtas` | Fracciones impropias y números mixtos | `mat.fracciones.equivalentes` | `DBA Matemáticas 4° · #1` · Singapur P4 | sí |
| `mat.fracciones.suma_resta_mismo_denominador` | Sumar y restar fracciones de igual denominador | `mat.fracciones.equivalentes` | `DBA Matemáticas 4° · #2` | sí |
| `mat.decimales.decimas_y_centesimas` | Décimas y centésimas | `mat.fracciones.notacion`, `mat.numeros.valor_posicional_millares` | `DBA Matemáticas 4° · #2` (evidencia literal: denominador 10, 100) | sí |
| `mat.decimales.suma_resta` | Sumar y restar decimales | `mat.decimales.decimas_y_centesimas`, `mat.suma.tres_cifras` | `DBA Matemáticas 4° · #2` | sí |

#### Grado 5° (8 nodos)

| ID propuesto | Nombre | Prerrequisitos | `dba_colombia` | V? |
|---|---|---|---|---|
| `mat.fracciones.comparar_y_ordenar` | Comparar y ordenar fracciones | `mat.fracciones.impropias_y_mixtas` | `DBA Matemáticas 5° · #3` | sí |
| `mat.fracciones.suma_resta_distinto_denominador` | Sumar y restar fracciones de distinto denominador | `mat.fracciones.suma_resta_mismo_denominador`, `mat.numeros.multiplos` | `DBA Matemáticas 5° · #1` | sí |
| `mat.fracciones.multiplicacion` | Multiplicar fracciones | `mat.fracciones.suma_resta_distinto_denominador` | `DBA Matemáticas 5° · #1` · Singapur P5 | sí |
| `mat.decimales.multiplicacion_division` | Multiplicar y dividir decimales | `mat.decimales.suma_resta`, `mat.multiplicacion.por_dos_cifras` | `DBA Matemáticas 5° · #1` · Singapur P5 | sí |
| `mat.porcentajes.concepto` | Qué es un porcentaje | `mat.decimales.decimas_y_centesimas`, `mat.fracciones.equivalentes` | `Estándares Básicos 4°-5° · pensamiento numérico` (literal) — **no hay DBA** | sí |
| `mat.numeros.potenciacion` | Potencias y cuadrados | `mat.multiplicacion.por_dos_cifras` | `DBA Matemáticas 5° · #1, #2` | sí |
| `mat.operaciones.orden_y_parentesis` | El orden de las operaciones | `mat.multiplicacion.por_una_cifra`, `mat.division.exacta_por_una_cifra` | `DBA Matemáticas 5° · #9` · Singapur P5 | sí |
| `mat.proporcionalidad.directa` | Proporcionalidad directa | `mat.multiplicacion.por_dos_cifras`, `mat.fracciones.notacion` | `Estándares Básicos 4°-5°` · `DBA Matemáticas 4° · #1` (razón) | sí |

**Total: 41 nodos nuevos + 13 existentes = 54 nodos** para cubrir el pensamiento
numérico del MEN de 1° a 5°.

**Y sigue faltando cabeza de pista.** Con 54 nodos que terminan en 5°, un niño de
5° veloz llega al final del grafo. `ARCHITECTURE.md` §12 dice explícitamente que
eso es un techo real. Habría que agregar nodos de 6° (números enteros, razones y
proporciones, álgebra inicial) — pero **`schema.json` lo prohíbe hoy**
(`grado_sugerido` máximo 5). Ver §7.0(b).

### 7.2 Nodos para arrancar `lenguaje.yaml`

El schema admite `materia: lectura` y `materia: escritura`, y prefijos de ID
`lec.` y `esc.`. **24 nodos propuestos** — 13 de lectura, 11 de escritura.

**La advertencia va primero, porque cambia cómo se lee la tabla:** los DBA de
Lenguaje V.2 **no descomponen la decodificación** (§2.3). Los nodos de conciencia
fonológica y de sílabas **no tienen anclaje DBA, y la propuesta es que lo digan**
(campo ausente) en vez de inventarse una referencia plausible. Es exactamente el
caso donde la regla del proyecto —*"None es una respuesta válida y hay que dejar
que llegue hasta la superficie"*— aplica al currículum y no solo al reporte.

**Segunda advertencia, de schema:** el campo `alineacion` solo admite
`dba_colombia` y `core_knowledge`, y **Core Knowledge Language Arts es de fonética
inglesa**: no transfiere a la decodificación del español, donde el problema es
otro (sistema silábico transparente, sílabas trabadas, la eñe, la tilde). El
segundo anclaje de `lenguaje.yaml` **no puede ser Core Knowledge**. Esa decisión
hay que tomarla antes de escribir el YAML, y probablemente implique tocar
`schema.json`. Ver §6 punto 2: las Mallas de Aprendizaje del MEN son la candidata
más obvia.

#### Lectura — 13 nodos

| ID propuesto | Nombre | Grado | Prerrequisitos | `dba_colombia` | V? |
|---|---|---|---|---|---|
| `lec.fonologia.rimas_y_silabas` | Oír rimas y partir palabras en sílabas | 1 | — | `DBA Lenguaje 1° · #5` | sí |
| `lec.fonologia.sonido_inicial_y_final` | Reconocer con qué sonido empieza y termina una palabra | 1 | `lec.fonologia.rimas_y_silabas` | `DBA Lenguaje 1° · #5` | sí |
| `lec.fonologia.segmentar_fonemas` | Separar una palabra en sus sonidos | 1 | `lec.fonologia.sonido_inicial_y_final` | **sin anclaje DBA** | sí |
| `lec.decodificacion.vocales` | Las cinco vocales | 1 | `lec.fonologia.sonido_inicial_y_final` | **sin anclaje DBA** | sí |
| `lec.decodificacion.silabas_directas` | Sílabas directas (ma, me, mi, mo, mu) | 1 | `lec.decodificacion.vocales` | **sin anclaje DBA** | sí |
| `lec.decodificacion.silabas_inversas` | Sílabas inversas (al, en, is) | 1 | `lec.decodificacion.silabas_directas` | **sin anclaje DBA** | sí |
| `lec.decodificacion.silabas_trabadas` | Sílabas trabadas (bra, pla, tri) | 2 | `lec.decodificacion.silabas_inversas` | **sin anclaje DBA** | sí |
| `lec.decodificacion.palabras_completas` | Leer palabras completas sin deletrear | 2 | `lec.decodificacion.silabas_trabadas` | `DBA Lenguaje 1° · #6` | sí |
| `lec.fluidez.oracion_en_voz_alta` | Leer una oración corrida, con sentido | 2 | `lec.decodificacion.palabras_completas` | `DBA Lenguaje 2° · #5` | no |
| `lec.comprension.literal` | Responder qué dice el texto | 2 | `lec.fluidez.oracion_en_voz_alta` | `DBA Lenguaje 2° · #6` | no |
| `lec.comprension.estructura_narrativa` | Quién narra, qué pasa primero y después | 3 | `lec.comprension.literal` | `DBA Lenguaje 3° · #3` | no |
| `lec.comprension.inferencial` | Deducir lo que el texto no dice con todas las letras | 3 | `lec.comprension.literal` | `DBA Lenguaje 3° · #6` · `5° · #5` | no |
| `lec.comprension.proposito_del_texto` | Para qué fue escrito este texto | 5 | `lec.comprension.inferencial` | `DBA Lenguaje 5° · #6` · `4° · #6` | no |

#### Escritura — 11 nodos

| ID propuesto | Nombre | Grado | Prerrequisitos | `dba_colombia` | V? |
|---|---|---|---|---|---|
| `esc.grafia.trazo_de_letras` | Trazar las letras | 1 | — | **sin anclaje DBA** | no |
| `esc.ortografia.sonido_a_letra` | Escribir la letra que suena | 1 | `lec.fonologia.segmentar_fonemas` | **sin anclaje DBA** | sí |
| `esc.escritura.palabras` | Escribir palabras que quiere decir | 1 | `esc.ortografia.sonido_a_letra`, `esc.grafia.trazo_de_letras` | `DBA Lenguaje 1° · #8` | sí |
| `esc.escritura.oracion_completa` | Escribir una oración entera | 2 | `esc.escritura.palabras` | `DBA Lenguaje 2° · #8` | no |
| `esc.ortografia.mayuscula_y_punto` | Mayúscula al empezar, punto al terminar | 2 | `esc.escritura.oracion_completa` | `DBA Lenguaje 3° · #8` | sí |
| `esc.ortografia.reglas_frecuentes` | Las reglas que más se usan (b/v, c/s/z, ll/y, h muda) | 3 | `esc.ortografia.mayuscula_y_punto` | `DBA Lenguaje 3° · #8` | sí |
| `esc.escritura.parrafo` | Escribir un párrafo con una sola idea | 3 | `esc.escritura.oracion_completa` | `DBA Lenguaje 3° · #4` | no |
| `esc.escritura.texto_narrativo` | Contar algo por escrito, con principio y final | 3 | `esc.escritura.parrafo`, `lec.comprension.estructura_narrativa` | `DBA Lenguaje 3° · #4` | no |
| `esc.ortografia.tilde` | Dónde va la tilde | 4 | `esc.ortografia.reglas_frecuentes`, `lec.fonologia.rimas_y_silabas` | `DBA Lenguaje 3° · #8` | sí |
| `esc.escritura.adecuacion_al_lector` | Escribir distinto según quién va a leer | 4 | `esc.escritura.texto_narrativo` | `DBA Lenguaje 4° · #8` | no |
| `esc.escritura.plan_textual` | Planear antes de escribir | 5 | `esc.escritura.adecuacion_al_lector` | `DBA Lenguaje 5° · #8` | no |

**Sobre `verificable_en_codigo` en lenguaje.** Es el campo que decide si
`check_answer` puede validar o si hace falta juicio del modelo. La partición
propuesta: **decodificación y ortografía sí** (hay una respuesta única: la sílaba
es esa, la tilde va ahí, la palabra se escribe así), **comprensión y producción
no** (no hay una única respuesta correcta y forzarla sería falsear). De los 24
nodos, **13 quedan verificables en código** — suficiente para que el banco de
ejercicios de lectura y escritura no dependa entero del juicio de un modelo, que
era el riesgo.

---

## 8. Lo que este documento deja pendiente

En orden de rentabilidad:

1. **Buscar las Mallas de Aprendizaje del MEN en dominio oficial** y leerlas para
   1° y 2° de Lenguaje. Es lo único que puede darle anclaje MEN a los 8 nodos de
   decodificación que hoy quedarían sin él.
2. **Decidir qué pasa con Core Knowledge** (licencia NC-SA, §1). Es la única
   pendiente con riesgo legal.
3. **Decidir el segundo anclaje de `lenguaje.yaml`**, que no puede ser Core
   Knowledge (§7.2), y ver si eso obliga a tocar `schema.json`.
4. **Resolver el techo de `grado_sugerido` en `schema.json`** (§7.0b), que
   contradice §12 de la arquitectura y bloquea la cabeza de pista.
5. **Confirmar que los DBA V.2 siguen vigentes** y que no hay V.3 (§6.7).
6. **Contrastar el techo de tiempo por sesión de `config.py`** con los 30-45
   minutos de la evidencia de tutoría de alto impacto (§4.4).
