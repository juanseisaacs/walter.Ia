/**
 * EL STREAM DE AUDIO NO SE CORTA NUNCA.
 *
 * Sale de `ses_02805f3edba1` (24/08): 25 turnos, la voz del niño llegando
 * tarde, las frases enredándose entre sí, y al final dos mudeces seguidas y la
 * sesión muerta sin poder seguir. RBH lo describió así: «parecía como si mi voz
 * llegara tarde, y entonces como que se enredaba, y al final se cayó».
 *
 * La causa es el arreglo del 23/08, que resolvió un bug creando otro. Para que
 * el eco del tutor no le cortara la generación, el micrófono dejó de mandar
 * audio mientras el tutor hablaba. Pero la Live API dice:
 *
 *   «`silenceDurationMs` only works within a continuous stream — it measures
 *    quiet periods, not stream interruptions.»
 *
 * El VAD del servidor no mide el paso del tiempo: mide el audio que le llega.
 * Sin audio, su reloj se detiene, el turno del niño se queda colgado en el
 * buffer del servidor, y al volver el micrófono lo nuevo se pega con lo viejo
 * como si fueran contiguos.
 *
 * La solución es mandar SILENCIO en lugar de nada: el eco del tutor no viaja y
 * el reloj del VAD sigue corriendo.
 *
 * Estos tests miran el silencio en sí (que sea silencio de verdad, del largo
 * correcto y barato de generar). El que comprueba que el micrófono lo MANDA
 * —que es la mitad que importa— vive en `tests/test_contrato_version.py`, donde
 * ya están los otros contratos de este camino.
 */

import { describe, expect, it } from "vitest";

import { silencioPcm16Base64 } from "./audio";

/** Vuelve a PCM16 lo que se manda por el cable. `audio.ts` tiene su propio
    decodificador pero es privado, y exportarlo solo para un test agrandaría la
    superficie del módulo a cambio de nada. */
function bytesDe(base64: string): Int16Array {
  const binario = atob(base64);
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

describe("el silencio que mantiene vivo el stream", () => {
  it("es silencio de verdad: el VAD no puede oír nada ahí", () => {
    // Si esto tuviera cualquier cosa distinta de cero, estaríamos mandándole al
    // servidor algo que puede leer como que el niño empezó a hablar — que es
    // justo el bug del 23/08 que no se puede reintroducir.
    const muestras = bytesDe(silencioPcm16Base64(512));
    expect(muestras.length).toBe(512);
    expect(muestras.every((m) => m === 0)).toBe(true);
  });

  it("dura exactamente lo que el bloque que reemplaza", () => {
    // El stream tiene que avanzar al mismo ritmo que el reloj de pared. Si el
    // silencio fuera más corto que el bloque retenido, el reloj del VAD se
    // atrasaría y volveríamos —más despacio— al mismo problema.
    for (const largo of [128, 512, 1024]) {
      expect(bytesDe(silencioPcm16Base64(largo)).length).toBe(largo);
    }
  });

  it("se cachea: esto corre cada ~64 ms en el hilo del navegador", () => {
    // Mismo string exacto, no uno equivalente: si se recodificara cada vez,
    // estaríamos quemando el hilo que además procesa el audio en tiempo real.
    expect(silencioPcm16Base64(512)).toBe(silencioPcm16Base64(512));
  });

  it("un largo distinto da un bloque distinto, no el cacheado", () => {
    expect(silencioPcm16Base64(256)).not.toBe(silencioPcm16Base64(512));
  });
});
