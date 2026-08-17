"""Verifica los dos supuestos sobre los que se apoya la arquitectura de voz.

Ver ARCHITECTURE.md §10 — "Pendiente de verificar con API key real".

  1. CANDADO #1: que la configuracion se pueda ATAR al token efimero.
     Si no existe, el navegador puede cambiar la persona, el playbook y la
     politica de seguridad -> habria que reevaluar el proxy.

  2. TOOL CALLING: que el modelo pueda llamar funciones en Live API.
     Todo el diseno de los 4 tools lo supone.

Se prueba con TEXTO, no con audio: alcanza para responder ambas preguntas y no
necesita navegador ni microfono.

    python -m scripts.verificar_gemini
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from google import genai  # noqa: E402

from tutor import config as cfg  # noqa: E402
from tutor.voice import DECLARACIONES_TOOLS  # noqa: E402

OK = "  [OK]  "
FALLA = "  [FALLA]"


def cliente() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise SystemExit("Falta GOOGLE_API_KEY en .env")
    return genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})


# ─────────────────────────────────────────────────────────────────────────────
# 1. Token con configuracion atada
# ─────────────────────────────────────────────────────────────────────────────


def verificar_token_atado(c: genai.Client) -> bool:
    print("\n1. CANDADO #1 — configuracion atada al token")
    print("   Pregunta: puede el servidor fijar el system prompt para que el")
    print("   navegador NO pueda cambiarlo?\n")

    ahora = datetime.now(UTC)
    instruccion = "Sos un tutor. Nunca das la respuesta."

    try:
        token = c.auth_tokens.create(
            config={
                "uses": 1,
                "new_session_expire_time": (ahora + timedelta(seconds=60)).isoformat(),
                "expire_time": (ahora + timedelta(minutes=30)).isoformat(),
                "live_connect_constraints": {
                    "model": cfg.MODELO_TUTOR_VOZ,
                    "config": {
                        "response_modalities": ["TEXT"],
                        "system_instruction": instruccion,
                    },
                },
            }
        )
    except Exception as e:
        print(f"{FALLA} el API rechazo live_connect_constraints")
        print(f"        {type(e).__name__}: {str(e)[:300]}")
        print("\n        -> El candado #1 NO existe. Hay que reevaluar el proxy.")
        return False

    print(f"{OK} token emitido con configuracion atada")
    print(f"        nombre: {str(token.name)[:28]}...")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tool calling en Live API
# ─────────────────────────────────────────────────────────────────────────────


async def verificar_tool_calling(c: genai.Client) -> bool:
    print("\n2. TOOL CALLING en Live API")
    print("   Pregunta: puede el modelo llamar a check_answer durante la charla?\n")

    # AUDIO, no TEXT: este modelo solo devuelve audio. La ENTRADA sigue siendo
    # texto — alcanza para ver si emite una llamada a funcion.
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": (
            "Sos un tutor de matematica. Cuando el nino te diga una respuesta, "
            "SIEMPRE usas la herramienta check_answer para verificarla. Vos no calculas."
        ),
        "tools": [{"function_declarations": DECLARACIONES_TOOLS}],
    }

    try:
        async with c.aio.live.connect(model=cfg.MODELO_TUTOR_VOZ, config=config) as sesion:
            await sesion.send_client_content(
                turns={
                    "role": "user",
                    "parts": [{"text": "El ejercicio e1 era 27 mas 15. Yo digo que da 42."}],
                },
                turn_complete=True,
            )

            llamadas = []
            texto = ""
            async for respuesta in sesion.receive():
                if getattr(respuesta, "tool_call", None):
                    for fc in respuesta.tool_call.function_calls:
                        llamadas.append((fc.name, dict(fc.args or {})))
                    break
                if getattr(respuesta, "text", None):
                    texto += respuesta.text
                sc = getattr(respuesta, "server_content", None)
                if sc and getattr(sc, "turn_complete", False):
                    break

    except Exception as e:
        print(f"{FALLA} error abriendo o usando la sesion Live")
        print(f"        {type(e).__name__}: {str(e)[:300]}")
        return False

    if llamadas:
        print(f"{OK} el modelo llamo a una herramienta")
        for nombre, args in llamadas:
            print(f"        -> {nombre}({args})")
        return True

    print(f"{FALLA} el modelo NO llamo ninguna herramienta")
    print(f"        respondio con texto: {texto[:200]!r}")
    print("\n        -> Revisar el formato de las declaraciones de tools.")
    return False


# ─────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    print("=" * 70)
    print("  VERIFICACION DE SUPUESTOS — ARCHITECTURE.md §10")
    print(f"  modelo: {cfg.MODELO_TUTOR_VOZ}")
    print("=" * 70)

    c = cliente()
    r1 = verificar_token_atado(c)
    r2 = await verificar_tool_calling(c)

    print("\n" + "=" * 70)
    print(f"  candado #1 (config atada) : {'OK' if r1 else 'FALLA'}")
    print(f"  tool calling              : {'OK' if r2 else 'FALLA'}")
    print("=" * 70)

    if r1 and r2:
        print("\n  Los dos supuestos se sostienen. La arquitectura sigue en pie.\n")
    else:
        print("\n  Hay que revisar la arquitectura antes de seguir construyendo.\n")


if __name__ == "__main__":
    asyncio.run(main())
