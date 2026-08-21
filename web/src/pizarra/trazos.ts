/**
 * Las letras y los números, como los traza una mano.
 *
 * Cada glifo es la lista de TRAZOS del lápiz, en el orden en que se escriben —
 * no el contorno de la letra. Un contorno animado se ve como alguien
 * repasando el borde; un trazo se ve como alguien escribiendo.
 *
 * Cómo se anima, y por qué es tan barato: cada trazo es un `<path>` con
 * `pathLength="1"`. Eso normaliza la longitud, así que `stroke-dasharray: 1` y
 * `stroke-dashoffset` de 1 → 0 dibuja la línea de punta a punta **sin tener que
 * medir nada**. Es una transición de CSS: sin `requestAnimationFrame`, sin
 * bucle, sin un frame de trabajo compitiendo con el audio.
 *
 * Caja de cada glifo: 50 de ancho por 100 de alto.
 *      y=10  techo de las altas (b, d, f, h, k, l, t)
 *      y=36  techo de las bajas (a, c, e, m, n, o…)
 *      y=75  la línea del renglón
 *      y=95  el pie de las que bajan (g, j, p, q, y)
 */

/** Un glifo son sus trazos, en orden de escritura. */
export type Glifo = string[];

export const ANCHO_GLIFO = 50;
export const ALTO_GLIFO = 100;

/** Cuánto tarda cada trazo en dibujarse.

Subido de 420 a 750 el 20/08, por el niño (`ses_227808f15f49`):

  "me la mostraste muy rápido, me confundes y no sé si me estás hablando de lo
   que dibujé o de lo que me estás mostrando... sería mejor que me vayas
   explicando y a medida de eso la vas dibujando"

La letra terminaba de escribirse antes de que el tutor terminara la frase que la
explicaba, y quedaban las dos cosas sueltas en el aire. Escribir despacio no es
un adorno: es lo que deja que la voz y el trazo vayan juntos. */
export const MS_POR_TRAZO = 750;

/** Un respiro antes del primer trazo.

El tutor llama a la pizarra en el momento en que lo decide, que suele ser ANTES
de decir "mira". Sin esta pausa la letra ya está a medio escribir cuando él
recién la está anunciando. */
export const MS_ANTES_DE_EMPEZAR = 900;

const NUMEROS: Record<string, Glifo> = {
  "0": ["M25 12 C13 12 9 28 9 43 C9 58 13 74 25 74 C37 74 41 58 41 43 C41 28 37 12 25 12"],
  "1": ["M14 25 L26 12 L26 74"],
  "2": ["M10 24 C10 15 18 12 25 12 C36 12 41 20 41 29 C41 43 20 52 10 74 L42 74"],
  "3": [
    "M11 18 C17 12 27 10 34 15 C42 21 40 33 28 38 C41 41 45 51 41 62 C37 72 22 78 11 70",
  ],
  "4": ["M33 74 L33 12 L8 55 L44 55"],
  "5": ["M40 12 L15 12 L12 40 C21 33 34 35 39 45 C45 57 38 72 24 74 C17 75 12 72 9 68"],
  "6": [
    "M38 15 C30 10 18 15 13 27 C9 39 9 62 19 71 C28 79 40 73 41 60 C41 48 32 40 22 43 C15 45 12 51 12 57",
  ],
  "7": ["M9 12 L42 12 L22 74"],
  "8": [
    "M25 12 C16 12 13 20 15 27 C18 36 34 38 38 48 C42 58 36 74 25 74 C14 74 8 58 12 48 C16 38 32 36 35 27 C37 20 34 12 25 12",
  ],
  "9": [
    "M13 68 C21 76 33 71 37 59 C41 47 41 22 32 14 C23 6 11 12 10 24 C10 36 19 44 29 41 C35 39 38 33 38 27",
  ],
};

const SIGNOS: Record<string, Glifo> = {
  "+": ["M25 22 L25 62", "M6 42 L44 42"],
  "−": ["M7 44 L43 44"],
  "-": ["M7 44 L43 44"],
  "×": ["M11 26 L39 58", "M39 26 L11 58"],
  x: ["M11 26 L39 58", "M39 26 L11 58"],
  "÷": ["M7 44 L43 44", "M25 27 L25 29", "M25 59 L25 61"],
  "=": ["M8 34 L42 34", "M8 54 L42 54"],
  "/": ["M38 12 L12 74"],
  ",": ["M26 70 C26 78 23 82 19 85"],
  ".": ["M25 73 L25 75"],
  "¿": ["M12 36 C12 26 19 20 26 22 C34 24 36 32 31 38 C27 43 25 46 25 53", "M25 62 L25 64"],
  "?": ["M14 30 C14 20 22 14 30 17 C38 20 39 29 34 35 C29 41 26 44 26 53", "M26 62 L26 64"],
};

/** Minúsculas. Es lo que un niño de primaria escribe: la mayúscula viene después. */
const LETRAS: Record<string, Glifo> = {
  a: ["M39 42 C33 34 20 33 14 41 C7 50 8 66 15 72 C22 78 34 76 39 69", "M39 36 L39 75"],
  b: ["M13 10 L13 75", "M13 44 C20 36 33 36 39 44 C45 53 44 66 37 72 C29 78 18 76 13 68"],
  c: ["M40 44 C34 35 20 33 13 42 C6 51 7 66 14 72 C21 78 34 76 40 68"],
  d: ["M39 10 L39 75", "M39 44 C32 36 19 36 13 44 C7 53 8 66 15 72 C23 78 34 76 39 68"],
  e: ["M10 56 L41 56", "M41 56 C41 44 32 34 22 36 C12 39 7 50 9 61 C12 72 23 78 34 73"],
  f: ["M38 15 C30 8 22 13 22 25 L22 75", "M11 38 L34 38"],
  g: [
    "M39 44 C32 36 19 36 13 44 C7 53 8 66 15 72 C23 78 34 76 39 68",
    "M39 36 L39 84 C39 93 30 97 20 93",
  ],
  h: ["M13 10 L13 75", "M13 46 C20 37 34 37 38 47 L38 75"],
  i: ["M25 23 L25 25", "M25 37 L25 75"],
  j: ["M28 23 L28 25", "M28 37 L28 85 C28 94 20 97 12 92"],
  k: ["M13 10 L13 75", "M38 39 L15 59", "M22 53 L39 75"],
  l: ["M25 10 L25 68 C25 74 29 77 34 75"],
  m: ["M11 37 L11 75", "M11 47 C16 38 26 38 29 47 L29 75", "M29 47 C33 38 43 38 46 47 L46 75"],
  n: ["M13 37 L13 75", "M13 47 C19 38 33 38 38 47 L38 75"],
  ñ: [
    "M13 37 L13 75",
    "M13 47 C19 38 33 38 38 47 L38 75",
    "M11 22 C16 15 22 24 28 21 C33 19 35 15 39 17",
  ],
  o: ["M25 35 C15 35 8 44 8 55 C8 67 15 76 25 76 C35 76 42 67 42 55 C42 44 35 35 25 35"],
  p: ["M13 37 L13 95", "M13 45 C20 37 33 37 39 45 C45 53 44 66 37 72 C29 78 18 76 13 68"],
  q: ["M39 45 C32 37 19 37 13 45 C7 53 8 66 15 72 C23 78 34 76 39 68", "M39 37 L39 95"],
  r: ["M14 37 L14 75", "M14 49 C18 39 28 34 37 38"],
  s: ["M39 43 C34 34 20 32 14 40 C8 47 14 54 24 57 C34 60 40 64 37 70 C33 77 18 78 11 71"],
  t: ["M22 17 L22 66 C22 74 28 78 34 74", "M11 37 L34 37"],
  u: ["M13 37 L13 64 C13 73 24 78 32 73 C36 71 38 68 38 64 L38 37", "M38 60 L38 75"],
  v: ["M11 37 L25 75 L39 37"],
  w: ["M8 37 L17 75 L25 51 L33 75 L42 37"],
  x: ["M12 37 L39 75", "M39 37 L12 75"],
  y: ["M11 37 L25 72", "M39 37 L21 90 C17 96 12 96 9 93"],
  z: ["M12 37 L39 37 L12 75 L41 75"],
  á: ["M39 42 C33 34 20 33 14 41 C7 50 8 66 15 72 C22 78 34 76 39 69", "M39 36 L39 75", "M20 25 L32 16"],
  é: ["M10 56 L41 56", "M41 56 C41 44 32 34 22 36 C12 39 7 50 9 61 C12 72 23 78 34 73", "M18 25 L30 16"],
  í: ["M25 37 L25 75", "M19 25 L31 16"],
  ó: ["M25 35 C15 35 8 44 8 55 C8 67 15 76 25 76 C35 76 42 67 42 55 C42 44 35 35 25 35", "M19 25 L31 16"],
  ú: ["M13 37 L13 64 C13 73 24 78 32 73 C36 71 38 68 38 64 L38 37", "M38 60 L38 75", "M19 25 L31 16"],
};

const GLIFOS: Record<string, Glifo> = { ...NUMEROS, ...SIGNOS, ...LETRAS };

/**
 * Los trazos de un carácter, o `null` si todavía no está dibujado.
 *
 * Que devuelva `null` NO es un error: quien llama vuelve a la letra impresa de
 * siempre. Es mejor mostrar la letra bien y sin animación que no mostrarla.
 */
export function trazosDe(caracter: string): Glifo | null {
  return GLIFOS[caracter] ?? GLIFOS[caracter.toLowerCase()] ?? null;
}

/** Si TODO lo que hay que escribir se puede trazar a mano. */
export function seEscribeAMano(texto: string): boolean {
  const sinEspacios = [...texto].filter((c) => c !== " ");
  return sinEspacios.length > 0 && sinEspacios.every((c) => trazosDe(c) !== null);
}

/** Todos los caracteres que se saben trazar. Para verlos juntos y corregirlos. */
export const CARACTERES_CONOCIDOS = Object.keys(GLIFOS);
