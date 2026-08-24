/**
 * Del nombre que dice el tutor al dibujito que ve el niño.
 *
 * Lo que se prueba no es el mapa —una lista de palabras no necesita test— sino
 * que la BÚSQUEDA aguante cómo escribe el tutor de verdad: en frases, en
 * plural, con tildes, y a veces nombrando algo que no sabemos dibujar.
 */

import { describe, expect, it } from "vitest";

import { dibujoDe } from "./emojis";

describe("lo que Juan pidió", () => {
  it("dibuja las gallinas y los patos que pidió ver", () => {
    // Sesión ses_817fc1fce8fc: "me gustaría poder ver las gallinas y los patos".
    // El tutor le contestó que solo podía poner grupitos y números.
    expect(dibujoDe("gallinas")).toBe("🐔");
    expect(dibujoDe("patos")).toBe("🦆");
  });

  it("dibuja las galletas que el niño no supo reconocer", () => {
    // "¿los puntos naranjas y verdes son las galletas?" — tuvo que preguntar
    // qué estaba mirando.
    expect(dibujoDe("galletas")).toBe("🍪");
  });
});

describe("cómo escribe el tutor de verdad", () => {
  it("encuentra la cosa dentro de una frase", () => {
    expect(dibujoDe("bolsas de manzanas")).toBe("🍎");
    expect(dibujoDe("cajas de lápices")).toBe("✏️");
  });

  it("le da igual el plural", () => {
    expect(dibujoDe("carro")).toBe(dibujoDe("carros"));
    expect(dibujoDe("dulces")).toBe("🍬");
  });

  it("aguanta los plurales que no salen de quitar una s", () => {
    expect(dibujoDe("peces")).toBe("🐟");
    expect(dibujoDe("lápices")).toBe("✏️");
    expect(dibujoDe("aviones")).toBe("✈️");
  });

  it("le da igual la tilde", () => {
    expect(dibujoDe("plátanos")).toBe(dibujoDe("platanos"));
    expect(dibujoDe("aviones")).toBe(dibujoDe("aviónes"));
  });

  it("le da igual la mayúscula y la puntuación", () => {
    expect(dibujoDe("Manzanas,")).toBe("🍎");
  });
});

describe("cuando no sabemos dibujarlo", () => {
  it("devuelve null en vez de inventar un dibujito", () => {
    // Un emoji parecido-pero-no es peor que un punto: el niño está CONTANDO, y
    // un dibujo que no es lo que el tutor nombró lo manda a otra pregunta.
    expect(dibujoDe("cosas")).toBeNull();
    expect(dibujoDe("elementos")).toBeNull();
  });

  it("sin nombre tampoco revienta", () => {
    expect(dibujoDe(undefined)).toBeNull();
    expect(dibujoDe("")).toBeNull();
    expect(dibujoDe("   ")).toBeNull();
  });

  it("una palabra rara no tumba la búsqueda de la que sí está", () => {
    expect(dibujoDe("xyz manzanas")).toBe("🍎");
  });
});

describe("lo que Juan pidió y no estaba", () => {
  /* `ses_398803222958` (23/08), dos tareas seguidas:

       nino:  «Son 10 tenis más ocho tenis.»
       tutor: «imagen de tenis no tengo, pero te puse unos puntitos»
       nino:  «¿Y los emojis dónde los tienes?»
       nino:  «que quede registrado que deberías tener TODOS los emojis
               disponibles como imagen para este tipo de sumas»

     Todos no se puede —son miles—, pero el criterio es suyo y es el correcto:
     que un niño no tenga que conformarse con puntos por nombrar algo normal. */

  it("los tenis y las gafas de esa sesión", () => {
    expect(dibujoDe("tenis")).toBe("👟");
    expect(dibujoDe("gafas")).toBe("👓");
  });

  it("entiende la frase como la dice el tutor", () => {
    expect(dibujoDe("10 tenis")).toBe("👟");
    expect(dibujoDe("gafas de sol")).toBe("👓");
    expect(dibujoDe("grupos de leones")).toBe("🦁");
  });

  it("los plurales que no salen de quitar una s", () => {
    expect(dibujoDe("ratones")).toBe("🐭");
    expect(dibujoDe("corazones")).toBe("❤️");
    expect(dibujoDe("camiones")).toBe("🚚");
  });

  it("lo que no sabemos dibujar sigue cayendo al punto, sin romper nada", () => {
    expect(dibujoDe("wombats")).toBeNull();
  });
});
