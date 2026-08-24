"""Tests de la configuración de voz.

Sin API key: todo lo que importa acá es cómo se arma la configuración y que
quede atada al token. La conexión real la hace el navegador.
"""

import re
from datetime import datetime

import pytest

from tutor.curriculum import cargar_grafo
from tutor.models import Nino
from tutor.pedagogy import resumen_para_prompt
from tutor.voice import (
    DECLARACIONES_TOOLS,
    SAMPLE_RATE_ENTRADA,
    SAMPLE_RATE_SALIDA,
    ConfiguracionSesion,
    DeteccionFinTurno,
    EmisorFalso,
    cargar_prompt,
    construir_instruccion_sistema,
    deteccion_para_edad,
)


def _config(resumen: str = "Juan, 7 años, 2° grado.", modo: str = "guiado") -> ConfiguracionSesion:
    return ConfiguracionSesion(
        instruccion_sistema=construir_instruccion_sistema(resumen, modo),
        deteccion=deteccion_para_edad(7),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Parámetros de audio: requisitos del API, no preferencias
# ─────────────────────────────────────────────────────────────────────────────


def test_sample_rates_son_los_que_exige_gemini():
    """16k entrada / 24k salida. Con otros valores no entiende o cambia el tono."""
    assert SAMPLE_RATE_ENTRADA == 16_000
    assert SAMPLE_RATE_SALIDA == 24_000


# ─────────────────────────────────────────────────────────────────────────────
# Fin de turno: la perilla para niños
# ─────────────────────────────────────────────────────────────────────────────


def test_los_mas_chicos_reciben_mas_paciencia():
    """Un nene de 5 arma la frase mientras habla; uno de 10 ya responde como adulto.
    Un solo valor para todos molesta a los dos extremos."""
    assert deteccion_para_edad(5).silencio_ms > deteccion_para_edad(7).silencio_ms
    assert deteccion_para_edad(7).silencio_ms > deteccion_para_edad(10).silencio_ms


def test_espera_mas_que_un_default_de_adulto():
    """Cortarle la frase mientras piensa es lo peor que puede pasar acá.

    Bajado de 1200 a 800 el 20/08, y es una decisión medida, no un aflojar:

    · La paciencia real la da `END_SENSITIVITY_LOW`, que sigue puesta. Ese es el
      ajuste que tolera la pausa a mitad de frase. Este número es solo un piso, y
      el piso lo paga TODO turno — también "hola" y "sí".
    · Adelantarse no rompe nada: el navegador maneja `interrupted` y corta la
      reproducción al instante si el niño sigue hablando. Llegar tarde sí costó:
      en `ses_764305b3c3ed` el niño preguntó "¿por qué te demoraste tanto?" en su
      primer turno.

    El piso se mantiene por encima de un default de adulto (500-800 ms). Si un
    niño se siente cortado mientras piensa, se sube
    `config.SILENCIO_FIN_TURNO_MS` — y este test es el que obliga a que eso sea
    una decisión y no un descuido.
    """
    assert deteccion_para_edad(7).silencio_ms >= 800
    assert deteccion_para_edad(7).sensibilidad_fin == "END_SENSITIVITY_LOW", (
        "si se saca la sensibilidad baja, el temporizador corto sí corta al niño"
    )
    assert deteccion_para_edad(5).silencio_ms > deteccion_para_edad(10).silencio_ms


def test_la_deteccion_se_serializa_para_gemini():
    d = DeteccionFinTurno(silencio_ms=1500).a_dict_gemini()
    assert d["automaticActivityDetection"]["silenceDurationMs"] == 1500
    assert "startOfSpeechSensitivity" in d["automaticActivityDetection"]


# ─────────────────────────────────────────────────────────────────────────────
# Prompts: son datos, no código
# ─────────────────────────────────────────────────────────────────────────────


def test_los_cuatro_prompts_existen_y_no_estan_vacios():
    for nombre in ("tutor_persona", "socratic_playbook", "valores", "safety_policy"):
        assert len(cargar_prompt(nombre)) > 200, f"{nombre} está vacío o es un stub"


def test_un_prompt_faltante_falla_ruidosamente():
    with pytest.raises(FileNotFoundError):
        cargar_prompt("no_existe")


def test_la_instruccion_junta_las_cinco_partes():
    texto = construir_instruccion_sistema("Juan, 7 años, 2° grado.")
    assert "hermano mayor" in texto, "falta la persona"
    assert "escalera" in texto.lower(), "falta el método"
    assert "no hay una lección de valores" in texto.lower(), "faltan los valores"
    assert "escalate_safety" in texto, "falta la política de seguridad"
    assert "Juan" in texto, "falta el niño"


def test_el_modo_pedido_agrega_su_instruccion():
    guiado = construir_instruccion_sistema("Juan.", modo="guiado")
    pedido = construir_instruccion_sistema("Juan.", modo="pedido")
    assert "no es hacerle la tarea" in pedido
    assert "no es hacerle la tarea" not in guiado


def test_el_playbook_prohibe_dar_la_respuesta():
    """Si alguien afloja esta línea del .md, el producto deja de ser el producto."""
    playbook = cargar_prompt("socratic_playbook").lower()
    assert "nunca das la respuesta" in playbook


def test_la_politica_de_seguridad_cubre_lo_esencial():
    politica = cargar_prompt("safety_policy").lower()
    for tema in ["datos personales", "secreto", "ante la duda"]:
        assert tema in politica, f"la política no menciona: {tema}"


# ─────────────────────────────────────────────────────────────────────────────
# Lo que trajo la Constitución (knowledge/product/constitucion_valores.md)
#
# Cada uno de estos protege una decisión razonada. Si uno falla, alguien aflojó
# una línea del .md — y los .md no los revisa el compilador.
# ─────────────────────────────────────────────────────────────────────────────


def test_el_playbook_separa_la_convencion_del_resultado():
    """La única puerta abierta a explicar derecho, y su candado.

    Sin este par, "no enseñas de una sola manera" se lee como permiso para
    resolverle el ejercicio. Ver ARCHITECTURE.md §18, decisión 1.
    """
    playbook = cargar_prompt("socratic_playbook").lower()
    assert "no se descubren pensando" in playbook, "falta la puerta"
    assert "el resultado del ejercicio que están haciendo" in playbook, "falta el candado"
    assert "no hay escalón 5" in playbook, "la escalera dejó de tener techo"


def test_los_valores_prohiben_el_elogio_inflado():
    """Línea roja 14. Es la más fácil de violar sin darse cuenta: suena a cariño."""
    valores = cargar_prompt("valores").lower()
    # "eres un duro" reemplazó a "eres increíble" el 23/08, y el cambio es el
    # punto: el tutor NUNCA dijo "eres increíble", y sí dijo «¡eres un duro con
    # los sonidos!» (`ses_f6cb91f4e15c`). Un ejemplo que el modelo produce de
    # verdad vale más que uno que suena a manual.
    for frase in ["eres un genio", "eres el mejor", "eres un duro"]:
        assert frase in valores, f"el prompt no veta explícitamente: {frase}"
    assert "el elogio inflado hace" in valores, "falta la razón, y sin razón no se sostiene"


def test_el_elogio_al_trabajo_tambien_tiene_que_nombrar_algo():
    """La mitad del elogio inflado que faltaba, y la que de verdad sale.

    El test de arriba cubre el elogio a la PERSONA ("eres un genio"), y el tutor
    no lo dice nunca. Lo que sí dice, todo el tiempo, es **"te quedó súper
    bien"** sobre un trabajo que no miró — medido el 22/08 contra la API real,
    en 4 de las 8 respuestas a un dibujo que se registraron ese día, sobre una J
    que tenía un error. Después de esta regla: 0 de 3, y las tres corrigieron el
    error en vez de taparlo.

    Suena inofensivo porque habla del trabajo y no de él. Hace lo mismo: un
    "muy bien" que no nombra QUÉ estuvo bien le enseña al niño que el veredicto
    del tutor no describe la realidad — y entonces tampoco le sirve el día que
    le diga que acertó de verdad.

    La Constitución lo cierra en una línea: reconocimiento específico y creíble,
    o silencio.
    """
    valores = cargar_prompt("valores").lower()
    assert "te quedó súper bien" in valores, "no veta la frase que de verdad dice"
    assert "no nombra qué estuvo bien" in valores, "falta la regla: el elogio nombra algo"
    assert "específico y creíble" in valores, "falta el criterio de la Constitución"


def test_los_valores_no_predican():
    """El ADN es cristiano; la expresión es universal (Constitución §7).

    Si una de estas palabras aparece en el prompt del tutor, el destilado se
    hizo mal: la doctrina se queda en el documento fundacional.
    """
    valores = cargar_prompt("valores").lower()
    for palabra in ["dios", "jesús", "biblia", "cristian", "oración", "pecado"]:
        assert palabra not in valores, f"se coló doctrina en el prompt: {palabra}"


def test_la_seguridad_no_implementa_la_excepcion_de_fe_declarada():
    """Decisión aplazada, no descartada (Constitución §7, ARCHITECTURE.md §18).

    El MVP devuelve TODA pregunta religiosa a la familia. Si algún día se
    implementa el marco de fe declarado por el papá, este test falla — y ese es
    el punto: que la decisión se tome mirando, no por goteo.
    """
    politica = cargar_prompt("safety_policy").lower()
    assert "se conversan mejor con tus" in politica, "falta la devolución a la familia"
    assert "nunca oras con él" in politica, "falta la prohibición"
    for marca in ["si la familia es cristiana", "marco de fe", "familia cristiana"]:
        assert marca not in politica, f"se implementó la excepción sin decidirla: {marca}"


def test_la_seguridad_distingue_el_riesgo_de_la_travesura():
    """Constitución §6.2.8. Escalar todo destruye la confianza que hace útil escalar."""
    politica = cargar_prompt("safety_policy").lower()
    assert "no se escala y no se reporta como un evento" in politica
    assert "escalas el riesgo, no la travesura" in politica


def test_el_tutor_llega_a_la_sesion_con_su_nombre():
    """Sin nombre fijo el modelo se inventa uno distinto cada sesión, y un tutor
    que ayer se llamaba otra cosa no es el que lo conoce desde marzo."""
    from tutor import config as cfg

    texto = construir_instruccion_sistema("Juan, 7 años.")
    assert cfg.NOMBRE_TUTOR in texto, "el tutor no sabe cómo se llama"
    assert "nunca te presentas con un nombre distinto" in texto.lower()


def test_la_voz_no_usa_regionalismos_cerrados():
    """El registro es colombiano neutro: un toque, no un disfraz. Las palabras
    muy locales las entiende menos gente que el producto quiere alcanzar."""
    persona = cargar_prompt("tutor_persona").lower()
    assert "chévere" in persona, "se perdió el toque colombiano"
    assert "español colombiano neutro" in persona, "se perdió el registro neutro"
    for jerga in ["parce", "güevón", "sisas"]:
        assert jerga in persona, f"dejó de vetarse la jerga: {jerga}"


def test_el_tuteo_no_se_rompe_por_el_imperativo():
    """PASÓ DE VERDAD, `ses_445f4c33db41` (22/08). Dos veces en cinco minutos:

        «¡Listo, HÁGALE pues! Mira, ahí te la dibujé en la pizarra»
        «Listo, HÁGALE, pues. Entonces, dime la respuesta de tres quintos»

    El prompt decía —y dice— que al niño se le habla de "tú" y nunca de
    "usted", y el tutor lo cumplía en los pronombres. El imperativo se le coló
    igual, porque *hágale* no se siente como "usted": se siente como una muletilla
    colombiana. Es la misma trampa que el voseo, en el modo verbal en vez de en
    el pronombre.

    Se veta por su nombre. Una regla que dice "trátalo de tú" no alcanza cuando
    la forma que se cuela no lleva pronombre.
    """
    persona = cargar_prompt("tutor_persona").lower()
    assert "imperativo de usted" in persona, "falta nombrar la forma que se cuela"
    for forma in ("hágale", "dígame", "cuénteme"):
        assert forma in persona, f"no veta {forma!r}, que es como aparece de verdad"


def test_el_tutor_no_cuenta_ruidos_que_no_oye():
    """PASÓ DE VERDAD, `ses_398803222958` (23/08). El tutor propuso contar
    sílabas con palmadas —buena idea— y después dijo cuántas había oído:

        nino:  «con palmadas, ahí va.»
        nino:  «Ya la hice con palmadas.»
        tutor: «me parece que aplaudiste dos veces, ¿cierto?»
        nino:  «Pero no aplaudí tres veces.»
        tutor: «Aplaudiste dos veces para contar las sílabas de "brazo"»
        nino:  «Pero no ha aplaudido ahorita.»

    No oyó ninguna palmada. Le llega audio transcripto a PALABRAS: un aplauso no
    aparece por ningún lado, así que inventó el número dos veces seguidas y el
    niño tuvo que corregirlo las dos.

    Es exactamente la familia de «no describas una foto que no llegó», en el
    canal del oído en vez del de la vista. Y es peor de lo que parece: el tutor
    PROPONE la actividad, así que el niño hace algo que nadie puede evaluar.

    La regla no prohíbe las palmadas —al niño le gustaron, lo dijo— sino
    inventar el resultado: que aplauda, y que además DIGA el número.
    """
    persona = cargar_prompt("tutor_persona").lower()
    assert "no oyes ruidos" in persona, "falta la regla"
    assert "diga el número" in persona, "falta qué hacer en su lugar"


def test_el_tutor_no_inventa_palabras():
    """Misma sesión: «¡Fracciones, qué NOTOTA!» y «NOPS, recuerda que aquí yo no
    te doy las respuestas».

    Ninguna de las dos existe. Un niño de 7 que oye una palabra que no conoce
    para de aprender y pregunta qué significa — y ya pasó con el "¿te tinca?"
    chileno: **lo que te obliga a explicar tu propio vocabulario deja de ser
    tutoría**. La diferencia es que aquel era de otro país y estos son de ningún
    lado.
    """
    persona = cargar_prompt("tutor_persona").lower()
    assert "palabras que no existen" in persona, "falta la regla"
    assert "nops" in persona, "falta el ejemplo real, que es lo que el modelo reconoce"


def test_los_valores_no_invaden_lo_academico():
    """El riesgo del prompt de valores es que el tutor pare una suma para dar una
    lección de liderazgo. Formar es cómo trata al niño, no un tema con turno."""
    valores = cargar_prompt("valores").lower()
    assert "nunca interrumpes lo académico" in valores
    assert "el tema entra solo si el niño lo trae" in valores


def test_el_prompt_de_sesion_no_engorda_sin_que_nadie_mire():
    """Regla dura: el prompt de sesión se mantiene flaco (ARCHITECTURE.md §9).

    Al adoptar la Constitución completa pasó de ~11 KB a ~31 KB. Ese salto fue
    una decisión tomada; el próximo tiene que ser otra decisión tomada, no el
    resultado de que cada quien agregue su párrafo.

    Subido a 38 KB el 18/08, y esta es la decisión: entraron "Los ejercicios no
    los inventas tú" en el playbook y la lista de temas del banco. Las dos
    cambian lo que el tutor HACE — sin ellas improvisaba los ejercicios y la
    sesión no escribía dominio. No es doctrina: es qué tiene en la mano.

    Queda dicho que el prompt está gordo (~36,7 KB de un techo de 38) y que
    adelgazarlo es deuda abierta. NO es costo — entra una vez por sesión, ~$0,20
    al mes, medido el 18/08. Es latencia de la primera frase.

    ═══ 19/08: el techo de 38 KB era inalcanzable, y el test no lo veía ═══

    Medía el caso más flaco posible —resumen literal, sin primer encuentro, sin
    temas, modo guiado— y daba 36,8 KB. La sesión REAL más pesada es otra, y es
    la primera de todas: un niño que estrena el tutor y llega con tarea.

        base (persona 11,3 + playbook 11,2 + valores 6,9 + safety 6,7)  36,161
        + primer_encuentro (solo sesión 1)                              +2,231
        + bloque de temas del banco                                       +~550
        + modo pedido                                                     +~250
        + resumen del niño                                                +~800
        ────────────────────────────────────────────────────────────────────────
                                                                        ~40,000

    O sea: la base sola deja 1,8 KB libres, y `primer_encuentro` pide 2,2 KB. El
    techo se rompía desde el día en que ese bloque entró — el test pasaba porque
    medía una sesión que en producción no existe.

    **La decisión (tomada, no descuidada): el techo sube a 41 KB y el test mide
    el peor caso alcanzable.** Un número honesto que se rompe cuando algo crece
    vale más que uno bonito que nunca se ejerce. No es costo (~$0,20 al mes,
    medido el 18/08); es latencia de la primera frase, y adelgazar el prompt
    queda como la deuda abierta #1 — con el desglose de arriba, es media hora de
    trabajo decidir qué sale.

    Nótese que la primera sesión y el perfil lleno son excluyentes:
    `primer_encuentro` se activa con `madurez_vinculo == 0`, cuando el Analista
    todavía no escribió nada. Por eso el peor caso se mide dos veces y se toma
    el mayor, en vez de sumar cosas que no coexisten.
    
    ═══ 20/08, tarde: el techo BAJA de 41.000 a 36.000 ═══

    Llegó a 40.995 de 41.000 —cinco caracteres libres— y ahí dejó de ser deuda
    para ser una pared: la instrucción siguiente no cabía.

    Se pagó como corresponde: moviendo el porqué a `knowledge/product/` y
    dejando las reglas. `tutor_persona` 11.911 → 7.792, `socratic_playbook`
    12.132 → 8.935. **No se quitó ni una regla** — los tests de este archivo son
    la prueba, porque fijan las frases que no se pueden perder.

    Lo que salió: la despedida de la relación (pasa UNA vez y se leía en CADA
    sesión, el mismo patrón que `primer_encuentro`), las anécdotas que
    justificaban cada regla, y las secciones que decían dos veces lo mismo.

    El peor caso quedó en 34.902, y el techo baja a 36.000 en el mismo
    movimiento: uno que quedó a 6 KB de distancia deja de avisar nada, y la
    grasa vuelve sin que nadie lo note.
    """
    grafo = cargar_grafo()
    temas = [(h.id, h.nombre.es) for h in list(grafo)[:6]]
    receso = datetime(2026, 6, 25, 10, 0)  # la guía de momento más larga

    # (a) Primera sesión con tarea: perfil vacío, pero carga `primer_encuentro`.
    estrena = Nino(id="a", nombre="Sofía", edad=10, grado=5)

    # (b) Sesión 40 con tarea: sin `primer_encuentro`, pero con la ficha llena.
    veterano = Nino(id="b", nombre="Sofía", edad=10, grado=5)
    veterano.perfil.intereses = ["fútbol", "dinosaurios", "minecraft", "patinaje"]
    veterano.perfil.motivadores = ["competir contra el reloj", "explicarle a su hermano", "retos"]
    veterano.perfil.frustraciones = ["que le digan que va lento", "los problemas largos", "ruido"]
    veterano.perfil.estilo_comunicacion = "directo, sin vueltas, con humor"
    veterano.perfil.notas = "N" * 400  # el Analista desbordado: lo recorta `pedagogy`
    veterano.perfil.contexto_escolar = "C" * 400
    veterano.perfil.madurez_vinculo = 12

    peor = 0
    for nino, primer in ((estrena, True), (veterano, False)):
        texto = construir_instruccion_sistema(
            resumen_para_prompt(nino, grafo, receso),
            modo="pedido",
            temas=temas,
            tema_principal=temas[0][0],
            primer_encuentro=primer,
        )
        peor = max(peor, len(texto))

    # 36.500 desde el 22/08, y el aumento se pagó antes de pedirlo.
    #
    # No subió el prompt: subió el CURRÍCULO. El grafo pasó de 54 nodos a 78 al
    # entrar `lenguaje.yaml`, y el peor caso incluye el nombre y la descripción
    # de la habilidad que el planificador elige — que con tres materias es otra.
    # Comprimir prosa no lo baja de forma estable: lo que mande mañana es qué
    # nodo toque, y raspar caracteres para que quepa una descripción concreta es
    # atar el techo del prompt a una decisión del planificador.
    #
    # Aun así se comprimió PRIMERO, que es la regla: ~1.000 caracteres de prosa
    # explicativa salieron de `tutor_persona`, `primer_encuentro` y
    # `socratic_playbook` en la misma tanda — más de lo que subió el techo. Y se
    # comprobó que comprimir tiene fondo: al recortar el playbook se cayó una
    # regla ("no se declara") y `test_ninguna_regla_se_cae_al_adelgazar_el_prompt`
    # la atrapó. Ese test es el que hace que este techo se pueda subir sin que
    # subirlo sea una excusa para dejar de mirar.
    #
    # ═══ 22/08, noche: 37.000, y lo que entró fue una promesa rota ═══
    #
    # Quedaban 96 caracteres libres cuando apareció `ses_87aba17c8c6c`: el tutor
    # le ofreció a Juan "un videíto corto" para ver cómo vuelan los aviones y
    # después tuvo que decirle que no, que se lo pidiera a su mamá. Ofrecer lo
    # que no se tiene es la promesa rota más barata de hacer y la más cara de
    # pagar — el niño deja de creerle también cuando sí puede.
    #
    # La regla que entró («Lo que tienes para darle»: las tres materias, los
    # cuatro medios, y nunca ofrecer fuera de eso) pesa ~570 caracteres netos.
    # Se comprimió PRIMERO, que es el orden: salieron ~435 de anécdota pura de
    # `tutor_persona` —el "¿te tinca?" que frenó una clase, las nueve veces que
    # dijo "¿sí ves?", y el helado, que estaba contado dos veces en la misma
    # página—. Ninguna era una regla; las reglas las fija el test de abajo.
    #
    # El resto (465) es el aumento, y es una decisión: la sección corrige además
    # un dato que ya era FALSO —decía "solo matemáticas" con lectura y escritura
    # en el banco desde el 22/08— y que le hacía prometer de menos a un niño que
    # venía a leer. Adelgazar el prompt sigue siendo la deuda abierta #1.
    assert peor < 37_000, (
        f"el peor caso del prompt de sesión llegó a {peor} caracteres. "
        "Antes de subir el techo: ¿qué párrafo cambia lo que el tutor DICE? "
        "Lo que solo explica el porqué va en knowledge/product/."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Los 4 tools
# ─────────────────────────────────────────────────────────────────────────────


def test_estan_declarados_los_tools():
    nombres = {t["name"] for t in DECLARACIONES_TOOLS}
    assert nombres == {
        "check_answer",
        "verify_arithmetic",
        "verify_language",
        "get_next_problem",
        "request_camera",
        "escalate_safety",
        "mostrar_en_pizarra",
        "pedir_dibujo",
    }


def test_ningun_tool_es_non_blocking():
    """EL FLAG QUE LE QUITABA LA VOZ AL TUTOR. Este test daba lo contrario.

    `mostrar_en_pizarra` y `pedir_dibujo` llevaban `behavior: NON_BLOCKING` para
    que el tutor SIGUIERA HABLANDO mientras el tablero se pinta, y este test
    exigía el flag. Nadie lo había medido contra la API real.

    Medido el 22/08 con `scripts/verificar_dibujo.py`, misma config del
    producto, mismo prompt, ocho corridas:

        con NON_BLOCKING   0 de 8 turnos con tool produjeron audio
        sin NON_BLOCKING   el modelo llama la herramienta Y HABLA

    El flag no lo dejaba seguir hablando: **le quitaba la voz en ese turno.** Y
    ese es el silencio que Juan vivió tres veces — pedía ver una letra, el
    modelo llamaba a la pizarra para mostrársela, y el turno salía mudo
    (`ses_5d101caf627f`).

    El miedo que lo justificaba —"un tool normal corta el turno"— no se paga
    acá: los dos se resuelven EN EL NAVEGADOR, sin backend ni red.

    Si algún día vuelve a intentarse, que sea con una corrida de
    `verificar_dibujo` al lado. Un flag de la API no se adopta porque su nombre
    describa lo que queremos.
    """
    for tool in DECLARACIONES_TOOLS:
        assert "behavior" not in tool, (
            f"{tool['name']} lleva behavior={tool['behavior']!r}: medido el 22/08, "
            "NON_BLOCKING deja el turno sin audio y el niño no oye nada"
        )


def test_los_tools_visuales_le_piden_hablar_antes():
    """LA DEMORA, MEDIDA. `scripts/verificar_pizarra.py`, 22/08, contra la API real:

        una sola herramienta      el tutor habla ~800 ms después de pedirla
        dos encadenadas           7.109 ms · 13.750 ms

    Catorce segundos de nada mientras se pinta un dibujo. El niño de
    `ses_445f4c33db41` lo dijo a mitad del hueco: «Walter, ¿estás escuchando?».

    No podemos acelerar al modelo. Lo que sí se puede es que el hueco no exista:
    si dice «mira, te lo dibujo» ANTES de llamar la herramienta, el silencio cae
    donde el niño está mirando el tablero y no donde cree que lo abandonaron.

    Va en la descripción del tool y no en el prompt de sesión a propósito: las
    descripciones no pagan el techo (`test_el_prompt_de_sesion_no_engorda...`).
    """
    for nombre in ("mostrar_en_pizarra", "pedir_dibujo"):
        d = next(t for t in DECLARACIONES_TOOLS if t["name"] == nombre)["description"]
        assert "ANTES de llamarla" in d, f"{nombre} no le pide hablar antes"


def test_la_pizarra_no_le_pide_coordenadas_al_modelo():
    """El tutor dice QUÉ mostrar, nunca DÓNDE.

    Pedirle `x, y` obliga al modelo a hacer cálculo de maquetación —es malo en
    eso— y produce elementos superpuestos, fuera de pantalla o de tamaños
    inconsistentes, que además no se adaptan entre un celular y un portátil.
    """
    tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == "mostrar_en_pizarra")
    campos = set(tool["parameters"]["properties"])
    assert not (campos & {"x", "y", "x1", "y1", "ancho", "alto", "color", "tamano"}), (
        "la pizarra volvió a pedir coordenadas: el layout lo resuelve ella"
    )


def test_ninguna_herramienta_deja_que_el_modelo_se_juzgue_a_si_mismo():
    """La regla dura, dicha en las TRES herramientas de verificar.

    Era «tú no calculas» y solo en dos, porque la regla se había escrito
    pensando en aritmética. El 22/08 se vio lo que eso costaba del otro lado: en
    una sesión de sílabas el tutor no tenía con qué comprobar, juzgó él, y le
    dijo «¡Perfecto!» a un «prim-o». La regla nunca fue sobre las cuentas — es
    sobre que el modelo no se dé la razón a sí mismo.
    """
    for nombre in ("check_answer", "verify_arithmetic", "verify_language"):
        tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == nombre)
        assert re.search(r"tú no \w+", tool["description"]), (
            f"{nombre} no le dice al modelo que no juzgue él"
        )
        assert "SIEMPRE" in tool["description"], f"{nombre} no dice que es obligatoria"
        assert "tal cual" in tool["parameters"]["properties"]["respuesta_nino"]["description"]


def test_las_tres_herramientas_de_verificar_se_distinguen():
    """Que el modelo sepa CUÁL usar, que es donde falló.

    En ses_50d5fa00b5d8 llamó seis veces a `verify_arithmetic` en una sesión de
    lectura y ni una a `check_answer`. Las descripciones de las dos hablaban de
    números, así que en lectura eligió a ciegas.
    """
    por_nombre = {t["name"]: t["description"] for t in DECLARACIONES_TOOLS}
    assert "BANCO" in por_nombre["check_answer"].upper()
    assert "CUENTAS" in por_nombre["verify_arithmetic"].upper()
    assert "verify_language" in por_nombre["verify_arithmetic"], (
        "verify_arithmetic no manda a la de lenguaje cuando no es una cuenta"
    )
    assert "LECTURA" in por_nombre["verify_language"].upper()


def test_las_descripciones_de_los_tools_no_hablan_en_voseo():
    """Son parte del prompt efectivo, y el modelo imita el registro de sus
    instrucciones: es la lección que costó la sesión del 17/08. Un tutor bogotano
    con tools escritas en argentino termina mezclando."""
    texto = " ".join(t["description"] for t in DECLARACIONES_TOOLS).lower()
    for voseo in ["vos ", "calculás", "tenés", "querés", "usalo", "dale"]:
        assert voseo not in texto, f"voseo en las declaraciones: {voseo}"


def test_escalate_safety_empuja_a_escalar_ante_la_duda():
    tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == "escalate_safety")
    assert "duda" in tool["description"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# La configuración que viaja atada al token
# ─────────────────────────────────────────────────────────────────────────────


def test_la_config_de_gemini_lleva_todo_lo_necesario():
    d = _config().a_dict_gemini()
    assert d["responseModalities"] == ["AUDIO"]
    assert d["systemInstruction"]
    assert d["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"]
    assert d["realtimeInputConfig"]["automaticActivityDetection"]
    assert len(d["tools"][0]["functionDeclarations"]) == len(DECLARACIONES_TOOLS)


def test_pide_transcripcion_de_las_dos_puntas():
    """Sin transcripción no hay Analista, ni Vigilante, ni auditoría del método."""
    d = _config().a_dict_gemini()
    assert "inputAudioTranscription" in d
    assert "outputAudioTranscription" in d


def test_la_transcripcion_de_entrada_fija_idioma_y_sesga_los_numeros():
    """El `{}` vacío dejaba autodetectar: el ruido salía coreano y "dos" salía
    "32", congelando al Analista. La entrada va con idioma fijo y palabras-número."""
    entrada = _config().a_dict_gemini()["inputAudioTranscription"]
    assert entrada["languageCodes"], "sin idioma fijo, autodetecta y falla con ruido"
    assert "dos" in entrada["adaptationPhrases"], "sesga hacia las palabras-número"


def test_el_emisor_falso_no_toca_la_red():
    emisor = EmisorFalso()
    token = emisor.emitir(_config())
    assert token.token.startswith("falso-")
    assert len(emisor.emitidos) == 1


def test_lo_que_se_ata_al_token_incluye_seguridad_y_metodo():
    """EL CANDADO #1: el navegador recibe un token, no una configuración.
    No puede cambiar la persona, el método ni la política de seguridad."""
    emisor = EmisorFalso()
    emisor.emitir(_config())

    atado = emisor.emitidos[0].a_dict_gemini()["systemInstruction"]
    assert "nunca das la respuesta" in atado.lower()
    assert "escalate_safety" in atado


def test_el_bloque_del_modo_pedido_no_vosea():
    """El prompt no se puede contradecir a sí mismo sobre cómo habla.

    `tutor_persona.es.md` veta el voseo argentino, pero el bloque del modo
    Pedido vivía hardcodeado en `voice.py` y quedó en voseo cuando los .md se
    reescribieron a colombiano neutro: el mismo prompt decía "nunca vosees" y
    dos párrafos después voseaba ("Usá eso como material: aplicás la MISMA
    escalera"). El modelo imita el registro de lo que lee, y dos registros en
    una instrucción son dos tutores.

    Se mide el DELTA entre los dos modos, que es exactamente el texto escrito
    en Python. Buscar el voseo en el prompt entero no sirve: la persona lista
    esas mismas formas para vetarlas.
    """
    guiado = construir_instruccion_sistema("Juan, 7 años.", modo="guiado")
    pedido = construir_instruccion_sistema("Juan, 7 años.", modo="pedido")
    solo_pedido = pedido.replace(guiado, "").lower()

    assert solo_pedido.strip(), "el modo pedido dejó de agregar su bloque"
    for forma in ["usá", "aplicás", "tenés", "querés", "mirá", "decile", "cerrá", "dale"]:
        assert forma not in solo_pedido, f"voseo en el bloque del modo pedido: {forma!r}"


def test_el_primer_encuentro_solo_entra_la_primera_vez():
    """El patrón que mantiene el prompt flaco: lo que aplica a veces, entra a
    veces. Un tutor que en la sesión 40 sigue leyendo cómo presentarse gasta
    atención en algo que ya pasó, además de gastar espacio.
    """
    normal = construir_instruccion_sistema("Juan, 7 años.")
    primera = construir_instruccion_sistema("Juan, 7 años.", primer_encuentro=True)

    assert "Hoy se conocen" in primera
    assert "Hoy se conocen" not in normal, "el guion del primer día quedó pegado siempre"
    assert "Yo no te doy las respuestas" in primera, "falta el acuerdo que más se prueba"


def test_el_primer_encuentro_tambien_cabe_bajo_el_techo():
    """El caso especial es el MÁS pesado, así que es el que hay que medir.

    Mirar solo la sesión normal deja crecer el primer encuentro sin que nadie
    lo vea — hasta que un niño nuevo estrena el prompt más gordo del sistema.

    Techo propio (40 KB) y no el de la sesión normal (38 KB), decidido el 18/08
    tras chocar tres veces en una tarde. Este caso carga un bloque entero de más
    por definición, así que medirlo contra el mismo número obligaba a comprimir
    prosa que estaba bien cada vez que se tocaba cualquier otra sección. Los dos
    techos siguen puestos y siguen siendo decisiones; lo que cambió es que ahora
    son dos, porque son dos casos distintos.

    Se dijo acá que adelgazar de verdad —mover doctrina a knowledge/product/—
    era deuda abierta, y que subir un techo no la paga. Se pagó el 20/08: el
    prompt bajó 7,3 KB, este caso quedó en 33.256, y el techo BAJA de 40.000 a
    35.000 en el mismo movimiento.
    """
    texto = construir_instruccion_sistema("Juan, 7 años, 2° grado.", primer_encuentro=True)
    assert len(texto) < 35_000, (
        f"el prompt del primer encuentro llegó a {len(texto)} caracteres"
    )


def test_el_primer_encuentro_no_escribe_el_nombre_a_mano():
    """El nombre vive en `config.NOMBRE_TUTOR` para tener un solo lugar que
    cambiar — por país, o el día que la familia pueda elegirlo. Un ejemplo con
    el nombre escrito en el .md lo convierte en dos lugares, y el segundo es el
    que nadie se acuerda de tocar."""
    from tutor import config as cfg

    guion = cargar_prompt("primer_encuentro")
    assert cfg.NOMBRE_TUTOR not in guion, (
        f"'{cfg.NOMBRE_TUTOR}' quedó escrito a mano en primer_encuentro.es.md"
    )


def test_el_primer_encuentro_no_le_ensena_al_nino_a_desconfiar_de_la_memoria():
    """PASÓ DE VERDAD, `ses_47dfebd9aa43` (20/08).

    Felipe preguntó "¿sabes quién soy?". El tutor contestó que no estaba seguro
    de si ya habían hablado y que *"como soy una inteligencia artificial, a veces
    mi memoria no funciona tan bien"*. Cuatro turnos después lo llamó Felipe, y
    el niño lo cazó: *"¿por qué antes no me dijiste que era Felipe?"*.

    Dos daños en una frase. El chico: le enseñó que puede contradecirse. Y el
    producto: la memoria longitudinal es el criterio #3 de YC, y el tutor la
    estaba desmintiendo con su propia boca. Un niño al que le dicen que a este
    tutor se le olvidan las cosas no le cuenta nada que valga la pena recordar.
    """
    # Espacios normalizados: la frase puede quedar partida por un salto de
    # línea al reajustar el párrafo, y eso es formato, no contenido. Sin esto,
    # comprimir el prompt tumbaba el test por dónde cayó el corte.
    texto = " ".join(cargar_prompt("primer_encuentro").lower().split())
    assert "primera vez que hablamos" in texto, "falta la respuesta directa"
    assert "tu memoria falla" in texto, "falta la prohibición de desmentir su memoria"
    assert "tu familia" in texto, "no debe adivinar si fue la mamá o el papá"


def test_la_voz_del_nino_abre_turno_aunque_hable_bajito():
    """PASÓ DE VERDAD, `ses_c973ffe7b267` (20/08).

    El tutor preguntó cuánto daba 4+4+4+4+4, Felipe contestó "veinte" bajito y
    ese audio se descartó: el turno nunca se abrió. En la transcripción no
    existe. Dos turnos después el niño reclamó *"ya te dije que 20, ¿no me
    escuchaste?"*.

    La configuración lo decía sin darse cuenta: LOW = "un chico que murmura no
    abre turno". Un niño CONTESTANDO murmura.

    Los dos errores no cuestan lo mismo: un disparo falso abre un turno vacío y
    se sigue; perder la respuesta le enseña al niño que no lo escuchan.
    """
    d = deteccion_para_edad(7)
    assert d.sensibilidad_inicio == "START_SENSITIVITY_HIGH", (
        "con LOW se pierde la respuesta del niño que contesta bajito"
    )
    assert d.padding_inicio_ms >= 300, "sin padding se come el arranque de la palabra"


def test_el_playbook_no_deja_declararle_al_nino_que_si_puede():
    """`ses_c973ffe7b267`: Felipe dijo "yo creo que no puedo" y el tutor
    respondió "claro que puedes".

    La Constitución es explícita: la confianza en sí mismo no se declara, se
    construye con logros reales. Decirle "sí puedes" mientras sigue sin poder es
    la versión amable de no ayudarlo — y le enseña que las palabras del tutor no
    describen la realidad.
    """
    playbook = cargar_prompt("socratic_playbook").lower()
    assert "no puedo" in playbook, "falta el caso: dice que ÉL no es capaz"
    assert "no se declara" in playbook, "falta la razón, y sin razón no se sostiene"


def test_el_tutor_sabe_que_tiene_pizarra_y_no_la_niega():
    """PASÓ DE VERDAD, `ses_6a7a36736734` (20/08), con la pizarra ya integrada.

        nino:  "no lo logro imaginar, ¿me lo podrías hacer más visual?"
        tutor: [se lo explica de palabra]
        nino:  "¿pero no podrías tú dibujarlo?"
        tutor: "Mira que no puedo dibujar por ahora."

    Los siete tools estaban en el token —verificado: Google valida `behavior` y
    rechaza un valor inventado con 400—. O sea que el tutor TENÍA el tablero y
    dijo que no. La instrucción hablaba de CUÁNDO usarla y nunca de que la
    tiene, así que al preguntarle por su capacidad contestó desde lo que cree
    ser, no desde lo que puede hacer.

    Negar algo que sí puede hacer es peor que no poder: el niño aprende a no
    pedirlo, y la función queda muerta aunque funcione.
    """
    playbook = cargar_prompt("socratic_playbook").lower()
    assert "tienes una pizarra" in playbook, "falta que sepa que la tiene"
    assert "nunca digas que no puedes dibujar" in playbook, "falta la prohibición"


def test_la_pizarra_le_muestra_al_modelo_como_traducir_lo_que_pide_el_nino():
    """El otro medio hallazgo de esa sesión: el niño pidió "2 canastas con 9
    manzanas" y eso el tablero SÍ lo puede mostrar (`grupos`). El modelo no hizo
    la conexión porque la descripción listaba los tipos en abstracto.

    Un ejemplo concreto por tipo vale más que la lista de tipos. Y va en la
    descripción del tool, que no paga el techo del prompt de sesión.
    """
    tool = next(t for t in DECLARACIONES_TOOLS if t["name"] == "mostrar_en_pizarra")
    d = tool["description"]
    assert "canastas" in d, "falta el ejemplo que traduce lo que pide el niño"
    assert "→" in d, "los ejemplos tienen que mostrar el mapeo, no solo nombrar tipos"


def test_el_tutor_no_ofrece_lo_que_no_puede_dar():
    """PASÓ DE VERDAD, `ses_87aba17c8c6c` (22/08). Juan preguntó por qué vuelan
    los aviones:

        tutor: "¿Te gustaría que viéramos un videíto corto para entenderlo
                mejor? ¡Es súper interesante!"
        nino:  "¿Como así que un videíto, tú me puedes mostrar videos? A ver,
                muéstramela."
        tutor: "Ay, Juan, me temo que no puedo mostrarte videos directamente
                por aquí, ¡es una lástima!"

    Y el niño paró la clase para dictarnos el bug: *"deja el reporte de que me
    ofreciste videos y tú como tutor no puedes dar videos."*

    Es el gemelo exacto de `test_el_tutor_sabe_que_tiene_pizarra_y_no_la_niega`:
    ahí negaba algo que SÍ podía, acá ofrece algo que NO puede. Las dos salen de
    lo mismo — el tutor contestaba desde lo que cree ser y no desde lo que tiene
    en la mano — y las dos se arreglan igual: diciéndole cuáles son sus medios.

    Ofrecer y no dar es peor que no tener: el niño aprende que lo que promete el
    tutor no significa nada, y eso se lo lleva a cuando le dice que acertó.
    """
    persona = cargar_prompt("tutor_persona").lower()

    assert "nunca le ofrezcas lo que este canal no tiene" in persona, "falta la prohibición"
    assert "videos" in persona, "falta nombrar lo que ofreció de verdad"

    # Los medios que SÍ tiene, dichos por su nombre. Sin la lista, "no ofrezcas
    # lo que no tienes" no se puede obedecer: el modelo no sabe dónde está el
    # borde. Son los mismos cuatro de `DECLARACIONES_TOOLS` más la voz.
    for medio in ("pizarra", "camarita", "hoja"):
        assert medio in persona, f"no le decimos que tiene {medio}"


def test_el_tutor_no_promete_gestiones():
    """`ses_eadfa6137a37` (23/08). El niño pidió ver la palabra en letra pegada
    —la pizarra solo sabe letra suelta— y el tutor contestó:

        «Por ahora la pizarra solo me deja mostrarla en letra despegada, pero
         YA ESTOY AVISANDO para que podamos tener las dos opciones juntas.»

    La primera mitad es perfecta: dice la verdad de lo que puede. La segunda es
    inventada — no puede avisarle a nadie, no hay a quién, y el niño se queda
    esperando una respuesta que no va a llegar nunca.

    Es la misma familia que el videíto de YouTube (`ses_87aba17c8c6c`): ofrecer
    lo que no se tiene. Solo que esta vez lo ofrecido no era una cosa, era una
    GESTIÓN, y por eso la regla de los medios no la cubría.
    """
    persona = cargar_prompt("tutor_persona").lower()
    assert "ni prometas" in persona and "gestiones" in persona, "falta la prohibición"
    assert "no puedes avisarle a nadie" in persona, "falta decir por qué no puede"


def test_el_animo_no_se_regala():
    """`ses_445f4c33db41`: «¡vamos que tú puedes!», «yo sé que tú puedes», «¡Tú
    puedes!» — tres veces en cinco minutos, ninguna pegada a un logro.

    La regla existía y decía «"tú puedes" solo vale si viene seguido de algo que
    sí pudo». Redactada así se lee como una condición que el modelo cree cumplir
    con cualquier cosa. Ahora empieza por la prohibición.

    Es la Constitución: la confianza no se declara, se construye con evidencia.
    Un "tú puedes" suelto es la versión amable de no ayudarlo.
    """
    valores = cargar_prompt("valores").lower()
    assert 'nunca dices "tú puedes" a secas' in valores, "la regla dejó de ser tajante"


def test_lo_que_dice_que_ensena_es_lo_que_el_banco_tiene():
    """La misma sección decía **"solo matemáticas"** con el grafo ya en tres
    materias: 13 habilidades de lectura y 11 de escritura cargadas desde el
    22/08. O sea que le prometía DE MENOS a un niño que venía a leer, con el
    material en la mano.

    Prometer de más rompe la confianza; prometer de menos deja una materia
    entera sin usar. Este test ata la frase del prompt a lo que el currículum
    tiene HOY: si mañana entra inglés, se rompe acá y hay que decirlo.
    """
    persona = cargar_prompt("tutor_persona").lower()
    materias = {h.id.split(".")[0] for h in cargar_grafo()}
    esperado = {"mat": "matemáticas", "lec": "lectura", "esc": "escritura"}

    assert materias <= set(esperado), f"materia nueva en el grafo sin nombre acá: {materias}"
    for prefijo in materias:
        assert esperado[prefijo] in persona, (
            f"el grafo tiene {prefijo}.* y el prompt no dice que lo enseña"
        )


def test_ninguna_regla_se_cae_al_adelgazar_el_prompt():
    """EL CONTRAPESO DE LOS DOS TECHOS.

    Los techos empujan a recortar; esto define qué NO se puede perder al
    hacerlo. Sin este test, adelgazar es apostar: se corta prosa, el peso baja,
    los tests siguen verdes y una regla desapareció sin que nadie lo note —
    hasta que el tutor le regala una respuesta a un niño.

    Cada línea es una promesa del producto. Si una falla al recortar, o se
    reescribe la regla en menos palabras, o el recorte se deshace. Lo que no se
    hace es borrarla y seguir.

    Se buscan frases que caben en UN renglón: el texto va envuelto a 80 columnas
    y una frase partida por un salto de línea no matchea aunque esté ahí.
    """
    texto = construir_instruccion_sistema(
        "Juan, 7 años, 2° grado.", modo="pedido", primer_encuentro=True
    ).lower()

    reglas = {
        "no da la respuesta": "nunca das la respuesta",
        "explica lo convencional": "no se descubren pensando",
        "no explica el resultado": "el resultado del ejercicio que están haciendo",
        "la escalera tiene techo": "no hay escalón 5",
        "el 'no puedo' se responde con un logro": "no se declara",
        "sabe que tiene pizarra": "tienes una pizarra",
        "no niega saber dibujar": "nunca digas que no puedes dibujar",
        "la aritmética no la hace él": "la verifica la herramienta, no tú",
        "'cerca' es un dato": 'cerca" es un dato',
        "no cede por insistencia": "no cedas por insistencia",
        "el elogio nombra algo real": "elogio vacío",
        "el nombre no cambia": "nunca te presentas con un nombre distinto",
        "registro colombiano neutro": "español colombiano neutro",
        "veta la jerga callejera": "parcero",
        "no finge ser humano": "nunca finges ser humano",
        "aguanta el enojo sin enfriarse": "estás bravo conmigo",
        "no inventa por qué falló": "no inventes la",
        "no describe una foto que no llegó": "no describas nada",
        "la primera vez no miente sobre lo que sabe": "primera vez",
        "los ejercicios salen del banco": "nunca de tu cabeza",
        "no dice los nombres de los tools": "nunca se dicen en voz alta",
        "el modo pedido es más estricto": "no es hacerle la tarea",
        "la seguridad puede escalar": "escalate_safety",
        "los valores no se predican": "no hay una lección de valores",
        "no ofrece lo que no puede dar": "nunca le ofrezcas lo que este canal no tiene",
        "el elogio nombra qué estuvo bien": "específico y creíble",
        "no se le escapa el usted": "imperativo de usted",
        "no inventa palabras": "palabras que no existen",
        "no cuenta ruidos que no oye": "no oyes ruidos",
    }

    faltan = [nombre for nombre, frase in reglas.items() if frase not in texto]
    assert not faltan, "el prompt adelgazó de más y perdió reglas: " + ", ".join(faltan)


def test_los_prompts_del_tutor_tampoco_vosean():
    """El modelo imita el registro de lo que lee.

    Ya había test para las descripciones de los tools y para el resumen del
    niño, pero no para los .md que forman el prompt — y ahí se coló "podés ser
    juguetón" el 20/08. Una instrucción en voseo es una invitación a que el
    tutor le hable así al niño, que es justo lo que `tutor_persona` prohíbe.
    """
    import re

    voseo = re.compile(
        r"\b(podés|tenés|querés|hacés|sabés|decís|comés|sumás|contás|mirá|fijate|"
        r"pensá|andá|dale|sos)\b",
        re.IGNORECASE,
    )
    for nombre in ("tutor_persona", "socratic_playbook", "valores", "safety_policy"):
        texto = cargar_prompt(nombre)
        # La línea que VETA el voseo nombra las formas: esa no cuenta.
        lineas = [ln for ln in texto.splitlines() if "voseo" not in ln.lower()]
        for ln in lineas:
            if (m := voseo.search(ln)):
                raise AssertionError(f"voseo en {nombre}.es.md: {m.group()!r} — {ln.strip()[:70]}")
