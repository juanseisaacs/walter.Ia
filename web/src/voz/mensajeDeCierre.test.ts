/**
 * Por qué se cerró la sesión, dicho para que lo lea un niño.
 *
 * El 22/08 el tutor dejó de abrir: se habían acabado los créditos de la cuenta
 * de Gemini. El backend respondía 200 —el token se emite bien— y el niño veía
 * "Un segundito..." y volvía al botón de empezar, una y otra vez. El motivo
 * real venía en el evento de cierre del WebSocket y no lo leía nadie.
 *
 * Lo que se prueba acá no es el texto: es que un cierre con motivo NUNCA
 * termine en un mensaje que no diga nada.
 */

import { describe, expect, it } from "vitest";

import { mensajeDeCierre } from "./useTutor";

describe("cuando la sesión se cierra antes de abrirse", () => {
  it("dice que se acabó el cupo, sin código de error", () => {
    const dicho = mensajeDeCierre({
      code: 1011,
      reason: "Your prepayment credits are depleted. Please go to AI Studio",
    });
    expect(dicho).toContain("cupo");
    expect(dicho).toContain("adulto");
    expect(dicho).not.toContain("1011");
    expect(dicho).not.toContain("prepayment");
  });

  it("distingue el enlace vencido del cupo agotado", () => {
    const dicho = mensajeDeCierre({ code: 1008, reason: "token expired" });
    expect(dicho).toContain("enlace");
  });

  it("sin motivo, sigue diciendo algo que se pueda hacer", () => {
    for (const evento of [{}, { code: 1006 }, { reason: "" }, undefined]) {
      const dicho = mensajeDeCierre(evento);
      expect(dicho.length).toBeGreaterThan(20);
      expect(dicho).toMatch(/interne|intenta/i);
    }
  });

  it("nunca le echa la culpa al niño", () => {
    for (const reason of ["credits depleted", "token expired", "network error", ""]) {
      expect(mensajeDeCierre({ reason })).not.toMatch(/tu culpa|hiciste mal|error tuyo/i);
    }
  });
});
