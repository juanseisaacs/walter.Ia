/**
 * El tutor que se queda callado.
 *
 * Sale de `ses_87aba17c8c6c` (22/08). El niño dictó su tarea de sumas y el
 * tutor no volvió a hablar nunca. Lo que quedó escrito es el niño solo:
 *
 *   nino: Tengo una tarea que dice 5 + 5, luego otra que dice 3 - 4...
 *   nino: Walter, ¿por qué no estás aquí? ¿Qué te pasó? ¿Por qué te fuiste?
 *
 * La sesión seguía viva —el micrófono mandaba, Gemini transcribía— y la
 * pantalla no decía nada. El backend tampoco se enteró: no está en el camino
 * del audio. Nadie miraba el reloj.
 */

import { describe, expect, it } from "vitest";

import { MS_TOPE_TOOL } from "../api";
import {
  AVISO_DE_MUDEZ,
  EMPUJONES_ANTES_DE_RENDIRSE,
  MARCA_DE_MUDEZ,
  MS_MUDEZ,
  MS_MUDEZ_TRAS_EMPUJON,
} from "./useTutor";

describe("cuánto se espera", () => {
  it("le da tiempo de pensar antes de darlo por mudo", () => {
    // Callarse mientras el niño piensa es enseñar (`tutor_persona`), y el tutor
    // contesta en uno o dos segundos. Un vigilante nervioso lo interrumpiría
    // justo cuando está haciendo lo correcto.
    expect(MS_MUDEZ).toBeGreaterThanOrEqual(5_000);
  });

  it("pero no lo espera para siempre", () => {
    // El niño de la sesión aguantó ese silencio preguntando tres veces qué
    // había pasado. Ese es el techo que este número no puede superar.
    expect(MS_MUDEZ).toBeLessThanOrEqual(20_000);
  });

  it("le da MÁS margen después del empujón que antes", () => {
    // Medido el 22/08 (`verificar_dibujo`): un modelo trabado que reacciona al
    // empujón tarda 15,3 s en soltar la primera sílaba, contra 0,9-3,5 s de un
    // turno sano. Empujarlo otra vez con el reloj corto sería atropellarlo justo
    // cuando iba a hablar.
    expect(MS_MUDEZ_TRAS_EMPUJON).toBeGreaterThan(MS_MUDEZ);
    expect(MS_MUDEZ_TRAS_EMPUJON).toBeGreaterThanOrEqual(16_000);
  });

  it("no deja al niño más de medio minuto hablándole a nadie", () => {
    // El peor caso completo: silencio + empujones + rendirse. Es el número que
    // de verdad vive el niño, y ninguna constante suelta lo muestra.
    const peor = MS_MUDEZ + EMPUJONES_ANTES_DE_RENDIRSE * MS_MUDEZ_TRAS_EMPUJON;
    expect(peor).toBeLessThanOrEqual(30_000);
  });

  it("intenta recuperarlo antes de cortarle la sesión", () => {
    // Cerrar es la última carta: la mayoría de los silencios se destraban con
    // un turno de texto, y cortar de más manda al niño de vuelta al botón.
    expect(EMPUJONES_ANTES_DE_RENDIRSE).toBeGreaterThanOrEqual(1);
  });
});

describe("las dos capas encajan", () => {
  it("una tool colgada vence ANTES de que el vigilante empuje", () => {
    // Si no, el empujón llega mientras Gemini todavía espera la respuesta de la
    // herramienta —donde un turno de texto no destraba nada— y se gasta al
    // pedo. El orden es: primero se libera el tool, después se empuja.
    //
    // Este es el test que cruza los dos arreglos del 22/08. Sin él, subir
    // `MS_TOPE_TOOL` a 15 s dejaría el vigilante inútil y nada se pondría rojo.
    expect(MS_TOPE_TOOL).toBeLessThan(MS_MUDEZ);
  });
});

describe("el empujón", () => {
  it("le pide RETOMAR, no le pregunta si sigue ahí", () => {
    expect(AVISO_DE_MUDEZ.toLowerCase()).toContain("retoma");
  });

  it("no lo deja inventar por qué se calló", () => {
    // `tutor_persona`: "Si algo se rompe, no inventes por qué". Una causa que
    // suene bien le enseña al niño lo contrario de lo que le pedimos a él.
    expect(AVISO_DE_MUDEZ.toLowerCase()).toContain("no inventes");
  });

  it("no se menciona a sí mismo", () => {
    expect(AVISO_DE_MUDEZ.toLowerCase()).toContain("no menciones este aviso");
  });

  it("no vosea: el modelo imita el registro de lo que lee", () => {
    expect(AVISO_DE_MUDEZ).not.toMatch(/\b(podés|tenés|querés|contá|decile|mirá|dale|sos)\b/i);
  });
});

describe("la marca en la transcripción", () => {
  it("dice que el silencio fue del TUTOR", () => {
    // El Analista solo lee la transcripción. Sin esto, una sesión donde el
    // tutor se murió se ve igual que una donde el niño se aburrió y se fue —
    // y la ficha del niño termina diciendo que no participó.
    expect(MARCA_DE_MUDEZ.toLowerCase()).toContain("tutor");
  });

  it("va entre corchetes, como el resto de las marcas de sistema", () => {
    expect(MARCA_DE_MUDEZ.startsWith("[")).toBe(true);
    expect(MARCA_DE_MUDEZ.endsWith("]")).toBe(true);
  });
});
