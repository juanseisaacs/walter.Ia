"""Aviso al papá: reporte semanal y alerta de seguridad.

Dos urgencias distintas por el MISMO canal — ver ARCHITECTURE.md §14:

  · Reporte  → domingo, tranquilo, un adelanto de dos líneas y un link
  · Alerta   → al instante. Si el Vigilante escala un martes, el papá no puede
               enterarse el domingo

El mail NO lleva el reporte completo. Además de que se lee mejor en el panel,
hay una razón de privacidad: los datos de aprendizaje de un menor no pueden
quedar para siempre en una bandeja de entrada, fuera de nuestra política de
retención.

Este archivo es el punto de cambio a WhatsApp — que para Colombia es el canal
correcto, pero tiene trámite de aprobación con Meta. Cuando llegue el momento,
se escribe otra implementación de `Notificador` y no se toca nada más.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from pydantic import BaseModel


class Aviso(BaseModel):
    destinatario: str
    asunto: str
    cuerpo: str
    enlace: str
    urgente: bool = False


class Notificador(ABC):
    @abstractmethod
    def enviar(self, aviso: Aviso) -> None: ...


class NotificadorFalso(Notificador):
    """Guarda en memoria. Para tests y para desarrollar sin proveedor de mail."""

    def __init__(self) -> None:
        self.enviados: list[Aviso] = []

    def enviar(self, aviso: Aviso) -> None:
        self.enviados.append(aviso)


class NotificadorConsola(Notificador):
    """Imprime en la terminal. Útil en desarrollo local."""

    def enviar(self, aviso: Aviso) -> None:
        marca = "[URGENTE] " if aviso.urgente else ""
        print(f"\n--- MAIL {marca}a {aviso.destinatario} ---")
        print(f"Asunto: {aviso.asunto}\n{aviso.cuerpo}\n{aviso.enlace}\n")


def notificador_por_defecto() -> Notificador:
    """Consola en dev; en prod habría que enchufar un proveedor real."""
    return NotificadorConsola() if os.getenv("ENTORNO", "dev") == "dev" else NotificadorConsola()


# ─────────────────────────────────────────────────────────────────────────────
# Armado de los dos avisos
# ─────────────────────────────────────────────────────────────────────────────


def aviso_de_reporte(
    email: str, nombre_nino: str, adelanto: str, enlace: str
) -> Aviso:
    """Dos líneas y un link. El reporte completo vive en el panel."""
    return Aviso(
        destinatario=email,
        asunto=f"El resumen de la semana de {nombre_nino}",
        cuerpo=adelanto,
        enlace=enlace,
        urgente=False,
    )


def aviso_de_alerta(email: str, nombre_nino: str, enlace: str) -> Aviso:
    """Al instante, y SIN detalles en el mail.

    Lo que el niño dijo no viaja por correo: se lee en el panel, con contexto y
    con la conversación completa. Un fragmento suelto en un mail asusta y
    desinforma.
    """
    return Aviso(
        destinatario=email,
        asunto=f"Necesitamos que veas algo de la sesión de {nombre_nino}",
        cuerpo=(
            f"Durante la sesión de hoy con {nombre_nino} apareció algo que "
            "conviene que revises. Entrá cuando puedas — está todo en el panel, "
            "con la conversación completa."
        ),
        enlace=enlace,
        urgente=True,
    )
