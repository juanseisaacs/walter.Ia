"""¿El tutor CONTESTA cuando el niño le manda un dibujo?

    python -m scripts.verificar_dibujo
    python -m scripts.verificar_dibujo --sin-tools    # el mismo camino, sin herramientas

`verificar_vision.py` contesta si VE. Este contesta algo anterior y peor: si
VUELVE. Porque el camino de la imagen ya dejó al tutor mudo tres veces —
`ses_6b430731226f`, `ses_50d5fa00b5d8` y `ses_5d101caf627f`— y las tres el niño
se quedó hablándole a una pantalla:

    nino: [le muestra al tutor un dibujo que hizo]
    nino: ¿O bien? Ya la hice, ¿me quedó bien?
    tutor: [el tutor no contestó: se quedó callado]
    nino: Walter, ¿qué te está pasando?

La diferencia con `verificar_vision` es TODO lo que ese script simplifica: acá
se conecta con la configuración REAL del producto —el prompt de sesión entero y
las ocho herramientas— y se reproduce la secuencia completa que llevó al
silencio, incluido el `pedir_dibujo` NON_BLOCKING que va justo antes.

Esa es la sospecha que viene a probar o a descartar: que lo que cuelga al modelo
no sea la imagen, sino el estado en que lo deja la herramienta anterior.

Necesita Pillow y una GOOGLE_API_KEY con saldo.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from google import genai  # noqa: E402

from tutor import config as cfg  # noqa: E402
from tutor.voice import (  # noqa: E402
    ConfiguracionSesion,
    construir_instruccion_sistema,
    deteccion_para_edad,
    instruccion_de_apertura,
)

# Los mismos que la hoja del niño. Si la prueba dibuja distinto del producto,
# no está probando el producto.
FONDO, TINTA, GROSOR = "#fffdf7", "#33312c", 7
ANCHO, ALTO = 640, 420

RESUMEN_JUAN = (
    "Juan, 7 años, 2° grado. Le gustan los dinosaurios y el fútbol. "
    "Viene trabajando sílabas trabadas y la escritura de letras."
)

# El pedido que arrancó todo, textual de la transcripción.
PIDE_LA_J = "Necesito que me ayudes a aprender a hacer la letra j."


def _aviso_del_dibujo() -> str:
    """El aviso REAL que el navegador manda con la hoja, leído de su fuente.

    Vive en TypeScript (`AVISO_DEL_DIBUJO`) porque lo manda el cliente. Copiarlo
    acá lo dejaría desincronizado el día que alguien lo edite, y este script
    estaría probando un mensaje que ya no existe.
    """
    ts = (Path(__file__).resolve().parents[1] / "web/src/voz/useTutor.ts").read_text(
        encoding="utf-8"
    )
    bloque = re.search(r"AVISO_DEL_DIBUJO\s*=\s*(.*?);", ts, re.S)
    if not bloque:
        raise SystemExit("No encontré AVISO_DEL_DIBUJO en useTutor.ts")
    return "".join(re.findall(r'"([^"]*)"', bloque.group(1)))


def jota_dibujada() -> str:
    """Una J hecha a mano, como la haría un niño de 7 con el dedo.

    Sale un poco torcida a propósito: una J perfecta invita a "¡te quedó
    perfecta!" sin mirar, que es el otro bug de este mismo camino.
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    im = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(im)
    x, arriba, abajo = 360, 90, 300
    d.line([x, arriba, x + 6, abajo], fill=TINTA, width=GROSOR)  # el palo
    d.arc([x - 110, abajo - 70, x + 14, abajo + 60], 0, 170, fill=TINTA, width=GROSOR)  # la panza
    d.line([x - 70, arriba, x + 40, arriba - 6], fill=TINTA, width=GROSOR)  # el sombrerito
    b = io.BytesIO()
    im.save(b, "JPEG", quality=90)
    return base64.b64encode(b.getvalue()).decode()


# Lo que el navegador responde a cada tool, copiado de `atenderTool`. Los que
# van al backend se contestan con algo plausible: acá no se prueba el backend,
# se prueba si el modelo vuelve a hablar.
def responder_tool(nombre: str, args: dict) -> dict:
    if nombre == "pedir_dibujo":
        return {"hoja_abierta": True}
    if nombre == "mostrar_en_pizarra":
        return {"mostrado": True, "en_pantalla": "la letra J grande"}
    if nombre == "get_next_problem":
        return {"ejercicio": {"id": "esc.j.1", "enunciado": {"es": "Escribe la letra J"}}}
    if nombre in ("check_answer", "verify_arithmetic", "verify_language"):
        return {"correcto": True, "veredicto": "correcto"}
    if nombre == "request_camera":
        return {"camara_pedida": True}
    return {"ok": True}


# Elogio vacío: la frase hecha que se cierra sola.
#
# El detector busca el adjetivo pegado a un signo de puntuación, y esa es toda
# su inteligencia: "te quedó súper bien." se cierra sin nombrar nada, mientras
# que "esa curva te quedó bien cerradita" sigue con lo que estuvo bien y no
# matchea. Es la lección de `verificar_vision`: un detector que busca la palabra
# suelta reprueba también al que acierta.
_ELOGIO_VACIO = re.compile(
    r"(te qued[óo]|te sali[óo]|qued[óo]|est[áa])\s+(s[úu]per\s+|muy\s+)?"
    r"(bien|genial|perfect[ao]|ch[ée]vere|lind[ao])\s*([.!?,¡]|$)",
    re.IGNORECASE,
)


def elogios_vacios(dicho: str) -> list[str]:
    """Las frases hechas que aparecieron. Vacía = el elogio nombró algo."""
    return [m.group(0).strip() for m in _ELOGIO_VACIO.finditer(dicho)]


class Turno:
    """Lo que llegó del modelo en un turno: qué dijo, qué pidió, si cerró."""

    def __init__(self) -> None:
        self.dicho: list[str] = []
        self.tools: list[str] = []
        self.audio = 0
        self.cerro = False
        self.venció = False
        self.arranco_ms: float | None = None
        """Cuánto tardó el PRIMER bloque de audio. Es lo que el niño siente."""

    def __str__(self) -> str:
        que = "".join(self.dicho).strip()
        partes = []
        if self.tools:
            partes.append(f"tools: {', '.join(self.tools)}")
        arranque = f"{round(self.arranco_ms)} ms" if self.arranco_ms else "nunca"
        partes.append(f"audio: {self.audio} bloques · arrancó a los {arranque}")
        vacios = elogios_vacios(que)
        if vacios:
            partes.append(f"ELOGIO VACÍO: {vacios[0]!r}")
        if self.venció:
            partes.append("NO CONTESTÓ")
        elif not self.cerro:
            partes.append("no cerró el turno")
        return f"[{' · '.join(partes)}]\n    {que or '(nada)'}"


def bloque_de_ruido(nivel: float = 0.004, muestras: int = 1024) -> str:
    """Un bloque de micrófono en una habitación callada.

    NO es silencio digital: un micrófono real nunca manda ceros. Manda el piso
    de ruido del cuarto, que es lo que este número imita —bien por debajo del
    umbral de barge-in del navegador (0,045), o sea inaudible para nosotros.

    Es la única diferencia entre este script y el producto, y por eso existe:
    el navegador manda esto SIN PARAR, también cuando nadie habla.
    """
    import random  # noqa: PLC0415
    import struct  # noqa: PLC0415

    vals = [max(-32768, min(32767, int(random.gauss(0, nivel) * 32767))) for _ in range(muestras)]
    return base64.b64encode(struct.pack(f"<{muestras}h", *vals)).decode()


def _ms_esperando_mirada() -> int:
    """El piso REAL del producto, leído de su fuente.

    Si el script simulara un micrófono que vuelve a los 2 s cuando el navegador
    espera 8, estaría probando un producto que no existe — que es exactamente
    como el número viejo sobrevivió sin que nadie lo midiera.
    """
    ts = (Path(__file__).resolve().parents[1] / "web/src/voz/useTutor.ts").read_text(
        encoding="utf-8"
    )
    return int(re.search(r"MS_ESPERANDO_MIRADA\s*=\s*(\d+)", ts).group(1))


async def bombear_micro(sesion, desde_ms: int | None = None) -> None:
    """Reabre el micrófono cuando lo hace el navegador, y no para."""
    desde_ms = _ms_esperando_mirada() if desde_ms is None else desde_ms
    await asyncio.sleep(desde_ms / 1000)
    while True:
        try:
            await sesion.send_realtime_input(
                audio={"data": bloque_de_ruido(), "mimeType": "audio/pcm;rate=16000"}
            )
        except Exception:  # noqa: BLE001 — la sesión se cerró: la tarea muere
            return
        await asyncio.sleep(0.064)


# Los dos que se declaran NON_BLOCKING en `voice.py`. Su respuesta es la que
# lleva `scheduling`; a los normales el campo no les corresponde.
NO_BLOQUEANTES = ("mostrar_en_pizarra", "pedir_dibujo")


async def escuchar(sesion, limite: float = 25.0, scheduling: str | None = None) -> Turno:
    """Lee un turno entero, atendiendo tools como lo hace el navegador."""
    t = Turno()
    empezo = asyncio.get_event_loop().time()

    async def leer() -> None:
        async for r in sesion.receive():
            if r.tool_call and r.tool_call.function_calls:
                respuestas = []
                for fc in r.tool_call.function_calls:
                    t.tools.append(fc.name)
                    respuesta = {
                        "id": fc.id,
                        "name": fc.name,
                        "response": responder_tool(fc.name, fc.args or {}),
                    }
                    if scheduling and fc.name in NO_BLOQUEANTES:
                        respuesta["scheduling"] = scheduling
                    respuestas.append(respuesta)
                await sesion.send_tool_response(function_responses=respuestas)
                continue
            sc = r.server_content
            if not sc:
                continue
            if sc.output_transcription and sc.output_transcription.text:
                t.dicho.append(sc.output_transcription.text)
            if sc.model_turn:
                for parte in sc.model_turn.parts or []:
                    if parte.inline_data and parte.inline_data.data:
                        if t.arranco_ms is None:
                            t.arranco_ms = (asyncio.get_event_loop().time() - empezo) * 1000
                        t.audio += 1
            if sc.turn_complete:
                t.cerro = True
                return

    try:
        await asyncio.wait_for(leer(), limite)
    except TimeoutError:
        t.venció = True
    return t


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-tools", action="store_true", help="el mismo camino, sin herramientas")
    ap.add_argument(
        "--bloqueantes",
        action="store_true",
        help="quita behavior=NON_BLOCKING de la pizarra y el dibujo",
    )
    ap.add_argument(
        "--con-micro",
        action="store_true",
        help="manda audio de fondo mientras espera, como hace el navegador de verdad",
    )
    ap.add_argument(
        "--scheduling",
        choices=("INTERRUPT", "WHEN_IDLE", "SILENT"),
        help="agenda la respuesta de los tools NON_BLOCKING (lo que el navegador NO manda)",
    )
    args = ap.parse_args()

    clave = os.getenv("GOOGLE_API_KEY")
    if not clave:
        print("\n  Falta GOOGLE_API_KEY en .env\n")
        return 1

    configuracion = ConfiguracionSesion(
        instruccion_sistema=construir_instruccion_sistema(RESUMEN_JUAN),
        deteccion=deteccion_para_edad(7),
        **({"tools": []} if args.sin_tools else {}),
    )
    config = configuracion.a_dict_gemini()
    if args.sin_tools:
        config.pop("tools", None)
    if args.bloqueantes:
        for d in config["tools"][0]["functionDeclarations"]:
            d.pop("behavior", None)

    cliente = genai.Client(api_key=clave, http_options={"api_version": "v1alpha"})

    print("=" * 74)
    print(f"  ¿VUELVE DESPUÉS DEL DIBUJO?   modelo: {cfg.MODELO_TUTOR_VOZ}")
    print(f"  herramientas: {'NO (control)' if args.sin_tools else 'las 8 del producto'}")
    if args.bloqueantes:
        print("  behavior: los ocho tools BLOQUEANTES (sin NON_BLOCKING)")
    agenda = args.scheduling or "ninguno (como el navegador hoy)"
    print(f"  scheduling en los NON_BLOCKING: {agenda}")
    print("=" * 74)

    async with cliente.aio.live.connect(model=cfg.MODELO_TUTOR_VOZ, config=config) as s:
        print("\n1. La apertura (el tutor habla primero)")
        await s.send_client_content(
            turns={"role": "user", "parts": [{"text": instruccion_de_apertura()}]},
            turn_complete=True,
        )
        print(f"   {await escuchar(s, scheduling=args.scheduling)}")

        print(f"\n2. El niño pide la J — «{PIDE_LA_J}»")
        await s.send_client_content(
            turns={"role": "user", "parts": [{"text": PIDE_LA_J}]}, turn_complete=True
        )
        paso2 = await escuchar(s, scheduling=args.scheduling)
        print(f"   {paso2}")

        vuelve = f" + el micrófono que vuelve a los {_ms_esperando_mirada()} ms"
        etiqueta = vuelve if args.con_micro else ""
        print(f"\n3. Le manda el dibujo (imagen DENTRO del turno{etiqueta})")
        await s.send_client_content(
            turns={
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": "image/jpeg", "data": jota_dibujada()}},
                    {"text": _aviso_del_dibujo()},
                ],
            },
            turn_complete=True,
        )
        micro = asyncio.create_task(bombear_micro(s)) if args.con_micro else None
        paso3 = await escuchar(s, scheduling=args.scheduling)
        if micro:
            micro.cancel()
        print(f"   {paso3}")

        if not paso3.audio:
            print("\n4. El empujón del vigilante (10 s después, como en producción)")
            ts = (Path(__file__).resolve().parents[1] / "web/src/voz/useTutor.ts").read_text(
                encoding="utf-8"
            )
            bloque = re.search(r"AVISO_DE_MUDEZ\s*=\s*(.*?);", ts, re.S)
            aviso = "".join(re.findall(r'"([^"]*)"', bloque.group(1)))
            await s.send_client_content(
                turns={"role": "user", "parts": [{"text": aviso}]}, turn_complete=True
            )
            print(f"   {await escuchar(s, scheduling=args.scheduling)}")

    print("\n" + "=" * 74)
    if not paso3.audio:
        print("  REPRODUCIDO: el tutor NO habló después del dibujo.")
        print(f"  Lo último que pidió antes: {', '.join(paso2.tools) or 'nada'}")
    else:
        print(f"  El tutor SÍ habló después del dibujo ({paso3.audio} bloques de audio).")
        vacios = elogios_vacios("".join(paso3.dicho))
        if vacios:
            print(f"  Pero elogió sin nombrar nada: {', '.join(repr(v) for v in vacios)}")
        else:
            print("  Y su elogio nombró algo concreto, o no elogió.")
        if not paso3.cerro:
            print("  Pero NO cerró el turno: la transcripción del tutor se pierde.")
    print("=" * 74)
    return 1 if not paso3.audio else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
