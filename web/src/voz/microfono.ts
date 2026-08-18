/**
 * Captura del micrófono en AudioWorklet.
 *
 * NO se usa ScriptProcessorNode: está deprecado y compite con el render de la
 * UI, así que el audio se corta justo cuando React trabaja. AudioWorklet corre
 * en un hilo dedicado.
 *
 * Detalle fácil de equivocar: el nodo se declara con numberOfOutputs: 0 y NO
 * se conecta a destination. Si se conecta, el niño se escucha a sí mismo.
 */

import { SAMPLE_RATE_ENTRADA } from "./audio";

const LOTE = 1024; // ~64 ms. Menos = menos latencia, más mensajes.

/** El worklet va como blob: así no hace falta servir un archivo aparte. */
const CODIGO_WORKLET = `
class CapturaPCM extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(${LOTE});
    this.escritos = 0;
  }
  process(entradas) {
    const canal = entradas[0]?.[0];
    if (!canal) return true;
    for (let i = 0; i < canal.length; i++) {
      this.buffer[this.escritos++] = canal[i];
      if (this.escritos === ${LOTE}) {
        this.port.postMessage(this.buffer.slice());
        this.escritos = 0;
      }
    }
    return true;
  }
}
registerProcessor('captura-pcm', CapturaPCM);
`;

export interface CapturaMicrofono {
  detener: () => void;
}

export async function abrirMicrofono(
  alHaberAudio: (muestras: Float32Array, nivel: number) => void,
): Promise<{ captura: CapturaMicrofono; stream: MediaStream }> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      sampleRate: SAMPLE_RATE_ENTRADA,
      channelCount: 1,
      // CRÍTICO: sin esto el tutor se oye por los parlantes y se auto-interrumpe.
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  const ctx = new AudioContext({ sampleRate: SAMPLE_RATE_ENTRADA });
  const url = URL.createObjectURL(new Blob([CODIGO_WORKLET], { type: "application/javascript" }));
  await ctx.audioWorklet.addModule(url);
  URL.revokeObjectURL(url);

  const nodo = new AudioWorkletNode(ctx, "captura-pcm", { numberOfOutputs: 0 });
  nodo.port.onmessage = (evento) => {
    const muestras = evento.data as Float32Array;
    let suma = 0;
    for (const m of muestras) suma += m * m;
    alHaberAudio(muestras, Math.sqrt(suma / muestras.length));
  };

  ctx.createMediaStreamSource(stream).connect(nodo);
  // A propósito NO se conecta a ctx.destination.

  return {
    stream,
    captura: {
      detener: () => {
        nodo.port.onmessage = null;
        nodo.disconnect();
        void ctx.close();
        stream.getTracks().forEach((t) => t.stop());
      },
    },
  };
}
