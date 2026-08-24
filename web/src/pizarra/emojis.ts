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
  // «Ahora me gustan los unicornios. 16 unicornios + 15 unicornios» — y no
  // había ninguno. El catálogo se llena con lo que los niños piden, no con lo
  // que se nos ocurre a nosotros.
  unicornio: "🦄",
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

  // ── Lo que Juan pidió el 23/08 y no estaba ──────────────────────────────
  //
  //   nino:  «Son 10 tenis más ocho tenis.»
  //   tutor: «Fíjate que imagen de tenis no tengo, pero te puse unos puntitos»
  //   nino:  «que quede registrado que deberías tener todos los emojis
  //           disponibles como imagen para este tipo de sumas»
  //
  // Todos no se puede —son miles— pero el criterio es suyo y es el correcto:
  // que un niño no tenga que conformarse con puntos por nombrar algo normal.
  // Lo que sigue es lo que un chico de primaria nombra cuando cuenta cosas.
  tenis: "👟",
  zapato: "👟",
  zapatilla: "👟",
  bota: "🥾",
  gafas: "👓",
  gafa: "👓",
  lente: "👓",
  gorra: "🧢",
  sombrero: "🎩",
  camiseta: "👕",
  camisa: "👕",
  pantalon: "👖",
  media: "🧦",
  guante: "🧤",
  mochila: "🎒",
  maleta: "🎒",

  queso: "🧀",
  leche: "🥛",
  hamburguesa: "🍔",
  papa: "🥔",
  sandia: "🍉",
  pina: "🍍",
  limon: "🍋",
  durazno: "🍑",
  cereza: "🍒",
  zanahoria: "🥕",
  tomate: "🍅",
  maiz: "🌽",
  chocolate: "🍫",
  paleta: "🍭",
  jugo: "🧃",
  agua: "💧",

  leon: "🦁",
  tigre: "🐯",
  elefante: "🐘",
  mono: "🐵",
  oso: "🐻",
  conejo: "🐰",
  rana: "🐸",
  tortuga: "🐢",
  serpiente: "🐍",
  culebra: "🐍",
  arana: "🕷️",
  caracol: "🐌",
  delfin: "🐬",
  ballena: "🐳",
  tiburon: "🦈",
  pinguino: "🐧",
  panda: "🐼",
  jirafa: "🦒",
  cebra: "🦓",
  cocodrilo: "🐊",
  buho: "🦉",
  raton: "🐭",
  ardilla: "🐿️",
  cangrejo: "🦀",
  pulpo: "🐙",

  sol: "☀️",
  luna: "🌙",
  nube: "☁️",
  rayo: "⚡",
  fuego: "🔥",
  gota: "💧",
  montana: "⛰️",
  cactus: "🌵",
  hongo: "🍄",
  girasol: "🌻",
  rosa: "🌹",
  semilla: "🌰",

  casa: "🏠",
  reloj: "⏰",
  llave: "🔑",
  taza: "☕",
  vaso: "🥤",
  plato: "🍽️",
  cuchara: "🥄",
  tenedor: "🍴",
  silla: "🪑",
  cama: "🛏️",
  puerta: "🚪",
  ventana: "🪟",
  campana: "🔔",
  corazon: "❤️",
  diamante: "💎",
  trofeo: "🏆",
  medalla: "🏅",
  corona: "👑",
  dado: "🎲",
  carta: "✉️",
  tambor: "🥁",
  guitarra: "🎸",
  piano: "🎹",
  camara: "📷",
  telefono: "📱",
  celular: "📱",
  computador: "💻",
  robot: "🤖",
  cohete: "🚀",
  fantasma: "👻",

  tren: "🚂",
  moto: "🏍️",
  camion: "🚚",
  helicoptero: "🚁",
  patineta: "🛹",
  cometa: "🪁",
  raqueta: "🎾",
  canasta: "🏀",
  basquetbol: "🏀",
  beisbol: "⚾",
};

/** Plurales que no salen de quitar una `s`. */
const IRREGULARES: Record<string, string> = {
  peces: "pez",
  lapices: "lapiz",
  aviones: "avion",
  balones: "balon",
  pollitos: "pollito",
  unicornios: "unicornio",
  pollo: "pollito",
  pollos: "pollito",
  panes: "pan",
  flores: "flor",
  arboles: "arbol",
  pajaros: "pajaro",
  // Los que no salen de quitar la `s`.
  lentes: "lente",
  botas: "bota",
  narices: "nariz",
  leones: "leon",
  ratones: "raton",
  tiburones: "tiburon",
  corazones: "corazon",
  camiones: "camion",
  pantalones: "pantalon",
  limones: "limon",
  aranas: "arana",
  caracoles: "caracol",
  delfines: "delfin",
  pinguinos: "pinguino",
  relojes: "reloj",
  llaves: "llave",
  cometas: "cometa",
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
