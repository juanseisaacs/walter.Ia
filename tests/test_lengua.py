"""Lo que el código sabe del español, contra palabras de verdad.

Estos tests son de **calibración absoluta**, por la lección de la fase 2: no
comprueban que «las palabras largas tengan más sílabas» —eso pasa con el
silabeador roto— sino que «mariposa» dé exactamente `ma-ri-po-sa`. Un modelo de
lenguaje que se equivoque acá manda un ejercicio malo a un niño, y la única
defensa es que la respuesta correcta esté escrita a mano en un test.
"""

from __future__ import annotations

import pytest

from tutor.lengua import (
    clasificar,
    contar_silabas,
    le_falta_tilde,
    riman,
    silaba_tonica,
    silabas,
    sonido_final,
    sonido_inicial,
    tilde_bien_puesta,
    tipo_de_silaba,
    verificar,
)


class TestSilabeo:
    @pytest.mark.parametrize(
        "palabra, esperado",
        [
            # Lo simple: consonante + vocal, que es con lo que arranca 1°.
            ("mariposa", ["ma", "ri", "po", "sa"]),
            ("casa", ["ca", "sa"]),
            ("pelota", ["pe", "lo", "ta"]),
            # Dígrafos: una sola letra para el oído.
            ("calle", ["ca", "lle"]),
            ("chocolate", ["cho", "co", "la", "te"]),
            ("perro", ["pe", "rro"]),
            ("carro", ["ca", "rro"]),
            # Dos consonantes que NO forman grupo: se parten.
            ("carta", ["car", "ta"]),
            ("campo", ["cam", "po"]),
            ("hambre", ["ham", "bre"]),
            # Grupos inseparables: arrancan sílaba juntos.
            ("otro", ["o", "tro"]),
            ("hablar", ["ha", "blar"]),
            ("siglo", ["si", "glo"]),
            ("plato", ["pla", "to"]),
            ("brazo", ["bra", "zo"]),
            # Diptongos: una sola sílaba.
            ("viejo", ["vie", "jo"]),
            ("causa", ["cau", "sa"]),
            ("cuidado", ["cui", "da", "do"]),
            ("aire", ["ai", "re"]),
            # Hiatos: dos sílabas, aunque las vocales estén pegadas.
            ("leer", ["le", "er"]),
            ("caos", ["ca", "os"]),
            ("teatro", ["te", "a", "tro"]),
            ("dia", ["dia"]),  # sin tilde es diptongo, y es otra palabra
            ("día", ["dí", "a"]),  # la tilde parte el diptongo
            ("país", ["pa", "ís"]),
            ("baúl", ["ba", "úl"]),
            # Tres consonantes.
            ("transporte", ["trans", "por", "te"]),
            ("inglés", ["in", "glés"]),
            # Sílabas inversas: empiezan por vocal.
            ("alto", ["al", "to"]),
            ("antes", ["an", "tes"]),
            # Monosílabos.
            ("sol", ["sol"]),
            ("pan", ["pan"]),
            ("tres", ["tres"]),
        ],
    )
    def test_palabras_de_verdad(self, palabra, esperado):
        assert silabas(palabra) == esperado

    def test_le_da_igual_la_mayuscula_y_el_espacio(self):
        assert silabas("  Mariposa  ") == ["ma", "ri", "po", "sa"]

    def test_la_ene_sobrevive(self):
        # Normalizar «quitando tildes» se lleva la eñe por delante si se hace
        # mal, y «niño» pasa a ser «nino».
        assert silabas("niño") == ["ni", "ño"]
        assert silabas("año") == ["a", "ño"]

    def test_una_palabra_vacia_no_revienta(self):
        assert silabas("") == []
        assert contar_silabas("") == 0


class TestSonidos:
    def test_con_que_empieza(self):
        assert sonido_inicial("mesa") == "m"
        assert sonido_inicial("sol") == "s"
        # El dígrafo es UN sonido: un niño no dice que «chocolate» empieza con c.
        assert sonido_inicial("chocolate") == "ch"
        assert sonido_inicial("llave") == "ll"

    def test_con_que_termina(self):
        assert sonido_final("sol") == "l"
        assert sonido_final("mesa") == "a"
        assert sonido_final("canción") == "n"


class TestRimas:
    def test_las_que_riman(self):
        assert riman("gato", "pato")
        assert riman("casa", "pasa")
        assert riman("canción", "corazón")
        assert riman("mariposa", "hermosa")

    def test_las_que_no(self):
        assert not riman("gato", "carro")
        assert not riman("sol", "mesa")
        # «perro» y «carro» comparten las dos últimas sílabas menos la vocal
        # tónica, que es justo la que manda: e-rro contra a-rro.
        assert not riman("perro", "carro")

    def test_libro_y_grito_no_riman(self):
        # Este caso lo trajo una tanda de verdad, y venía al revés: el modelo
        # dijo «no riman» y el verificador lo rechazó por equivocado. El
        # equivocado era el verificador — buscaba la vocal tónica en toda la
        # cola en vez de dentro de la sílaba fuerte, y encontraba la «o» final
        # en las dos. Un tope que descarta contenido bueno es el modo de fallar
        # más caro de este proyecto, y es la cuarta vez.
        assert not riman("libro", "grito")
        assert not riman("libro", "amigo")

    def test_una_palabra_no_rima_consigo_misma(self):
        # Es lo primero que se le ocurre a un modelo al que le piden rimas, y no
        # enseña nada: el niño tiene que OÍR el parecido entre dos palabras.
        assert not riman("gato", "gato")
        assert not riman("canción", "cancion")

    def test_no_basta_con_que_terminen_igual(self):
        # «cantar» y «lugar» riman en «ar». «árbol» y «sol» no: la tónica de
        # árbol es «ár», así que la rima tendría que ser «árbol»/«farol» — no.
        assert riman("cantar", "lugar")
        assert not riman("árbol", "sol")


class TestAcentuacion:
    @pytest.mark.parametrize(
        "palabra, clase",
        [
            ("canción", "aguda"),
            ("papel", "aguda"),
            ("cantar", "aguda"),
            ("casa", "grave"),
            ("árbol", "grave"),
            ("lápiz", "grave"),
            ("mariposa", "grave"),
            ("pájaro", "esdrujula"),
            ("médico", "esdrujula"),
            ("rápido", "esdrujula"),
        ],
    )
    def test_clasificar(self, palabra, clase):
        assert clasificar(palabra) == clase

    def test_cual_suena_mas_fuerte(self):
        assert silaba_tonica("mariposa") == "po"
        assert silaba_tonica("canción") == "ción"
        assert silaba_tonica("pájaro") == "pá"

    @pytest.mark.parametrize("palabra", ["canción", "árbol", "lápiz", "pájaro", "médico"])
    def test_bien_escritas(self, palabra):
        assert tilde_bien_puesta(palabra) is True, f"«{palabra}» está bien y el código la rechaza"

    @pytest.mark.parametrize("palabra", ["cása", "papél", "cantár", "casáda"])
    def test_mal_escritas(self, palabra):
        assert tilde_bien_puesta(palabra) is False, f"«{palabra}» está mal y el código la acepta"

    @pytest.mark.parametrize("palabra", ["cancion", "arbol", "lapiz", "casa", "papel", "mariposa"])
    def test_sin_tilde_escrita_dice_que_no_sabe(self, palabra):
        # Este es el test que atrapó el bug: la primera versión INFERÍA la
        # tónica con la regla general y después comprobaba la regla general
        # contra sí misma. «cancion» y «canción» salían las dos correctas.
        # Sin tilde no hay tónica de dónde agarrarse, y decirlo es la respuesta.
        assert tilde_bien_puesta(palabra) is None

    def test_los_hiatos_no_se_rechazan(self):
        # «día» y «país» rompen la regla general a propósito. El verificador no
        # los tumba: rechazar contenido correcto es peor que no verificarlo.
        for palabra in ("día", "país", "baúl", "reúne"):
            assert tilde_bien_puesta(palabra) is not False

    def test_los_monosilabos_no_se_juzgan(self):
        # «sí», «él», «tú» llevan tilde por lo que significan, no por la regla.
        for palabra in ("sí", "él", "tú", "más"):
            assert tilde_bien_puesta(palabra) is None

    def test_la_pregunta_que_el_banco_hace_de_verdad(self):
        # El ejercicio es «cancion está sin tilde, ¿cómo se escribe?».
        assert le_falta_tilde("cancion", "canción")
        assert le_falta_tilde("arbol", "árbol")
        assert le_falta_tilde("pajaro", "pájaro")
        # La tilde en el lugar equivocado no cuenta como respuesta.
        assert not le_falta_tilde("cancion", "cáncion")
        # Ni contestar otra palabra.
        assert not le_falta_tilde("cancion", "canciones")


class TestTipoDeSilaba:
    def test_los_cuatro_tipos(self):
        assert tipo_de_silaba("ma") == "directa"
        assert tipo_de_silaba("al") == "inversa"
        assert tipo_de_silaba("bra") == "trabada"
        assert tipo_de_silaba("pan") == "mixta"
        assert tipo_de_silaba("a") == "sola"

    def test_el_digrafo_no_es_una_trabada(self):
        # «cha» tiene dos letras y un solo sonido: es directa, como «ma».
        assert tipo_de_silaba("cha") == "directa"
        assert tipo_de_silaba("lle") == "directa"


class TestLoQueEnsenoUnaTandaDeVerdad:
    """Casos que salieron generando el banco, no inventados en el escritorio.

    Los cinco venían al revés de como se leen: el modelo había escrito el
    ejercicio bien y el verificador lo tumbaba. Es el modo de fallar más caro
    del proyecto y ya iba por la quinta vez cuando se escribió esta clase.
    """

    def test_be_y_uve_suenan_igual(self):
        # «¿Nube rima con tuve?» — el modelo dijo que sí y tenía razón. En
        # español b y v son el mismo sonido, y este tutor entra por el oído.
        assert riman("nube", "tuve")
        assert riman("vaca", "flaca")

    def test_el_seseo_y_el_yeismo_de_acá(self):
        # Un tutor colombiano no distingue casa de caza, ni llave de yave.
        assert riman("casa", "caza")
        assert riman("cabello", "sello")

    def test_la_hache_no_suena(self):
        assert riman("hoja", "roja")

    def test_los_sonidos_de_una_palabra(self):
        # `lec.fonologia.segmentar_fonemas` se quedaba sin banco entero: no
        # había comprobación de fonemas, y el modelo usaba la de sílabas.
        assert verificar("sonidos(sol)", "/s/ /o/ /l/") is None
        assert verificar("sonidos(gato)", "g-a-t-o") is None
        assert verificar("fonemas(sol)", "3") is None

    def test_el_digrafo_es_un_solo_sonido(self):
        # «chocolate» tiene 8 sonidos, no 9: la ch es uno.
        assert verificar("fonemas(chocolate)", "8") is None
        assert verificar("fonemas(chocolate)", "9") is not None

    def test_da_igual_como_el_modelo_separe_los_sonidos(self):
        for forma in ("/s/ /o/ /l/", "s-o-l", "s, o, l", "s o l"):
            assert verificar("sonidos(sol)", forma) is None, forma
        # Pero no da igual que falte uno.
        assert verificar("sonidos(sol)", "/s/ /o/") is not None

    def test_un_numero_equivocado_no_pasa(self):
        # El test que faltaba, y que habría cazado el agujero: al aflojar la
        # comparación para los sonidos, los dígitos se filtraban también, así
        # que «4» y «99» eran los dos la cadena vacía y CUALQUIER respuesta
        # numérica se daba por buena.
        assert verificar("silabas(mariposa)", "4") is None
        for mala in ("3", "5", "99", "cero"):
            assert verificar("silabas(mariposa)", mala) is not None, mala
        assert verificar("fonemas(sol)", "4") is not None
        assert verificar("letras(gato)", "9") is not None

    def test_el_sonido_inicial_no_es_la_letra_inicial(self):
        # El nodo se llama «sonido inicial y final». A «¿con qué sonido empieza
        # casa?» se contesta /k/ y está bien, aunque se escriba con c. El
        # modelo lo contestó así y el verificador lo tumbaba.
        assert verificar("inicial(casa)", "/k/") is None
        assert verificar("inicial(casa)", "c") is None
        assert verificar("inicial(queso)", "/k/") is None
        assert verificar("final(sol)", "/l/") is None
        # Que se acepte el sonido no vuelve todo válido.
        assert verificar("inicial(casa)", "t") is not None
        assert verificar("inicial(triángulo)", "tr") is not None

    def test_los_sonidos_se_oyen_con_el_acento_de_acá(self):
        # «pez» son /p/ /e/ /s/: la z sesea. El modelo lo escribió así y el
        # verificador, que comparaba letras, lo tumbó.
        assert verificar("sonidos(pez)", "/p/ /e/ /s/") is None
        assert verificar("sonidos(lápiz)", "/l/ /á/ /p/ /i/ /s/") is None

    def test_el_arranque_de_una_trabada(self):
        # `lec.decodificacion.silabas_trabadas` necesita preguntar por las dos
        # consonantes pegadas, y no había con qué: el modelo lo declaraba con
        # `sonidos()`, que devuelve la palabra entera.
        assert verificar("arranque(plato)", "/p/ /l/") is None
        assert verificar("arranque(fruta)", "f-r") is None
        assert verificar("arranque(plato)", "/p/ /r/") is not None
