/**
 * Tests de la frontera con el modelo.
 *
 * Lo que llega acá lo escribe un modelo hablando en tiempo real: se equivoca de
 * tipo, se olvida campos y manda números absurdos. Lo que importa no es que
 * entienda todo, es que **lo que no entiende no se dibuje** — un tablero vacío
 * es mucho mejor que una cuenta rota adelante de un niño.
 */

import { describe, expect, it } from "vitest";

import { aCuadro, describir } from "./desdeElTutor";
import type { Cuadro } from "./escenas";

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

describe("fracciones impropias: 5/3 se dibuja, no se rechaza", () => {
  it("5/3 — EL CASO QUE FALLÓ (ses_4b6f870fcf5f)", () => {
    // El validador topaba en `numerador <= denominador` y devolvía null. El
    // niño pidió ver 5/3, el tutor se lo explicó bien de palabra —"dos
    // pasteles, cinco pedazos"— y después no pudo dibujar lo que acababa de
    // decir: "No veo nada. No hay ningún dibujo."
    //
    // Y es justo donde el dibujo más sirve: "más de un entero" es abstracto
    // hasta que se ve.
    const c = aCuadro({ tipo: "fraccion", numerador: 5, denominador: 3 });
    expect(c?.escena).toMatchObject({ tipo: "fraccion", numerador: 5, denominador: 3 });
  });

  it("un entero exacto también: 6/3", () => {
    expect(aCuadro({ tipo: "fraccion", numerador: 6, denominador: 3 })).not.toBeNull();
  });

  it("pero no veinte pasteles al lado", () => {
    expect(aCuadro({ tipo: "fraccion", numerador: 60, denominador: 3 })).toBeNull();
  });
});

describe("comparar dos fracciones: el caso de ses_020cfb503d5f", () => {
  it("un medio y un tercio, en UNA llamada", () => {
    // El tutor preguntó "¿qué es más grande, un medio o un tercio?" y las mandó
    // en dos llamadas. La segunda borró a la primera y él igual dijo "¿ahí ya
    // puedes ver las dos?". El niño lo corrigió dos veces.
    const c = aCuadro({
      tipo: "fraccion",
      numerador: 1,
      denominador: 2,
      comparar_con: { numerador: 1, denominador: 3 },
    });
    expect(c?.escena).toMatchObject({
      tipo: "fraccion",
      numerador: 1,
      denominador: 2,
      comparar: { numerador: 1, denominador: 3 },
    });
  });

  it("una comparación rota NO tumba el dibujo: se muestra la primera sola", () => {
    const c = aCuadro({
      tipo: "fraccion",
      numerador: 1,
      denominador: 2,
      comparar_con: { numerador: 99 },
    });
    expect(c?.escena).toMatchObject({ tipo: "fraccion", numerador: 1, denominador: 2 });
    expect((c?.escena as any).comparar).toBeUndefined();
  });

  it("no se comparan impropias: seis tortas no comparan nada", () => {
    const c = aCuadro({
      tipo: "fraccion",
      numerador: 5,
      denominador: 3,
      comparar_con: { numerador: 1, denominador: 2 },
    });
    expect((c?.escena as any).comparar).toBeUndefined();
  });
});

describe("describir(): lo que el tutor puede afirmar sin mentir", () => {
  it("nombra el color de cada fracción cuando hay dos", () => {
    const c = aCuadro({
      tipo: "fraccion",
      numerador: 1,
      denominador: 2,
      comparar_con: { numerador: 1, denominador: 3 },
    })!;
    const dicho = describir(c);
    expect(dicho).toContain("NARANJA");
    expect(dicho).toContain("AZUL");
    expect(dicho).toContain("1/2");
    expect(dicho).toContain("1/3");
  });

  it("dice que la cuenta quedó ABIERTA si no hay resultado", () => {
    const c = aCuadro({ tipo: "operacion", a: 56, b: 38, op: "+" })!;
    expect(describir(c)).toContain("abierta");
  });

  it("describe todas las escenas sin romperse", () => {
    const casos = [
      { tipo: "operacion", a: 7, b: 5, op: "+", resultado: 12 },
      { tipo: "grupos", grupos: 3, por_grupo: 45, nombre: "cajas" },
      { tipo: "recta", desde: 0, hasta: 20, marca: 7, salta_a: 12 },
      { tipo: "fraccion", numerador: 3, denominador: 4 },
      { tipo: "texto", contenido: "ñ" },
    ];
    for (const caso of casos) {
      const c = aCuadro(caso);
      expect(c, JSON.stringify(caso)).not.toBeNull();
      expect(describir(c!).length).toBeGreaterThan(5);
    }
  });
});

describe("lista de palabras: el caso de ses_cdb0b7fae50f", () => {
  it("tres palabras en UNA llamada", () => {
    // El niño pidió "dame tres palabras que empiecen por w". El tutor mandó
    // tres `texto` seguidos —cada uno borró al anterior— y dijo "ahí te LAS
    // puse". El niño lo narró: "ya se escribió waffle, se está escribiendo
    // windsurf, y ahora otra".
    const c = aCuadro({ tipo: "lista", palabras: ["vaca", "vela", "viento"] });
    expect(c?.escena).toMatchObject({ tipo: "lista", palabras: ["vaca", "vela", "viento"] });
  });

  it("si vienen en un solo string separadas por comas, se entienden igual", () => {
    const c = aCuadro({ tipo: "lista", palabras: "vaca, vela, viento" });
    expect(c?.escena).toMatchObject({ tipo: "lista", palabras: ["vaca", "vela", "viento"] });
  });

  it("una sola palabra cae a `texto`, que la escribe a mano y se ve mejor", () => {
    const c = aCuadro({ tipo: "lista", palabras: ["ñu"] });
    expect(c?.escena).toMatchObject({ tipo: "texto", contenido: "ñu" });
  });

  it("no entran más de cuatro: se queda con las primeras", () => {
    const c = aCuadro({ tipo: "lista", palabras: ["a", "be", "ce", "de", "efe", "ge"] });
    expect((c?.escena as any).palabras).toHaveLength(4);
  });

  it("una frase no es una palabra: se descarta esa y quedan las buenas", () => {
    const c = aCuadro({
      tipo: "lista",
      palabras: ["vaca", "esto es una frase entera y larga", "vela"],
    });
    expect((c?.escena as any).palabras).toEqual(["vaca", "vela"]);
  });

  it("sin palabras no se dibuja nada", () => {
    expect(aCuadro({ tipo: "lista", palabras: [] })).toBeNull();
  });

  it("describir() nombra las palabras y dice que van juntas", () => {
    const c = aCuadro({ tipo: "lista", palabras: ["vaca", "vela", "viento"] })!;
    const dicho = describir(c);
    expect(dicho).toContain("vaca");
    expect(dicho).toContain("viento");
    expect(dicho).toContain("color");
  });
});

describe("el tutor sabe con qué está dibujado", () => {
  it("le dice que son gallinas cuando el niño ve gallinas", () => {
    // Los emojis abrieron el mismo agujero que venían a tapar: si el tutor
    // cree que el niño ve puntos y el niño ve 🐔, vuelve el «¿los puntos
    // naranjas son las galletas?». Lo que no se le dice, se lo inventa.
    const dicho = describir({
      escena: { tipo: "grupos", grupos: 3, porGrupo: 4, nombre: "gallinas" },
    } as Cuadro);
    expect(dicho).toContain("🐔");
  });

  it("sigue diciendo puntos cuando no sabemos dibujarlo", () => {
    const dicho = describir({
      escena: { tipo: "grupos", grupos: 3, porGrupo: 4, nombre: "cosas" },
    } as Cuadro);
    expect(dicho).toContain("puntos");
  });
});

describe("lo que el modelo manda DE VERDAD", () => {
  /* Capturado con `python -m scripts.verificar_pizarra` (22/08) pidiéndole al
     modelo real las tres cosas que pidió Juan en `ses_445f4c33db41`.

     No son casos inventados por nosotros para probar nuestro propio traductor:
     son la forma exacta en que el modelo llama a la pizarra cuando un niño de 7
     dice "muéstramela". Si un día `aCuadro` deja de entender uno, el niño se
     queda mirando un tablero vacío mientras el tutor le describe lo que cree
     haberle mostrado — y eso no lo atrapa ningún test escrito de memoria. */

  it("la letra suelta que pidió el niño", () => {
    const cuadro = aCuadro({ contenido: "w", tipo: "texto" });
    expect(cuadro?.escena).toEqual({ tipo: "texto", contenido: "w" });
  });

  it("la suma de tres montones, capturada del modelo real", () => {
    // Verificado el 23/08 con `python -m scripts.verificar_pizarra`, pidiéndole
    // textualmente lo que Juan pidió: «5 + 3 + 6 y no son bolitas, sino son
    // pollitos». Esto es lo que mandó, y lo que dijo encima:
    //
    //   «Mira, ahí te puse un grupo de cinco, otro de tres y otro de seis.
    //    ¿Me ayudas a descubrir cuántos pollitos son en total?»
    const cuadro = aCuadro({ nombre: "pollitos", cantidades: [5, 3, 6], tipo: "grupos" });
    expect(cuadro?.escena).toMatchObject({
      tipo: "grupos",
      cantidades: [5, 3, 6],
      nombre: "pollitos",
    });
  });

  it("la fracción, con las claves en el orden en que llegan", () => {
    // Llega `{denominador, numerador, tipo}` — el orden no importa en JS, pero
    // el caso importa: es lo que mandó al pedirle "las pizzas de tres quintos".
    const cuadro = aCuadro({ denominador: 5, numerador: 3, tipo: "fraccion" });
    expect(cuadro?.escena).toMatchObject({ tipo: "fraccion", numerador: 3, denominador: 5 });
    // Cinco partes todavía se leen como torta; con más, la barra gana.
    expect(describir(cuadro!)).toContain("torta");
  });
});

describe("la suma dibujada: montones distintos", () => {
  /* `ses_97d5b112a122`, dos veces en tres minutos:

       nino: «¿Cuánto daría si tengo 6 bolitas + 5 bolitas + 2 bolitas?»
       nino: «5 + 3 + 6, y no son bolitas, sino pollitos. ¿Podrías mostrarme
              los pollitos?»
       nino: «Me está mostrando tres cajas cada una con seis puntitos, eso no
              tiene nada que ver.»

     Y tenía razón: `operacion` solo acepta dos números y `grupos` dibujaba
     montones todos iguales. El modelo forzó lo único parecido que tenía. */

  it("dibuja 5 + 3 + 6 como tres montones de distinto tamaño", () => {
    const cuadro = aCuadro({ tipo: "grupos", cantidades: [5, 3, 6], nombre: "pollitos" });
    expect(cuadro?.escena).toMatchObject({ tipo: "grupos", cantidades: [5, 3, 6] });
  });

  it("se lo cuenta al tutor como la CUENTA, no como grupos iguales", () => {
    // Si le decimos "3 grupos de 6" sobre montones de 5, 3 y 6, el tutor le
    // habla al niño de algo que no está en la pantalla. Es el bug de los
    // emojis otra vez: lo que no se le dice, se lo inventa.
    const dicho = describir(aCuadro({ tipo: "grupos", cantidades: [5, 3, 6], nombre: "pollitos" })!);
    expect(dicho).toContain("5 + 3 + 6");
    expect(dicho).toContain("🐤");
  });

  it("acepta el string suelto, como ya hacía con las palabras", () => {
    expect(aCuadro({ tipo: "grupos", cantidades: "5, 3, 6" })?.escena).toMatchObject({
      cantidades: [5, 3, 6],
    });
  });

  it("un solo montón no es una suma: cae a los montones iguales", () => {
    // Con `cantidades: [7]` no hay nada que sumar. Se ignora y manda
    // grupos/por_grupo, que es lo que el modelo mandó junto.
    const cuadro = aCuadro({ tipo: "grupos", cantidades: [7], grupos: 2, por_grupo: 4 });
    expect(cuadro?.escena).toMatchObject({ tipo: "grupos", grupos: 2, porGrupo: 4 });
    expect((cuadro?.escena as { cantidades?: number[] }).cantidades).toBeUndefined();
  });

  it("los montones iguales siguen funcionando igual que siempre", () => {
    expect(aCuadro({ tipo: "grupos", grupos: 3, por_grupo: 4 })?.escena).toMatchObject({
      tipo: "grupos",
      grupos: 3,
      porGrupo: 4,
    });
  });
});

describe("lo que el tutor cree que escribió", () => {
  it("sabe que su letra es de imprenta y que NO tiene cursiva", () => {
    /* `ses_f6cb91f4e15c`: el niño pidió la W en cursiva y el tutor contestó
       «ahí te la puse en letra cursiva, ¿sí ves cómo es más curvita?». No
       había ninguna cursiva, y lo sostuvo dos veces con detalles inventados.

       El tutor no ve el tablero: sabe lo que este texto le dice que quedó. Si
       no dice con qué letra escribe, la inventa. */
    const dicho = describir(aCuadro({ tipo: "texto", contenido: "w" })!);
    expect(dicho).toContain("imprenta");
    expect(dicho.toLowerCase()).toContain("cursiva");
  });
});
