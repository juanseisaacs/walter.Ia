# Base académica del MEN — primaria colombiana

Marco del sistema educativo colombiano que rodea al grafo de habilidades: qué
áreas existen, con qué se evalúa al niño, en qué calendario vive, y cómo piensa
a cada edad. **No se carga en runtime.** Es material del que se destilan nodos
del currículum y párrafos de prompt, igual que `FUENTES.md`.

**Procedencia:** `Base_Academica_Tutor_Primaria_Colombia.docx`, recibido el
2026-08-19. Consolidación **secundaria**: cita al MEN pero no es un documento del
MEN. `FUENTES.md` sí trabaja sobre los PDF primarios descargados, y por eso manda
donde los dos hablan de lo mismo.

---

## ⚠️ La sección de DBA de este documento NO se usa

El documento original traía los DBA de las cinco áreas, grado por grado. **Se
eliminaron de esta copia**, porque al cruzarlos con `FUENTES.md` §2.2 y §2.3
—verificados contra los PDF del MEN— aparece un corrimiento sistemático:

> **Los primeros DBA de cada grado están tomados del grado siguiente.**

| Área | Lo que dice el documento | Lo verificado (`FUENTES.md`) |
|---|---|---|
| Matemáticas | *"Interpreta las fracciones como razón, relación parte todo, cociente y operador"* aparece en **3°** | Es el **DBA 4° #1** |
| Matemáticas | *"Interpreta los números **enteros** y racionales…"* aparece en **5°** | En 5° va *"naturales y racionales… potenciación"*; los enteros son de 6° |
| Matemáticas | El **DBA 3° #1** real (*"multiplicativos, directos e inversos"*) | **No aparece en ninguna parte del documento** |
| Lenguaje | *"Identifica las características de los medios de comunicación masiva"* aparece en **1°** | Es el **DBA 2° #1** |
| Lenguaje | El mismo patrón se repite en 2°, 3° y 4° | Los dos primeros DBA de cada grado vienen del grado siguiente |

Matemáticas 4° queda además con 10 DBA en vez de 11, que es el rastro del
corrimiento.

**Consecuencia práctica:** si esos DBA hubieran entrado al YAML, habríamos
anclado las fracciones un grado antes de lo que manda el MEN y perdido el DBA
que sostiene la multiplicación de 3°. **Los DBA se toman de `FUENTES.md`, nunca
de acá.**

Nada de esto invalida el resto del documento: la parte de EBC se cruzó contra
`FUENTES.md` §2.4 y **coincide texto a texto** donde se solapan, además de cubrir
las franjas que allá no se habían transcrito. Lo de las secciones IV y V no
depende de los DBA.

---

## Qué de acá está vivo en el código

| Sección | Dónde aterrizó |
|---|---|
| §III — EBC por ciclo | Campo `alineacion.ebc_colombia` en `schema.json` y `models.Alineacion`; poblado en los 13 nodos de `matematicas.yaml` |
| §V.5 — desarrollo cognitivo | `pedagogy.REGISTRO_POR_GRADO`, una línea por grado inyectada en `resumen_para_prompt` |
| §V.4 — el 20 % institucional | `session_analyst.es.md` → consolidado en `PerfilPersonal.notas` |
| §I, §II.6, §IV, §V.1-V.3 | Contexto y decisiones de alcance. Ver `ARCHITECTURE.md` §19 |

---



## Cómo usar este documento
Este documento consolida, en un solo lugar, todo el conocimiento académico oficial que el tutor debe tener para acompañar a niños y niñas de primaria en Colombia. Todo el contenido proviene de documentos oficiales del Ministerio de Educación Nacional (MEN), la Ley General de Educación (Ley 115 de 1994), el Decreto 1850 de 2002 (compilado en el Decreto 1075 de 2015) y el ICFES; las fuentes exactas aparecen citadas al pie y consolidadas en la sección final.
Regla de oro para el prompt: el tutor siempre debe saber (1) en qué grado está el niño, (2) en qué calendario estudia (A o B) y en qué momento del año escolar se encuentra, y (3) qué 20 % institucional ha aprendido del colegio del niño en conversaciones previas. Con esos tres datos, el tutor selecciona de este documento los DBA del grado, los EBC del ciclo correspondiente y el modo de lenguaje según la edad.


## I. LAS CINCO ÁREAS QUE ABARCA EL TUTOR
La Ley 115 de 1994 (art. 23) establece nueve grupos de áreas obligatorias y fundamentales que deben cubrir, como mínimo, el 80 % del plan de estudios de todo colegio del país.  De esas nueve, el tutor aborda únicamente cinco, que son las áreas de contenido académico explicables y evaluables en una conversación:
Ciencias naturales y educación ambiental.
Ciencias sociales, historia, geografía, constitución política y democracia. (Incluye la Historia de Colombia como disciplina integrada, obligatoria desde la Ley 1874 de 2017.2)
Humanidades, lengua castellana e idiomas extranjeros (en este proyecto: lengua castellana + inglés).
Matemáticas.
Tecnología e informática.
Las cuatro áreas restantes (educación artística y cultural; educación ética y en valores humanos; educación física, recreación y deportes; educación religiosa) quedan por fuera del alcance del tutor, porque su desarrollo es esencialmente experiencial, corporal, artístico o de formación personal familiar. Si el niño pregunta por ellas, el tutor puede dar orientaciones generales de conversación, pero no evalúa ni estructura pensum sobre ellas.
Nota importante sobre el 80 %: la ley exige que estas áreas obligatorias ocupen mínimo el 80 % del plan de estudios; el 20 % restante lo define cada colegio en su Proyecto Educativo Institucional (PEI).1 Esto significa que el tutor domina de fábrica el núcleo nacional común, pero debe asumir que cada colegio tiene particularidades (énfasis, proyectos, cátedras locales) que irá aprendiendo con el uso (ver sección V.4).


## Tecnología e informática (área sin DBA oficiales)
Situación oficial: el MEN no ha publicado DBA ni Estándares Básicos de Competencias para esta área. Los referentes oficiales vigentes son los Lineamientos Curriculares de Tecnología e Informática y la Guía 30 “Ser competente en tecnología: una necesidad para el desarrollo”, que organizan el área en torno a cuatro procesos:
Apropiación y uso de la tecnología: entender para qué sirven las tecnologías y usarlas con criterio.
Solución de problemas con tecnología: usar herramientas tecnológicas para resolver situaciones concretas.
Manejo de herramientas y software: operar dispositivos, archivos, programas y entornos digitales.
Ética, legalidad y ciudadanía digital: uso responsable, seguro y respetuoso de la tecnología.
Progresión sugerida por grado (construida desde los lineamientos, para que el tutor tenga un pensum de trabajo):
Grado 1.°: reconocer dispositivos tecnológicos del entorno (computador, tablet, celular) y para qué sirven; identificar partes básicas (pantalla, teclado, ratón); normas de cuidado y uso con acompañamiento de un adulto.
Grado 2.°: encender, usar y apagar dispositivos correctamente; abrir y cerrar programas; dibujar y escribir con herramientas digitales simples; entender que la información en internet puede ser verdadera o falsa.
Grado 3.°: crear, guardar y recuperar archivos; escribir textos cortos en procesador de texto; usar el teclado con soltura básica; normas de comportamiento en línea (no compartir datos personales).
Grado 4.°: buscar información en fuentes confiables con ayuda; organizar archivos en carpetas; presentaciones sencillas; introducción al pensamiento computacional (secuencias e instrucciones paso a paso, tipo algoritmo).
Grado 5.°: pensamiento computacional aplicado (patrones, descomposición de problemas, algoritmos sencillos, bloques de programación tipo Scratch); uso de hojas de datos simples; ciudadanía digital: respeto, privacidad y verificación de información.
Cómo lo usa el tutor: como no hay DBA oficiales, el tutor trata esta área como apoyo transversal (usar la tecnología para aprender las otras áreas) y refuerza siempre la seguridad digital del niño: nunca pedir ni almacenar datos personales del menor, y recordar que un adulto debe supervisar el uso de dispositivos.


## III. HABILIDADES POR CICLO — ESTÁNDARES BÁSICOS DE COMPETENCIAS (EBC), LINEAMIENTOS Y MALLAS
III.0 Cómo funcionan los ciclos y qué le aplica a cada niño
Los Estándares Básicos de Competencias (EBC, MEN 2006) definen qué debe saber y saber hacer el estudiante al terminar cada ciclo de grados, no cada año.8 Para primaria hay dos ciclos:
Grado del niño
 | Ciclo que aplica
 | Qué debe usar el tutor
 | 
1.°, 2.° o 3.°
 | Ciclo 1 (1.°–3.°)
 | Los EBC de “primero a tercero” como meta de fondo + los DBA del grado específico como ruta del año
 | 
4.° o 5.°
 | Ciclo 2 (4.°–5.°)
 | Los EBC de “cuarto a quinto” como meta de fondo + los DBA del grado específico como ruta del año
 | 
Reglas de interpretación para el prompt:8
Los EBC de un ciclo se alcanzan de forma gradual e integrada: no se reparten entre los grados del ciclo ni entre periodos del año.
Tienen coherencia vertical (cada ciclo contiene y profundiza al anterior: si un niño de 5.° falla en algo, el tutor revisa el estándar equivalente del ciclo 1.°–3.°) y coherencia horizontal (se organizan por ejes o componentes propios de cada área).
Relación entre documentos: los EBC dicen hacia dónde va el ciclo; los DBA dicen cuánto avanzar este año; las mallas sugieren en qué orden avanzar dentro del año.
A continuación, los estándares oficiales por área y ciclo (redactados en primera persona, como en el documento original del MEN):
EBC de Lenguaje
Fuente: Estándares Básicos de Competencias del Lenguaje (MEN, 2006).8 Ejes articuladores: producción y comprensión de textos orales y escritos; literatura; medios de comunicación y otros sistemas simbólicos; y elementos constitutivos del proceso de comunicación.
Ciclo 1 — Al terminar tercer grado (aplica si el niño está en 1.°, 2.° o 3.°)
Utilizo, de acuerdo con el contexto, un vocabulario adecuado para expresar mis ideas.
Expreso en forma clara mis ideas y sentimientos, según lo amerite la situación comunicativa.
Utilizo la entonación y los matices afectivos de voz para alcanzar mi propósito en diferentes situaciones comunicativas.
Tengo en cuenta aspectos semánticos y morfosintácticos, de acuerdo con la situación comunicativa en la que intervengo.
Describo personas, objetos, lugares, etc., en forma detallada.
Describo eventos de manera secuencial.
Elaboro instrucciones que evidencian secuencias lógicas en la realización de acciones.
Expongo y defiendo mis ideas en función de la situación comunicativa..
Determino el tema, el posible lector de mi texto y el propósito comunicativo que me lleva a producirlo.
Elijo el tipo de texto que requiere mi propósito comunicativo.
Busco información en distintas fuentes: personas, medios de comunicación y libros, entre otras.
Elaboro un plan para organizar mis ideas.
Desarrollo un plan textual para la producción de un texto descriptivo.
Reviso, socializo y corrijo mis escritos, teniendo en cuenta las propuestas de mis compañeros y profesor, y atendiendo algunos aspectos gramaticales (concordancia, tiempos verbales, pronombres) y ortográficos (acentuación, mayúsculas, signos de puntuación) de la lengua castellana..
Leo diferentes clases de textos: manuales, tarjetas, afiches, cartas, periódicos, etc.
Reconozco la función social de los diversos tipos de textos que leo.
Identifico la silueta o el formato de los textos que leo.
Elaboro hipótesis acerca del sentido global de los textos, antes y durante el proceso de lectura; para el efecto, me apoyo en mis conocimientos previos, las imágenes y los títulos.
Identifico el propósito comunicativo y la idea global de un texto.
Elaboro resúmenes y esquemas que dan cuenta del sentido de un texto.
Leo fábulas, cuentos, poemas, relatos mitológicos, leyendas, o cualquier otro texto literario.
Elaboro y socializo hipótesis predictivas acerca del contenido de los textos.
Identifico maneras de cómo se formula el inicio y el final de algunas narraciones.
Diferencio poemas, cuentos y obras de teatro.
Recreo relatos y cuentos cambiando personajes, ambientes, hechos y épocas.
Participo en la elaboración de guiones para teatro de títeres..
Identifico los diversos medios de comunicación masiva con los que interactúo.
Caracterizo algunos medios de comunicación: radio, televisión, prensa, entre otros.
Comento mis programas favoritos de televisión o radio.
Identifico la información que emiten los medios de comunicación masiva y la forma de presentarla.
Establezco diferencias y semejanzas entre noticieros, telenovelas, anuncios comerciales, dibujos animados, caricaturas, entre otros.
Utilizo los medios de comunicación masiva para adquirir información e incorporarla de manera significativa a mis esquemas de conocimiento..
Entiendo el lenguaje empleado en historietas y otros tipos de textos con imágenes fijas.
Expongo oralmente lo que me dicen mensajes cifrados en pictogramas, jeroglíficos, etc.
Reconozco la temática de caricaturas, tiras cómicas, historietas, anuncios publicitarios y otros medios de expresión gráfica.
Ordeno y completo la secuencia de viñetas que conforman una historieta.
Relaciono gráficas con texto escrito, ya sea completándolas o explicándolas..
Reconozco los principales elementos constitutivos de un proceso de comunicación: interlocutores, código, canal, texto y situación comunicativa.
Establezco semejanzas y diferencias entre quien produce el texto y quien lo interpreta.
Identifico en situaciones comunicativas reales los roles de quien produce y de quien interpreta un texto.
Identifico la intención de quien produce un texto.
Ciclo 2 — Al terminar quinto grado (aplica si el niño está en 4.° o 5.°)
Organizo mis ideas para producir un texto oral, teniendo en cuenta mi realidad y mis propias experiencias.
Elaboro un plan para la exposición de mis ideas.
Selecciono el léxico apropiado y acomodo mi estilo al plan de exposición así como al contexto comunicativo.
Adecuo la entonación y la pronunciación a las exigencias de las situaciones comunicativas en que participo.
Produzco un texto oral, teniendo en cuenta la entonación, la articulación y la organización de ideas que requiere la situación comunicativa..
Elijo un tema para producir un texto escrito, teniendo en cuenta un propósito, las características del interlocutor y las exigencias del contexto.
Diseño un plan para elaborar un texto informativo.
Produzco la primera versión de un texto informativo, atendiendo a requerimientos (formales y conceptuales) de la producción escrita en lengua castellana, con énfasis en algunos aspectos gramaticales (concordancia, tiempos verbales, nombres, pronombres, entre otros) y ortográficos.
Reescribo el texto a partir de las propuestas de corrección formuladas por mis compañeros y por mí..
Leo diversos tipos de texto: descriptivo, informativo, narrativo, explicativo y argumentativo.
Comprendo los aspectos formales y conceptuales (en especial: características de las oraciones y formas de relación entre ellas), al interior de cada texto leído.
Identifico la intención comunicativa de cada uno de los textos leídos.
Determino algunas estrategias para buscar, seleccionar y almacenar información: resúmenes, cuadros sinópticos, mapas conceptuales y fichas.
Establezco diferencias y semejanzas entre las estrategias de búsqueda, selección y almacenamiento de información.
Identifico los elementos constitutivos de la comunicación: interlocutores, código, canal, mensaje y contextos.
Caracterizo los roles desempeñados por los sujetos que participan del proceso comunicativo.
Tengo en cuenta, en mis interacciones comunicativas, principios básicos de la comunicación: reconocimiento del otro en tanto interlocutor válido y respeto por los turnos conversacionales.
Identifico en situaciones comunicativas reales los roles, las intenciones de los interlocutores y el respeto por los principios básicos de la comunicación. Conozco y analizo los elementos, roles, relaciones y reglas básicas de la comunicación, para inferir las intenciones y expectativas de mis interlocutores y hacer más eficaces mis procesos comunicativos..
Entiendo las obras no verbales como productos de las comunidades humanas.
Doy cuenta de algunas estrategias empleadas para comunicar a través del lenguaje no verbal.
Explico el sentido que tienen mensajes no verbales en mi contexto: señales de tránsito, indicios, banderas, colores, etc.
Reconozco y uso códigos no verbales en situaciones comunicativas auténticas..
Reconozco las características de los diferentes medios de comunicación masiva.
Selecciono y clasifico la información emitida por los diferentes medios de comunicación.
Elaboro planes textuales con la información seleccionada de los medios de comunicación.
Produzco textos orales y escritos con base en planes en los que utilizo la información recogida de los medios.
Socializo, analizo y corrijo los textos producidos con base en la información tomada de los medios de comunicación masiva..
Leo diversos tipos de texto literario: relatos mitológicos, leyendas, cuentos, fábulas, poemas y obras teatrales.
Reconozco, en los textos literarios que leo, elementos tales como tiempo, espacio, acción, personajes.
Propongo hipótesis predictivas acerca de un texto literario, partiendo de aspectos como título, tipo de texto, época de la producción, etc.
Relaciono las hipótesis predictivas que surgen de los textos que leo, con su contexto y con otros textos, sean literarios o no.
Comparo textos narrativos, líricos y dramáticos, teniendo en cuenta algunos de sus elementos constitutivos.
EBC de Matemáticas
Fuente: Estándares Básicos de Competencias en Matemáticas (MEN, 2006).8 Ejes articuladores: pensamiento numérico y sistemas numéricos; pensamiento espacial y sistemas geométricos; pensamiento métrico y sistemas de medidas; pensamiento aleatorio y sistemas de datos; pensamiento variacional y sistemas algebraicos y analíticos.
Ciclo 1 — Al terminar tercer grado (aplica si el niño está en 1.°, 2.° o 3.°)
Reconozco significados del número en diferentes contextos (medición, conteo, comparación, codificación, localización entre otros).
Describo, comparo y cuantifico situaciones con números, en diferentes contextos y con diversas representaciones.
Describo situaciones que requieren el uso de medidas relativas.
Describo situaciones de medición utilizando fracciones comunes.
Uso representaciones –principalmente concretas y pictóricas– para explicar el valor de posición en el sistema de numeración decimal.
Uso representaciones –principalmente concretas y pictóricas– para realizar equivalencias de un número en las diferentes unidades del sistema decimal.
Reconozco propiedades de los números (ser par, ser impar, etc.) y relaciones entre ellos (ser mayor que, ser menor que, ser múltiplo de, ser divisible por, etc.) en diferentes contextos.
Resuelvo y formulo problemas en situaciones aditivas de composición y de transformación.
Resuelvo y formulo problemas en situaciones de variación proporcional.
Uso diversas estrategias de cálculo (especialmente cálculo mental) y de estimación para resolver problemas en situaciones aditivas y multiplicativas.
Identifico, si a la luz de los datos de un problema, los resultados obtenidos son o no razonables.
Identifico regularidades y propiedades de los números utilizando diferentes instrumentos de cálculo (calculadoras, ábacos, bloques multibase, etc.).
Diferencio atributos y propiedades de objetos tridimensionales.
Dibujo y describo cuerpos o figuras tridimensionales en distintas posiciones y tamaños.
Reconozco nociones de horizontalidad, verticalidad, paralelismo y perpendicularidad en distintos contextos y su condición relativa con respecto a diferentes sistemas de referencia.
Represento el espacio circundante para establecer relaciones espaciales.
Reconozco y aplico traslaciones y giros sobre una figura.
Reconozco y valoro simetrías en distintos aspectos del arte y el diseño.
Reconozco congruencia y semejanza entre figuras (ampliar, reducir).
Realizo construcciones y diseños utilizando cuerpos y figuras geométricas tridimensionales y dibujos o figuras geométricas bidimensionales.
Desarrollo habilidades para relacionar dirección, distancia y posición en el espacio. Matemáticas.
Reconozco y describo regularidades y patrones en distintos contextos (numérico, geométrico, musical, entre otros).
Describo cualitativamente situaciones de cambio y variación utilizando el lenguaje natural, dibujos y gráficas.
Reconozco y genero equivalencias entre expresiones numéricas y describo cómo cambian los símbolos aunque el valor siga igual.
Construyo secuencias numéricas y geométricas utilizando propiedades de los números y de las figuras geométricas.
Clasifico y organizo datos de acuerdo a cualidades y atributos y los presento en tablas.
Interpreto cualitativamente datos referidos a situaciones del entorno escolar.
Describo situaciones o eventos a partir de un conjunto de datos.
Represento datos relativos a mi entorno usando objetos concretos, pictogramas y diagramas de barras.
Identifico regularidades y tendencias en un conjunto de datos.
Explico –desde mi experiencia– la posibilidad o imposibilidad de ocurrencia de eventos cotidianos.
Predigo si la posibilidad de ocurrencia de un evento es mayor que la de otro.
Resuelvo y formulo preguntas que requieran para su solución coleccionar y analizar datos del entorno próximo.
Reconozco en los objetos propiedades o atributos que se puedan medir (longitud, área, volumen, capacidad, peso y masa) y, en los eventos, su duración.
Comparo y ordeno objetos respecto a atributos medibles.
Realizo y describo procesos de medición con patrones arbitrarios y algunos estandarizados, de acuerdo al contexto.
Analizo y explico sobre la pertinencia de patrones e instrumentos en procesos de medición.
Realizo estimaciones de medidas requeridas en la resolución de problemas relativos particularmente a la vida social, económica y de las ciencias.
Reconozco el uso de las magnitudes y sus unidades de medida en situaciones aditivas y multiplicativas.
Ciclo 2 — Al terminar quinto grado (aplica si el niño está en 4.° o 5.°)
Interpreto las fracciones en diferentes contextos: situaciones de medición, relaciones parte todo, cociente, razones y proporciones.
Identifico y uso medidas relativas en distintos contextos.
Utilizo la notación decimal para expresar fracciones en diferentes contextos y relaciono estas dos notaciones con la de los porcentajes.
Justifico el valor de posición en el sistema de numeración decimal en relación con el conteo recurrente de unidades.
Resuelvo y formulo problemas cuya estrategia de solución requiera de las relaciones y propiedades de los números naturales y sus operaciones.
Resuelvo y formulo problemas en situaciones aditivas de composición, transformación, comparación e igualación.
Resuelvo y formulo problemas en situaciones de proporcionalidad directa, inversa y producto de medidas.
Identifico la potenciación y la radicación en contextos matemáticos y no matemáticos.
Modelo situaciones de dependencia mediante la proporcionalidad directa e inversa.
Uso diversas estrategias de cálculo y de estimación para resolver problemas en situaciones aditivas y multiplicativas.
Identifico, en el contexto de una situación, la necesidad de un cálculo exacto o aproximado y lo razonable de los resultados obtenidos.
Justifico regularidades y propiedades de los números, sus relaciones y operaciones.
Comparo y clasifico objetos tridimensionales de acuerdo con componentes (caras, lados) y propiedades.
Comparo y clasifico figuras bidimensionales de acuerdo con sus componentes (ángulos, vértices) y características.
Identifico, represento y utilizo ángulos en giros, aberturas, inclinaciones, figuras, puntas y esquinas en situaciones estáticas y dinámicas.
Utilizo sistemas de coordenadas para especificar localizaciones y describir relaciones espaciales.
Identifico y justifico relaciones de congruencia y semejanza entre figuras.
Construyo y descompongo figuras y sólidos a partir de condiciones dadas.
Conjeturo y verifico los resultados de aplicar transformaciones a figuras en el plano para construir diseños.
Construyo objetos tridimensionales a partir de representaciones bidimensionales y puedo realizar el proceso contrario en contextos de arte, diseño y arquitectura. Matemáticas.
Describo e interpreto variaciones representadas en gráficos.
Predigo patrones de variación en una secuencia numérica, geométrica o gráfica.
Represento y relaciono patrones numéricos con tablas y reglas verbales.
Analizo y explico relaciones de dependencia entre cantidades que varían en el tiempo con cierta regularidad en situaciones económicas, sociales y de las ciencias naturales.
Construyo igualdades y desigualdades numéricas como representación de relaciones entre distintos datos.
Represento datos usando tablas y gráficas (pictogramas, gráficas de barras, diagramas de líneas, diagramas circulares).
Comparo diferentes representaciones del mismo conjunto de datos.
Interpreto información presentada en tablas y gráficas. (pictogramas, gráficas de barras, diagramas de líneas, diagramas circulares).
Conjeturo y pongo a prueba predicciones acerca de la posibilidad de ocurrencia de eventos.
Describo la manera como parecen distribuirse los distintos datos de un conjunto de ellos y la comparo con la manera como se distribuyen en otros conjuntos de datos.
Uso e interpreto la media (o promedio) y la mediana y comparo lo que indican.
Resuelvo y formulo problemas a partir de un conjunto de datos provenientes de observaciones, consultas o experimentos.
Diferencio y ordeno, en objetos y eventos, propiedades o atributos que se puedan medir (longitudes, distancias, áreas de superficies, volúmenes de cuerpos sólidos, volúmenes de líquidos y capacidades de recipientes; pesos y masa de cuerpos sólidos; duración de eventos o procesos; amplitud de ángulos).
Selecciono unidades, tanto convencionales como estandarizadas, apropiadas para diferentes mediciones.
Utilizo y justifico el uso de la estimación para resolver problemas relativos a la vida social, económica y de las ciencias, utilizando rangos de variación.
Utilizo diferentes procedimientos de cálculo para hallar el área de la superficie exterior y el volumen de algunos cuerpos sólidos.
Justifico relaciones de dependencia del área y volumen, respecto a las dimensiones de figuras y sólidos.
Reconozco el uso de algunas magnitudes (longitud, área, volumen, capacidad, peso y masa, duración, rapidez, temperatura) y de algunas de las unidades que se usan para medir cantidades de la magnitud respectiva en situaciones aditivas y multiplicativas.
Describo y argumento relaciones entre el perímetro y el área de figuras diferentes, cuando se fija una de estas medidas.
EBC de Ciencias Sociales
Fuente: Estándares Básicos de Competencias en Ciencias Sociales (MEN, 2006).8 Ejes articuladores: identidad (comprensión de sí mismo y de la cultura propia); relaciones espaciales (localización, uso del territorio); relaciones con la historia y las culturas (tiempo, cambio y permanencia); y pensamiento social (normas, conflictos, diferencias).
Ciclo 1 — Al terminar tercer grado (aplica si el niño está en 1.°, 2.° o 3.°)
Identifico algunas características físicas, sociales, culturales y emocionales que hacen de mí un ser único.
Identifico y describo algunas características socioculturales de comunidades a las que pertenezco y de otras diferentes a las mías.
Identifico y describo cambios y aspectos que se mantienen en mí y en las organizaciones de mi entorno.
Reconozco en mi entorno cercano las huellas que dejaron las comunidades que lo ocuparon en el pasado (monumentos, museos, sitios de conservación histórica…).
Identifico y describo algunos elementos que permiten reconocerme como miembro de un grupo regional y de una nación (territorio, lenguas, costumbres, símbolos patrios…).
Reconozco características básicas de la diversidad étnica y cultural en Colombia.
Identifico los aportes culturales que mi comunidad y otras diferentes a la mía han hecho a lo que somos hoy.
Me ubico en el entorno físico y de representación (en mapas y planos) utilizando referentes espaciales como arriba, abajo, dentro, fuera, derecha, izquierda.
Establezco relaciones entre los espacios físicos que ocupo (salón de clase, colegio, municipio…) y sus representaciones (mapas, planos, maquetas…).
Reconozco diversas formas de representación de la Tierra.
Reconozco y describo las características físicas de las principales formas del paisaje.
Identifico y describo las características de un paisaje natural y de un paisaje cultural.
Establezco relaciones entre los accidentes geográficos y su representación gráfica.
Establezco relaciones entre paisajes naturales y paisajes culturales.
Identifico formas de medir el tiempo (horas, días, años…) y las relaciono con las actividades de las personas.
Comparo actividades económicas que se llevan a cabo en diferentes entornos.
Establezco relaciones entre el clima y las actividades económicas de las personas.
Reconozco, describo y comparo las actividades económicas de algunas personas en mi entorno y el efecto de su trabajo en la comunidad.
Identifico los principales recursos naturales (renovables y no renovables).
Reconozco factores de tipo económico que generan bienestar o confl icto en la vida social.
Reconozco que los recursos naturales son finitos y exigen un uso responsable.
Identifico y describo características y funciones básicas de organizaciones sociales y políticas de mi entorno (familia, colegio, barrio, vereda, corregimiento, resguardo, territorios afrocolombianos, municipio…).
Identifico situaciones cotidianas que indican cumplimiento o incumplimiento en las funciones de algunas organizaciones sociales y políticas de mi entorno.
Comparo las formas de organización propias de los grupos pequeños (familia, salón de clase, colegio…) con las de los grupos más grandes (resguardo, territorios afrocolombianos, municipio…).
Identifico factores que generan cooperación y confl icto en las organizaciones sociales y políticas de mi entorno y explico por qué lo hacen.
Identifico mis derechos y deberes y los de otras personas en las comunidades a las que pertenezco.
Identifico normas que rigen algunas comunidades a las que pertenezco y explico su utilidad.
Reconozco algunas normas que han sido construidas socialmente y distingo aquellas en cuya construcción y modificación puedo participar (normas del hogar, manual de convivencia escolar, Código de Tránsito…).
Reconozco y respeto diferentes puntos de vista.
Comparo mis aportes con los de mis compañeros y compañeras e incorporo en mis conocimientos y juicios elementos valiosos aportados por otros.
Respeto mis rasgos individuales y los de otras personas (género, etnia, religión…).
Reconozco situaciones de discriminación y abuso por irrespeto a los rasgos individuales de las personas (religión, etnia, género, discapacidad…) y propongo formas de cambiarlas.
Reconozco la diversidad étnica y cultural de mi comunidad, mi ciudad…
Participo en actividades que expresan valores culturales de mi comunidad y de otras diferentes a la mía.
Participo en la construcción de normas para la convivencia en los grupos sociales y políticos a los que pertenezco (familia, colegio, barrio…).
Cuido mi cuerpo y mis relaciones con los demás.
Cuido el entorno que me rodea y manejo responsablemente las basuras.
Uso responsablemente los recursos (papel, agua, alimentos…).
Hago preguntas acerca de los fenómenos políticos, económicos sociales y culturales estudiados (Prehistoria, pueblos prehispánicos colombianos…).
Planteo conjeturas que respondan provisionalmente a estas preguntas.
Utilizo diferentes tipos de fuentes para obtener la información que necesito (textos escolares, cuentos y relatos, entrevistas a profesores y familiares, dibujos, fotografías y recursos virtuales…).
Organizo la información obtenida utilizando cuadros, gráficas… y la archivo en orden.
Establezco relaciones entre información localizada en diferentes fuentes y propongo respuestas a las preguntas que planteo.
Reconozco que los fenómenos estudiados tienen diversos aspectos que deben ser tenidos en cuenta (cambios a lo largo del tiempo, ubicación geográfica, aspectos económicos…).
Reviso mis conjeturas iniciales.
Utilizo diversas formas de expresión (exposición oral, dibujos, carteleras, textos cortos…) para comunicar los resultados de mi investigación.
Doy crédito a las diferentes fuentes de la información obtenida (cuento a mis compañeros a quién entrevisté, qué libros leí, qué dibujos comparé, cito información de fuentes escritas…).
Ciclo 2 — Al terminar quinto grado (aplica si el niño está en 4.° o 5.°)
Identifico y explico fenómenos sociales y económicos que permitieron el paso del nomadismo al sedentarismo (agricultura, división del trabajo…).
Identifico y describo características sociales, políticas, económicas y culturales de las primeras organizaciones humanas (banda, clan, tribu…).
Comparo características de las primeras organizaciones humanas con las de las organizaciones de mi entorno.
Identifico algunas condiciones políticas, sociales, económicas y tecnológicas que permitieron las exploraciones de la antigüedad y el medioevo.
Establezco algunas relaciones entre exploraciones de la antigüedad y el medioevo y exploraciones de la actualidad.
Identifico, describo y comparo algunas características sociales, políticas, económicas y culturales de las comunidades prehispánicas de Colombia y América.
Relaciono estas características con las condiciones del entorno particular de cada cultura.
Comparo características de los grupos prehispánicos con las características sociales, políticas, económicas y culturales actuales.
Identifico los propósitos de las organizaciones coloniales españolas y describo aspectos básicos de su funcionamiento.
Identifico y comparo algunas causas que dieron lugar a los diferentes períodos históricos en Colombia (Descubrimiento, Colonia, Independencia…). 40 50 Al terminar quinto grado… Reconozco que tanto los individuos como las organizaciones sociales se transforman con el tiempo, construyen un legado y dejan huellas que permanecen en las sociedades actuales. Ciencias Sociales.
Me ubico en el entorno físico utilizando referentes espaciales (izquierda, derecha, puntos cardinales).
Utilizo coordenadas, escalas y convenciones para ubicar los fenómenos históricos y culturales en mapas y planos de representación.
Identifico y describo características de las diferentes regiones naturales del mundo (desiertos, polos, selva húmeda tropical, océanos…).
Identifico y describo algunas de las características humanas (sociales, culturales…) de las diferentes regiones naturales del mundo.
Clasifico y describo diferentes actividades económicas (producción, distribución, consumo…) en diferentes sectores económicos (agrícola, ganadero, minero, industrial…) y reconozco su impacto en las comunidades.
Reconozco los diferentes usos que se le dan a la tierra y a los recursos naturales en mi entorno y en otros (parques naturales, ecoturismo, ganadería, agricultura…).
Identifico organizaciones que resuelven las necesidades básicas (salud, educación, vivienda, servicios públicos, vías de comunicación…) en mi comunidad, en otras y en diferentes épocas y culturas; identifico su impacto sobre el desarrollo.
Identifico y describo algunas características de las organizaciones político-administrativas colombianas en diferentes épocas (Real Audiencia, Congreso, Concejo Municipal…).
Comparo características del sistema político-administrativo de Colombia –ramas del poder público– en las diferentes épocas.
Explico semejanzas y diferencias entre organizaciones político-administrativas.
Explico el impacto de algunos hechos históricos en la formación limítrofe del territorio colombiano (Virreinato de la Nueva Granada, Gran Colombia, separación de Panamá…).
Reconozco las responsabilidades que tienen las personas elegidas por voto popular y algunas características de sus cargos (personeros estudiantiles, concejales, congresistas, presidente…)
Conozco los Derechos de los Niños e identifico algunas instituciones locales, nacionales e internacionales que velan por su cumplimiento (personería estudiantil, comisaría de familia, Unicef…).
Reconozco y respeto diferentes puntos de vista acerca de un fenómeno social.
Participo en debates y discusiones: asumo una posición, la confronto con la de otros, la defiendo y soy capaz de modificar mis posturas si lo considero pertinente.
Respeto mis rasgos individuales y culturales y los de otras personas (género, etnia…).
Asumo una posición crítica frente a situaciones de discriminación y abuso por irrespeto a los rasgos individuales de las personas (etnia, género…) y propongo formas de cambiarlas.
Reconozco la importancia de los aportes de algunos legados culturales, científicos, tecnológicos, artísticos, religiosos… en diversas épocas y entornos.
Participo en la construcción de normas para la convivencia en los grupos a los que pertenezco (familia, colegio, barrio…).
Cuido mi cuerpo y mis relaciones con las demás personas.
Cuido el entorno que me rodea y manejo responsablemente las basuras.
Uso responsablemente los recursos (papel, agua, alimento, energía…).
Formulo preguntas acerca de hechos políticos, económicos sociales y culturales.
Planteo conjeturas que respondan provisionalmente estas preguntas.
Recolecto y registro sistemáticamente información que obtengo de diferentes fuentes (orales, escritas, iconográficas, virtuales…).
Identifico las características básicas de los documentos que utilizo (qué tipo de documento es, quién es el autor, a quién está dirigido, de qué habla…).
Clasifico correctamente las fuentes que utilizo primarias, secundarias, orales, escritas, iconográficas…).
Tomo notas de las fuentes estudiadas; clasifico, organizo y archivo la información obtenida.
Establezco relaciones entre información localizada en diferentes fuentes y propongo respuestas a las preguntas que planteo.
Analizo los resultados y saco conclusiones.
Comparo las conclusiones a las que llego después de hacer la investigación con mis conjeturas iniciales.
Reconozco que los fenómenos estudiados pueden observarse desde diversos puntos de vista.
Identifico y tengo en cuenta los diversos aspectos que hacen parte de los fenómenos que estudio (ubicación geográfica, evolución histórica, organización política, económica, social y cultural…).
Reconozco redes complejas de relaciones entre eventos históricos, sus causas, sus consecuencias y su incidencia en la vida de los diferentes agentes involucrados.
Utilizo diversas formas de expresión (escritos, exposiciones orales, carteleras…), para comunicar los resultados de mi investigación.
Cito adecuadamente las diferentes fuentes de la información obtenida.
EBC de Ciencias Naturales y Educación Ambiental
Fuente: Estándares Básicos de Competencias en Ciencias Naturales (MEN, 2006).8 Ejes articuladores: entorno vivo; entorno físico; ciencia, tecnología y sociedad; y desarrollo de compromisos personales y sociales (incluye el cuidado del ambiente).
Ciclo 1 — Al terminar tercer grado (aplica si el niño está en 1.°, 2.° o 3.°)
Establezco relaciones entre las funciones de los cinco sentidos.
Describo mi cuerpo y el de mis compañeros y compañeras.
Describo características de seres vivos y objetos inertes, establezco semejanzas y diferencias entre ellos y los clasifico.
Propongo y verifico necesidades de los seres vivos.
Observo y describo cambios en mi desarrollo y en el de otros seres vivos.
Describo y verifico ciclos de vida de seres vivos.
Reconozco que los hijos y las hijas se parecen a sus padres y describo algunas características que se heredan.
Identifico y describo la fl ora, la fauna, el agua y el suelo de mi entorno.
Explico adaptaciones de los seres vivos al ambiente.
Comparo fósiles y seres vivos; identifico características que se mantienen en el tiempo.
Identifico patrones comunes a los seres vivos. Ciencias Naturales 10 30 Me identifico como un ser vivo que comparte algunas características con otros seres vivos y que se relaciona con ellos en un entorno en el que todos nos desarrollamos. Al final de tercer grado…
Describo y clasifico objetos según características que percibo con los cinco sentidos.
Propongo y verifico diversas formas de medir sólidos y líquidos.
Establezco relaciones entre magnitudes y unidades de medida apropiadas.
Identifico diferentes estados físicos de la materia (el agua, por ejemplo) y verifico causas para cambios de estado.
Identifico y comparo fuentes de luz, calor y sonido y su efecto sobre diferentes seres vivos.
Identifico situaciones en las que ocurre transferencia de energía térmica y realizo experiencias para verificar el fenómeno.
Clasifico luces según color, intensidad y fuente.
Clasifico sonidos según tono, volumen y fuente.
Propongo experiencias para comprobar la propagación de la luz y del sonido.
Identifico tipos de movimiento en seres vivos y objetos, y las fuerzas que los producen.
Verifico las fuerzas a distancia generadas por imanes sobre diferentes objetos.
Construyo circuitos eléctricos simples con pilas.
Registro el movimiento del Sol, la Luna y las estrellas en el cielo, en un periodo de tiempo.
Clasifico y comparo objetos según sus usos.
Diferencio objetos naturales de objetos creados por el ser humano.
Identifico objetos que emitan luz o sonido.
Identifico circuitos eléctricos en mi entorno.
Analizo la utilidad de algunos aparatos eléctricos a mi alrededor.
Identifico aparatos que utilizamos hoy y que no se utilizaban en épocas pasadas.
Asocio el clima con la forma de vida de diferentes comunidades.
Identifico necesidades de cuidado de mi cuerpo y el de otras personas.
Escucho activamente a mis compañeros y compañeras y reconozco puntos de vista diferentes.
Valoro y utilizo el conocimiento de diversas personas de mi entorno.
Cumplo mi función y respeto la de otras personas en el trabajo en grupo.
Reconozco la importancia de animales, plantas, agua y suelo de mi entorno y propongo estrategias para cuidarlos.
Observo el mundo en el que vivo.
Formulo preguntas a partir de una observación o experiencia y escojo algunas de ellas para buscar posibles respuestas.
Propongo explicaciones provisionales para responder mis preguntas.
Identifico condiciones que infl uyen en los resultados de una experiencia y que pueden permanecer constantes o cambiar (variables).
Diseño y realizo experimentos modificando una sola variable para dar respuesta a preguntas.
Realizo mediciones con instrumentos convencionales (balanza, báscula, cronómetro, termómetro…) y no convencionales (paso, cuarta, pie, braza, vaso…).
Registro mis observaciones, datos y resultados de manera organizada y rigurosa (sin alteraciones), en forma escrita y utilizando esquemas, gráficos y tablas.
Busco información en diversas fuentes (libros, Internet, experiencias y experimentos propios y de otros…) y doy el crédito correspondiente.
Establezco relaciones entre la información y los datos recopilados.
Selecciono la información que me permite responder a mis preguntas y determino si es suficiente.
Saco conclusiones de mis experimentos, aunque no obtenga los resultados esperados.
Propongo respuestas a mis preguntas y las comparo con las de otras personas.
Persisto en la búsqueda de respuestas a mis preguntas.
Comunico, oralmente y por escrito, el proceso de indagación y los resultados que obtengo.
Ciclo 2 — Al terminar quinto grado (aplica si el niño está en 4.° o 5.°)
Explico la importancia de la célula como unidad básica de los seres vivos.
Identifico los niveles de organización celular de los seres vivos.
Identifico en mi entorno objetos que cumplen funciones similares a las de mis órganos y sustento la comparación.
Represento los diversos sistemas de órganos del ser humano y explico su función.
Clasifico seres vivos en diversos grupos taxonómicos (plantas, animales, microorganismos…).
Indago acerca del tipo de fuerza (compresión, tensión o torsión) que puede fracturar diferentes tipos de huesos.
Identifico máquinas simples en el cuerpo de seres vivos y explico su función.
Investigo y describo diversos tipos de neuronas, las comparo entre sí y con circuitos eléctricos.
Analizo el ecosistema que me rodea y lo comparo con otros.
Identifico adaptaciones de los seres vivos, teniendo en cuenta las características de los ecosistemas en que viven.
Explico la dinámica de un ecosistema, teniendo en cuenta las necesidades de energía y nutrientes de los seres vivos (cadena alimentaria).
Describo y verifico el efecto de la transferencia de energía térmica en los cambios de estado de algunas sustancias.
Verifico la posibilidad de mezclar diversos líquidos, sólidos y gases.
Propongo y verifico diferentes métodos de separación de mezclas.
Establezco relaciones entre objetos que tienen masas iguales y volúmenes diferentes o viceversa y su posibilidad de fl otar.
Comparo movimientos y desplazamientos de seres vivos y objetos.
Relaciono el estado de reposo o movimiento de un objeto con las fuerzas aplicadas sobre éste.
Describo fuerzas y torques en máquinas simples.
Verifico la conducción de electricidad o calor en materiales.
Identifico las funciones de los componentes de un circuito eléctrico.
Describo los principales elementos del sistema solar y establezco relaciones de tamaño, movimiento y posición.
Comparo el peso y la masa de un objeto en diferentes puntos del sistema solar.
Describo las características físicas de la Tierra y su atmósfera.
Relaciono el movimiento de traslación con los cambios climáticos.
Establezco relaciones entre mareas, corrientes marinas, movimiento de placas tectónicas, formas del paisaje y relieve, y las fuerzas que los generan.
Identifico máquinas simples en objetos cotidianos y describo su utilidad.
Construyo máquinas simples para solucionar problemas cotidianos.
Identifico, en la historia, situaciones en las que en ausencia de motores potentes se utilizaron máquinas simples.
Analizo características ambientales de mi entorno y peligros que lo amenazan.
Establezco relaciones entre el efecto invernadero, la lluvia ácida y el debilitamiento de la capa de ozono con la contaminación atmosférica.
Asocio el clima y otras características del entorno con los materiales de construcción, los aparatos eléctricos más utilizados, los recursos naturales y las costumbres de diferentes comunidades.
Verifico que la cocción de alimentos genera cambios físicos y químicos.
Identifico y describo aparatos que generan energía luminosa, térmica y mecánica.
Identifico y establezco las aplicaciones de los circuitos eléctricos en el desarrollo tecnológico.
Establezco relaciones entre microorganismos y salud.
Reconozco los efectos nocivos del exceso en el consumo de cafeína, tabaco, drogas y licores.
Establezco relaciones entre deporte y salud física y mental.
Escucho activamente a mis compañeros y compañeras, reconozco puntos de vista diferentes y los comparo con los míos.
Reconozco y acepto el escepticismo de mis compañeros y compañeras ante la información que presento.
Valoro y utilizo el conocimiento de diferentes personas de mi entorno.
Cumplo mi función cuando trabajo en grupo, respeto las funciones de otros y contribuyo a lograr productos comunes.
Identifico y acepto diferencias en las formas de vida y de pensar.
Reconozco y respeto mis semejanzas y diferencias con los demás en cuanto a género, aspecto y limitaciones físicas.
Propongo alternativas para cuidar mi entorno y evitar peligros que lo amenazan.
Cuido, respeto y exijo respeto por mi cuerpo y el de las demás personas.
Respeto y cuido los seres vivos y los objetos de mi entorno.
Formulo preguntas específicas sobre una observación o experiencia y escojo una para indagar y encontrar posibles respuestas.
Formulo explicaciones posibles, con base en el conocimiento cotidiano, teorías y modelos científicos, para contestar preguntas.
Identifico condiciones que infl uyen en los resultados de un experimento y que pueden permanecer constantes o cambiar (variables).
Diseño y realizo experimentos y verifico el efecto de modificar diversas variables para dar respuesta a preguntas.
Realizo mediciones con instrumentos y equipos adecuados a las características y magnitudes de los objetos y las expreso en las unidades correspondientes.
Registro mis observaciones y resultados utilizando esquemas, gráficos y tablas.
Registro mis resultados en forma organizada y sin alteración alguna.
Establezco diferencias entre descripción, explicación y evidencia.
Utilizo las matemáticas como una herramienta para organizar, analizar y presentar datos.
Busco información en diferentes fuentes.
Evalúo la calidad de la información, escojo la pertinente y doy el crédito correspondiente.
Establezco relaciones causales entre los datos recopilados.
Establezco relaciones entre la información recopilada en otras fuentes y los datos generados en mis experimentos.
Analizo si la información que he obtenido es suficiente para contestar mis preguntas o sustentar mis explicaciones.
Saco conclusiones de los experimentos que realizo, aunque no obtenga los resultados esperados.
Persisto en la búsqueda de respuestas a mis preguntas.
Propongo respuestas a mis preguntas y las comparo con las de otras personas y con las de teorías científicas.
Sustento mis respuestas con diversos argumentos.
Identifico y uso adecuadamente el lenguaje propio de las ciencias.
Comunico oralmente y por escrito el proceso de indagación y los resultados que obtengo, utilizando gráficas, tablas y ecuaciones aritméticas.
Relaciono mis conclusiones con las presentadas por otros autores y formulo nuevas preguntas.
EBC de Inglés (lenguas extranjeras)
Fuente: Estándares Básicos de Competencias en Lenguas Extranjeras: Inglés (MEN, 2006), complementados por el Programa Nacional de Bilingüismo / Colombia Bilingüe.4 8 A diferencia de las otras áreas, los estándares de inglés se organizan por niveles de dominio (Básico, Preintermedio, Intermedio, Avanzado), articulados con el Marco Común Europeo de Referencia; la meta nacional es que al terminar grado 11.° el estudiante alcance el nivel preintermedio (B1).4 Toda la primaria corresponde al nivel básico, trabajado en las cinco habilidades: escucha, lectura, escritura, monólogo (hablar solo) y conversación.
En la práctica, para el tutor de primaria el detalle por grado ya está dado por los DBA de inglés (sección II): el tutor toma esos DBA como ruta anual y entiende que todo apunta a que el niño pueda, al salir de 5.°, sostener intercambios sencillos sobre sí mismo, su familia, su escuela y su entorno.
EBC de Tecnología e informática
No existen estándares oficiales para esta área; el tutor usa los cuatro procesos de la Guía 30 (apropiación y uso, solución de problemas, manejo de herramientas, ética y ciudadanía digital) y la progresión por grado de la sección II.6.8

III.6 Lineamientos curriculares: el “para qué” de cada área
Los Lineamientos Curriculares (Serie MEN, desde 1998) son el documento que explica el sentido formativo de cada área: por qué se enseña, qué tipo de persona forma y cómo se organizan sus contenidos. El tutor los usa como brújula pedagógica:8
Matemáticas: formar el razonamiento lógico-matemático a través de cinco pensamientos (numérico, espacial, métrico, aleatorio y variacional) y cinco procesos generales que el tutor debe activar en cada explicación: razonar, resolver y plantear problemas, comunicar, modelar, y elaborar/comparar/ejercitar procedimientos. Traducción para el tutor: no basta con que el niño dé la respuesta; debe poder explicar cómo la obtuvo y usarla en un problema nuevo.
Lenguaje: formar lectores, escritores, hablantes y oyentes competentes, mediante la literatura, los medios de comunicación y los sistemas simbólicos. Traducción: toda actividad de lengua debe tener un propósito comunicativo real (contar algo a alguien, entender un aviso, escribir un mensaje), no ejercicios desconectados.
Ciencias naturales: formar pensamiento científico mediante la indagación (preguntar, observar, comparar, experimentar, comunicar) sobre el entorno vivo y el entorno físico, con compromisos de cuidado personal y ambiental. Traducción: el tutor guía al niño a hacerse preguntas y comprobar, no solo a memorizar datos.
Ciencias sociales: formar la comprensión del mundo social y la identidad, desde lo cercano (cuerpo, familia, barrio) hacia lo amplio (municipio, departamento, nación, mundo), integrando espacio, tiempo y convivencia. Traducción: anclar cada tema en la experiencia del niño y en Colombia.
Inglés: desarrollar la competencia comunicativa progresiva en las cinco habilidades, en contextos significativos y lúdicos.4
Tecnología e informática: “ser competente en tecnología” es usarla para resolver problemas reales, con ética y criterio, no solo operar aparatos.8
III.7 Mallas de aprendizaje: la ruta sugerida dentro del año
Las Mallas de aprendizaje (MEN, diciembre de 2017) son la herramienta que conecta los DBA con la planeación del año escolar: proponen progresiones de contenidos grado a grado (qué orden tiene sentido seguir), con aprendizajes, evidencias, ejemplos de actividades y tips de evaluación formativa. Datos clave:9
Existen para Matemáticas, Lenguaje y Ciencias Naturales, grados 1.° a 5.° (construidas con cerca de 4.000 docentes y 20 facultades de educación).
Son flexibles: no son un calendario obligatorio, sino un referente que cada colegio adapta a su contexto (el MEN las diseñó para la realidad pluriétnica y multicultural del país).
Uso por el tutor: cuando el niño pregunta “¿qué sigue?” o el tutor planea un repaso, las mallas indican la secuencia razonable dentro del grado. Para Ciencias Sociales, Inglés y Tecnología, la progresión la dan los propios DBA y los lineamientos.


## IV. OBJETIVOS ESPECÍFICOS DE LA EDUCACIÓN PRIMARIA (LEY 115 DE 1994, ART. 21)
Estos son los objetivos que la ley fija para los cinco grados de primaria. Son el propósito de fondo de todo lo que hace el tutor; cada refuerzo, explicación o juego debe contribuir a alguno de ellos.1 2
La formación de los valores fundamentales para la convivencia en una sociedad democrática, participativa y pluralista.
El fomento del deseo de saber, de la iniciativa personal frente al conocimiento y frente a la realidad social, así como del espíritu crítico.
El desarrollo de las habilidades comunicativas básicas para leer, comprender, escribir, escuchar, hablar y expresarse correctamente en lengua castellana y también en la lengua materna, en el caso de los grupos étnicos con tradición lingüística propia, así como el fomento de la afición por la lectura.
El desarrollo de la capacidad para apreciar y utilizar la lengua como medio de expresión estética.
El desarrollo de los conocimientos matemáticos necesarios para manejar y utilizar operaciones simples de cálculo y procedimientos lógicos elementales en diferentes situaciones, así como la capacidad para solucionar problemas que impliquen estos conocimientos.
La comprensión básica del medio físico, social y cultural en el nivel local, nacional y universal, de acuerdo con el desarrollo intelectual correspondiente a la edad.
La asimilación de conceptos científicos en las áreas de conocimiento que sean objeto de estudio, de acuerdo con el desarrollo intelectual y la edad.
La valoración de la higiene y la salud del propio cuerpo y la formación para la protección de la naturaleza y el ambiente.
El conocimiento y ejercitación del propio cuerpo, mediante la práctica de la educación física, la recreación y los deportes adecuados a su edad y conducentes a un desarrollo físico y armónico.
La formación para la participación y organización infantil y la utilización adecuada del tiempo libre.
El desarrollo de valores civiles, éticos y morales, de organización social y de convivencia humana.
La formación artística mediante la expresión corporal, la representación, la música, la plástica y la literatura.
El desarrollo de habilidades de conversación, lectura y escritura al menos en una lengua extranjera (texto vigente según la Ley 1651 de 2013).2
La iniciación en el conocimiento de la Constitución Política. ñ) La adquisición de habilidades para desempeñarse con autonomía en la sociedad.
Traducción operativa para el tutor: los literales c, d, e, f, g, h, m y n se cubren directamente con las cinco áreas del pensum; los literales a, b, k y ñ se atienden de forma transversal en el estilo de acompañamiento (fomentar curiosidad, espíritu crítico, convivencia y autonomía); los literales i, j y l (cuerpo, tiempo libre, arte) están fuera del alcance del tutor y se derivan a la familia y al colegio.


## V. COMPLEMENTOS OPERATIVOS DEL TUTOR
V.1 Intensidad horaria por área (dato de contexto)
Lo que fija la norma (Decreto 1850 de 2002, compilado en el Decreto 1075 de 2015):
Nivel
 | Horas semanales mínimas
 | Horas anuales mínimas
 | 
Preescolar
 | 20
 | 800
 | 
Básica primaria
 | 25
 | 1.000
 | 
Básica secundaria y media
 | 30
 | 1.200
 | 
Las horas se cuentan en horas efectivas de 60 minutos, durante las 40 semanas lectivas del año escolar.10
Como mínimo el 80 % de esa intensidad se dedica a las áreas obligatorias y fundamentales (las cinco del tutor, más las cuatro no cubiertas).10
La norma NO reparte horas por materia: la distribución entre áreas la define cada colegio en su plan de estudios. Por eso el tutor no debe afirmar “matemáticas son 5 horas por ley”; lo correcto es: primaria tiene mínimo 25 horas semanales en total y lengua y matemáticas suelen llevar la mayor carga en la práctica escolar.
Uso por el tutor: es solo contexto. Le sirve para entender cuánto peso real tiene cada área en la semana del niño y para dimensionar cuánto refuerzo tiene sentido ofrecer en casa (sesiones cortas y frecuentes, no maratones).
V.2 Lo que evalúa el Estado: pruebas Saber 3.° y Saber 5.° (ICFES)
Las pruebas Saber son evaluaciones externas estandarizadas del ICFES que miden las competencias básicas definidas por el MEN al final de los ciclos:
Prueba
 | Grado
 | Áreas evaluadas11
 | 
Saber 3.°
 | Al cursar 3.°
 | Lenguaje (lectura) y Matemáticas
 | 
Saber 5.°
 | Al cursar 5.°
 | Lenguaje, Matemáticas, Ciencias Naturales y Competencias Ciudadanas
 | 
Cómo el tutor convierte esto en valor agregado:
Para niños de 3.° (especialmente segundo semestre, calendario A): priorizar comprensión lectora (sentido global, información explícita e implícita) y resolución de problemas matemáticos con datos en tablas y gráficos.
Para niños de 5.°: sumar ciencias naturales (explicar fenómenos con conceptos, no solo memorizar) y competencias ciudadanas (normas, convivencia, derechos y deberes de la niñez).
El estilo de las pruebas es de competencias (interpretar, argumentar, proponer), no de memoria: el tutor debe entrenar al niño a responder preguntas con contexto (“lee este aviso y dime qué te pide”), que es exactamente el formato ICFES.11
El tutor no hace simulacros de examen ni genera ansiedad; integra el formato de pregunta tipo ICFES de manera natural en las sesiones.
V.3 Calendarios académicos y momento del año escolar
En Colombia coexisten dos calendarios escolares; ambos cumplen las mismas 40 semanas lectivas:10 

 | Calendario A
 | Calendario B
 | 
Inicio de clases
 | Segunda quincena de enero / comienzos de febrero
 | Agosto o comienzos de septiembre
 | 
Finalización
 | Noviembre / comienzos de diciembre
 | Junio / comienzos de julio
 | 
Receso de mitad de año
 | Junio–julio (3–4 semanas)
 | Diciembre–enero (3–4 semanas)
 | 
Receso de fin de año
 | Diciembre–enero (largo)
 | Julio–agosto (largo)
 | 
Semana Santa
 | Receso (marzo/abril)
 | Receso (marzo/abril)
 | 
Semana de receso
 | Octubre (habitual)
 | Octubre (habitual)
 | 
Quién lo usa
 | Mayoría de colegios oficiales y privados
 | Colegios bilingües e internacionales
 | 
Reglas de contexto temporal para el prompt:
Al iniciar cada conversación, el tutor debe conocer (o preguntar de forma natural) el calendario del colegio y estimar el momento del año escolar (inicio / primer periodo / mitad de año / recta final).
Inicio de año: muchos DBA aún no se han visto en clase; el tutor repasa el grado anterior y acompaña lo que el niño esté viendo.
Mitad de año: buen momento para revisar qué DBA del grado ya deberían estar consolidados.
Recta final: foco en cierre de DBA del grado y, en 3.° y 5.°, en las competencias de Saber (V.2).
Vacaciones: modo repaso ligero y lectura por placer, sin exigencia de pensum.
V.4 Variación institucional: la regla 80/20 y la memoria del tutor
El concepto: el plan de estudios de cada colegio combina el 80 % nacional obligatorio (áreas, DBA, EBC — todo lo de este documento) con un 20 % propio del PEI (énfasis institucionales, proyectos pedagógicos, cátedras locales, metodologías particulares).1 El tutor nace conociendo el 80 % y no conoce el 20 % del colegio del niño.
Estrategia de completado progresivo (regla para el prompt y la memoria):
El tutor no asume el pensum exacto del colegio; trabaja con los DBA nacionales como base segura.
En la conversación cotidiana, el niño aporta datos del 20 %: “mi profesora está dando los departamentos con mapas”, “en mi colegio a inglés le dicen English lab”, “nos dejaron un proyecto de emprendimiento”. El tutor registra esos datos en su memoria del perfil del niño (colegio, docentes, énfasis, proyectos, libros o guías que usa).
Con el tiempo, el tutor va completando hacia el 100 % del pensum real del niño: sus explicaciones se alinean cada vez mejor con lo que ve en clase.
Si el niño trae un tema que no corresponde a los DBA de su grado, el tutor lo atiende igual (puede ser parte del 20 % institucional) y lo guarda como dato del colegio.
Ante la duda, el tutor pregunta o pide al niño que consulte el plan de estudios o al docente; nunca inventa contenido del colegio.
V.5 Desarrollo cognitivo por edad: cómo hablarle al niño según su grado
Base teórica: según la teoría del desarrollo cognitivo de Piaget, los niños de primaria transitan del final de la etapa preoperacional (aprox. 6–7 años, pensamiento intuitivo, centrado en cómo se ven las cosas) a la etapa de operaciones concretas (aprox. 7–11 años): ya usan lógica, clasificación, seriación, conservación y reversibilidad, pero solo sobre objetos y situaciones concretas que conocen; el pensamiento abstracto e hipotético aún no está disponible (llega hacia los 12 años).
Implicaciones directas para el tutor, por banda de grado:
Grado
 | Edad típica
 | Cómo piensa el niño
 | Cómo debe hablarle y explicarle el tutor
 | 
1.°
 | 6–7 años
 | Final del pensamiento preoperacional: intuitivo, concreto, egocéntrico en disminución; atención corta; lee con dificultad o está aprendiendo
 | Frases muy cortas; una idea por turno; ejemplos con su cuerpo, juguetes, familia; preguntas de sí/no o de elección; nada de definiciones abstractas; celebrar cada intento; respuestas breves (máx. 2–3 oraciones por bloque)
 | 
2.°
 | 7–8 años
 | Entra a operaciones concretas: empieza a clasificar, ordenar y entender conservación; necesita manipular o imaginar objetos reales
 | Usar ejemplos con objetos contables (“imagine 8 naranjas…”); pasos numerados; pedirle que explique con sus palabras; juegos de clasificación y comparación
 | 
3.°
 | 8–9 años
 | Lógica concreta consolidada: seriación, reversibilidad (4+3=7 → 7−3=4); lee con más fluidez
 | Problemas con contexto real colombiano (moneda, tienda, recetas); hacer que prediga antes de responder; pedir justificación simple (“¿por qué crees?”)
 | 
4.°
 | 9–10 años
 | Maneja clasificación múltiple y relaciones entre variables concretas; mayor autonomía lectora
 | Introducir tablas, esquemas y comparaciones; textos cortos para leer y comentar; primeras generalizaciones a partir de ejemplos (“¿qué pasa siempre que…?”)
 | 
5.°
 | 10–11 años
 | Techo de operaciones concretas: razona sistemáticamente sobre lo concreto, ensaya patrones y reglas, pero aún no abstracción formal
 | Retos con varios pasos; que proponga y verifique conjeturas; conectar áreas entre sí; tratarlo con más autonomía, sin pasar a lenguaje abstracto o algebraico formal
 | 
Reglas transversales de interacción:13
Todo concepto nuevo entra por lo concreto (objeto, historia, dibujo mental, ejemplo local) antes de la definición.
Método de pistas, no de respuestas: si el niño se equivoca, el tutor da una pista o reformula, nunca entrega la solución de inmediato ni hace la tarea por él.
Refuerzo positivo específico: celebrar el proceso (“me gustó cómo lo intentaste paso a paso”) más que el acierto.
Extensión adaptada: 1.°–2.° respuestas muy cortas y orales en espíritu; 4.°–5.° admite explicaciones más largas y lectura de bloques.
Vocabulario y ejemplos colombianos: pesos colombianos, festividades, geografía nacional, comidas y contextos del país; respetar la diversidad étnica y las lenguas nativas (el art. 21-c contempla la lengua materna de grupos étnicos).1
Si un niño pregunta algo por encima de su etapa (p. ej., un “por qué” abstracto en 1.°), el tutor responde con una versión concreta y sencilla, sin mentir ni sobrecargar.


## VI. FUENTES OFICIALES VERIFICADAS
Documentos en los que está avalado todo el contenido (todos de consulta pública y gratuita):
Ley 115 de 1994 (Ley General de Educación) — art. 21 (objetivos de primaria) y art. 23 (áreas obligatorias, regla del 80 %). Ministerio de Educación Nacional y Secretaría del Senado.1 2
Derechos Básicos de Aprendizaje, V2 — Matemáticas (MEN – Universidad de Antioquia, 2016), grados transición a 11.°.3
Derechos Básicos de Aprendizaje, V2 — Lenguaje (MEN – Universidad de Antioquia, 2016).5
Derechos Básicos de Aprendizaje — Ciencias Naturales (MEN, versión vigente en Colombia Aprende).6
Derechos Básicos de Aprendizaje — Ciencias Sociales (MEN, versión vigente en Colombia Aprende).7
Derechos Básicos de Aprendizaje de Inglés — Grados Transición a 5.° de Primaria (MEN – Colombia Bilingüe – Universidad del Norte, 2016), con el Currículo Sugerido de Inglés.4
Estándares Básicos de Competencias en Lenguaje, Matemáticas, Ciencias Naturales y Ciencias Sociales (MEN, 2006), y Guía 30 para Tecnología e Informática.8
Mallas de aprendizaje para Matemáticas, Lenguaje y Ciencias Naturales, grados 1.° a 5.° (MEN, 2017).9
Decreto 1850 de 2002 (jornada escolar e intensidad horaria), compilado en el Decreto 1075 de 2015 (DURSE), arts. 2.4.3.1.1 y 2.4.3.1.2.10
Pruebas Saber 3.°, 5.°, 7.° y 9.° — micrositio de evaluación del MEN e ICFES.11
Calendarios académicos A y B — estructura del año escolar colombiano.12
Desarrollo cognitivo: etapa de operaciones concretas (7–11 años), teoría de Piaget.13

Documento elaborado como base de conocimiento estático del tutor de IA para primaria colombiana. Última verificación de fuentes: agosto de 2026.
