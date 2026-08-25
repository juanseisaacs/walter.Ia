/**
 * La línea de retardo del micrófono, y la regla que decide qué sale por ella.
 *
 * ESTO ES UNA SOLA INVARIANTE: **por cada bloque que entra, sale exactamente
 * uno.** El stream que ve el servidor avanza al mismo ritmo que el reloj de
 * pared — ni se corta ni se alarga. Todo lo demás de este archivo existe para
 * sostener eso mientras se resuelven dos problemas que tiran en direcciones
 * opuestas:
 *
 *   · **el eco del tutor no puede viajar.** El VAD del servidor corre en
 *     `START_SENSITIVITY_HIGH` —a propósito, para que el niño que habla bajito
 *     abra turno— y con ese oído el eco por los parlantes cuenta como "el niño
 *     empezó a hablar": le corta la generación a mitad de palabra.
 *
 *   · **pero el stream no puede pararse.** «`silenceDurationMs` only works
 *     within a continuous stream — it measures quiet periods, not stream
 *     interruptions.» Sin audio, el reloj del VAD se detiene y el turno del
 *     niño se queda colgado sin cerrar.
 *
 * La respuesta a los dos es la misma: mientras el tutor suena sale SILENCIO del
 * largo exacto del bloque que entró. Y cuando el barge-in confirma que abajo
 * estaba el niño, sale el audio de verdad — incluido el que ya estaba en la
 * cola, que es donde vive la primera sílaba de la interrupción.
 *
 * Vive fuera de `useTutor` porque es la pieza donde un error no se ve: se
 * siente, tres turnos después, como un tutor que contesta a destiempo. Acá se
 * puede contar bloque a bloque.
 */

/** Un bloque listo para el cable. `mudo` = va como silencio, no como audio. */
export interface BloqueDeSalida {
  muestras: Float32Array;
  mudo: boolean;
}

export interface EstadoDeLaCola {
  /** ¿Hay que retener? (el tutor suena, o se está esperando el saludo) */
  reteniendo: boolean;
  /** ¿El barge-in ya confirmó que lo que hay abajo es el niño? */
  interrumpio: boolean;
  /** Profundidad de la línea de retardo, en bloques. Ver `BLOQUES_RETENIDOS`. */
  fondo: number;
}

/**
 * Mete un bloque en la cola y devuelve los que salen, ya decididos.
 *
 * `cola` se muta: es un búfer de audio que se recorre cada ~64 ms en el hilo
 * del navegador, y copiarlo entero en cada vuelta sería pagar por nada.
 *
 * Reteniendo, la cola guarda `fondo` bloques: ese retardo es lo que le da al
 * barge-in tiempo de pronunciarse sobre un bloque ANTES de que salga, y por eso
 * la primera sílaba de una interrupción sale entera en vez de perderse. Cuando
 * ya no hay nada que retener la cola se vacía de una: esa descarga no alarga el
 * stream —esos bloques nunca se enviaron— y es la que devuelve el arranque de
 * la frase del niño que empieza a hablar pegado al final del turno del tutor.
 */
export function pasarPorLaCola(
  cola: Float32Array[],
  muestras: Float32Array,
  { reteniendo, interrumpio, fondo }: EstadoDeLaCola,
): BloqueDeSalida[] {
  cola.push(muestras);

  const salida: BloqueDeSalida[] = [];
  const enEspera = reteniendo ? fondo : 0;
  while (cola.length > enEspera) {
    // El `!` es seguro: la guarda del while ya garantiza que hay al menos uno.
    salida.push({ muestras: cola.shift()!, mudo: reteniendo && !interrumpio });
  }
  return salida;
}

/**
 * ¿Cuánto lleva sonando una voz que no es la del tutor?
 *
 * Devuelve el acumulado nuevo. Cuando pasa de `MS_PARA_CORTAR` el barge-in
 * corta — ver `useTutor`.
 *
 * DECAE, NO SE RESETEA, y esa es la corrección del 25/08. Una frase no es un
 * tono continuo: entre sílaba y sílaba hay bloques de 64 ms por debajo del
 * umbral, y ponerlo en cero con cada uno hacía que el contador casi nunca
 * llegara al corte. El niño hablaba encima del tutor, el barge-in no se
 * confirmaba, y su audio se iba al silencio mientras él veía que no lo
 * escuchaban. Decayendo al mismo ritmo que sube, una frase con pausas normales
 * llega igual y un golpe suelto en la mesa sigue sin alcanzar.
 */
export function vozSostenida(
  acumuladoMs: number,
  { hayVoz, bloqueMs }: { hayVoz: boolean; bloqueMs: number },
): number {
  return hayVoz ? acumuladoMs + bloqueMs : Math.max(0, acumuladoMs - bloqueMs);
}

/**
 * Tras callar al tutor, ¿el audio que sigue llegando todavía está en duda?
 *
 * El barge-in apaga el parlante, pero Gemini sigue mandando el resto del turno.
 * Esos bloques iban derecho al reproductor y **el tutor volvía a sonar encima
 * del niño** medio segundo después de que lo callaron — la otra mitad de «al
 * mismo tiempo que me escucha, está hablando».
 *
 * No se tiran, se retienen: si el barge-in fue un falso positivo —una silla, un
 * eco fuerte— el servidor no va a confirmar ningún corte, y tirar el audio
 * dejaría al tutor mudo a mitad de frase, que es peor que el bug. Mientras esto
 * diga que sí, el audio espera; cuando vence, el tutor retoma donde iba y el
 * falso positivo costó una pausa en vez del turno entero.
 *
 * `abortadoEn` en 0 significa que no hay nada abortado.
 */
export function sigueEnDuda(abortadoEn: number, ahora: number, esperaMs: number): boolean {
  return abortadoEn !== 0 && ahora - abortadoEn <= esperaMs;
}
