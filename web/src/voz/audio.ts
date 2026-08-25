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

/** Lo que viaja en cada bloque. DERIVADO de la constante, no escrito a mano.
 *
 * Estaba cableado como `"audio/pcm;rate=16000"` en el hook mientras el sample
 * rate vivía acá arriba: mover uno dejaba al otro mintiendo, y el resultado no
 * es un error sino un tutor que oye al niño a otra velocidad. El backend ya lo
 * derivaba (`voice.MIME_ENTRADA`); esta punta no. */
export const MIME_ENTRADA = `audio/pcm;rate=${SAMPLE_RATE_ENTRADA}`;

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
  /** Cuándo se vació la cola (`Date.now()`). 0 = no viene de hablar. */
  private finDeHabla = 0;
  /** ¿Hay un `resume()` en vuelo? Evita encolar uno por chunk. */
  private despertando = false;
  /**
   * `Date.now()` de la última vez que un trozo TERMINÓ DE SONAR de verdad.
   *
   * No es lo mismo que "se programó": un `AudioBufferSourceNode` sobre un
   * contexto suspendido nunca dispara `onended`, porque el reloj que lo
   * dispararía está detenido. Justamente por eso sirve como prueba de vida —
   * es la única señal que distingue «el tutor está hablando» de «el tutor cree
   * que está hablando». Ver `vozMuda`.
   */
  private ultimoSonido = 0;
  /** `Date.now()` en que empezó la tanda de audio que está sonando ahora. Es la
      referencia cuando todavía no terminó de sonar ningún trozo. */
  private programadoDesde = 0;

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

    // UN SOLO `resume()` A LA VEZ.
    //
    // Gemini manda la respuesta en ráfaga: con el contexto suspendido, cada
    // chunk entraba acá y encolaba su propio `resume()`. Al resolverse todos,
    // `detenerTodo()` corría una vez por chunk — y cada corrida borraba lo que
    // las anteriores acababan de programar. El resultado es que la ráfaga
    // entera se perdía aunque el contexto ya hubiera despertado.
    //
    // Se ve como un tutor que "vuelve" pero no suena, y es lo que hacía más
    // difícil recuperarse de un contexto suspendido (`ses_6c6fb58aafbb`).
    if (this.despertando) return;
    this.despertando = true;

    void ctx.resume().then(() => {
      this.despertando = false;
      // El reloj estuvo detenido: lo encolado quedó en un futuro que ya no
      // corresponde. Se descarta para que la próxima frase suene YA.
      //
      // detenerTodo() y no solo mover el puntero: si las fuentes viejas siguen
      // programadas, vuelven a sonar encima de lo que venga y el niño oye dos
      // tutores. Lo que se dijo mientras nadie escuchaba ya no sirve.
      this.detenerTodo();
    }, (e) => {
      // El navegador puede rechazar el resume (política de autoplay, contexto
      // ya cerrado). Sin este brazo, `despertando` se quedaba en true para
      // siempre y NUNCA se volvía a intentar: el tutor quedaba mudo el resto de
      // la sesión por un rechazo transitorio.
      this.despertando = false;
      console.warn("[audio] no se pudo despertar el contexto:", e);
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

    if (this.fuentes.size === 0) this.programadoDesde = Date.now();
    this.fuentes.add(fuente);
    this.finDeHabla = 0; // vuelve a haber audio programado
    fuente.onended = () => {
      this.fuentes.delete(fuente);
      // Prueba de vida: si esto corre, el reloj del contexto está andando y el
      // trozo se reprodujo. Sobre un contexto suspendido nunca llega.
      this.ultimoSonido = Date.now();
      if (this.fuentes.size === 0) {
        this.finDeHabla = Date.now();
        this.alTerminar?.();
      }
    };
  }

  /**
   * ¿Hay audio programado que NO está sonando?
   *
   * Es el diagnóstico que faltaba, y el que convierte en dato lo que hasta el
   * 25/08 había que descubrir hablando: *«estoy viendo que estás hablando y
   * hablando y como que no se escucha, solo leo lo que estás diciendo»*
   * (`ses_660ce383567d`). El mismo síntoma exacto había aparecido ya en
   * `ses_91c13b1747a2` y `ses_6c6fb58aafbb`, cada vez por una causa distinta —
   * el contexto suspendido, la cola en el futuro, un turno retenido de más.
   *
   * Por eso esto NO pregunta por ninguna causa: pregunta por el síntoma. Hay
   * trozos programados, ha pasado `toleranciaMs` y ninguno terminó de sonar.
   * Sea cual sea el motivo, el niño está viendo hablar a un tutor mudo.
   */
  vozMuda(toleranciaMs: number): boolean {
    if (this.fuentes.size === 0) return false; // no hay nada que debiera sonar

    // LA TOLERANCIA SE APLICA SIEMPRE, también cuando el contexto no está
    // corriendo. Una suspensión es normal y transitoria —la pestaña se va al
    // fondo, el sistema ahorra energía— y `asegurarActivo()` la resuelve sola
    // en milisegundos. Denunciarla en el acto convertiría cada una de esas en
    // un contexto recreado, y dos seguidas le cerrarían la sesión al niño por
    // haber mirado otra ventana.
    //
    // Si todavía no terminó de sonar ningún trozo de esta tanda, la referencia
    // es cuándo empezó: el primer turno de la sesión también tiene que estar
    // cubierto, y ahí `ultimoSonido` es cero.
    const referencia = this.ultimoSonido || this.programadoDesde;
    if (referencia === 0 || Date.now() - referencia <= toleranciaMs) return false;
    return true;
  }

  /**
   * El último recurso: tirar el contexto y hacer uno nuevo.
   *
   * `iniciar()` no puede hacerlo —ve que ya hay uno y se va—, y hay estados de
   * los que un `resume()` no saca: el dispositivo de salida que se fue con los
   * audífonos, el contexto que quedó atado a un sink que ya no existe. Devuelve
   * si el contexto nuevo quedó andando: fuera del gesto del usuario el
   * navegador puede dejarlo suspendido, y en ese caso hay que decírselo al niño
   * en vez de dejarlo mirando a un tutor que no suena.
   */
  reiniciar(): boolean {
    const anterior = this.ctx;
    if (anterior) {
      anterior.onstatechange = null;
      void anterior.close().catch(() => {});
    }
    this.ctx = null;
    this.fuentes.clear();
    this.proximoInicio = 0;
    this.finDeHabla = 0;
    this.ultimoSonido = 0;
    this.despertando = false;
    document.removeEventListener("visibilitychange", this.alVolverAlFrente);
    this.iniciar();
    return this.ctx !== null && (this.ctx as AudioContext).state === "running";
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
    // Sin cola de guarda: acá el tutor no terminó, lo CALLARON. Lo que venga
    // por el micrófono es el niño interrumpiendo y tiene que salir ya.
    this.finDeHabla = 0;
  }

  get hablando(): boolean {
    return this.fuentes.size > 0;
  }

  /**
   * Como `hablando`, pero aguantando `colaMs` después del último sonido.
   *
   * Existe porque `hablando` cae a false en dos momentos en los que el tutor
   * NO terminó de hablar:
   *
   *   · **entre chunks.** Gemini manda en ráfagas; si una llega tarde, la cola
   *     se vacía a mitad de frase y el set queda en cero por unos milisegundos.
   *   · **justo al terminar.** La última fuente deja de sonar, pero la cola
   *     acústica del parlante sigue entrando por el micrófono.
   *
   * En los dos casos el micrófono soltaba audio con el eco del propio tutor
   * adentro, y del otro lado el VAD del servidor —en `START_SENSITIVITY_HIGH`,
   * a propósito, para que el niño que habla bajito abra turno— lo leía como
   * "el niño empezó a hablar" y CORTABA LA GENERACIÓN.
   *
   * Es la mitad que faltaba del arreglo del 23/08: retener mientras
   * `hablando` sea true tapó el caso largo y dejó abiertos los huecos cortos.
   * En `ses_0a6036dedf55` el saludo de apertura quedó partido a mitad de frase
   * —«¿tienes alguna»— y el niño lo dijo él mismo: «no terminaste de hablar,
   * como que se te cortó la frase».
   *
   * NO se usa para el barge-in: ahí manda `hablando` pelado, porque cortar al
   * tutor es decisión del niño y no puede depender de un colchón nuestro.
   */
  sonandoHace(colaMs: number): boolean {
    if (this.fuentes.size > 0) return true;
    return this.finDeHabla > 0 && Date.now() - this.finDeHabla < colaMs;
  }

  alTerminar?: () => void;

  cerrar(): void {
    this.detenerTodo();
    document.removeEventListener("visibilitychange", this.alVolverAlFrente);
    if (this.ctx) this.ctx.onstatechange = null;
    void this.ctx?.close();
    this.ctx = null;
    // Si quedó un resume en vuelo sobre el contexto que acabamos de cerrar, su
    // flag no puede sobrevivir: bloquearía el próximo despertar.
    this.despertando = false;
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

/**
 * Un bloque de silencio PCM16 del largo pedido, listo para mandar.
 *
 * EXISTE PORQUE EL VAD DE GEMINI NECESITA UN STREAM CONTINUO, y esa es la
 * causa raíz de que la conversación se enredara y terminara cayéndose
 * (`ses_02805f3edba1`). La documentación de la Live API lo dice sin
 * ambigüedad:
 *
 *   «`silenceDurationMs` only works within a continuous stream — it measures
 *    quiet periods, not stream interruptions.»
 *
 * El arreglo del 23/08 dejó de mandar audio mientras el tutor habla, para que
 * su propio eco no le cortara la generación. Resolvió eso y rompió el supuesto
 * de abajo: **el reloj del VAD dejó de correr**. El servidor se quedaba con
 * audio en caché sin cerrar, y al volver el micrófono pegaba lo de antes con lo
 * nuevo como si fueran contiguos — la voz del niño llegando tarde y las frases
 * enredándose una con otra.
 *
 * Mandar silencio en vez de nada resuelve las dos cosas a la vez: el eco del
 * tutor no viaja (sigue el arreglo del 23/08) y el reloj del VAD sigue
 * corriendo, viendo exactamente lo que hay — silencio.
 *
 * Se cachea por largo: son siempre los mismos dos o tres tamaños, y esto corre
 * cada ~64 ms en el hilo del navegador.
 */
const silencios = new Map<number, string>();

export function silencioPcm16Base64(muestras: number): string {
  const guardado = silencios.get(muestras);
  if (guardado !== undefined) return guardado;
  const b64 = aPcm16Base64(new Float32Array(muestras));
  silencios.set(muestras, b64);
  return b64;
}
