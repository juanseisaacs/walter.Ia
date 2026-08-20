"""Tests del cargador y validador del grafo.

Lo importante acá no es que cargue: es que RECHACE grafos rotos. Un ciclo o un
prerrequisito colgado que pasa desapercibido se convierte, meses después, en un
niño trabado sin explicación.
"""

import json

import pytest

from tutor.config import CURRICULUM
from tutor.curriculum import ErrorGrafo, GrafoHabilidades, cargar_grafo
from tutor.models import Alineacion, Habilidad, Materia, TextoLocalizado


def _hab(hid: str, prereqs: list[str] | None = None, grado: int = 2) -> Habilidad:
    """Habilidad mínima para armar grafos de prueba."""
    return Habilidad(
        id=hid,
        nombre=TextoLocalizado(es=hid),
        descripcion=TextoLocalizado(es="prueba"),
        materia=Materia.MATEMATICAS,
        grado_sugerido=grado,
        prerequisitos=prereqs or [],
    )


# ─────────────────────────────────────────────────────────────────────────────
# El validador rechaza grafos rotos
# ─────────────────────────────────────────────────────────────────────────────


def test_rechaza_ciclo_directo():
    """A necesita B, B necesita A → ningún niño podría empezar nunca."""
    with pytest.raises(ErrorGrafo, match="Ciclo"):
        GrafoHabilidades([_hab("mat.a", ["mat.b"]), _hab("mat.b", ["mat.a"])])


def test_rechaza_ciclo_largo():
    """Los ciclos indirectos son los peligrosos: nadie los ve leyendo el YAML."""
    with pytest.raises(ErrorGrafo, match="Ciclo"):
        GrafoHabilidades(
            [
                _hab("mat.a", ["mat.c"]),
                _hab("mat.b", ["mat.a"]),
                _hab("mat.c", ["mat.b"]),
            ]
        )


def test_el_error_de_ciclo_dice_cual_es():
    """Un mensaje que no señala el problema obliga a buscarlo a mano."""
    with pytest.raises(ErrorGrafo) as exc:
        GrafoHabilidades([_hab("mat.a", ["mat.b"]), _hab("mat.b", ["mat.a"])])
    assert "mat.a" in str(exc.value) and "mat.b" in str(exc.value)


def test_rechaza_prerequisito_inexistente():
    with pytest.raises(ErrorGrafo, match="no existe"):
        GrafoHabilidades([_hab("mat.a", ["mat.fantasma"])])


def test_rechaza_id_duplicado():
    with pytest.raises(ErrorGrafo, match="duplicado"):
        GrafoHabilidades([_hab("mat.a"), _hab("mat.a")])


def test_acepta_grafo_valido_con_ramas():
    """Dos caminos que salen de un nodo y vuelven a juntarse: eso es un DAG."""
    g = GrafoHabilidades(
        [
            _hab("mat.base"),
            _hab("mat.izq", ["mat.base"]),
            _hab("mat.der", ["mat.base"]),
            _hab("mat.union", ["mat.izq", "mat.der"]),
        ]
    )
    assert len(g) == 4


# ─────────────────────────────────────────────────────────────────────────────
# Navegación
# ─────────────────────────────────────────────────────────────────────────────


def test_navega_en_las_dos_direcciones():
    g = GrafoHabilidades(
        [_hab("mat.base"), _hab("mat.medio", ["mat.base"]), _hab("mat.alto", ["mat.medio"])]
    )
    assert [h.id for h in g.prerequisitos_de("mat.medio")] == ["mat.base"]
    assert [h.id for h in g.desbloqueadas_por("mat.base")] == ["mat.medio"]


def test_raices_son_los_puntos_de_entrada():
    """Por acá arranca un niño nuevo: nodos sin prerrequisitos."""
    g = GrafoHabilidades([_hab("mat.base"), _hab("mat.otro"), _hab("mat.medio", ["mat.base"])])
    assert {h.id for h in g.raices()} == {"mat.base", "mat.otro"}


def test_habilidad_inexistente_falla_claro():
    g = GrafoHabilidades([_hab("mat.a")])
    assert g.existe("mat.a")
    assert not g.existe("mat.z")
    with pytest.raises(ErrorGrafo, match="No existe"):
        g.habilidad("mat.z")


# ─────────────────────────────────────────────────────────────────────────────
# El currículum real
# ─────────────────────────────────────────────────────────────────────────────


def test_el_curriculum_del_repo_es_valido():
    """Si esto falla, alguien rompió knowledge/curriculum/ y no debe llegar a main."""
    g = cargar_grafo()
    assert len(g) > 0


def test_curriculum_real_tiene_al_menos_una_raiz():
    """Sin raíz, un niño nuevo no tiene por dónde empezar."""
    assert cargar_grafo().raices()


def test_curriculum_real_cita_estandares():
    """Criterio #1 de YC: hay que poder responder '¿contra qué está alineado?'."""
    g = cargar_grafo()
    sin_anclaje = [
        h.id for h in g if not (h.alineacion.dba_colombia or h.alineacion.core_knowledge)
    ]
    assert not sin_anclaje, f"habilidades sin alineación curricular: {sin_anclaje}"


def test_cadena_de_suma_esta_bien_ordenada():
    """Suma llevando no puede venir antes que suma sin llevar."""
    g = cargar_grafo()
    prereqs = {h.id for h in g.prerequisitos_de("mat.suma.con_reagrupacion")}
    assert "mat.suma.sin_reagrupacion" in prereqs


def test_filtros_por_materia_y_grado():
    g = cargar_grafo()
    assert g.por_materia(Materia.MATEMATICAS)
    assert g.por_grado(2)


def test_schema_json_y_el_modelo_pydantic_no_se_desincronizan():
    """Hay DOS definiciones del mismo nodo (schema.json y models.Habilidad) y
    pueden separarse sin que nada avise.

    Pasó de verdad: `verificable_en_codigo` vivió en schema.json desde la fase 0
    y no estaba en el modelo. El YAML lo declaraba, jsonschema lo validaba, y
    Pydantic lo tiraba en silencio.
    """
    esquema = json.loads((CURRICULUM / "schema.json").read_text(encoding="utf-8"))
    del_esquema = set(esquema["properties"])
    del_modelo = set(Habilidad.model_fields)

    assert not (del_esquema - del_modelo), "campos en schema.json que el modelo ignora"
    assert not (del_modelo - del_esquema), "campos del modelo que el schema no valida"

    # `alineacion` es un objeto anidado, y la comparación de arriba no lo mira:
    # se podía agregar un anclaje al schema y que Pydantic lo tirara en silencio
    # —exactamente el fallo de `verificable_en_codigo`, un nivel más abajo—.
    # Se descubrió al agregar `ebc_colombia`: el test pasaba en verde igual.
    anclajes_esquema = set(esquema["properties"]["alineacion"]["properties"])
    anclajes_modelo = set(Alineacion.model_fields)
    assert anclajes_esquema == anclajes_modelo, (
        "los anclajes de `alineacion` se desincronizaron entre schema.json y models.Alineacion"
    )


def test_el_curriculum_declara_que_es_verificable_en_codigo():
    """Matemática se verifica sin modelo. Si un nodo no lo declara,
    check_answer devolvería REQUIERE_JUICIO y perderíamos el determinismo."""
    g = cargar_grafo()
    sin_declarar = [
        h.id for h in g.por_materia(Materia.MATEMATICAS) if not h.verificable_en_codigo
    ]
    assert not sin_declarar, f"habilidades de matemática sin verificación en código: {sin_declarar}"


def test_el_schema_deja_escribir_cabeza_de_pista_por_encima_de_5():
    """SIN TECHO también significa poder ESCRIBIR el nodo.

    `ARCHITECTURE.md` §12: el grafo tiene que tener siempre cabeza de pista por
    encima del grado del niño, porque uno que termina en 5° le pone techo real a
    un chico veloz de 5°. Hasta el 18/08 `grado_sugerido` topaba en 5 en el
    schema Y en Pydantic: el planificador no filtraba por grado, pero el nodo de
    6° era inválido y no se podía crear. El techo estaba un paso antes de donde
    lo buscábamos.
    """
    adelantada = Habilidad(
        id="mat.algebra.ecuaciones_simples",
        nombre=TextoLocalizado(es="Ecuaciones simples"),
        descripcion=TextoLocalizado(es="Despejar una incógnita"),
        materia=Materia.MATEMATICAS,
        grado_sugerido=8,
    )
    assert adelantada.grado_sugerido == 8

    esquema = json.loads((CURRICULUM / "schema.json").read_text(encoding="utf-8"))
    assert esquema["properties"]["grado_sugerido"]["maximum"] > 5, (
        "el schema volvió a impedir la cabeza de pista"
    )
