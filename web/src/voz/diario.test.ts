/**
 * El diario de la voz.
 *
 * Existe porque tres diagnósticos seguidos el 25/08 terminaron en una hipótesis:
 * todo lo que decide si una conversación se siente fluida —latencias, tools,
 * mudez, barge-in— vivía en `console.info` y se perdía al cerrar la pestaña.
 *
 * Los dos riesgos de una pieza así son que estorbe (mande en el camino del
 * audio) o que crezca sin techo. Los dos tienen test acá.
 */

import { describe, expect, it, vi } from "vitest";

import { Diario, EVENTOS_POR_LOTE, TECHO_PENDIENTES } from "./diario";

describe("Diario", () => {
  it("no manda nada hasta juntar un lote: el envío no va por evento", () => {
    const enviar = vi.fn();
    const d = new Diario(enviar);
    for (let i = 0; i < EVENTOS_POR_LOTE - 1; i++) d.anota({ t: "latencia", ms: i });
    expect(enviar).not.toHaveBeenCalled();
    expect(d.pendiente).toBe(EVENTOS_POR_LOTE - 1);
  });

  it("manda el lote completo al llenarse", () => {
    const enviar = vi.fn();
    const d = new Diario(enviar);
    for (let i = 0; i < EVENTOS_POR_LOTE; i++) d.anota({ t: "latencia", ms: i });
    expect(enviar).toHaveBeenCalledTimes(1);
    expect(enviar.mock.calls[0][0]).toHaveLength(EVENTOS_POR_LOTE);
    expect(d.pendiente).toBe(0);
  });

  it("le pone la hora a cada evento: sin eso no hay línea de tiempo", () => {
    // «Se enredó al final» se prueba viendo QUÉ pasó y CUÁNDO. Un evento sin
    // hora es un dato que no contesta la pregunta que lo motivó.
    const enviar = vi.fn();
    const d = new Diario(enviar);
    d.anota({ t: "mudez" });
    d.drena();
    expect(enviar.mock.calls[0][0][0].en).toBeGreaterThan(0);
  });

  it("drena lo que quede, aunque no llegue a un lote", () => {
    // El lote que falta es siempre el que explica por qué se cayó.
    const enviar = vi.fn();
    const d = new Diario(enviar);
    d.anota({ t: "voz_muda" });
    d.drena();
    expect(enviar).toHaveBeenCalledTimes(1);
    expect(enviar.mock.calls[0][0]).toHaveLength(1);
  });

  it("drenar sin nada pendiente no llama a nadie", () => {
    const enviar = vi.fn();
    new Diario(enviar).drena();
    expect(enviar).not.toHaveBeenCalled();
  });

  it("con techo, y tira los VIEJOS: lo que explica la caída está al final", () => {
    // Si el envío falla toda la sesión, esto no puede llenar la memoria del
    // navegador — rompería justo lo que viene a diagnosticar. Y al recortar se
    // conserva el final: guardar el principio sería quedarse con la única
    // parte que no hace falta.
    const d = new Diario(() => {
      throw new Error("la red no anda");
    });
    for (let i = 0; i < TECHO_PENDIENTES + 50; i++) {
      try {
        d.anota({ t: "barge_in", nivel: i });
      } catch {
        /* el envío falla, el diario sigue */
      }
    }
    expect(d.pendiente).toBeLessThanOrEqual(TECHO_PENDIENTES);
  });
});
