"""La cadena de veredictos: que el papá pueda VERIFICAR, no solo confiar.

Módulo PURO — sin red, sin estado. Solo hashes y comparaciones.

El producto le promete al papá que el tutor nunca le da la respuesta a su hijo,
y le muestra un porcentaje. Hasta ahora ese número se sostenía en que nosotros
lo dijéramos: las auditorías vivían en archivos sueltos que cualquiera con
acceso al disco podía editar, borrar o inventar, y no había forma de notarlo.

Acá cada veredicto queda anotado en un registro **append-only encadenado por
SHA-256**: cada eslabón lleva el hash del anterior y la huella del veredicto que
certifica. Cambiar una sola letra de una auditoría vieja rompe la cadena desde
ese punto, y `verificar` dice exactamente dónde.

Eso convierte *«confía en nuestro reporte»* en *«verifica la cadena»*, que es
otra categoría de argumento delante de un papá, un colegio o un inversor.

**Lo que esto SÍ garantiza:** que el histórico no se pueda retocar sin dejar
rastro. Quien edite un veredicto para que el método se vea mejor de lo que fue,
rompe la cadena.

**Lo que NO garantiza:** que el veredicto original fuera correcto — eso lo
decide el Analista, y para eso están los evals. Y como la cadena vive en el
mismo disco, quien pueda reescribirla ENTERA desde cero puede fabricar una
consistente. Contra eso hace falta anclar el último hash fuera de casa (en el
correo semanal al papá, por ejemplo), y eso todavía no está.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

GENESIS = "genesis"
"""El eslabón cero. Un valor fijo y conocido: la cadena tiene que poder
verificarse de punta a punta sin depender de nada guardado aparte."""


def huella_de(contenido: str) -> str:
    """SHA-256 del veredicto tal como quedó escrito en su archivo.

    Se hashea el TEXTO, no el objeto ya parseado: así la huella también detecta
    que alguien edite el JSON a mano dejando los mismos valores pero cambiando
    el formato — y, sobre todo, no depende de cómo Pydantic decida serializar
    mañana. Un cambio de librería no puede invalidar la cadena entera.
    """
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


class Eslabon(BaseModel):
    """Un veredicto anotado en la cadena.

    No guarda el veredicto: guarda su huella. La cadena certifica los archivos,
    no los reemplaza — el panel del papá los sigue leyendo como siempre.
    """

    seq: int = Field(description="Posición en la cadena, desde 1")
    sesion_id: str
    huella: str = Field(description="SHA-256 del contenido de la auditoría")
    prev_hash: str = Field(description="El `hash` del eslabón anterior, o `genesis`")
    hash: str

    @staticmethod
    def _calcular(seq: int, sesion_id: str, huella: str, anterior: str) -> str:
        # El separador va explícito para que dos campos distintos no puedan
        # producir la misma cadena de bytes concatenados.
        material = "|".join([anterior, str(seq), sesion_id, huella])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @classmethod
    def forjar(cls, seq: int, sesion_id: str, contenido: str, anterior: str) -> Eslabon:
        huella = huella_de(contenido)
        return cls(
            seq=seq,
            sesion_id=sesion_id,
            huella=huella,
            prev_hash=anterior,
            hash=cls._calcular(seq, sesion_id, huella, anterior),
        )

    def hash_esperado(self) -> str:
        return self._calcular(self.seq, self.sesion_id, self.huella, self.prev_hash)


def leer_cadena(ruta: Path) -> list[Eslabon]:
    """Los eslabones en el orden en que se escribieron. Vacía si no existe."""
    if not ruta.exists():
        return []
    eslabones = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            eslabones.append(Eslabon.model_validate_json(linea))
    return eslabones


# ─────────────────────────────────────────────────────────────────────────────
# Verificación
# ─────────────────────────────────────────────────────────────────────────────


class Rotura(StrEnum):
    """Cómo se rompió. Cada una dice algo distinto de lo que pasó."""

    NO_ENCADENA = "no_encadena"
    """El `prev_hash` no es el hash del anterior: se insertó, se borró o se
    reordenó un eslabón."""

    HASH_ALTERADO = "hash_alterado"
    """El eslabón fue editado: su hash no corresponde a su contenido."""

    VEREDICTO_ALTERADO = "veredicto_alterado"
    """El archivo de la auditoría cambió después de anotarse. Es el caso que
    importa: alguien retocó el veredicto para que el método se viera mejor."""

    VEREDICTO_AUSENTE = "veredicto_ausente"
    """La cadena certifica una auditoría que ya no está en el disco. Puede ser
    un borrado deliberado, o el archivo perdido en una copia mal hecha."""

    SEQ_ROTA = "seq_rota"
    """La numeración salta. La cadena tiene que ser 1, 2, 3… sin huecos."""


class Hallazgo(BaseModel):
    """Dónde y qué se rompió."""

    seq: int
    sesion_id: str
    rotura: Rotura
    detalle: str = ""

    def __str__(self) -> str:
        return f"eslabón {self.seq} ({self.sesion_id}): {self.rotura.value}" + (
            f" — {self.detalle}" if self.detalle else ""
        )


class Veredicto(BaseModel):
    """El resultado de recorrer la cadena entera."""

    eslabones: int
    hallazgos: list[Hallazgo] = Field(default_factory=list)
    sin_anotar: list[str] = Field(default_factory=list)
    """Auditorías que están en el disco y NO en la cadena. No la rompen —son
    anteriores a que existiera— pero no las respalda nadie."""

    @property
    def integra(self) -> bool:
        return not self.hallazgos

    def resumen(self) -> str:
        if not self.eslabones:
            return "la cadena está vacía: ningún veredicto anotado todavía"
        estado = "ÍNTEGRA" if self.integra else f"ROTA en {len(self.hallazgos)} punto(s)"
        texto = f"{self.eslabones} veredicto(s) encadenados · {estado}"
        if self.sin_anotar:
            texto += f" · {len(self.sin_anotar)} auditoría(s) fuera de la cadena"
        return texto


def verificar(ruta_cadena: Path, ruta_auditorias: Path) -> Veredicto:
    """Recorre la cadena y contrasta cada eslabón con su archivo.

    Devuelve TODOS los hallazgos, no solo el primero: quien audita necesita ver
    el alcance de lo que se tocó, no el punto donde empezó.
    """
    eslabones = leer_cadena(ruta_cadena)
    hallazgos: list[Hallazgo] = []
    anterior = GENESIS

    for esperada, eslabon in enumerate(eslabones, start=1):
        if eslabon.seq != esperada:
            hallazgos.append(
                Hallazgo(
                    seq=eslabon.seq, sesion_id=eslabon.sesion_id, rotura=Rotura.SEQ_ROTA,
                    detalle=f"se esperaba {esperada}",
                )
            )

        if eslabon.prev_hash != anterior:
            hallazgos.append(
                Hallazgo(
                    seq=eslabon.seq, sesion_id=eslabon.sesion_id, rotura=Rotura.NO_ENCADENA,
                    detalle="alguien insertó, borró o reordenó un eslabón",
                )
            )

        if eslabon.hash != eslabon.hash_esperado():
            hallazgos.append(
                Hallazgo(
                    seq=eslabon.seq, sesion_id=eslabon.sesion_id, rotura=Rotura.HASH_ALTERADO,
                    detalle="el eslabón fue editado",
                )
            )

        archivo = ruta_auditorias / f"{eslabon.sesion_id}.json"
        if not archivo.exists():
            hallazgos.append(
                Hallazgo(
                    seq=eslabon.seq, sesion_id=eslabon.sesion_id, rotura=Rotura.VEREDICTO_AUSENTE,
                    detalle=f"falta {archivo.name}",
                )
            )
        elif huella_de(archivo.read_text(encoding="utf-8")) != eslabon.huella:
            hallazgos.append(
                Hallazgo(
                    seq=eslabon.seq, sesion_id=eslabon.sesion_id, rotura=Rotura.VEREDICTO_ALTERADO,
                    detalle="el veredicto cambió después de anotarse",
                )
            )

        # La cadena sigue con lo que el eslabón DICE, no con lo recalculado: así
        # una rotura se reporta una vez y no contamina a todos los siguientes.
        anterior = eslabon.hash

    anotadas = {e.sesion_id for e in eslabones}
    sin_anotar = sorted(
        a.stem
        for a in ruta_auditorias.glob("*.json")
        if a.stem not in anotadas and a.name != "cadena.jsonl"
    )

    return Veredicto(eslabones=len(eslabones), hallazgos=hallazgos, sin_anotar=sin_anotar)


def sembrar(ruta_cadena: Path, ruta_auditorias: Path, sesiones: list[str]) -> int:
    """Ancla auditorías que ya existían antes de que hubiera cadena.

    Se corre UNA vez, con las 41 auditorías que este repo acumuló antes del
    22/08. Deja constancia de lo que ya había — no puede probar que no se tocó
    nada antes de anclarlo, y por eso no se hace sola ni en silencio.

    `sesiones` viene en el orden en que ocurrieron: la cadena es un registro
    temporal, y sembrarla en orden de nombre de archivo la volvería mentira.
    """
    if leer_cadena(ruta_cadena):
        raise ValueError("la cadena ya tiene eslabones: sembrar la reescribiría")

    lineas, anterior, seq = [], GENESIS, 0
    for sesion_id in sesiones:
        archivo = ruta_auditorias / f"{sesion_id}.json"
        if not archivo.exists():
            continue
        seq += 1
        eslabon = Eslabon.forjar(
            seq=seq, sesion_id=sesion_id,
            contenido=archivo.read_text(encoding="utf-8"), anterior=anterior,
        )
        lineas.append(eslabon.model_dump_json())
        anterior = eslabon.hash

    if lineas:
        ruta_cadena.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return len(lineas)


def ultimo_hash(ruta_cadena: Path) -> str | None:
    """El extremo de la cadena. Publicarlo fuera del disco es lo que impediría
    reescribirla entera desde cero — hoy no se publica en ningún lado."""
    eslabones = leer_cadena(ruta_cadena)
    return eslabones[-1].hash if eslabones else None
