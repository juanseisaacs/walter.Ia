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

/**
 * Si lo próximo quedó programado más allá de esto, algo se desincronizó.
 *
 * Pasa cuando el contexto estuvo suspendido: su reloj se detiene, pero los
 * chunks siguen llegando y encolándose uno detrás del otro. Al reanudar, la
 * cola arranca en un instante que ya quedó lejísimos en el futuro y el tutor
 * sigue mudo aunque técnicamente esté "reproduciendo".
 *
 * ESTO ES UNA RED DE SEGURIDAD, NO UN UMBRAL DE CONVERSACIÓN. Estuvo en 2 s
 * entre el 18/08 09:04 y las 13:30, y ahí se rompió el audio: Gemini manda la
 * respuesta en ráfaga, mucho más rápido que tiempo real, así que una frase de
 * más de dos segundos deja la cola legítimamente en el futuro. Con el umbral
 * en 2 s eso se leía como desincronización en CADA frase.
 *
 * El caso patológico deja la cola minutos adelante, no segundos. 30 s no se
 * alcanza hablando y sigue atrapando la suspensión real.
 */
const DERIVA_MAX_SEG = 30;

export class ReproductorContinuo {
  private ctx: AudioContext | null = null;
  private proximoInicio = 0;
  private fuentes = new Set<AudioBufferSourceNode>();
  private alVolverAlFrente = () => this.asegurarActivo();

  /** Tiene que llamarse DENTRO del gesto del usuario o el navegador lo suspende. */
  iniciar(): void {
    if (this.ctx) {
      this.asegurarActivo();
      return;
    }
    this.ctx = new AudioContext({ sampleRate: SAMPLE_RATE_SALIDA });
    this.proximoInicio = 0;

    // El navegador puede suspender el contexto por su cuenta — al cambiar de
    // pestaña, al bloquear la pantalla, por ahorro de energía. Nadie avisa: el
    // audio simplemente deja de sonar mientras todo lo demás sigue igual.
    this.ctx.onstatechange = () => {
      console.info(`[audio] contexto ${this.ctx?.state}`);
      if (this.ctx?.state === "suspended") this.asegurarActivo();
    };
    document.addEventListener("visibilitychange", this.alVolverAlFrente);
  }

  /**
   * Despierta el contexto si el navegador lo durmió.
   *
   * Sin esto, `iniciar()` veía que el contexto ya existía y volvía sin más: los
   * chunks se programaban contra un reloj detenido. Es lo que le pasó a Juan en
   * `ses_91c13b1747a2` — "¿por qué dejaste de hablar y solo estoy viendo el
   * texto?". El tutor no se colgó: estaba hablando para nadie.
   */
  private asegurarActivo(): void {
    const ctx = this.ctx;
    if (!ctx || ctx.state !== "suspended") return;
    void ctx.resume().then(() => {
      // El reloj estuvo detenido: lo encolado quedó en un futuro que ya no
      // corresponde. Se descarta para que la próxima frase suene YA.
      //
      // detenerTodo() y no solo mover el puntero: si las fuentes viejas siguen
      // programadas, vuelven a sonar encima de lo que venga y el niño oye dos
      // tutores. Lo que se dijo mientras nadie escuchaba ya no sirve.
      this.detenerTodo();
    });
  }

  programar(base64: string): void {
    if (!this.ctx) return;
    this.asegurarActivo();

    // Red de seguridad: si la cola se fue al futuro, se vuelve al presente.
    // Programar para dentro de tres minutos es indistinguible de estar mudo.
    //
    // detenerTodo() y NO `proximoInicio = currentTime` a secas. Mover el
    // puntero sin cortar lo que ya está sonando no resincroniza: SOLAPA. El
    // chunk nuevo arranca encima del audio en curso y se oyen dos voces del
    // mismo tutor, cada vez peor a medida que se acumulan. Es lo que rompió
    // las sesiones del 18/08 entre las 09:04 y las 13:30.
    //
    // Lo encolado ya perdió su momento en la conversación: se descarta.
    if (this.proximoInicio > this.ctx.currentTime + DERIVA_MAX_SEG) {
      console.warn("[audio] cola desincronizada: se descarta y se resincroniza");
      this.detenerTodo(); // deja proximoInicio en currentTime
    }

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
    document.removeEventListener("visibilitychange", this.alVolverAlFrente);
    if (this.ctx) this.ctx.onstatechange = null;
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
