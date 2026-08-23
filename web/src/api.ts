/**
 * Cliente del backend de control.
 *
 * El AUDIO no pasa por acá: va directo del navegador a Gemini. Esto es solo el
 * plano de control — abrir sesión, los tools, y reportar los turnos.
 */

export interface Ejercicio {
  id: string;
  habilidad_id: string;
  enunciado: { es: string };
  respuesta: string;
}

export interface SesionAbierta {
  sesion_id: string;
  max_tokens?: number;
  avisar_tokens?: number;
  max_minutos?: number;
  avisar_minutos?: number;
  token: string;
  modelo: string;
  deteccion: { silencio_ms: number };
  habilidad_id: string;
  habilidad_nombre: string;
  ejercicios: Ejercicio[];
  /** Instrucción interna que dispara el saludo del tutor. No la oye el niño. */
  apertura?: string;
}

export interface Turno {
  quien: "nino" | "tutor";
  texto: string;
}

/** Un error del backend, con su código. El código es lo que decide qué hacer. */
export class ErrorApi extends Error {
  constructor(
    readonly status: number,
    mensaje: string,
  ) {
    super(mensaje);
    this.name = "ErrorApi";
  }

  /**
   * La sesión ya no existe del lado del servidor.
   *
   * Distinguirlo importa: mientras se trató como un error cualquiera, el
   * navegador siguió reportando turnos a una sesión muerta — 32 POST con 404
   * el 18/08 — y el niño estuvo 99 segundos hablándole a un tutor que no podía
   * entregarle un ejercicio ni guardar lo que decía.
   */
  get sesionMurio(): boolean {
    return this.status === 404;
  }
}

/**
 * Tope duro de una llamada de tool. NO es un número de rendimiento: es la
 * garantía de que el tutor vuelve a hablar.
 *
 * `fetch` sin señal no vence nunca por su cuenta — se queda colgado hasta que
 * el sistema operativo decida, y eso son minutos. Adentro de `atenderTool` eso
 * no es "un ejercicio que tarda": Gemini bloquea el turno hasta recibir la
 * respuesta de cada tool que pidió, así que un fetch colgado deja al tutor
 * MUDO para siempre con la sesión viva, el micrófono abierto y el niño
 * hablándole a nadie. La regla de `useTutor` —«sendToolResponse se manda
 * SIEMPRE, pase lo que pase»— no se podía cumplir sin esto: el `catch` que la
 * sostiene solo atrapa promesas que fallan, y una promesa colgada no falla.
 *
 * 8 segundos es holgadísimo para un backend medido en 4 ms (ARCHITECTURE §9).
 * Si se llega acá, algo está roto y lo que importa es que el tutor lo SEPA y
 * pueda decir algo, no esperar por si acaso.
 */
export const MS_TOPE_TOOL = 8_000;

/** Abrir sesión precarga el banco: tarda más y no está en ningún turno. */
const MS_TOPE_SESION = 30_000;

async function pedir<T>(ruta: string, opciones?: RequestInit, msTope = MS_TOPE_TOOL): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`/api${ruta}`, {
      headers: { "Content-Type": "application/json" },
      ...opciones,
      // Después del spread a propósito: el tope no lo pisa quien llama.
      signal: AbortSignal.timeout(msTope),
    });
  } catch (e: any) {
    // Se traduce a ErrorApi para que arriba haya UN solo tipo de fallo. El
    // status 0 dice "ni siquiera hubo respuesta" y no es 404: la sesión sigue
    // viva del lado del servidor, lo que se cayó es el camino.
    const vencio = e?.name === "TimeoutError" || e?.name === "AbortError";
    throw new ErrorApi(
      0,
      vencio
        ? `el backend no contestó en ${Math.round(msTope / 1000)}s`
        : (e?.message ?? "no se pudo hablar con el backend"),
    );
  }
  if (!r.ok) {
    const detalle = await r.json().catch(() => ({ detail: r.statusText }));
    throw new ErrorApi(r.status, detalle.detail ?? `Error ${r.status}`);
  }
  return r.json() as Promise<T>;
}

/**
 * El bundle que está corriendo AHORA MISMO en esta pestaña.
 *
 * `import.meta.url` es la URL de este módulo, y Vite le mete el hash del build
 * en el nombre: `/assets/index-C1QkbTfb.js`. O sea que el frontend puede decir
 * con qué versión de sí mismo está corriendo, sin que nadie tenga que acordarse
 * de subir un número a mano.
 *
 * En desarrollo (`vite dev`) los módulos no llevan hash y esto da otra cosa;
 * por eso el chequeo solo actúa cuando el backend informa un build concreto.
 */
export const MI_BUILD = import.meta.url.split("/").pop() ?? "";

/** Marca de que ya recargamos por versión vieja. Evita el bucle: si tras la
 *  recarga seguimos viejos, el problema es otro y hay que decirlo, no repetir. */
const YA_RECARGUE = "rbh-recargado-por-version";

/**
 * ¿El JavaScript de esta pestaña es el que el servidor está sirviendo?
 *
 * EL BUG QUE ESTO EVITA (`ses_4ed4e930e60f`, 23/08): el niño tenía la pestaña
 * abierta de hacía rato y tocó "empezar". El backend ya se había reiniciado con
 * la pizarra nueva y le dijo al modelo que podía pedir `cantidades`; el
 * JavaScript vivo en esa pestaña era el de antes y no sabía traducirlo. El
 * tutor terminó diciéndole al niño «como que el tablero no me quiere funcionar
 * hoy» — una versión hablando con otra, y el niño en el medio.
 *
 * Devuelve `true` si se disparó una recarga (y entonces no hay que seguir).
 */
export async function recargarSiEstoyViejo(): Promise<boolean> {
  let servido: string | null | undefined;
  try {
    servido = (await pedir<{ build?: string | null }>("/salud")).build;
  } catch {
    // Sin respuesta no se recarga nada: quedarse con el front viejo es mucho
    // mejor que un bucle de recargas contra un backend caído.
    return false;
  }

  if (!servido || servido === MI_BUILD) {
    sessionStorage.removeItem(YA_RECARGUE);
    return false;
  }

  if (sessionStorage.getItem(YA_RECARGUE)) {
    // Recargamos y seguimos viejos: el navegador está sirviendo el HTML de su
    // caché igual. Se deja de insistir y lo dice quien tiene la pantalla.
    console.error(`[version] sigo en ${MI_BUILD} y el servidor sirve ${servido}`);
    return false;
  }

  console.warn(`[version] esta pestaña es ${MI_BUILD}, el servidor sirve ${servido}: recargo`);
  sessionStorage.setItem(YA_RECARGUE, "1");
  location.reload();
  return true;
}

export const api = {
  abrirSesion: (ninoId: string, modo: "guiado" | "pedido" = "guiado", token?: string | null) =>
    pedir<SesionAbierta>(
      "/sesiones",
      {
        method: "POST",
        // El `token` es la credencial del niño, del enlace que recibió el papá.
        // Sin ella el backend contesta 401: el `nino_id` viaja en la URL y nunca
        // fue un secreto.
        body: JSON.stringify({ nino_id: ninoId, modo, token }),
      },
      MS_TOPE_SESION,
    ),

  /** Reportar habilita recargar ejercicios. Sin esto la sesión se queda sin material. */
  reportarTurnos: (sesionId: string, turnos: Turno[]) =>
    pedir<{ alertas: unknown[] }>(`/sesiones/${sesionId}/turnos`, {
      method: "POST",
      body: JSON.stringify({ turnos }),
    }),

  cerrarSesion: (sesionId: string, interrumpida = false, tokensConsumidos = 0) =>
    pedir(`/sesiones/${sesionId}/cerrar`, {
      method: "POST",
      body: JSON.stringify({ interrumpida, tokens_consumidos: tokensConsumidos }),
    }),

  /* ── Tools ─────────────────────────────────────────────────────────────
     ~100ms, ocasional (cada 30-60s). check_answer vive SOLO en el backend:
     nunca reimplementado acá. Una sola implementación de lo que no puede
     estar mal. */

  checkAnswer: (sesionId: string, ejercicioId: string, respuestaNino: string) =>
    pedir<{ correcto: boolean; veredicto: string; valor_interpretado: string | null }>(
      "/tools/check_answer",
      {
        method: "POST",
        body: JSON.stringify({
          sesion_id: sesionId,
          ejercicio_id: ejercicioId,
          respuesta_nino: respuestaNino,
        }),
      },
    ),

  /** Para las cuentas que el tutor improvisa fuera del banco. Nunca devuelve
      el resultado correcto: solo si acertó y qué tan lejos quedó. */
  verifyArithmetic: (operacion: string, respuestaNino: string) =>
    pedir<{
      correcto: boolean;
      veredicto: string;
      valor_interpretado: string | null;
      distancia: string | null;
    }>("/tools/verify_arithmetic", {
      method: "POST",
      body: JSON.stringify({ operacion, respuesta_nino: respuestaNino }),
    }),

  /** Para lectura y escritura fuera del banco. El gemelo de verifyArithmetic.
      Acá SÍ vuelve lo correcto, pero solo cuando el niño ya se equivocó: la
      corrección de un silabeo no arruina el ejercicio, y sin ella el tutor la
      inventa — le dijo "¡Perfecto!" a un "prim-o" (ses_50d5fa00b5d8). */
  verifyLanguage: (palabra: string, que: string, respuestaNino: string, palabra2 = "") =>
    pedir<{
      correcto: boolean;
      veredicto: string;
      valor_interpretado: string | null;
      lo_correcto: string | null;
    }>("/tools/verify_language", {
      method: "POST",
      body: JSON.stringify({
        palabra,
        que,
        respuesta_nino: respuestaNino,
        palabra2,
      }),
    }),

  getNextProblem: (sesionId: string, habilidadId?: string) =>
    pedir<{
      ejercicio: Ejercicio | null;
      se_agota?: boolean;
      temas_disponibles?: string[];
      mensaje?: string;
    }>(
      `/tools/get_next_problem?sesion_id=${encodeURIComponent(sesionId)}` +
        (habilidadId ? `&habilidad_id=${encodeURIComponent(habilidadId)}` : ""),
      { method: "POST" },
    ),

  /* ── Onboarding: la conversación que da de alta a un niño ───────────── */

  iniciarOnboarding: () =>
    pedir<{ onboarding_id: string; pregunta: string; falta: string[] }>("/onboarding", {
      method: "POST",
    }),

  responderOnboarding: (onboardingId: string, texto: string) =>
    pedir<{
      listo: boolean;
      pregunta?: string;
      falta?: string[];
      nino_id?: string;
      nombre?: string;
      mensaje?: string;
    }>(`/onboarding/${encodeURIComponent(onboardingId)}`, {
      method: "POST",
      body: JSON.stringify({ texto }),
    }),

  escalateSafety: (sesionId: string, motivo: string, evidencia?: string) =>
    pedir("/tools/escalate_safety", {
      method: "POST",
      body: JSON.stringify({ sesion_id: sesionId, motivo, evidencia }),
    }),
};
