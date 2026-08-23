"""Cuando el niño pide VER algo, ¿qué manda el tutor a la pizarra?

    python -m scripts.verificar_pizarra

`test_contrato_pizarra.py` comprueba que los TIPOS declarados en Python tengan
handler en TypeScript. Eso no alcanza: el modelo puede mandar un tipo válido con
argumentos que el traductor rechaza, y ahí el niño se queda mirando un tablero
vacío mientras el tutor le habla de lo que cree haberle mostrado.

Pasó en `ses_445f4c33db41` (22/08). El niño lo dijo con todas las letras:

    tutor: «Mira, ahí te la dibujé en la pizarra, es como una eme al revés»
    nino:  «A ver, okay, sí, pero NO ME SALE EL TABLERO.»

Y al final de esa misma sesión, pidiendo ver 3/5 primero y unas gallinas
después, el tutor se quedó mudo y no volvió.

Este script le pide al modelo REAL las tres cosas que pidió el niño y reporta,
por turno: qué mandó a la pizarra, si tuvo voz, si habló ANTES de pedir la
herramienta (que es lo que tapa la demora), si se le escapó una palabra vetada,
y —si se quedó mudo— si el empujón del vigilante lo recupera.

Los argumentos crudos quedan en `data/pizarra_capturada.json`. Los que importan
se copian a mano al bloque «lo que el modelo manda DE VERDAD» de
`web/src/pizarra/desdeElTutor.test.ts`: ahí quedan como regresión permanente,
sin volver a gastar cuota. `data/` no se versiona, así que el JSON es evidencia
local y el test es lo que viaja.

Necesita GOOGLE_API_KEY con saldo.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from google import genai  # noqa: E402

from scripts.verificar_dibujo import RESUMEN_JUAN, Turno, escuchar  # noqa: E402
from tutor import config as cfg  # noqa: E402
from tutor.voice import (  # noqa: E402
    ConfiguracionSesion,
    construir_instruccion_sistema,
    deteccion_para_edad,
    instruccion_de_apertura,
)

SALIDA = Path(__file__).resolve().parents[1] / "data" / "pizarra_capturada.json"


def _aviso_de_mudez() -> str:
    """El empujón REAL del navegador, leído de su fuente."""
    import re  # noqa: PLC0415

    ts = (Path(__file__).resolve().parents[1] / "web/src/voz/useTutor.ts").read_text(
        encoding="utf-8"
    )
    bloque = re.search(r"AVISO_DE_MUDEZ\s*=\s*(.*?);", ts, re.S)
    return "".join(re.findall(r'"([^"]*)"', bloque.group(1)))


# Textuales de `ses_445f4c33db41`. No son ejemplos inventados: son las tres
# cosas que un niño de 7 pidió ver en cinco minutos, y las tres fallaron.
PEDIDOS = [
    ("la letra W", "Vamos a empezar por aprender a hacer la letra w. Muéstramela."),
    (
        "la pizza de 3/5",
        "No tengo imaginación, ¿me muestras cómo se verían las pizzas de tres quintos?",
    ),
    (
        "gallinas y pollitos",
        "Hagamos un ejemplo con gallinas y pollitos, sumas y restas. "
        "Pero que me pueda yo ver las gallinas y los pollitos.",
    ),
    (
        "3 pollitos + 5 pollitos (ses_4ed4e930e60f)",
        "Hola, Walter, ¿me ayudas a sumar cuánto dan tres pollitos más cinco "
        "pollitos, pero que se vea visualmente?",
    ),
    (
        "la suma de tres montones",
        "5 + 3 + 6 y no son bolitas, sino son pollitos. ¿Podrías mostrarme los pollitos?",
    ),
]


# Lo que el tutor NO puede decir, tal como apareció en `ses_445f4c33db41`. El
# prompt las veta por su nombre; esto comprueba que la veda se cumple.
VETADAS = ("hágale", "hagale", "nops", "notota", "dígame", "cuénteme", "oiga")


def palabras_raras(dicho: str) -> list[str]:
    bajo = dicho.lower()
    return [p for p in VETADAS if p in bajo]


def _resumen(nombre: str, turno: Turno) -> str:
    pizarra = [(n, a) for n, a in turno.llamadas if n == "mostrar_en_pizarra"]
    if not pizarra:
        otros = ", ".join(n for n, _ in turno.llamadas) or "ninguna herramienta"
        return f"NO USÓ LA PIZARRA ({otros})"
    return " · ".join(json.dumps(a, ensure_ascii=False) for _, a in pizarra)


async def main() -> int:
    clave = os.getenv("GOOGLE_API_KEY")
    if not clave:
        print("\n  Falta GOOGLE_API_KEY en .env\n")
        return 1

    config = ConfiguracionSesion(
        instruccion_sistema=construir_instruccion_sistema(RESUMEN_JUAN),
        deteccion=deteccion_para_edad(7),
    ).a_dict_gemini()

    cliente = genai.Client(api_key=clave, http_options={"api_version": "v1alpha"})

    print("=" * 74)
    print(f"  ¿QUÉ LE MANDA A LA PIZARRA?   modelo: {cfg.MODELO_TUTOR_VOZ}")
    print("=" * 74)

    capturado: list[dict] = []
    async with cliente.aio.live.connect(model=cfg.MODELO_TUTOR_VOZ, config=config) as s:
        await s.send_client_content(
            turns={"role": "user", "parts": [{"text": instruccion_de_apertura()}]},
            turn_complete=True,
        )
        await escuchar(s)

        for nombre, pedido in PEDIDOS:
            print(f"\n▸ {nombre} — «{pedido[:60]}…»")
            await s.send_client_content(
                turns={"role": "user", "parts": [{"text": pedido}]}, turn_complete=True
            )
            turno = await escuchar(s)
            print(f"   manda: {_resumen(nombre, turno)}")
            print(f"   {turno}")

            raras = palabras_raras("".join(turno.dicho))
            if raras:
                print(f"   ⚠ PALABRAS VETADAS: {', '.join(raras)}")

            # ¿Habló ANTES de pedir la herramienta? Es lo que tapa la demora.
            if turno.pidio_tool_ms is not None and turno.arranco_ms is not None:
                antes = turno.arranco_ms < turno.pidio_tool_ms
                print(f"   orden: {'habló primero' if antes else 'pidió primero'}")

            # Y si se quedó mudo, ¿lo recupera el empujón del vigilante?
            if not turno.audio:
                print("   (mudo) → empujón del vigilante")
                await s.send_client_content(
                    turns={"role": "user", "parts": [{"text": _aviso_de_mudez()}]},
                    turn_complete=True,
                )
                rescate = await escuchar(s)
                print(f"   {rescate}")
                print(f"   manda: {_resumen(nombre, rescate)}")
                turno.llamadas.extend(rescate.llamadas)
            for tool, args in turno.llamadas:
                if tool == "mostrar_en_pizarra":
                    capturado.append({"pidio": nombre, "args": args})

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(capturado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  {len(capturado)} llamada(s) guardadas en {SALIDA.relative_to(Path.cwd())}")
    print("  Correr `cd web && npm test` para pasarlas por el traductor real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
