"""Los 4 tools del tutor en vivo.

Módulo PURO — sin red, sin I/O. Todo se resuelve en memoria.
REGLA: ningún tool puede hacer una llamada de red. Ver ARCHITECTURE.md §9.

Los tools devuelven DECISIONES, no efectos. Pedir la cámara o escalar una alerta
son intenciones que ejecuta session.py; acá solo se decide.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, Field

from .lengua import COMPROBACIONES as COMPROBACIONES_LENGUA
from .lengua import NOMBRE_DE_LETRA
from .lengua import nombre_a_letra as _a_letra
from .models import Ejercicio, Habilidad

# ─────────────────────────────────────────────────────────────────────────────
# check_answer — la verificación determinística
# ─────────────────────────────────────────────────────────────────────────────
# LA REGLA MÁS IMPORTANTE DEL PRODUCTO: la aritmética jamás la valida un modelo.
# Un "¡correcto!" a 7+5=13 destruye la confianza del papá para siempre.
#
# Principio: TOLERANTE CON LA FORMA, ESTRICTO CON EL VALOR.
# El niño habla, no escribe. "cuarenta y dos", "es 42", "42 manzanas" y "42" son
# la misma respuesta. Pero 41 nunca es 42.


class Veredicto(StrEnum):
    CORRECTO = "correcto"
    INCORRECTO = "incorrecto"

    REQUIERE_JUICIO = "requiere_juicio"
    """El código no puede decidir: comprensión lectora, redacción, explicar un
    razonamiento. Devolver INCORRECTO acá sería mentir — no es que esté mal, es
    que esta pregunta no se contesta con una comparación."""

    NO_SE_ENTENDIO = "no_se_entendio"
    """Llegó algo que no se puede leer como respuesta. NO es un error del niño.

    La transcripción es lo único que tenemos de su voz, y a veces la pierde. Al
    descomponer 729 un niño dijo "siete de cien, dos de diez, nueve de uno" y
    llegó `7102191`: el reconocedor pasó cada palabra a dígito y los pegó. La
    respuesta era CORRECTA. El tutor le dijo que se había equivocado.

    Hasta el 18/08 esto devolvía INCORRECTO, que es la misma falla de la fase 6
    mirando al niño en vez de al papá: tratar la ausencia de evidencia como
    evidencia. No pudimos leerlo no significa que esté mal.

    De todos los errores que este sistema puede cometer, decirle "te
    equivocaste" a un niño que acertó es el que más daño hace: castiga
    exactamente la conducta que queremos. Ante la duda se vuelve a preguntar."""


class ResultadoVerificacion(BaseModel):
    veredicto: Veredicto
    valor_interpretado: str | None = Field(
        default=None, description="Qué se entendió que dijo el niño. Para auditar y depurar."
    )


# Muletillas y unidades que el niño dice alrededor de la respuesta.
_RELLENO = {
    "es", "son", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "da", "queda", "quedan", "resultado", "resultados", "total", "igual", "iguales",
    "creo", "que", "seria", "sera", "me", "a", "de", "y",
    "manzanas", "figuritas", "puntos", "pesos", "unidades", "decenas", "centenas",
    "anos", "veces", "partes", "grupos",
}

_UNIDADES = {
    "cero": 0, "uno": 1, "una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiuno": 21, "veintiuna": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
}

_DECENAS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90,
}

_CENTENAS = {
    "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300,
    "cuatrocientos": 400, "quinientos": 500, "seiscientos": 600,
    "setecientos": 700, "ochocientos": 800, "novecientos": 900,
}


def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def palabras_a_numero(texto: str) -> int | None:
    """Convierte números dichos en palabras a entero. Rango 0–1000.

    Es el rango de primaria; más allá no hace falta. Un niño de 7 años dice
    "cuarenta y dos", no "42" — si no se traduce, todas sus respuestas
    habladas figuran como incorrectas.
    """
    palabras = [p for p in _sin_acentos(texto.lower()).split() if p and p != "y"]
    if not palabras:
        return None

    total = 0
    reconocio_algo = False

    for palabra in palabras:
        if palabra == "mil":
            total = (total or 1) * 1000
            reconocio_algo = True
        elif palabra in _CENTENAS:
            total += _CENTENAS[palabra]
            reconocio_algo = True
        elif palabra in _DECENAS:
            total += _DECENAS[palabra]
            reconocio_algo = True
        elif palabra in _UNIDADES:
            total += _UNIDADES[palabra]
            reconocio_algo = True
        else:
            return None  # una palabra desconocida invalida toda la lectura

    return total if reconocio_algo else None


def _a_numero(texto: str) -> float | None:
    """Extrae el valor numérico de lo que dijo el niño, en dígitos o en palabras."""
    limpio = _sin_acentos(texto.lower().strip())
    limpio = limpio.replace("$", " ").replace("%", " ")

    # Dígitos: "42", "4,5" (coma decimal, como se usa en Colombia), "-3"
    if hallazgos := re.findall(r"-?\d+(?:[.,]\d+)?", limpio):
        if len(hallazgos) == 1:
            return float(hallazgos[0].replace(",", "."))
        return None  # varios números: ambiguo, no adivinar

    palabras_utiles = [p for p in re.split(r"[^\w]+", limpio) if p and p not in _RELLENO]
    numero = palabras_a_numero(" ".join(palabras_utiles))
    return float(numero) if numero is not None else None


def _normalizar_texto(texto: str) -> str:
    """Para respuestas que no son números: saca acentos, relleno y puntuación."""
    limpio = _sin_acentos(texto.lower())
    palabras = [p for p in re.split(r"[^\w]+", limpio) if p and p not in _RELLENO]
    return " ".join(palabras)



"""Los nombres de las letras viven en `lengua`, con el resto del español.

Estuvieron acá un rato, y en ese rato `check_answer` entendía «eme» y
`verify_language` no: la misma respuesta del mismo niño valía o no según por
dónde entrara. Dos verificadores con reglas distintas son peor que uno."""


# Cuántos dígitos de más hacen sospechar de la transcripción y no del niño.
# Tres: "729" contra "7102191" son cuatro de más. Un niño que se equivoca de
# orden suele irse uno o dos ("7290"), y eso SÍ se corrige.
DIGITOS_ABSURDOS = 3


def _huele_a_transcripcion_rota(dicho: float, esperado: float) -> bool:
    """¿El número que llegó es absurdo para la pregunta que se hizo?

    Al descomponer 729 un niño dijo "siete de cien, dos de diez, nueve de uno" y
    llegó `7102191`: el reconocedor pasó cada palabra a dígito y las pegó. Es un
    número perfectamente válido, así que `_a_numero` lo acepta — y el niño, que
    había acertado, recibió un "te equivocaste".

    Esto es una HEURÍSTICA y no puede pretender otra cosa. Se sostiene porque el
    costo de equivocarse es asimétrico: confundir un error con una duda cuesta
    una repregunta; confundir un acierto con un error le enseña al niño que
    responder bien no sirve. Ante la duda, se pregunta de nuevo.
    """
    if dicho <= 0 or esperado <= 0:
        return False
    return len(str(int(dicho))) - len(str(int(esperado))) >= DIGITOS_ABSURDOS


def check_answer(
    ejercicio: Ejercicio, respuesta_nino: str, habilidad: Habilidad | None = None
) -> ResultadoVerificacion:
    """Verifica la respuesta del niño. ~5ms, sin red, sin modelo.

    Si la habilidad no es verificable en código (comprensión, redacción), lo dice
    explícitamente en vez de inventar un veredicto.
    """
    if habilidad is not None and not habilidad.verificable_en_codigo:
        return ResultadoVerificacion(veredicto=Veredicto.REQUIERE_JUICIO)

    esperado_num = _a_numero(ejercicio.respuesta)

    if esperado_num is not None:
        dicho_num = _a_numero(respuesta_nino)
        if dicho_num is None:
            # No se pudo leer. Puede ser transcripción rota, puede ser un "no
            # sé", puede ser que estuviera explicando. Ninguna de las tres es
            # una respuesta equivocada.
            return ResultadoVerificacion(veredicto=Veredicto.NO_SE_ENTENDIO)
        if _huele_a_transcripcion_rota(dicho_num, esperado_num):
            return ResultadoVerificacion(veredicto=Veredicto.NO_SE_ENTENDIO)

        # Tolerancia mínima por el ida y vuelta de float, no por "casi acertó".
        correcto = abs(dicho_num - esperado_num) < 1e-9
        return ResultadoVerificacion(
            veredicto=Veredicto.CORRECTO if correcto else Veredicto.INCORRECTO,
            valor_interpretado=f"{dicho_num:g}",
        )

    dicho = _normalizar_texto(respuesta_nino)
    esperado = _normalizar_texto(ejercicio.respuesta)
    if not dicho:
        return ResultadoVerificacion(veredicto=Veredicto.NO_SE_ENTENDIO)

    # Cuando lo que se espera es una letra, el niño la NOMBRA: dice «eme», no
    # «m». Se traduce lo que dijo antes de comparar — igual que con los números.
    if esperado in NOMBRE_DE_LETRA.values() and (letra := _a_letra(dicho)):
        return ResultadoVerificacion(
            veredicto=Veredicto.CORRECTO if letra == esperado else Veredicto.INCORRECTO,
            valor_interpretado=letra,
        )

    return ResultadoVerificacion(
        veredicto=Veredicto.CORRECTO if dicho == esperado else Veredicto.INCORRECTO,
        valor_interpretado=dicho,
    )


# ─────────────────────────────────────────────────────────────────────────────
# verify_arithmetic — para lo que el tutor improvisa
# ─────────────────────────────────────────────────────────────────────────────
# `check_answer` solo sabe de ejercicios del banco: valida contra un `ejercicio_id`.
# Cuando el tutor se sale del banco —y se sale, porque el niño pide otra cosa— no
# tiene con qué verificar, y el modelo termina juzgando la aritmética él mismo.
#
# Pasó en `ses_91c13b1747a2`, y la correlación fue perfecta: los tres ejercicios
# del banco, bien evaluados; los tres inventados, mal. Al niño que dijo "780" para
# 135+241 le contestó "estás muy cerca" (la respuesta es 376), y a un "cuarenta y
# ocho" para 7−3 le dijo "¡Eso!".
#
# La respuesta no es prohibirle improvisar: es que también lo improvisado pase por
# código. La regla dura se sostiene — la aritmética JAMÁS la valida un modelo.


class Distancia(StrEnum):
    """Qué tan lejos quedó, calculado en CÓDIGO.

    Existe para que "estás cerca" deje de ser una impresión del modelo. Es la
    frase que más se dijo cuando no tenía con qué medir, y era falsa: 780 no
    está cerca de 376.
    """

    EXACTO = "exacto"
    CERCA = "cerca"
    """Se equivocó en poco: el error es menor al 10% del resultado."""
    LEJOS = "lejos"


class ResultadoAritmetica(BaseModel):
    veredicto: Veredicto
    valor_interpretado: str | None = None
    distancia: Distancia | None = Field(
        default=None, description="Solo si se pudo verificar. Para graduar la pista."
    )


# Dos números y un operador. Deliberadamente angosto: nada de `eval`, que con un
# modelo del otro lado es una puerta abierta. Lo que no entra acá se declara no
# verificable, y el tutor no puede afirmar nada — que es el comportamiento seguro.
_OPERACION = re.compile(r"^\s*(-?\d+)\s*([+\-*x×/÷])\s*(-?\d+)\s*=?\s*$", re.IGNORECASE)

_OPERADORES = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "x": lambda a, b: a * b,
    "×": lambda a, b: a * b,
}


def resolver_operacion(operacion: str) -> float | None:
    """El resultado de una operación de dos términos. None si no se puede.

    NO se expone al tutor: el resultado nunca sale de acá. Si el modelo lo
    tuviera, la tentación de decirlo en voz alta es exactamente el fracaso que
    el producto promete no tener.
    """
    m = _OPERACION.match(operacion.replace(",", ""))
    if m is None:
        return None
    izq, op, der = int(m.group(1)), m.group(2).lower(), int(m.group(3))

    if op in ("/", "÷"):
        if der == 0 or izq % der != 0:
            return None  # en primaria, división no exacta no se verifica sola
        return izq / der
    return float(_OPERADORES[op](izq, der))


def verify_arithmetic(operacion: str, respuesta_nino: str) -> ResultadoAritmetica:
    """Verifica una cuenta que el tutor improvisó. ~1ms, sin red, sin modelo.

    Devuelve si acertó y qué tan lejos quedó — NUNCA el resultado correcto.
    """
    esperado = resolver_operacion(operacion)
    if esperado is None:
        return ResultadoAritmetica(veredicto=Veredicto.REQUIERE_JUICIO)

    dicho = _a_numero(respuesta_nino)
    if dicho is None:
        # Igual que en check_answer: no haberlo entendido no lo vuelve un error.
        return ResultadoAritmetica(veredicto=Veredicto.NO_SE_ENTENDIO)

    error = abs(dicho - esperado)
    if error < 1e-9:
        distancia = Distancia.EXACTO
    elif error <= max(abs(esperado) * 0.1, 1):
        distancia = Distancia.CERCA
    else:
        distancia = Distancia.LEJOS

    return ResultadoAritmetica(
        veredicto=Veredicto.CORRECTO if distancia is Distancia.EXACTO else Veredicto.INCORRECTO,
        valor_interpretado=f"{dicho:g}",
        distancia=distancia,
    )


# ─────────────────────────────────────────────────────────────────────────────
# get_next_problem — del banco precargado, en memoria
# ─────────────────────────────────────────────────────────────────────────────


class BancoDeSesion:
    """Ejercicios cargados en memoria al ABRIR la sesión.

    Durante la sesión no se consulta la base: se saca de esta lista. ~0ms.
    Ver ARCHITECTURE.md §9 — todo el trabajo pesado va antes de que el niño hable.

    Guarda MÁS DE UNA habilidad, y esa es la razón de ser de esta clase.

    Un niño cambia de tema a mitad de sesión — "mejor hagamos restas de un solo
    dígito" — y hasta el 18/08 el banco traía solo la habilidad del día. El
    tutor no tenía qué entregarle, así que improvisaba. Improvisando inventa
    ejercicios que nadie validó, llama a `check_answer` con ids que no existen
    (404 en ses_88be006b825f) y, sobre todo, nada queda atado a un nodo del
    grafo: `habilidades_trabajadas` sale vacío, el Analista no puede escribir
    dominio, y el tutor no aprende nada del niño. Se rompe justo la promesa
    central del producto por no tener a mano un ejercicio de resta que SÍ
    estaba en la base.

    Que el niño elija tema no significa que el modelo invente el ejercicio: el
    tema lo elige el niño, el ejercicio sale del banco validado en código.
    """

    def __init__(
        self, ejercicios: list[Ejercicio], principal: str | None = None
    ) -> None:
        self._por_habilidad: dict[str, list[Ejercicio]] = {}
        for ejercicio in ejercicios:
            self._por_habilidad.setdefault(ejercicio.habilidad_id, []).append(ejercicio)

        # La habilidad del día: la que decidió el planificador. Es de donde se
        # sirve cuando el tutor no pide nada en particular.
        self._principal = principal or (ejercicios[0].habilidad_id if ejercicios else None)
        self._entregados: list[Ejercicio] = []

    def get_next_problem(self, habilidad_id: str | None = None) -> Ejercicio | None:
        """Saca el siguiente. Nunca repite mientras queden sin usar.

        Sin argumento sirve la habilidad del día, y si esa se agotó cae en
        cualquier otra que quede — antes que dejar al tutor sin nada, porque
        sin ejercicio improvisa.

        Con `habilidad_id` sirve ESE tema y solo ese: si no hay, devuelve None
        en vez de entregar otra cosa. El tutor tiene que poder decir "de eso hoy
        no tengo, ¿probamos con...?" en vez de dar un ejercicio que nadie pidió.
        """
        if habilidad_id is not None:
            return self._sacar(habilidad_id)

        if (ejercicio := self._sacar(self._principal)) is not None:
            return ejercicio
        for otra in self._por_habilidad:
            if (ejercicio := self._sacar(otra)) is not None:
                return ejercicio
        return None

    def _sacar(self, habilidad_id: str | None) -> Ejercicio | None:
        cola = self._por_habilidad.get(habilidad_id or "")
        if not cola:
            return None
        ejercicio = cola.pop(0)
        self._entregados.append(ejercicio)
        return ejercicio

    @property
    def temas(self) -> list[str]:
        """Habilidades con ejercicios sin entregar. Van al prompt de sesión.

        El tutor no puede ofrecer lo que no sabe que tiene, y no puede pedir por
        id una habilidad que nadie le nombró.
        """
        return sorted(h for h, cola in self._por_habilidad.items() if cola)

    @property
    def principal(self) -> str | None:
        return self._principal

    @property
    def restantes(self) -> int:
        return sum(len(cola) for cola in self._por_habilidad.values())

    def restantes_de(self, habilidad_id: str) -> int:
        return len(self._por_habilidad.get(habilidad_id, []))

    @property
    def entregados(self) -> list[Ejercicio]:
        return list(self._entregados)

    def se_esta_agotando(self, umbral: int = 3) -> bool:
        """Aviso para que session.py recargue antes de quedarse sin nada.

        Mira la habilidad del día, no el total: con quince ejercicios de resta
        y cero de lo que toca hoy, el banco está agotado para lo que importa.
        """
        principal = self.restantes_de(self._principal) if self._principal else 0
        return principal <= umbral


# ─────────────────────────────────────────────────────────────────────────────
# request_camera — decisión, no efecto
# ─────────────────────────────────────────────────────────────────────────────


class SolicitudCamara(BaseModel):
    motivo: str = Field(description="Qué necesita ver. El tutor se lo dice al niño.")


def request_camera(motivo: str) -> SolicitudCamara:
    """Pide ver el cuaderno o la tarea. Central en modo Pedido."""
    return SolicitudCamara(motivo=motivo)


# ─────────────────────────────────────────────────────────────────────────────
# escalate_safety — el segundo camino a la alarma
# ─────────────────────────────────────────────────────────────────────────────


class AlertaSeguridad(BaseModel):
    """Alerta levantada por el TUTOR (el Vigilante tiene su propio camino).

    Dos caminos independientes a la alarma = defensa en profundidad. Cualquiera
    de los dos la dispara; ninguno depende del otro.
    """

    motivo: str
    evidencia: str | None = None
    origen: str = "tutor"


def escalate_safety(motivo: str, evidencia: str | None = None) -> AlertaSeguridad:
    return AlertaSeguridad(motivo=motivo, evidencia=evidencia)


# ─────────────────────────────────────────────────────────────────────────────
# verify_language — el gemelo de verify_arithmetic, para lectura y escritura
# ─────────────────────────────────────────────────────────────────────────────
# El 22/08, en una sesión de sílabas trabadas, el tutor llamó SEIS veces a
# `verify_arithmetic` y ni una a `check_answer`. La herramienta de aritmética
# le devolvió REQUIERE_JUICIO las seis —no sabe nada de sílabas— y entonces el
# modelo juzgó él. A un niño que separó "prim-o" le dijo "¡Perfecto!".
#
# Lo notó el niño, no nosotros:
#
#   «De pronto podría revisar una forma de calificar mejor, porque te dije
#    "primo" en vez de "primo" y me calificaste bien.»
#
# El argumento es idéntico al que creó `verify_arithmetic` y está escrito arriba:
# no se le prohíbe improvisar, se hace que lo improvisado también pase por
# código. La regla dura no era sobre la aritmética: era sobre que **el modelo no
# se juzgue a sí mismo**. Media aplicación se había quedado sin ella.


class ResultadoLengua(BaseModel):
    """Lo que sabe el código sobre una respuesta de lenguaje."""

    veredicto: Veredicto
    valor_interpretado: str | None = None
    lo_correcto: str | None = None
    """Solo cuando el niño YA se equivocó, para que el tutor no invente la
    corrección. Nunca se manda antes de que conteste."""


def _numero_dicho(respuesta: str) -> str | None:
    """«dos» -> "2". «son dos» -> "2". «una sola sílaba» -> "1".

    Solo para las comprobaciones cuya respuesta ES un número —cuántas sílabas,
    cuántos sonidos, cuántas letras—. Devuelve `None` cuando no hay número que
    sacar, y entonces no se toca nada: una respuesta de texto se compara como
    texto, igual que antes.
    """
    # OJO: acá NO se usa `_normalizar_texto`, que borra el relleno.
    #
    # Para `check_answer` está bien —"un cuarenta y dos" es "cuarenta y dos"—
    # pero acá el artículo ES la respuesta: a «¿cuántas sílabas?» el niño
    # contesta «una», y `_RELLENO` se la comía entera. La frase quedaba vacía y
    # el número se perdía justo en el caso que trajo todo esto.
    palabras = [p for p in re.split(r"[^\w]+", _sin_acentos(respuesta.lower())) if p]
    if not palabras:
        return None

    # La frase entera primero: es lo que hace funcionar «cuarenta y dos».
    if (entero := palabras_a_numero(" ".join(palabras))) is not None:
        return str(entero)

    # Si no, el número que haya adentro de la frase: «una sola sílaba» -> 1,
    # «creo que son dos» -> 2. Se toma el trozo más largo que convierta, de
    # izquierda a derecha, para no partir «veinticinco» ni «cuarenta y dos».
    hallados: list[int] = []
    i = 0
    while i < len(palabras):
        for largo in range(len(palabras) - i, 0, -1):
            if (n := palabras_a_numero(" ".join(palabras[i : i + largo]))) is not None:
                hallados.append(n)
                i += largo
                break
        else:
            i += 1

    # Dos números distintos es una duda, no una respuesta: «dos o tres» no se
    # adivina. Misma regla que `check_answer`, que ya la tenía escrita.
    return str(hallados[0]) if len(set(hallados)) == 1 else None


def verify_language(
    palabra: str, que: str, respuesta_nino: str, palabra2: str = ""
) -> ResultadoLengua:
    """Verifica una respuesta de lenguaje que el tutor improvisó. ~1ms, sin modelo.

    `que` es qué le preguntó: cuántas sílabas, con qué sonido empieza, si dos
    palabras riman. La cuenta la hace `tutor.lengua`, que no adivina — y cuando
    no puede saber, lo dice en vez de inventar.
    """
    from .lengua import verificar

    tipo = (que or "").strip().lower()
    if tipo not in COMPROBACIONES_LENGUA:
        return ResultadoLengua(veredicto=Veredicto.REQUIERE_JUICIO)
    if not palabra.strip() or not respuesta_nino.strip():
        return ResultadoLengua(veredicto=Veredicto.NO_SE_ENTENDIO)

    args = f"{palabra.strip()},{palabra2.strip()}" if palabra2.strip() else palabra.strip()
    expresion = f"{tipo}({args})"

    motivo = verificar(expresion, respuesta_nino)

    # EL NIÑO HABLA: dice «dos», no «2».
    #
    # `lengua.verificar` nació para validar el BANCO, comparando lo que escribió
    # el generador contra lo calculado — y ahí "2" es "2". El 22/08 se reusó tal
    # cual para esta herramienta, y con eso entró el bug más caro que tiene este
    # proyecto escrito: **confundir un acierto con un error.**
    #
    # `ses_f6cb91f4e15c` (23/08), sesión de lectura entera arruinada:
    #
    #   tutor: «¿Cuántas sílabas tiene "brazo"?»
    #   nino:  «una»            -> la herramienta: INCORRECTO (y lo era)
    #   nino:  «dos»            -> la herramienta: INCORRECTO (¡y NO lo era!)
    #   tutor: «no te alcanzo a entender bien, ¿me lo repites?»
    #
    # El tutor no estaba sordo: estaba atrapado entre lo que oía y lo que la
    # herramienta le decía. Y el niño lo diagnosticó mejor que nosotros —«al
    # parecer hay un problema cuando te digo que es una sola sílaba»—.
    #
    # `check_answer` aprendió esto hace fases (`palabras_a_numero`,
    # `NOMBRE_DE_LETRA`). Su gemelo nació sin ello. Misma lección de siempre:
    # cada tipo de respuesta que entra trae su propia forma de decirse en voz
    # alta, y no se ve venir desde el código — se ve pasando por acá lo que un
    # niño diría de verdad.
    if motivo is not None and (hablado := _numero_dicho(respuesta_nino)) is not None:
        if verificar(expresion, hablado) is None:
            return ResultadoLengua(veredicto=Veredicto.CORRECTO, valor_interpretado=hablado)

    if motivo is None:
        return ResultadoLengua(
            veredicto=Veredicto.CORRECTO, valor_interpretado=respuesta_nino.strip()
        )
    # Una expresión que el verificador no entiende NO es un error del niño: es
    # que no supimos comprobarlo. Decirlo, y que el tutor lo trabaje hablando.
    if "NO CIERRA" not in motivo:
        return ResultadoLengua(veredicto=Veredicto.REQUIERE_JUICIO)

    # Lo correcto se extrae de lo que ya calculó el verificador, no se recalcula.
    correcto = None
    if (m := re.search(r"= '([^']*)'", motivo)) or (m := re.search(r"es (sí|no),", motivo)):
        correcto = m.group(1)
    return ResultadoLengua(
        veredicto=Veredicto.INCORRECTO,
        # Se devuelve el NÚMERO que se entendió, no la frase cruda: el tutor
        # necesita poder decir «entendí que eran tres» para que el niño sepa
        # qué se le está corrigiendo.
        valor_interpretado=_numero_dicho(respuesta_nino) or respuesta_nino.strip(),
        lo_correcto=correcto,
    )
