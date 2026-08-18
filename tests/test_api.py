"""Tests de la API.

Lo que se verifica acá no es FastAPI: es que los candados de la arquitectura
sobrevivan al pasar por HTTP, y que el papá no pueda ver la ficha de un niño
que no es suyo.
"""

import pytest
from fastapi.testclient import TestClient

from tutor import api
from tutor.models import Ejercicio, Nino, TextoLocalizado
from tutor.notificaciones import NotificadorFalso


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    from tutor.curriculum import cargar_grafo
    from tutor.session import Orquestador
    from tutor.storage import RepositorioSQLite
    from tutor.voice import EmisorFalso

    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    nino = Nino(id="n1", nombre="Juan", edad=7, grado=2)
    repo.guardar_nino(nino)
    repo.guardar_nino(Nino(id="n2", nombre="Sofia", edad=8, grado=3))
    grafo = cargar_grafo()
    # Para toda habilidad, como la base real: así el fixture no se rompe cada
    # vez que el planificador cambia de opinión sobre por dónde empezar.
    repo.guardar_ejercicios(
        [
            Ejercicio(
                id=f"e_{h.id}_{i}",
                habilidad_id=h.id,
                enunciado=TextoLocalizado(es="27 + 15"),
                respuesta="42",
                validado=True,
            )
            for h in grafo
            for i in range(20)
        ]
    )
    monkeypatch.setattr(api, "_repo", repo)
    monkeypatch.setattr(api, "_grafo", grafo)
    monkeypatch.setattr(api, "_orquestador", Orquestador(repo, grafo, EmisorFalso()))
    monkeypatch.setattr(api, "_notificador", NotificadorFalso())
    api._ENLACES.clear()

    return TestClient(api.app)


def _abrir(cliente) -> str:
    r = cliente.post("/api/sesiones", json={"nino_id": "n1"})
    assert r.status_code == 200
    return r.json()["sesion_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Sesión
# ─────────────────────────────────────────────────────────────────────────────


def test_abrir_devuelve_token_y_ejercicios_no_la_configuracion(cliente):
    """Candado #1 sobre HTTP: el navegador nunca ve el system prompt."""
    datos = cliente.post("/api/sesiones", json={"nino_id": "n1"}).json()

    assert datos["token"]
    assert len(datos["ejercicios"]) >= 15, "la habilidad del día más las vecinas"
    assert "instruccion_sistema" not in datos
    assert "playbook" not in str(datos).lower()


def test_el_tope_diario_devuelve_429(cliente):
    """Solo cuentan las sesiones donde el nino realmente trabajo."""
    for _ in range(3):
        sid = cliente.post("/api/sesiones", json={"nino_id": "n1"}).json()["sesion_id"]
        cliente.post("/api/tools/get_next_problem", params={"sesion_id": sid})
        cliente.post(f"/api/sesiones/{sid}/cerrar", json={})
    r = cliente.post("/api/sesiones", json={"nino_id": "n1"})
    assert r.status_code == 429


def test_una_sesion_que_no_se_uso_no_quema_cupo(cliente):
    """Se corto internet o toco el boton sin querer: no pierde el cupo."""
    for _ in range(3):
        sid = cliente.post("/api/sesiones", json={"nino_id": "n1"}).json()["sesion_id"]
        cliente.post(f"/api/sesiones/{sid}/cerrar", json={"interrumpida": True})
    assert cliente.post("/api/sesiones", json={"nino_id": "n1"}).status_code == 200


def test_un_nino_inexistente_da_400(cliente):
    assert cliente.post("/api/sesiones", json={"nino_id": "x"}).status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────


def test_check_answer_entiende_numeros_hablados(cliente):
    sid = _abrir(cliente)
    ej = cliente.post("/api/tools/get_next_problem", params={"sesion_id": sid}).json()

    r = cliente.post(
        "/api/tools/check_answer",
        json={
            "sesion_id": sid,
            "ejercicio_id": ej["ejercicio"]["id"],
            "respuesta_nino": "cuarenta y dos",
        },
    ).json()

    assert r["correcto"] is True
    assert r["valor_interpretado"] == "42"


def test_check_answer_es_estricto_con_el_valor(cliente):
    sid = _abrir(cliente)
    ej = cliente.post("/api/tools/get_next_problem", params={"sesion_id": sid}).json()
    r = cliente.post(
        "/api/tools/check_answer",
        json={"sesion_id": sid, "ejercicio_id": ej["ejercicio"]["id"], "respuesta_nino": "41"},
    ).json()
    assert r["correcto"] is False


def test_no_se_puede_verificar_un_ejercicio_no_entregado(cliente):
    """Sin esto se podría sondear el banco entero desde afuera."""
    sid = _abrir(cliente)
    r = cliente.post(
        "/api/tools/check_answer",
        json={"sesion_id": sid, "ejercicio_id": "e99", "respuesta_nino": "42"},
    )
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Turnos y alerta inmediata
# ─────────────────────────────────────────────────────────────────────────────


def test_reportar_turnos_persiste(cliente):
    sid = _abrir(cliente)
    r = cliente.post(
        f"/api/sesiones/{sid}/turnos",
        json={"turnos": [{"quien": "nino", "texto": "cuarenta y dos"}]},
    )
    assert r.status_code == 200
    assert api._repo.obtener_transcripcion(sid)


def test_una_senal_grave_avisa_al_papa_en_el_momento(cliente):
    """Si el Vigilante escala un martes, el papá no puede enterarse el domingo."""
    sid = _abrir(cliente)
    cliente.post(
        f"/api/sesiones/{sid}/turnos",
        json={"turnos": [{"quien": "nino", "texto": "mi papa me pega"}]},
    )

    enviados = api._notificador.enviados
    assert len(enviados) == 1
    assert enviados[0].urgente is True


def test_la_alerta_no_lleva_lo_que_dijo_el_nino(cliente):
    """Un fragmento suelto en un mail asusta y desinforma. Se lee en el panel."""
    sid = _abrir(cliente)
    cliente.post(
        f"/api/sesiones/{sid}/turnos",
        json={"turnos": [{"quien": "nino", "texto": "mi papa me pega"}]},
    )
    aviso = api._notificador.enviados[0]
    assert "me pega" not in aviso.cuerpo
    assert aviso.enlace


def test_una_sesion_normal_no_dispara_nada(cliente):
    sid = _abrir(cliente)
    cliente.post(
        f"/api/sesiones/{sid}/turnos",
        json={"turnos": [{"quien": "nino", "texto": "cuarenta y dos"}]},
    )
    assert api._notificador.enviados == []


def test_candado_2_sin_reportar_no_hay_recarga(cliente):
    sid = _abrir(cliente)
    assert cliente.post(f"/api/sesiones/{sid}/recargar").status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# Panel del papá — magic link
# ─────────────────────────────────────────────────────────────────────────────


def _token_para(cliente, nino_id: str) -> str:
    cliente.post("/api/auth/magic-link", json={"nino_id": nino_id, "email": "p@ej.com"})
    return api._notificador.enviados[-1].enlace.split("token=")[1]


def test_el_enlace_llega_por_mail_y_abre_el_panel(cliente):
    token = _token_para(cliente, "n1")
    r = cliente.get("/api/ninos/n1/progreso", params={"token": token})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Juan"


def test_sin_enlace_no_se_ve_nada(cliente):
    assert cliente.get("/api/ninos/n1/progreso").status_code == 422
    assert cliente.get("/api/ninos/n1/progreso", params={"token": "inventado"}).status_code == 401


def test_el_enlace_de_un_nino_no_sirve_para_otro(cliente):
    """Un papá no puede ver la ficha del hijo de otro cambiando el id en la URL."""
    token = _token_para(cliente, "n1")
    assert cliente.get("/api/ninos/n2/progreso", params={"token": token}).status_code == 403


def test_el_panel_no_habla_en_jerga(cliente):
    """Ni 'nodos', ni 'grafo', ni 'dominio'. Temas y qué sabe hacer."""
    token = _token_para(cliente, "n1")
    texto = str(cliente.get("/api/ninos/n1/progreso", params={"token": token}).json()).lower()
    for jerga in ["nodo", "grafo", "habilidad_id", "prerequisito"]:
        assert jerga not in texto


def test_el_panel_muestra_si_va_adelantado(cliente):
    token = _token_para(cliente, "n1")
    datos = cliente.get("/api/ninos/n1/progreso", params={"token": token}).json()
    assert "adelanto_grados" in datos
    assert "grado_de_trabajo" in datos


def test_salud_responde(cliente):
    datos = cliente.get("/api/salud").json()
    assert datos["ok"] is True
    assert datos["habilidades"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# Panel del papá — la página
# ─────────────────────────────────────────────────────────────────────────────


def _sesion_auditada(sid: str, regalo_la_respuesta: bool) -> None:
    """Una sesión ya pasada por el Analista, con su veredicto persistido."""
    from datetime import datetime

    from tutor.models import AuditoriaCumplimiento, ModoSesion, Sesion

    api._repo.crear_sesion(
        Sesion(id=sid, nino_id="n1", modo=ModoSesion.GUIADO, inicio=datetime.now())
    )
    sesion = api._repo.obtener_sesion(sid)
    sesion.analizada = True
    api._repo.actualizar_sesion(sesion)
    api._repo.guardar_auditoria(
        sid,
        AuditoriaCumplimiento(
            regalo_la_respuesta=regalo_la_respuesta,
            respeto_escalera_pistas=True,
            detecto_frustracion=False,
        ),
    )


def test_el_enlace_del_mail_abre_una_pagina_no_un_json(cliente):
    """El papá hace clic en el mail y ve el panel, no una respuesta de API."""
    token = _token_para(cliente, "n1")
    r = cliente.get("/panel/n1", params={"token": token})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Juan" in r.text


def test_el_panel_se_puede_recargar(cliente):
    """El papá refresca la página, o vuelve mañana con el mismo mail. El enlace
    dura 24 horas: no puede morir en el primer uso."""
    token = _token_para(cliente, "n1")
    assert cliente.get("/panel/n1", params={"token": token}).status_code == 200
    assert cliente.get("/panel/n1", params={"token": token}).status_code == 200


def test_el_panel_de_un_nino_no_se_abre_con_el_enlace_de_otro(cliente):
    token = _token_para(cliente, "n1")
    r = cliente.get("/panel/n2", params={"token": token})

    assert r.status_code == 403
    assert "Sofia" not in r.text


def test_un_enlace_vencido_explica_en_castellano(cliente):
    """Un 401 con JSON en la cara es el momento en que un papá abandona."""
    r = cliente.get("/panel/n1", params={"token": "inventado"})

    assert r.status_code == 401
    assert r.headers["content-type"].startswith("text/html")
    assert "enlace" in r.text.lower()
    assert "detail" not in r.text


def test_sin_medir_el_metodo_el_panel_no_inventa_un_100(cliente):
    """Nunca se auditó ≠ salió perfecto. Inventar el número acá es exactamente
    lo que destruye la confianza que el panel existe para construir."""
    token = _token_para(cliente, "n1")
    texto = cliente.get("/panel/n1", params={"token": token}).text

    assert "100%" not in texto
    assert "Todavía no hay sesiones auditadas" in texto


def test_el_panel_muestra_la_fraccion_de_sesiones_con_el_metodo_sostenido(cliente):
    """Tres sesiones auditadas, en una regaló la respuesta: 67%, no 100%."""
    _sesion_auditada("s_ok1", regalo_la_respuesta=False)
    _sesion_auditada("s_ok2", regalo_la_respuesta=False)
    _sesion_auditada("s_mal", regalo_la_respuesta=True)
    token = _token_para(cliente, "n1")

    assert "67%" in cliente.get("/panel/n1", params={"token": token}).text


def test_la_pagina_del_papa_no_habla_en_jerga(cliente):
    """Ni 'nodos', ni 'grafo', ni ids de habilidad. Temas y qué sabe hacer."""
    _sesion_auditada("s_ok1", regalo_la_respuesta=False)
    token = _token_para(cliente, "n1")
    texto = cliente.get("/panel/n1", params={"token": token}).text.lower()

    for jerga in ["nodo", "grafo", "habilidad_id", "prerequisito", "mat.", "dominio_"]:
        assert jerga not in texto


def test_el_panel_no_se_contradice_sobre_cuantas_auditó(cliente):
    """Paso de verdad en el panel real: arriba decia "todavia no hay sesiones
    auditadas" y abajo "2 auditadas por el metodo". "Auditada" significa UNA
    cosa: que hay veredicto guardado. En la superficie que existe para
    verificar, una contradiccion visible cuesta mas que el dato que aporta.
    """
    from datetime import datetime

    from tutor.models import ModoSesion, Sesion

    # Analizada por el Analista, pero sin veredicto persistido (el caso real:
    # se analizó antes de que existiera `guardar_auditoria`).
    api._repo.crear_sesion(
        Sesion(id="s_vieja", nino_id="n1", modo=ModoSesion.GUIADO, inicio=datetime.now())
    )
    vieja = api._repo.obtener_sesion("s_vieja")
    vieja.analizada = True
    api._repo.actualizar_sesion(vieja)

    token = _token_para(cliente, "n1")
    texto = cliente.get("/panel/n1", params={"token": token}).text

    assert "Todavía no hay sesiones auditadas" in texto
    assert "<strong>0</strong> auditadas" in texto


def test_lo_que_se_cuenta_como_auditado_es_lo_que_se_promedia(cliente):
    """El numero de arriba y el de abajo salen de la misma lista."""
    _sesion_auditada("s_ok1", regalo_la_respuesta=False)
    _sesion_auditada("s_mal", regalo_la_respuesta=True)
    token = _token_para(cliente, "n1")
    texto = cliente.get("/panel/n1", params={"token": token}).text

    assert "50%" in texto
    assert "<strong>2</strong> auditadas" in texto


def test_verificar_una_cuenta_improvisada_no_necesita_sesion(cliente):
    """Es una funcion pura sobre dos strings. Atarla a una sesion seria pedirle
    estado a algo que no lo tiene."""
    r = cliente.post(
        "/api/tools/verify_arithmetic",
        json={"operacion": "578 - 34", "respuesta_nino": "400"},
    )

    assert r.status_code == 200
    assert r.json()["correcto"] is False
    assert r.json()["distancia"] == "lejos"


def test_el_endpoint_no_le_pasa_el_resultado_al_modelo(cliente):
    """Del otro lado hay un modelo hablandole a un nino: si tiene el numero,
    tarde o temprano lo dice."""
    r = cliente.post(
        "/api/tools/verify_arithmetic",
        json={"operacion": "135 + 241", "respuesta_nino": "780"},
    )
    assert "376" not in r.text


def test_el_tutor_puede_pedir_un_tema_distinto(cliente):
    """El niño dice "mejor hagamos restas" y el tutor tiene que poder pedirlo.

    El tema lo elige el niño; el ejercicio sale del banco validado en código.
    Sin esto el tutor improvisa, y lo que improvisa no queda atado a un nodo del
    grafo: la sesión no escribe dominio (18/08, ses_88be006b825f).
    """
    abierta = cliente.post("/api/sesiones", json={"nino_id": "n1"}).json()
    sid = abierta["sesion_id"]
    otro = next(
        e["habilidad_id"]
        for e in abierta["ejercicios"]
        if e["habilidad_id"] != abierta["habilidad_id"]
    )

    r = cliente.post(
        "/api/tools/get_next_problem", params={"sesion_id": sid, "habilidad_id": otro}
    ).json()

    assert r["ejercicio"] is not None
    assert r["ejercicio"]["habilidad_id"] == otro, "entregó de otro tema, no del pedido"


def test_un_tema_sin_ejercicios_no_devuelve_otra_cosa(cliente):
    """Responde qué SÍ hay, en vez de un error a secas.

    Un "no tengo" sin alternativas deja al tutor sin nada que ofrecer, y sin
    nada que ofrecer inventa. Tampoco puede entregar otro tema en silencio: el
    tutor terminaría corrigiendo contra un enunciado que el niño nunca oyó.
    """
    sid = cliente.post("/api/sesiones", json={"nino_id": "n1"}).json()["sesion_id"]

    r = cliente.post(
        "/api/tools/get_next_problem",
        params={"sesion_id": sid, "habilidad_id": "mat.no.existe"},
    ).json()

    assert r["ejercicio"] is None
    assert r["temas_disponibles"], "no le dijo al tutor qué sí tiene"


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding — sin esto no hay segundo usuario
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def cliente_con_entrevistador(cliente, monkeypatch):
    """El entrevistador contesta con un guion; lo que se prueba es el circuito."""
    from tutor.pipeline import ClienteFalso, FichaInicial

    class Entrevistador(ClienteFalso):
        """Devuelve ficha incompleta la primera vez y completa después."""

        def __init__(self):
            super().__init__(texto="¿Cómo se llama tu hijo?")
            self.vueltas = 0

        def extraer(self, modelo, sistema, mensaje, esquema, **kw):
            self.vueltas += 1
            if self.vueltas == 1:
                return FichaInicial(nombre_nino="Sofía")
            return FichaInicial(
                email_papa="papa@ejemplo.com",
                nombre_nino="Sofía",
                edad=8,
                grado=3,
                intereses=["caballos"],
            )

    monkeypatch.setattr(api, "_cliente_analista", Entrevistador())
    monkeypatch.setattr(api, "_HAY_ANALISTA", True)
    return cliente


def test_el_onboarding_da_de_alta_a_un_nino_de_verdad(cliente_con_entrevistador):
    """El motor existía desde la fase 6 y no lo exponía nadie: el único niño de
    la base se había creado a mano.
    """
    c = cliente_con_entrevistador

    inicio = c.post("/api/onboarding").json()
    assert inicio["pregunta"], "el papá tiene que recibir una primera pregunta"
    assert "email_papa" in inicio["falta"]

    oid = inicio["onboarding_id"]

    a_medias = c.post(f"/api/onboarding/{oid}", json={"texto": "Se llama Sofía"}).json()
    assert a_medias["listo"] is False, "con la ficha incompleta no se da de alta"
    assert a_medias["pregunta"]

    fin = c.post(f"/api/onboarding/{oid}", json={"texto": "Tiene 8, va en 3°"}).json()
    assert fin["listo"] is True
    assert fin["nino_id"]

    # Y el niño existe de verdad: puede abrir sesión.
    abierta = c.post("/api/sesiones", json={"nino_id": fin["nino_id"]})
    assert abierta.status_code == 200, "se dio de alta un niño que no puede estudiar"


def test_una_entrevista_que_no_existe_lo_dice(cliente_con_entrevistador):
    r = cliente_con_entrevistador.post("/api/onboarding/onb_inventado", json={"texto": "hola"})
    assert r.status_code == 404


def test_sin_modelo_el_onboarding_lo_dice_en_vez_de_fingirlo(cliente, monkeypatch):
    """Un formulario de mentira que no guarda nada es peor que un error claro."""
    monkeypatch.setattr(api, "_HAY_ANALISTA", False)
    assert cliente.post("/api/onboarding").status_code == 503
