/**
 * Doble del Web Audio API para los tests. NO se usa en producción.
 *
 * jsdom no trae `AudioContext`, y aunque lo trajera no serviría: lo que hay que
 * poder inspeccionar acá es *cuándo* se programó cada chunk y *si* se cortaron
 * las fuentes pendientes. Un contexto real solo suena.
 *
 * Las dos cosas que este doble hace y un contexto real no deja hacer:
 *
 * 1. El reloj (`currentTime`) no avanza solo — se mueve a mano con `avanzar()`.
 *    Así se puede encolar una respuesta entera "en ráfaga", que es exactamente
 *    como la manda Gemini: mucho más rápido que tiempo real.
 * 2. Cada `AudioBufferSourceNode` recuerda en qué instante lo arrancaron y si
 *    lo detuvieron. Sin eso no se puede distinguir "resincronizó" de "solapó".
 */

type EstadoContexto = "suspended" | "running" | "closed";

export class BufferFalso {
  /** Lo que le copiaron por `copyToChannel`: la decodificación base64→Float32. */
  readonly datos: Float32Array;

  constructor(
    readonly numberOfChannels: number,
    readonly length: number,
    readonly sampleRate: number,
  ) {
    this.datos = new Float32Array(length);
  }

  get duration(): number {
    return this.length / this.sampleRate;
  }

  copyToChannel(fuente: Float32Array, _canal: number): void {
    this.datos.set(fuente);
  }
}

export class FuenteFalsa {
  buffer: BufferFalso | null = null;
  onended: (() => void) | null = null;

  /** Instante del reloj del contexto en el que la programaron. `null` = nunca. */
  inicio: number | null = null;
  detenida = false;
  desconectada = false;
  readonly conexiones: unknown[] = [];

  /** Para probar que cortar una fuente ya terminada no rompe `detenerTodo()`. */
  lanzarAlDetener = false;

  connect(destino: unknown): void {
    this.conexiones.push(destino);
  }

  start(cuando: number): void {
    this.inicio = cuando;
  }

  stop(): void {
    if (this.lanzarAlDetener) throw new Error("InvalidStateError");
    this.detenida = true;
  }

  disconnect(): void {
    this.desconectada = true;
  }

  /** Simula que el navegador terminó de reproducirla. */
  terminar(): void {
    this.onended?.();
  }
}

export class NodoDeStreamFalso {
  readonly conexiones: unknown[] = [];

  constructor(readonly stream: unknown) {}

  connect(destino: unknown): void {
    this.conexiones.push(destino);
  }
}

export class AudioContextFalso {
  state: EstadoContexto = "running";
  currentTime = 0;
  readonly destination = { esElDestino: true };
  onstatechange: (() => void) | null = null;

  readonly sampleRate: number;
  readonly fuentes: FuenteFalsa[] = [];
  readonly buffers: BufferFalso[] = [];
  readonly modulosCargados: string[] = [];
  readonly nodosDeStream: NodoDeStreamFalso[] = [];
  cerrado = false;
  reanudaciones = 0;

  readonly audioWorklet = {
    addModule: async (url: string): Promise<void> => {
      this.modulosCargados.push(url);
    },
  };

  constructor(opciones?: { sampleRate?: number }) {
    this.sampleRate = opciones?.sampleRate ?? 48_000;
  }

  createBuffer(canales: number, largo: number, sampleRate: number): BufferFalso {
    const buffer = new BufferFalso(canales, largo, sampleRate);
    this.buffers.push(buffer);
    return buffer;
  }

  createBufferSource(): FuenteFalsa {
    const fuente = new FuenteFalsa();
    this.fuentes.push(fuente);
    return fuente;
  }

  createMediaStreamSource(stream: unknown): NodoDeStreamFalso {
    const nodo = new NodoDeStreamFalso(stream);
    this.nodosDeStream.push(nodo);
    return nodo;
  }

  async resume(): Promise<void> {
    this.reanudaciones++;
    this.state = "running";
  }

  async close(): Promise<void> {
    this.cerrado = true;
    this.state = "closed";
  }

  /* ── Perillas que solo existen en el doble ───────────────────────────── */

  /** Corre el reloj como lo haría el tiempo real. */
  avanzar(segundos: number): void {
    this.currentTime += segundos;
  }

  /**
   * El navegador durmió el contexto (pestaña de fondo, pantalla bloqueada).
   * El reloj se queda donde está: eso es lo que rompía el audio.
   */
  suspender(): void {
    this.state = "suspended";
    this.onstatechange?.();
  }

  /** Las fuentes que siguen programadas y nadie cortó. */
  get vivas(): FuenteFalsa[] {
    return this.fuentes.filter((f) => !f.detenida);
  }
}

/** Clase que se registra como `AudioWorkletNode` global durante los tests. */
export class NodoWorkletFalso {
  readonly port = {
    onmessage: null as ((evento: { data: Float32Array }) => void) | null,
    postMessage: (_mensaje: unknown): void => {},
  };
  readonly conexiones: unknown[] = [];
  desconectado = false;

  constructor(
    readonly ctx: AudioContextFalso,
    readonly nombre: string,
    readonly opciones?: { numberOfOutputs?: number },
  ) {}

  connect(destino: unknown): void {
    this.conexiones.push(destino);
  }

  disconnect(): void {
    this.desconectado = true;
  }
}

interface GlobalConAudio {
  AudioContext: unknown;
  AudioWorkletNode: unknown;
}

/**
 * Deja `new AudioContext(...)` y `new AudioWorkletNode(...)` apuntando a los
 * dobles. Devuelve la lista de contextos creados, en orden.
 */
export function instalarAudioFalso(): {
  contextos: AudioContextFalso[];
  nodos: NodoWorkletFalso[];
  desinstalar: () => void;
} {
  const contextos: AudioContextFalso[] = [];
  const nodos: NodoWorkletFalso[] = [];

  class ContextoRegistrado extends AudioContextFalso {
    constructor(opciones?: { sampleRate?: number }) {
      super(opciones);
      contextos.push(this);
    }
  }

  class NodoRegistrado extends NodoWorkletFalso {
    constructor(
      ctx: AudioContextFalso,
      nombre: string,
      opciones?: { numberOfOutputs?: number },
    ) {
      super(ctx, nombre, opciones);
      nodos.push(this);
    }
  }

  const global = globalThis as unknown as GlobalConAudio;
  const antesCtx = global.AudioContext;
  const antesNodo = global.AudioWorkletNode;
  global.AudioContext = ContextoRegistrado;
  global.AudioWorkletNode = NodoRegistrado;

  return {
    contextos,
    nodos,
    desinstalar: () => {
      global.AudioContext = antesCtx;
      global.AudioWorkletNode = antesNodo;
    },
  };
}

/** Espera a que corran las promesas pendientes (`resume().then(...)`). */
export function esperarMicrotareas(): Promise<void> {
  return new Promise((resolver) => setTimeout(resolver, 0));
}
