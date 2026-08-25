/**
 * Traduce lo que manda el tutor a una escena de la pizarra.
 *
 * Es la frontera, y por eso desconfía: los argumentos los escribe un modelo, y
 * un modelo se equivoca de tipo, se olvida un campo o manda un número absurdo.
 * Lo que no se entiende devuelve `null` y **no se dibuja nada** — un tablero
 * vacío es mucho mejor que uno con una cuenta rota adelante de un niño.
 */

import { dibujoDe } from "./emojis";
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
      const nombre = typeof args.nombre === "string" ? args.nombre : undefined;

      // EL `tipo` ES LA ETIQUETA; LOS CAMPOS SON LA INTENCIÓN.
      //
      // Tercera vez que el mismo validador rechaza un pedido que se entiende
      // perfecto —`MAX_POR_GRUPO` en 12, el montón suelto, y ahora esto—, así
      // que acá el arreglo deja de ser puntual: cuando la etiqueta y los campos
      // se contradicen, **mandan los campos**.
      //
      // `ses_610e057cfd91`, tal cual llegó:
      //     {"tipo":"grupos","nombre":"pollitos","op":"+","a":7,"b":5}
      //
      // El modelo mezcló familias: pidió `grupos` con los campos de
      // `operacion`. Quiso decir "siete pollitos y cinco pollitos", que es
      // exactamente `cantidades: [7, 5]`. El validador devolvió null, el
      // tablero quedó vacío, y el niño tuvo que decir «no veo la pizarra» y
      // después «Walter, reacciona».
      //
      // Dos montones nombrados NO son una cuenta en columna: si el modelo puso
      // `nombre`, quiere dibujitos para contar, no dígitos.
      const dosMontones =
        args.cantidades === undefined && args.a !== undefined && args.b !== undefined
          ? [args.a, args.b]
          : null;

      // Montones DESIGUALES: "5 + 3 + 6 pollitos". Es la suma dibujada, y hasta
      // el 23/08 no había forma de pedirla — ver `Grupos.cantidades`.
      //
      // El modelo manda a veces "5, 3, 6" en un string, igual que con las
      // palabras de `lista`: se entiende en vez de devolver null.
      const crudas = Array.isArray(args.cantidades)
        ? args.cantidades
        : typeof args.cantidades === "string"
          ? args.cantidades.split(/[,;+·]/)
          : dosMontones;
      if (crudas) {
        const cantidades = crudas
          .map((c: unknown) => entero(c, 0, MAX_POR_GRUPO))
          .filter((c: number | undefined): c is number => c !== undefined)
          .slice(0, MAX_GRUPOS);
        // Con una sola caja no hay suma que ver, y con ninguna no hay dibujo.
        if (cantidades.length >= 2) {
          return {
            tipo: "grupos",
            grupos: cantidades.length,
            porGrupo: Math.max(...cantidades),
            cantidades,
            nombre,
          };
        }
      }

      // UN SOLO MONTÓN: `por_grupo` sin `grupos`.
      //
      // "Imagínate que tienes 9 galletas" no es un problema de grupos iguales:
      // es un montón y ya. El modelo lo manda como `por_grupo: 9` sin `grupos`,
      // que es exactamente lo que quiso decir, y hasta hoy eso devolvía `null`.
      //
      // Pasó en `ses_0a6036dedf55`: el niño pidió el dibujo —«sí, mejor
      // dibújalo»—, el tablero quedó vacío, y el silencio que siguió lo leyó
      // como que el tutor se había colgado: «¿me escuchas? estás como trabado».
      //
      // Es el mismo agujero que tenía `MAX_POR_GRUPO` en 12 (ver arriba): el
      // validador rechazando en silencio un pedido que se entiende perfecto. El
      // esquema nunca dijo que `grupos` fuera obligatorio, y no tiene por qué
      // serlo — un montón es un grupo.
      // AUSENTE no es lo mismo que INVÁLIDO, y esta distinción la agarró el
      // test de "cien grupos": con `grupos ?? 1` a secas, un pedido de 100
      // grupos —que se rechaza porque no cabe en el tablero— se convertía en
      // un montón de uno y el niño veía algo que nadie pidió. Solo se asume el
      // montón cuando el campo NO VINO.
      const pidioGrupos = args.grupos !== undefined && args.grupos !== null;
      const grupos = pidioGrupos ? entero(args.grupos, 1, MAX_GRUPOS) : 1;
      const porGrupo = entero(args.por_grupo ?? args.porGrupo, 1, MAX_POR_GRUPO);
      // Al revés NO se asume: `grupos: 3` sin `por_grupo` es "tres cajas de no
      // se sabe cuánto", y ahí no hay dibujo que adivinar.
      if (grupos === undefined || porGrupo === undefined) return null;
      return { tipo: "grupos", grupos, porGrupo, nombre };
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
    case "grupos": {
      // CON QUÉ está dibujado, no solo cuántos. Desde que hay emojis, el niño
      // puede estar viendo gallinas de verdad — y si el tutor cree que son
      // puntos, vuelve exactamente el problema que los emojis venían a
      // resolver: el niño preguntando «¿los puntos naranjas son las galletas?».
      // Lo que no se le dice al tutor, se lo inventa.
      const dibujo = dibujoDe(e.nombre);
      const cuantos = e.cantidades?.length ? e.cantidades : [e.porGrupo];
      const con =
        Math.max(...cuantos) > 12
          ? " (con el número escrito adentro donde no caben los dibujos)"
          : dibujo
            ? ` (dibujados como ${dibujo}, para contarlos)`
            : " (puntos para contar)";
      // Con cantidades distintas se le dice LA CUENTA, no "N grupos de M": el
      // tutor tiene que poder hablar de lo que el niño está viendo, y lo que ve
      // son tres montones diferentes.
      if (e.cantidades?.length) {
        return `${e.cantidades.join(" + ")} ${e.nombre ?? "cosas"} en montones separados${con}`;
      }
      // Un montón solo no son "1 grupos con 9 en cada uno". Se lo decimos como
      // lo ve el niño —nueve galletas juntas—, porque de esto sale la frase con
      // la que el tutor le habla.
      if (e.grupos === 1) {
        return `${e.porGrupo} ${e.nombre ?? "cosas"} en un montón${con}`;
      }
      return `${e.grupos} ${e.nombre ?? "grupos"} con ${e.porGrupo} en cada uno${con}`;
    }
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
      // "de imprenta" no es un adorno: es lo único que impide la mentira.
      //
      // `ses_f6cb91f4e15c`: el niño pidió la W en cursiva y el tutor contestó
      // «ahí te la puse en la pizarra en letra cursiva, ¿sí ves cómo es más
      // curvita?». No había ninguna cursiva. Después le pidió "Walter" en
      // cursiva y volvió a decir que sí. El niño tuvo que dictarnos el bug:
      // «voy a dejar como reporte que solo escribes en letra despegada».
      //
      // El tutor no ve el tablero: sabe lo que le decimos que quedó. Si no le
      // decimos con qué letra escribe, la inventa — y una vez inventada la
      // sostiene con detalles («más curvita») que el niño no ve por ningún lado.
      return `«${e.contenido}» escrito grande, en letra de imprenta suelta (la pizarra NO sabe cursiva)`;
    case "lista":
      return `${e.palabras.length} palabras, una debajo de otra y cada una de un color: ${e.palabras
        .map((p) => `«${p}»`)
        .join(", ")}`;
  }
}
