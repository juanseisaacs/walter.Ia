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
  token: string;
  modelo: string;
  deteccion: { silencio_ms: number };
  habilidad_id: string;
  habilidad_nombre: string;
  ejercicios: Ejercicio[];
}

export interface Turno {
  quien: "nino" | "tutor";
  texto: string;
}

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const r = await fetch(`/api${ruta}`, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  if (!r.ok) {
    const detalle = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(detalle.detail ?? `Error ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  abrirSesion: (ninoId: string, modo: "guiado" | "pedido" = "guiado") =>
    pedir<SesionAbierta>("/sesiones", {
      method: "POST",
      body: JSON.stringify({ nino_id: ninoId, modo }),
    }),

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

  escalateSafety: (sesionId: string, motivo: string, evidencia?: string) =>
    pedir("/tools/escalate_safety", {
      method: "POST",
      body: JSON.stringify({ sesion_id: sesionId, motivo, evidencia }),
    }),
};
