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
  const entregadosRef = useRef<Set<string>>(new Set());
  const ejercicioActualRef = useRef<string | null>(null);
  const arrancandoRef = useRef(false);
  const arranquesRef = useRef(0);

  /** Identidad de ESTA pestaña. Sirve para ignorar los avisos propios. */
  const pestanaRef = useRef(Math.random().toString(36).slice(2, 8));
  const canalRef = useRef<BroadcastChannel | null>(null);

  // El techo de tokens por sesión y el tope mensual por niño existen en
  // config.py desde la fase 1, y hasta ahora eran ficción: el cierre mandaba
  // `tokens_consumidos: 0` fijo. Todas las sesiones figuran con 0 gastado.
  //
  // RESUELTO el 18/08 con `scripts/verificar_tokens.py` contra la API real:
  // `totalTokenCount` es ACUMULATIVO DE LA SESIÓN, no de su request. Medido en
  // cinco turnos: 10.299 · 10.682 · 11.140 · 11.561 · 11.946.
  //
  // Se reporta `ultimo`, NO `suma`. Sumarlos sobreestimaba 4,7x con cinco
  // turnos y casi 10x con veinte: ses_88be006b825f figura con 178.416 tokens
  // cuando gastó unos 18.500. Con ese número inflado el techo de sesión
  // saltaba por gasto que nunca ocurrió, y encima llevó a concluir que el
  // prompt se pagaba en cada turno. No: entra una vez al conectar y el modelo
  // mantiene el contexto del lado del servidor. Cada turno suma ~400.
  //
  // `suma` se conserva solo para el log: si un día el número dejara de crecer
  // monótono, la consola lo muestra y esta decisión se revisa.
  const tokensRef = useRef({ suma: 0, ultimo: 0 });

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
    // `info` y no `debug`: Chrome esconde los debug salvo que actives "Verbose",
    // y una medición que hay que ir a buscar es una medición que no se mira.
    // Se loguea también QUÉ devolvió: es lo único que distingue "llamó a la
    // herramienta y le desobedeció" de "nunca la llamó y lo dijo de memoria".
    const t0 = performance.now();
    const medir = (r: object) => {
      console.info(`[tool] ${nombre}: ${Math.round(performance.now() - t0)}ms`, r);
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
      case "verify_arithmetic": {
        // El tutor se sale del banco cuando el niño pide otra cosa, y ahí
        // `check_answer` no aplica: no hay ejercicio_id que valga. Sin esto el
        // modelo juzga la cuenta él mismo — y en ses_91c13b1747a2 le dijo a un
        // "780" para 135+241 que estaba "muy cerca" de 376.
        return medir(
          await api.verifyArithmetic(
            String(args.operacion ?? ""),
            String(args.respuesta_nino ?? ""),
          ),
        );
      }
      case "get_next_problem": {
        // Los ejercicios YA vinieron al abrir la sesión. Ir a buscarlos por red
        // es un viaje de ida y vuelta por nada: se sirven de acá, ~0ms.
        //
        // El tema lo pide el tutor cuando el niño quiere cambiar. El ejercicio
        // igual sale del banco validado: el niño elige DE QUÉ, nunca CUÁL.
        const tema = args.habilidad_id ? String(args.habilidad_id) : null;

        // ORDEN IDÉNTICO AL DEL BACKEND, y no es un detalle de estilo: los dos
        // bancos parten de la misma lista y avanzan en paralelo. Si entregaran
        // distinto, `check_answer` verificaría contra un enunciado que el niño
        // nunca oyó — y le diría que se equivocó por resolver bien otro
        // ejercicio. Sin tema se sirve la habilidad del día y, si se agotó,
        // cualquier otra; con tema, solo ese. Igual que BancoDeSesion.
        const libre = (h: string | null) =>
          bancoRef.current.find(
            (e) => !entregadosRef.current.has(e.id) && (h === null || e.habilidad_id === h),
          );
        const local = tema ? libre(tema) : (libre(sesion.habilidad_id) ?? libre(null));

        if (local) {
          entregadosRef.current.add(local.id);
          ejercicioActualRef.current = local.id;
          // El backend igual tiene que enterarse: su BancoDeSesion alimenta
          // habilidades_trabajadas y decide cuándo recargar. Pero que se entere
          // NO puede costarle el silencio al niño — sale sin esperarlo.
          void api.getNextProblem(sesion.sesion_id, tema ?? undefined).catch(() => {});
          return medir({
            ejercicio_id: local.id,
            enunciado: local.enunciado.es,
            tema: local.habilidad_id,
          });
        }

        // Se acabó lo precargado de ese tema: acá sí toca esperar.
        const r = await api.getNextProblem(sesion.sesion_id, tema ?? undefined);
        if (!r.ejercicio) {
          // No es un fallo: es "de eso hoy no tengo". Se le devuelven los temas
          // que sí hay para que pueda ofrecerlos en vez de inventar uno.
          return medir({
            sin_ejercicios: true,
            mensaje: r.mensaje ?? "No quedan ejercicios de ese tema.",
            temas_disponibles: r.temas_disponibles ?? [],
          });
        }
        entregadosRef.current.add(r.ejercicio.id);
        ejercicioActualRef.current = r.ejercicio.id;
        return medir({
          ejercicio_id: r.ejercicio.id,
          enunciado: r.ejercicio.enunciado.es,
          tema: r.ejercicio.habilidad_id,
        });
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

  /* ── Soltar recursos ────────────────────────────────────────
     Micrófono, WebSocket y audio. Lo llaman terminar(), onerror y empezar():
     este último para que NUNCA queden dos sesiones vivas a la vez. */

  const soltarRecursos = useCallback(() => {
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
  }, []);

  /* ── Cierre ────────────────────────────────────────────────────────────── */

  const terminar = useCallback(
    async (interrumpida = false) => {
      soltarRecursos();

      const sesion = sesionRef.current;
      if (sesion) {
        if (pendientesRef.current.length) {
          await api.reportarTurnos(sesion.sesion_id, pendientesRef.current.splice(0)).catch(() => {});
        }
        await api
          .cerrarSesion(sesion.sesion_id, interrumpida, tokensRef.current.ultimo)
          .catch(() => {});
      }
      sesionRef.current = null;
      acumNinoRef.current = "";
      acumTutorRef.current = "";
      bancoRef.current = [];
      entregadosRef.current = new Set();
      tokensRef.current = { suma: 0, ultimo: 0 };
      setEstado("inicio");
      setTextoNino("");
      setTextoTutor("");
    },
    [soltarRecursos],
  );

  /* ── Una sola pestaña a la vez ──────────────────────────────────────────

     El backend ya cierra la sesión previa del niño cuando abre otra, pero eso
     es contabilidad: la conexión Live de la pestaña vieja tiene su token y
     Gemini no sabe nada de nuestra base. Sigue hablando por los mismos
     parlantes aunque su sesión ya esté cerrada.

     Recargar la página no necesita esto — el navegador mata el WebSocket al
     descargar. Dos pestañas sí: son dos JS vivos al mismo tiempo. */

  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return; // navegador viejo
    const canal = new BroadcastChannel("rbh-tutor-sesion");

    canal.onmessage = (evento) => {
      const dato = evento.data;
      if (dato?.tipo !== "arranco" || dato.pestana === pestanaRef.current) return;
      if (!sesionRef.current) return; // esta pestaña no tenía nada abierto

      console.warn("[sesion] otra pestaña tomó el tutor: esta se cierra");
      void terminar(true).then(() => {
        setError("Abriste el tutor en otra pestaña. Aquí quedó cerrado.");
        setEstado("error");
      });
    };

    canalRef.current = canal;
    return () => {
      canal.close();
      canalRef.current = null;
    };
  }, [terminar]);

  /* ── Arranque ──────────────────────────────────────────────────────────── */

  const empezar = useCallback(async () => {
    // GUARDIA DE REENTRADA — el bug de "dos tutores".
    //
    // Sin esto, dos llamadas a empezar() abren dos conexiones Live. liveRef y
    // micRef se sobrescriben con la segunda, y la PRIMERA queda huérfana: nadie
    // guarda su referencia, así que terminar() ya no la puede cerrar, pero
    // sigue viva. Sigue recibiendo el audio del micrófono viejo (que quedó
    // capturado en su closure) y sigue hablando por su propio reproductor.
    // El niño oye dos tutores encima, cada uno con su propia conversación.
    //
    // Lo disparaba "Probar de nuevo": onerror ponía el estado en "error" sin
    // soltar nada, y el reintento abría la segunda sobre la primera viva.
    // Instrumentación: la prueba del 18/08 mostró TRES POST /api/sesiones y
    // nadie supo de dónde salieron. Ahora el navegador lo dice.
    arranquesRef.current += 1;
    console.info(
      `[sesion] arranque #${arranquesRef.current} en la pestaña ${pestanaRef.current}`,
    );
    if (arranquesRef.current > 1) {
      console.warn("[sesion] esta pestaña ya había arrancado el tutor antes");
    }

    if (arrancandoRef.current) {
      console.warn("[sesion] arranque ignorado: ya hay uno en curso");
      return;
    }
    arrancandoRef.current = true;

    // Si quedó algo de un intento anterior, se cierra ANTES de abrir.
    // terminar() y no soltarRecursos(): la sesión del backend también tiene
    // que cerrarse, o queda contando contra el cupo diario del niño.
    if (sesionRef.current) await terminar(true);

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
      entregadosRef.current = new Set();
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

            const gastados = (mensaje as any).usageMetadata?.totalTokenCount;
            if (gastados) {
              tokensRef.current.suma += gastados;
              tokensRef.current.ultimo = gastados;
              console.info(
                `[tokens] acumulado=${gastados} (suma ingenua ${tokensRef.current.suma})`,
              );
            }

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

              // Lo que el Analista va a LEER, visible en el momento. La
              // transcripción es su único insumo: un "dos" que llega como "32"
              // se ve acá y no dos días después, en la ficha del niño.
              if (dichoNino) console.info(`[niño] ${dichoNino}`);
              if (dichoTutor) console.info(`[tutor] ${dichoTutor}`);

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
            // Soltar YA. Si el usuario le da a "Probar de nuevo" con el
            // micrófono y el socket todavía vivos, se suman dos tutores.
            soltarRecursos();
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

      // Avisar al resto: si otra pestaña tenía el tutor abierto, se cierra.
      canalRef.current?.postMessage({ tipo: "arranco", pestana: pestanaRef.current });

      setEstado("escuchando");
    } catch (e: any) {
      // Un arranque a medias deja el micrófono abierto y el socket colgando:
      // el siguiente intento se sumaría encima en vez de reemplazarlo.
      soltarRecursos();
      const denegado = e?.name === "NotAllowedError";
      setError(denegado ? "Necesito permiso para usar el micrófono." : (e?.message ?? "No pude conectarme."));
      setEstado("error");
    } finally {
      arrancandoRef.current = false;
    }
  }, [ninoId, atenderTool, encolar, terminar, soltarRecursos]);

  useEffect(() => () => void terminar(true), [terminar]);

  return { estado, error, tema, textoNino, textoTutor, nivelMic, empezar, terminar };
}
