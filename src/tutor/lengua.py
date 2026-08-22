"""Lo que del español se puede verificar sin preguntarle a un modelo.

Es el gemelo de `evaluar_cuenta` en el generador del banco, y nace de la misma
regla dura: **la aritmética jamás la valida un modelo.** Cuando entró lectura y
escritura, esa regla se quedó sin brazo — un ejercicio de lenguaje no tiene
`operacion`, así que el validador del banco lo dejaba pasar mirándole solo el
largo y el voseo. Es decir: el modelo escribía el ejercicio y el modelo decía
que estaba bien.

«Mariposa tiene 4 sílabas» es tan verificable como «27 + 15 = 42». No hace falta
un modelo para contarlas, y por lo tanto no se le pide a uno. Lo que este módulo
NO intenta es lo que de verdad exige juicio —si un párrafo tiene una sola idea,
si un final cierra la historia—; ahí el ejercicio va sin verificación y se sabe
que va sin verificación, que no es lo mismo que creer que se verificó.

Módulo puro: no toca red, ni disco, ni base. Como `pedagogy` y `tools`.
"""

from __future__ import annotations

import unicodedata

# ─────────────────────────────────────────────────────────────────────────────
# El alfabeto
# ─────────────────────────────────────────────────────────────────────────────

FUERTES = "aeoáéó"
"""Vocales abiertas. Dos seguidas NO caben en una sílaba: le-er, ca-os."""

DEBILES = "iuü"
"""Vocales cerradas sin tilde. Se pegan a la de al lado: vie-jo, cau-sa."""

DEBILES_TILDADAS = "íú"
"""La tilde en una débil ROMPE el diptongo: dí-a, ba-úl. Por eso está aparte."""

VOCALES = FUERTES + DEBILES + DEBILES_TILDADAS

DIGRAFOS = ("ch", "ll", "rr")
"""Dos letras, un sonido. Nunca se parten: ca-lle, no cal-le."""

INSEPARABLES = frozenset(
    {"bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "kl", "kr", "pl", "pr", "tl", "tr"}
)
"""Grupos que arrancan sílaba juntos: ha-blar, o-tro, si-glo.

`tl` está adentro porque en América «atlas» se silabea a-tlas. En España es
at-las; para un tutor colombiano manda la de acá."""


def _sin_tilde(texto: str) -> str:
    """Quita tildes pero deja la eñe y la diéresis en pie."""
    salida = []
    for c in unicodedata.normalize("NFD", texto):
        if unicodedata.combining(c):
            continue
        salida.append(c)
    return unicodedata.normalize("NFC", "".join(salida))


def normalizar(palabra: str) -> str:
    """Deja la palabra como la trabaja este módulo: minúscula y sin basura.

    Las tildes SE CONSERVAN — son información: separan «dia» de «día» y son la
    mitad del trabajo de acentuación.
    """
    limpia = palabra.strip().lower()
    return "".join(c for c in limpia if c in VOCALES or c.isalpha())


def es_vocal(c: str) -> bool:
    return c.lower() in VOCALES


# ─────────────────────────────────────────────────────────────────────────────
# Silabeo
# ─────────────────────────────────────────────────────────────────────────────


def _mismo_nucleo(a: str, b: str) -> bool:
    """¿Estas dos vocales seguidas van en la misma sílaba?"""
    # Una débil con tilde siempre abre hiato: pa-ís, rí-o, ba-úl.
    if a in DEBILES_TILDADAS or b in DEBILES_TILDADAS:
        return False
    # Dos abiertas nunca caben juntas: te-a-tro, le-ón, ca-er.
    if a in FUERTES and b in FUERTES:
        return False
    # Lo demás es diptongo: fuerte+débil, débil+fuerte, débil+débil.
    return True


def _nucleos(palabra: str) -> list[tuple[int, int]]:
    """Los grupos de vocales que suenan como una sola sílaba, como (inicio, fin)."""
    grupos: list[tuple[int, int]] = []
    i = 0
    while i < len(palabra):
        if not es_vocal(palabra[i]):
            i += 1
            continue
        inicio = i
        i += 1
        while (
            i < len(palabra)
            and es_vocal(palabra[i])
            and _mismo_nucleo(palabra[i - 1], palabra[i])
        ):
            i += 1
        grupos.append((inicio, i))
    return grupos


def _unidades(consonantes: str) -> list[str]:
    """Parte las consonantes en unidades, sin romper un dígrafo por la mitad."""
    fuera: list[str] = []
    i = 0
    while i < len(consonantes):
        par = consonantes[i : i + 2]
        if par in DIGRAFOS:
            fuera.append(par)
            i += 2
        else:
            fuera.append(consonantes[i])
            i += 1
    return fuera


def _corte(consonantes: str) -> int:
    """Cuántas consonantes se quedan con la sílaba de la IZQUIERDA."""
    us = _unidades(consonantes)
    if len(us) <= 1:
        # Ninguna, o una sola que se va con la vocal que sigue: ca-sa, ca-lle.
        return 0
    if len(us) == 2:
        # Juntas si forman grupo: o-tro, ha-blar. Separadas si no: car-ta.
        return 0 if "".join(us) in INSEPARABLES else len(us[0])
    if len(us) == 3:
        # Con tres, las dos últimas deciden: ham-bre (br pega), trans-por-te.
        return len(us[0]) if "".join(us[1:]) in INSEPARABLES else len(us[0]) + len(us[1])
    # Cuatro o más: dos y dos. «obstruir» -> obs-truir.
    return len(us[0]) + len(us[1])


def silabas(palabra: str) -> list[str]:
    """Parte la palabra en sílabas.

    >>> silabas("mariposa")
    ['ma', 'ri', 'po', 'sa']
    >>> silabas("calle")
    ['ca', 'lle']
    >>> silabas("día")
    ['dí', 'a']
    """
    p = normalizar(palabra)
    if not p:
        return []
    grupos = _nucleos(p)
    if not grupos:
        return [p]  # ni una vocal: no es una palabra, se devuelve entera

    cortes = [0]
    for (_, fin_a), (inicio_b, _) in zip(grupos, grupos[1:], strict=False):
        cortes.append(fin_a + _corte(p[fin_a:inicio_b]))
    cortes.append(len(p))
    return [p[a:b] for a, b in zip(cortes, cortes[1:], strict=False) if p[a:b]]


def contar_silabas(palabra: str) -> int:
    return len(silabas(palabra))


# ─────────────────────────────────────────────────────────────────────────────
# Sonidos: con qué empieza, con qué termina, y si dos palabras riman
# ─────────────────────────────────────────────────────────────────────────────


def sonido_inicial(palabra: str) -> str:
    """La letra —o el dígrafo— con que arranca. 'chocolate' empieza con 'ch'."""
    p = normalizar(palabra)
    if not p:
        return ""
    # «qu» va junto igual que los dígrafos: «queso» empieza con /k/, y la q
    # sola no suena a nada en español.
    return p[:2] if p[:2] in DIGRAFOS or p[:2] == "qu" else p[:1]


def sonido_final(palabra: str) -> str:
    p = normalizar(palabra)
    return _sin_tilde(p[-1:]) if p else ""


def a_sonido(texto: str) -> str:
    """Cómo SUENA lo escrito, para un niño colombiano.

    La ortografía del español distingue letras que el oído no distingue, y este
    tutor entra por el oído: el niño ESCUCHA el ejercicio y CONTESTA hablando.

    Lo trajo una tanda de verdad: el modelo escribió «¿nube rima con tuve?» y el
    verificador lo tumbó porque «ube» no es «uve». Al oído riman, y el modelo
    tenía razón — b y v son el mismo sonido en español desde hace siglos. Es la
    quinta vez que un tope de este proyecto descarta contenido correcto por no
    saber leerlo.

    Se aplica el habla de acá: seseo (casa/caza suenan igual) y yeísmo
    (llave/yave). Un tutor colombiano no distingue esas parejas, y por lo tanto
    tampoco su verificador.
    """
    s = _sin_tilde(normalizar(texto))
    s = s.replace("qu", "k").replace("gue", "ge").replace("gui", "gi")
    s = s.replace("ch", "C")  # se protege el dígrafo antes de tocar la c
    s = s.replace("ll", "y")  # yeísmo
    s = s.replace("ce", "se").replace("ci", "si").replace("z", "s")  # seseo
    s = s.replace("c", "k").replace("C", "ch")
    s = s.replace("v", "b")  # b y v son el mismo sonido
    s = s.replace("ge", "je").replace("gi", "ji")
    s = s.replace("h", "")  # muda
    return s


def riman(a: str, b: str) -> bool:
    """¿Riman? Desde la vocal tónica hasta el final, sin contar la tilde.

    Rima consonante, que es la que un niño de primaria oye y la que el
    currículum pide: gato/pato sí, gato/carro no.

    Una palabra NO rima consigo misma. Repetirla es lo primero que se le ocurre
    a un niño —y a un modelo generando ejercicios—, y no enseña nada.
    """
    pa, pb = normalizar(a), normalizar(b)
    if not pa or not pb or _sin_tilde(pa) == _sin_tilde(pb):
        return False

    def _cola(p: str) -> str:
        ss = silabas(p)
        if not ss:
            return ""
        desde = _indice_tonica(ss)
        # La rima se oye desde la VOCAL TÓNICA, no desde la consonante que la
        # precede ni desde la primera vocal de la sílaba. «casa» y «pasa» riman
        # en «asa»; y «canción» rima con «corazón» en «ón» —no en «ión»—
        # porque la «i» de «ción» es átona: va pegada a la ó, no suena sola.
        #
        # La vocal tónica se busca DENTRO de la sílaba fuerte, no en toda la
        # cola. Buscarla en la cola entera hacía que «libro» y «grito» rimaran:
        # en las dos, la primera vocal abierta era la «o» del final, así que las
        # dos rimaban en «o». Lo cazó una tanda de verdad, no la suite — el
        # modelo dijo que no rimaban y tenía razón.
        tonica = ss[desde]
        cola = tonica[_vocal_tonica(tonica) :] + "".join(ss[desde + 1 :])
        # Se compara el SONIDO, no la letra: «nube» y «tuve» riman.
        return a_sonido(cola)

    return _cola(pa) == _cola(pb)


# ─────────────────────────────────────────────────────────────────────────────
# Acentuación
# ─────────────────────────────────────────────────────────────────────────────


def _vocal_tonica(trozo: str) -> int:
    """Dónde arranca el sonido tónico dentro de la sílaba fuerte.

    Es la vocal con tilde; si no hay, la abierta del diptongo; si son las dos
    cerradas, la segunda. En «ción» es la «ó», no la «i»."""
    vocales = [i for i, c in enumerate(trozo) if es_vocal(c)]
    if not vocales:
        return 0
    for i in vocales:
        if trozo[i] in "áéíóú":
            return i
    for i in vocales:
        if trozo[i] in FUERTES:
            return i
    # Núcleo de dos cerradas («ciu-dad»): manda la segunda.
    nucleo = [i for i in vocales if i == vocales[0] or i - 1 in vocales]
    return nucleo[-1] if nucleo else vocales[0]


def _indice_tonica(ss: list[str]) -> int:
    """Cuál de las sílabas es la fuerte."""
    for i, s in enumerate(ss):
        if any(c in "áéíóú" for c in s):
            return i  # con tilde escrita no hay nada que adivinar
    if len(ss) == 1:
        return 0
    # Sin tilde: grave si termina en vocal, n o s; aguda si no.
    ultima = _sin_tilde(ss[-1])
    final = ultima[-1] if ultima else ""
    return len(ss) - 2 if (final in "aeiou" or final in "ns") else len(ss) - 1


def silaba_tonica(palabra: str) -> str:
    ss = silabas(palabra)
    return ss[_indice_tonica(ss)] if ss else ""


def clasificar(palabra: str) -> str:
    """aguda, grave, esdrujula o sobresdrujula."""
    ss = silabas(palabra)
    if not ss:
        return ""
    desde_el_final = len(ss) - _indice_tonica(ss)
    return {1: "aguda", 2: "grave", 3: "esdrujula"}.get(desde_el_final, "sobresdrujula")


def lleva_tilde(palabra: str) -> bool:
    """¿La palabra ESTÁ escrita con tilde?"""
    return any(c in "áéíóú" for c in normalizar(palabra))


def tilde_bien_puesta(palabra: str) -> bool | None:
    """¿La tilde de esta palabra respeta la regla general?

    Devuelve `None` cuando NO SE PUEDE SABER, y ese es el punto del diseño.

    Sin tilde escrita no hay de dónde sacar dónde suena fuerte la palabra:
    «cancion» se lee «CAN-cion» o «can-CION» según quien la diga, y solo un
    diccionario —o alguien que la conozca— lo resuelve. La primera versión de
    esta función igual contestaba: inferia la tónica con la regla general y
    después comprobaba la regla general contra sí misma. Siempre decía que sí.
    Un verificador circular es peor que ninguno, porque parece uno.

    Con tilde escrita sí se sabe, y ahí contesta: «cása» es False, «canción» es
    True. Eso alcanza para lo que hace falta —el ejercicio de tilde pregunta
    cómo SE ESCRIBE una palabra, y la respuesta correcta lleva la tilde puesta.

    Solo la regla general. Los monosílabos diacríticos (tú/tu, él/el) y los
    hiatos (día, país) quedan fuera a propósito: rompen la regla por diseño, y
    un verificador que los juzgue mal rechaza contenido correcto — el modo de
    fallar más caro que tiene este proyecto.
    """
    p = normalizar(palabra)
    if not p:
        return None
    if not lleva_tilde(p):
        return None  # no lo sabemos, y decirlo es la respuesta

    ss = silabas(p)
    if len(ss) == 1:
        # Monosílabo con tilde: o es diacrítico (sí, él, tú) o está mal. Los
        # diacríticos dependen del significado, así que no se juzga.
        return None

    # Hiato con la débil tónica: lleva tilde siempre, sin mirar la regla
    # general. día, país, baúl, reúne.
    for i, c in enumerate(p):
        if c in DEBILES_TILDADAS and (
            (i > 0 and p[i - 1] in FUERTES) or (i + 1 < len(p) and p[i + 1] in FUERTES)
        ):
            return True

    ultima = _sin_tilde(ss[-1])
    final = ultima[-1] if ultima else ""
    termina_en_vocal_n_s = final in "aeiou" or final in "ns"

    clase = clasificar(p)
    if clase == "aguda":
        return termina_en_vocal_n_s
    if clase == "grave":
        return not termina_en_vocal_n_s
    return True  # esdrújulas y sobresdrújulas, todas


def le_falta_tilde(sin_tilde: str, con_tilde: str) -> bool:
    """¿`con_tilde` es `sin_tilde` bien acentuada?

    Esta es la pregunta que el banco necesita de verdad: el ejercicio dice
    «esta palabra está sin tilde: cancion. ¿Cómo se escribe?» y la respuesta es
    «canción». Se comprueba que sean la misma palabra y que la respuesta esté
    bien acentuada — lo cual sí se puede juzgar, porque la respuesta trae la
    tilde puesta y con ella la tónica.
    """
    a, b = normalizar(sin_tilde), normalizar(con_tilde)
    if not a or not b or _sin_tilde(a) != _sin_tilde(b):
        return False
    return tilde_bien_puesta(b) is True


# ─────────────────────────────────────────────────────────────────────────────
# Tipo de sílaba — el andamio de la decodificación en 1°
# ─────────────────────────────────────────────────────────────────────────────


def tipo_de_silaba(silaba: str) -> str:
    """directa (ma), inversa (al), trabada (bra), mixta (pan) o sola (a)."""
    s = normalizar(silaba)
    if not s:
        return ""
    inicio = ""
    i = 0
    while i < len(s) and not es_vocal(s[i]):
        par = s[i : i + 2]
        inicio += par if par in DIGRAFOS else s[i]
        i += 2 if par in DIGRAFOS else 1
    nucleo_fin = i
    while nucleo_fin < len(s) and es_vocal(s[nucleo_fin]):
        nucleo_fin += 1
    cierre = s[nucleo_fin:]

    unidades_inicio = _unidades(inicio)
    if len(unidades_inicio) >= 2:
        return "trabada"
    if not inicio:
        return "inversa" if cierre else "sola"
    return "mixta" if cierre else "directa"


# ─────────────────────────────────────────────────────────────────────────────
# El puente con el banco de ejercicios
# ─────────────────────────────────────────────────────────────────────────────

def sonidos(palabra: str) -> list[str]:
    """Los sonidos de la palabra, uno por uno: sol es /s/ /o/ /l/.

    Los dígrafos cuentan UNO: «chocolate» empieza con /ch/, no con /c/ y /h/.
    Es lo que pide `lec.fonologia.segmentar_fonemas`, y sin esta función el
    nodo entero se quedaba sin banco — el modelo escribía los ejercicios bien y
    usaba `separar()` (que es sílabas) porque no había otra cosa que usar."""
    p = _sin_tilde(normalizar(palabra))
    fuera: list[str] = []
    i = 0
    while i < len(p):
        par = p[i : i + 2]
        if par in DIGRAFOS or par == "qu":
            fuera.append(par)
            i += 2
        else:
            fuera.append(p[i])
            i += 1
    return fuera


def arranque(palabra: str) -> str:
    """Con qué consonantes arranca la palabra: «plato» es p-l, «fruta» f-r.

    Es lo que pide `lec.decodificacion.silabas_trabadas` — el niño tiene que
    oír las DOS consonantes pegadas. Faltaba, y el modelo escribía el ejercicio
    bien pero lo declaraba con `sonidos()`, que devuelve la palabra entera."""
    p = _sin_tilde(normalizar(palabra))
    fuera: list[str] = []
    i = 0
    while i < len(p) and not es_vocal(p[i]):
        par = p[i : i + 2]
        if par in DIGRAFOS or par == "qu":
            fuera.append(par)
            i += 2
        else:
            fuera.append(p[i])
            i += 1
    return "-".join(fuera)


_COMPROBACIONES = {
    "sonidos": lambda p: "-".join(sonidos(p)),
    "arranque": arranque,
    "fonemas": lambda p: str(len(sonidos(p))),
    "silabas": lambda p: str(contar_silabas(p)),
    "separar": lambda p: "-".join(silabas(p)),
    "inicial": sonido_inicial,
    "final": sonido_final,
    "tonica": silaba_tonica,
    "clase": clasificar,
    "tipo": tipo_de_silaba,
    "letras": lambda p: str(len(normalizar(p))),
}
"""Las de una palabra: `silabas(mariposa)` tiene que dar `4`."""

_COMPARACIONES = {
    "rima": riman,
    "tilde": le_falta_tilde,
}
"""Las de dos: `rima(gato,pato)` da sí o no; `tilde(cancion,canción)`, lo mismo."""

_POR_SONIDO = frozenset({"inicial", "final", "sonidos", "arranque"})
"""Las que se contestan con lo que se OYE, no con lo que se escribe."""

SI = {"si", "sí", "s", "true", "verdadero"}
NO = {"no", "n", "false", "falso"}


def _comparable(texto: str) -> str:
    """Deja letras y NÚMEROS, y tira los separadores.

    Se ignora con qué separó el modelo: «/s/ /o/ /l/», «s-o-l» y «s, o, l»
    dicen lo mismo, y lo que se verifica es qué sonidos dijo y en qué orden.

    Los dígitos se conservan, y ese detalle es todo. La primera versión filtraba
    con `isalpha()`, así que «4» y «99» se comparaban los dos como cadena vacía
    y **cualquier respuesta numérica pasaba**: `silabas(mariposa) = 99` entraba
    al banco. Aflojar la comparación para un caso rompió todos los demás sin que
    un solo test se pusiera rojo — el descarte silencioso otra vez, ahora del
    lado del que aprueba.
    """
    return "".join(c for c in _sin_tilde(texto.lower()) if c.isalnum())


def _igual(a: str, b: str) -> bool:
    return _comparable(a) == _comparable(b)


def verificar(expresion: str, respuesta: str) -> str | None:
    """Comprueba un ejercicio de lenguaje. Devuelve el motivo del rechazo, o None.

    Es el `evaluar_cuenta` de lectura y escritura. El generador declara qué se
    comprueba y sobre qué palabra —`silabas(mariposa)`, `rima(gato,pato)`— y acá
    se ejecuta de verdad y se compara con la respuesta que el modelo escribió.
    Si no cierra, el ejercicio no entra al banco.

    Una expresión que no se entiende es un RECHAZO, no un permiso. Es la falla
    del descarte silencioso: si «no supe leerla» dejara pasar el ejercicio, la
    forma más fácil de saltarse el validador sería escribir cualquier cosa.
    """
    exp = expresion.strip()
    if "(" not in exp or not exp.endswith(")"):
        return f"verificación ilegible: '{exp}' (se espera algo como 'silabas(mariposa)')"

    abre = exp.index("(")
    nombre, dentro = exp[:abre].strip().lower(), exp[abre + 1 : -1]
    args = [a.strip() for a in dentro.split(",") if a.strip()]

    if nombre in _COMPROBACIONES:
        if len(args) != 1:
            return f"'{nombre}' se aplica a UNA palabra, y llegaron {len(args)}"
        real = _COMPROBACIONES[nombre](args[0])
        # Estas preguntan por el SONIDO, no por la letra: a «¿con qué sonido
        # empieza casa?» se contesta /k/ y está bien, aunque se escriba con c;
        # y los sonidos de «pez» son /p/ /e/ /s/, porque acá la z sesea. Los
        # nodos se llaman «sonido inicial y final» y «separar en sus sonidos».
        if nombre in _POR_SONIDO and a_sonido(real) == a_sonido(respuesta):
            return None
        if not _igual(real, respuesta):
            return f"NO CIERRA: {exp} = '{real}', pero el ejercicio dice '{respuesta}'"
        return None

    if nombre in _COMPARACIONES:
        if len(args) != 2:
            return f"'{nombre}' compara DOS palabras, y llegaron {len(args)}"
        real = _COMPARACIONES[nombre](args[0], args[1])
        dicho = respuesta.strip().lower()
        # A «tilde» se le puede contestar con la palabra bien escrita en vez de
        # «sí» — que es lo que un niño diría, y lo que el ejercicio pide.
        if nombre == "tilde" and dicho not in SI | NO:
            if _igual(dicho, args[1]):
                return None
            return f"NO CIERRA: la respuesta debía ser '{args[1]}'"
        if dicho in SI:
            esperado = True
        elif dicho in NO:
            esperado = False
        else:
            return f"'{nombre}' se contesta sí o no, y el ejercicio dice '{respuesta}'"
        if real != esperado:
            fue = 'sí' if real else 'no'
            return f"NO CIERRA: {exp} es {fue}, pero el ejercicio dice '{respuesta}'"
        return None

    conocidas = ", ".join(sorted(_COMPROBACIONES | _COMPARACIONES))
    return f"no sé comprobar '{nombre}'. Las que conozco: {conocidas}"
