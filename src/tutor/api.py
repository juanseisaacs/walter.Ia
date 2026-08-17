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

import secrets
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import config as cfg
from .curriculum import cargar_grafo
from .models import Ejercicio, ModoSesion, Nino
from .notificaciones import Notificador, aviso_de_alerta, notificador_por_defecto
from .pedagogy import adelanto, esta_dominada, grado_de_trabajo
from .session import ErrorPresupuesto, ErrorSesion, Orquestador, Turno
from .storage import RepositorioSQLite
from .tools import Veredicto, check_answer
from .voice import emisor_por_defecto

app = FastAPI(title="RBH Tutor", version="0.1.0")

# Se arman una vez al arrancar, no por request.
_repo = RepositorioSQLite(cfg.DB, cfg.DATOS)
_grafo = cargar_grafo()
_orquestador = Orquestador(_repo, _grafo, emisor_por_defecto())
_notificador: Notificador = notificador_por_defecto()


# ─────────────────────────────────────────────────────────────────────────────
# Magic link — el papá no administra otra contraseña
# ─────────────────────────────────────────────────────────────────────────────
# Cada contraseña es un papá que no entra, y uno que no entra es uno que cancela.
#
# ⚠️ En memoria: sirve para un solo proceso. Al escalar a varios workers hay que
# moverlo a la base (una tabla `enlaces` con vencimiento).

_ENLACES: dict[str, tuple[str, datetime]] = {}
VIDA_ENLACE = timedelta(hours=24)


def _crear_enlace(nino_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _ENLACES[token] = (nino_id, datetime.now() + VIDA_ENLACE)
    return token


def _canjear(token: str) -> str:
    entrada = _ENLACES.get(token)
    if entrada is None:
        raise HTTPException(401, "Enlace inválido")
    nino_id, vence = entrada
    if datetime.now() > vence:
        _ENLACES.pop(token, None)
        raise HTTPException(401, "El enlace venció. Pedí uno nuevo.")
    return nino_id


def papa_autenticado(token: str = Query(..., description="Token del enlace del mail")) -> str:
    """Devuelve el nino_id al que el enlace da acceso."""
    return _canjear(token)


# ─────────────────────────────────────────────────────────────────────────────
# Sesión del niño
# ─────────────────────────────────────────────────────────────────────────────


class AbrirSesion(BaseModel):
    nino_id: str
    modo: ModoSesion = ModoSesion.GUIADO


@app.post("/api/sesiones", tags=["niño"])
def abrir_sesion(cuerpo: AbrirSesion):
    """Devuelve el TOKEN, no la configuración.

    El navegador no puede cambiar la persona, el playbook ni la política de
    seguridad (candado #1).
    """
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


class CerrarSesion(BaseModel):
    interrumpida: bool = False
    tokens_consumidos: int = 0


@app.post("/api/sesiones/{sesion_id}/cerrar", tags=["niño"])
def cerrar_sesion(sesion_id: str, cuerpo: CerrarSesion):
    try:
        return _orquestador.cerrar(
            sesion_id,
            interrumpida=cuerpo.interrumpida,
            tokens_consumidos=cuerpo.tokens_consumidos,
        )
    except ErrorSesion as e:
        raise HTTPException(404, str(e)) from e


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
    }


@app.post("/api/tools/get_next_problem", tags=["tools"])
def tool_get_next_problem(sesion_id: str):
    """Sale del banco precargado en memoria. No toca la base."""
    try:
        banco = _orquestador.banco(sesion_id)
    except ErrorSesion as e:
        raise HTTPException(404, str(e)) from e

    ejercicio = banco.get_next_problem()
    if ejercicio is None:
        raise HTTPException(409, "Banco agotado. Recargá reportando turnos.")
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


class PedirEnlace(BaseModel):
    nino_id: str
    email: str


@app.post("/api/auth/magic-link", tags=["papá"])
def pedir_enlace(cuerpo: PedirEnlace):
    """Manda un enlace al mail. Sin contraseñas."""
    nino = _repo.obtener_nino(cuerpo.nino_id)
    if nino is None:
        raise HTTPException(404, "No existe el niño")

    token = _crear_enlace(cuerpo.nino_id)
    _notificador.enviar(_enlace_de_acceso(cuerpo.email, nino, token))
    return {"enviado": True}


# ─────────────────────────────────────────────────────────────────────────────
# Internos
# ─────────────────────────────────────────────────────────────────────────────

BASE_PANEL = "http://localhost:5173/panel"


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
    """PENDIENTE: el mail del papá todavía no está en el modelo.

    Lo captura el Compañero del Papá durante el onboarding (fase pendiente).
    Hasta entonces, marcador de posición.
    """
    return f"papa+{nino.id}@pendiente.local"


@app.get("/api/salud", tags=["sistema"])
def salud():
    return {
        "ok": True,
        "habilidades": len(_grafo),
        "modelo_voz": cfg.MODELO_TUTOR_VOZ,
    }
