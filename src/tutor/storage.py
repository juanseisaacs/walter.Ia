"""Persistencia — "el mesero".

Todo acceso a datos pasa por la interfaz `Repositorio`. El resto de la app nunca
sabe si los datos vienen de un archivo, de SQLite o de un servidor.

El día que haya servidor (necesario para las tiendas), se escribe una nueva
implementación de esta interfaz y no se toca nada más.

Reparto de responsabilidades — ver ARCHITECTURE.md §8:
  · SQLite (data/tutor.db) → ficha del niño, sesiones, banco. Escritura concurrente.
  · Archivos JSON          → transcripciones, reportes. Append-only.
  · knowledge/ (git)       → currículum y prompts. NO pasa por acá.

La interfaz se mantiene chica: los métodos que se usan, no un ORM.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .cadena import GENESIS, Eslabon, leer_cadena
from .models import (
    AuditoriaCumplimiento,
    Calendario,
    Ejercicio,
    EstadoSesion,
    ModoSesion,
    Nino,
    PerfilPersonal,
    RegistroDominio,
    ReporteParaPapa,
    Sesion,
    TextoLocalizado,
)


class Repositorio(ABC):
    """Contrato de persistencia."""

    # ── Niños ────────────────────────────────────────────────────────────────

    @abstractmethod
    def obtener_nino(self, nino_id: str) -> Nino | None: ...

    @abstractmethod
    def ids_de_ninos(self) -> list[str]:
        """Los ids de todos los niños. Lo usan las tareas periódicas (el reporte
        semanal), que trabajan sobre la población y no sobre uno."""

    @abstractmethod
    def guardar_nino(self, nino: Nino) -> None:
        """Guarda la ficha completa (ambas mitades).

        Debe ser atómico: la sesión en vivo y el pipeline offline escriben la
        misma ficha. Sin atomicidad se pierde historial de aprendizaje en
        silencio — la razón por la que esto es SQLite y no un JSON.
        """

    # ── Sesiones ─────────────────────────────────────────────────────────────

    @abstractmethod
    @abstractmethod
    def crear_enlace(self, token: str, nino_id: str, vence: datetime) -> None: ...

    @abstractmethod
    def canjear_enlace(self, token: str, ahora: datetime | None = None) -> str | None:
        """nino_id si el enlace vale; None si no existe o venció."""

    @abstractmethod
    def crear_sesion(self, sesion: Sesion) -> None: ...

    @abstractmethod
    def obtener_sesion(self, sesion_id: str) -> Sesion | None: ...

    @abstractmethod
    def actualizar_sesion(self, sesion: Sesion) -> None:
        """Se llama también A MITAD de sesión, no solo al final.

        Si cae el modelo de voz, el estado guardado permite reanudar sin que el
        niño pierda su trabajo.
        """

    @abstractmethod
    def sesiones_sin_analizar(self) -> list[Sesion]:
        """Cola del Analista.

        IDEMPOTENCIA: filtra por `analizada == False`. Una sesión nunca se
        procesa dos veces (evita doble conteo de dominio).
        """

    @abstractmethod
    def sesiones_de(self, nino_id: str, desde: datetime, hasta: datetime) -> list[Sesion]:
        """Insumo del reporte semanal."""

    # ── Banco de ejercicios ──────────────────────────────────────────────────

    @abstractmethod
    def ejercicios_de(
        self, habilidad_id: str, limite: int = 15, tema: str | None = None
    ) -> list[Ejercicio]:
        """Precarga al INICIO de la sesión, nunca durante.

        Durante la sesión, `get_next_problem` saca de memoria: ~0ms.
        Solo devuelve ejercicios con `validado == True`.
        """

    @abstractmethod
    def guardar_ejercicios(self, ejercicios: list[Ejercicio]) -> None:
        """Escribe el banco. Lo llama scripts/build_exercise_bank.py."""

    @abstractmethod
    def habilidades_con_ejercicios(self) -> set[str]:
        """Qué habilidades tienen banco validado.

        La usa el planificador para no elegir un nodo sin ejercicios: la sesión
        abriría con nada que darle al niño y el tutor improvisaría. Es una
        consulta al abrir, no durante (§9)."""

    # ── Transcripciones (archivos) ───────────────────────────────────────────

    @abstractmethod
    def guardar_transcripcion(self, sesion_id: str, contenido: str) -> None: ...

    @abstractmethod
    def obtener_transcripcion(self, sesion_id: str) -> str | None:
        """Insumo del Analista. Puede no existir si ya pasó la retención."""

    @abstractmethod
    def anotar_en_diario(self, sesion_id: str, eventos: list[dict]) -> None:
        """El diario de la VOZ, que solo el navegador puede escribir.

        Todo lo que decide si una conversación se siente fluida pasa en la
        pestaña —cuánto tardó el modelo en contestar, cuánto tardó un tool, si
        el barge-in disparó, si el audio no sonó— y hasta el 25/08 vivía solo en
        la consola del navegador: se iba con la pestaña.

        Tres diagnósticos seguidos ese día terminaron en una hipótesis por eso.
        El backend responde en 4 ms y no ve nada de esto; la transcripción llega
        por otro camino y se ve igual de sana. Ver `revisar_sesion`.
        """

    @abstractmethod
    def leer_diario(self, sesion_id: str) -> list[dict]:
        """Los eventos que reportó la pestaña, en orden. Vacío si no hay."""

    @abstractmethod
    def borrar_transcripciones_anteriores_a(self, fecha: datetime) -> int:
        """Política de retención de datos de menores (Ley 1581 CO / COPPA US).

        El activo es la ficha estructurada, no la conversación cruda. Una vez que
        el Analista extrajo las señales, la transcripción ya cumplió su función.

        Devuelve cuántas borró.
        """

    # ── Reportes ─────────────────────────────────────────────────────────────

    @abstractmethod
    def guardar_reporte(self, reporte: ReporteParaPapa) -> None: ...

    @abstractmethod
    def ultimo_reporte(self, nino_id: str) -> ReporteParaPapa | None:
        """El reporte más reciente que se le mostró al papá. None si no hay."""

    # ── Auditoría de cumplimiento (por sesión) ───────────────────────────────

    @abstractmethod
    def guardar_auditoria(self, sesion_id: str, cumplimiento: AuditoriaCumplimiento) -> None:
        """El veredicto del método, sesión a sesión. Es la evidencia durable que
        sostiene el "¿le está dando las respuestas?" del panel — sobrevive al
        borrado de la transcripción, porque son booleanos, no la charla cruda."""

    @abstractmethod
    def obtener_auditoria(self, sesion_id: str) -> AuditoriaCumplimiento | None: ...


# ─────────────────────────────────────────────────────────────────────────────
# Esquema
# ─────────────────────────────────────────────────────────────────────────────

VERSION_ESQUEMA = 7

_ESQUEMA_V1 = """
CREATE TABLE ninos (
    id          TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    edad        INTEGER NOT NULL,
    grado       INTEGER NOT NULL,
    idioma      TEXT NOT NULL DEFAULT 'es',
    perfil      TEXT NOT NULL,               -- PerfilPersonal como JSON: es un
    creado_en   TEXT                         -- documento, nunca se consulta por dentro
);

-- El dominio SÍ es tabla propia: es la consulta caliente del planificador.
CREATE TABLE dominio (
    nino_id             TEXT NOT NULL REFERENCES ninos(id) ON DELETE CASCADE,
    habilidad_id        TEXT NOT NULL,
    nivel               REAL NOT NULL DEFAULT 0.0,
    intentos            INTEGER NOT NULL DEFAULT 0,
    aciertos            INTEGER NOT NULL DEFAULT 0,
    pistas_necesitadas  INTEGER NOT NULL DEFAULT 0,
    primera_practica    TEXT,
    ultima_practica     TEXT,
    PRIMARY KEY (nino_id, habilidad_id)
);

CREATE TABLE sesiones (
    id                      TEXT PRIMARY KEY,
    nino_id                 TEXT NOT NULL REFERENCES ninos(id) ON DELETE CASCADE,
    modo                    TEXT NOT NULL,
    estado                  TEXT NOT NULL,
    inicio                  TEXT NOT NULL,
    fin                     TEXT,
    habilidades_trabajadas  TEXT NOT NULL DEFAULT '[]',
    tokens_consumidos       INTEGER NOT NULL DEFAULT 0,
    analizada               INTEGER NOT NULL DEFAULT 0
);

-- Cola del Analista: parcial, porque solo interesan las no analizadas.
CREATE INDEX idx_sesiones_sin_analizar ON sesiones(analizada) WHERE analizada = 0;
CREATE INDEX idx_sesiones_nino_inicio  ON sesiones(nino_id, inicio);

CREATE TABLE ejercicios (
    id            TEXT PRIMARY KEY,
    habilidad_id  TEXT NOT NULL,
    enunciado     TEXT NOT NULL,
    respuesta     TEXT NOT NULL,
    tema          TEXT,
    validado      INTEGER NOT NULL DEFAULT 0
);

-- Precarga al inicio de sesión: solo ejercicios validados.
CREATE INDEX idx_ejercicios_precarga ON ejercicios(habilidad_id, tema) WHERE validado = 1;
"""


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de conversión
# ─────────────────────────────────────────────────────────────────────────────
# SQLite no tiene tipo fecha. Se guarda ISO-8601 y se convierte a mano: los
# adaptadores automáticos de sqlite3 están deprecados desde Python 3.12.


def _fecha_a_texto(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None


def _texto_a_fecha(valor: str | None) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None


# ─────────────────────────────────────────────────────────────────────────────
# Implementación
# ─────────────────────────────────────────────────────────────────────────────


_ESQUEMA_V2 = """
CREATE TABLE enlaces (
    token    TEXT PRIMARY KEY,
    nino_id  TEXT NOT NULL,
    vence    TEXT NOT NULL,
    FOREIGN KEY (nino_id) REFERENCES ninos(id) ON DELETE CASCADE
);
CREATE INDEX idx_enlaces_vence ON enlaces(vence);
"""

_ESQUEMA_V7 = """
ALTER TABLE sesiones ADD COLUMN motivo_cierre TEXT;
"""
"""POR QUÉ terminó la sesión. Antes se perdía, y eso costaba caro.

Todo cierre pasaba por un booleano —`interrumpida`— así que una sesión que el
niño terminó, una que se pasó del techo de tokens, una pestaña que se cerró y un
socket muerto quedaban todas iguales en la base.

Cada vez que RBH decía «se desapareció», averiguar por qué era una investigación
forense de media hora sobre el log del servidor, y terminaba en una hipótesis.
Cuatro veces seguidas. La quinta se contesta con un `SELECT`.

Aditiva y sin default: lo anterior queda en NULL, que es la verdad — de esas
sesiones no sabemos por qué terminaron y no vamos a inventarlo."""

_ESQUEMA_V6 = """
ALTER TABLE ninos ADD COLUMN token_acceso TEXT;
UPDATE ninos SET token_acceso = lower(hex(randomblob(16))) WHERE token_acceso IS NULL;
"""
"""La credencial del niño.

El `UPDATE` no es opcional: las fichas que ya existían quedarían sin token y
sus niños no podrían entrar. Se les genera uno acá mismo, dentro de la misma
migración, para que no haya un instante en que la columna exista vacía.

`randomblob(16)` son 128 bits del generador de SQLite. No es un secreto de alto
valor —da acceso a las sesiones de UN niño, no a los datos del papá— pero tiene
que ser imposible de adivinar, que es justo lo que le faltaba al `nino_id`.
"""

_ESQUEMA_V5 = """
ALTER TABLE ninos ADD COLUMN email_papa TEXT;
"""
"""El correo del papá, que se guardaba en el modelo y NO en la base.

`Nino.email_papa` existía desde hacía fases, `FichaInicial` lo declaraba
obligatorio y `crear_nino_desde_ficha` lo poblaba — pero la tabla `ninos` nunca
tuvo la columna, así que al releer la ficha volvía en `None`. Siempre.

Es la lección de la fase 4 con otra cara: dos definiciones del mismo concepto
—el modelo Pydantic y el esquema SQL— que se separan sin que nadie avise.
`test_el_modelo_del_nino_y_la_tabla_no_se_desincronizan` lo cierra.

Y tenía una consecuencia que no era menor: `_email_del_papa` se "arregló" el
21/08 para leer este campo en vez de un marcador de posición, con un docstring
que afirmaba que ya se persistía. No se persistía. **La alerta de seguridad
siguió yendo a una dirección inventada todo este tiempo.**
"""

_ESQUEMA_V4 = """
ALTER TABLE sesiones ADD COLUMN tecnica_id TEXT;
ALTER TABLE sesiones ADD COLUMN dominio_inicial REAL;
"""
"""Qué técnica se usó y en qué nivel arrancó la habilidad del día.

Los dos juntos son todo lo que el motor de técnicas necesita para medir: la
ganancia de una técnica es la suma de `dominio_final - dominio_inicial` de las
sesiones donde estuvo activa, y el dominio final ya vive en la tabla `dominio`.

Aditiva y sin default: las sesiones anteriores al motor quedan en NULL, que es
lo correcto — no dicen nada de ninguna técnica y `medir()` las ignora. Poner un
cero habría sido inventar que arrancaron sin dominio.
"""

_ESQUEMA_V3 = """
ALTER TABLE ninos ADD COLUMN calendario TEXT NOT NULL DEFAULT 'A';
"""
"""El calendario escolar del colegio (A o B).

Migración puramente aditiva: `ADD COLUMN` con default no reescribe filas ni
puede perder datos, y las fichas que ya existían quedan en 'A', que es el
calendario de la mayoría de los colegios del país. Un niño de calendario B se
corrige editando su ficha, no migrando nada.

Va como columna y no dentro del JSON de `perfil` porque es un dato
administrativo del mismo orden que `grado`, no algo que el Analista deduzca de
oír al niño.
"""
"""Los enlaces mágicos del papá.

Vivían en un dict del proceso de la API. Dos cosas se rompían con eso: al
reiniciar el servidor el papá perdía el acceso sin entender por qué, y el script
que genera los reportes —otro proceso— no podía emitir un enlace válido, así que
el correo semanal no tenía a dónde apuntar y nunca se mandó.

Se guarda el token tal cual y no un hash: da acceso de lectura al panel de un
solo niño, vence en 24 horas, y quien pueda leer esta tabla ya tiene la ficha
completa delante. Cuando haya cuentas de verdad, esto se revisa."""


class RepositorioSQLite(Repositorio):
    """SQLite + archivos JSON.

    SQLite NO es un servidor — es un archivo. Sin proceso, sin Docker, sin
    connection string. Se copia, se versiona, se borra como cualquier archivo.

    Configuración que importa (y por qué):
      · WAL          → un escritor y varios lectores a la vez sin bloquearse.
                       Es lo que evita el 'database is locked' de la sesión en
                       vivo compitiendo con el pipeline offline.
      · busy_timeout → si hay contención, espera en vez de fallar al instante.
      · foreign_keys → SQLite las ignora salvo que se pidan explícitamente.
    """

    ESPERA_BLOQUEO_MS = 5_000

    def __init__(self, ruta_db: Path, ruta_datos: Path) -> None:
        self.ruta_db = Path(ruta_db)
        self.ruta_datos = Path(ruta_datos)
        self.ruta_transcripciones = self.ruta_datos / "transcripts"
        self.ruta_reportes = self.ruta_datos / "reports"
        self.ruta_auditorias = self.ruta_datos / "audits"

        self.ruta_db.parent.mkdir(parents=True, exist_ok=True)
        self.ruta_transcripciones.mkdir(parents=True, exist_ok=True)
        self.ruta_reportes.mkdir(parents=True, exist_ok=True)
        self.ruta_auditorias.mkdir(parents=True, exist_ok=True)

        self._migrar()

    # ── Conexión ─────────────────────────────────────────────────────────────

    @contextmanager
    def _conectar(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.ruta_db, timeout=self.ESPERA_BLOQUEO_MS / 1000)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute(f"PRAGMA busy_timeout = {self.ESPERA_BLOQUEO_MS}")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _migrar(self) -> None:
        """Migraciones por `PRAGMA user_version`. Sin dependencias externas."""
        with self._conectar() as con:
            con.execute("PRAGMA journal_mode = WAL")  # persistente en el archivo
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version < 1:
                con.executescript(_ESQUEMA_V1)
            if version < 2:
                con.executescript(_ESQUEMA_V2)
            if version < 3:
                con.executescript(_ESQUEMA_V3)
            if version < 4:
                con.executescript(_ESQUEMA_V4)
            if version < 5:
                con.executescript(_ESQUEMA_V5)
            if version < 6:
                con.executescript(_ESQUEMA_V6)
            if version < 7:
                con.executescript(_ESQUEMA_V7)
            if version < VERSION_ESQUEMA:
                con.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")

    # ── Enlaces del papá ─────────────────────────────────────────────────────

    def crear_enlace(self, token: str, nino_id: str, vence: datetime) -> None:
        with self._conectar() as con:
            con.execute(
                "INSERT OR REPLACE INTO enlaces (token, nino_id, vence) VALUES (?, ?, ?)",
                (token, nino_id, vence.isoformat()),
            )

    def canjear_enlace(self, token: str, ahora: datetime | None = None) -> str | None:
        """Devuelve el nino_id, o None si no existe o venció.

        El vencido se borra al detectarlo: la tabla se limpia sola con el uso, sin
        una tarea aparte que alguien tenga que acordarse de correr.
        """
        ahora = ahora or datetime.now()
        with self._conectar() as con:
            fila = con.execute(
                "SELECT nino_id, vence FROM enlaces WHERE token = ?", (token,)
            ).fetchone()
            if fila is None:
                return None
            if datetime.fromisoformat(fila["vence"]) < ahora:
                con.execute("DELETE FROM enlaces WHERE token = ?", (token,))
                return None
            return fila["nino_id"]

    # ── Niños ────────────────────────────────────────────────────────────────

    def obtener_nino(self, nino_id: str) -> Nino | None:
        with self._conectar() as con:
            fila = con.execute("SELECT * FROM ninos WHERE id = ?", (nino_id,)).fetchone()
            if fila is None:
                return None

            dominio = {
                d["habilidad_id"]: RegistroDominio(
                    habilidad_id=d["habilidad_id"],
                    nivel=d["nivel"],
                    intentos=d["intentos"],
                    aciertos=d["aciertos"],
                    pistas_necesitadas=d["pistas_necesitadas"],
                    primera_practica=_texto_a_fecha(d["primera_practica"]),
                    ultima_practica=_texto_a_fecha(d["ultima_practica"]),
                )
                for d in con.execute("SELECT * FROM dominio WHERE nino_id = ?", (nino_id,))
            }

        return Nino(
            id=fila["id"],
            nombre=fila["nombre"],
            edad=fila["edad"],
            grado=fila["grado"],
            idioma=fila["idioma"],
            calendario=Calendario(fila["calendario"]),
            email_papa=fila["email_papa"],
            token_acceso=fila["token_acceso"],
            dominio=dominio,
            perfil=PerfilPersonal.model_validate_json(fila["perfil"]),
            creado_en=_texto_a_fecha(fila["creado_en"]),
        )

    def ids_de_ninos(self) -> list[str]:
        with self._conectar() as con:
            return [f["id"] for f in con.execute("SELECT id FROM ninos ORDER BY creado_en")]

    def guardar_nino(self, nino: Nino) -> None:
        """Las dos mitades en UNA transacción.

        Si se guardara la ficha personal y fallara el dominio (o al revés), el
        niño quedaría con mitades de momentos distintos. Acá o entra todo o no
        entra nada.
        """
        with self._conectar() as con:
            con.execute(
                """
                INSERT INTO ninos (id, nombre, edad, grado, idioma, calendario,
                                   email_papa, token_acceso, perfil, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    nombre     = excluded.nombre,
                    edad       = excluded.edad,
                    grado      = excluded.grado,
                    idioma     = excluded.idioma,
                    calendario = excluded.calendario,
                    email_papa = excluded.email_papa,
                    -- El token NO se pisa con NULL: quien guarda la ficha desde
                    -- el pipeline no lo lleva, y perderlo dejaría al niño sin
                    -- poder entrar hasta que el papá pidiera otro enlace.
                    token_acceso = COALESCE(excluded.token_acceso, ninos.token_acceso),
                    perfil     = excluded.perfil
                """,
                (
                    nino.id,
                    nino.nombre,
                    nino.edad,
                    nino.grado,
                    nino.idioma,
                    nino.calendario.value,
                    nino.email_papa,
                    nino.token_acceso,
                    nino.perfil.model_dump_json(),
                    _fecha_a_texto(nino.creado_en or datetime.now()),
                ),
            )
            con.executemany(
                """
                INSERT INTO dominio (nino_id, habilidad_id, nivel, intentos, aciertos,
                                     pistas_necesitadas, primera_practica, ultima_practica)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(nino_id, habilidad_id) DO UPDATE SET
                    nivel              = excluded.nivel,
                    intentos           = excluded.intentos,
                    aciertos           = excluded.aciertos,
                    pistas_necesitadas = excluded.pistas_necesitadas,
                    primera_practica   = excluded.primera_practica,
                    ultima_practica    = excluded.ultima_practica
                """,
                [
                    (
                        nino.id,
                        r.habilidad_id,
                        r.nivel,
                        r.intentos,
                        r.aciertos,
                        r.pistas_necesitadas,
                        _fecha_a_texto(r.primera_practica),
                        _fecha_a_texto(r.ultima_practica),
                    )
                    for r in nino.dominio.values()
                ],
            )

    # ── Sesiones ─────────────────────────────────────────────────────────────

    @staticmethod
    def _fila_a_sesion(fila: sqlite3.Row) -> Sesion:
        return Sesion(
            id=fila["id"],
            nino_id=fila["nino_id"],
            modo=ModoSesion(fila["modo"]),
            estado=EstadoSesion(fila["estado"]),
            inicio=_texto_a_fecha(fila["inicio"]),
            fin=_texto_a_fecha(fila["fin"]),
            habilidades_trabajadas=json.loads(fila["habilidades_trabajadas"]),
            tokens_consumidos=fila["tokens_consumidos"],
            analizada=bool(fila["analizada"]),
            tecnica_id=fila["tecnica_id"],
            dominio_inicial=fila["dominio_inicial"],
            motivo_cierre=fila["motivo_cierre"],
        )

    def crear_sesion(self, sesion: Sesion) -> None:
        with self._conectar() as con:
            con.execute(
                """
                INSERT INTO sesiones (id, nino_id, modo, estado, inicio, fin,
                                      habilidades_trabajadas, tokens_consumidos, analizada,
                                      tecnica_id, dominio_inicial)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._valores_sesion(sesion),
            )

    def obtener_sesion(self, sesion_id: str) -> Sesion | None:
        with self._conectar() as con:
            fila = con.execute("SELECT * FROM sesiones WHERE id = ?", (sesion_id,)).fetchone()
        return self._fila_a_sesion(fila) if fila else None

    def actualizar_sesion(self, sesion: Sesion) -> None:
        with self._conectar() as con:
            con.execute(
                """
                UPDATE sesiones SET
                    estado = ?, fin = ?, habilidades_trabajadas = ?,
                    tokens_consumidos = ?, analizada = ?,
                    tecnica_id = ?, dominio_inicial = ?, motivo_cierre = ?
                WHERE id = ?
                """,
                (
                    sesion.estado.value,
                    _fecha_a_texto(sesion.fin),
                    json.dumps(sesion.habilidades_trabajadas),
                    sesion.tokens_consumidos,
                    int(sesion.analizada),
                    sesion.tecnica_id,
                    sesion.dominio_inicial,
                    sesion.motivo_cierre,
                    sesion.id,
                ),
            )

    @staticmethod
    def _valores_sesion(s: Sesion) -> tuple:
        return (
            s.id,
            s.nino_id,
            s.modo.value,
            s.estado.value,
            _fecha_a_texto(s.inicio),
            _fecha_a_texto(s.fin),
            json.dumps(s.habilidades_trabajadas),
            s.tokens_consumidos,
            int(s.analizada),
            s.tecnica_id,
            s.dominio_inicial,
        )

    def sesiones_sin_analizar(self) -> list[Sesion]:
        with self._conectar() as con:
            filas = con.execute(
                "SELECT * FROM sesiones WHERE analizada = 0 ORDER BY inicio"
            ).fetchall()
        return [self._fila_a_sesion(f) for f in filas]

    def sesiones_de(self, nino_id: str, desde: datetime, hasta: datetime) -> list[Sesion]:
        with self._conectar() as con:
            filas = con.execute(
                """
                SELECT * FROM sesiones
                WHERE nino_id = ? AND inicio >= ? AND inicio <= ?
                ORDER BY inicio
                """,
                (nino_id, _fecha_a_texto(desde), _fecha_a_texto(hasta)),
            ).fetchall()
        return [self._fila_a_sesion(f) for f in filas]

    # ── Banco de ejercicios ──────────────────────────────────────────────────

    def ejercicios_de(
        self, habilidad_id: str, limite: int = 15, tema: str | None = None
    ) -> list[Ejercicio]:
        consulta = "SELECT * FROM ejercicios WHERE habilidad_id = ? AND validado = 1"
        parametros: list = [habilidad_id]
        if tema is not None:
            consulta += " AND tema = ?"
            parametros.append(tema)
        # Al azar: el niño no debe recibir siempre los mismos ejercicios.
        consulta += " ORDER BY RANDOM() LIMIT ?"
        parametros.append(limite)

        with self._conectar() as con:
            filas = con.execute(consulta, parametros).fetchall()

        return [
            Ejercicio(
                id=f["id"],
                habilidad_id=f["habilidad_id"],
                enunciado=TextoLocalizado.model_validate_json(f["enunciado"]),
                respuesta=f["respuesta"],
                tema=f["tema"],
                validado=bool(f["validado"]),
            )
            for f in filas
        ]

    def habilidades_con_ejercicios(self) -> set[str]:
        with self._conectar() as con:
            return {
                f["habilidad_id"]
                for f in con.execute(
                    "SELECT DISTINCT habilidad_id FROM ejercicios WHERE validado = 1"
                )
            }

    def guardar_ejercicios(self, ejercicios: list[Ejercicio]) -> None:
        with self._conectar() as con:
            con.executemany(
                """
                INSERT INTO ejercicios (id, habilidad_id, enunciado, respuesta, tema, validado)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    enunciado = excluded.enunciado,
                    respuesta = excluded.respuesta,
                    tema      = excluded.tema,
                    validado  = excluded.validado
                """,
                [
                    (
                        e.id,
                        e.habilidad_id,
                        e.enunciado.model_dump_json(),
                        e.respuesta,
                        e.tema,
                        int(e.validado),
                    )
                    for e in ejercicios
                ],
            )

    # ── Transcripciones (archivos, no SQLite) ────────────────────────────────

    def _ruta_transcripcion(self, sesion_id: str) -> Path:
        # El id viene de adentro del sistema, pero igual se aísla el nombre:
        # nunca se construye una ruta con texto sin sanear.
        return self.ruta_transcripciones / f"{Path(sesion_id).name}.txt"

    def guardar_transcripcion(self, sesion_id: str, contenido: str) -> None:
        self._ruta_transcripcion(sesion_id).write_text(contenido, encoding="utf-8")

    def obtener_transcripcion(self, sesion_id: str) -> str | None:
        ruta = self._ruta_transcripcion(sesion_id)
        return ruta.read_text(encoding="utf-8") if ruta.exists() else None

    def _ruta_diario(self, sesion_id: str) -> Path:
        return self.ruta_transcripciones / f"{Path(sesion_id).name}.eventos.jsonl"

    def anotar_en_diario(self, sesion_id: str, eventos: list[dict]) -> None:
        """Se APENDA, no se reescribe: llegan de a lotes durante la sesión.

        Y va en el mismo directorio que la transcripción a propósito: es dato de
        la conversación de un menor, así que tiene que morir con ella cuando
        corra la retención. Un diario que sobreviva a la transcripción sería una
        política de datos con un agujero.
        """
        if not eventos:
            return
        with self._ruta_diario(sesion_id).open("a", encoding="utf-8") as f:
            for e in eventos:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def leer_diario(self, sesion_id: str) -> list[dict]:
        ruta = self._ruta_diario(sesion_id)
        if not ruta.exists():
            return []
        salida = []
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            try:
                salida.append(json.loads(linea))
            except json.JSONDecodeError:
                # Una línea a medio escribir no puede tirar el diario entero:
                # esto se lee justo cuando algo salió mal.
                continue
        return salida

    def borrar_transcripciones_anteriores_a(self, fecha: datetime) -> int:
        """Retención de datos de menores.

        La fecha de la sesión manda (es el dato real), no la fecha del archivo.
        Los archivos huérfanos —sin sesión asociada— se barren por mtime, para
        que nada quede sin borrar por un hueco en la base.

        El diario de la voz se va con su transcripción: es dato de la misma
        conversación, y dejarlo vivo sería un agujero en la política.
        """
        with self._conectar() as con:
            viejas = {
                f["id"]
                for f in con.execute(
                    "SELECT id FROM sesiones WHERE inicio < ?", (_fecha_a_texto(fecha),)
                )
            }
            conocidas = {f["id"] for f in con.execute("SELECT id FROM sesiones")}

        borradas = 0
        for ruta in self.ruta_transcripciones.glob("*.txt"):
            sesion_id = ruta.stem
            vencida = sesion_id in viejas or (
                sesion_id not in conocidas  # huérfano: manda el mtime
                and datetime.fromtimestamp(ruta.stat().st_mtime) < fecha
            )
            if vencida:
                ruta.unlink()
                borradas += 1
                self._ruta_diario(sesion_id).unlink(missing_ok=True)

        # Y los diarios que quedaron sin transcripción (una sesión que murió
        # antes de cerrar): mismo dato, misma política.
        for ruta in self.ruta_transcripciones.glob("*.eventos.jsonl"):
            sesion_id = ruta.name.removesuffix(".eventos.jsonl")
            if sesion_id in viejas or (
                sesion_id not in conocidas
                and datetime.fromtimestamp(ruta.stat().st_mtime) < fecha
            ):
                ruta.unlink()
        return borradas

    # ── Reportes (archivos) ──────────────────────────────────────────────────

    def guardar_reporte(self, reporte: ReporteParaPapa) -> None:
        nombre = f"{Path(reporte.nino_id).name}_{reporte.hasta:%Y-%m-%d}.json"
        (self.ruta_reportes / nombre).write_text(
            reporte.model_dump_json(indent=2), encoding="utf-8"
        )

    def ultimo_reporte(self, nino_id: str) -> ReporteParaPapa | None:
        prefijo = f"{Path(nino_id).name}_"
        candidatos = sorted(self.ruta_reportes.glob(f"{prefijo}*.json"))
        if not candidatos:
            return None
        # El nombre lleva la fecha `hasta`: el último por orden es el más reciente.
        return ReporteParaPapa.model_validate_json(candidatos[-1].read_text(encoding="utf-8"))

    # ── Auditoría de cumplimiento (archivos) ─────────────────────────────────

    def _ruta_auditoria(self, sesion_id: str) -> Path:
        return self.ruta_auditorias / f"{Path(sesion_id).name}.json"

    @property
    def ruta_cadena(self) -> Path:
        """El registro encadenado de veredictos. Append-only, nunca se reescribe."""
        return self.ruta_auditorias / "cadena.jsonl"

    def guardar_auditoria(self, sesion_id: str, cumplimiento: AuditoriaCumplimiento) -> None:
        contenido = cumplimiento.model_dump_json(indent=2)
        self._ruta_auditoria(sesion_id).write_text(contenido, encoding="utf-8")
        self._encadenar(sesion_id, contenido)

    def _encadenar(self, sesion_id: str, contenido: str) -> None:
        """Anota el veredicto en la cadena. Ver `huella_de` para el porqué."""
        eslabones = leer_cadena(self.ruta_cadena)
        ultimo = eslabones[-1] if eslabones else None
        nuevo = Eslabon.forjar(
            seq=(ultimo.seq + 1) if ultimo else 1,
            sesion_id=sesion_id,
            contenido=contenido,
            anterior=ultimo.hash if ultimo else GENESIS,
        )
        with self.ruta_cadena.open("a", encoding="utf-8") as f:
            f.write(nuevo.model_dump_json() + "\n")

    def obtener_auditoria(self, sesion_id: str) -> AuditoriaCumplimiento | None:
        ruta = self._ruta_auditoria(sesion_id)
        if not ruta.exists():
            return None
        return AuditoriaCumplimiento.model_validate_json(ruta.read_text(encoding="utf-8"))
