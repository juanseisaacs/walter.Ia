"""¿Se puede hablar con el tutor AHORA MISMO? Una sola respuesta: sí o no.

    python -m scripts.listo_para_hablar

Existe porque el 24/08 se entregaron cuatro enlaces "verificados" y ninguno
servía. La verificación había mirado la capa HTTP —`POST /api/sesiones` daba
200 en los cuatro— y el camino de la VOZ, que es el único que le importa al
niño, no lo miró nadie. Google contestaba:

    1011 Your prepayment credits are depleted.

O sea: el backend sano, la sesión abierta, el token firmado, y el producto
caído. Y en pantalla un mensaje que decía «sin cupo por hoy», indistinguible
del tope diario del niño — que es normal y saludable. Media hora buscando un
bug que no existía.

**Un enlace no se entrega sin haber corrido esto.** Gasta una conexión Live de
un segundo; el error que evita cuesta una sesión entera.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from tutor import config as cfg  # noqa: E402

BASE = os.getenv("BASE_TUTOR", "http://localhost:8000")


def _servidor() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{BASE}/api/salud", timeout=5) as r:
            import json

            d = json.loads(r.read())
        return True, f"build {d.get('build')} · {d.get('habilidades')} habilidades"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


async def _voz() -> tuple[bool, str]:
    """El camino que de verdad usa el niño. Lo demás puede estar perfecto igual."""
    from google import genai

    llave = os.getenv("GOOGLE_API_KEY")
    if not llave:
        return False, "no hay GOOGLE_API_KEY en el entorno"
    cliente = genai.Client(api_key=llave, http_options={"api_version": "v1alpha"})
    try:
        async with cliente.aio.live.connect(
            model=cfg.MODELO_TUTOR_VOZ, config={"responseModalities": ["AUDIO"]}
        ) as s:
            await s.send_client_content(
                turns={"role": "user", "parts": [{"text": "hola"}]}, turn_complete=True
            )
            async for m in s.receive():
                if getattr(m, "server_content", None):
                    return True, cfg.MODELO_TUTOR_VOZ
        return False, "conectó pero no contestó"
    except Exception as e:  # noqa: BLE001
        detalle = str(e)[:180]
        if any(p in detalle.lower() for p in ("credit", "quota", "billing", "deplet")):
            return False, f"SIN CRÉDITOS EN GOOGLE — {detalle}"
        return False, f"{type(e).__name__}: {detalle}"


def _ninos() -> list[tuple[str, str, str, int]]:
    """Quién puede abrir sesión hoy, contado como lo cuenta el backend."""
    from datetime import datetime

    hoy = datetime.now().strftime("%Y-%m-%d")
    con = sqlite3.connect(cfg.DB)
    con.row_factory = sqlite3.Row
    salida = []
    for n in con.execute("SELECT id, nombre, token_acceso FROM ninos"):
        usadas = sum(
            1
            for r in con.execute(
                "SELECT habilidades_trabajadas FROM sesiones "
                "WHERE nino_id = ? AND inicio LIKE ?",
                (n["id"], f"{hoy}%"),
            )
            # El backend solo cuenta las sesiones donde el niño TRABAJÓ.
            if r[0] and r[0] != "[]"
        )
        salida.append((n["id"], n["nombre"], n["token_acceso"], usadas))
    return salida


def main() -> int:
    print("=" * 74)
    print("  ¿SE PUEDE HABLAR CON EL TUTOR AHORA?")
    print("=" * 74)

    ok_srv, det_srv = _servidor()
    print(f"\n  {'OK  ' if ok_srv else 'NO  '} servidor · {det_srv}")

    ok_voz, det_voz = asyncio.run(_voz())
    print(f"  {'OK  ' if ok_voz else 'NO  '} voz (Gemini Live) · {det_voz}")

    if not (ok_srv and ok_voz):
        print("\n  NO SE PUEDE HABLAR. No entregues enlaces todavía.")
        if "CRÉDITOS" in det_voz:
            print("  → Recargar en https://ai.studio/projects (billing del proyecto)")
        print()
        return 1

    print("\n  Enlaces que sirven hoy:\n")
    hubo = False
    for nino_id, nombre, token, usadas in _ninos():
        if usadas >= cfg.MAX_SESIONES_DIA:
            print(f"    (sin cupo: {nombre} — {usadas}/{cfg.MAX_SESIONES_DIA} hoy)")
            continue
        hubo = True
        libres = cfg.MAX_SESIONES_DIA - usadas
        print(f"    {nombre} · {libres} sesión(es)")
        print(f"      {BASE}/?nino={nino_id}&t={token}")
    if not hubo:
        print("    NINGUNO: todos llegaron al tope de hoy.")
        return 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
