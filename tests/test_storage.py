"""Tests de persistencia.

Lo que importa acá no es que guarde y traiga —eso es lo fácil— sino los dos
candados que definimos en la arquitectura: idempotencia y retención.
"""

from datetime import datetime, timedelta

import pytest

from tutor.models import (
    Ejercicio,
    EstadoSesion,
    MetricasReporte,
    ModoSesion,
    Nino,
    RegistroDominio,
    ReporteParaPapa,
    Sesion,
    TextoLocalizado,
)
from tutor.storage import VERSION_ESQUEMA, RepositorioSQLite

AHORA = datetime(2026, 8, 17, 10, 0)


@pytest.fixture
def repo(tmp_path):
    return RepositorioSQLite(ruta_db=tmp_path / "tutor.db", ruta_datos=tmp_path)


def _nino() -> Nino:
    n = Nino(id="n1", nombre="Juan", edad=7, grado=2, creado_en=AHORA)
    n.perfil.intereses = ["fútbol", "dinosaurios"]
    n.perfil.estilo_comunicacion = "directo"
    n.perfil.madurez_vinculo = 4
    n.dominio["mat.suma.sin_reagrupacion"] = RegistroDominio(
        habilidad_id="mat.suma.sin_reagrupacion",
        nivel=0.85,
        intentos=9,
        aciertos=8,
        pistas_necesitadas=2,
        primera_practica=AHORA - timedelta(days=5),
        ultima_practica=AHORA,
    )
    return n


def _sesion(sid: str = "s1", inicio: datetime = AHORA, analizada: bool = False) -> Sesion:
    return Sesion(
        id=sid, nino_id="n1", modo=ModoSesion.GUIADO, inicio=inicio, analizada=analizada
    )


# ─────────────────────────────────────────────────────────────────────────────
# Configuración que hace segura la escritura concurrente
# ─────────────────────────────────────────────────────────────────────────────


def test_wal_activado(repo):
    """WAL es lo que evita 'database is locked' entre la sesión en vivo y el
    pipeline offline. Sin esto, SQLite no aporta nada sobre un JSON."""
    with repo._conectar() as con:
        assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_claves_foraneas_activadas(repo):
    """SQLite las ignora salvo que se pidan explícitamente en cada conexión."""
    with repo._conectar() as con:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_version_de_esquema_registrada(repo):
    with repo._conectar() as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == VERSION_ESQUEMA


def test_reabrir_no_rompe_nada(tmp_path):
    """Migrar es idempotente: abrir la misma base dos veces no la destruye."""
    r1 = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    r1.guardar_nino(_nino())
    r2 = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    assert r2.obtener_nino("n1") is not None


# ─────────────────────────────────────────────────────────────────────────────
# La ficha del niño: las dos mitades
# ─────────────────────────────────────────────────────────────────────────────


def test_guarda_y_trae_las_dos_mitades(repo):
    repo.guardar_nino(_nino())
    n = repo.obtener_nino("n1")

    assert n.nombre == "Juan"
    assert n.perfil.intereses == ["fútbol", "dinosaurios"], "mitad personal"
    assert n.perfil.madurez_vinculo == 4

    reg = n.dominio["mat.suma.sin_reagrupacion"]
    assert reg.nivel == 0.85, "mitad académica"
    assert reg.aciertos == 8
    assert reg.ultima_practica == AHORA, "las fechas sobreviven el viaje"


def test_nino_inexistente_devuelve_none(repo):
    assert repo.obtener_nino("no-existe") is None


def test_guardar_de_nuevo_actualiza_sin_duplicar(repo):
    n = _nino()
    repo.guardar_nino(n)

    n.perfil.intereses.append("robots")
    n.dominio["mat.suma.sin_reagrupacion"].nivel = 0.95
    repo.guardar_nino(n)

    traido = repo.obtener_nino("n1")
    assert "robots" in traido.perfil.intereses
    assert traido.dominio["mat.suma.sin_reagrupacion"].nivel == 0.95
    assert len(traido.dominio) == 1, "no se duplicó la fila de dominio"


def test_las_dos_mitades_viajan_juntas(repo):
    """ATOMICIDAD: si fallara a mitad de camino, el niño quedaría con la ficha
    personal de hoy y el dominio de la semana pasada."""
    n = _nino()
    n.dominio["mat.resta.sin_desagrupacion"] = RegistroDominio(
        habilidad_id="mat.resta.sin_desagrupacion", nivel=0.4, ultima_practica=AHORA
    )
    n.perfil.motivadores = ["competir"]
    repo.guardar_nino(n)

    traido = repo.obtener_nino("n1")
    assert len(traido.dominio) == 2
    assert traido.perfil.motivadores == ["competir"]


# ─────────────────────────────────────────────────────────────────────────────
# Sesiones e IDEMPOTENCIA
# ─────────────────────────────────────────────────────────────────────────────


def test_ciclo_de_vida_de_una_sesion(repo):
    repo.guardar_nino(_nino())
    s = _sesion()
    repo.crear_sesion(s)

    s.estado = EstadoSesion.COMPLETADA
    s.fin = AHORA + timedelta(minutes=30)
    s.habilidades_trabajadas = ["mat.suma.sin_reagrupacion"]
    s.tokens_consumidos = 4200
    repo.actualizar_sesion(s)

    traida = repo.obtener_sesion("s1")
    assert traida.estado == EstadoSesion.COMPLETADA
    assert traida.habilidades_trabajadas == ["mat.suma.sin_reagrupacion"]
    assert traida.tokens_consumidos == 4200


def test_la_cola_del_analista_solo_trae_lo_no_analizado(repo):
    """EL CANDADO DE IDEMPOTENCIA: sin esto, una sesión reprocesada suma dominio
    dos veces y el niño figura sabiendo más de lo que sabe."""
    repo.guardar_nino(_nino())
    repo.crear_sesion(_sesion("s1", analizada=False))
    repo.crear_sesion(_sesion("s2", analizada=True))

    pendientes = {s.id for s in repo.sesiones_sin_analizar()}
    assert pendientes == {"s1"}


def test_marcar_analizada_la_saca_de_la_cola(repo):
    repo.guardar_nino(_nino())
    repo.crear_sesion(_sesion("s1"))
    assert repo.sesiones_sin_analizar()

    s = repo.obtener_sesion("s1")
    s.analizada = True
    repo.actualizar_sesion(s)
    assert repo.sesiones_sin_analizar() == []


def test_sesiones_de_un_rango_para_el_reporte(repo):
    repo.guardar_nino(_nino())
    repo.crear_sesion(_sesion("vieja", AHORA - timedelta(days=20)))
    repo.crear_sesion(_sesion("s1", AHORA - timedelta(days=3)))
    repo.crear_sesion(_sesion("s2", AHORA - timedelta(days=1)))

    semana = repo.sesiones_de("n1", AHORA - timedelta(days=7), AHORA)
    assert [s.id for s in semana] == ["s1", "s2"], "ordenadas y sin la vieja"


# ─────────────────────────────────────────────────────────────────────────────
# Banco de ejercicios
# ─────────────────────────────────────────────────────────────────────────────


def _ej(eid: str, validado: bool = True, tema: str | None = None) -> Ejercicio:
    return Ejercicio(
        id=eid,
        habilidad_id="mat.suma.con_reagrupacion",
        enunciado=TextoLocalizado(es="27 + 15"),
        respuesta="42",
        tema=tema,
        validado=validado,
    )


def test_solo_se_entregan_ejercicios_validados(repo):
    """Un ejercicio sin verificar en código NUNCA llega a un niño."""
    repo.guardar_ejercicios([_ej("e1"), _ej("e2", validado=False)])
    entregados = repo.ejercicios_de("mat.suma.con_reagrupacion")
    assert [e.id for e in entregados] == ["e1"]


def test_filtra_por_tema_para_variantes_personalizadas(repo):
    repo.guardar_ejercicios([_ej("e1", tema="futbol"), _ej("e2", tema="dinosaurios")])
    futbol = repo.ejercicios_de("mat.suma.con_reagrupacion", tema="futbol")
    assert [e.id for e in futbol] == ["e1"]


def test_respeta_el_limite_de_precarga(repo):
    repo.guardar_ejercicios([_ej(f"e{i}") for i in range(30)])
    assert len(repo.ejercicios_de("mat.suma.con_reagrupacion", limite=15)) == 15


def test_el_enunciado_sobrevive_el_viaje(repo):
    repo.guardar_ejercicios([_ej("e1")])
    e = repo.ejercicios_de("mat.suma.con_reagrupacion")[0]
    assert e.enunciado.es == "27 + 15"
    assert e.respuesta == "42"


# ─────────────────────────────────────────────────────────────────────────────
# RETENCIÓN de datos de menores
# ─────────────────────────────────────────────────────────────────────────────


def test_transcripcion_ida_y_vuelta(repo):
    repo.guardar_transcripcion("s1", "Tutor: hola\nNiño: hola")
    assert "Niño: hola" in repo.obtener_transcripcion("s1")
    assert repo.obtener_transcripcion("no-existe") is None


def test_borra_las_viejas_y_conserva_las_nuevas(repo):
    """Ley 1581 (CO) / COPPA (US): el activo es la ficha, no la conversación."""
    repo.guardar_nino(_nino())
    repo.crear_sesion(_sesion("vieja", AHORA - timedelta(days=60)))
    repo.crear_sesion(_sesion("reciente", AHORA - timedelta(days=2)))
    repo.guardar_transcripcion("vieja", "conversación de hace dos meses")
    repo.guardar_transcripcion("reciente", "conversación de anteayer")

    borradas = repo.borrar_transcripciones_anteriores_a(AHORA - timedelta(days=30))

    assert borradas == 1
    assert repo.obtener_transcripcion("vieja") is None
    assert repo.obtener_transcripcion("reciente") is not None


def test_la_ficha_sobrevive_al_borrado_de_transcripciones(repo):
    """Lo que se aprendió del niño NO se pierde: solo se borra la conversación."""
    repo.guardar_nino(_nino())
    repo.crear_sesion(_sesion("vieja", AHORA - timedelta(days=60)))
    repo.guardar_transcripcion("vieja", "...")

    repo.borrar_transcripciones_anteriores_a(AHORA - timedelta(days=30))

    n = repo.obtener_nino("n1")
    assert n.dominio["mat.suma.sin_reagrupacion"].nivel == 0.85
    assert n.perfil.intereses == ["fútbol", "dinosaurios"]


def test_manda_la_fecha_de_la_sesion_no_la_del_archivo(repo):
    """El archivo se escribe hoy aunque la sesión sea de hace dos meses."""
    repo.guardar_nino(_nino())
    repo.crear_sesion(_sesion("vieja", AHORA - timedelta(days=90)))
    repo.guardar_transcripcion("vieja", "...")  # archivo creado recién

    assert repo.borrar_transcripciones_anteriores_a(AHORA - timedelta(days=30)) == 1


def test_los_huerfanos_tambien_se_barren(repo):
    """Un hueco en la base no puede dejar datos de un menor sin borrar."""
    import os
    import time

    repo.guardar_transcripcion("sin-sesion", "...")
    ruta = repo._ruta_transcripcion("sin-sesion")
    viejo = time.time() - 60 * 86_400
    os.utime(ruta, (viejo, viejo))

    assert repo.borrar_transcripciones_anteriores_a(AHORA - timedelta(days=30)) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Reportes
# ─────────────────────────────────────────────────────────────────────────────


def test_guarda_el_reporte_como_archivo(repo):
    reporte = ReporteParaPapa(
        nino_id="n1",
        desde=AHORA - timedelta(days=7),
        hasta=AHORA,
        metricas=MetricasReporte(
            sesiones=3,
            minutos_totales=95,
            cumplimiento_metodo=1.0,
            grado_de_trabajo=3,
            adelanto_grados=1,
        ),
        contenido="Juan avanzó muy bien esta semana.",
    )
    repo.guardar_reporte(reporte)
    assert list(repo.ruta_reportes.glob("n1_*.json"))
