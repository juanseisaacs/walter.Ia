"""El cerebro: dominio, olvido, qué enseñar y cómo dar pistas.

Módulo PURO — sin red, sin I/O. Se testea en milisegundos.

Todo lo que hay acá podría haber sido un agente LLM y deliberadamente no lo es:
es cálculo, no criterio. Gratis, instantáneo, predecible, auditable. Con los
mismos datos da siempre la misma respuesta — y eso se puede explicar a un papá.

DECISIÓN CLAVE — el decaimiento se calcula al LEER, no al escribir:
    Se guarda `nivel` (el valor en la última práctica) y `ultima_practica`.
    El nivel actual es una función pura de esos dos datos más la fecha de hoy.
    La alternativa (un job que decae a todos todas las noches) exige un proceso
    corriendo, se rompe si no corre un día, y no es reproducible.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import IntEnum

from .curriculum import GrafoHabilidades
from .models import Habilidad, Nino, RegistroDominio, TipoObservacion

# ─────────────────────────────────────────────────────────────────────────────
# Parámetros del modelo de aprendizaje
# ─────────────────────────────────────────────────────────────────────────────

UMBRAL_DOMINIO = 0.80
"""A partir de acá la habilidad se considera dominada y desbloquea a las que dependen de ella."""

UMBRAL_REPASO = 0.60
"""Por debajo de acá, algo que estuvo dominado necesita repaso."""

TASA_APRENDIZAJE = 0.30
"""Cuánto mueve cada intento el nivel. Media móvil exponencial: lo reciente pesa más."""

VIDA_MEDIA_BASE_DIAS = 12.0
"""Días para olvidar la mitad de algo apenas aprendido y poco practicado.

Calibrado contra la realidad, no contra la curva de Ebbinghaus: esa mide sílabas
sin sentido. Una habilidad entendida y practicada se retiene muchísimo más.
Un chico que aprendió a contar hasta 100 no lo pierde en dos semanas."""

FACTOR_CONSOLIDACION = 6.0
"""Cuánto alarga la vida media el dominio alto. Lo bien aprendido se olvida más lento."""

FACTOR_REPETICION = 0.4
"""Cuánto alarga la vida media haber practicado muchas veces.

Es el principio del repaso espaciado: cada práctica exitosa estira el intervalo
hasta el próximo repaso. Crece logarítmicamente — las primeras repeticiones
consolidan mucho más que la décima."""


# ─────────────────────────────────────────────────────────────────────────────
# Dominio
# ─────────────────────────────────────────────────────────────────────────────


def valor_evidencia(acerto: bool, pistas_usadas: int) -> float:
    """Cuánto vale un intento como evidencia de dominio.

    Acertar con ayuda no es lo mismo que acertar solo. Si no se distingue, un
    niño que necesita tres pistas cada vez figura como que domina el tema.
    """
    if not acerto:
        return 0.0
    if pistas_usadas == 0:
        return 1.0
    if pistas_usadas == 1:
        return 0.70
    return 0.40


def actualizar_dominio(
    registro: RegistroDominio,
    acerto: bool,
    pistas_usadas: int = 0,
    ahora: datetime | None = None,
) -> RegistroDominio:
    """Registra un intento y recalcula el nivel.

    Parte del nivel EFECTIVO (ya decaído), no del guardado: si el niño volvió
    después de un mes, el intento se suma a lo que realmente recordaba.
    """
    ahora = ahora or datetime.now()
    base = nivel_efectivo(registro, ahora)
    evidencia = valor_evidencia(acerto, pistas_usadas)

    nuevo = base * (1 - TASA_APRENDIZAJE) + evidencia * TASA_APRENDIZAJE

    return registro.model_copy(
        update={
            "nivel": max(0.0, min(1.0, nuevo)),
            "intentos": registro.intentos + 1,
            "aciertos": registro.aciertos + (1 if acerto else 0),
            "pistas_necesitadas": registro.pistas_necesitadas + pistas_usadas,
            "primera_practica": registro.primera_practica or ahora,
            "ultima_practica": ahora,
        }
    )


def nivel_efectivo(registro: RegistroDominio, ahora: datetime | None = None) -> float:
    """Nivel de dominio HOY, aplicando olvido.

    Decaimiento exponencial. La vida media depende de dos cosas:
      · qué tan bien se aprendió  (nivel)
      · cuántas veces se practicó (aciertos, logarítmico)

    Lo entendido y repetido se olvida despacio; lo aprendido a medias y visto una
    vez, rápido. Un sistema que asume que el niño nunca olvida es falso y se nota
    rápido; uno que asume que olvida todo en dos semanas, también.
    """
    if registro.ultima_practica is None or registro.nivel <= 0.0:
        return registro.nivel

    ahora = ahora or datetime.now()
    dias = (ahora - registro.ultima_practica).total_seconds() / 86_400
    if dias <= 0:
        return registro.nivel

    consolidacion = 1 + registro.nivel * FACTOR_CONSOLIDACION
    repeticion = 1 + math.log1p(registro.aciertos) * FACTOR_REPETICION
    vida_media = VIDA_MEDIA_BASE_DIAS * consolidacion * repeticion

    return registro.nivel * (0.5 ** (dias / vida_media))


def esta_dominada(registro: RegistroDominio | None, ahora: datetime | None = None) -> bool:
    return registro is not None and nivel_efectivo(registro, ahora) >= UMBRAL_DOMINIO


def necesita_repaso(registro: RegistroDominio, ahora: datetime | None = None) -> bool:
    """Estuvo dominado y decayó. No aplica a lo que nunca se aprendió."""
    if registro.nivel < UMBRAL_DOMINIO:
        return False
    return nivel_efectivo(registro, ahora) < UMBRAL_REPASO


# ─────────────────────────────────────────────────────────────────────────────
# El planificador  (esto NO es un agente)
# ─────────────────────────────────────────────────────────────────────────────


def _registro(nino: Nino, habilidad_id: str) -> RegistroDominio:
    return nino.dominio.get(habilidad_id) or RegistroDominio(habilidad_id=habilidad_id)


def habilidades_para_repasar(
    nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> list[Habilidad]:
    """Lo que se dominó y se está olvidando. Repaso espaciado."""
    pendientes = [
        grafo.habilidad(hid)
        for hid, reg in nino.dominio.items()
        if grafo.existe(hid) and necesita_repaso(reg, ahora)
    ]
    return sorted(pendientes, key=lambda h: nivel_efectivo(_registro(nino, h.id), ahora))


def habilidades_disponibles(
    nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> list[Habilidad]:
    """La frontera: lo que el niño PUEDE aprender ahora.

    Prerrequisitos dominados y esta todavía no. Esto es lo que hace posible que
    el tutor sea adaptativo — una lista lineal no puede responder esta pregunta.
    """
    frontera = []
    for h in grafo:
        if esta_dominada(nino.dominio.get(h.id), ahora):
            continue
        if all(esta_dominada(nino.dominio.get(p), ahora) for p in h.prerequisitos):
            frontera.append(h)
    return frontera


def siguiente_habilidad(
    nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> Habilidad | None:
    """Qué trabajar ahora. Determinístico: mismos datos, misma respuesta.

    Prioridad:
      1. Repaso — lo olvidado bloquea todo lo que se apoya en ello
      2. Frontera, priorizando el grado del niño y el prerrequisito más firme

    Devuelve None solo si el niño dominó todo el grafo alcanzable.
    """
    if repasos := habilidades_para_repasar(nino, grafo, ahora):
        return repasos[0]

    disponibles = habilidades_disponibles(nino, grafo, ahora)
    if not disponibles:
        return None

    def prioridad(h: Habilidad) -> tuple:
        # SIN TECHO: subir de grado no se penaliza nunca. Solo se prefiere no
        # bajar, porque volver atrás sin necesidad aburre. Si el niño llegó a
        # contenido de tres grados más arriba, es porque tiene los
        # prerrequisitos — y entonces se lo gana.
        distancia_grado = max(0, nino.grado - h.grado_sugerido)
        # Con prerrequisitos más firmes, el próximo paso es más seguro
        firmeza = (
            min(nivel_efectivo(_registro(nino, p), ahora) for p in h.prerequisitos)
            if h.prerequisitos
            else 1.0
        )
        # Avance parcial primero: terminar lo empezado antes de abrir un frente nuevo
        avance = nivel_efectivo(_registro(nino, h.id), ahora)
        return (distancia_grado, -avance, -firmeza, h.id)

    return min(disponibles, key=prioridad)


# ─────────────────────────────────────────────────────────────────────────────
# Sin techo: dónde está realmente el niño
# ─────────────────────────────────────────────────────────────────────────────
# El grado escolar es una etiqueta administrativa, no un límite. El sistema
# mide dónde está el niño por lo que domina, y lo deja llegar tan lejos como
# pueda. Ver ARCHITECTURE.md §11.


def grado_de_trabajo(nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None) -> int:
    """En qué grado está trabajando el niño DE VERDAD.

    Es el grado más bajo que todavía no domina: lo que tiene enfrente. Un niño
    de 2° que ya dominó todo 2° trabaja en 3°, y así se lo reporta.
    """
    if disponibles := habilidades_disponibles(nino, grafo, ahora):
        return min(h.grado_sugerido for h in disponibles)
    grados = [h.grado_sugerido for h in grafo]
    return max(grados) if grados else nino.grado


def adelanto(nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None) -> int:
    """Grados por encima (+) o por debajo (−) del grado escolar.

    Positivo NO es un problema a corregir: es el producto funcionando.
    """
    return grado_de_trabajo(nino, grafo, ahora) - nino.grado


def va_adelantado(nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None) -> bool:
    """¿Amerita contárselo al papá?

    Es de lo más potente que puede leer: "tu hijo trabaja un grado por encima".
    """
    return adelanto(nino, grafo, ahora) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# La escalera socrática
# ─────────────────────────────────────────────────────────────────────────────


class NivelPista(IntEnum):
    """Escalones de ayuda, de menos a más concreto.

    NO EXISTE UN NIVEL "DAR LA RESPUESTA". Esa es la garantía del producto,
    y está codificada en el tipo: no se puede devolver algo que no existe.

    Si el niño sigue trabado en el último escalón, se resuelve un ejercicio
    PARECIDO juntos — nunca el suyo.
    """

    PREGUNTA_ABIERTA = 0
    """"¿Qué se te ocurre para empezar?" — cero información."""

    PREGUNTA_ORIENTADORA = 1
    """"¿Qué pasa con las unidades?" — dirige la atención, no revela."""

    PISTA_CONCEPTUAL = 2
    """"Acordate de qué pasa cuando las unidades pasan de 9." — recuerda la regla."""

    PISTA_CONCRETA = 3
    """"7 más 5 son 12. ¿Dónde ponés el 1?" — un paso resuelto, no el resultado."""

    EJEMPLO_PARALELO = 4
    """Resolver OTRO ejercicio parecido juntos, y volver al suyo."""


def siguiente_pista(intentos_fallidos: int) -> NivelPista:
    """A qué escalón subir según cuántas veces se trabó.

    Nunca pasa de EJEMPLO_PARALELO: la escalera no llega a la respuesta.
    """
    return NivelPista(min(max(intentos_fallidos, 0), NivelPista.EJEMPLO_PARALELO))


def hay_frustracion(observaciones: list[TipoObservacion], pistas_seguidas: int) -> bool:
    """¿Conviene bajar la exigencia antes de que abandone?

    Frustración explícita, o tres pistas seguidas sin salir adelante.
    """
    return TipoObservacion.FRUSTRACION in observaciones or pistas_seguidas >= 3


# ─────────────────────────────────────────────────────────────────────────────
# Resumen para el prompt de sesión
# ─────────────────────────────────────────────────────────────────────────────


def resumen_para_prompt(
    nino: Nino, grafo: GrafoHabilidades, ahora: datetime | None = None
) -> str:
    """Comprime la ficha a unas pocas líneas.

    El prompt de sesión se mantiene flaco (ARCHITECTURE.md §9): nunca la
    historia completa, nunca el currículum entero. Solo lo que cambia la
    conducta del tutor en ESTA sesión.
    """
    lineas = [f"{nino.nombre}, {nino.edad} años, {nino.grado}° grado."]

    dominadas = [hid for hid, reg in nino.dominio.items() if esta_dominada(reg, ahora)]
    if dominadas:
        lineas.append(f"Ya domina {len(dominadas)} habilidades.")

    if (delta := adelanto(nino, grafo, ahora)) >= 1:
        grados = "grado" if delta == 1 else "grados"
        lineas.append(
            f"VA ADELANTADO: ya trabaja {delta} {grados} por encima del suyo "
            f"(está en {grado_de_trabajo(nino, grafo, ahora)}°). "
            "No lo frenes ni bajes la exigencia — seguí subiendo mientras responda."
        )

    if (objetivo := siguiente_habilidad(nino, grafo, ahora)) is not None:
        lineas.append(f"Hoy: {objetivo.nombre.es} — {objetivo.descripcion.es}")

    if repasos := habilidades_para_repasar(nino, grafo, ahora):
        lineas.append("Conviene repasar: " + ", ".join(h.nombre.es for h in repasos[:3]) + ".")

    p = nino.perfil
    if p.intereses:
        lineas.append("Le gusta: " + ", ".join(p.intereses[:4]) + ".")
    if p.motivadores:
        lineas.append("Lo motiva: " + ", ".join(p.motivadores[:3]) + ".")
    if p.frustraciones:
        lineas.append("Lo traba: " + ", ".join(p.frustraciones[:3]) + ".")
    if p.estilo_comunicacion:
        lineas.append(f"Estilo: {p.estilo_comunicacion}.")
    if p.notas:
        lineas.append(p.notas)

    if p.madurez_vinculo < 3:
        lineas.append("Todavía lo conocés poco: preguntá y explorá.")

    return "\n".join(lineas)
