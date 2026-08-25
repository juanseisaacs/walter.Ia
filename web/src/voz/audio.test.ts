/**
 * Tests del reproductor continuo.
 *
 * Este archivo existe por dos bugs reales, con dos días de diferencia, que
 * dejaron al tutor inutilizable y que ningún test podía atrapar porque el
 * frontend no tenía ninguno:
 *
 * 1. EL TUTOR MUDO — el contexto se suspendía, su reloj se paraba, y los chunks
 *    se programaban contra un reloj detenido. El tutor "hablaba" para nadie.
 * 2. EL AUDIO SOLAPADO — la corrección del #1 movía el puntero al presente sin
 *    detener las fuentes ya programadas. Eso no resincroniza: SOLAPA. El niño
 *    oía dos voces del mismo tutor.
 *
 * Cada uno tiene acá un test que falla si vuelve.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MockInstance } from "vitest";

import { ReproductorContinuo, SAMPLE_RATE_SALIDA, aPcm16Base64 } from "./audio";
import {
  AudioContextFalso,
  esperarMicrotareas,
  instalarAudioFalso,
} from "./audioContextFalso";

/** Espejo del privado en `audio.ts`: el colchón para no rellenar un hueco. */
const COLCHON_SEG = 0.015;

let audioFalso: ReturnType<typeof instalarAudioFalso>;
let reproductor: ReproductorContinuo;
let avisos: MockInstance;

beforeEach(() => {
  audioFalso = instalarAudioFalso();
  avisos = vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "info").mockImplementation(() => {});
  reproductor = new ReproductorContinuo();
});

afterEach(() => {
  reproductor.cerrar();
  audioFalso.desinstalar();
  vi.restoreAllMocks();
});

/** El contexto que creó el reproductor al iniciar. */
function contexto(): AudioContextFalso {
  const ctx = audioFalso.contextos[0];
  if (!ctx) throw new Error("el reproductor no creó ningún AudioContext");
  return ctx;
}

const enCache = new Map<number, string>();

/** Un chunk de audio de la duración pedida (silencio: acá importa el largo). */
function chunkDe(segundos: number): string {
  const guardado = enCache.get(segundos);
  if (guardado !== undefined) return guardado;
  const b64 = aPcm16Base64(new Float32Array(Math.round(segundos * SAMPLE_RATE_SALIDA)));
  enCache.set(segundos, b64);
  return b64;
}

/* ─────────────────────────────────────────────────────────────────────────
 * Encadenamiento: la razón de ser del archivo
 * ───────────────────────────────────────────────────────────────────────── */

describe("encadenamiento de chunks", () => {
  it("cada chunk arranca exactamente donde termina el anterior", () => {
    reproductor.iniciar();
    const ctx = contexto();

    reproductor.programar(chunkDe(0.5));
    reproductor.programar(chunkDe(0.25));
    reproductor.programar(chunkDe(0.75));

    const inicios = ctx.fuentes.map((f) => f.inicio ?? -1);
    expect(inicios[0]).toBeCloseTo(COLCHON_SEG, 6);
    expect(inicios[1]).toBeCloseTo(COLCHON_SEG + 0.5, 6);
    expect(inicios[2]).toBeCloseTo(COLCHON_SEG + 0.75, 6);
  });

  it("no deja ni un hueco entre un chunk y el siguiente", () => {
    reproductor.iniciar();
    const ctx = contexto();

    reproductor.programar(chunkDe(0.4));
    reproductor.programar(chunkDe(0.4));

    const [primera, segunda] = ctx.fuentes;
    const finDeLaPrimera = (primera.inicio ?? 0) + (primera.buffer?.duration ?? 0);
    expect(segunda.inicio).toBeCloseTo(finDeLaPrimera, 6);
  });

  it("un chunk que llega tarde arranca ya, sin esperar a la cola vieja", () => {
    reproductor.iniciar();
    const ctx = contexto();

    reproductor.programar(chunkDe(0.2));
    ctx.avanzar(5); // el niño se quedó callado un rato

    reproductor.programar(chunkDe(0.2));

    expect(ctx.fuentes[1].inicio).toBeCloseTo(5 + COLCHON_SEG, 6);
  });

  it("cada chunk sale por el destino del contexto", () => {
    reproductor.iniciar();
    const ctx = contexto();
    reproductor.programar(chunkDe(0.1));

    expect(ctx.fuentes[0].conexiones).toEqual([ctx.destination]);
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * El bug del solapamiento (18/08, 09:04–13:30)
 * ───────────────────────────────────────────────────────────────────────── */

describe("red de seguridad contra la deriva", () => {
  it("una respuesta larga encolada en ráfaga no se toma por desincronización", () => {
    // ESTE es el test que habría atrapado el bug. Gemini manda la respuesta
    // completa mucho más rápido que tiempo real, así que diez segundos de voz
    // llegan casi de golpe y la cola queda legítimamente diez segundos en el
    // futuro. Con el umbral en 2 s eso se leía como desincronización EN CADA
    // FRASE, y cada frase se cortaba encima de la anterior.
    reproductor.iniciar();
    const ctx = contexto();

    for (let i = 0; i < 10; i++) reproductor.programar(chunkDe(1));

    expect(ctx.fuentes).toHaveLength(10);
    expect(ctx.vivas).toHaveLength(10); // nadie cortó nada
    expect(avisos).not.toHaveBeenCalled();

    // Y siguen encadenados de punta a punta.
    ctx.fuentes.forEach((fuente, i) => {
      expect(fuente.inicio).toBeCloseTo(COLCHON_SEG + i, 6);
    });
  });

  it("cuando la cola se va al futuro se cortan las fuentes pendientes", () => {
    // Mover `proximoInicio` al presente sin detener lo programado no
    // resincroniza: solapa. Este test falla si alguien vuelve a hacerlo.
    reproductor.iniciar();
    const ctx = contexto();

    for (let i = 0; i < 6; i++) reproductor.programar(chunkDe(5)); // cola en ~30 s
    const previas = [...ctx.fuentes];
    expect(previas.every((f) => !f.detenida)).toBe(true);

    reproductor.programar(chunkDe(1)); // acá salta la red

    expect(previas.every((f) => f.detenida)).toBe(true);
    expect(previas.every((f) => f.desconectada)).toBe(true);
    expect(avisos).toHaveBeenCalled();
  });

  it("al resincronizar el chunk nuevo suena ya, no encima de lo anterior", () => {
    reproductor.iniciar();
    const ctx = contexto();

    for (let i = 0; i < 6; i++) reproductor.programar(chunkDe(5));
    reproductor.programar(chunkDe(1));

    const nueva = ctx.fuentes[ctx.fuentes.length - 1];
    expect(nueva.inicio).toBeCloseTo(ctx.currentTime + COLCHON_SEG, 6);
    // Y es la única que sigue en pie: no hay dos voces del mismo tutor.
    expect(ctx.vivas).toEqual([nueva]);
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * El bug del tutor mudo (ses_91c13b1747a2)
 * ───────────────────────────────────────────────────────────────────────── */

describe("suspensión del contexto", () => {
  it("al despertar se descarta lo encolado en vez de solaparlo", async () => {
    reproductor.iniciar();
    const ctx = contexto();
    ctx.avanzar(3);

    reproductor.programar(chunkDe(1));
    reproductor.programar(chunkDe(1)); // la cola llega hasta 5.015
    const dormidas = [...ctx.fuentes];

    ctx.suspender(); // el reloj se congela en 3
    await esperarMicrotareas();

    expect(ctx.reanudaciones).toBe(1);
    expect(dormidas.every((f) => f.detenida)).toBe(true);

    // Lo que se dijo mientras nadie escuchaba ya no sirve: la frase que viene
    // suena YA (3.015), no donde había quedado la cola muerta (5.015).
    reproductor.programar(chunkDe(1));
    expect(ctx.fuentes[2].inicio).toBeCloseTo(3 + COLCHON_SEG, 6);
  });

  it("volver a la pestaña despierta el contexto dormido", async () => {
    reproductor.iniciar();
    const ctx = contexto();
    ctx.state = "suspended"; // el navegador durmió sin avisar

    document.dispatchEvent(new Event("visibilitychange"));
    await esperarMicrotareas();

    expect(ctx.reanudaciones).toBe(1);
    expect(ctx.state).toBe("running");
  });

  it("iniciar sobre un contexto ya dormido lo despierta en vez de crear otro", async () => {
    reproductor.iniciar();
    const ctx = contexto();
    ctx.state = "suspended";

    reproductor.iniciar();
    await esperarMicrotareas();

    expect(audioFalso.contextos).toHaveLength(1);
    expect(ctx.reanudaciones).toBe(1);
  });

  it("un contexto sano no se reanuda por las dudas", async () => {
    reproductor.iniciar();
    const ctx = contexto();

    reproductor.programar(chunkDe(0.2));
    document.dispatchEvent(new Event("visibilitychange"));
    await esperarMicrotareas();

    expect(ctx.reanudaciones).toBe(0);
    expect(ctx.vivas).toHaveLength(1);
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * Interrupción
 * ───────────────────────────────────────────────────────────────────────── */

describe("detenerTodo", () => {
  it("corta lo ya programado y deja el puntero en el presente", () => {
    reproductor.iniciar();
    const ctx = contexto();

    reproductor.programar(chunkDe(2));
    reproductor.programar(chunkDe(2));
    ctx.avanzar(0.5); // el niño interrumpe a mitad de la primera

    reproductor.detenerTodo();

    expect(ctx.fuentes.every((f) => f.detenida)).toBe(true);
    expect(reproductor.hablando).toBe(false);

    // El puntero quedó en el presente: lo próximo arranca de una.
    reproductor.programar(chunkDe(0.3));
    expect(ctx.fuentes[2].inicio).toBeCloseTo(0.5 + COLCHON_SEG, 6);
  });

  it("una fuente que ya terminó no impide cortar las demás", () => {
    reproductor.iniciar();
    const ctx = contexto();

    reproductor.programar(chunkDe(0.3));
    reproductor.programar(chunkDe(0.3));
    ctx.fuentes[0].lanzarAlDetener = true; // stop() sobre algo ya terminado

    expect(() => reproductor.detenerTodo()).not.toThrow();
    expect(ctx.fuentes[1].detenida).toBe(true);
  });

  it("cerrar suelta el contexto y deja de escuchar a la pestaña", async () => {
    reproductor.iniciar();
    const ctx = contexto();
    reproductor.programar(chunkDe(0.3));

    reproductor.cerrar();
    await esperarMicrotareas();

    expect(ctx.cerrado).toBe(true);
    expect(ctx.onstatechange).toBeNull();

    // Si el listener siguiera vivo, tocaría un contexto que ya no existe.
    ctx.state = "suspended";
    document.dispatchEvent(new Event("visibilitychange"));
    await esperarMicrotareas();
    expect(ctx.reanudaciones).toBe(0);
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * Estado hablando / fin de la respuesta
 * ───────────────────────────────────────────────────────────────────────── */

describe("estado de la reproducción", () => {
  it("se declara hablando solo mientras queda audio en la cola", () => {
    reproductor.iniciar();
    const ctx = contexto();

    expect(reproductor.hablando).toBe(false);
    reproductor.programar(chunkDe(0.2));
    expect(reproductor.hablando).toBe(true);

    ctx.fuentes[0].terminar();
    expect(reproductor.hablando).toBe(false);
  });

  it("avisa que terminó recién cuando se vació la cola, no en cada chunk", () => {
    reproductor.iniciar();
    const ctx = contexto();
    const avisado = vi.fn();
    reproductor.alTerminar = avisado;

    reproductor.programar(chunkDe(0.2));
    reproductor.programar(chunkDe(0.2));

    ctx.fuentes[0].terminar();
    expect(avisado).not.toHaveBeenCalled();

    ctx.fuentes[1].terminar();
    expect(avisado).toHaveBeenCalledTimes(1);
  });

  it("programar sin haber iniciado no revienta ni crea contextos sueltos", () => {
    expect(() => reproductor.programar(chunkDe(0.2))).not.toThrow();
    expect(audioFalso.contextos).toHaveLength(0);
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * Conversión PCM ↔ base64
 * ───────────────────────────────────────────────────────────────────────── */

describe("conversión de muestras", () => {
  /** Codifica, programa, y devuelve lo que efectivamente entró al buffer. */
  function idaYVuelta(muestras: Float32Array): Float32Array {
    reproductor.iniciar();
    reproductor.programar(aPcm16Base64(muestras));
    return contexto().buffers[0].datos;
  }

  it("lo que se codifica es lo que se reproduce", () => {
    const original = new Float32Array([0, 0.5, -0.5, 0.25, -0.75, 1, -1]);
    const vuelta = idaYVuelta(original);

    expect(vuelta).toHaveLength(original.length);
    original.forEach((valor, i) => expect(vuelta[i]).toBeCloseTo(valor, 4));
  });

  it("un valor fuera de rango se recorta, no da la vuelta", () => {
    // Sin el clamp, 2 pasa por setInt16 y sale -0.00006: un pico positivo se
    // convierte en silencio invertido y el audio chasquea.
    const vuelta = idaYVuelta(new Float32Array([2, -2, 7.5, -7.5]));

    expect(vuelta[0]).toBeCloseTo(1, 3);
    expect(vuelta[1]).toBeCloseTo(-1, 3);
    expect(vuelta[2]).toBeCloseTo(1, 3);
    expect(vuelta[3]).toBeCloseTo(-1, 3);
  });

  it("el silencio sobrevive al viaje", () => {
    const vuelta = idaYVuelta(new Float32Array(64));
    expect([...vuelta].every((v) => v === 0)).toBe(true);
  });

  it("el buffer se arma al sample rate que devuelve Gemini", () => {
    reproductor.iniciar();
    reproductor.programar(chunkDe(0.5));

    const buffer = contexto().buffers[0];
    expect(buffer.sampleRate).toBe(SAMPLE_RATE_SALIDA);
    expect(buffer.numberOfChannels).toBe(1);
    expect(buffer.duration).toBeCloseTo(0.5, 6);
  });
});

describe("cola de guarda contra el eco (sonandoHace)", () => {
  /* Los dos huecos por los que el eco del tutor le cortaba la frase: entre
     chunk y chunk, y la cola del parlante justo después del último. Ver
     `ReproductorContinuo.sonandoHace` y `ses_0a6036dedf55`. */

  it("aguanta después de la última muestra, cuando el parlante todavía suena", () => {
    vi.useFakeTimers();
    try {
      reproductor.iniciar();
      const ctx = contexto();

      reproductor.programar(chunkDe(0.2));
      ctx.fuentes[0].terminar();

      // `hablando` ya dice que no, pero el micrófono sigue oyendo al tutor.
      expect(reproductor.hablando).toBe(false);
      expect(reproductor.sonandoHace(300)).toBe(true);

      vi.advanceTimersByTime(299);
      expect(reproductor.sonandoHace(300)).toBe(true);
      vi.advanceTimersByTime(2);
      expect(reproductor.sonandoHace(300)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("tapa el hueco entre chunks: el turno no terminó, solo llegó tarde", () => {
    vi.useFakeTimers();
    try {
      reproductor.iniciar();
      const ctx = contexto();

      reproductor.programar(chunkDe(0.2));
      ctx.fuentes[0].terminar(); // la cola se vació a mitad de frase
      vi.advanceTimersByTime(80); // Gemini manda en ráfagas: este llegó tarde
      expect(reproductor.sonandoHace(300)).toBe(true);

      reproductor.programar(chunkDe(0.2));
      expect(reproductor.sonandoHace(300)).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("un barge-in APAGA la cola: la voz del niño no espera 300 ms más", () => {
    vi.useFakeTimers();
    try {
      reproductor.iniciar();
      reproductor.programar(chunkDe(0.2));

      // Acá al tutor lo callaron, no terminó solo. Lo que venga por el
      // micrófono es el niño interrumpiendo y tiene que salir ya.
      reproductor.detenerTodo();
      expect(reproductor.sonandoHace(300)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("sin haber hablado nunca, no hay cola que aguantar", () => {
    reproductor.iniciar();
    expect(reproductor.sonandoHace(300)).toBe(false);
  });
});

describe("despertar el contexto sin borrar la ráfaga (ses_6c6fb58aafbb)", () => {
  it("un solo resume aunque lleguen muchos chunks suspendido", () => {
    reproductor.iniciar();
    const ctx = contexto();
    ctx.suspender();

    // Gemini manda la respuesta en ráfaga. Cada chunk pedía su propio resume,
    // y cada uno resolvía llamando a detenerTodo(): la ráfaga entera se
    // borraba a sí misma aunque el contexto ya hubiera despertado.
    for (let i = 0; i < 5; i++) reproductor.programar(chunkDe(0.2));

    expect(ctx.reanudaciones).toBe(1);
  });

  it("si el navegador rechaza el resume, se puede volver a intentar", async () => {
    // Sin el brazo de rechazo, el flag quedaba en true para siempre y el tutor
    // se quedaba mudo el resto de la sesión por un rechazo transitorio.
    reproductor.iniciar();
    const ctx = contexto();
    ctx.rechazarResume = true;
    ctx.suspender();

    reproductor.programar(chunkDe(0.2));
    await esperarMicrotareas();
    expect(ctx.reanudaciones).toBe(1);

    ctx.rechazarResume = false;
    reproductor.programar(chunkDe(0.2));
    expect(ctx.reanudaciones, "quedó trabado: no reintentó nunca más").toBe(2);
  });
});
