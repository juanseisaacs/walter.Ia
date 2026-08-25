"""Endpoints HTTP (FastAPI).

Frontera deliberada: el backend no sabe qué frontend lo llama. Hoy es una web;
mañana es la misma API detrás de una app en las tiendas. Por eso ninguna lógica
vive acá — esto solo traduce HTTP a llamadas de los otros módulos.

El audio NO pasa por acá (ARCHITECTURE.md §10). Este es el plano de control:
  · abre sesiones y firma el token con la configuración atada
  · atiende los tools que el navegador reenvía durante la conversación
  · recibe los turnos transcriptos y dispara la seguridad
  · sirve el panel del papá
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import config as cfg
from .curriculum import cargar_grafo
from .models import Ejercicio, ModoSesion, Nino
from .notificaciones import Notificador, aviso_de_alerta, notificador_por_defecto
from .panel import render_error, render_panel
from .pedagogy import adelanto, esta_dominada, grado_de_trabajo, nivel_efectivo
from .pipeline import (
    FichaInicial,
    cliente_por_defecto,
    crear_nino_desde_ficha,
    extraer_ficha,
    primera_pregunta,
    procesar_sesion,
    siguiente_pregunta,
)
from .session import ErrorPresupuesto, ErrorSesion, Orquestador, Turno
from .storage import RepositorioSQLite
from .tecnicas import cambio_de_metodo, cargar_biblioteca
from .tools import Veredicto, check_answer, verify_arithmetic, verify_language
from .voice import emisor_por_defecto


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI):
    """Arma el cliente de Google antes de que llegue el primer niño.

    Construirlo cuesta ~1,6 s de handshake TLS y pool. Cacheado, la apertura de
    sesión bajó de 1010 ms a ~400 ms — pero la PRIMERA del día se comía los 2 s
    enteros, que es justo el peor lugar: el niño ya apretó el botón.

    Que falle no puede tumbar el arranque: sin llave el emisor es el falso, y un
    error de red acá solo significa que la primera sesión paga lo de antes.
    """
    if (calentar := getattr(_emisor, "_obtener", None)) is not None:
        try:
            calentar()
        except Exception as e:  # noqa: BLE001 — es optimización, no requisito
            print(f"[arranque] no se pudo precalentar el emisor: {e}")

    # Lo que quedó ACTIVA de un proceso anterior no lo usa nadie: el navegador
    # que lo abrió habla con un proceso que ya no existe. Se cierra acá porque
    # el reaper solo ve lo que tiene en memoria, y si no, un huérfano de ayer
    # vive para siempre — ocupando cupo y sin llegar nunca al Analista.
    try:
        for vieja in _orquestador.cerrar_huerfanas_de_arranque():
            print(f"[arranque] {vieja.id} había quedado huérfana: cerrada")
    except Exception as e:  # noqa: BLE001 — limpiar no puede impedir arrancar
        print(f"[arranque] no se pudieron cerrar las huérfanas: {e}")

    reaper = asyncio.create_task(_barrer_abandonadas())
    try:
        yield
    finally:
        reaper.cancel()


SEGUNDOS_ENTRE_BARRIDOS = 30


async def _barrer_abandonadas() -> None:
    """EL ÚNICO VIGILANTE QUE VIVE FUERA DE LA PESTAÑA.

    Todos los demás —la mudez, el reloj de sesión, el techo de tokens, la
    reconexión— son `setTimeout` en el navegador. **Un vigilante que vive
    adentro de lo que vigila no puede detectar que eso muera**, y por eso cada
    forma nueva de morirse nos tomaba por sorpresa: se llevaba puesto al
    vigilante junto con todo lo demás.

    `ses_610e057cfd91` quedó `activa`, sin `fin` y con 0 tokens. En el log no
    hay `/cerrar` ni `/reconectar`: la pestaña desapareció y el backend nunca se
    enteró. Esa sesión seguía ocupando un cupo del niño y su trabajo no había
    llegado al Analista.

    Esto corre en su propio reloj, sin depender de que haya alguien del otro
    lado. Y encola al Analista, que es la mitad que importa: al niño no puede
    costarle el dominio que ganó el que se le haya caído el navegador.
    """
    while True:
        try:
            await asyncio.sleep(SEGUNDOS_ENTRE_BARRIDOS)
            for sesion in _orquestador.cerrar_abandonadas():
                print(f"[reaper] {sesion.id} sin latido: cerrada como interrumpida")
                if _HAY_ANALISTA:
                    # En un hilo: el Analista habla con la API de Anthropic y
                    # bloquear el loop dejaría sin atender a los niños que sí
                    # están conectados.
                    await asyncio.to_thread(
                        procesar_sesion, _repo, _grafo, sesion, _cliente_analista
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            # Un barrido que revienta no puede matar al reaper: sin él volvemos
            # a quedar ciegos ante la pestaña que se cae.
            print(f"[reaper] falló un barrido: {e}")


app = FastAPI(title="RBH Tutor", version="0.1.0", lifespan=_ciclo_de_vida)

# Se arman una vez al arrancar, no por request.
_repo = RepositorioSQLite(cfg.DB, cfg.DATOS)
_grafo = cargar_grafo()
# Se carga una vez: la usan el orquestador (para elegir) y el panel (para
# contarle al papá qué se eligió y por qué).
_tecnicas = cargar_biblioteca()
_emisor = emisor_por_defecto()
_orquestador = Orquestador(_repo, _grafo, _emisor, tecnicas=_tecnicas)
_notificador: Notificador = notificador_por_defecto()

# El Analista corre offline con este cliente. Sin ANTHROPIC_API_KEY es un
# ClienteFalso sin guion: no puede analizar, así que ni se dispara y la sesión
# queda en cola para `scripts/procesar_pendientes.py` cuando haya llave.
_cliente_analista = cliente_por_defecto()
_HAY_ANALISTA = type(_cliente_analista).__name__ != "ClienteFalso"


# ─────────────────────────────────────────────────────────────────────────────
# Magic link — el papá no administra otra contraseña
# ─────────────────────────────────────────────────────────────────────────────
# Cada contraseña es un papá que no entra, y uno que no entra es uno que cancela.
#
# Viven en la base desde el 18/08. Eran un dict del proceso y eso rompía dos
# cosas: al reiniciar el servidor el papá perdía el acceso sin entender por qué,
# y el script que genera los reportes —otro proceso— no podía emitir un enlace
# válido, así que el correo semanal no tenía a dónde apuntar y nunca se mandó.

VIDA_ENLACE = timedelta(hours=24)


def _crear_enlace(nino_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _repo.crear_enlace(token, nino_id, datetime.now() + VIDA_ENLACE)
    return token


def _canjear(token: str) -> str:
    nino_id = _repo.canjear_enlace(token)
    if nino_id is None:
        raise HTTPException(401, "El enlace no vale o venció. Pide uno nuevo.")
    return nino_id


def papa_autenticado(token: str = Query(..., description="Token del enlace del mail")) -> str:
    """Devuelve el nino_id al que el enlace da acceso."""
    return _canjear(token)


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding — la conversación con el papá que da de alta a un niño
# ─────────────────────────────────────────────────────────────────────────────
# El motor vivía en pipeline.py con tests desde la fase 6 y no lo exponía nadie:
# el único niño de la base se había creado a mano. Sin esto no hay segundo
# usuario, y sin segundo usuario no hay producto.
#
# No es un formulario a propósito. Un papá contesta con matices ("le cuesta
# concentrarse cuando se frustra") que ninguna lista desplegable captura, y esos
# matices son lo que el tutor va a usar desde la primera sesión.
#
# ⚠️ En memoria: si el proceso se reinicia a mitad de la entrevista, el papá
# empieza de nuevo. Aceptable porque dura minutos y se rehace sin pérdida real;
# los enlaces del papá, que duran 24 horas, sí se movieron a la base.

_ONBOARDINGS: dict[str, list[tuple[str, str]]] = {}

_FICHAS_EN_CURSO: dict[str, FichaInicial] = {}
"""La ficha del turno ANTERIOR de cada entrevista.

Existe para poder lanzar la extracción y la pregunta a la vez. La pregunta
necesita saber qué falta, y esperar a la extracción para averiguarlo costaba
3,5 s de los 7,2 que tardaba cada turno (medido el 20/08). Con la ficha previa
alcanza: es una PISTA de qué falta, no la verdad — la verdad está en la
conversación, que el entrevistador lee entera y sí tiene el último mensaje."""


def _exigir_entrevistador() -> None:
    """Sin modelo no hay entrevista, y hay que decirlo en vez de fingirla."""
    if not _HAY_ANALISTA:
        raise HTTPException(503, "El onboarding necesita ANTHROPIC_API_KEY configurada.")


@app.post("/api/onboarding", tags=["papá"])
def iniciar_onboarding():
    """Abre la entrevista y devuelve la primera pregunta."""
    _exigir_entrevistador()

    onboarding_id = f"onb_{secrets.token_urlsafe(9)}"
    historial: list[tuple[str, str]] = []
    ficha = FichaInicial()

    # La primera pregunta no depende de nada: la conversación está vacía y el
    # modelo devolvía siempre el mismo saludo. Gastábamos 3,5 s de Sonnet para
    # generar un "hola" en la pantalla que el papá ve PRIMERO. Ahora es
    # instantánea, y el entrevistador entra en el turno 2, cuando ya hay algo
    # que leer y su criterio sirve para algo.
    pregunta = primera_pregunta()
    historial.append(("tutor", pregunta))
    _ONBOARDINGS[onboarding_id] = historial
    _FICHAS_EN_CURSO[onboarding_id] = ficha

    return {"onboarding_id": onboarding_id, "pregunta": pregunta, "falta": ficha.falta()}


class RespuestaDelPapa(BaseModel):
    texto: str


@app.post("/api/onboarding/{onboarding_id}", tags=["papá"])
def responder_onboarding(onboarding_id: str, cuerpo: RespuestaDelPapa):
    """Un turno de la entrevista. Cuando alcanza para arrancar, crea al niño.

    La ficha se re-extrae del historial COMPLETO en cada turno en vez de irse
    acumulando por partes: el papá corrige sobre la marcha ("tiene siete... no,
    perdón, ocho") y solo la conversación entera dice cuál de los dos vale.
    """
    _exigir_entrevistador()

    historial = _ONBOARDINGS.get(onboarding_id)
    if historial is None:
        raise HTTPException(404, "Esa entrevista no está abierta. Hay que empezar de nuevo.")

    historial.append(("papa", cuerpo.texto))
    previa = _FICHAS_EN_CURSO.get(onboarding_id, FichaInicial())

    # Las dos llamadas a la vez. Eran secuenciales y sumaban 7,2 s por turno con
    # la pantalla en blanco — la primera impresión que se lleva un papá.
    #
    # Se pueden paralelizar porque la pregunta NO necesita la ficha fresca:
    # necesita la conversación, que ya incluye lo que el papá acaba de decir. La
    # ficha previa solo le dice por dónde iba. Si el papá acaba de dar el último
    # dato, el entrevistador lo ve en la conversación y no lo vuelve a pedir.
    with ThreadPoolExecutor(max_workers=2) as pool:
        tarea_ficha = pool.submit(extraer_ficha, historial, _cliente_analista)
        tarea_pregunta = pool.submit(siguiente_pregunta, historial, previa, _cliente_analista)
        ficha = tarea_ficha.result()
        pregunta = tarea_pregunta.result()

    if not ficha.completa:
        _FICHAS_EN_CURSO[onboarding_id] = ficha
        historial.append(("tutor", pregunta))
        return {"listo": False, "pregunta": pregunta, "falta": ficha.falta()}

    nino = crear_nino_desde_ficha(ficha, f"n_{secrets.token_urlsafe(6)}")
    _repo.guardar_nino(nino)
    _ONBOARDINGS.pop(onboarding_id, None)
    _FICHAS_EN_CURSO.pop(onboarding_id, None)

    # El cierre NO se le vuelve a pedir al modelo: sería una tercera llamada de
    # 3,5 s justo en el momento en que el papá ya quiere entrar. Se arma con los
    # datos de la ficha, que es exactamente lo que el papá quiere oír de vuelta
    # —y como sale de la ficha, no puede afirmar nada que él no haya dicho.
    return {
        "listo": True,
        "nino_id": nino.id,
        "nombre": nino.nombre,
        # El enlace del NIÑO, con su credencial. Es lo que el papá tiene que
        # guardar: sin esto el alta termina y nadie puede entrar.
        "enlace_del_nino": _url_del_nino(nino),
        "mensaje": _despedida(ficha),
    }


def _despedida(ficha: FichaInicial) -> str:
    """Lo que el papá lee al terminar la entrevista. Solo datos que él dio."""
    partes = [
        f"Listo. {ficha.nombre_nino}, {ficha.edad} años, {ficha.grado}° grado.",
    ]
    if ficha.intereses:
        partes.append(f"Le gusta {', '.join(ficha.intereses[:3])}.")
    if ficha.dificultades:
        partes.append(f"Y me contaste que le cuesta {ficha.dificultades[0]}.")
    partes.append(
        f"Con eso arrancamos. El reporte te llega a {ficha.email_papa} cada semana, "
        "y ahí mismo te aviso si algo necesita tu atención."
    )
    return " ".join(partes)


# ─────────────────────────────────────────────────────────────────────────────
# Sesión del niño
# ─────────────────────────────────────────────────────────────────────────────


class AbrirSesion(BaseModel):
    nino_id: str
    modo: ModoSesion = ModoSesion.GUIADO
    token: str | None = None
    """La credencial del niño, del enlace que recibió el papá.

    Es `None`-able en el modelo y obligatoria en la práctica: así el 401 lo da
    la comprobación de abajo, con su mensaje, en vez de un 422 de validación
    que no le dice nada a nadie."""


@app.post("/api/sesiones", tags=["niño"])
def abrir_sesion(cuerpo: AbrirSesion):
    """Devuelve el TOKEN de voz, no la configuración.

    El navegador no puede cambiar la persona, el playbook ni la política de
    seguridad (candado #1).

    Y hay que probar quién es. Hasta el 22/08 esto abría sesión con cualquier
    `nino_id` que le mandaran: se podía quemar la cuota de un niño ajeno, leer
    los ejercicios que le tocaban hoy y, sobre todo, **obtener un token efímero
    de Gemini** sin credencial ninguna. El `nino_id` viaja en la URL de la app
    y no es un secreto — nunca lo fue, y `nino.ts` ya lo decía: *«no es
    autenticación y no pretende serlo»*.
    """
    nino = _repo.obtener_nino(cuerpo.nino_id)
    # Mismo 401 para "no existe" y "token que no cuadra": distinguirlos
    # convertiría esto en un oráculo para enumerar niños.
    if (
        nino is None
        or not nino.token_acceso
        or not secrets.compare_digest(cuerpo.token or "", nino.token_acceso)
    ):
        raise HTTPException(401, "Enlace inválido. Pídele a tu papá o mamá el enlace de nuevo.")

    try:
        return _orquestador.abrir(cuerpo.nino_id, cuerpo.modo)
    except ErrorPresupuesto as e:
        raise HTTPException(429, str(e)) from e
    except ErrorSesion as e:
        raise HTTPException(400, str(e)) from e


class TurnosReportados(BaseModel):
    turnos: list[Turno]


@app.post("/api/sesiones/{sesion_id}/turnos", tags=["niño"])
def reportar_turnos(sesion_id: str, cuerpo: TurnosReportados):
    """Candado #2: reportar es lo que habilita recargar ejercicios.

    Dispara los dos niveles de seguridad. Si alguno escala, se avisa al papá
    EN EL MOMENTO — no el domingo.
    """
    try:
        alertas = _orquestador.registrar_turnos(sesion_id, cuerpo.turnos)
    except ErrorSesion as e:
        raise HTTPException(404, str(e)) from e

    if any(a.requiere_escalamiento for a in alertas):
        _avisar_al_papa(sesion_id)

    return {"alertas": alertas}


@app.post("/api/sesiones/{sesion_id}/recargar", tags=["niño"])
def recargar(sesion_id: str) -> list[Ejercicio]:
    try:
        return _orquestador.recargar_ejercicios(sesion_id)
    except ErrorSesion as e:
        raise HTTPException(409, str(e)) from e


@app.post("/api/sesiones/{sesion_id}/latido", status_code=204, tags=["niño"])
def latido(sesion_id: str):
    """La pestaña avisa que sigue ahí. Lo que le da ojos al reaper.

    No alcanza con mirar los turnos: un niño dibujando dos minutos en la hoja no
    dice nada, y sin latido el reaper lo tomaría por muerto justo mientras
    trabaja. Ver `SessionOrchestrator.latido` y `ABANDONO_SEG`.

    No falla nunca: si la sesión ya no existe, un latido de más no rompe nada y
    devolver un error solo pondría al navegador a reintentar contra el vacío.
    """
    _orquestador.latido(sesion_id)


@app.post("/api/sesiones/{sesion_id}/reconectar", tags=["niño"])
def reconectar(sesion_id: str):
    """Un token de voz nuevo para la misma sesión, cuando se cae el canal.

    El niño no tiene que empezar de cero porque se murió un socket. No cobra
    presupuesto ni replanifica: es la misma sesión, con el mismo objetivo y los
    mismos ejercicios ya cargados. Ver `SessionOrchestrator.reconectar`.

    409 y no 404: que no se pueda reconectar no es "no existe" — es "esto ya no
    se puede recuperar, abrí una nueva". El navegador los trata distinto.
    """
    try:
        return _orquestador.reconectar(sesion_id)
    except ErrorSesion as e:
        raise HTTPException(409, str(e)) from e


class CerrarSesion(BaseModel):
    interrumpida: bool = False
    tokens_consumidos: int = 0
    motivo: str | None = None
    """POR QUÉ terminó, dicho por quien la cierra. Ver `Sesion.motivo_cierre`."""


@app.post("/api/sesiones/{sesion_id}/cerrar", tags=["niño"])
def cerrar_sesion(sesion_id: str, cuerpo: CerrarSesion, fondo: BackgroundTasks):
    try:
        sesion = _orquestador.cerrar(
            sesion_id,
            interrumpida=cuerpo.interrumpida,
            tokens_consumidos=cuerpo.tokens_consumidos,
            motivo=cuerpo.motivo,
        )
    except ErrorSesion as e:
        raise HTTPException(404, str(e)) from e

    # Cierra el circuito adaptativo FUERA del camino de respuesta: el Analista lee
    # la transcripción recién guardada y escribe el dominio. Corre después de que
    # el niño ya recibió el 200, así que nunca lo hace esperar.
    if _HAY_ANALISTA:
        fondo.add_task(procesar_sesion, _repo, _grafo, sesion, _cliente_analista)

    return sesion


# ─────────────────────────────────────────────────────────────────────────────
# Tools — los reenvía el navegador durante la conversación
# ─────────────────────────────────────────────────────────────────────────────
# ~100ms, ocasional (cada 30-60s), no en cada turno. La regla de oro se sostiene:
# la respuesta hablada del tutor no espera a nuestra infraestructura.


class VerificarRespuesta(BaseModel):
    sesion_id: str
    ejercicio_id: str
    respuesta_nino: str = Field(description="Lo que dijo el niño, sin interpretar")


@app.post("/api/tools/check_answer", tags=["tools"])
def tool_check_answer(cuerpo: VerificarRespuesta):
    """La aritmética JAMÁS la valida un modelo.

    Vive solo acá — nunca reimplementado en el navegador. Una sola
    implementación de lo que no puede estar mal.
    """
    try:
        banco = _orquestador.banco(cuerpo.sesion_id)
    except ErrorSesion as e:
        raise HTTPException(404, str(e)) from e

    ejercicio = next((e for e in banco.entregados if e.id == cuerpo.ejercicio_id), None)
    if ejercicio is None:
        raise HTTPException(404, f"Ejercicio '{cuerpo.ejercicio_id}' no fue entregado")

    habilidad = (
        _grafo.habilidad(ejercicio.habilidad_id)
        if _grafo.existe(ejercicio.habilidad_id)
        else None
    )
    resultado = check_answer(ejercicio, cuerpo.respuesta_nino, habilidad)
    return {
        "correcto": resultado.veredicto == Veredicto.CORRECTO,
        "veredicto": resultado.veredicto.value,
        "valor_interpretado": resultado.valor_interpretado,
        # Explícito y no deducido de `correcto: false`: si el modelo lo lee como
        # un error, corrige a un niño que quizá acertó.
        "no_se_entendio": resultado.veredicto == Veredicto.NO_SE_ENTENDIO,
    }


class VerificarCuenta(BaseModel):
    operacion: str = Field(description="La cuenta que improvisó el tutor. Ej: '578 - 34'")
    respuesta_nino: str = Field(description="Lo que dijo el niño, sin interpretar")


@app.post("/api/tools/verify_arithmetic", tags=["tools"])
def tool_verify_arithmetic(cuerpo: VerificarCuenta):
    """Lo mismo que `check_answer`, para lo que el tutor propone fuera del banco.

    No necesita sesión: es una función pura sobre dos strings. Lo que devuelve
    NUNCA incluye el resultado correcto — si el modelo lo tuviera, la tentación
    de decirlo en voz alta es el fracaso que el producto promete no tener.
    """
    r = verify_arithmetic(cuerpo.operacion, cuerpo.respuesta_nino)
    return {
        "correcto": r.veredicto == Veredicto.CORRECTO,
        "veredicto": r.veredicto.value,
        "valor_interpretado": r.valor_interpretado,
        "distancia": r.distancia.value if r.distancia else None,
    }


class VerificarLengua(BaseModel):
    palabra: str = Field(description="La palabra por la que preguntó el tutor")
    que: str = Field(description="Qué le preguntó: silabas, separar, inicial, rima…")
    respuesta_nino: str = Field(description="Lo que dijo el niño, sin interpretar")
    palabra2: str = Field(default="", description="Solo para `rima`: la segunda palabra")


@app.post("/api/tools/verify_language", tags=["tools"])
def tool_verify_language(cuerpo: VerificarLengua):
    """Lo mismo que `verify_arithmetic`, para lectura y escritura.

    Existe porque el 22/08, en una sesión de sílabas trabadas, el tutor llamó
    seis veces a `verify_arithmetic` —la única herramienta de verificar que
    tenía— y como no sabe nada de sílabas le devolvió REQUIERE_JUICIO las seis.
    Entonces el modelo juzgó él, y a un niño que separó «prim-o» le dijo
    «¡Perfecto!». Lo notó el niño.

    A diferencia de la aritmética, acá SÍ se devuelve lo correcto, pero solo
    cuando el niño ya se equivocó: la corrección de un silabeo no es «la
    respuesta» que arruina el ejercicio, y sin ella el tutor la inventa.
    """
    r = verify_language(cuerpo.palabra, cuerpo.que, cuerpo.respuesta_nino, cuerpo.palabra2)
    return {
        "correcto": r.veredicto == Veredicto.CORRECTO,
        "veredicto": r.veredicto.value,
        "valor_interpretado": r.valor_interpretado,
        "lo_correcto": r.lo_correcto,
    }


@app.post("/api/tools/get_next_problem", tags=["tools"])
def tool_get_next_problem(sesion_id: str, habilidad_id: str | None = None):
    """Sale del banco precargado en memoria. No toca la base.

    `habilidad_id` es el tema que pidió el niño. El tema lo elige él; el
    ejercicio sale del banco validado en código — nunca lo inventa el modelo.
    """
    try:
        banco = _orquestador.banco(sesion_id)
    except ErrorSesion as e:
        raise HTTPException(404, str(e)) from e

    ejercicio = banco.get_next_problem(habilidad_id)
    if ejercicio is None:
        # Se devuelven los temas que SÍ hay. Un "no tengo" a secas deja al tutor
        # sin nada que ofrecer, y sin nada que ofrecer improvisa.
        return {
            "ejercicio": None,
            "temas_disponibles": banco.temas,
            "mensaje": (
                f"No quedan ejercicios de '{habilidad_id}'."
                if habilidad_id
                else "Banco agotado."
            ),
        }
    return {"ejercicio": ejercicio, "se_agota": banco.se_esta_agotando()}


class EscalarSeguridad(BaseModel):
    sesion_id: str
    motivo: str
    evidencia: str | None = None


@app.post("/api/tools/escalate_safety", tags=["tools"])
def tool_escalate_safety(cuerpo: EscalarSeguridad):
    """El segundo camino a la alarma: lo levanta el tutor.

    Independiente del Vigilante. Cualquiera de los dos la dispara.
    """
    _avisar_al_papa(cuerpo.sesion_id)
    return {"escalado": True}


# ─────────────────────────────────────────────────────────────────────────────
# Panel del papá
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/api/ninos/{nino_id}/progreso", tags=["papá"])
def progreso(nino_id: str, autorizado: str = Depends(papa_autenticado)):
    """Sin jerga: ni 'nodos', ni 'grafo', ni 'dominio'. Temas y qué sabe hacer."""
    if autorizado != nino_id:
        raise HTTPException(403, "Ese enlace no da acceso a este niño")

    nino = _repo.obtener_nino(nino_id)
    if nino is None:
        raise HTTPException(404, "No existe el niño")

    ahora = datetime.now()
    domina, trabajando = [], []
    for hid, registro in nino.dominio.items():
        if not _grafo.existe(hid):
            continue
        nombre = _grafo.habilidad(hid).nombre.es
        (domina if esta_dominada(registro, ahora) else trabajando).append(nombre)

    return {
        "nombre": nino.nombre,
        "grado_escolar": nino.grado,
        "grado_de_trabajo": grado_de_trabajo(nino, _grafo, ahora),
        "adelanto_grados": adelanto(nino, _grafo, ahora),
        "ya_domina": sorted(domina),
        "esta_trabajando": sorted(trabajando),
        "intereses": nino.perfil.intereses,
    }


@app.get("/api/ninos/{nino_id}/cumplimiento", tags=["papá"])
def cumplimiento(nino_id: str, dias: int = 30, autorizado: str = Depends(papa_autenticado)):
    """La evidencia de que el método se sostuvo. Criterio #4 de YC.

    No es una métrica interna: es lo que le mostrás al papá cuando pregunta
    "¿cómo sé que no le está dando las respuestas?".
    """
    if autorizado != nino_id:
        raise HTTPException(403, "Ese enlace no da acceso a este niño")

    hasta = datetime.now()
    sesiones = _repo.sesiones_de(nino_id, hasta - timedelta(days=dias), hasta)
    return {
        "sesiones_en_el_periodo": len(sesiones),
        "sesiones_auditadas": sum(1 for s in sesiones if s.analizada),
        "dias": dias,
    }


def _nivel_al_cerrar(nino, sesion, ahora: datetime) -> float:
    """En qué nivel quedó la habilidad que esa sesión trabajó.

    Igual que en el reporte: solo la primera habilidad declarada. Atribuirle a
    la técnica el movimiento de todo lo que se tocó la premiaría por trabajo
    que no hizo.
    """
    if not sesion.habilidades_trabajadas:
        return sesion.dominio_inicial or 0.0
    registro = nino.dominio.get(sesion.habilidades_trabajadas[0])
    if registro is None:
        return sesion.dominio_inicial or 0.0
    return nivel_efectivo(registro, sesion.fin or ahora)


def _veredictos_de(sesiones: list) -> list:
    """Los veredictos del método que existen para estas sesiones.

    "Auditada" en el panel significa UNA sola cosa: que hay veredicto guardado.
    Contarlas por `analizada` (pasó por el Analista) daba una página que se
    contradecía sola — "todavía no hay sesiones auditadas" arriba y "2 auditadas
    por el método" abajo. En la superficie que existe para verificar, una
    contradicción visible cuesta más que el dato que aporta.
    """
    return [v for s in sesiones if (v := _repo.obtener_auditoria(s.id)) is not None]


def _metodo_sostenido(veredictos: list) -> float | None:
    """Fracción de sesiones donde el tutor NO regaló la respuesta. None si
    todavía no hay veredictos — no se inventa un 100% cuando no se midió nada."""
    if not veredictos:
        return None
    return sum(1 for v in veredictos if not v.regalo_la_respuesta) / len(veredictos)


@app.get("/panel/{nino_id}", response_class=HTMLResponse, tags=["papá"])
def panel_papa(nino_id: str, token: str = Query(...), dias: int = 30):
    """El panel del papá, renderizado en el servidor. El link inteligente cae acá.

    Superficie de VERIFICACIÓN: números en código contra la fuente, estables entre
    visitas. Ver panel.py para por qué no es un SPA ni un agente que genera HTML.
    """
    try:
        autorizado = _canjear(token)
    except HTTPException:
        return HTMLResponse(render_error("El enlace venció o no es válido. Pedí uno nuevo."), 401)
    if autorizado != nino_id:
        return HTMLResponse(render_error("Ese enlace no da acceso a este niño."), 403)

    nino = _repo.obtener_nino(nino_id)
    if nino is None:
        return HTMLResponse(render_error("No encontramos a ese niño."), 404)

    ahora = datetime.now()
    domina, trabajando = [], []
    for hid, registro in nino.dominio.items():
        if not _grafo.existe(hid):
            continue
        nombre = _grafo.habilidad(hid).nombre.es
        (domina if esta_dominada(registro, ahora) else trabajando).append(nombre)

    sesiones = _repo.sesiones_de(nino_id, ahora - timedelta(days=dias), ahora)
    veredictos = _veredictos_de(sesiones)
    reporte = _repo.ultimo_reporte(nino_id)

    # CÓMO se le está enseñando. Se calcula acá y no se lee del reporte porque
    # el panel se abre cuando el papá quiere: el reporte puede tener una semana
    # y el método haber cambiado ayer.
    metodo = cambio_de_metodo(
        _tecnicas,
        [
            (s.tecnica_id, s.dominio_inicial or 0.0, _nivel_al_cerrar(nino, s, ahora))
            for s in sesiones
        ],
    )

    html = render_panel(
        nombre=nino.nombre,
        grado_escolar=nino.grado,
        grado_de_trabajo=grado_de_trabajo(nino, _grafo, ahora),
        adelanto_grados=adelanto(nino, _grafo, ahora),
        ya_domina=sorted(domina),
        esta_trabajando=sorted(trabajando),
        intereses=nino.perfil.intereses,
        datos_suyos=nino.perfil.datos_suyos,
        contexto_escolar=nino.perfil.contexto_escolar,
        sesiones_total=len(sesiones),
        sesiones_auditadas=len(veredictos),
        metodo_sostenido=_metodo_sostenido(veredictos),
        dias=dias,
        metodo_actual=metodo.actual,
        porque_cambio=metodo.porque,
        reporte_narrativo=reporte.contenido if reporte else None,
        sugerencia_para_casa=reporte.sugerencia if reporte else None,
        generado_en=ahora,
    )
    return HTMLResponse(html)


class PedirEnlace(BaseModel):
    nino_id: str
    email: str


def _mismo_correo(uno: str, otro: str) -> bool:
    """Compara correos sin castigar por mayúsculas ni espacios de más.

    No normaliza más que eso a propósito: quitar puntos o lo que va detrás de
    un `+` es política de un proveedor concreto, y tratarlas como el mismo
    buzón haría que `papa+x@gmail.com` abriera el panel de un niño registrado
    con `papa@gmail.com`.
    """
    return uno.strip().casefold() == otro.strip().casefold()


@app.post("/api/auth/magic-link", tags=["papá"])
def pedir_enlace(cuerpo: PedirEnlace):
    """Manda el enlace del panel al correo REGISTRADO de ese niño.

    Hasta el 22/08 esto mandaba el enlace al correo que le pasaran, sin
    comprobar nada: quien conociera o adivinara un `nino_id` se enviaba a sí
    mismo acceso de 24 horas al panel de un menor — nombre, edad, grado,
    intereses, frustraciones, dominio y las notas de la auditoría.

    Y la respuesta es **la misma pase lo que pase**. Contestar "no existe ese
    niño" o "ese no es el correo" convertía este endpoint en un oráculo para
    enumerar niños y adivinar correos; el 404 de antes ya lo era.
    """
    nino = _repo.obtener_nino(cuerpo.nino_id)

    if (
        nino is not None
        and nino.email_papa
        and _mismo_correo(cuerpo.email, nino.email_papa)
    ):
        token = _crear_enlace(cuerpo.nino_id)
        _notificador.enviar(_enlace_de_acceso(cuerpo.email, nino, token))

    # Un niño sin `email_papa` no recibe enlace, y es correcto: si no hay a
    # quién avisar, tampoco hay a quién dejar entrar. El onboarding lo exige
    # desde hace fases; los que están vacíos son fichas viejas hechas a mano.
    return {"enviado": True}


# ─────────────────────────────────────────────────────────────────────────────
# Internos
# ─────────────────────────────────────────────────────────────────────────────

# El panel lo sirve ESTE backend (server-rendered), no el frontend del niño.
# En producción se apunta con URL_PUBLICA_BACKEND al dominio real.
BASE_PANEL = os.getenv("URL_PUBLICA_BACKEND", "http://localhost:8000") + "/panel"
URL_APP = os.getenv("URL_PUBLICA_BACKEND", "http://localhost:8000")


def _url_del_nino(nino: Nino) -> str:
    """El enlace con el que el niño entra, credencial incluida.

    Va el token y no solo el id porque el id nunca fue un secreto: viaja en la
    URL, se comparte por accidente y `nino.ts` lo dice desde el principio.
    """
    return f"{URL_APP}/?nino={nino.id}&t={nino.token_acceso or ''}"


def _url_panel(nino_id: str, token: str) -> str:
    return f"{BASE_PANEL}/{nino_id}?token={token}"


def _enlace_de_acceso(email: str, nino: Nino, token: str):
    from .notificaciones import Aviso

    return Aviso(
        destinatario=email,
        asunto=f"Tu acceso al panel de {nino.nombre}",
        cuerpo="Entrá con este enlace. Vence en 24 horas.",
        enlace=_url_panel(nino.id, token),
    )


def _avisar_al_papa(sesion_id: str) -> None:
    """Alerta INMEDIATA. Si el Vigilante escala un martes, el papá se entera
    el martes — no el domingo.

    El mail no lleva detalles: lo que el niño dijo se lee en el panel, con
    contexto. Un fragmento suelto asusta y desinforma.
    """
    sesion = _repo.obtener_sesion(sesion_id)
    if sesion is None:
        return
    nino = _repo.obtener_nino(sesion.nino_id)
    if nino is None:
        return

    token = _crear_enlace(nino.id)
    _notificador.enviar(
        aviso_de_alerta(_email_del_papa(nino), nino.nombre, _url_panel(nino.id, token))
    )


def _email_del_papa(nino: Nino) -> str:
    """El correo real del papá, que el onboarding exige y guarda.

    Esta función devolvía SIEMPRE el marcador de posición, con un docstring que
    decía que el campo "todavía no está en el modelo". Sí estaba: `email_papa`
    es obligatorio en `FichaInicial` y `crear_nino_desde_ficha` lo persiste
    desde entonces. O sea que la alerta de seguridad —el camino más urgente que
    tiene el producto— se despachaba a una dirección inventada aunque el papá
    tuviera la suya registrada. El reporte semanal ya leía el campo bien
    (`scripts/generar_reportes.py`); solo este quedó atrás.

    El marcador sobrevive para los niños creados antes del onboarding: sin él
    esto reventaría al alertar, y quedarse sin alerta es peor que mandarla a una
    casilla que no existe.
    """
    return nino.email_papa or f"papa+{nino.id}@pendiente.local"


@app.get("/api/salud", tags=["sistema"])
def salud():
    return {
        "ok": True,
        "habilidades": len(_grafo),
        "modelo_voz": cfg.MODELO_TUTOR_VOZ,
        # Con qué versión del frontend está hablando este backend. El navegador
        # la compara con la suya ANTES de abrir sesión — ver `build_servido`.
        "build": build_servido(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# La interfaz del niño, servida por el mismo proceso
# ─────────────────────────────────────────────────────────────────────────────
#
# Se monta AL FINAL, después de todas las rutas de la API: el `/` de StaticFiles
# se traga lo que no esté declarado antes.
#
# Por qué acá y no en el `vite dev`: el servidor de desarrollo entrega React sin
# minificar y los módulos sueltos, y esta app procesa audio PCM en tiempo real
# en el hilo del navegador. Con el build de producción la sesión va fluida; con
# el de desarrollo el niño siente que el tutor "se va a buscar la respuesta"
# (medido el 19/08 — ver ARCHITECTURE.md §9). El proxy de dev además mete un
# salto extra en cada tool call.
#
# `vite dev` sigue sirviendo para trabajar en la interfaz. Para HABLAR con el
# tutor se usa esto.

_WEB = cfg.RAIZ / "web" / "dist"


def build_servido() -> str | None:
    """Qué bundle hay en disco AHORA, leído del `index.html` construido.

    Es el nombre con hash que le pone Vite (`index-C1QkbTfb.js`): un número de
    versión del frontend que no hay que inventar ni acordarse de subir, porque
    cambia exactamente cuando cambia el código.

    EXISTE POR `ses_4ed4e930e60f` (23/08). El backend se reinició con la
    pizarra nueva —`cantidades`, para dibujar sumas— y el niño tenía la pestaña
    abierta desde antes, con el JavaScript viejo vivo en memoria. El log lo
    muestra sin lugar a dudas: `POST /api/sesiones` ANTES del primer `GET /`.

    Entonces el modelo pidió lo que el backend le dijo que podía pedir, el
    traductor viejo no lo entendió, y el tutor le dijo al niño:

        «no pude ponerte los pollitos en la pizarra»
        «como que el tablero no me quiere funcionar hoy»

    No fue un bug de la pizarra: fueron dos versiones hablando entre sí. Y es
    estructural — el backend define lo que el tutor PUEDE pedir y el navegador
    define lo que SABE dibujar, así que cada cambio de contrato rompe cualquier
    pestaña que lleve rato abierta, en silencio y del peor modo posible.

    Se lee del disco en cada llamada a propósito: un `npm run build` con el
    servidor corriendo tiene que notarse sin reiniciar. Si esto se cacheara,
    diría que todo está al día justo cuando dejó de estarlo.
    """
    indice = _WEB / "index.html"
    if not indice.is_file():
        return None
    m = re.search(r"/assets/(index-[A-Za-z0-9_-]+\.js)", indice.read_text(encoding="utf-8"))
    return m.group(1) if m else None

if _WEB.is_dir():
    from fastapi.staticfiles import StaticFiles

    # La de Starlette, NO la de FastAPI: `StaticFiles` lanza la suya, y la de
    # FastAPI es una subclase — atrapar la hija no atrapa a la madre.
    from starlette.exceptions import HTTPException as ErrorEstatico

    class _SPA(StaticFiles):
        """Sirve el bundle, y para una ruta que no es archivo devuelve el index.

        La interfaz decide qué pantalla mostrar mirando la URL, así que rutas
        como `/pizarra` no existen en el disco. Sin esto, `StaticFiles` devuelve
        404 y la pantalla no abre nunca.

        Solo cae acá lo que no matcheó ninguna ruta de la API, porque este
        montaje va al final de todo.

        `StaticFiles` **lanza** el 404, no lo devuelve: por eso se atrapa la
        excepción en vez de mirar `status_code`.
        """

        def is_not_modified(self, response_headers, request_headers=None) -> bool:
            """El `index.html` NUNCA sale de la caché del navegador.

            Es la otra mitad del arreglo de `ses_4ed4e930e60f`: de nada sirve
            detectar que el front está viejo si al recargar el navegador vuelve
            a entregar el mismo HTML de su caché, apuntando al mismo bundle
            viejo. El HTML es el único archivo sin hash en el nombre, así que es
            el único que puede quedar pegado.

            Los assets sí se cachean, y fuerte: llevan el hash adentro del
            nombre, así que un archivo nunca cambia de contenido — cambia de
            nombre. Eso lo dice `immutable` en `file_response`.
            """
            return False

        def file_response(self, full_path, stat_result, scope, status_code=200):
            respuesta = super().file_response(full_path, stat_result, scope, status_code)
            url = scope.get("path", "")
            if url.startswith("/assets/"):
                respuesta.headers["cache-control"] = "public, max-age=31536000, immutable"
            else:
                respuesta.headers["cache-control"] = "no-store, must-revalidate"
            return respuesta

        async def get_response(self, path: str, scope):
            try:
                return await super().get_response(path, scope)
            except ErrorEstatico as e:
                # `/api/…` que no existe sigue siendo 404. Devolverle el index a
                # un cliente que pidió JSON esconde el error: el navegador dice
                # 200, el JSON no parsea, y se pierde la tarde buscando en el
                # lugar equivocado.
                #
                # Se mira `scope["path"]` y no `path`: este último ya viene
                # convertido a ruta del sistema, y en Windows llega como
                # `api\no_existe` — con contrabarra. El `startswith("api/")`
                # nunca daba y el 404 se escapaba.
                url = scope.get("path", "")
                if e.status_code != 404 or url.startswith("/api/"):
                    raise
                return await super().get_response("index.html", scope)

    app.mount("/", _SPA(directory=_WEB, html=True), name="web")
