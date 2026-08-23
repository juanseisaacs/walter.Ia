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

import { MS_ESPERANDO_MIRADA, MS_MUDEZ, AVISO_DEL_DIBUJO } from "./useTutor";

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

  it("prohíbe el elogio vacío SIN condición", () => {
    // La versión anterior decía que un "te quedó súper bien" *sin haber
    // descrito nada* estaba mal. El modelo la cumplió al pie de la letra:
    // describía el trazo y después soltaba el elogio vacío igual, incluso sobre
    // una J con un error (medido el 22/08: 4 de 8 respuestas con la condición,
    // 0 de 3 sin ella).
    //
    // Una prohibición con condición es una instrucción de cómo cumplirla a
    // medias. Esta no la tiene.
    expect(AVISO_DEL_DIBUJO).toContain("NO VALE NUNCA");
    expect(AVISO_DEL_DIBUJO.toLowerCase()).toContain("después de describirlo");
  });

  it("le dice qué decir en vez del elogio vacío", () => {
    // Prohibir sin dar el reemplazo deja al tutor sin nada que decir cuando el
    // niño SÍ lo hizo bien, y ahí se calla o improvisa otra frase hecha.
    expect(AVISO_DEL_DIBUJO).toContain("di CUÁL");
  });

  it("le dice que no mencione el aviso", () => {
    expect(AVISO_DEL_DIBUJO).toContain("No menciones este aviso");
  });
});

describe("el micrófono que se calla mientras el tutor mira", () => {
  it("vuelve solo, pase lo que pase", () => {
    // Es un PISO de seguridad: si el tutor no contesta, el micro tiene que
    // volver igual. Un niño mudo es peor que un tutor callado.
    expect(MS_ESPERANDO_MIRADA).toBeGreaterThan(0);
  });

  it("le da tiempo al tutor de mirar la imagen antes de volver", () => {
    // Este test pedía <= 3000 ms, y ese techo era el bug.
    //
    // Medido el 22/08 contra la API real (`scripts/verificar_dibujo.py`), el
    // tutor tarda entre 1.250 y 3.188 ms en soltar su primera sílaba después de
    // una imagen. Con el piso en 2.000 el micrófono volvía A MITAD de eso, el
    // audio entrante le cerraba el turno al modelo, y la frase quedaba por la
    // mitad: «¡Te quedó muy bien» — y silencio.
    expect(MS_ESPERANDO_MIRADA).toBeGreaterThanOrEqual(5000);
  });

  it("pero se rinde antes de que el vigilante empuje", () => {
    // Si el micro siguiera callado cuando el vigilante manda su empujón, el
    // niño no podría contestarle al tutor que acaba de volver.
    expect(MS_ESPERANDO_MIRADA).toBeLessThan(MS_MUDEZ);
  });
});
