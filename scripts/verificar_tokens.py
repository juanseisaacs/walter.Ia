"""Resuelve la duda que quedo abierta en useTutor.ts: `totalTokenCount`
que manda Gemini Live, es de SU request o el acumulado de la sesion?

De la respuesta depende el presupuesto entero. Si es acumulativo y los sumamos,
el gasto que reportamos esta varias veces sobreestimado -- y estariamos
recortando el producto por un numero inventado. Si es por request, el consumo
que medimos es real y el prompt se paga en cada turno.

Se prueba con TEXTO de entrada (el modelo solo devuelve audio, pero la entrada
acepta texto). Varios turnos cortos y se mira como evoluciona el numero:

    monotono creciente (500, 1200, 2100...) -> ACUMULATIVO, hay que reportar el ultimo
    estable o sin patron                    -> POR REQUEST, la suma esta bien

    python -m scripts.verificar_tokens
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from google import genai  # noqa: E402

from tutor import config as cfg  # noqa: E402
from tutor.voice import construir_instruccion_sistema  # noqa: E402

TURNOS = [
    "Hola, soy Juan.",
    "Tengo siete anos.",
    "Me gusta el futbol.",
    "Cuanto es dos mas dos?",
    "Y tres mas tres?",
]


async def main() -> None:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise SystemExit("Falta GOOGLE_API_KEY en .env")

    instruccion = construir_instruccion_sistema("Juan, 7 anos, 2do grado.")
    print(f"Prompt de sesion: {len(instruccion):,} caracteres (~{len(instruccion)//4:,} tokens)")
    print(f"Modelo: {cfg.MODELO_TUTOR_VOZ}\n")

    c = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})
    config = {"response_modalities": ["AUDIO"], "system_instruction": instruccion}

    medidas: list[int] = []
    async with c.aio.live.connect(model=cfg.MODELO_TUTOR_VOZ, config=config) as sesion:
        for i, texto in enumerate(TURNOS, 1):
            await sesion.send_client_content(
                turns={"role": "user", "parts": [{"text": texto}]}, turn_complete=True
            )
            del_turno = 0
            async for respuesta in sesion.receive():
                uso = getattr(respuesta, "usage_metadata", None)
                if uso and getattr(uso, "total_token_count", None):
                    del_turno = uso.total_token_count
                sc = getattr(respuesta, "server_content", None)
                if sc and getattr(sc, "turn_complete", False):
                    break
            medidas.append(del_turno)
            print(
                f"  turno {i}: total_token_count = {del_turno:>8,}   "
                f"(suma acumulada {sum(medidas):>9,})"
            )

    print()
    utiles = [m for m in medidas if m]
    if len(utiles) < 2:
        print("  No llegaron suficientes mediciones para concluir.")
        return

    # strict=False a propósito: comparar pares consecutivos empareja n con n-1,
    # así que la última sobra. Con strict=True esto lanzaría ValueError.
    creciente = all(b > a for a, b in zip(utiles, utiles[1:], strict=False))
    print("=" * 62)
    if creciente:
        print("  ACUMULATIVO: el numero crece en cada turno.")
        print("  -> Hay que reportar el ULTIMO, no la suma.")
        print(f"  -> Lo real de esta sesion seria {utiles[-1]:,}, no {sum(medidas):,}.")
        print(f"  -> Estamos sobreestimando {sum(medidas)/utiles[-1]:.1f}x")
    else:
        print("  POR REQUEST: el numero no crece monotono.")
        print("  -> Sumarlos es correcto. El consumo medido es real.")
        print(f"  -> Promedio por turno: {sum(utiles)//len(utiles):,}")
    print("=" * 62)


if __name__ == "__main__":
    asyncio.run(main())
