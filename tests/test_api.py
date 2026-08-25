"""Tests de la API.

Lo que se verifica acá no es FastAPI: es que los candados de la arquitectura
sobrevivan al pasar por HTTP, y que el papá no pueda ver la ficha de un niño
que no es suyo.
"""

import pytest
from fastapi.testclient import TestClient

from tutor import api
from tutor.api import _email_del_papa
from tutor.models import Ejercicio, Nino, TextoLocalizado
from tutor.notificaciones import NotificadorFalso

# La credencial de cada niño: el enlace que el papá recibió al darlo de alta.
TOKENS = {"n1": "tok-de-juan", "n2": "tok-de-sofia"}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    from tutor.curriculum import cargar_grafo
    from tutor.session import Orquestador
    from tutor.storage import RepositorioSQLite
    from tutor.voice import EmisorFalso

    repo = RepositorioSQLite(tmp_path / "t.db", tmp_path)
    # Con `email_papa`, que es como los crea el onboarding: es obligatorio, y
    # el enlace al panel solo se manda al correo REGISTRADO de cada niño.
    nino = Nino(
        id="n1", nombre="Juan", edad=7, grado=2,
        email_papa="papa.juan@ej.com", token_acceso=TOKENS["n1"],
    )
    repo.guardar_nino(nino)
    repo.guardar_nino(
        Nino(
            id="n2", nombre="Sofia", edad=8, grado=3,
            email_papa="mama.sofia@ej.com", token_acceso=TOKENS["n2"],
        )
    )
    grafo = cargar_grafo()
    # Para toda habilidad VERIFICABLE EN CÓDIGO, como la base real: un
    # ejercicio de "leer una oración corrida" con respuesta "42" no existe, y
    # con él `check_answer` devolvía REQUIERE_JUICIO — correcto por diseño, pero
    # el test parecía roto. Salió al entrar `lenguaje.yaml`, cuyos nodos de
    # comprensión y producción no se validan comparando cadenas.
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
            if h.verificable_en_codigo
            for i in range(20)
        ]
    )
    monkeypatch.setattr(api, "_repo", repo)
    monkeypatch.setattr(api, "_grafo", grafo)
    monkeypatch.setattr(api, "_orquestador", Orquestador(repo, grafo, EmisorFalso()))
    monkeypatch.setattr(api, "_notificador", NotificadorFalso())

    return TestClient(api.app)


def _abrir(cliente, nino_id: str = "n1", **extra) -> str:
    """Abre sesión como lo hace la app: con la credencial del niño."""
    r = cliente.post(
        "/api/sesiones",
        json={"nino_id": nino_id, "token": TOKENS[nino_id], **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()["sesion_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Sesión
# ─────────────────────────────────────────────────────────────────────────────


def test_abrir_devuelve_token_y_ejercicios_no_la_configuracion(cliente):
    """Candado #1 sobre HTTP: el navegador nunca ve el system prompt."""
    datos = cliente.post("/api/sesiones", json={"nino_id": "n1", "token": TOKENS["n1"]}).json()

    assert datos["token"]
    assert len(datos["ejercicios"]) >= 15, "la habilidad del día más las vecinas"
    assert "instruccion_sistema" not in datos
    assert "playbook" not in str(datos).lower()


def test_el_tope_diario_devuelve_429(cliente):
    """Solo cuentan las sesiones donde el nino realmente trabajo."""
    for _ in range(3):
        sid = _abrir(cliente)
        cliente.post("/api/tools/get_next_problem", params={"sesion_id": sid})
        cliente.post(f"/api/sesiones/{sid}/cerrar", json={})
    r = cliente.post("/api/sesiones", json={"nino_id": "n1", "token": TOKENS["n1"]})
    assert r.status_code == 429


def test_una_sesion_que_no_se_uso_no_quema_cupo(cliente):
    """Se corto internet o toco el boton sin querer: no pierde el cupo."""
    for _ in range(3):
        sid = _abrir(cliente)
        cliente.post(f"/api/sesiones/{sid}/cerrar", json={"interrumpida": True})
    abierta = cliente.post("/api/sesiones", json={"nino_id": "n1", "token": TOKENS["n1"]})
    assert abierta.status_code == 200


def test_un_nino_inexistente_da_400(cliente):
    # 401 y no 400: contestar distinto para "no existe" y "token que no cuadra"
    # convertiría esto en un oráculo para enumerar niños.
    assert cliente.post("/api/sesiones", json={"nino_id": "x"}).status_code == 401


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


CORREOS = {"n1": "papa.juan@ej.com", "n2": "mama.sofia@ej.com"}


def _token_para(cliente, nino_id: str) -> str:
    cliente.post(
        "/api/auth/magic-link", json={"nino_id": nino_id, "email": CORREOS[nino_id]}
    )
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


def test_salud_dice_con_que_frontend_esta_hablando(cliente):
    """EL CHEQUEO DE VERSIÓN, del lado del servidor. Sale de `ses_4ed4e930e60f`.

    El niño tenía la pestaña abierta desde antes; el backend se había reiniciado
    con la pizarra nueva. El log lo muestra sin discusión —`POST /api/sesiones`
    ANTES del primer `GET /`—: el JavaScript que corría era el viejo. El modelo
    pidió lo que el backend le dijo que podía pedir, el traductor no lo entendió,
    y el tutor le dijo al niño «el tablero no me quiere funcionar hoy».

    `build` es lo que le permite al navegador darse cuenta solo y recargarse.
    Si esta clave desaparece, el chequeo del front deja de actuar EN SILENCIO
    —`recargarSiEstoyViejo` no recarga cuando el backend no informa build— y
    volvemos exactamente al mismo bug.
    """
    datos = cliente.get("/api/salud").json()
    assert "build" in datos, "sin esto el navegador no puede saber si está viejo"

    from tutor.api import _WEB, build_servido

    if (_WEB / "index.html").is_file():
        assert datos["build"] == build_servido()
        assert datos["build"].startswith("index-") and datos["build"].endswith(".js")
    else:
        # Sin `npm run build` no hay bundle que anunciar, y eso es correcto: un
        # backend sin frontend construido no puede exigir una versión.
        assert datos["build"] is None


def test_el_html_no_se_cachea_y_los_assets_si(cliente):
    """La otra mitad: de nada sirve detectar que el front está viejo si al
    recargar el navegador vuelve a entregar el mismo HTML de su caché.

    El `index.html` es el único archivo sin hash en el nombre —los assets lo
    llevan adentro—, así que es el único que puede quedar pegado apuntando a un
    bundle que ya no existe.
    """
    from tutor.api import _WEB, build_servido

    if not (_WEB / "index.html").is_file():
        pytest.skip("hace falta `cd web && npm run build`")

    html = cliente.get("/")
    assert "no-store" in html.headers.get("cache-control", ""), (
        "el index.html se puede quedar cacheado y la recarga no traería nada nuevo"
    )

    asset = cliente.get(f"/assets/{build_servido()}")
    assert asset.status_code == 200
    assert "immutable" in asset.headers.get("cache-control", ""), (
        "el bundle lleva hash en el nombre: puede y debe cachearse fuerte"
    )


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
    abierta = cliente.post("/api/sesiones", json={"nino_id": "n1", "token": TOKENS["n1"]}).json()
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
    sid = _abrir(cliente)

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
    token_nuevo = fin["enlace_del_nino"].split("&t=")[1]
    abierta = c.post(
        "/api/sesiones", json={"nino_id": fin["nino_id"], "token": token_nuevo}
    )
    assert abierta.status_code == 200, "se dio de alta un niño que no puede estudiar"


def test_una_entrevista_que_no_existe_lo_dice(cliente_con_entrevistador):
    r = cliente_con_entrevistador.post("/api/onboarding/onb_inventado", json={"texto": "hola"})
    assert r.status_code == 404


def test_sin_modelo_el_onboarding_lo_dice_en_vez_de_fingirlo(cliente, monkeypatch):
    """Un formulario de mentira que no guarda nada es peor que un error claro."""
    monkeypatch.setattr(api, "_HAY_ANALISTA", False)
    assert cliente.post("/api/onboarding").status_code == 503


# ─────────────────────────────────────────────────────────────────────────────
# El 20% del colegio en el panel del papá
# ─────────────────────────────────────────────────────────────────────────────


def test_el_panel_muestra_lo_que_el_tutor_sabe_del_colegio():
    """Va en recuadro aparte de los intereses porque responde otra pregunta del
    papá: no "¿lo conoce?" sino "¿está alineado con lo que ve en clase?".

    Es también lo que hace VERIFICABLE la memoria institucional: el papá puede
    contrastarlo con el cuaderno de su hijo. Un tutor que dice conocer el
    colegio y no lo muestra no se puede auditar.
    """
    from tutor.panel import render_panel

    html = render_panel(
        nombre="Juan", grado_escolar=2, grado_de_trabajo=3, adelanto_grados=1,
        ya_domina=["Contar hasta 100"], esta_trabajando=["Centenas"], intereses=["fútbol"],
        contexto_escolar="La profe Marcela está dando los mapas de Colombia.",
        sesiones_total=8, sesiones_auditadas=6, metodo_sostenido=0.83, dias=7,
    )
    assert "Lo que sabe del colegio de Juan" in html
    assert "profe Marcela" in html


def test_sin_datos_del_colegio_el_panel_no_deja_un_recuadro_vacio():
    """Ausencia de evidencia se dice callando. Un recuadro con título y nada
    adentro le promete al papá algo que el tutor todavía no sabe."""
    from tutor.panel import render_panel

    html = render_panel(
        nombre="Juan", grado_escolar=2, grado_de_trabajo=2, adelanto_grados=0,
        ya_domina=[], esta_trabajando=["Centenas"], intereses=["fútbol"],
        sesiones_total=8, sesiones_auditadas=6, metodo_sostenido=0.83, dias=7,
    )
    assert "Lo que sabe del colegio" not in html


def test_el_texto_del_colegio_lo_escribe_un_modelo_y_va_escapado():
    """`contexto_escolar` sale del Analista leyendo una transcripción: es la
    ruta más corta que existe entre lo que alguien dijo en voz alta y el
    navegador del papá. Escaparlo no es paranoia, es el camino real."""
    from tutor.panel import render_panel

    html = render_panel(
        nombre="Juan", grado_escolar=2, grado_de_trabajo=2, adelanto_grados=0,
        ya_domina=[], esta_trabajando=[], intereses=[],
        contexto_escolar="<script>alert(1)</script>",
        sesiones_total=1, sesiones_auditadas=0, metodo_sostenido=None, dias=7,
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ─────────────────────────────────────────────────────────────────────────────
# La interfaz servida por el mismo proceso
# ─────────────────────────────────────────────────────────────────────────────


def test_una_ruta_de_pantalla_devuelve_la_interfaz(cliente):
    """La interfaz elige qué pantalla mostrar mirando la URL, así que `/pizarra`
    no existe en el disco. Sin el respaldo al index, `StaticFiles` devuelve 404
    y la pantalla no abre nunca."""
    r = cliente.get("/pizarra")
    assert r.status_code in (200, 404)  # 404 solo si no se construyó el bundle
    if r.status_code == 200:
        assert "<title>" in r.text, "debería llegar el index, no un archivo suelto"


def test_una_ruta_de_api_que_no_existe_sigue_siendo_404(cliente):
    """El respaldo al index NO puede tragarse los errores de la API.

    Devolverle HTML a un cliente que pidió JSON esconde el problema: el
    navegador dice 200, el JSON no parsea, y se busca en el lugar equivocado.
    """
    assert cliente.get("/api/no_existe").status_code == 404


# ── A qué correo sale la alerta de seguridad ─────────────────────────────────


def test_la_alerta_va_al_correo_real_del_papa():
    """Se despachaba a `papa+n1@pendiente.local` aunque el papá tuviera el suyo
    registrado, porque esta función ignoraba el campo. El camino más urgente que
    tiene el producto apuntaba a una casilla inventada."""
    nino = Nino(id="n1", nombre="Juan", edad=7, grado=2, email_papa="mama@ejemplo.com")

    assert _email_del_papa(nino) == "mama@ejemplo.com"


def test_sin_correo_registrado_la_alerta_igual_sale():
    """Los niños creados antes del onboarding no tienen el campo. Quedarse sin
    alerta es peor que mandarla a una casilla que no existe."""
    viejo = Nino(id="n_viejo", nombre="Ana", edad=7, grado=2)

    assert _email_del_papa(viejo) == "papa+n_viejo@pendiente.local"


def test_el_panel_le_cuenta_al_papa_como_se_le_ensena(cliente):
    """El motor decide y el papá tiene que verlo. Elegir bien y no contarlo es
    exactamente no tener motor — el argumento del producto es poder contestar
    «¿por qué cambió de método?»."""
    from datetime import datetime, timedelta

    from tutor.models import ModoSesion, Sesion

    repo = api._repo
    ahora = datetime.now()
    for i, (tid, ini) in enumerate(
        [("concreto_primero", 0.20), ("concreto_primero", 0.20), ("estructura_primero", 0.20)]
    ):
        s = Sesion(
            id=f"ses_m{i}", nino_id="n1", modo=ModoSesion.GUIADO,
            inicio=ahora - timedelta(days=3 - i), fin=ahora - timedelta(days=3 - i),
            habilidades_trabajadas=["mat.numeros.conteo_hasta_100"],
            tecnica_id=tid, dominio_inicial=ini,
        )
        repo.crear_sesion(s)
        repo.actualizar_sesion(s)

    token = _token_para(cliente, "n1")
    html = cliente.get(f"/panel/n1?token={token}").text

    assert "Empezar por la estructura" in html, "el panel no dice cómo se le enseña"
    assert "Se cambió la forma de enseñarle" in html
    assert "Empezar por lo concreto" in html, "no dice de qué método venía"


def test_sin_tecnicas_el_panel_no_habla_de_metodo(cliente):
    """Las sesiones anteriores al motor están en NULL: no se inventa nada."""
    token = _token_para(cliente, "n1")
    html = cliente.get(f"/panel/n1?token={token}").text
    assert "Se cambió la forma de enseñarle" not in html
    assert "Cómo se le enseña" not in html


# ─────────────────────────────────────────────────────────────────────────────
# El enlace del panel solo va al correo registrado
# ─────────────────────────────────────────────────────────────────────────────


def test_no_se_le_manda_el_panel_de_un_nino_a_un_correo_cualquiera(cliente):
    """EL agujero, cerrado.

    Hasta el 22/08 este endpoint mandaba el enlace al correo que le pasaran:
    quien conociera o adivinara un `nino_id` se enviaba a sí mismo acceso de 24
    horas al panel de un menor — nombre, edad, grado, intereses, frustraciones,
    dominio y las notas de la auditoría.
    """
    r = cliente.post(
        "/api/auth/magic-link", json={"nino_id": "n1", "email": "cualquiera@ajeno.com"}
    )

    assert r.status_code == 200, "la respuesta no puede delatar que falló"
    assert api._notificador.enviados == [], "mandó el panel de un niño a un desconocido"


def test_al_correo_registrado_si_le_llega(cliente):
    cliente.post("/api/auth/magic-link", json={"nino_id": "n1", "email": "papa.juan@ej.com"})
    assert len(api._notificador.enviados) == 1


def test_el_correo_no_distingue_mayusculas_ni_espacios(cliente):
    """Un papá que escribe su correo a mano no tiene por qué acertar el formato."""
    cliente.post(
        "/api/auth/magic-link", json={"nino_id": "n1", "email": "  Papa.Juan@EJ.com "}
    )
    assert len(api._notificador.enviados) == 1


def test_la_respuesta_es_la_misma_exista_o_no_el_nino(cliente):
    """Si contestara distinto, esto sería un oráculo para enumerar niños.

    El 404 de antes lo era: bastaba probar ids hasta que dejara de dar 404.
    """
    real = cliente.post("/api/auth/magic-link", json={"nino_id": "n1", "email": "x@y.com"})
    fantasma = cliente.post(
        "/api/auth/magic-link", json={"nino_id": "n_no_existe", "email": "x@y.com"}
    )

    assert real.status_code == fantasma.status_code == 200
    assert real.json() == fantasma.json()
    assert api._notificador.enviados == []


def test_un_nino_sin_correo_registrado_no_abre_el_panel_de_nadie(cliente):
    """Sin `email_papa` no hay a quién avisar, así que tampoco a quién dejar
    entrar. Las fichas viejas hechas a mano quedan así hasta que se completen."""
    api._repo.guardar_nino(Nino(id="n_sin_correo", nombre="Ana", edad=7, grado=2))

    cliente.post(
        "/api/auth/magic-link", json={"nino_id": "n_sin_correo", "email": "quien@sea.com"}
    )
    assert api._notificador.enviados == []


# ─────────────────────────────────────────────────────────────────────────────
# Nadie abre sesión con un niño que no es suyo
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_credencial_no_se_abre_sesion(cliente):
    """EL segundo agujero, cerrado.

    Hasta el 22/08 bastaba conocer un `nino_id` —que viaja en la URL de la app
    y nunca fue un secreto— para quemarle la cuota a un niño ajeno, leer los
    ejercicios que le tocaban hoy y, sobre todo, llevarse un token efímero de
    Gemini sin credencial ninguna.
    """
    r = cliente.post("/api/sesiones", json={"nino_id": "n1"})

    assert r.status_code == 401
    assert "token" not in r.json(), "no puede filtrar un token de voz en el error"


def test_con_la_credencial_de_otro_nino_tampoco(cliente):
    """Tener acceso a UN niño no da acceso a los demás."""
    r = cliente.post("/api/sesiones", json={"nino_id": "n1", "token": TOKENS["n2"]})
    assert r.status_code == 401


def test_el_401_es_el_mismo_exista_o_no_el_nino(cliente):
    """Si el niño inexistente diera 400 y el token malo 401, probando ids se
    podría enumerar quién está dado de alta."""
    inexistente = cliente.post("/api/sesiones", json={"nino_id": "n_fantasma", "token": "x"})
    real_mal_token = cliente.post("/api/sesiones", json={"nino_id": "n1", "token": "x"})

    assert inexistente.status_code == real_mal_token.status_code == 401
    assert inexistente.json() == real_mal_token.json()


def test_el_error_le_dice_al_nino_qué_hacer(cliente):
    """Un chico de 7 años frente a «401 Unauthorized» no sabe qué hacer."""
    detalle = cliente.post("/api/sesiones", json={"nino_id": "n1"}).json()["detail"]
    assert "papá" in detalle or "mamá" in detalle


def test_el_onboarding_entrega_el_enlace_con_el_que_el_nino_entra(cliente_con_entrevistador):
    """Sin esto, el alta termina y nadie puede entrar: el papá se queda con un
    `nino_id` que ya no alcanza."""
    c = cliente_con_entrevistador
    onb = c.post("/api/onboarding").json()["onboarding_id"]
    # El entrevistador del fixture completa la ficha en el SEGUNDO turno.
    c.post(f"/api/onboarding/{onb}", json={"texto": "Se llama Sofía"})
    fin = c.post(f"/api/onboarding/{onb}", json={"texto": "listo"}).json()

    assert fin["listo"] is True
    enlace = fin["enlace_del_nino"]
    assert f"nino={fin['nino_id']}" in enlace
    assert "&t=" in enlace, "el enlace no lleva la credencial"

    token = enlace.split("&t=")[1]
    assert len(token) >= 20, "una credencial corta se adivina"
    assert c.post(
        "/api/sesiones", json={"nino_id": fin["nino_id"], "token": token}
    ).status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Reconectar
# ─────────────────────────────────────────────────────────────────────────────


def test_reconectar_devuelve_token_sin_abrir_sesion_nueva(cliente):
    """Se cayó el canal de voz, no la sesión. El niño no tiene que empezar de
    cero porque se murió un socket (`ses_02805f3edba1`)."""
    sid = _abrir(cliente)
    r = cliente.post(f"/api/sesiones/{sid}/reconectar")

    assert r.status_code == 200
    datos = r.json()
    assert datos["sesion_id"] == sid, "reconectar abrió una sesión nueva"
    assert datos["token"], "sin token no hay voz"
    assert datos["ejercicios"] == [], "el navegador ya los tiene: repetirlos se los pisa"


def test_reconectar_no_expone_la_configuracion(cliente):
    """El candado #1 vale igual acá: el navegador recibe un token, no un prompt.
    Un camino nuevo hacia el mismo token es un camino nuevo por donde se puede
    escapar la configuración."""
    sid = _abrir(cliente)
    datos = cliente.post(f"/api/sesiones/{sid}/reconectar").json()
    assert "instruccion_sistema" not in datos
    assert "configuracion" not in datos


def test_reconectar_una_sesion_cerrada_da_409(cliente):
    """409 y no 404: no es "no existe", es "esto ya no se puede recuperar,
    abrí una nueva". El navegador los trata distinto."""
    sid = _abrir(cliente)
    cliente.post(f"/api/sesiones/{sid}/cerrar", json={})
    assert cliente.post(f"/api/sesiones/{sid}/reconectar").status_code == 409


def test_reconectar_no_quema_el_cupo_diario(cliente):
    """Un socket que se cae no es una sesión más. Si contara, un niño con mala
    conexión se quedaría sin tutor a media tarde por algo que no hizo."""
    sid = _abrir(cliente)
    for _ in range(6):
        assert cliente.post(f"/api/sesiones/{sid}/reconectar").status_code == 200
    # Y todavía puede abrir una sesión de verdad después.
    cliente.post(f"/api/sesiones/{sid}/cerrar", json={})
    assert cliente.post(
        "/api/sesiones", json={"nino_id": "n1", "token": TOKENS["n1"]}
    ).status_code == 200


def test_el_latido_mantiene_la_sesion_y_no_falla_nunca(cliente):
    """Lo que le da ojos al reaper. Un POST vacío, fuera del camino del audio."""
    sid = _abrir(cliente)
    assert cliente.post(f"/api/sesiones/{sid}/latido").status_code == 204
    # Uno tardío, de una pestaña que no se enteró de que la sesión murió: no
    # puede devolver error o el navegador se pone a reintentar contra el vacío.
    assert cliente.post("/api/sesiones/ses_fantasma/latido").status_code == 204


def test_cerrar_acepta_el_cuerpo_que_manda_sendBeacon(cliente):
    """`sendBeacon` manda un Blob con `application/json`, no un fetch normal.

    Es el camino que se usa cuando la PESTAÑA se va, y si el backend no lo
    parsea la sesión queda huérfana igual — que es justo el bug que esto viene a
    tapar (`ses_610e057cfd91`, `estado: activa` para siempre)."""
    sid = _abrir(cliente)
    r = cliente.post(
        f"/api/sesiones/{sid}/cerrar",
        content=b'{"interrumpida": true, "tokens_consumidos": 4200}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "interrumpida"
    assert r.json()["tokens_consumidos"] == 4200
