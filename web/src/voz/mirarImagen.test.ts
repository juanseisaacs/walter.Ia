/**
 * Lo que pasa cuando el niño le muestra algo al tutor.
 *
 * Sale de ses_6b430731226f, una sesión de 81 segundos donde falló todo lo que
 * podía fallar en ese camino:
 *
 *   nino: [le muestra al tutor un dibujo que hizo]
 *   nino: Ya la envié. Hola.            <- tuvo que insistir
 *   tutor: ¡Uy, ya la veo! Te quedó súper bien
 *
 * La letra estaba mal a propósito. El tutor no la había mirado: le contestó a
 * la VOZ. Y no la había mirado porque el micrófono, que manda audio sin parar,
 * le mantenía el turno abierto al niño y el `turnComplete` de la imagen no
 * disparaba nada.
 */

import { describe, expect, it } from "vitest";

import { MS_ESPERANDO_MIRADA, AVISO_DEL_DIBUJO } from "./useTutor";

describe("el aviso que viaja con el dibujo", () => {
  it("le exige describir ANTES de juzgar", () => {
    const a = AVISO_DEL_DIBUJO.toLowerCase();
    expect(a).toMatch(/qué ves|que ves/);
    expect(a).toMatch(/después|despues/);
  });

  it("le pide corregir, no solo felicitar", () => {
    expect(AVISO_DEL_DIBUJO.toLowerCase()).toMatch(/díselo|diselo|dile/);
  });

  it("nombra el elogio vacío para que no lo repita", () => {
    // El elogio inflado está prohibido por regla dura, y "te quedó súper bien"
    // sobre una letra mal hecha es exactamente eso: le enseña al niño que da
    // igual cómo lo haga.
    expect(AVISO_DEL_DIBUJO).toContain("súper bien");
  });

  it("le dice que no mencione el aviso", () => {
    expect(AVISO_DEL_DIBUJO).toContain("No menciones este aviso");
  });
});

describe("el micrófono que se calla mientras el tutor mira", () => {
  it("vuelve solo, y pronto", () => {
    // Es un PISO de seguridad: si el tutor no contesta, el micro tiene que
    // volver igual. Un niño mudo es peor que un tutor callado.
    expect(MS_ESPERANDO_MIRADA).toBeGreaterThan(0);
    expect(MS_ESPERANDO_MIRADA).toBeLessThanOrEqual(3000);
  });
});
