"""¿Cuánto se traba la conversación? El número que faltaba.

    python -m scripts.medir_fluidez
    python -m scripts.medir_fluidez --desde ses_567fc061b515

"No está fluida" es la queja más repetida sobre este producto y la única que
nunca tuvo un número detrás. Se discutió tres veces mirando el backend —que
responde en 4 ms— y las tres el problema estaba en otro lado.

Esto lo mide sobre lo único que queda de cada sesión: la transcripción. No mide
latencia (esa vive en la consola del navegador); mide **lo que el niño siente**,
que son tres cosas distintas y se confundían entre sí:

  · CORTADO   el turno del tutor termina a mitad de palabra. Alguien le cortó
              la generación — antes, el eco de su propia voz entrando por el
              micrófono con el VAD en sensibilidad alta.
  · RETOMA    dos turnos seguidos del tutor sin el niño en medio: se cortó y
              volvió a arrancar. Cada uno es una frase que el niño oyó dos veces
              a medias.
  · MUDEZ     `MARCA_DE_MUDEZ`: se quedó callado y hubo que empujarlo.
  · SIN VOZ   `MARCA_DE_VOZ_MUDA`: contestó, pero el niño no lo oyó. Es la peor
              de todas y la que no se veía — el texto llega por un camino y el
              audio por otro, así que la transcripción se ve igual de sana.
  · SORDO     `MARCA_DE_SORDERA`: el niño habló y su voz no llegó a ningún
              lado. La espejo de SIN VOZ, y la que dejó morir en silencio a
              `ses_60ea3b164f17` — nadie la miraba porque el vigilante de la
              mudez se arma cuando llega la voz del niño.
  · NIÑO✂     el turno del NIÑO termina a mitad de frase. Este mira para el otro
              lado: el VAD del servidor le cerró el turno antes de que
              terminara de hablar. «Tengo una tarea de» (`ses_02805f3edba1`) es
              un chico de 7 años pensando cómo seguir, y el sistema decidió por
              él que ya había terminado.
  · NIÑO✁     el turno del niño EMPIEZA a mitad de frase. Los otros tres miran
              el final; este mira el principio, y es el que explica «mi audio le
              llega tarde» (`ses_31593f90ab26`). El micrófono le tiraba hasta
              medio segundo de audio cada vez que el tutor terminaba de hablar,
              por considerarlo eco — y ahí estaba el arranque de su respuesta.

No necesita API key ni red: lee `data/transcripts/`. Correrlo después de cada
sesión es la forma de saber si un cambio mejoró algo o solo lo movió de lugar.
"""

from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tutor import config as cfg  # noqa: E402

TRANSCRIPTS = cfg.RAIZ / "data" / "transcripts"

# Un turno que no termina en signo de cierre quedó a mitad de frase. Los puntos
# suspensivos cuentan como cierre: el tutor los usa a propósito al dejar algo
# abierto.
#
# Y los DOS PUNTOS también, que es un falso positivo que costó tiempo: el
# playbook le ORDENA al tutor decir una frase corta antes de usar una
# herramienta —«a ver, déjame busco...», «de una, ahí te va:»— para que el niño
# no oiga silencio mientras se resuelve. Contar eso como "se cortó" convertía
# el cumplimiento de una regla en una alarma, y mandaba a buscar un bug donde
# había buen comportamiento.
CIERRES = '.!?"»)]…:'

# Lo que el navegador escribe cuando algo sale mal. Vive en `useTutor.ts` y se
# lee de ahí para que no se desincronice.
def _marca(nombre: str, respaldo: str) -> str:
    import re  # noqa: PLC0415

    ts = (cfg.RAIZ / "web" / "src" / "voz" / "useTutor.ts").read_text(encoding="utf-8")
    m = re.search(rf'{nombre}\s*=\s*"([^"]*)"', ts)
    return m.group(1) if m else respaldo


def _marca_de_mudez() -> str:
    return _marca("MARCA_DE_MUDEZ", "[el tutor no contestó")


def _marca_de_voz_muda() -> str:
    return _marca("MARCA_DE_VOZ_MUDA", "[el niño no oyó esto")


def _marca_de_sordera() -> str:
    return _marca("MARCA_DE_SORDERA", "[el niño habló acá")


def _turnos(texto: str) -> list[tuple[str, str]]:
    """Un turno puede ocupar VARIAS líneas, y eso rompía la medición entera.

    El modelo mete saltos de línea en lo que dice —párrafos, o el hueco que
    deja un tool call en medio de la frase—. La primera versión de esto leía
    solo las líneas que empiezan con `tutor:` o `nino:` y **descartaba el
    resto**: 14 de 82 líneas en `ses_6c6fb58aafbb`.

    El efecto era doble y en la misma dirección: un turno que termina bien tres
    líneas más abajo se contaba como CORTADO, porque la primera línea queda a
    mitad de palabra. Así, «…Vamos con las letras pues. A ver, déjame busco»
    figuraba como corte del VAD cuando en realidad seguía —«…la primera.
    Espérame un momentico.»— y era el silencio de un tool call.

    O sea que el número de cortes estaba inflado por el propio instrumento, y
    dos de los cuatro «cortes» que se le atribuyeron al VAD eran esto.
    """
    salida: list[tuple[str, str]] = []
    for linea in texto.splitlines():
        if linea.startswith("tutor:"):
            salida.append(("tutor", linea[6:].strip()))
        elif linea.startswith("nino:"):
            salida.append(("nino", linea[5:].strip()))
        elif salida:
            # Continuación del turno anterior. Se pega con un espacio: acá
            # interesa dónde TERMINA el turno, no cómo estaba maquetado.
            quien, dicho = salida[-1]
            salida[-1] = (quien, f"{dicho} {linea.strip()}".strip())
    return salida


def medir(texto: str, marca_mudez: str) -> dict:
    turnos = _turnos(texto)
    del_tutor = [t for quien, t in turnos if quien == "tutor" and t]

    cortados = [t for t in del_tutor if t and t[-1] not in CIERRES]

    # Los del niño, que son la falla espejo: acá el VAD le cerró el turno ANTES
    # de que terminara de hablar.
    #
    # Dos exclusiones, y las dos son casos legítimos que sin ellas se contaban
    # como cortes y tapaban los de verdad:
    #   · menos de tres palabras — "impar", "nueve", "bueno sí": una respuesta
    #     corta no lleva punto y está completa.
    #   · contar en voz alta — "1 2 3 4 5 6 7 8 9 10 11 12" es un niño contando
    #     hasta el final, no un niño interrumpido.
    del_nino = [t for quien, t in turnos if quien == "nino" and t]
    cortados_nino = [
        t
        for t in del_nino
        if t
        and t[-1] not in CIERRES
        and len(t.split()) >= 3
        and not all(p.isdigit() for p in t.split())
    ]

    # Y la falla que faltaba: el turno del niño cortado POR DELANTE.
    #
    # Las otras tres miran el final de la frase. Esta mira el principio, y es la
    # que explica «mi audio le llega tarde» (`ses_31593f90ab26`, 25/08): el
    # micrófono le tiraba al niño hasta medio segundo de audio cada vez que el
    # tutor terminaba de hablar, por considerarlo eco. Adentro estaba el arranque
    # de su respuesta — «respuesta, si era que primero se hacía la línea recta»,
    # «estadio. Y ahí vieron un partido», «hacer».
    #
    # La señal es la minúscula inicial: el transcriptor abre en mayúscula, así
    # que una frase que empieza en minúscula empezó antes de lo que se oyó. Se
    # exigen cuatro palabras para no contar las respuestas sueltas —"siete",
    # "impar"—, que legítimamente vienen en minúscula por ser continuación.
    descabezados = [
        t for t in del_nino if len(t.split()) >= 4 and t[:1].islower()
    ]

    # Dos turnos del tutor seguidos: se cortó y retomó.
    retomas = sum(
        1
        for i in range(1, len(turnos))
        if turnos[i][0] == "tutor" and turnos[i - 1][0] == "tutor"
    )

    mudeces = sum(1 for _, t in turnos if marca_mudez[:20] in t)

    # LA PEOR DE TODAS, y la que no se veía. El tutor contestó, la
    # transcripción llegó, el muñeco movió la boca — y por el parlante no salió
    # nada. `ses_660ce383567d`: «estás hablando y hablando y como que no se
    # escucha, solo leo lo que estás diciendo». Sin esta marca, esa sesión se
    # ve idéntica a una sana: el texto llega por un camino y el audio por otro.
    voz_muda = sum(1 for _, t in turnos if _marca_de_voz_muda()[:20] in t)

    # La espejo de la anterior, y la que dejó morir `ses_60ea3b164f17` en
    # silencio: el niño habló y su voz no llegó a ningún lado. Nadie la miraba
    # porque el vigilante de la mudez se arma CUANDO llega la voz del niño.
    sordera = sum(1 for _, t in turnos if _marca_de_sordera()[:20] in t)

    return {
        "turnos": len(del_tutor),
        "cortados": len(cortados),
        "retomas": retomas,
        "mudeces": mudeces,
        "voz_muda": voz_muda,
        "sordera": sordera,
        "cortados_nino": len(cortados_nino),
        "descabezados": len(descabezados),
        "turnos_nino": len(del_nino),
        "ejemplos": ["…" + t[-34:] for t in cortados[:2]],
        "ejemplos_nino": ["…" + t[-34:] for t in cortados_nino[:2]],
        "ejemplos_descabezados": [t[:34] + "…" for t in descabezados[:2]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", help="solo las sesiones desde esta (por id), inclusive")
    args = ap.parse_args()

    if not TRANSCRIPTS.is_dir():
        print(f"\n  No hay transcripciones en {TRANSCRIPTS}\n")
        return 1

    archivos = sorted(TRANSCRIPTS.glob("*.txt"), key=lambda p: p.stat().st_mtime)
    if args.desde:
        desde = [i for i, f in enumerate(archivos) if f.stem == args.desde]
        if not desde:
            print(f"\n  No encuentro {args.desde}\n")
            return 1
        archivos = archivos[desde[0] :]

    marca = _marca_de_mudez()
    print("=" * 78)
    print("  FLUIDEZ — lo que el niño siente, contado sobre las transcripciones")
    print("=" * 78)
    print(
        f"\n{'sesión':22}{'turnos':>7}{'cortados':>10}{'retomas':>9}{'mudez':>7}"
        f"{'niño✂':>8}{'niño✁':>8}{'sin voz':>9}{'sordo':>7}"
    )

    total = {
        "turnos": 0,
        "cortados": 0,
        "retomas": 0,
        "mudeces": 0,
        "voz_muda": 0,
        "sordera": 0,
        "cortados_nino": 0,
        "descabezados": 0,
        "turnos_nino": 0,
    }
    peores: list[tuple[str, list[str]]] = []
    peores_nino: list[tuple[str, list[str]]] = []
    peores_cabeza: list[tuple[str, list[str]]] = []
    for f in archivos:
        m = medir(f.read_text(encoding="utf-8"), marca)
        if not m["turnos"]:
            continue
        for k in total:
            total[k] += m[k]
        print(
            f"{f.stem:22}{m['turnos']:>7}{m['cortados']:>10}{m['retomas']:>9}"
            f"{m['mudeces']:>7}{m['cortados_nino']:>8}{m['descabezados']:>8}"
            f"{m['voz_muda']:>9}{m['sordera']:>7}"
        )
        if m["ejemplos"]:
            peores.append((f.stem, m["ejemplos"]))
        if m["ejemplos_nino"]:
            peores_nino.append((f.stem, m["ejemplos_nino"]))
        if m["ejemplos_descabezados"]:
            peores_cabeza.append((f.stem, m["ejemplos_descabezados"]))

    t = max(total["turnos"], 1)
    print("\n" + "-" * 78)
    print(
        f"  {total['cortados']}/{total['turnos']} turnos cortados "
        f"({100 * total['cortados'] / t:.0f}%) · "
        f"{total['retomas']} retomas · {total['mudeces']} mudeces · "
        f"{total['cortados_nino']} turnos del niño cortados al final · "
        f"{total['descabezados']} descabezados · "
        f"{total['voz_muda']} turnos que el niño NO OYÓ · "
        f"{total['sordera']} veces que al niño NO LO OYERON"
    )

    if peores:
        print("\n  Dónde se cortó (últimas):")
        for sesion, ejemplos in peores[-3:]:
            for e in ejemplos:
                print(f"    {sesion}  {e}")

    if peores_nino:
        print("\n  Dónde se le cortó AL NIÑO (el VAD le cerró el turno antes):")
        for sesion, ejemplos in peores_nino[-3:]:
            for e in ejemplos:
                print(f"    {sesion}  {e}")

    if peores_cabeza:
        print("\n  Dónde empezó a mitad (el micrófono se comió el arranque):")
        for sesion, ejemplos in peores_cabeza[-3:]:
            for e in ejemplos:
                print(f"    {sesion}  {e}")

    # Las dos referencias contra las que se compara un cambio. Si vuelven a
    # subir, algo desarmó el arreglo que las bajó.
    print("\n  Referencia: 20% de cortes el 23/08 (8 sesiones, antes del arreglo).")
    print("  Referencia: 10,3% de turnos del niño descabezados el 20/08 (165 turnos).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
