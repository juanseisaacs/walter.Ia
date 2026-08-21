/**
 * Traduce lo que manda el tutor a una escena de la pizarra.
 *
 * Es la frontera, y por eso desconfía: los argumentos los escribe un modelo, y
 * un modelo se equivoca de tipo, se olvida un campo o manda un número absurdo.
 * Lo que no se entiende devuelve `null` y **no se dibuja nada** — un tablero
 * vacío es mucho mejor que uno con una cuenta rota adelante de un niño.
 */

import { MAX_PALABRAS } from "./escenas";
import type { Anotacion, Cuadro, Escena } from "./escenas";

/** Cuántas cajas caben en el tablero sin volverse ilegibles. */
const MAX_GRUPOS = 10;

/** Cuántas cosas por grupo, como mucho.
 *
 * Alto a propósito. Estaba en 12 y rechazaba en silencio pedidos perfectamente
 * razonables: en `ses_697a02991605` el tutor pidió "3 cajitas con 45 canicas",
 * el validador devolvió `null`, no se dibujó nada — y el tutor igual le dijo al
 * niño "ahí en la pizarra te estoy mostrando". El niño tuvo que contestarle
 * "no veo ninguna pizarra".
 *
 * El tope real no era de validación sino de DIBUJO: 45 puntos apretados en una
 * cajita no son un dibujo. Eso ahora lo resuelve la escena escribiendo el
 * número adentro de la caja (`MAX_PUNTOS_CONTABLES`), que es lo que hace un
 * profesor. Acá solo queda el límite de lo que un niño de primaria multiplica. */
const MAX_POR_GRUPO = 999;

/** Partes en que se corta CADA entero. Más de doce no se distinguen ni en barra. */
const MAX_PARTES = 12;

/** Cuántos enteros se pueden dibujar al lado, para las fracciones impropias.

Cuatro pasteles ya llenan el tablero; más se vuelven ilegibles. */
const MAX_ENTEROS = 4;
/** Una recta con doscientas marcas es una línea negra. */
const MAX_PUNTOS_RECTA = 40;

/** Más largo que esto no es una palabra suelta: es una frase, y para eso está la voz. */
const MAX_LARGO_PALABRA = 16;

function num(v: unknown): number | undefined {
  const n = typeof v === "string" ? Number(v) : v;
  return typeof n === "number" && Number.isFinite(n) ? n : undefined;
}

function entero(v: unknown, min: number, max: number): number | undefined {
  const n = num(v);
  if (n === undefined) return undefined;
  const r = Math.round(n);
  return r >= min && r <= max ? r : undefined;
}

export function aCuadro(args: any): Cuadro | null {
  const escena = aEscena(args);
  if (!escena) return null;

  const anotaciones: Anotacion[] = [];
  // Solo tienen sentido sobre la cuenta en columna: en las otras escenas no hay
  // "unidades" ni "decenas" a las que apuntar.
  if (escena.tipo === "operacion") {
    if (typeof args?.senalar === "string") {
      anotaciones.push({ ancla: args.senalar, gesto: "circulo" });
    }
    if (typeof args?.tachar === "string") {
      anotaciones.push({ ancla: args.tachar, gesto: "tachado", tono: "alerta" });
    }
  }

  return anotaciones.length ? { escena, anotaciones } : { escena };
}

function aEscena(args: any): Escena | null {
  switch (args?.tipo) {
    case "operacion": {
      const a = num(args.a);
      const b = num(args.b);
      const op = args.op;
      // Sin los dos números y el signo no hay cuenta que escribir.
      if (a === undefined || b === undefined) return null;
      if (!["+", "−", "×", "÷"].includes(op)) return null;
      return {
        tipo: "operacion",
        a,
        b,
        op,
        resultado: num(args.resultado),
        llevada: num(args.llevada),
      };
    }

    case "grupos": {
      const grupos = entero(args.grupos, 1, MAX_GRUPOS);
      const porGrupo = entero(args.por_grupo ?? args.porGrupo, 1, MAX_POR_GRUPO);
      if (grupos === undefined || porGrupo === undefined) return null;
      return {
        tipo: "grupos",
        grupos,
        porGrupo,
        nombre: typeof args.nombre === "string" ? args.nombre : undefined,
      };
    }

    case "recta": {
      const desde = num(args.desde);
      const hasta = num(args.hasta);
      if (desde === undefined || hasta === undefined || hasta <= desde) return null;
      if (hasta - desde > MAX_PUNTOS_RECTA) return null;
      return {
        tipo: "recta",
        desde: Math.round(desde),
        hasta: Math.round(hasta),
        marca: num(args.marca),
        saltaA: num(args.salta_a ?? args.saltaA),
      };
    }

    case "fraccion": {
      const denominador = entero(args.denominador, 2, MAX_PARTES);
      // El numerador PUEDE pasarse del denominador: 5/3 es una fracción
      // impropia perfectamente válida, y es justo donde el dibujo más sirve —
      // "más de un entero" es abstracto hasta que se ve.
      //
      // Estaba topado en `numerador <= denominador` y devolvía null: en
      // `ses_4b6f870fcf5f` el niño pidió ver 5/3, el tutor se lo explicó bien
      // de palabra ("dos pasteles, cinco pedazos") y después no pudo dibujar
      // lo que acababa de decir. "No veo nada. No hay ningún dibujo."
      const numerador = entero(args.numerador, 0, MAX_PARTES * MAX_ENTEROS);
      if (denominador === undefined || numerador === undefined) return null;
      if (numerador > denominador * MAX_ENTEROS) return null;

      // La segunda, para comparar. Acá SÍ se exige propia (numerador <=
      // denominador): dos fracciones impropias lado a lado son cuatro o seis
      // tortas y no se compara nada. Si viene mal, se cae la comparación —
      // nunca el dibujo entero: mostrar una fracción es mejor que no mostrar.
      const c = args.comparar_con ?? args.comparar;
      const cd = entero(c?.denominador, 2, MAX_PARTES);
      const cn = entero(c?.numerador, 0, MAX_PARTES);
      const comparar =
        cd !== undefined && cn !== undefined && cn <= cd && numerador <= denominador
          ? { numerador: cn, denominador: cd }
          : undefined;

      return {
        tipo: "fraccion",
        numerador,
        denominador,
        // La torta se lee mejor con pocas partes; con muchas se vuelve un
        // abanico ilegible y la barra gana.
        forma: denominador <= 6 ? "torta" : "barra",
        comparar,
      };
    }

    case "texto": {
      const contenido = typeof args.contenido === "string" ? args.contenido.trim() : "";
      // Un párrafo en la pizarra no se lee: para eso está la voz.
      if (!contenido || contenido.length > 24) return null;
      return { tipo: "texto", contenido };
    }

    case "lista": {
      const crudas = Array.isArray(args.palabras)
        ? args.palabras
        : typeof args.palabras === "string"
          ? // El modelo a veces manda "vaca, vela, viento" en un solo string.
            // Es lo que quiso decir: se entiende en vez de devolver null.
            args.palabras.split(/[,;·]/)
          : [];
      const palabras = crudas
        .map((w: unknown) => (typeof w === "string" ? w.trim() : ""))
        .filter((w: string) => w.length > 0 && w.length <= MAX_LARGO_PALABRA)
        .slice(0, MAX_PALABRAS);
      // Una sola palabra no es una lista: es `texto`, que la escribe a mano y
      // se ve mucho mejor. Se degrada en vez de rechazar.
      if (palabras.length === 0) return null;
      if (palabras.length === 1) return { tipo: "texto", contenido: palabras[0] };
      return { tipo: "lista", palabras };
    }

    default:
      return null;
  }
}

/**
 * Lo que quedó en pantalla, en palabras, para devolvérselo al tutor.
 *
 * El tool devolvía `{ mostrado: true }` y nada más. Con eso el tutor no tenía
 * cómo saber qué se ve, y afirmaba de más: mandó un medio, después un tercio, y
 * preguntó "¿ahí ya puedes ver las dos?" — la segunda había borrado a la
 * primera. Tampoco sabía los colores, así que dijo "el pedazo naranja" cuando
 * los dos dibujos tenían naranja.
 *
 * No se le pide al modelo que adivine el estado del tablero: se lo decimos.
 */
export function describir(cuadro: Cuadro): string {
  const e = cuadro.escena;
  switch (e.tipo) {
    case "operacion":
      return `la cuenta ${e.a} ${e.op} ${e.b}${
        e.resultado === undefined ? " sin resultado, abierta para él" : ` = ${e.resultado}`
      }, escrita en columna con el signo en naranja`;
    case "grupos":
      return `${e.grupos} ${e.nombre ?? "grupos"} con ${e.porGrupo} en cada uno${
        e.porGrupo > 12 ? " (el número escrito adentro, no puntos)" : " (puntos para contar)"
      }`;
    case "recta":
      return `una recta del ${e.desde} al ${e.hasta}${
        e.marca !== undefined ? `, marcado el ${e.marca}` : ""
      }${e.saltaA !== undefined ? ` y un salto hasta el ${e.saltaA}` : ""}`;
    case "fraccion": {
      const uno = `${e.numerador}/${e.denominador}`;
      if (e.comparar) {
        return `${uno} en NARANJA a la izquierda y ${e.comparar.numerador}/${e.comparar.denominador} en AZUL a la derecha, del mismo tamaño para poder compararlas`;
      }
      return `${uno}: ${e.forma === "torta" ? "una torta" : "una barra"} partida en ${
        e.denominador
      } con ${e.numerador} ${e.numerador === 1 ? "parte pintada" : "partes pintadas"} de naranja`;
    }
    case "texto":
      return `«${e.contenido}» escrito grande`;
    case "lista":
      return `${e.palabras.length} palabras, una debajo de otra y cada una de un color: ${e.palabras
        .map((p) => `«${p}»`)
        .join(", ")}`;
  }
}
