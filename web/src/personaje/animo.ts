/**
 * En qué está el tutor, dicho en términos del personaje.
 *
 * Esto es lo ÚNICO del personaje que se puede testear: el SVG es un dibujo y
 * un dibujo no se prueba con asserts, se mira (ver `/pizarra`). Lo que sí se
 * prueba es la traducción — de lo que pasa en la sesión a lo que hace el
 * cuerpo — porque es donde se puede meter un bug callado: un tutor que sigue
 * moviendo la boca cuando ya se calló, o que se queda mirando la pizarra
 * mientras el niño le habla.
 *
 * Ningún ánimo sale de adivinar. Los cinco salen de señales que la app YA
 * tiene: el estado de la conexión, si le mandaron una foto, y el reloj de la
 * mudez (`MS_MUDEZ` en `voz/useTutor.ts`).
 */

/** Lo que el cuerpo del personaje puede estar haciendo. */
export type Animo =
  /** Todavía no hay sesión. Quieto, presente, sin fingir que duerme. */
  | "reposo"
  /** Conectando: el saludo. Dura poco y no se repite. */
  | "saludando"
  /** El turno es del niño. Cabeza ladeada, mirada al frente. */
  | "escuchando"
  /** El turno es del tutor. La boca articula. */
  | "hablando"
  /** Le llegó una foto y la está mirando. Se inclina hacia el papel. */
  | "mirando"
  /** El niño no contesta hace rato. Espera con paciencia, sin apurar. */
  | "esperando";

/** Lo que el personaje necesita saber. Nada de esto es voz ni red. */
export interface Señales {
  /** El mismo `Estado` de `useTutor`, tal cual. */
  estado: "inicio" | "conectando" | "escuchando" | "hablando" | "error";
  /** Le mandaron una foto y todavía no contesta. */
  mirandoFoto?: boolean;
  /** El reloj de la mudez ya se venció al menos una vez. */
  mudo?: boolean;
}

/**
 * De lo que pasa en la sesión a lo que hace el cuerpo.
 *
 * El orden de las guardas ES la decisión pedagógica: hablar gana sobre todo lo
 * demás porque la voz es el producto. Si el tutor está hablando de la foto, el
 * personaje habla — no se queda con cara de estar leyendo.
 */
export function animoDesde({ estado, mirandoFoto, mudo }: Señales): Animo {
  if (estado === "hablando") return "hablando";
  if (estado === "conectando") return "saludando";
  if (estado === "inicio" || estado === "error") return "reposo";
  // De acá para abajo, el turno es del niño.
  if (mirandoFoto) return "mirando";
  if (mudo) return "esperando";
  return "escuchando";
}

/**
 * Lo que oye quien no ve la pantalla.
 *
 * El personaje es decorativo para un lector de pantalla EXCEPTO en una cosa:
 * de quién es el turno. Eso no es adorno — es la información que el niño
 * vidente saca del color y de la cabeza ladeada.
 */
export function comoSeLee(animo: Animo): string {
  switch (animo) {
    case "hablando":
      return "tu tutor está hablando";
    case "mirando":
      return "tu tutor está mirando tu foto";
    case "esperando":
      return "tu tutor te espera";
    case "saludando":
      return "tu tutor está llegando";
    case "reposo":
      return "tu tutor";
    case "escuchando":
      return "tu tutor te escucha";
  }
}

/**
 * El nivel del micrófono, convertido en el "respiro" del personaje.
 *
 * Solo mientras escucha: es la señal de vuelta de que lo están oyendo. Se
 * corta a 1.12 porque un grito no puede hacer que el tutor se salga de la
 * pantalla, y el `Math.max(0, …)` porque un nivel negativo daría vuelta el
 * dibujo — eso sí que asusta a un niño.
 */
export function respiro(animo: Animo, nivelMic: number): number {
  if (animo === "hablando") return 1.03;
  if (animo !== "escuchando") return 1;
  return 1 + Math.min(Math.max(0, nivelMic), 1) * 0.12;
}
