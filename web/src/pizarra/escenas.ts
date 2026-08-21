/**
 * El vocabulario de la pizarra.
 *
 * Una escena dice QUÉ mostrar, nunca DÓNDE. El tablero se encarga del layout.
 *
 * Por qué no coordenadas: la alternativa era que el tutor mandara `x, y` de cada
 * elemento. Eso obliga al modelo a hacer cálculo de maquetación —es malo en
 * eso—, produce cosas superpuestas o fuera de pantalla, y no se adapta entre un
 * celular y un portátil. Con escenas, el tutor apunta a SIGNIFICADO ("la suma
 * 56 + 38", "resaltá las unidades") y el tablero resuelve el resto. Siempre se
 * ve bien porque no hay forma de que se vea mal.
 *
 * Son cinco a propósito. Cubren casi todo lo que un profesor de primaria
 * escribe en un tablero, y una lista corta es una lista que se puede probar.
 */

/** Los anclajes a los que se puede apuntar sin saber dónde quedaron en pantalla. */
export type Ancla =
  | "unidades"
  | "decenas"
  | "centenas"
  | "llevada"
  | "resultado"
  | "primero"
  | "segundo"
  | "todo";

/** Una marca encima de la escena, como cuando el profe rodea algo con el marcador. */
export interface Anotacion {
  /** Qué parte de la escena se está señalando. */
  ancla: Ancla;
  /** Círculo alrededor · tachado encima · flecha que apunta. */
  gesto: "circulo" | "tachado" | "flecha";
  /** Sin color, usa el del tutor. `alerta` para el error, `exito` para el acierto. */
  tono?: "neutro" | "alerta" | "exito";
}

/** Cuenta en columna, como se escribe en el cuaderno. El pan de cada día. */
export interface Operacion {
  tipo: "operacion";
  a: number;
  b: number;
  op: "+" | "−" | "×" | "÷";
  /** El resultado. Si falta, la cuenta queda abierta esperando al niño. */
  resultado?: number;
  /** La que se lleva, arriba de la columna. Solo cuando se está explicando. */
  llevada?: number;
}

/** N grupos de M cosas. Es cómo se entiende la multiplicación antes del algoritmo.
 *
 * Con pocas cosas por grupo se dibujan los puntos y el niño los cuenta. Con
 * muchas se escribe el número adentro de la caja, que es lo que hace un
 * profesor de verdad: nadie cuenta 135 puntos, y 45 puntos apretados en una
 * cajita no son un dibujo, son una mancha.
 */
export interface Grupos {
  tipo: "grupos";
  grupos: number;
  porGrupo: number;
  /** "cajas", "bolsas", "platos". Solo para el rótulo. */
  nombre?: string;
}

/** Hasta acá los puntos se cuentan de un vistazo. Pasado esto, va el número. */
export const MAX_PUNTOS_CONTABLES = 12;

/** Recta numérica, con un salto opcional para mostrar el movimiento. */
export interface Recta {
  tipo: "recta";
  desde: number;
  hasta: number;
  /** Dónde poner el punto gordo. */
  marca?: number;
  /** Salta de `marca` a este otro número, con arco y todo. */
  saltaA?: number;
}

/** Una fracción vista, no escrita: la barra partida y coloreada. */
export interface Fraccion {
  tipo: "fraccion";
  numerador: number;
  denominador: number;
  /** Barra partida o torta partida. La torta ayuda con medios y cuartos. */
  forma?: "barra" | "torta";
  /**
   * La segunda fracción, al lado, para COMPARAR. Cada una de su color.
   *
   * Existe porque comparar es el uso central de las fracciones en primaria —el
   * DBA lo pide con esas palabras— y el tablero no podía. En `ses_020cfb503d5f`
   * el tutor preguntó "¿qué es más grande, un medio o un tercio?", mandó las dos
   * en llamadas separadas y la segunda borró a la primera. Le dijo al niño "¿ahí
   * ya puedes ver las dos?" con una sola en pantalla, y el niño tuvo que
   * corregirlo dos veces.
   *
   * El color separa: con las dos pintadas del mismo naranja, el niño contestó
   * "el de un tercio tiene un pedazo naranja, el de un medio también, no sé de
   * qué estamos hablando". Tenía razón.
   */
  comparar?: { numerador: number; denominador: number };
}

/** Letra, palabra o número, grande y solo. Para lectura y escritura. */
export interface Texto {
  tipo: "texto";
  contenido: string;
  /** Un renglón chico debajo, para dar contexto sin robarle protagonismo. */
  pie?: string;
}

/**
 * Dos a cuatro palabras, una debajo de otra. La lista del tablero.
 *
 * Es la sexta escena y la primera que no es de aritmética. Entró porque el
 * tablero no podía hacer lo más común de una clase de lectura: escribir tres
 * palabras y mirarlas juntas. En `ses_cdb0b7fae50f` el niño pidió "dame tres
 * palabras que empiecen por w"; el tutor mandó tres `texto` seguidos, cada uno
 * borró al anterior, y aun así dijo "ahí te LAS puse". El niño lo narró solo:
 * "ya se escribió waffle, se está escribiendo windsurf, y ahora otra". Volvió
 * a pasar en la misma sesión con vaca, vela y viento.
 *
 * La advertencia en el tool no alcanza cuando lo que el tutor quiere hacer es
 * razonable y no hay forma de hacerlo: ahí no deja de pedirlo, empieza a
 * afirmarlo. Es lo mismo que pasó con las fracciones impropias y con las 45
 * canicas — la respuesta es dar la capacidad, no repetir la prohibición.
 */
export interface Lista {
  tipo: "lista";
  palabras: string[];
}

/** Cuántas palabras entran sin que la pizarra deje de leerse de un vistazo. */
export const MAX_PALABRAS = 4;

export type Escena = Operacion | Grupos | Recta | Fraccion | Texto | Lista;

/** Lo que el tablero muestra en un momento dado. */
export interface Cuadro {
  escena: Escena;
  anotaciones?: Anotacion[];
}

/**
 * Cuánto tarda en aparecer cada trazo, en ms.
 *
 * La gracia es que se vea ESCRIBIR, no que aparezca de golpe. Muy rápido y no
 * se nota; muy lento y el niño se adelanta y deja de mirar.
 */
export const MS_ENTRE_TRAZOS = 260;
