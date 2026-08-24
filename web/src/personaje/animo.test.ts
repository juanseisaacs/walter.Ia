/**
 * Lo que se puede probar del personaje sin mirarlo.
 *
 * El dibujo se mira en `/pizarra`; acá solo se prueba la traducción de la
 * sesión al cuerpo, que es donde cabe un bug callado. Los dos que estos tests
 * impiden:
 *
 *  1. Que el tutor siga moviendo la boca después de callarse (o al revés).
 *  2. Que se quede con la mirada en el papel mientras el niño le habla.
 *
 * Ninguno de los dos rompe nada ni tira un error: simplemente el personaje
 * miente sobre lo que está pasando, y un niño de 7 le cree al dibujo.
 */

import { describe, expect, it } from "vitest";

import { type Animo, animoDesde, comoSeLee, respiro } from "./animo";

const ANIMOS: Animo[] = ["reposo", "saludando", "escuchando", "hablando", "mirando", "esperando"];

describe("animoDesde", () => {
  it("hablando gana sobre todo lo demás", () => {
    // Si el tutor está HABLANDO de la foto, el personaje habla. Quedarse con
    // cara de estar leyendo mientras suena la voz es la peor combinación:
    // el niño ve un dibujo que no corresponde a lo que oye.
    expect(animoDesde({ estado: "hablando", mirandoFoto: true, mudo: true })).toBe("hablando");
  });

  it("el turno del niño es escuchar, no esperar quieto", () => {
    expect(animoDesde({ estado: "escuchando" })).toBe("escuchando");
  });

  it("cuando llega una foto, baja los ojos al papel", () => {
    expect(animoDesde({ estado: "escuchando", mirandoFoto: true })).toBe("mirando");
  });

  it("la mudez cambia el gesto, pero solo si no hay foto en el medio", () => {
    expect(animoDesde({ estado: "escuchando", mudo: true })).toBe("esperando");
    // Mirar la foto explica por qué el niño no habla: no es que se haya ido.
    expect(animoDesde({ estado: "escuchando", mirandoFoto: true, mudo: true })).toBe("mirando");
  });

  it("conectando saluda; el error no", () => {
    expect(animoDesde({ estado: "conectando" })).toBe("saludando");
    // Un oso saludando alegre encima de un mensaje de error es una burla.
    expect(animoDesde({ estado: "error" })).toBe("reposo");
    expect(animoDesde({ estado: "inicio" })).toBe("reposo");
  });
});

describe("comoSeLee", () => {
  it("todo ánimo tiene texto: sin `default` que tape uno nuevo", () => {
    for (const animo of ANIMOS) {
      expect(comoSeLee(animo)).toMatch(/tutor/);
    }
  });

  it("quien no ve la pantalla se entera de quién tiene el turno", () => {
    expect(comoSeLee("hablando")).not.toBe(comoSeLee("escuchando"));
  });
});

describe("respiro", () => {
  it("solo respira con el micrófono mientras escucha", () => {
    expect(respiro("escuchando", 0.5)).toBeGreaterThan(1);
    // Hablando el movimiento es la boca. Si además latiera con el micrófono,
    // latiría con su propia voz saliendo por el parlante.
    expect(respiro("hablando", 0.9)).toBe(1.03);
    expect(respiro("mirando", 0.9)).toBe(1);
  });

  it("un grito no lo saca de la pantalla, y un nivel negativo no lo da vuelta", () => {
    expect(respiro("escuchando", 40)).toBeCloseTo(1.12);
    expect(respiro("escuchando", -3)).toBe(1);
  });
});
