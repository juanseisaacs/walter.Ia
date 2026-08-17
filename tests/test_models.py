"""Smoke tests de los contratos de datos.

No prueban lógica (todavía no hay). Prueban que las formas definidas en
models.py sean coherentes y que las validaciones disparen donde deben.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from tutor.models import (
    Alineacion,
    AnalisisSesion,
    AuditoriaCumplimiento,
    EstadoSesion,
    Habilidad,
    Materia,
    ModoSesion,
    Nino,
    NivelSeguridad,
    Observacion,
    RegistroDominio,
    Sesion,
    TextoLocalizado,
    TipoObservacion,
)


def test_habilidad_con_doble_anclaje():
    """Criterio #1 de YC: el grafo debe poder citar contra qué está alineado."""
    h = Habilidad(
        id="mat.suma.con_reagrupacion",
        nombre=TextoLocalizado(es="Suma llevando"),
        descripcion=TextoLocalizado(es="Sumar dos numeros de dos cifras reagrupando"),
        materia=Materia.MATEMATICAS,
        grado_sugerido=2,
        prerequisitos=["mat.suma.sin_reagrupacion", "mat.valor_posicional.decenas"],
        alineacion=Alineacion(
            dba_colombia="DBA Matematicas 2 - #3",
            core_knowledge="Grade 2 Mathematics - Addition with regrouping",
        ),
    )
    assert len(h.prerequisitos) == 2
    assert h.alineacion.dba_colombia is not None
    assert h.nombre.en is None, "el campo en existe pero queda vacio hasta la fase de ingles"


def test_nino_arranca_con_las_dos_mitades():
    """Ficha academica (codigo) y ficha personal (analista) — ARCHITECTURE.md 10."""
    n = Nino(id="n1", nombre="Juan", edad=7, grado=2)
    assert n.dominio == {}
    assert n.perfil.intereses == []
    assert n.perfil.madurez_vinculo == 0, "en la sesion 1 el tutor no conoce al nino"


def test_grado_fuera_de_rango_falla():
    with pytest.raises(ValidationError):
        Nino(id="n1", nombre="Juan", edad=7, grado=9)


def test_nivel_de_dominio_acotado():
    """El nivel es 0..1 — el decaimiento nunca puede sacarlo de ahi."""
    RegistroDominio(habilidad_id="mat.suma.con_reagrupacion", nivel=0.6)
    with pytest.raises(ValidationError):
        RegistroDominio(habilidad_id="mat.suma.con_reagrupacion", nivel=1.4)


def test_sesion_arranca_sin_analizar():
    """`analizada` es la llave de idempotencia: evita doble conteo de dominio."""
    s = Sesion(id="s1", nino_id="n1", modo=ModoSesion.GUIADO, inicio=datetime.now())
    assert s.analizada is False
    assert s.estado == EstadoSesion.ACTIVA


def test_modo_pedido_existe():
    """El nino puede traer su propia agenda (tarea, duda) — ARCHITECTURE.md 6."""
    s = Sesion(id="s2", nino_id="n1", modo=ModoSesion.PEDIDO, inicio=datetime.now())
    assert s.modo == ModoSesion.PEDIDO


def test_analisis_trae_las_dos_preguntas():
    """Una llamada, dos preguntas: senales del NINO + auditoria del TUTOR."""
    a = AnalisisSesion(
        sesion_id="s1",
        observaciones=[
            Observacion(
                habilidad_id="mat.suma.con_reagrupacion",
                tipo=TipoObservacion.PISTA_NECESARIA,
                evidencia="no me sale, ayudame",
            )
        ],
        cumplimiento=AuditoriaCumplimiento(
            regalo_la_respuesta=False,
            respeto_escalera_pistas=True,
            detecto_frustracion=True,
        ),
    )
    assert a.cumplimiento.regalo_la_respuesta is False, "el diferencial del producto"
    assert a.observaciones[0].evidencia, "toda observacion se respalda con cita textual"


def test_niveles_de_seguridad_escalan():
    assert NivelSeguridad.OK != NivelSeguridad.CRITICO
    assert len(list(NivelSeguridad)) == 4
