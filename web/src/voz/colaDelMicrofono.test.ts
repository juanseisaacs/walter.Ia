/**
 * EL STREAM NI SE CORTA NI SE ALARGA.
 *
 * Sale de `ses_31593f90ab26` (25/08). RBH, después de una sesión de 1,7 minutos
 * con 3 de 8 turnos del tutor partidos: «creo que a veces mi audio le llega
 * tarde, o a veces pareciera como que al mismo tiempo que escucha está
 * hablando, se siente extraño».
 *
 * La causa era de contabilidad. Mientras el tutor sonaba se mandaba silencio Y
 * ADEMÁS se guardaba una copia del bloque; al confirmarse el barge-in, la copia
 * salía ENCIMA del silencio que ya había ocupado su lugar en el tiempo. Medio
 * segundo de audio de más por cada interrupción, y el stream no lo recupera
 * nunca: se acumula. A los pocos barge-ins el servidor está procesando lo que
 * el niño dijo turnos atrás mientras el tutor ya habla de otra cosa.
 *
 * Estos tests cuentan bloques. Es lo único que distingue "suena bien" de "está
 * bien": la deriva no se ve leyendo el código, se siente tres turnos después.
 */

import { describe, expect, it } from "vitest";

import { pasarPorLaCola, sigueEnDuda, vozSostenida } from "./colaDelMicrofono";

const FONDO = 5;
const BLOQUE_MS = 64;

/** Un bloque cualquiera, reconocible por su primera muestra. */
function bloque(n: number): Float32Array {
  const b = new Float32Array(1024);
  b[0] = n;
  return b;
}

/** Corre una secuencia de estados y devuelve todo lo que salió por el cable. */
function correr(pasos: Array<{ reteniendo: boolean; interrumpio: boolean }>) {
  const cola: Float32Array[] = [];
  const enviados: Array<{ n: number; mudo: boolean }> = [];
  pasos.forEach((paso, i) => {
    for (const s of pasarPorLaCola(cola, bloque(i), { ...paso, fondo: FONDO })) {
      enviados.push({ n: s.muestras[0], mudo: s.mudo });
    }
  });
  return { enviados, quedanEnCola: cola.length };
}

describe("la línea de retardo del micrófono", () => {
  it("en directo, cada bloque sale en el acto y con su audio", () => {
    const { enviados, quedanEnCola } = correr(
      Array.from({ length: 20 }, () => ({ reteniendo: false, interrumpio: false })),
    );
    expect(enviados).toHaveLength(20);
    expect(enviados.every((e) => !e.mudo)).toBe(true);
    expect(quedanEnCola).toBe(0);
  });

  it("mientras el tutor suena, lo que sale va mudo: su eco no viaja", () => {
    const { enviados } = correr(
      Array.from({ length: 30 }, () => ({ reteniendo: true, interrumpio: false })),
    );
    expect(enviados.every((e) => e.mudo)).toBe(true);
  });

  it("retiene `fondo` bloques: es el margen que necesita el barge-in", () => {
    // Con el fondo en 5, los primeros 5 se quedan adentro esperando decisión.
    // Ese retardo es lo que permite decidir sobre un bloque ANTES de que salga.
    const { enviados, quedanEnCola } = correr(
      Array.from({ length: 8 }, () => ({ reteniendo: true, interrumpio: false })),
    );
    expect(enviados).toHaveLength(3);
    expect(quedanEnCola).toBe(FONDO);
  });

  it("LA INVARIANTE: entra un bloque, sale un bloque", () => {
    // 200 bloques con el tutor entrando y saliendo, y tres interrupciones en
    // medio. Pase lo que pase, el servidor tiene que haber recibido tanto audio
    // como tiempo pasó — ni un bloque más (llega tarde) ni uno menos (se corta).
    const pasos = Array.from({ length: 200 }, (_, i) => ({
      reteniendo: i % 40 < 25, // el tutor habla en tandas
      interrumpio: i === 60 || i === 100 || i === 140,
    }));
    const { enviados, quedanEnCola } = correr(pasos);
    expect(enviados.length + quedanEnCola).toBe(200);
  });

  it("una interrupción NO alarga el stream — el bug del 25/08", () => {
    // 10 bloques con el tutor sonando, el barge-in confirma, 10 más en directo.
    const pasos = [
      ...Array.from({ length: 10 }, () => ({ reteniendo: true, interrumpio: false })),
      ...Array.from({ length: 10 }, () => ({ reteniendo: false, interrumpio: true })),
    ];
    const { enviados, quedanEnCola } = correr(pasos);
    // Antes acá salían 25: los 20 del stream MÁS los 5 de la cola, que ya
    // habían viajado como silencio. Esos 5 de más son el retraso que el niño
    // sentía, y no se recuperaban nunca.
    expect(enviados.length + quedanEnCola).toBe(20);
  });

  it("la primera sílaba de la interrupción sale entera, no se pierde", () => {
    // El niño arranca a hablar en el bloque 10; el barge-in tarda 4 bloques en
    // confirmarlo. Como esos bloques siguen en la cola cuando se decide, salen
    // con su audio de verdad: el tutor oye la interrupción desde el principio y
    // el niño no tiene que repetirse.
    const pasos = [
      ...Array.from({ length: 10 }, () => ({ reteniendo: true, interrumpio: false })),
      ...Array.from({ length: 4 }, () => ({ reteniendo: true, interrumpio: false })),
      { reteniendo: false, interrumpio: true },
    ];
    const { enviados } = correr(pasos);
    const conVoz = enviados.filter((e) => !e.mudo).map((e) => e.n);
    expect(conVoz).toContain(10); // el bloque donde empezó a hablar
    expect(Math.min(...conVoz)).toBeLessThanOrEqual(10);
  });

  it("al dejar de retener la cola se vacía: el micrófono vuelve en directo", () => {
    const cola: Float32Array[] = [];
    for (let i = 0; i < 10; i++) {
      pasarPorLaCola(cola, bloque(i), { reteniendo: true, interrumpio: false, fondo: FONDO });
    }
    expect(cola).toHaveLength(FONDO);

    const salida = pasarPorLaCola(cola, bloque(99), {
      reteniendo: false,
      interrumpio: false,
      fondo: FONDO,
    });
    expect(salida).toHaveLength(FONDO + 1);
    expect(cola).toHaveLength(0);
    // Y salen con audio: el tutor ya calló, esto es el niño arrancando a hablar
    // pegado al final de su turno. Antes se tiraba entero, y por eso los turnos
    // del niño llegaban descabezados: «hacer», «¿Cuál», «respuesta, si era…».
    expect(salida.every((s) => !s.mudo)).toBe(true);
  });
});

describe("la voz sostenida que confirma el barge-in", () => {
  it("sube mientras hay voz", () => {
    let ms = 0;
    for (let i = 0; i < 4; i++) ms = vozSostenida(ms, { hayVoz: true, bloqueMs: BLOQUE_MS });
    expect(ms).toBe(256);
  });

  it("una frase con pausas entre sílabas llega igual al corte", () => {
    // Este es el caso que se rompía: reseteando a cero, un solo bloque flojo
    // —el hueco entre dos sílabas— borraba todo lo acumulado y el barge-in no
    // se confirmaba nunca. El niño hablaba y su audio se iba al silencio.
    let ms = 0;
    for (const hayVoz of [true, true, false, true, true, true, false, true, true]) {
      ms = vozSostenida(ms, { hayVoz, bloqueMs: BLOQUE_MS });
    }
    expect(ms).toBeGreaterThanOrEqual(200); // MS_PARA_CORTAR
  });

  it("un golpe suelto en la mesa sigue sin alcanzar", () => {
    let ms = 0;
    for (const hayVoz of [true, false, false, false, true, false, false, false]) {
      ms = vozSostenida(ms, { hayVoz, bloqueMs: BLOQUE_MS });
    }
    expect(ms).toBeLessThan(200);
  });

  it("nunca baja de cero: el silencio largo no acumula crédito al revés", () => {
    let ms = 0;
    for (let i = 0; i < 50; i++) ms = vozSostenida(ms, { hayVoz: false, bloqueMs: BLOQUE_MS });
    expect(ms).toBe(0);
  });
});

describe("el turno que el barge-in dejó en duda", () => {
  const ESPERA = 900;

  it("sin nada abortado, el audio del tutor suena y punto", () => {
    expect(sigueEnDuda(0, 5_000, ESPERA)).toBe(false);
  });

  it("recién callado, lo que llegue NO vuelve al parlante", () => {
    // Es el bug: Gemini sigue mandando el resto del turno y el tutor volvía a
    // sonar encima del niño medio segundo después de que lo callaron.
    expect(sigueEnDuda(1_000, 1_200, ESPERA)).toBe(true);
  });

  it("si el servidor no confirma en el plazo, el tutor retoma", () => {
    // El barge-in se equivocó —una silla, un eco fuerte—: no había a quién oír.
    // Dejarlo mudo a mitad de frase sería peor que el bug que esto tapa.
    expect(sigueEnDuda(1_000, 2_000, ESPERA)).toBe(false);
  });

  it("el borde del plazo todavía cuenta como duda", () => {
    expect(sigueEnDuda(1_000, 1_900, ESPERA)).toBe(true);
    expect(sigueEnDuda(1_000, 1_901, ESPERA)).toBe(false);
  });
});
