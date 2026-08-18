/**
 * Tests de la captura del micrófono.
 *
 * Lo que se protege acá son los dos errores que dejan la sesión inservible sin
 * que nada falle a la vista:
 *
 * - Si el nodo de captura se conecta a `destination`, el niño se escucha a sí
 *   mismo por los parlantes.
 * - Si `detener()` no cierra el contexto ni para los tracks, el navegador
 *   sigue mostrando el indicador de micrófono encendido después de colgar.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SAMPLE_RATE_ENTRADA } from "./audio";
import { abrirMicrofono } from "./microfono";
import { AudioContextFalso, instalarAudioFalso } from "./audioContextFalso";

interface TrackFalso {
  stop: ReturnType<typeof vi.fn>;
}

let audioFalso: ReturnType<typeof instalarAudioFalso>;
let tracks: TrackFalso[];
let stream: { getTracks: () => TrackFalso[] };
let pedidos: MediaStreamConstraints[];
let urlsCreadas: string[];
let urlsLiberadas: string[];

beforeEach(() => {
  audioFalso = instalarAudioFalso();
  tracks = [{ stop: vi.fn() }, { stop: vi.fn() }];
  stream = { getTracks: () => tracks };
  pedidos = [];
  urlsCreadas = [];
  urlsLiberadas = [];

  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: async (opciones: MediaStreamConstraints) => {
        pedidos.push(opciones);
        return stream as unknown as MediaStream;
      },
    },
  });

  // jsdom no implementa las object URL — ni siquiera existen como método, así
  // que hay que ponerlas, no espiarlas. El worklet va como blob: sin esto
  // `abrirMicrofono` no llega a cargar el módulo.
  const urlGlobal = URL as unknown as Record<string, unknown>;
  urlGlobal.createObjectURL = () => {
    const url = `blob:falsa-${urlsCreadas.length}`;
    urlsCreadas.push(url);
    return url;
  };
  urlGlobal.revokeObjectURL = (url: string) => {
    urlsLiberadas.push(url);
  };
});

afterEach(() => {
  audioFalso.desinstalar();
  const urlGlobal = URL as unknown as Record<string, unknown>;
  delete urlGlobal.createObjectURL;
  delete urlGlobal.revokeObjectURL;
  vi.restoreAllMocks();
});

function contexto(): AudioContextFalso {
  const ctx = audioFalso.contextos[0];
  if (!ctx) throw new Error("no se creó ningún AudioContext");
  return ctx;
}

describe("apertura del micrófono", () => {
  it("pide cancelación de eco: sin eso el tutor se auto-interrumpe", async () => {
    await abrirMicrofono(() => {});

    const audio = pedidos[0].audio as MediaTrackConstraints;
    expect(audio.echoCancellation).toBe(true);
    expect(audio.channelCount).toBe(1);
    expect(audio.sampleRate).toBe(SAMPLE_RATE_ENTRADA);
  });

  it("captura al sample rate que Gemini espera", async () => {
    await abrirMicrofono(() => {});
    expect(contexto().sampleRate).toBe(SAMPLE_RATE_ENTRADA);
  });

  it("el nodo de captura no se conecta a los parlantes", async () => {
    await abrirMicrofono(() => {});
    const nodo = audioFalso.nodos[0];

    // El micrófono entra al nodo…
    expect(contexto().nodosDeStream[0].conexiones).toEqual([nodo]);
    // …y el nodo no sale a ningún lado. Si saliera, el niño se oiría a sí mismo.
    expect(nodo.conexiones).toEqual([]);
    expect(nodo.opciones?.numberOfOutputs).toBe(0);
  });

  it("el worklet se carga desde un blob y la url se libera enseguida", async () => {
    await abrirMicrofono(() => {});

    expect(contexto().modulosCargados).toEqual(urlsCreadas);
    expect(urlsLiberadas).toEqual(urlsCreadas);
  });

  it("cada lote llega con su nivel de volumen", async () => {
    const recibido = vi.fn();
    await abrirMicrofono(recibido);

    const muestras = new Float32Array([0.5, -0.5, 0.5, -0.5]);
    audioFalso.nodos[0].port.onmessage?.({ data: muestras });

    expect(recibido).toHaveBeenCalledTimes(1);
    const [muestrasRecibidas, nivel] = recibido.mock.calls[0];
    expect(muestrasRecibidas).toBe(muestras);
    expect(nivel).toBeCloseTo(0.5, 6); // RMS
  });

  it("el silencio se reporta como nivel cero", async () => {
    const recibido = vi.fn();
    await abrirMicrofono(recibido);

    audioFalso.nodos[0].port.onmessage?.({ data: new Float32Array(128) });

    expect(recibido.mock.calls[0][1]).toBe(0);
  });
});

describe("cierre del micrófono", () => {
  it("detener cierra el contexto y apaga el micrófono del navegador", async () => {
    const { captura } = await abrirMicrofono(() => {});

    captura.detener();

    expect(contexto().cerrado).toBe(true);
    expect(tracks.every((t) => t.stop.mock.calls.length === 1)).toBe(true);
  });

  it("detener deja de entregar audio aunque el worklet siga mandando", async () => {
    const recibido = vi.fn();
    const { captura } = await abrirMicrofono(recibido);
    const nodo = audioFalso.nodos[0];

    captura.detener();

    expect(nodo.desconectado).toBe(true);
    expect(nodo.port.onmessage).toBeNull();
    expect(recibido).not.toHaveBeenCalled();
  });

  it("devuelve el stream para que quien lo abrió pueda mirarlo", async () => {
    const { stream: devuelto } = await abrirMicrofono(() => {});
    expect(devuelto).toBe(stream as unknown as MediaStream);
  });
});
