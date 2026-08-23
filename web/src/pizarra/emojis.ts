/**
 * De la palabra del tutor al dibujito que ve el niño.
 *
 * Lo pidió Juan, con estas palabras, el 22/08:
 *
 *   «Explora la opción de que puedas de alguna forma pintar una especie de
 *    dibujitos y no solo cuadros y números. Me gustaría eso a mí como niño.»
 *
 * Y antes, en la misma sesión: «me gustaría poder ver las gallinas y los patos».
 * El tutor le contestó la verdad —que solo podía poner grupitos y números— y
 * siguió con puntos naranjas. El niño tuvo que preguntar «¿los puntos naranjas y
 * verdes son las galletas?» para entender qué estaba mirando.
 *
 * Esto no cambia nada de cómo el tutor pide la pizarra: sigue mandando
 * `grupos` con un `nombre`. Lo único que cambia es que si ese nombre es una cosa
 * que sabemos dibujar, en vez de un punto sale la cosa. Cero tokens, cero
 * llamadas, cero cambios en el contrato con el modelo.
 *
 * Sin coincidencia se dibuja el punto de siempre, que funciona: un mapa
 * incompleto no puede dejar la pizarra en blanco.
 */

/** Palabra (en singular, sin tildes) → dibujito. */
const DIBUJOS: Record<string, string> = {
  // Lo que un tutor de primaria usa para contar. Salido de los enunciados
  // reales del banco y de lo que apareció en las sesiones.
  manzana: "🍎",
  galleta: "🍪",
  dulce: "🍬",
  caramelo: "🍬",
  mandarina: "🍊",
  naranja: "🍊",
  banano: "🍌",
  platano: "🍌",
  pera: "🍐",
  fresa: "🍓",
  uva: "🍇",
  huevo: "🥚",
  pan: "🍞",
  torta: "🍰",
  pastel: "🍰",
  helado: "🍦",
  pizza: "🍕",

  gallina: "🐔",
  // Juan pidió pollitos dos veces en la misma sesión y le salieron puntos:
  // `gallina` estaba, `pollito` no (ses_97d5b112a122).
  pollito: "🐤",
  pollo: "🐥",
  pato: "🦆",
  vaca: "🐄",
  cerdo: "🐷",
  marrano: "🐷",
  oveja: "🐑",
  caballo: "🐴",
  perro: "🐶",
  gato: "🐱",
  pez: "🐟",
  pajaro: "🐦",
  mariposa: "🦋",
  abeja: "🐝",
  hormiga: "🐜",
  dinosaurio: "🦖",

  carro: "🚗",
  carrito: "🚗",
  bus: "🚌",
  avion: "✈️",
  barco: "⛵",
  bicicleta: "🚲",
  pelota: "⚽",
  balon: "⚽",
  juguete: "🧸",
  muneco: "🧸",
  peluche: "🧸",
  globo: "🎈",
  regalo: "🎁",

  lapiz: "✏️",
  libro: "📚",
  cuaderno: "📓",
  crayon: "🖍️",
  tijera: "✂️",
  moneda: "🪙",
  billete: "💵",
  estrella: "⭐",
  flor: "🌸",
  arbol: "🌳",
  hoja: "🍃",
  piedra: "🪨",
  concha: "🐚",
  ficha: "🔵",
  bolita: "🔵",
  canica: "🔵",
};

/** Plurales que no salen de quitar una `s`. */
const IRREGULARES: Record<string, string> = {
  peces: "pez",
  lapices: "lapiz",
  aviones: "avion",
  balones: "balon",
  pollitos: "pollito",
  pollo: "pollito",
  pollos: "pollito",
  panes: "pan",
  flores: "flor",
  arboles: "arbol",
  pajaros: "pajaro",
};

function normalizar(palabra: string): string {
  return palabra
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // fuera tildes: "plátano" y "platano" son lo mismo
    .replace(/[^a-zñ]/g, "");
}

/**
 * El dibujito de lo que el tutor nombró, o `null` si no lo sabemos dibujar.
 *
 * Acepta la frase entera («bolsas de manzanas», «cajas de 4 lápices») y busca
 * palabra por palabra: el tutor escribe en español de verdad, no etiquetas.
 */
export function dibujoDe(nombre: string | undefined): string | null {
  if (!nombre) return null;

  for (const cruda of nombre.split(/\s+/)) {
    const palabra = normalizar(cruda);
    if (!palabra) continue;

    if (DIBUJOS[palabra]) return DIBUJOS[palabra];
    if (IRREGULARES[palabra]) return DIBUJOS[IRREGULARES[palabra]];

    // Plural regular. Las dos formas, y en este orden: quitando solo la `s`
    // sale "dulce" de "dulces"; quitando `es`, sale "flor" de "flores". Con
    // una sola regla, "dulces" daba "dulc" y no encontraba nada.
    for (const singular of [palabra.replace(/s$/, ""), palabra.replace(/es$/, "")]) {
      if (DIBUJOS[singular]) return DIBUJOS[singular];
    }
  }
  return null;
}
