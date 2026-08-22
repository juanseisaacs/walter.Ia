"""El contrato entre lo que el tutor puede PEDIR y lo que el navegador sabe DIBUJAR.

El enum de `mostrar_en_pizarra` vive en `voice.py`; quien lo atiende vive en
`web/src/pizarra/desdeElTutor.ts` y `web/src/pizarra/Pizarra.tsx`. Son dos
lenguajes distintos y no hay nada que los obligue a coincidir: agregar un tipo
al enum y olvidar el handler NO rompe nada visible. El tutor pide el dibujo, el
navegador devuelve `null`, y el niño se queda mirando un tablero vacío mientras
el tutor le habla de algo que no está.

Es el mismo antipatrón que ya mordió dos veces en este repo — algo declarado de
un lado y consumido del otro, sin nadie que compruebe que coinciden:

  · fase 4: `verificable_en_codigo` vivía en el JSON schema y Pydantic lo
    descartaba en silencio.
  · 21/08: cuatro funciones bien escritas y bien testeadas que nadie llamaba.

Este archivo lee los dos lados y los compara. No importa nada del front: lee
los `.ts` como TEXTO, que es lo único que se puede hacer desde Python y es
suficiente. Por eso cada extractor lleva su guarda anti-vacío — ver
`_casos_entre`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tutor.voice import DECLARACIONES_TOOLS

RAIZ = Path(__file__).resolve().parent.parent
DESDE_EL_TUTOR = RAIZ / "web" / "src" / "pizarra" / "desdeElTutor.ts"
PIZARRA = RAIZ / "web" / "src" / "pizarra" / "Pizarra.tsx"
USE_TUTOR = RAIZ / "web" / "src" / "voz" / "useTutor.ts"


# ─────────────────────────────────────────────────────────────────────────────
# Extractores
# ─────────────────────────────────────────────────────────────────────────────


def _enum_de(tool: str, campo: str) -> set[str]:
    """Los valores que el modelo puede mandar en ese campo."""
    declaracion = next(t for t in DECLARACIONES_TOOLS if t["name"] == tool)
    valores = declaracion["parameters"]["properties"][campo].get("enum")
    assert valores, f"{tool}.{campo} dejó de tener enum: este test ya no mide nada"
    return set(valores)


def _texto(ruta: Path) -> str:
    assert ruta.exists(), (
        f"No existe {ruta.relative_to(RAIZ)}. Si el archivo se movió o se renombró, "
        f"actualizá la ruta acá: si no, este test pasa sin comprobar nada."
    )
    return ruta.read_text(encoding="utf-8")


def _casos_entre(texto: str, desde: str, hasta: str | None, donde: str) -> set[str]:
    """Los `case "x":` de UN switch, delimitado por dos marcas del archivo.

    Se acota por función a propósito: `desdeElTutor.ts` tiene dos switches
    distintos, y un tipo que esté en uno y falte en el otro es exactamente el
    bug que buscamos. Sacar los `case` del archivo entero los mezclaría.

    LA GUARDA IMPORTANTE: si el regex no encuentra NINGÚN caso, esto revienta en
    vez de devolver un conjunto vacío. Un conjunto vacío hace que todas las
    comparaciones de abajo pasen felices sin haber mirado nada — que es la
    lección de la fase 8 (`un test que mide lo que no es, pasa igual`). Si
    alguien cambia el `switch` por un mapa de objetos, este test tiene que
    gritar, no aprobar.
    """
    inicio = texto.find(desde)
    assert inicio != -1, f"{donde}: no se encontró «{desde}». El test perdió su ancla."

    fin = texto.find(hasta, inicio) if hasta else len(texto)
    if fin == -1:
        fin = len(texto)

    casos = set(re.findall(r'case\s+"([a-z_]+)"\s*:', texto[inicio:fin]))
    assert casos, (
        f"{donde}: cero `case` encontrados entre «{desde}» y «{hasta}». "
        f"O el switch se reescribió de otra forma, o el regex quedó viejo. "
        f"Este test NO puede pasar sin haber leído nada."
    )
    return casos


# Lo que el tutor puede pedir, según el enum del tool.
TIPOS_DECLARADOS = _enum_de("mostrar_en_pizarra", "tipo")
ANCLAS_DECLARADAS = _enum_de("mostrar_en_pizarra", "senalar") | _enum_de(
    "mostrar_en_pizarra", "tachar"
)


# ─────────────────────────────────────────────────────────────────────────────
# El contrato de los tipos de escena
# ─────────────────────────────────────────────────────────────────────────────

TIPOS_FUERA_DE_LA_PIZARRA = {
    # `limpiar` no arma ninguna escena: borra el tablero. `useTutor.ts` lo
    # atiende ANTES de llamar a `aCuadro`, y por eso no tiene `case` acá. La
    # excepción va escrita y con test propio (ver abajo), no perdonada en
    # silencio.
    "limpiar",
}


def test_cada_tipo_que_el_tutor_puede_pedir_lo_sabe_armar_el_navegador():
    """El tutor no puede pedir un dibujo que nadie sabe hacer.

    Si esto falla: agregaste un tipo al enum de `mostrar_en_pizarra` y te
    faltó el `case` en `aEscena()`. El tutor lo va a pedir, `aCuadro` va a
    devolver `null` y el niño va a ver el tablero vacío.
    """
    arma = _casos_entre(
        _texto(DESDE_EL_TUTOR),
        "function aEscena",
        "export function describir",
        "desdeElTutor.aEscena",
    )
    faltan = TIPOS_DECLARADOS - TIPOS_FUERA_DE_LA_PIZARRA - arma
    assert not faltan, (
        f"El tutor puede pedir {sorted(faltan)} y `aEscena()` no sabe armarlo. "
        f"O le agregás el `case` en desdeElTutor.ts, o lo sacás del enum de voice.py."
    )


def test_el_navegador_no_arma_escenas_que_el_tutor_no_puede_pedir():
    """La dirección inversa: código que nadie puede alcanzar.

    Un `case` sin su valor en el enum es código muerto — se lee igual que
    código vivo, tiene su lógica, y nunca corre. Es la lección del 21/08.
    """
    arma = _casos_entre(
        _texto(DESDE_EL_TUTOR),
        "function aEscena",
        "export function describir",
        "desdeElTutor.aEscena",
    )
    huerfanos = arma - TIPOS_DECLARADOS
    assert not huerfanos, (
        f"`aEscena()` sabe armar {sorted(huerfanos)} y el tutor no lo puede pedir: "
        f"falta en el enum de `mostrar_en_pizarra`, o sobra el `case`."
    )


def test_el_tutor_se_entera_de_todo_lo_que_quedo_en_pantalla():
    """Todo lo que se arma tiene que poder describirse.

    `describir()` es lo que el tool le devuelve al tutor para que sepa QUÉ hay
    en el tablero. Una escena que se arma y no se describe deja al tutor
    hablando de un dibujo que no puede ver — y ahí se lo inventa. Es la lección
    de visión del 21/08: «un tool que cambia lo que el niño ve le devuelve al
    tutor QUÉ quedó en pantalla, no un ok».
    """
    texto = _texto(DESDE_EL_TUTOR)
    arma = _casos_entre(texto, "function aEscena", "export function describir", "aEscena")
    describe = _casos_entre(texto, "export function describir", None, "describir")

    sin_describir = arma - describe
    assert not sin_describir, (
        f"`aEscena()` arma {sorted(sin_describir)} y `describir()` no lo cuenta. "
        f"El tutor va a tener eso en pantalla sin saber qué es."
    )


def test_limpiar_se_atiende_antes_de_llegar_a_la_pizarra():
    """La excepción declarada, comprobada donde de verdad vive.

    Si esto falla, `limpiar` dejó de tratarse en `useTutor.ts` y tampoco tiene
    `case` en `aEscena` — o sea que el tutor pide limpiar el tablero y no pasa
    nada. Ya pasó una vez: un niño preguntó por qué seguían las macetas en
    pantalla cuando hacía rato cantaban una canción.
    """
    assert 'tipo === "limpiar"' in _texto(USE_TUTOR), (
        "`limpiar` está en el enum, no tiene `case` en aEscena() y ya no se "
        "atiende en useTutor.ts. El tablero dejó de poder borrarse."
    )


# ─────────────────────────────────────────────────────────────────────────────
# El contrato de las anclas (señalar y tachar)
# ─────────────────────────────────────────────────────────────────────────────

ANCLAS_SIN_USO_CONOCIDAS: set[str] = set()
"""Anclas que la pizarra sabe ubicar y el tutor no puede pedir.

Estaba en `{"primero", "segundo"}` — las dos filas de la cuenta, que la pizarra
dibujaba desde siempre y nadie podía invocar. Se cerraron el 22/08 agregándolas
al enum de `senalar`, que era el arreglo natural: el código servía, lo que
faltaba era dárselo al tutor.

Queda en vacío a propósito. Que vuelva a llenarse significa que alguien agregó
una posición a la pizarra y se olvidó del otro lado."""


def test_cada_ancla_que_el_tutor_puede_senalar_tiene_lugar_en_pantalla():
    """Señalar algo que la pizarra no sabe ubicar deja el círculo en el vacío.

    `caja()` cae a un rectángulo que cubre el tablero entero cuando no reconoce
    el ancla: no revienta, pero el tutor dice «mirá las decenas» y se rodea todo.
    """
    ubica = _casos_entre(_texto(PIZARRA), "function caja(", "\n}", "Pizarra.caja")
    faltan = ANCLAS_DECLARADAS - ubica
    assert not faltan, (
        f"El tutor puede señalar {sorted(faltan)} y `caja()` no sabe dónde está. "
        f"El marcador va a rodear el tablero entero."
    )


def test_las_anclas_que_el_tutor_no_puede_pedir_siguen_siendo_las_conocidas():
    """Que el código inalcanzable no crezca en silencio.

    No falla por las dos que ya sabemos que están (van anotadas arriba con su
    motivo). Falla si aparece una tercera — que es cuando alguien agregó una
    posición a la pizarra y se olvidó de dársela al tutor.
    """
    ubica = _casos_entre(_texto(PIZARRA), "function caja(", "\n}", "Pizarra.caja")
    inalcanzables = ubica - ANCLAS_DECLARADAS
    nuevas = inalcanzables - ANCLAS_SIN_USO_CONOCIDAS
    assert not nuevas, (
        f"`caja()` sabe ubicar {sorted(nuevas)} y el tutor no lo puede pedir. "
        f"Agregalo al enum de `senalar`/`tachar` en voice.py, o sacá el `case`."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Que este archivo no pueda pasar en vacío
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "conjunto,nombre",
    [
        (TIPOS_DECLARADOS, "tipos de mostrar_en_pizarra"),
        (ANCLAS_DECLARADAS, "anclas de señalar/tachar"),
    ],
)
def test_los_enums_no_llegaron_vacios(conjunto: set[str], nombre: str):
    """Sin esto, un enum vacío haría pasar todas las comparaciones de arriba."""
    assert len(conjunto) >= 4, f"{nombre}: solo {len(conjunto)}. ¿Se vació el enum?"
