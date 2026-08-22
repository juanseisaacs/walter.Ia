"""Prueba de punta a punta de la pantalla del niño, con navegador de verdad.

    python -m scripts.e2e_voz              # completo: abre sesión real. GASTA CUOTA
    python -m scripts.e2e_voz --sin-voz    # solo lo que no cuesta nada
    python -m scripts.e2e_voz --ver        # con el navegador a la vista

Es lo que `PENDIENTE.md` viene pidiendo desde hace días: *«una sesión de voz con
audio real»*, hecha a mano cada vez. Acá se automatiza lo que se puede.

**Por qué no se parece a la prueba equivalente de otros tutores.** Cuando el
servidor hace de proxy del audio, basta con espiar su WebSocket para ver todo lo
que pasa. Acá el navegador habla DIRECTO con Gemini (`ARCHITECTURE.md` §10), así
que el backend no ve una sola palabra y no hay nada que espiar desde afuera: hay
que observar desde la propia página — el estado de la UI, la consola y lo que el
backend sí recibe (los turnos reportados, que es el candado #2).

**Contra una base desechable.** Levanta su propio backend con `DATOS_DIR`
apuntando a un temporal, así que ni un niño inventado ni una sesión de prueba
tocan `data/`. Las 19 sesiones vacías que ensucian la base de hoy salieron
justamente de probar contra los datos de verdad.

Lo que comprueba, en orden:

  1. el backend levanta y responde
  2. la app carga SIN un solo error de consola  ← acá cae casi todo lo que rompe
  3. sin enlace, el niño ve que le pidan el enlace (no una pantalla en blanco)
  4. con enlace, aparece el botón de empezar
  5. (con voz) al apretarlo, la sesión llega a "Te escucho", y se mide cuánto tardó
  6. (con voz) el backend registró la sesión, y al terminar quedó encolada
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web" / "dist"

# Cuánto se espera a que el tutor conteste antes de darlo por muerto. Generoso a
# propósito: si esto salta, el problema no es el margen.
ESPERA_SESION_MS = 40_000


# ─────────────────────────────────────────────────────────────────────────────
# Marcador de resultados
# ─────────────────────────────────────────────────────────────────────────────


class Resultados:
    """Acumula comprobaciones y decide el código de salida.

    Va acumulando en vez de reventar en la primera: una corrida que falla en el
    paso 2 y no dice nada de los otros seis obliga a correrla siete veces.
    """

    def __init__(self) -> None:
        self.pasadas = 0
        self.fallos: list[str] = []

    def comprobar(self, nombre: str, condicion: bool, detalle: str = "") -> bool:
        if condicion:
            self.pasadas += 1
            print(f"  ok    {nombre}")
        else:
            self.fallos.append(f"{nombre}{' — ' + detalle if detalle else ''}")
            print(f"  FALLA {nombre}  {detalle}")
        return condicion

    def dato(self, nombre: str, valor: str) -> None:
        print(f"  ·     {nombre}: {valor}")

    def resumen(self) -> int:
        print()
        if self.fallos:
            print(f"  {self.pasadas} pasaron, {len(self.fallos)} FALLARON:")
            for f in self.fallos:
                print(f"    ✗ {f}")
            print()
            return 1
        print(f"  {self.pasadas} comprobaciones pasaron.\n")
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# El backend de prueba
# ─────────────────────────────────────────────────────────────────────────────


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _esperar_backend(puerto: int, segundos: int = 30) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/salud", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            time.sleep(0.4)
    return False


def _sembrar_nino(datos: Path) -> str:
    """Un niño de 2° en la base desechable. Devuelve su id.

    Se crea con el mismo camino que usa el onboarding real —`crear_nino_desde
    _ficha`— y no escribiendo la fila a mano: si el alta cambia, esta prueba se
    entera.
    """
    entorno = dict(os.environ, DATOS_DIR=str(datos))
    codigo = (
        "from tutor.pipeline import FichaInicial, crear_nino_desde_ficha;"
        "from tutor.storage import RepositorioSQLite;"
        "from tutor import config as cfg;"
        "f=FichaInicial(nombre_nino='Prueba', edad=7, grado=2, email_papa='e2e@ejemplo.test');"
        "n=crear_nino_desde_ficha(f,'n_e2e');"
        "RepositorioSQLite(cfg.DB, cfg.DATOS).guardar_nino(n);"
        "print(n.id)"
    )
    r = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=RAIZ, env=entorno, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(f"no se pudo sembrar el niño:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip().splitlines()[-1]


def _levantar_backend(datos: Path, puerto: int) -> subprocess.Popen:
    entorno = dict(
        os.environ,
        DATOS_DIR=str(datos),
        # Los topes de producción existen para proteger al niño y al margen; una
        # prueba que corre tres veces seguidas no puede chocar contra ellos.
        MAX_SESIONES_DIA="100",
        PYTHONIOENCODING="utf-8",
    )
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tutor.api:app",
         "--host", "127.0.0.1", "--port", str(puerto), "--log-level", "warning"],
        cwd=RAIZ, env=entorno,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )


def _sesiones_en(datos: Path) -> list[dict]:
    """Lo que quedó registrado en la base desechable."""
    import sqlite3

    db = datos / "tutor.db"
    if not db.exists():
        return []
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute("SELECT * FROM sesiones ORDER BY inicio")]
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# La prueba
# ─────────────────────────────────────────────────────────────────────────────


def _correr(
    res: Resultados, base: str, nino_id: str, datos: Path, con_voz: bool, ver: bool
) -> None:
    from playwright.sync_api import sync_playwright

    errores_consola: list[str] = []
    capturas = RAIZ / "capturas"
    capturas.mkdir(exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch(
            headless=not ver,
            args=[
                "--use-fake-ui-for-media-stream",      # concede el micrófono sin diálogo
                "--use-fake-device-for-media-stream",  # tono sintético en vez de micrófono real
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        ctx = navegador.new_context(
            viewport={"width": 430, "height": 932},   # un celular, que es donde vive
            device_scale_factor=2,
            permissions=["microphone"],
        )
        pag = ctx.new_page()
        pag.on("console", lambda m: errores_consola.append(m.text) if m.type == "error" else None)
        pag.on("pageerror", lambda e: errores_consola.append(f"excepción: {e}"))

        # ── 3. sin enlace ────────────────────────────────────────────────────
        pag.goto(base, wait_until="networkidle")
        res.comprobar(
            "sin enlace, le pide el enlace a un adulto",
            "el enlace para entrar" in pag.content(),
            "debería ver la pantalla de '¡Hola!', no una en blanco",
        )

        # ── 4. con enlace ────────────────────────────────────────────────────
        pag.goto(f"{base}/?nino={nino_id}", wait_until="networkidle")
        pag.wait_for_selector("text=¿Empezamos?", timeout=10_000)
        res.comprobar("con enlace, aparece el botón de empezar", True)
        res.comprobar(
            "también ofrece el modo Pedido",
            pag.locator("text=Traigo una tarea").count() == 1,
            "el modo Pedido existía completo y sin forma de llegar a él",
        )
        pag.screenshot(path=str(capturas / "e2e-01-inicio.png"))

        # El id NO puede quedarse en la barra: un enlace compartido por accidente
        # deja entrar a cualquiera como ese niño.
        res.comprobar(
            "el id del niño se borra de la URL",
            "nino=" not in pag.url,
            f"quedó a la vista: {pag.url}",
        )

        if not con_voz:
            res.comprobar(
                "la app cargó sin errores de consola",
                not errores_consola,
                " | ".join(errores_consola[:3]),
            )
            navegador.close()
            return

        # ── 5. la sesión de verdad ───────────────────────────────────────────
        print("\n  abriendo sesión contra Gemini…")
        arranque = time.monotonic()
        pag.click("text=Hablar con mi tutor")

        llegó = True
        try:
            pag.wait_for_selector("text=Te escucho", timeout=ESPERA_SESION_MS)
        except Exception:
            llegó = False

        if not res.comprobar(
            "la sesión llega a escuchar al niño",
            llegó,
            pag.locator(".error").inner_text()
            if pag.locator(".error").count()
            else "se quedó conectando",
        ):
            pag.screenshot(path=str(capturas / "e2e-99-fallo.png"))
            navegador.close()
            return

        res.dato("del click a 'Te escucho'", f"{(time.monotonic() - arranque) * 1000:.0f} ms")
        pag.screenshot(path=str(capturas / "e2e-02-en-sesion.png"))

        tema = pag.locator(".tema").inner_text() if pag.locator(".tema").count() else ""
        res.comprobar(
            "el planificador eligió un tema y se ve en pantalla",
            tema.startswith("Hoy:"),
            f"decía {tema!r} — sin tema, el tutor improvisa ejercicios",
        )

        # ── 6. el backend se enteró ──────────────────────────────────────────
        sesiones = _sesiones_en(datos)
        res.comprobar(
            "el backend registró la sesión", len(sesiones) == 1, f"{len(sesiones)} sesiones"
        )

        # ── LA comprobación ──────────────────────────────────────────────────
        # El micrófono es sintético: emite un tono, no habla. Así que este niño
        # de prueba se comporta exactamente como el que abre la app y se queda
        # callado esperando — y ahí está lo que hay que medir.
        #
        # Medido el 22/08 sobre las 71 transcripciones reales: el niño abre la
        # conversación en las 52 que tienen contenido, el tutor en NINGUNA, y 19
        # quedaron vacías. Una de cada cuatro sesiones muere porque nadie rompe
        # el silencio. Un chico de 7 años frente a una cara que no le habla no
        # insiste: se va.
        print("  esperando 15 s a ver si el tutor rompe el silencio…")
        hablo = True
        try:
            pag.wait_for_selector("text=Tu tutor está hablando", timeout=15_000)
        except Exception:
            hablo = False
        pag.screenshot(path=str(capturas / "e2e-03-hablando.png"))

        res.comprobar(
            "el tutor le habla primero al niño",
            hablo,
            "15 s en 'Te escucho' sin decir nada. En 71 sesiones reales el tutor "
            "abrió la conversación 0 veces, y 19 murieron vacías",
        )

        pag.click("text=Terminar")
        pag.wait_for_timeout(2_500)

        sesiones = _sesiones_en(datos)
        cerrada = sesiones[0] if sesiones else {}
        res.comprobar("al terminar, la sesión queda cerrada", bool(cerrada.get("fin")))

        transcripcion = datos / "transcripts" / f"{cerrada.get('id')}.txt"
        turnos = transcripcion.read_text(encoding="utf-8").strip() if transcripcion.exists() else ""
        if turnos:
            res.dato("turnos registrados", str(len(turnos.splitlines())))
            res.dato("primera línea", turnos.splitlines()[0][:70])
            # Con turnos, la sesión TIENE que quedar en la cola del Analista.
            res.comprobar(
                "y encolada para el Analista",
                cerrada.get("analizada") == 0,
                "hubo conversación y salió de la cola sin analizarse",
            )
        else:
            # Sin turnos no hay nada que analizar y `procesar_sesion` la saca de
            # la cola con un WARNING: es el comportamiento diseñado, no un bug.
            # Lo que sí es un bug es que la sesión llegue vacía hasta acá.
            res.dato("transcripción", "VACÍA — nadie dijo una palabra en toda la sesión")

        res.comprobar(
            "ni un error de consola en toda la sesión",
            not errores_consola,
            " | ".join(errores_consola[:3]),
        )
        navegador.close()

    print(f"\n  capturas en {capturas.relative_to(RAIZ)}/")


def main() -> int:
    p = argparse.ArgumentParser(description="Prueba de punta a punta de la pantalla del niño.")
    p.add_argument("--sin-voz", action="store_true", help="No abre sesión: no gasta cuota")
    p.add_argument("--ver", action="store_true", help="Muestra el navegador")
    args = p.parse_args()
    con_voz = not args.sin_voz

    if not WEB.exists() or not (WEB / "index.html").exists():
        print("\n  Falta el build del front. Corré:  cd web && npm run build\n")
        return 1

    if con_voz and not os.getenv("GOOGLE_API_KEY"):
        print("\n  Falta GOOGLE_API_KEY en .env. Para la parte gratis: --sin-voz\n")
        return 1

    print("=" * 72)
    modo = "  ·  GASTA CUOTA" if con_voz else "  ·  sin voz, gratis"
    print(f"  E2E DE LA PANTALLA DEL NIÑO{modo}")
    print("=" * 72)

    datos = Path(tempfile.mkdtemp(prefix="rbh-e2e-"))
    puerto = _puerto_libre()
    res = Resultados()
    backend = None

    try:
        nino_id = _sembrar_nino(datos)
        res.dato("niño de prueba", nino_id)
        res.dato("datos desechables", str(datos))

        backend = _levantar_backend(datos, puerto)
        base = f"http://127.0.0.1:{puerto}"
        if not res.comprobar("el backend levanta y responde", _esperar_backend(puerto)):
            salida = backend.stdout.read() if backend.stdout else ""
            print(f"\n{salida[-1500:]}\n")
            return 1

        _correr(res, base, nino_id, datos, con_voz, args.ver)
        return res.resumen()

    finally:
        if backend is not None:
            backend.terminate()
            try:
                backend.wait(timeout=10)
            except subprocess.TimeoutExpired:
                backend.kill()
        # La base desechable se borra: lleva la transcripción de la sesión de
        # prueba, y el activo es la ficha, no la charla.
        shutil.rmtree(datos, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
