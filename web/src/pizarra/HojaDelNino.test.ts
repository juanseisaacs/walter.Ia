/**
 * La hoja donde el niño traza, y lo que tiene que poder VER mientras traza.
 *
 * Sale de `ses_445f4c33db41` (22/08):
 *
 *   tutor: «Mira, ahí te la dibujé en la pizarra, es como una eme al revés.
 *           ¿Te animas a intentar trazarla con tu dedo?»
 *   tutor: «De una, ahí te abrí la hojita.»          <- y la W desapareció
 *   nino:  «A ver, okay, sí, pero NO ME SALE EL TABLERO.»
 *
 * La hoja y el tablero se excluían en pantalla, así que abrir la hoja borraba
 * justo lo que el niño iba a copiar. Y el tutor no puede ver la pantalla: le
 * contestó "déjame lo mando otra vez" y volvió a pasar lo mismo.
 */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import HojaDelNino from "./HojaDelNino";
import type { Cuadro } from "./escenas";

const pintar = (referencia?: Cuadro | null) =>
  renderToStaticMarkup(
    createElement(HojaDelNino, {
      consigna: "Dibújame la W",
      referencia,
      alEnviar: () => {},
    }),
  );

describe("el modelo a copiar", () => {
  it("sigue en pantalla cuando se abre la hoja", () => {
    const svg = pintar({ escena: { tipo: "texto", contenido: "w" } });
    expect(svg).toContain("hoja-modelo");
    // Y es el trazo de verdad, el mismo de la pizarra: copiar una W impresa no
    // enseña a escribirla.
    expect(svg).toContain("escritura-trazo");
  });

  it("no ocupa el lugar del lienzo: la hoja sigue siendo la hoja", () => {
    const svg = pintar({ escena: { tipo: "texto", contenido: "w" } });
    expect(svg).toContain("hoja-lienzo");
    expect(svg).toContain("Listo, mira");
  });

  it("sin nada que copiar, la hoja queda exactamente como antes", () => {
    // El cambio es aditivo: si el tutor abre la hoja sin haber mostrado nada,
    // no aparece una banda vacía ocupando la pantalla del niño.
    expect(pintar(null)).not.toContain("hoja-modelo");
    expect(pintar()).not.toContain("hoja-modelo");
  });
});
