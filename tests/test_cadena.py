"""La cadena de veredictos.

Lo que se prueba acá no es que la cadena se escriba: es que **detecte**. Una
cadena de hashes que no se verifica es decoración cara — sirve exactamente para
lo mismo que no tenerla, con la diferencia de que da confianza.

Por eso casi todos los tests de abajo rompen algo a propósito.
"""

from __future__ import annotations

import json

import pytest

from tutor.cadena import (
    GENESIS,
    Eslabon,
    Rotura,
    huella_de,
    leer_cadena,
    sembrar,
    ultimo_hash,
    verificar,
)
from tutor.models import AuditoriaCumplimiento
from tutor.storage import RepositorioSQLite


def _cumplio(regalo: bool = False) -> AuditoriaCumplimiento:
    return AuditoriaCumplimiento(
        regalo_la_respuesta=regalo,
        respeto_escalera_pistas=True,
        detecto_frustracion=True,
    )


@pytest.fixture
def repo(tmp_path) -> RepositorioSQLite:
    return RepositorioSQLite(tmp_path / "t.db", tmp_path)


def _verificar(repo: RepositorioSQLite):
    return verificar(repo.ruta_cadena, repo.ruta_auditorias)


# ─────────────────────────────────────────────────────────────────────────────
# Que se escriba
# ─────────────────────────────────────────────────────────────────────────────


def test_cada_veredicto_queda_encadenado_al_anterior(repo):
    for i in range(3):
        repo.guardar_auditoria(f"ses_{i}", _cumplio())

    eslabones = leer_cadena(repo.ruta_cadena)
    assert [e.seq for e in eslabones] == [1, 2, 3]
    assert eslabones[0].prev_hash == GENESIS
    assert eslabones[1].prev_hash == eslabones[0].hash
    assert eslabones[2].prev_hash == eslabones[1].hash
    assert _verificar(repo).integra


def test_la_cadena_no_reemplaza_al_veredicto_lo_certifica(repo):
    """El panel del papá sigue leyendo el JSON de siempre."""
    repo.guardar_auditoria("ses_1", _cumplio(regalo=True))
    guardada = repo.obtener_auditoria("ses_1")
    assert guardada is not None and guardada.regalo_la_respuesta is True


def test_una_cadena_vacia_es_integra_no_rota(repo):
    """Un proyecto sin auditorías todavía no tiene nada que ocultar."""
    v = _verificar(repo)
    assert v.integra and v.eslabones == 0
    assert "vacía" in v.resumen()


# ─────────────────────────────────────────────────────────────────────────────
# Que detecte
# ─────────────────────────────────────────────────────────────────────────────


def test_detecta_que_alguien_maquillo_un_veredicto(repo):
    """EL caso que justifica todo esto.

    Alguien con acceso al disco cambia un `regalo_la_respuesta: true` por
    `false` y el porcentaje del panel mejora solo. Sin cadena, indetectable.
    """
    repo.guardar_auditoria("ses_1", _cumplio(regalo=True))
    repo.guardar_auditoria("ses_2", _cumplio())
    assert _verificar(repo).integra, "arranca sana"

    archivo = repo.ruta_auditorias / "ses_1.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["regalo_la_respuesta"] = False
    archivo.write_text(json.dumps(datos, indent=2), encoding="utf-8")

    v = _verificar(repo)
    assert not v.integra
    assert [h.rotura for h in v.hallazgos] == [Rotura.VEREDICTO_ALTERADO]
    assert v.hallazgos[0].sesion_id == "ses_1"


def test_detecta_que_alguien_borro_un_veredicto_incomodo(repo):
    repo.guardar_auditoria("ses_1", _cumplio(regalo=True))
    (repo.ruta_auditorias / "ses_1.json").unlink()

    v = _verificar(repo)
    assert [h.rotura for h in v.hallazgos] == [Rotura.VEREDICTO_AUSENTE]


def test_detecta_que_arrancaron_un_eslabon_del_medio(repo):
    """Borrar la línea de la cadena Y el archivo: sin encadenamiento, limpio."""
    for i in range(4):
        repo.guardar_auditoria(f"ses_{i}", _cumplio())

    lineas = repo.ruta_cadena.read_text(encoding="utf-8").splitlines()
    del lineas[1]
    repo.ruta_cadena.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (repo.ruta_auditorias / "ses_1.json").unlink()

    v = _verificar(repo)
    roturas = {h.rotura for h in v.hallazgos}
    assert Rotura.NO_ENCADENA in roturas, "el hueco tiene que romper la cadena"
    assert Rotura.SEQ_ROTA in roturas, "y la numeración tiene que saltar"


def test_detecta_que_editaron_la_propia_cadena(repo):
    """Quien maquilla el veredicto puede intentar arreglar también su huella."""
    repo.guardar_auditoria("ses_1", _cumplio(regalo=True))

    eslabon = leer_cadena(repo.ruta_cadena)[0]
    falso = eslabon.model_copy(update={"huella": huella_de("otra cosa")})
    repo.ruta_cadena.write_text(falso.model_dump_json() + "\n", encoding="utf-8")

    v = _verificar(repo)
    roturas = {h.rotura for h in v.hallazgos}
    assert Rotura.HASH_ALTERADO in roturas, "el hash del eslabón ya no cuadra"
    assert Rotura.VEREDICTO_ALTERADO in roturas, "y tampoco cuadra con el archivo"


def test_detecta_un_eslabon_metido_al_final(repo):
    """Inventar una sesión impecable que nunca ocurrió."""
    repo.guardar_auditoria("ses_1", _cumplio())
    inventado = Eslabon.forjar(seq=2, sesion_id="ses_falsa", contenido="{}", anterior="cualquiera")
    with repo.ruta_cadena.open("a", encoding="utf-8") as f:
        f.write(inventado.model_dump_json() + "\n")

    v = _verificar(repo)
    assert Rotura.NO_ENCADENA in {h.rotura for h in v.hallazgos}


def test_reporta_todas_las_roturas_no_solo_la_primera(repo):
    """Quien audita necesita el alcance de lo que se tocó, no dónde empezó."""
    for i in range(4):
        repo.guardar_auditoria(f"ses_{i}", _cumplio())
    for i in (0, 2):
        (repo.ruta_auditorias / f"ses_{i}.json").write_text("{}", encoding="utf-8")

    v = _verificar(repo)
    assert len(v.hallazgos) == 2
    assert {h.sesion_id for h in v.hallazgos} == {"ses_0", "ses_2"}


# ─────────────────────────────────────────────────────────────────────────────
# Sembrar lo que ya existía
# ─────────────────────────────────────────────────────────────────────────────


def test_sembrar_ancla_las_auditorias_viejas(repo, tmp_path):
    """41 auditorías existían antes de que hubiera cadena."""
    for i in range(3):
        (repo.ruta_auditorias / f"vieja_{i}.json").write_text(
            _cumplio().model_dump_json(indent=2), encoding="utf-8"
        )

    anclados = sembrar(repo.ruta_cadena, repo.ruta_auditorias, ["vieja_0", "vieja_1", "vieja_2"])

    assert anclados == 3
    assert _verificar(repo).integra


def test_sembrar_sobre_una_cadena_viva_se_niega(repo):
    """Sembrar reescribe desde cero: sobre una cadena en uso sería borrarla."""
    repo.guardar_auditoria("ses_1", _cumplio())
    with pytest.raises(ValueError, match="ya tiene eslabones"):
        sembrar(repo.ruta_cadena, repo.ruta_auditorias, ["ses_1"])


def test_las_auditorias_fuera_de_la_cadena_se_reportan_sin_romperla(repo):
    """Las viejas no la rompen, pero no las respalda nadie y hay que verlo."""
    repo.guardar_auditoria("ses_1", _cumplio())
    (repo.ruta_auditorias / "huerfana.json").write_text("{}", encoding="utf-8")

    v = _verificar(repo)
    assert v.integra, "una auditoría sin anotar no invalida la cadena"
    assert v.sin_anotar == ["huerfana"]
    assert "fuera de la cadena" in v.resumen()


def test_el_ultimo_hash_es_el_extremo_publicable(repo):
    assert ultimo_hash(repo.ruta_cadena) is None
    repo.guardar_auditoria("ses_1", _cumplio())
    repo.guardar_auditoria("ses_2", _cumplio())
    assert ultimo_hash(repo.ruta_cadena) == leer_cadena(repo.ruta_cadena)[-1].hash


def test_el_archivo_de_la_cadena_no_se_confunde_con_una_auditoria(repo):
    """`cadena.jsonl` vive en la misma carpeta que los veredictos."""
    repo.guardar_auditoria("ses_1", _cumplio())
    assert "cadena" not in _verificar(repo).sin_anotar


# ─────────────────────────────────────────────────────────────────────────────
# El comando
# ─────────────────────────────────────────────────────────────────────────────
# Una cadena que nadie verifica es decoración cara. Estos tests entran por
# `main()` — por donde entra quien audita — y no por las funciones sueltas.


def _preparar(tmp_path, monkeypatch, *, sesiones: int = 2):
    """Un repo con auditorías y `config` apuntando ahí."""
    from tutor import config as cfg

    monkeypatch.setattr(cfg, "DB", tmp_path / "t.db")
    monkeypatch.setattr(cfg, "DATOS", tmp_path)
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    for i in range(sesiones):
        repo.guardar_auditoria(f"ses_{i}", _cumplio())
    return repo


def test_el_comando_aprueba_una_cadena_intacta(tmp_path, monkeypatch, capsys):
    import sys as _sys

    import scripts.verificar_cadena as script

    _preparar(tmp_path, monkeypatch)
    monkeypatch.setattr(_sys, "argv", ["verificar_cadena"])

    assert script.main() == 0
    assert "ÍNTEGRA" in capsys.readouterr().out


def test_el_comando_falla_con_un_veredicto_maquillado(tmp_path, monkeypatch, capsys):
    """Si esto pasara en verde, la cadena no serviría para nada."""
    import sys as _sys

    import scripts.verificar_cadena as script

    repo = _preparar(tmp_path, monkeypatch)
    archivo = repo.ruta_auditorias / "ses_0.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["regalo_la_respuesta"] = True
    archivo.write_text(json.dumps(datos, indent=2), encoding="utf-8")

    monkeypatch.setattr(_sys, "argv", ["verificar_cadena"])

    assert script.main() == 1, "el comando aprobó una cadena rota"
    salida = capsys.readouterr().out
    assert "ROTURA" in salida and "ses_0" in salida


def test_guardar_una_auditoria_la_encadena_sola(tmp_path, monkeypatch):
    """El eslabón no se anota a mano en ningún lado: sale de `guardar_auditoria`.

    Si alguien separa las dos cosas, las auditorías nuevas dejan de anclarse y
    la cadena queda congelada en el pasado sin que nada falle.
    """
    repo = _preparar(tmp_path, monkeypatch, sesiones=1)
    antes = len(leer_cadena(repo.ruta_cadena))

    repo.guardar_auditoria("ses_nueva", _cumplio())

    assert len(leer_cadena(repo.ruta_cadena)) == antes + 1
    assert verificar(repo.ruta_cadena, repo.ruta_auditorias).integra
