/**
 * El hook del tutor: junta el backend con Gemini Live.
 *
 *   1. Pide la sesión al backend  -> token con la configuración ATADA
 *   2. Conecta DIRECTO a Gemini   -> el audio no pasa por nuestro servidor
 *   3. Atiende los tool calls     -> los reenvía a nuestra API
 *   4. Reporta los turnos         -> habilita recargar ejercicios
 *
 * El navegador nunca ve el system prompt: recibe un token, no una
 * configuración. No puede cambiar la persona, el método ni la seguridad.
 */

import { GoogleGenAI, type LiveServerMessage, Modality } from "@google/genai";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, type SesionAbierta, type Turno } from "../api";
import { ReproductorContinuo, aPcm16Base64 } from "./audio";
import { abrirMicrofono, type CapturaMicrofono } from "./microfono";

export type Estado = "inicio" | "conectando" | "escuchando" | "hablando" | "error";

/** Cada cuántos turnos se reporta al backend. Bajo = más seguro, más llamadas. */
const TURNOS_POR_REPORTE = 2;

export function useTutor(ninoId: string) {
  const [estado, setEstado] = useState<Estado>("inicio");
  const [error, setError] = useState<string | null>(null);
  const [tema, setTema] = useState("");
  const [textoNino, setTextoNino] = useState("");
  const [textoTutor, setTextoTutor] = useState("");
  const [nivelMic, setNivelMic] = useState(0);

  const sesionRef = useRef<SesionAbierta | null>(null);
  const liveRef = useRef<any>(null);
  const micRef = useRef<CapturaMicrofono | null>(null);
  const reproductorRef = useRef<ReproductorContinuo | null>(null);
  const pendientesRef = useRef<Turno[]>([]);
  const ejercicioActualRef = useRef<string | null>(null);

  /* ── Reporte de turnos ─────────────────────────────────────────────────
     No bloquea nada: sale en paralelo mientras el tutor sigue hablando. */

  const encolar = useCallback((turno: Turno) => {
    if (!turno.texto.trim()) return;
    pendientesRef.current.push(turno);
    if (pendientesRef.current.length < TURNOS_POR_REPORTE) return;

    const sesion = sesionRef.current;
    if (!sesion) return;
    const lote = pendientesRef.current.splice(0);
    void api.reportarTurnos(sesion.sesion_id, lote).catch(() => {
      pendientesRef.current.unshift(...lote); // reintentar en el próximo
    });
  }, []);

  /* ── Tool calls ────────────────────────────────────────────────────────
     El modelo los pide; nosotros los resolvemos contra el backend. */

  const atenderTool = useCallback(async (nombre: string, args: any): Promise<object> => {
    const sesion = sesionRef.current;
    if (!sesion) return { error: "sin sesión" };

    switch (nombre) {
      case "check_answer": {
        const id = args.ejercicio_id ?? ejercicioActualRef.current;
        if (!id) return { error: "todavía no hay ejercicio entregado" };
        return api.checkAnswer(sesion.sesion_id, id, String(args.respuesta_nino ?? ""));
      }
      case "get_next_problem": {
        const { ejercicio } = await api.getNextProblem(sesion.sesion_id);
        ejercicioActualRef.current = ejercicio.id;
        return { ejercicio_id: ejercicio.id, enunciado: ejercicio.enunciado.es };
      }
      case "request_camera":
        return { pedido: true, motivo: args.motivo };
      case "escalate_safety":
        await api.escalateSafety(sesion.sesion_id, args.motivo, args.evidencia);
        return { escalado: true };
      default:
        return { error: `tool desconocido: ${nombre}` };
    }
  }, []);

  /* ── Arranque ──────────────────────────────────────────────────────────── */

  const empezar = useCallback(async () => {
    setError(null);
    setEstado("conectando");

    try {
      const reproductor = new ReproductorContinuo();
      reproductor.iniciar(); // dentro del gesto del usuario
      reproductor.alTerminar = () => setEstado((e) => (e === "hablando" ? "escuchando" : e));
      reproductorRef.current = reproductor;

      const sesion = await api.abrirSesion(ninoId);
      sesionRef.current = sesion;
      setTema(sesion.habilidad_nombre);

      // El token ya trae la configuración atada: no mandamos ni prompt ni tools.
      const ai = new GoogleGenAI({
        apiKey: sesion.token,
        httpOptions: { apiVersion: "v1alpha" },
      });

      const live = await ai.live.connect({
        model: sesion.modelo,
        config: { responseModalities: [Modality.AUDIO] },
        callbacks: {
          onmessage: (mensaje: LiveServerMessage) => {
            const contenido = mensaje.serverContent as any;

            for (const parte of contenido?.modelTurn?.parts ?? []) {
              if (parte.inlineData?.data) {
                setEstado("hablando");
                reproductor.programar(parte.inlineData.data);
              }
            }

            // El niño habló encima: cortar YA todo lo programado.
            if (contenido?.interrupted) {
              reproductor.detenerTodo();
              setEstado("escuchando");
            }

            const delTutor =
              contenido?.outputTranscription?.text ?? (mensaje as any).outputTranscription?.text;
            if (delTutor) {
              setTextoTutor((prev) => prev + delTutor);
            }

            const delNino =
              contenido?.inputTranscription?.text ?? (mensaje as any).inputTranscription?.text;
            if (delNino) setTextoNino((prev) => prev + delNino);

            if (contenido?.turnComplete) {
              setTextoNino((t) => {
                if (t) encolar({ quien: "nino", texto: t });
                return "";
              });
              setTextoTutor((t) => {
                if (t) encolar({ quien: "tutor", texto: t });
                return t;
              });
            }

            // Tool calls
            const llamadas = (mensaje as any).toolCall?.functionCalls ?? [];
            if (llamadas.length) {
              void Promise.all(
                llamadas.map(async (fc: any) => ({
                  id: fc.id,
                  name: fc.name,
                  response: await atenderTool(fc.name, fc.args ?? {}),
                })),
              ).then((respuestas) => live.sendToolResponse({ functionResponses: respuestas }));
            }
          },
          onerror: (e: any) => {
            setError(e?.message ?? "Se cortó la conexión con el tutor.");
            setEstado("error");
          },
          onclose: () => setEstado((e) => (e === "error" ? e : "inicio")),
        },
      });
      liveRef.current = live;

      const { captura } = await abrirMicrofono((muestras, nivel) => {
        setNivelMic(Math.min(1, nivel * 5));
        try {
          live.sendRealtimeInput({
            audio: { data: aPcm16Base64(muestras), mimeType: "audio/pcm;rate=16000" },
          });
        } catch {
          /* sesión cerrada a mitad de un lote */
        }
      });
      micRef.current = captura;

      setEstado("escuchando");
    } catch (e: any) {
      const denegado = e?.name === "NotAllowedError";
      setError(denegado ? "Necesito permiso para usar el micrófono." : (e?.message ?? "No pude conectarme."));
      setEstado("error");
    }
  }, [ninoId, atenderTool, encolar]);

  /* ── Cierre ────────────────────────────────────────────────────────────── */

  const terminar = useCallback(
    async (interrumpida = false) => {
      micRef.current?.detener();
      micRef.current = null;
      try {
        liveRef.current?.close();
      } catch {
        /* ya cerrada */
      }
      liveRef.current = null;
      reproductorRef.current?.cerrar();
      reproductorRef.current = null;

      const sesion = sesionRef.current;
      if (sesion) {
        if (pendientesRef.current.length) {
          await api.reportarTurnos(sesion.sesion_id, pendientesRef.current.splice(0)).catch(() => {});
        }
        await api.cerrarSesion(sesion.sesion_id, interrumpida).catch(() => {});
      }
      sesionRef.current = null;
      setEstado("inicio");
      setTextoNino("");
      setTextoTutor("");
    },
    [],
  );

  useEffect(() => () => void terminar(true), [terminar]);

  return { estado, error, tema, textoNino, textoTutor, nivelMic, empezar, terminar };
}
