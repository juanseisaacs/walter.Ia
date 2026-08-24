"""El contrato de VERSIÓN entre el backend y la pestaña del niño.

El backend define lo que el tutor PUEDE pedir (las declaraciones de tools viajan
atadas al token) y el navegador define lo que SABE hacer con eso. Son dos
programas distintos, en dos lenguajes distintos, y **el segundo puede llevar
horas abierto sin enterarse de que el primero cambió**.

Pasó el 23/08 en `ses_4ed4e930e60f`, y el log del servidor lo muestra sin lugar
a dudas: `POST /api/sesiones` llegó ANTES del primer `GET /`. O sea que la
pestaña no se cargó de ese servidor — estaba abierta desde antes, con el
JavaScript anterior vivo en memoria. Mientras tanto el backend, recién
reiniciado, le decía al modelo que podía pedir `cantidades` para dibujar sumas.

    tutor: «no pude ponerte los pollitos en la pizarra ahora mismo»
    nino:  «Muéstrame, en el tablero, muéstrame.»
    tutor: «como que el tablero no me quiere funcionar hoy»

No falló la pizarra: hablaron dos versiones distintas, con el niño en el medio.

Este archivo comprueba que las dos puntas del arreglo siguen conectadas. Cada
una sola es inútil: un backend que anuncia su build y un front que no lo mira, o
un front que mira una clave que el backend dejó de mandar, fallan **en silencio**
— que es exactamente como falló la primera vez.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API_TS = RAIZ / "web" / "src" / "api.ts"
USE_TUTOR = RAIZ / "web" / "src" / "voz" / "useTutor.ts"


def _texto(ruta: Path) -> str:
    assert ruta.exists(), (
        f"No existe {ruta.relative_to(RAIZ)}. Si el archivo se movió, actualizá "
        f"la ruta acá: si no, este test pasa sin comprobar nada."
    )
    return ruta.read_text(encoding="utf-8")


def test_el_navegador_sabe_que_version_es_el_mismo():
    """El front tiene que poder decir con qué build está corriendo.

    Sale de `import.meta.url`, que en producción trae el nombre con hash que le
    puso Vite. Es un número de versión que nadie tiene que acordarse de subir:
    cambia exactamente cuando cambia el código.
    """
    ts = _texto(API_TS)
    assert "import.meta.url" in ts, "el front no tiene forma de saber qué versión es"
    assert "MI_BUILD" in ts


def test_el_navegador_compara_con_el_backend_y_se_recarga():
    ts = _texto(API_TS)
    assert "/salud" in ts, "el chequeo no consulta al backend"
    assert ".build" in ts, "no lee la versión que el backend anuncia"
    assert "location.reload()" in ts, "detecta que está viejo y no hace nada al respecto"


def test_el_chequeo_corre_ANTES_de_abrir_la_sesion():
    """El orden es la mitad del arreglo.

    Recargar con la sesión ya abierta deja una sesión huérfana contando contra
    el cupo diario del niño, y —peor— el niño ya oyó al tutor saludar. El
    chequeo va antes de `abrirSesion`, cuando todavía no hay nada que perder.
    """
    ts = _texto(USE_TUTOR)
    assert "recargarSiEstoyViejo" in ts, "nadie llama al chequeo"
    assert ts.index("recargarSiEstoyViejo()") < ts.index("api.abrirSesion"), (
        "el chequeo de versión quedó DESPUÉS de abrir la sesión"
    )


def test_el_chequeo_no_puede_entrar_en_bucle():
    """Si tras recargar seguimos viejos, el navegador está sirviendo su caché y
    recargar otra vez no arregla nada: sería un niño mirando una pantalla que
    parpadea para siempre. Se intenta UNA vez y después se dice."""
    ts = _texto(API_TS)
    assert "sessionStorage" in ts, "sin marca, una recarga que no arregla se repite sin fin"


def test_el_microfono_se_calla_mientras_el_tutor_habla():
    """LA CAUSA DE QUE EL TUTOR SE CORTARA A MITAD DE PALABRA.

    Medido con `python -m scripts.medir_fluidez` sobre las 8 transcripciones del
    23/08: **20 de 99 turnos del tutor quedaron partidos** —«¡Ah, ya lo veo!
    Mira,», «está en la pizarrita blanca justo»—. RBH lo dijo dentro de la
    sesión: «se corta y no terminas de hablar y te demoras un poco al regresar».

    El micrófono mandaba audio SIEMPRE, también mientras el tutor sonaba. El VAD
    del servidor corre con `START_SENSITIVITY_HIGH` —puesta a propósito para que
    el niño que habla bajito abra turno— y con ese oído el eco del propio tutor
    cuenta como "el niño empezó a hablar": el servidor le cortaba la generación.
    Por eso la frase queda partida también en la transcripción.

    El arreglo NO fue bajar la sensibilidad (eso devuelve el bug de Felipe: sus
    respuestas se perdían). Fue dejar de mandarle al servidor el eco del tutor.

    Este test mira el orden, que es lo único que importa: el `return` que retiene
    tiene que estar ANTES del `sendRealtimeInput`. Si alguien mueve el envío
    arriba, el bug vuelve entero y en silencio.
    """
    ts = _texto(USE_TUTOR)
    inicio = ts.index("MIENTRAS EL TUTOR HABLA, EL AUDIO NO SALE")
    envio = ts.index("sendRealtimeInput", inicio)
    retencion = ts.index("if (tutorSonando) {", inicio)
    assert retencion < envio, "el audio vuelve a salir mientras el tutor habla"
    assert "retenidos.push(muestras)" in ts, "sin buffer, interrumpir cuesta la primera sílaba"


def test_lo_retenido_solo_sale_si_hubo_interrupcion_de_verdad():
    """Al terminar su turno, esos bloques son el ECO del tutor. Mandarlos le
    abriría al niño un turno sobre algo que nadie dijo."""
    ts = _texto(USE_TUTOR)
    assert "interrumpioDeVerdad" in ts
    assert "if (!interrumpioDeVerdad) aSoltar.length = 0;" in ts
