/**
 * Traduce lo que manda el tutor a una escena de la pizarra.
 *
 * Es la frontera, y por eso desconfía: los argumentos los escribe un modelo, y
 * un modelo se equivoca de tipo, se olvida un campo o manda un número absurdo.
 * Lo que no se entiende devuelve `null` y **no se dibuja nada** — un tablero
 * vacío es mucho mejor que uno con una cuenta rota adelante de un niño.
 */

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
      return {
        tipo: "fraccion",
        numerador,
        denominador,
        // La torta se lee mejor con pocas partes; con muchas se vuelve un
        // abanico ilegible y la barra gana.
        forma: denominador <= 6 ? "torta" : "barra",
      };
    }

    case "texto": {
      const contenido = typeof args.contenido === "string" ? args.contenido.trim() : "";
      // Un párrafo en la pizarra no se lee: para eso está la voz.
      if (!contenido || contenido.length > 24) return null;
      return { tipo: "texto", contenido };
    }

    default:
      return null;
  }
}
