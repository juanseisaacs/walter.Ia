"""Tests del cargador y validador del grafo.

Lo importante acá no es que cargue: es que RECHACE grafos rotos. Un ciclo o un
prerrequisito colgado que pasa desapercibido se convierte, meses después, en un
niño trabado sin explicación.
"""

import pytest

from tutor.curriculum import ErrorGrafo, GrafoHabilidades, cargar_grafo
from tutor.models import Habilidad, Materia, TextoLocalizado


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
