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
