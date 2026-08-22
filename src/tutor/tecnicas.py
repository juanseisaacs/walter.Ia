"""El motor de técnicas: descubrir CÓMO le entra a este niño.

Módulo PURO — sin red, sin I/O más allá de leer los YAML al arrancar.

El planificador (`pedagogy`) contesta **qué** enseñarle hoy. Esto contesta la
otra mitad: **cómo**. Son preguntas distintas y hasta ahora solo había respuesta
para la primera — el tutor explicaba como le saliera, y si esa forma no le
entraba al niño, nadie se enteraba.

El ciclo es: se asigna una técnica → se mide si el dominio subió mientras estuvo
activa → si no subió en N sesiones, se abandona y entra su rival. Eso es lo que
convierte *«creemos que así se enseña mejor»* en *«con ésta subió y con la otra
no»*, que es lo que un papá puede preguntar y hay que poder contestar.

DECISIÓN DE DISEÑO — la técnica se ASIGNA, no se infiere:
    Otros sistemas puntúan técnicas contra señales que un modelo extrae de la
    conversación. Acá no: la elige el backend al abrir la sesión, igual que
    elige la habilidad, y la evidencia sale de la tabla `dominio` que ya se
    llena sola.

    Es a propósito y tiene precio. Se pierde poder para *predecir* cuál probar
    primero; se gana no tocar el esquema del Analista, que es la operación que
    la fase 7 dejó marcada como la más cara (`BITACORA.md`: agregar un campo a
    esa salida tumbó una suite de evals de 4/4 a 0/4).

    Y se pierde menos de lo que parece: predecir solo dice por dónde empezar a
    probar. Quien decide es la ganancia medida, y eso se puede hacer sin señales
    nuevas. El día que haya niños de verdad y datos para calibrar un predictor,
    se agrega encima de esto sin tirar nada.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from . import config as cfg

TECNICAS = cfg.KNOWLEDGE / "tecnicas"

SESIONES_PARA_JUZGAR = 3
"""Cuántas sesiones se le dan a una técnica antes de decidir si sirve.

Menos sería juzgar por un mal día: un niño cansado baja con cualquier método.
Más lo deja meses con algo que no le entra. Tres es lo que aguanta un papá
esperando a que el sistema "encuentre la forma", y es el mismo número que usan
otros sistemas del rubro — que no es evidencia, es un punto de partida a
calibrar cuando haya datos.
"""

GANANCIA_MINIMA = 0.05
"""Cuánto tiene que subir el dominio para que cuente como que la técnica sirve.

No es cero: el dominio se mueve solo con cualquier práctica, y tomar cualquier
movimiento como éxito haría que la primera técnica probada gane siempre.
"""


class ErrorTecnicas(Exception):
    """La biblioteca está mal. Falla ruidosamente: una biblioteca a medias
    elegiría entre las que sí cargaron y nadie lo notaría."""


class Evidencia(BaseModel):
    """De dónde sale que esta técnica funciona — y qué tan seguro es.

    `efecto_verificado` existe para no poder mentir por omisión. Si nadie
    contrastó el tamaño del efecto contra la fuente original, va en `false` y
    se ve. Es la misma regla que el currículum aplica con los DBA.
    """

    fuente: str
    respaldo: str
    efecto_verificado: bool = False
    adaptacion_es: str = ""
    """Si la evidencia viene en inglés, ¿transfiere al español? Obliga a
    contestarlo en vez de suponer que sí."""
    confianza_es: str = "media"


class Tecnica(BaseModel):
    """Una forma de enseñar. No un contenido: un método."""

    id: str
    nombre: str
    rival: str
    """Su opuesta. Es lo que hace que haya algo que elegir — si cada técnica
    cubriera un contenido distinto, esto sería un catálogo, no un motor."""

    aplica_a: list[str] = Field(default_factory=list)
    """Palabras que tienen que aparecer en el id de la habilidad. Vacío = todas."""

    como_ensena: str
    """Lo que entra al prompt de sesión. Es la técnica, en la práctica."""

    senal_de_que_funciona: str
    senal_de_que_no: str
    evidencia: Evidencia

    def sirve_para(self, habilidad_id: str) -> bool:
        if not self.aplica_a:
            return True
        return any(clave in habilidad_id for clave in self.aplica_a)


class Biblioteca:
    """Las técnicas disponibles, indexadas por id."""

    def __init__(self, tecnicas: list[Tecnica]) -> None:
        self._por_id: dict[str, Tecnica] = {}
        for t in tecnicas:
            if t.id in self._por_id:
                raise ErrorTecnicas(f"Técnica duplicada: {t.id}")
            self._por_id[t.id] = t

        if not self._por_id:
            raise ErrorTecnicas("La biblioteca de técnicas está vacía")

        # Los pares tienen que cerrar en las dos direcciones. Un rival colgado
        # deja al motor sin a dónde ir cuando abandona, y eso solo se descubre
        # con el niño enfrente, tres sesiones después.
        for t in self._por_id.values():
            rival = self._por_id.get(t.rival)
            if rival is None:
                raise ErrorTecnicas(f"{t.id} declara rival '{t.rival}', que no existe")
            if rival.rival != t.id:
                raise ErrorTecnicas(
                    f"{t.id} apunta a {rival.id}, pero {rival.id} apunta a {rival.rival}: "
                    f"los pares tienen que ser mutuos"
                )

    def __iter__(self):
        return iter(self._por_id.values())

    def __len__(self) -> int:
        return len(self._por_id)

    def existe(self, tecnica_id: str) -> bool:
        return tecnica_id in self._por_id

    def obtener(self, tecnica_id: str) -> Tecnica:
        if tecnica_id not in self._por_id:
            raise ErrorTecnicas(f"No existe la técnica '{tecnica_id}'")
        return self._por_id[tecnica_id]

    def para(self, habilidad_id: str) -> list[Tecnica]:
        """Las que tienen sentido con esta habilidad, en orden estable."""
        return sorted(
            (t for t in self._por_id.values() if t.sirve_para(habilidad_id)),
            key=lambda t: t.id,
        )


def cargar_biblioteca(directorio: Path | None = None) -> Biblioteca:
    """Lee `knowledge/tecnicas/*.yaml`. Falla ruidosamente si algo está mal."""
    directorio = directorio or TECNICAS
    if not directorio.is_dir():
        raise ErrorTecnicas(f"No existe el directorio de técnicas: {directorio}")

    tecnicas: list[Tecnica] = []
    for ruta in sorted(directorio.glob("*.yaml")):
        crudo = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        if not isinstance(crudo, list):
            raise ErrorTecnicas(f"{ruta.name}: se esperaba una lista de técnicas")
        for item in crudo:
            try:
                tecnicas.append(Tecnica.model_validate(item))
            except Exception as e:
                raise ErrorTecnicas(f"{ruta.name}: técnica inválida — {e}") from e

    return Biblioteca(tecnicas)


# ─────────────────────────────────────────────────────────────────────────────
# El ciclo: probar, medir, abandonar
# ─────────────────────────────────────────────────────────────────────────────


class Intento(BaseModel):
    """Lo que se sabe de una técnica con UN niño y UNA habilidad.

    Sale de las sesiones ya cerradas: cada una guardó qué técnica usó y en qué
    nivel de dominio arrancó. No hay tabla nueva ni nada que el Analista deba
    decir — es aritmética sobre lo que ya se persistía.
    """

    tecnica_id: str
    sesiones: int
    ganancia: float
    """Cuánto subió el dominio en total mientras esta técnica estuvo activa."""

    @property
    def funciono(self) -> bool:
        return self.ganancia >= GANANCIA_MINIMA

    @property
    def ya_se_juzgo(self) -> bool:
        """¿Tuvo sus tres sesiones? Antes de eso no se decide nada."""
        return self.sesiones >= SESIONES_PARA_JUZGAR

    @property
    def hay_que_abandonarla(self) -> bool:
        return self.ya_se_juzgo and not self.funciono


def medir(sesiones: list[tuple[str | None, float, float]]) -> dict[str, Intento]:
    """Qué pasó con cada técnica probada.

    Recibe, por sesión ya cerrada: `(tecnica_id, dominio_al_abrir, dominio_al_cerrar)`.
    Función pura: no toca la base. Así se puede recalcular sobre sesiones viejas
    sin volver a llamar a nadie, y se puede testear en microsegundos.
    """
    acumulado: dict[str, list[float]] = {}
    for tecnica_id, antes, despues in sesiones:
        if tecnica_id is None:
            continue  # sesión anterior al motor: no dice nada de ninguna técnica
        acumulado.setdefault(tecnica_id, []).append(despues - antes)

    return {
        tid: Intento(tecnica_id=tid, sesiones=len(gs), ganancia=round(sum(gs), 4))
        for tid, gs in acumulado.items()
    }


class Decision(BaseModel):
    """Qué técnica usar hoy, y por qué. El `porque` va al panel del papá."""

    tecnica_id: str
    porque: str
    es_nueva: bool = False
    """Primera sesión con esta técnica. Sirve para no prometerle al papá que
    'está funcionando' cuando todavía no se midió nada."""


def elegir(
    biblioteca: Biblioteca,
    habilidad_id: str,
    historial: dict[str, Intento],
    activa: str | None = None,
) -> Decision:
    """Con qué técnica se trabaja hoy.

    Determinístico: mismos datos, misma respuesta. Es la misma regla que el
    planificador — lo que decide algo sobre el niño se explica, y para
    explicarlo tiene que ser reproducible.

    El orden:
      1. Si la activa todavía sirve o no se juzgó, se sigue con ella. Cambiar de
         método cada sesión es lo mismo que no tener método.
      2. Si se agotó, entra su rival — que ataca lo mismo por el camino opuesto.
      3. Si el rival ya se probó y tampoco, cualquiera sin probar.
      4. Si se probaron todas, la que mejor anduvo. Ninguna sirvió mucho, pero
         volver a la menos mala es mejor que quedarse con la peor.
    """
    candidatas = biblioteca.para(habilidad_id)
    if not candidatas:
        raise ErrorTecnicas(f"Ninguna técnica aplica a '{habilidad_id}'")

    # 1. Seguir con la activa mientras tenga crédito.
    if activa and biblioteca.existe(activa):
        intento = historial.get(activa)
        if intento is None or not intento.hay_que_abandonarla:
            if intento is None:
                return Decision(tecnica_id=activa, porque="recién empieza", es_nueva=True)
            if intento.funciono:
                return Decision(
                    tecnica_id=activa,
                    porque=(
                        f"le está funcionando: +{intento.ganancia:.2f} "
                        f"en {intento.sesiones} sesión(es)"
                    ),
                )
            return Decision(
                tecnica_id=activa,
                porque=(
                    f"va {intento.sesiones} de {SESIONES_PARA_JUZGAR} sesiones; "
                    f"todavía no se juzga"
                ),
            )

        # 2. Se agotó: entra el rival.
        rival = biblioteca.obtener(activa).rival
        if biblioteca.existe(rival) and rival not in historial:
            return Decision(
                tecnica_id=rival,
                porque=(
                    f"con {activa} no se movió ({intento.ganancia:+.2f} en "
                    f"{intento.sesiones} sesiones); se prueba el camino opuesto"
                ),
                es_nueva=True,
            )

    # 3. Cualquiera sin probar.
    sin_probar = [t for t in candidatas if t.id not in historial]
    if sin_probar:
        return Decision(
            tecnica_id=sin_probar[0].id,
            porque=(
                "todavía no se ha probado con él" if historial
                else "primera técnica que se prueba"
            ),
            es_nueva=True,
        )

    # 4. Todas probadas: la mejor de las que hay.
    mejor = max(
        (t for t in candidatas),
        key=lambda t: historial[t.id].ganancia if t.id in historial else -999,
    )
    return Decision(
        tecnica_id=mejor.id,
        porque=f"de las probadas es la que mejor anduvo ({historial[mejor.id].ganancia:+.2f})",
    )


def bloque_para_prompt(tecnica: Tecnica) -> str:
    """Cómo entra la técnica al prompt de sesión.

    Va solo `como_ensena`. Ni el nombre, ni la evidencia, ni las señales: el
    tutor no tiene que saber que está siendo parte de un experimento, tiene que
    enseñar así. Decírselo gasta prompt y le da algo de qué hablar que no le
    incumbe al niño.
    """
    return f"# Cómo enseñas hoy\n\n{tecnica.como_ensena.strip()}"


class CambioDeMetodo(BaseModel):
    """Lo que se le cuenta al papá sobre CÓMO se le enseñó en el período.

    Los tres campos van calculados en código y llegan hechos al redactor: la
    frase que contesta *«¿por qué cambió de método?»* es la promesa del
    producto, y no puede depender de que un modelo la infiera bien.

    Todo en `None` cuando no hay nada que decir. Es la lección de la fase 6:
    "no lo medimos" se dice, no se completa con un default que parece un dato.
    """

    actual: str | None = None
    anterior: str | None = None
    porque: str | None = None


def cambio_de_metodo(
    biblioteca: Biblioteca, sesiones: list[tuple[str | None, float, float]]
) -> CambioDeMetodo:
    """Qué método se usó en el período, y si cambió, por qué.

    `sesiones` viene en orden cronológico, como `medir()`: cada una es
    `(tecnica_id, dominio_al_abrir, dominio_al_cerrar)`.

    Función pura. Se le pasan nombres al papá, no ids: "Empezar por lo
    concreto", no `concreto_primero`.
    """
    usadas = [t for t, _, _ in sesiones if t is not None and biblioteca.existe(t)]
    if not usadas:
        return CambioDeMetodo()

    actual_id = usadas[-1]
    actual = biblioteca.obtener(actual_id).nombre

    # El anterior es el último distinto del actual, mirando hacia atrás.
    anterior_id = next((t for t in reversed(usadas) if t != actual_id), None)
    if anterior_id is None:
        return CambioDeMetodo(actual=actual)

    anterior = biblioteca.obtener(anterior_id).nombre
    intento = medir(sesiones).get(anterior_id)
    if intento is None:  # no debería pasar, pero no se inventa una razón
        return CambioDeMetodo(actual=actual, anterior=anterior)

    return CambioDeMetodo(
        actual=actual,
        anterior=anterior,
        porque=(
            f"con «{anterior}» el nivel no se movió en {intento.sesiones} "
            f"sesiones, así que se pasó a «{actual}»"
        ),
    )
