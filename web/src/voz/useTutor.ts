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

import { api, type Ejercicio, type SesionAbierta, type Turno } from "../api";
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
  const acumNinoRef = useRef("");
  const acumTutorRef = useRef("");
  const bancoRef = useRef<Ejercicio[]>([]);
  const indiceRef = useRef(0);
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

    // Mientras esto corre el tutor está MUDO y el niño cree que lo abandonaron.
    // El número va a consola para poder decidir con datos, no con sensación.
    const t0 = performance.now();
    const medir = (r: object) => {
      console.debug(`[tool] ${nombre}: ${Math.round(performance.now() - t0)}ms`);
      return r;
    };

    // Esta función NO PUEDE tirar una excepción. Si tira, el .catch() de abajo
    // la agarra y devuelve un error legible — pero la regla vive acá también
    // porque el precio de romperla es que el niño se quede hablándole a nadie.

    switch (nombre) {
      case "check_answer": {
        const id = args.ejercicio_id ?? ejercicioActualRef.current;
        if (!id) return { error: "todavía no hay ejercicio entregado" };
        // Este SÍ tiene que ir al backend: la aritmética se valida en un solo
        // lugar. Reimplementarla acá sería tener dos versiones de lo único que
        // no puede estar mal.
        return medir(
          await api.checkAnswer(sesion.sesion_id, id, String(args.respuesta_nino ?? "")),
        );
      }
      case "get_next_problem": {
        // Los ejercicios YA vinieron al abrir la sesión. Ir a buscarlos por red
        // es un viaje de ida y vuelta por nada: se sirven de acá, ~0ms.
        const local = bancoRef.current[indiceRef.current];
        if (local) {
          indiceRef.current += 1;
          ejercicioActualRef.current = local.id;
          // El backend igual tiene que enterarse: su BancoDeSesion alimenta
          // habilidades_trabajadas y decide cuándo recargar. Pero que se entere
          // NO puede costarle el silencio al niño — sale sin esperarlo.
          void api.getNextProblem(sesion.sesion_id).catch(() => {});
          return medir({ ejercicio_id: local.id, enunciado: local.enunciado.es });
        }
        // Se acabó el precargado: acá sí toca esperar.
        const { ejercicio } = await api.getNextProblem(sesion.sesion_id);
        ejercicioActualRef.current = ejercicio.id;
        return medir({ ejercicio_id: ejercicio.id, enunciado: ejercicio.enunciado.es });
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
      bancoRef.current = sesion.ejercicios ?? [];
      indiceRef.current = 0;
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

            // El acumulado vive en refs, NO en el estado. Dos razones:
            //   1. encolar() es un efecto; adentro de un updater StrictMode lo
            //      corre dos veces y cada turno se reporta duplicado.
            //   2. leer el acumulado sin depender de cuándo React aplique el
            //      set evita el bug de no limpiarlo (crecía toda la sesión).
            const delTutor =
              contenido?.outputTranscription?.text ?? (mensaje as any).outputTranscription?.text;
            if (delTutor) {
              acumTutorRef.current += delTutor;
              setTextoTutor(acumTutorRef.current);
            }

            const delNino =
              contenido?.inputTranscription?.text ?? (mensaje as any).inputTranscription?.text;
            if (delNino) {
              acumNinoRef.current += delNino;
              setTextoNino(acumNinoRef.current);
            }

            if (contenido?.turnComplete) {
              const dichoNino = acumNinoRef.current;
              const dichoTutor = acumTutorRef.current;
              acumNinoRef.current = "";
              acumTutorRef.current = "";

              if (dichoNino) encolar({ quien: "nino", texto: dichoNino });
              if (dichoTutor) encolar({ quien: "tutor", texto: dichoTutor });

              setTextoNino("");
              setTextoTutor(dichoTutor); // en pantalla queda el ÚLTIMO turno, no la suma
            }

            // Tool calls
            //
            // REGLA DURA: sendToolResponse se manda SIEMPRE, pase lo que pase.
            //
            // Gemini bloquea el turno hasta recibir la respuesta de cada tool
            // que pidió. Si una falla y no contestamos, no se "pierde un
            // ejercicio": el tutor se queda MUDO para siempre y el niño le
            // habla a nadie. Ya pasó (ses_ea39b9de2677, 17/08): el modelo se
            // inventó un ejercicio, mandó un ejercicio_id inexistente, el
            // backend respondió 404, la promesa se rechazó y ahí murió todo.
            //
            // Por eso cada llamada se aísla en su propio catch (una que falle
            // no puede arrastrar a las otras) y el envío tiene el suyo.
            const llamadas = (mensaje as any).toolCall?.functionCalls ?? [];
            if (llamadas.length) {
              void Promise.all(
                llamadas.map(async (fc: any) => {
                  let respuesta: object;
                  try {
                    respuesta = await atenderTool(fc.name, fc.args ?? {});
                  } catch (e: any) {
                    // El modelo lee esto y puede recuperarse hablando. Es
                    // mucho mejor que el silencio.
                    respuesta = { error: e?.message ?? "falló la herramienta" };
                    console.warn(`[tool] ${fc.name} falló:`, e);
                  }
                  return { id: fc.id, name: fc.name, response: respuesta };
                }),
              )
                .then((respuestas) => live.sendToolResponse({ functionResponses: respuestas }))
                .catch((e) => console.error("[tool] no se pudo responder:", e));
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
      acumNinoRef.current = "";
      acumTutorRef.current = "";
      bancoRef.current = [];
      indiceRef.current = 0;
      setEstado("inicio");
      setTextoNino("");
      setTextoTutor("");
    },
    [],
  );

  useEffect(() => () => void terminar(true), [terminar]);

  return { estado, error, tema, textoNino, textoTutor, nivelMic, empezar, terminar };
}
