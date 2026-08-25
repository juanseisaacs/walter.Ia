/**
 * El diario de la voz: lo que solo esta pestaña sabe.
 *
 * Cuánto tardó el modelo en contestar, cuánto tardó un tool, cuándo el barge-in
 * cortó al tutor, cuándo la voz dejó de sonar. Todo eso decide si una
 * conversación se siente fluida, y hasta el 25/08 vivía en `console.info` — o
 * sea, **se perdía al cerrar la pestaña**.
 *
 * Tres diagnósticos seguidos ese día terminaron en una hipótesis por eso. El
 * backend responde en 4 ms y no ve nada de este camino; la transcripción llega
 * por otro lado, así que una sesión que se sintió pésima se ve igual de sana
 * que una buena. Lo único que quedaba era el niño diciendo «se enreda».
 *
 * Reglas de esta pieza, y las dos son la razón de que exista aparte:
 *
 *   · **nunca en el camino del audio.** Se acumula en memoria y se manda en
 *     lotes, sin esperar respuesta. Si un lote se pierde, se pierde: es
 *     diagnóstico, no puede costarle un milisegundo al niño.
 *   · **con techo.** Una sesión larga con el barge-in disparando seguido
 *     generaría miles de eventos; el diario que llena la memoria del navegador
 *     rompería justo lo que viene a diagnosticar.
 */

/** Un evento del camino de voz. `t` es el tipo; el resto depende de cuál. */
export interface EventoDeVoz {
  t: string;
  ms?: number;
  [clave: string]: unknown;
}

/** Cuántos eventos se juntan antes de mandar el lote. */
export const EVENTOS_POR_LOTE = 12;

/**
 * Techo de eventos sin mandar. Al pasarlo se tiran los MÁS VIEJOS.
 *
 * Los viejos y no los nuevos: cuando una sesión se rompe, lo que explica por
 * qué está al final. Guardar el principio y perder el final sería quedarse con
 * la única parte que no hace falta.
 */
export const TECHO_PENDIENTES = 200;

export class Diario {
  private pendientes: EventoDeVoz[] = [];

  constructor(private readonly enviar: (eventos: EventoDeVoz[]) => void) {}

  /** Anota un evento y manda el lote si ya se juntaron suficientes. */
  anota(evento: EventoDeVoz): void {
    this.pendientes.push({ ...evento, en: Date.now() });
    if (this.pendientes.length > TECHO_PENDIENTES) {
      this.pendientes.splice(0, this.pendientes.length - TECHO_PENDIENTES);
    }
    if (this.pendientes.length >= EVENTOS_POR_LOTE) this.drena();
  }

  /** Manda lo que haya. Se llama al cerrar la sesión y cada tanto. */
  drena(): void {
    if (!this.pendientes.length) return;
    this.enviar(this.pendientes.splice(0));
  }

  get pendiente(): number {
    return this.pendientes.length;
  }
}
