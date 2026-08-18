/**
 * Reproducción de audio sin cortes.
 *
 * EL ERROR HABITUAL es reproducir cada trozo apenas llega, lo que produce
 * clics y silencios entre trozos. La solución es programar cada chunk en el
 * instante exacto donde termina el anterior, usando el reloj del AudioContext.
 *
 * Es la pieza que hace que la voz suene continua. Si se toca una sola cosa de
 * este archivo, que no sea esto.
 *
 * (Verificado en el experimento walter-voz.)
 */

export const SAMPLE_RATE_SALIDA = 24_000; // lo que devuelve Gemini
export const SAMPLE_RATE_ENTRADA = 16_000; // lo que Gemini espera

/** Colchón por si venimos con retraso: arrancar ya en vez de rellenar un hueco. */
const COLCHON_SEG = 0.015;

export class ReproductorContinuo {
  private ctx: AudioContext | null = null;
  private proximoInicio = 0;
  private fuentes = new Set<AudioBufferSourceNode>();

  /** Tiene que llamarse DENTRO del gesto del usuario o el navegador lo suspende. */
  iniciar(): void {
    if (this.ctx) return;
    this.ctx = new AudioContext({ sampleRate: SAMPLE_RATE_SALIDA });
    this.proximoInicio = 0;
  }

  programar(base64: string): void {
    if (!this.ctx) return;

    const muestras = pcm16DesdeBase64(base64);
    const buffer = this.ctx.createBuffer(1, muestras.length, SAMPLE_RATE_SALIDA);
    buffer.copyToChannel(muestras, 0);

    const fuente = this.ctx.createBufferSource();
    fuente.buffer = buffer;
    fuente.connect(this.ctx.destination);

    const inicio = Math.max(this.ctx.currentTime + COLCHON_SEG, this.proximoInicio);
    fuente.start(inicio);
    this.proximoInicio = inicio + buffer.duration;

    this.fuentes.add(fuente);
    fuente.onended = () => {
      this.fuentes.delete(fuente);
      if (this.fuentes.size === 0) this.alTerminar?.();
    };
  }

  /**
   * Corta TODO lo ya programado, no solo deja de programar nuevo.
   *
   * Si no se detienen las fuentes que ya están en la cola, el tutor sigue
   * hablando varios segundos después de que el niño lo interrumpió.
   */
  detenerTodo(): void {
    for (const fuente of this.fuentes) {
      try {
        fuente.stop();
        fuente.disconnect();
      } catch {
        /* ya terminó */
      }
    }
    this.fuentes.clear();
    this.proximoInicio = this.ctx?.currentTime ?? 0;
  }

  get hablando(): boolean {
    return this.fuentes.size > 0;
  }

  alTerminar?: () => void;

  cerrar(): void {
    this.detenerTodo();
    void this.ctx?.close();
    this.ctx = null;
  }
}

/* ── Conversión ─────────────────────────────────────────────────────────── */

// El genérico explícito hace falta desde TS 5.7: copyToChannel exige
// Float32Array<ArrayBuffer>, no el ArrayBufferLike que se infiere solo.
function pcm16DesdeBase64(base64: string): Float32Array<ArrayBuffer> {
  const binario = atob(base64);
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);

  const enteros = new Int16Array(bytes.buffer);
  const flotantes = new Float32Array(enteros.length);
  for (let i = 0; i < enteros.length; i++) flotantes[i] = enteros[i] / 32_768;
  return flotantes;
}

/** Float32 → PCM 16-bit little-endian → base64. Es el único formato que acepta. */
export function aPcm16Base64(muestras: Float32Array): string {
  const buffer = new ArrayBuffer(muestras.length * 2);
  const vista = new DataView(buffer);
  for (let i = 0; i < muestras.length; i++) {
    const v = Math.max(-1, Math.min(1, muestras[i]));
    vista.setInt16(i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }
  const bytes = new Uint8Array(buffer);
  let binario = "";
  for (let i = 0; i < bytes.length; i++) binario += String.fromCharCode(bytes[i]);
  return btoa(binario);
}
