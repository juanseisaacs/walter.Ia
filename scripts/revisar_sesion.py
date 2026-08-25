"""¿Cómo salió la última sesión? Todo en una pantalla.

    python -m scripts.revisar_sesion            # la última
    python -m scripts.revisar_sesion ses_abc123 # una en particular

EXISTE PARA CORTAR UN CICLO QUE COSTÓ DÍAS. La conversación se repetía así:

    — «se trabó, se desapareció, arréglalo»
    — media hora de forense entre el log del servidor, la base y la
      transcripción, terminando en una hipótesis

El problema no era ninguno de los bugs: era que **nadie podía ver el estado de
una sesión sin reconstruirlo a mano**. Los datos estaban todos —turnos,
tokens, dominio, auditoría, motivo de cierre—, repartidos en cinco lugares.

Esto los junta. Cada sesión pasa a ser evidencia en vez de una discusión sobre
impresiones, y el siguiente paso se vuelve obvio: se lee en la pantalla.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tutor import config as cfg  # noqa: E402

# Medido sobre dos recargas de US$10 agotadas: US$20 / 520,3 minutos.
# No es la tarifa de lista de Google (esa cubre solo el stream de audio); es lo
# que de verdad costó, con el contexto reprocesándose en cada turno.
USD_POR_MINUTO = 0.0384


def _marca(ok: bool | None, si: str, no: str) -> str:
    if ok is None:
        return f"  ??  {si}"
    return f"  OK  {si}" if ok else f"  --  {no}"


def main() -> int:
    con = sqlite3.connect(cfg.DB)
    con.row_factory = sqlite3.Row

    if len(sys.argv) > 1:
        fila = con.execute("SELECT * FROM sesiones WHERE id = ?", (sys.argv[1],)).fetchone()
    else:
        fila = con.execute(
            "SELECT * FROM sesiones WHERE fin IS NOT NULL ORDER BY inicio DESC LIMIT 1"
        ).fetchone()
    if fila is None:
        print("\n  No hay sesión que revisar.\n")
        return 1

    nino = con.execute("SELECT nombre FROM ninos WHERE id = ?", (fila["nino_id"],)).fetchone()
    habs = json.loads(fila["habilidades_trabajadas"] or "[]")
    minutos = 0.0
    if fila["fin"]:
        minutos = (
            datetime.fromisoformat(fila["fin"]) - datetime.fromisoformat(fila["inicio"])
        ).total_seconds() / 60

    print("=" * 74)
    print(f"  {fila['id']}   {nino['nombre'] if nino else fila['nino_id']}")
    print(f"  {fila['inicio'][:16].replace('T', ' ')} · {minutos:.1f} min")
    print("=" * 74)

    # ── Cerró bien ────────────────────────────────────────────────────────
    print("\n CIERRE")
    print(f"  estado: {fila['estado']} · motivo: {fila['motivo_cierre'] or 'SIN REGISTRAR'}")
    print(
        _marca(
            fila["motivo_cierre"] is not None,
            "quedó registrado por qué terminó",
            "NO se sabe por qué terminó — es el agujero que costó cuatro investigaciones",
        )
    )

    # ── Aprendió algo ─────────────────────────────────────────────────────
    print("\n APRENDIZAJE  (¿el circuito adaptativo se cerró?)")
    print(_marca(bool(habs), f"trabajó: {', '.join(habs)}", "NO trabajó ninguna habilidad"))
    escribio = []
    for h in habs:
        d = con.execute(
            "SELECT nivel, intentos, aciertos FROM dominio WHERE nino_id = ? AND habilidad_id = ?",
            (fila["nino_id"], h),
        ).fetchone()
        if d:
            escribio.append(f"{h} → {d['nivel']:.2f} ({d['aciertos']}/{d['intentos']})")
    print(_marca(bool(escribio), "dominio escrito: " + " · ".join(escribio), "sin dominio escrito"))
    print(
        _marca(
            bool(fila["analizada"]),
            "el Analista ya la procesó",
            "todavía en la cola del Analista",
        )
    )

    # ── Cómo enseñó ───────────────────────────────────────────────────────
    ruta = cfg.RAIZ / "data" / "audits" / f"{fila['id']}.json"
    print("\n MÉTODO  (auditoría)")
    if ruta.exists():
        a = json.loads(ruta.read_text(encoding="utf-8"))
        print(_marca(not a["regalo_la_respuesta"], "no regaló la respuesta", "REGALÓ la respuesta"))
        print(_marca(a["respeto_escalera_pistas"], "respetó la escalera", "SALTÓ escalones"))
        print(_marca(not a["elogio_inflado"], "sin elogio inflado", "ELOGIO INFLADO"))
        print(_marca(not a["afirmo_algo_falso"], "no afirmó nada falso", "AFIRMÓ ALGO FALSO"))
        if a.get("notas"):
            print(f"\n  {a['notas'][:400]}")
    else:
        print("  ??  todavía sin auditar")

    # ── Cómo se sintió ────────────────────────────────────────────────────
    tr = cfg.RAIZ / "data" / "transcripts" / f"{fila['id']}.txt"
    print("\n FLUIDEZ")
    if tr.exists():
        from scripts.medir_fluidez import _marca_de_mudez, medir

        m = medir(tr.read_text(encoding="utf-8"), _marca_de_mudez())
        pct = 100 * m["cortados"] / max(m["turnos"], 1)
        print(
            f"  {m['turnos']} turnos · {m['cortados']} cortados ({pct:.0f}%) · "
            f"{m['mudeces']} mudeces"
        )
        print(_marca(m["mudeces"] == 0, "el tutor nunca se quedó mudo", "SE QUEDÓ MUDO"))
        print(
            _marca(
                m["cortados_nino"] == 0,
                "no se le cortó al niño",
                f"al niño se le cortó {m['cortados_nino']} vez/veces",
            )
        )
    else:
        print("  ??  sin transcripción")

    # ── Cuánto costó ──────────────────────────────────────────────────────
    print("\n COSTO")
    print(f"  {minutos:.1f} min × US${USD_POR_MINUTO:.4f}/min ≈ US${minutos * USD_POR_MINUTO:.2f}")
    print(f"  tokens registrados: {fila['tokens_consumidos']:,}")
    if fila["tokens_consumidos"] == 0 and minutos > 0.5:
        print("  --  gastó y NO quedó anotado: el navegador no alcanzó a reportar")

    # ── Lo que se tiró a la basura ────────────────────────────────────────
    perdidas = con.execute(
        "SELECT id, inicio, fin FROM sesiones WHERE motivo_cierre = 'sin_latido' "
        "OR motivo_cierre = 'nino_inactivo' ORDER BY inicio DESC LIMIT 5"
    ).fetchall()
    if perdidas:
        print("\n SESIONES QUE SE CERRARON SOLAS  (plata que ya no se tira)")
        for p in perdidas:
            d = (
                datetime.fromisoformat(p["fin"]) - datetime.fromisoformat(p["inicio"])
            ).total_seconds() / 60
            print(f"  {p['id']}  {d:.1f} min  ≈ US${d * USD_POR_MINUTO:.2f}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
