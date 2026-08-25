"""Tests de persistencia.

Lo que importa acá no es que guarde y traiga —eso es lo fácil— sino los dos
candados que definimos en la arquitectura: idempotencia y retención.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

import pytest

from tutor.models import (
    AuditoriaCumplimiento,
    Calendario,
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
from tutor.storage import (
    _ESQUEMA_V1,
    _ESQUEMA_V2,
    VERSION_ESQUEMA,
    RepositorioSQLite,
)

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


def _reporte(hasta: datetime, contenido: str) -> ReporteParaPapa:
    return ReporteParaPapa(
        nino_id="n1",
        desde=hasta - timedelta(days=7),
        hasta=hasta,
        metricas=MetricasReporte(
            sesiones=3,
            minutos_totales=95,
            cumplimiento_metodo=1.0,
            grado_de_trabajo=3,
            adelanto_grados=1,
        ),
        contenido=contenido,
    )


def test_sin_reportes_no_hay_ultimo(repo):
    """El panel de un niño que recién arranca no puede reventar."""
    assert repo.ultimo_reporte("n1") is None


def test_el_ultimo_reporte_es_el_mas_reciente(repo):
    """Se guardan en orden salteado a propósito: el orden de escritura no manda."""
    repo.guardar_reporte(_reporte(AHORA - timedelta(days=14), "hace dos semanas"))
    repo.guardar_reporte(_reporte(AHORA, "esta semana"))
    repo.guardar_reporte(_reporte(AHORA - timedelta(days=7), "la semana pasada"))

    assert repo.ultimo_reporte("n1").contenido == "esta semana"


def test_el_reporte_de_un_nino_no_se_le_muestra_a_otro(repo):
    repo.guardar_reporte(_reporte(AHORA, "esta semana"))
    assert repo.ultimo_reporte("n2") is None


# ─────────────────────────────────────────────────────────────────────────────
# Auditoría del método
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_auditoria_devuelve_none(repo):
    """Nunca se midió ≠ salió bien. El panel necesita poder distinguirlos."""
    assert repo.obtener_auditoria("s1") is None


def test_el_veredicto_del_metodo_va_y_vuelve_entero(repo):
    repo.guardar_auditoria(
        "s1",
        AuditoriaCumplimiento(
            regalo_la_respuesta=True,
            respeto_escalera_pistas=False,
            detecto_frustracion=True,
            notas="Le dijo 'son dos centenas' sin que el niño llegara.",
        ),
    )
    v = repo.obtener_auditoria("s1")

    assert v.regalo_la_respuesta is True
    assert v.respeto_escalera_pistas is False
    assert v.notas.startswith("Le dijo")


def test_el_veredicto_sobrevive_al_borrado_de_la_transcripcion(repo):
    """La razón de ser de esta tabla: son booleanos, no la charla cruda. La
    evidencia de "no le doy las respuestas" tiene que durar más que la
    conversación que la produjo."""
    repo.guardar_nino(_nino())
    repo.crear_sesion(_sesion("vieja", AHORA - timedelta(days=60)))
    repo.guardar_transcripcion("vieja", "nino: 32\ntutor: ¡eso! son dos centenas")
    repo.guardar_auditoria(
        "vieja",
        AuditoriaCumplimiento(
            regalo_la_respuesta=False, respeto_escalera_pistas=True, detecto_frustracion=False
        ),
    )

    repo.borrar_transcripciones_anteriores_a(AHORA - timedelta(days=30))

    assert repo.obtener_transcripcion("vieja") is None
    assert repo.obtener_auditoria("vieja").regalo_la_respuesta is False


def test_listar_ninos_para_las_tareas_periodicas(repo):
    """El reporte semanal trabaja sobre la población, no sobre un niño."""
    assert repo.ids_de_ninos() == []

    repo.guardar_nino(_nino())
    repo.guardar_nino(Nino(id="n2", nombre="Sofia", edad=8, grado=3, creado_en=AHORA))

    assert set(repo.ids_de_ninos()) == {"n1", "n2"}


# ─────────────────────────────────────────────────────────────────────────────
# Enlaces del papá
# ─────────────────────────────────────────────────────────────────────────────


def test_el_enlace_del_papa_sobrevive_a_un_reinicio(tmp_path):
    """Vivían en un dict del proceso, y eso rompía dos cosas.

    El papá perdía el acceso cada vez que se reiniciaba el servidor, sin
    entender por qué. Y el script que genera los reportes —otro proceso— no
    podía emitir un enlace válido: por eso el correo semanal nunca se mandó,
    aunque `aviso_de_reporte()` existiera desde hacía semanas.
    """
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(Nino(id="n1", nombre="Juan", edad=7, grado=2))
    repo.crear_enlace("tok123", "n1", datetime.now() + timedelta(hours=24))

    # Otro proceso: el generador de reportes, o el servidor recién levantado.
    otro = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    assert otro.canjear_enlace("tok123") == "n1"


def test_un_enlace_vencido_no_abre_el_panel(tmp_path):
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(Nino(id="n1", nombre="Juan", edad=7, grado=2))
    repo.crear_enlace("viejo", "n1", datetime.now() - timedelta(minutes=1))

    assert repo.canjear_enlace("viejo") is None
    # Y se limpia solo al detectarlo: la tabla no crece sin que nadie la barra.
    assert repo.canjear_enlace("viejo") is None


def test_un_token_inventado_no_abre_nada(tmp_path):
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    assert repo.canjear_enlace("no-existe") is None


# ─────────────────────────────────────────────────────────────────────────────
# Migraciones sobre bases que YA tienen datos
# ─────────────────────────────────────────────────────────────────────────────


def test_migrar_de_v2_a_v3_no_pierde_la_ficha_de_nadie(tmp_path):
    """LA PRUEBA QUE IMPORTA DE UNA MIGRACIÓN.

    `test_reabrir_no_rompe_nada` corre sobre una base que el código actual creó
    entero: nunca ejerce el salto de versión. Acá se fabrica una base tal como
    quedaba en v2 —con un niño y su dominio adentro— y se abre con el código
    nuevo, que es lo que va a pasar en la máquina donde ya hay datos.

    Lo que se verifica no es que la columna exista: es que **el aprendizaje del
    niño sobrevivió**. Perder la tabla `dominio` en una migración es perder
    meses de sesiones, y no hay backup que lo devuelva con el niño esperando.
    """
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.executescript(_ESQUEMA_V1)
    con.executescript(_ESQUEMA_V2)
    con.execute("PRAGMA user_version = 2")
    con.execute(
        "INSERT INTO ninos (id,nombre,edad,grado,idioma,perfil,creado_en)"
        " VALUES (?,?,?,?,?,?,?)",
        ("n1", "Juan", 7, 2, "es", json.dumps({"intereses": ["fútbol"], "madurez_vinculo": 3}),
         "2026-08-01T10:00:00"),
    )
    con.execute(
        "INSERT INTO dominio (nino_id,habilidad_id,nivel,intentos,aciertos,ultima_practica)"
        " VALUES (?,?,?,?,?,?)",
        ("n1", "mat.numeros.conteo_hasta_100", 0.91, 12, 11, "2026-08-15T10:00:00"),
    )
    con.commit()
    con.close()

    repo = RepositorioSQLite(ruta, tmp_path)
    juan = repo.obtener_nino("n1")

    assert juan is not None, "la migración se llevó la ficha por delante"
    assert juan.perfil.intereses == ["fútbol"], "se perdió el perfil personal"
    assert juan.perfil.madurez_vinculo == 3
    assert juan.dominio["mat.numeros.conteo_hasta_100"].nivel == 0.91, "se perdió el aprendizaje"

    # El campo nuevo toma su default sin que nadie lo escriba: las fichas viejas
    # quedan en calendario A, que es el de la mayoría de colegios del país.
    assert juan.calendario == Calendario.A
    assert juan.perfil.contexto_escolar is None

    # Y se puede escribir lo nuevo sin tocar lo viejo.
    juan.calendario = Calendario.B
    juan.perfil.contexto_escolar = "La profe está dando los mapas de Colombia."
    repo.guardar_nino(juan)

    releido = repo.obtener_nino("n1")
    assert releido.calendario == Calendario.B
    assert releido.perfil.contexto_escolar.startswith("La profe")
    assert releido.dominio["mat.numeros.conteo_hasta_100"].nivel == 0.91


def test_el_correo_del_papa_sobrevive_a_la_base(tmp_path):
    """Se guardaba en el modelo y NO en la base: la columna no existía.

    `Nino.email_papa` estaba desde hacía fases, el onboarding lo declaraba
    obligatorio y `crear_nino_desde_ficha` lo poblaba — pero al releer la ficha
    volvía en `None`. Siempre. Y de ahí sale a dónde se manda la ALERTA DE
    SEGURIDAD, que es el camino más urgente del producto.
    """
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_nino(
        Nino(id="n1", nombre="Juan", edad=7, grado=2, email_papa="papa@ejemplo.com")
    )

    assert repo.obtener_nino("n1").email_papa == "papa@ejemplo.com"


def test_el_modelo_del_nino_y_la_tabla_no_se_desincronizan(tmp_path):
    """EL candado. Es la lección de la fase 4, en el otro par de definiciones.

    Allá eran `schema.json` y `models.Habilidad`; acá son `models.Nino` y la
    tabla `ninos`. Un campo que se agrega al modelo y no al esquema no rompe
    nada al escribir —SQLite lo ignora— y vuelve vacío al leer. Sin este test,
    el siguiente campo se pierde igual que se perdió `email_papa`.
    """
    import sqlite3

    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    con = sqlite3.connect(repo.ruta_db)
    columnas = {c[1] for c in con.execute("PRAGMA table_info(ninos)")}
    con.close()

    # Lo que vive en otro lado a propósito, no en una columna suya.
    aparte = {
        "perfil",   # documento JSON: nunca se consulta por dentro
        "dominio",  # tabla propia: es la consulta caliente del planificador
    }
    del_modelo = set(Nino.model_fields) - aparte

    faltan = del_modelo - columnas
    assert not faltan, (
        f"{sorted(faltan)} está(n) en `Nino` y no en la tabla `ninos`: se "
        f"guarda(n) sin error y vuelve(n) vacío(s) al leer. Agregá una "
        f"migración, como la v5 para `email_papa`."
    )


def test_el_diario_de_la_voz_se_apenda_y_se_lee(tmp_path):
    """Llega de a lotes durante la sesión: reescribir perdería los anteriores."""
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.anotar_en_diario("s1", [{"t": "latencia", "ms": 900}])
    repo.anotar_en_diario("s1", [{"t": "tool", "nombre": "check_answer", "ms": 12}])

    diario = repo.leer_diario("s1")
    assert [e["t"] for e in diario] == ["latencia", "tool"]
    assert diario[0]["ms"] == 900


def test_un_diario_sin_eventos_no_crea_archivo(tmp_path):
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.anotar_en_diario("s1", [])
    assert repo.leer_diario("s1") == []


def test_una_linea_rota_no_tira_el_diario_entero(tmp_path):
    """Esto se lee justo cuando algo salió mal: un lote a medio escribir no
    puede llevarse por delante los eventos que sí sirven."""
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.anotar_en_diario("s1", [{"t": "mudez"}])
    with (tmp_path / "transcripts" / "s1.eventos.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"t": "voz_mud\n')
    repo.anotar_en_diario("s1", [{"t": "reconexion"}])

    assert [e["t"] for e in repo.leer_diario("s1")] == ["mudez", "reconexion"]


def test_el_diario_muere_con_su_transcripcion(tmp_path):
    """Es dato de la conversación de un menor. Un diario que sobreviva a la
    transcripción sería un agujero en la política de retención."""
    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    repo.guardar_transcripcion("vieja", "nino: hola")
    repo.anotar_en_diario("vieja", [{"t": "latencia", "ms": 100}])

    # Huérfana (sin fila en sesiones) y con mtime viejo: la barre por mtime.
    antiguo = (datetime.now() - timedelta(days=400)).timestamp()
    for nombre in ("vieja.txt", "vieja.eventos.jsonl"):
        os.utime(tmp_path / "transcripts" / nombre, (antiguo, antiguo))

    repo.borrar_transcripciones_anteriores_a(datetime.now() - timedelta(days=30))
    assert repo.obtener_transcripcion("vieja") is None
    assert repo.leer_diario("vieja") == []
