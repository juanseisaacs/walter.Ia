"""¿El tutor VE lo que el nino le muestra, o describe lo que esperaba ver?

    python -m scripts.verificar_vision

Existe porque durante tres dias el tutor invento todo lo que "vio". Dijo que un
circulo con UNA linea tenia dos, y le leyo al nino "5 + 3" en un cuaderno donde
decia "8 + 5". Nadie lo noto porque las verificaciones anteriores usaban
imagenes ADIVINABLES: una mano con cinco dedos, una gorra con letras. Un modelo
que no ve nada acierta las dos.

De ahi el metodo, y es lo unico que hace falta recordar de este archivo:

    SE LE MUESTRA ALGO QUE NO PUEDE ADIVINAR.

Un 7 gigante cuando el prompt dice que espera una torta. Un cuaderno con dos
cuentas concretas. Si contesta "una torta partida en cuatro", no vio: completo.

Se comparan los dos caminos de envio, porque la diferencia entre ellos es
exactamente la diferencia entre ver y no ver:

  - `send_realtime_input(video=...)`  el canal de streaming de camara
  - la imagen DENTRO del turno         `send_client_content` con `inlineData`

Necesita Pillow (`pip install pillow`) y una GOOGLE_API_KEY con saldo.
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import sys

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from google import genai  # noqa: E402

from tutor import config as cfg  # noqa: E402

# Los mismos que usa la hoja del nino (`HojaDelNino.tsx`): si la prueba dibuja
# distinto de como dibuja el producto, no esta probando el producto.
FONDO, TINTA, GROSOR = "#fffdf7", "#33312c", 7
ANCHO, ALTO = 640, 420
CALIDAD = 90


def _pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

        return Image, ImageDraw, ImageFont
    except ImportError:
        print("\n  Falta Pillow:  pip install pillow\n")
        raise SystemExit(1) from None


def _jpeg(im) -> str:
    b = io.BytesIO()
    im.save(b, "JPEG", quality=CALIDAD)
    return base64.b64encode(b.getvalue()).decode()


def dibujo_una_linea() -> str:
    """Un circulo partido por UNA linea. El tutor dijo que eran dos."""
    Image, ImageDraw, _ = _pillow()
    im = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(im)
    cx, cy, r = ANCHO // 2, ALTO // 2, 150
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=TINTA, width=GROSOR)
    d.line([cx, cy - r, cx, cy + r], fill=TINTA, width=GROSOR)
    return _jpeg(im)


def siete_gigante() -> str:
    """EL CONTROL. Nadie adivina un 7 cuando el prompt dice que espera una torta."""
    Image, ImageDraw, ImageFont = _pillow()
    im = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(im)
    d.text(
        (ANCHO // 2, ALTO // 2),
        "7",
        font=ImageFont.truetype("arialbd.ttf", 320),
        fill=TINTA,
        anchor="mm",
    )
    return _jpeg(im)


def cuaderno() -> str:
    """Dos cuentas concretas. Es el caso de la camara, y el que mas dano hace."""
    Image, ImageDraw, ImageFont = _pillow()
    im = Image.new("RGB", (800, 600), "#ffffff")
    d = ImageDraw.Draw(im)
    for y in range(80, 600, 60):
        d.line([40, y, 760, y], fill="#bcd4e8", width=2)
    f = ImageFont.truetype("arial.ttf", 90)
    d.text((90, 140), "8 + 5 =", font=f, fill="#1a2a6c")
    d.text((90, 300), "12 - 7 =", font=f, fill="#1a2a6c")
    return _jpeg(im)


PERSONA = (
    "Eres un tutor de primaria. Le pediste al nino que dibuje una torta partida "
    "en CUATRO pedazos iguales. Describe con precision lo que ves. Si no ves "
    "ninguna imagen, dilo."
)
PREGUNTA = "[Sistema: llego lo que el nino te muestra. Describe exactamente que ves.]"

# (nombre, como dibujarlo, que tiene que decir, que NO puede decir)
#
# El "no puede decir" no sobra: con solo pistas positivas, "veo UN circulo con
# cuatro lineas" cuenta como acierto porque dice "un". Lo que delata al que
# adivina es que completa la figura ESPERADA — cuatro pedazos, una torta.
CASOS = [
    (
        "circulo con UNA linea",
        dibujo_una_linea,
        ["una", "sola", "mitad", "dos"],
        ["cuatro", "4 pedazos", "dos lineas"],
    ),
    ("un 7 gigante (control)", siete_gigante, ["siete", "7"], ["torta", "circulo", "círculo"]),
    ("cuaderno: 8+5 y 12-7", cuaderno, ["8", "ocho"], ["torta", "circulo", "círculo"]),
]


async def _decir(sesion, limite: float = 30.0) -> str:
    dicho: list[str] = []

    async def leer() -> None:
        async for r in sesion.receive():
            if not r.server_content:
                continue
            if r.server_content.output_transcription:
                dicho.append(r.server_content.output_transcription.text or "")
            if r.server_content.turn_complete:
                return

    try:
        await asyncio.wait_for(leer(), limite)
    except TimeoutError:
        dicho.append(" <<no cerro el turno>>")
    return "".join(dicho).strip()


async def preguntar(cliente, imagen: str, via: str) -> str:
    config = {
        "responseModalities": ["AUDIO"],
        "outputAudioTranscription": {},
        "systemInstruction": {"parts": [{"text": PERSONA}]},
    }
    async with cliente.aio.live.connect(model=cfg.MODELO_TUTOR_VOZ, config=config) as s:
        if via == "realtime":
            await s.send_realtime_input(video={"data": imagen, "mimeType": "image/jpeg"})
            await asyncio.sleep(0.3)
            await s.send_client_content(
                turns={"role": "user", "parts": [{"text": PREGUNTA}]}, turn_complete=True
            )
        else:
            await s.send_client_content(
                turns={
                    "role": "user",
                    "parts": [
                        {"inlineData": {"mimeType": "image/jpeg", "data": imagen}},
                        {"text": PREGUNTA},
                    ],
                },
                turn_complete=True,
            )
        return await _decir(s)


async def main() -> int:
    clave = os.getenv("GOOGLE_API_KEY")
    if not clave:
        print("\n  Falta GOOGLE_API_KEY en .env\n")
        return 1

    cliente = genai.Client(api_key=clave, http_options={"api_version": "v1alpha"})

    print("=" * 74)
    print(f"  ¿VE O ADIVINA?   modelo: {cfg.MODELO_TUTOR_VOZ}")
    print("=" * 74)

    fallos = 0
    for nombre, hacer, pistas in CASOS:
        imagen = hacer()
        print(f"\n  {nombre}")
        for via, etiqueta in (("realtime", "canal de video "), ("turno", "dentro del turno")):
            dicho = await preguntar(cliente, imagen, via)
            acerto = any(p in dicho.lower() for p in pistas)
            marca = "ok" if acerto else "NO"
            print(f"    [{marca}] {etiqueta}: {dicho[:150]}")
            if via == "turno" and not acerto:
                fallos += 1

    print("\n" + "=" * 74)
    if fallos:
        print(f"  {fallos} caso(s) fallaron POR EL CAMINO QUE USA EL PRODUCTO.")
        print("  El tutor le esta inventando al nino lo que ve. Es bloqueante.")
    else:
        print("  El camino del producto (dentro del turno) ve bien.")
        print("  Si el canal de video acerto tambien, fue casualidad: mira el 7.")
    print("=" * 74 + "\n")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
