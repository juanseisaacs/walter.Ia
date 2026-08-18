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
    assert len(datos["ejercicios"]) == 15
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
