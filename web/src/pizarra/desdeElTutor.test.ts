/**
 * Tests de la frontera con el modelo.
 *
 * Lo que llega acá lo escribe un modelo hablando en tiempo real: se equivoca de
 * tipo, se olvida campos y manda números absurdos. Lo que importa no es que
 * entienda todo, es que **lo que no entiende no se dibuje** — un tablero vacío
 * es mucho mejor que una cuenta rota adelante de un niño.
 */

import { describe, expect, it } from "vitest";

import { aCuadro } from "./desdeElTutor";

describe("lo que el tutor pide bien", () => {
  it("arma la cuenta en columna con su llevada", () => {
    const c = aCuadro({ tipo: "operacion", a: 56, b: 38, op: "+", llevada: 1 });
    expect(c?.escena).toMatchObject({ tipo: "operacion", a: 56, b: 38, op: "+", llevada: 1 });
  });

  it("deja la cuenta abierta si no mandó resultado", () => {
    const c = aCuadro({ tipo: "operacion", a: 7, b: 5, op: "×" });
    expect((c?.escena as any).resultado).toBeUndefined();
  });

  it("acepta los números que vienen como texto", () => {
    // Pasa: el modelo manda "56" en vez de 56 según el humor del muestreo.
    const c = aCuadro({ tipo: "operacion", a: "56", b: "38", op: "+" });
    expect((c?.escena as any).a).toBe(56);
  });

  it("traduce por_grupo, que es como se llama el campo del lado del modelo", () => {
    const c = aCuadro({ tipo: "grupos", grupos: 5, por_grupo: 4, nombre: "cajas" });
    expect(c?.escena).toMatchObject({ tipo: "grupos", grupos: 5, porGrupo: 4 });
  });

  it("elige torta con pocas partes y barra con muchas", () => {
    // La torta se lee mejor partida en pocas; con muchas es un abanico ilegible.
    expect((aCuadro({ tipo: "fraccion", numerador: 1, denominador: 2 })?.escena as any).forma)
      .toBe("torta");
    expect((aCuadro({ tipo: "fraccion", numerador: 3, denominador: 10 })?.escena as any).forma)
      .toBe("barra");
  });

  it("convierte señalar y tachar en marcas del profe", () => {
    const c = aCuadro({
      tipo: "operacion", a: 56, b: 38, op: "+", resultado: 84,
      senalar: "decenas", tachar: "resultado",
    });
    expect(c?.anotaciones).toEqual([
      { ancla: "decenas", gesto: "circulo" },
      { ancla: "resultado", gesto: "tachado", tono: "alerta" },
    ]);
  });
});

describe("grupos grandes: se dibujan igual, con el número adentro", () => {
  it("3 cajitas con 45 canicas — EL CASO QUE FALLÓ (ses_697a02991605)", () => {
    // El tope estaba en 12 y esto devolvía null: no se dibujaba nada, y el
    // tutor igual le decía al niño "ahí en la pizarra te estoy mostrando".
    // El niño tuvo que contestarle "no veo ninguna pizarra".
    //
    // El límite real no era de validación sino de DIBUJO: 45 puntos apretados
    // en una cajita no son un dibujo. Lo resuelve la escena escribiendo el
    // número adentro de la caja, que es lo que hace un profesor.
    const c = aCuadro({ tipo: "grupos", grupos: 3, por_grupo: 45, nombre: "cajitas" });
    expect(c?.escena).toMatchObject({ tipo: "grupos", grupos: 3, porGrupo: 45 });
  });

  it("sigue rechazando lo que de verdad no se puede dibujar", () => {
    expect(aCuadro({ tipo: "grupos", grupos: 3, por_grupo: 5000 })).toBeNull();
    expect(aCuadro({ tipo: "grupos", grupos: 3, por_grupo: 0 })).toBeNull();
  });
});

describe("lo que el tutor pide mal: no se dibuja nada", () => {
  it("una cuenta sin números", () => {
    expect(aCuadro({ tipo: "operacion", op: "+" })).toBeNull();
  });

  it("un signo que no existe", () => {
    expect(aCuadro({ tipo: "operacion", a: 2, b: 3, op: "elevado a" })).toBeNull();
  });

  it("una fracción con más partes pintadas que partes", () => {
    expect(aCuadro({ tipo: "fraccion", numerador: 7, denominador: 4 })).toBeNull();
  });

  it("cien grupos, que no caben en el tablero", () => {
    expect(aCuadro({ tipo: "grupos", grupos: 100, por_grupo: 3 })).toBeNull();
  });

  it("una recta del 0 al 1000, que sería una línea negra", () => {
    expect(aCuadro({ tipo: "recta", desde: 0, hasta: 1000 })).toBeNull();
  });

  it("una recta que termina antes de empezar", () => {
    expect(aCuadro({ tipo: "recta", desde: 20, hasta: 5 })).toBeNull();
  });

  it("un párrafo entero: para eso está la voz", () => {
    expect(aCuadro({ tipo: "texto", contenido: "a".repeat(80) })).toBeNull();
  });

  it("un tipo de escena inventado", () => {
    expect(aCuadro({ tipo: "grafico_de_barras_3d" })).toBeNull();
  });

  it("nada, null, o basura", () => {
    expect(aCuadro(null)).toBeNull();
    expect(aCuadro({})).toBeNull();
    expect(aCuadro({ tipo: "operacion", a: NaN, b: 2, op: "+" })).toBeNull();
  });

  it("no pone marcas donde no hay unidades ni decenas que señalar", () => {
    // `senalar` solo tiene sentido sobre la cuenta en columna.
    const c = aCuadro({ tipo: "texto", contenido: "ñ", senalar: "decenas" });
    expect(c?.anotaciones).toBeUndefined();
  });
});
