/**
 * Tests del tablero: se mira el SVG que sale, no cómo se ve.
 *
 * No reemplazan al ojo —si un glifo quedó torcido, esto pasa igual—, pero sí
 * atrapan la clase de error que dejó al niño sin ver nada: que el trazo no
 * llegue al lienzo.
 */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import Pizarra from "./Pizarra";
import type { Cuadro } from "./escenas";

const pintar = (cuadro: Cuadro | null) =>
  renderToStaticMarkup(createElement(Pizarra, { cuadro }));

describe("la escritura a mano llega al lienzo", () => {
  it("una letra sale como trazos, no como texto impreso", () => {
    const svg = pintar({ escena: { tipo: "texto", contenido: "ñ" } });
    expect(svg).toContain("escritura-trazo");
    expect(svg).toContain("pathLength");
  });

  it("NO va envuelta en foreignObject — EL BUG DE ses_afce08f934ea", () => {
    // La primera versión metía un `<svg>` adentro de un `<foreignObject>`
    // adentro de otro `<svg>`. `foreignObject` es para HTML: con contenido SVG
    // el navegador no dibuja nada. Las otras escenas se veían bien; esta era la
    // única que pasaba por ahí.
    //
    //   nino: "muéstrame cómo se escribe la m de mamá"
    //   nino: "No vi nada. No hay ninguna pizarra."
    //
    // Los trazos YA son SVG. Envolverlos era el error.
    const svg = pintar({ escena: { tipo: "texto", contenido: "m" } });
    expect(svg).not.toContain("foreignObject");
  });

  it("cada trazo del glifo llega entero", () => {
    // La ñ son tres: el palito, el arco y la virgulilla.
    const svg = pintar({ escena: { tipo: "texto", contenido: "ñ" } });
    expect(svg.match(/escritura-trazo/g)?.length).toBe(3);
  });

  it("un carácter que no sabemos trazar cae a la letra impresa", () => {
    // Mostrarla bien y quieta le gana a no mostrarla.
    const svg = pintar({ escena: { tipo: "texto", contenido: "€" } });
    expect(svg).not.toContain("escritura-trazo");
    expect(svg).toContain("pz-grande");
  });
});

describe("las demás escenas siguen saliendo", () => {
  it("la cuenta en columna, con su llevada", () => {
    const svg = pintar({
      escena: { tipo: "operacion", a: 56, b: 38, op: "+", llevada: 1 },
    });
    expect(svg).toContain("pz-llevada");
    expect(svg).toContain("pz-digito");
  });

  it("los grupos con puntos cuando se pueden contar", () => {
    const svg = pintar({ escena: { tipo: "grupos", grupos: 3, porGrupo: 4 } });
    expect(svg.match(/pz-punto/g)?.length).toBe(12);
  });

  it("los grupos con el número adentro cuando son demasiados", () => {
    const svg = pintar({ escena: { tipo: "grupos", grupos: 3, porGrupo: 45 } });
    expect(svg).toContain("pz-en-caja");
    expect(svg).not.toContain("pz-punto");
  });

  it("sin cuadro no hay tablero", () => {
    expect(pintar(null)).toBe("");
  });
});

describe("la fracción impropia se dibuja con varios enteros", () => {
  it("5/3 son dos pasteles: uno lleno y dos tercios del otro", () => {
    const svg = pintar({ escena: { tipo: "fraccion", numerador: 5, denominador: 3, forma: "torta" } });
    // 2 enteros × 3 porciones = 6 trozos; 5 pintados y 1 vacío.
    expect(svg.match(/pz-porcion-llena/g)?.length).toBe(5);
    expect(svg.match(/class="pz-porcion"/g)?.length).toBe(1);
  });

  it("3/4 sigue siendo un solo pastel", () => {
    const svg = pintar({ escena: { tipo: "fraccion", numerador: 3, denominador: 4, forma: "torta" } });
    expect(svg.match(/pz-porcion-llena/g)?.length).toBe(3);
    expect(svg.match(/class="pz-porcion"/g)?.length).toBe(1);
  });
});

describe("los montones desiguales llegan al lienzo", () => {
  it("dibuja una caja por cantidad, con lo suyo adentro", () => {
    const svg = pintar({
      escena: { tipo: "grupos", grupos: 3, porGrupo: 6, cantidades: [5, 3, 6], nombre: "pollitos" },
    });
    // Tres cajas...
    expect(svg.match(/class="pz-caja"/g)?.length).toBe(3);
    // ...y catorce pollitos, que es 5 + 3 + 6. Si el render usara `porGrupo`
    // saldrían dieciocho, que es exactamente lo que el niño vio y reclamó.
    expect(svg.match(/🐤/g)?.length).toBe(14);
  });

  it("el rótulo dice la cuenta, no 'N grupos de M'", () => {
    const svg = pintar({
      escena: { tipo: "grupos", grupos: 3, porGrupo: 6, cantidades: [5, 3, 6], nombre: "pollitos" },
    });
    expect(svg).toContain("5 + 3 + 6 pollitos");
  });

  it("cada caja decide sola si dibuja o escribe el número", () => {
    // 4 se cuenta de un vistazo; 40 es una mancha. Mezclarlos tiene que poder.
    const svg = pintar({ escena: { tipo: "grupos", grupos: 2, porGrupo: 40, cantidades: [4, 40] } });
    expect(svg.match(/class="pz-punto"/g)?.length).toBe(4);
    expect(svg).toContain(">40<");
  });
});

describe("la respuesta queda encerrada", () => {
  /* Lo pidió Juan como regla, después de pedir tres veces lo mismo en una sola
     cuenta (`ses_f6cb91f4e15c`):

       nino: «Pero deja el 31, no lo has puesto en el tablero.»
       nino: «Déjalo el 31 e incluye todavía el uno que habías llevado, como
              deja la operación completa.»
       nino: «Eso así debería ser siempre, como que se tenga el proceso y que
              uno sepa de dónde salió, e incluso puedes encerrar el 31.» */

  it("encierra el resultado sin que nadie se lo pida", () => {
    const svg = pintar({ escena: { tipo: "operacion", a: 16, b: 15, op: "+", resultado: 31 } });
    expect(svg).toContain("pz-respuesta");
  });

  it("no encierra nada mientras la cuenta está abierta", () => {
    // Sin resultado el niño todavía la está resolviendo: encerrar el vacío
    // sería marcarle una respuesta que no dio.
    const svg = pintar({ escena: { tipo: "operacion", a: 16, b: 15, op: "+" } });
    expect(svg).not.toContain("pz-respuesta");
  });

  it("el proceso completo cabe junto: llevada, resultado y el óvalo", () => {
    const svg = pintar({
      escena: { tipo: "operacion", a: 16, b: 15, op: "+", resultado: 31, llevada: 1 },
    });
    expect(svg).toContain("pz-llevada");
    expect(svg).toContain("pz-respuesta");
  });
});

describe("los montones grandes se pueden contar", () => {
  it("dibuja 16 y 15 en vez de escribir el número", () => {
    // «Me sale en dos cuadritos, uno que dice 16 y otro 15» — con el tope en 12
    // pedir ver algo devolvía el número escrito, que es lo contrario de ver.
    const svg = pintar({
      escena: { tipo: "grupos", grupos: 2, porGrupo: 16, cantidades: [16, 15], nombre: "unicornios" },
    });
    expect(svg.match(/🦄/g)?.length).toBe(31);
    expect(svg).not.toContain("pz-en-caja");
  });
});
