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

import { ErrorApi, api, type Ejercicio, type SesionAbierta, type Turno } from "../api";
import { ReproductorContinuo, SAMPLE_RATE_ENTRADA, aPcm16Base64 } from "./audio";
import { abrirCamara, capturarCuadro, cerrarCamara, explicarFallo } from "./camara";
import { abrirMicrofono, type CapturaMicrofono } from "./microfono";
import { aCuadro } from "../pizarra/desdeElTutor";
import type { Cuadro } from "../pizarra/escenas";

export type Estado = "inicio" | "conectando" | "escuchando" | "hablando" | "error";

/** Cada cuántos turnos se reporta al backend. Bajo = más seguro, más llamadas. */
const TURNOS_POR_REPORTE = 2;

/**
 * Volumen (RMS) desde el que se considera que el niño está hablando de verdad,
 * y no que se coló el eco del propio tutor por los parlantes.
 *
 * El micrófono pide `echoCancellation`, así que lo que queda del tutor es
 * residuo: bien por debajo de esto. Una voz normal a medio metro anda en 0,03 a
 * 0,15. Si el tutor llegara a cortarse solo, este número sube; si al niño le
 * cuesta interrumpir, baja.
 */
const UMBRAL_BARGE_IN = 0.045;

/**
 * Cuánto tiene que sostenerse esa voz antes de callar al tutor.
 *
 * Los bloques del micrófono son de ~64 ms: esto son tres seguidos. Una sílaba
 * los llena; una tos o un golpe en la mesa, no.
 */
const MS_PARA_CORTAR = 200;

/**
 * Cuánto esperar antes de EMPUJAR al tutor a hablar de la foto.
 *
 * Solo se empuja si en ese tiempo no dijo nada. La versión anterior preguntaba
 * a los 900 ms pasara lo que pasara, y eso resultó ser peor que no preguntar:
 * el modelo ya había empezado a contestar la imagen —"A ver,"— y el mensaje lo
 * CORTÓ, abriendo un turno nuevo donde la foto ya no estaba en foco. Después
 * decía, con razón, que no le había llegado nada.
 *
 * Tres cosas empujan turnos en esta pantalla a la vez: la voz del niño, la
 * imagen y este mensaje. La imagen es la única que no puede esperar su lugar,
 * así que las otras dos le ceden el paso.
 *
 * Bajó de 2.500 a 1.200 cuando la guardia dejó de esperar al audio: ahora se
 * detecta que el modelo arrancó en cuanto EMPIEZA a generar, no cuando ya
 * suena. Con eso, esperar de más solo agrega silencio.
 */
const ESPERA_ANTES_DE_EMPUJAR_MS = 1200;

export function useTutor(ninoId: string) {
  // Con qué modo se abrió la sesión. Lo elige el niño al empezar.
  const modoRef = useRef<"guiado" | "pedido">("guiado");
  const [estado, setEstado] = useState<Estado>("inicio");
  const [error, setError] = useState<string | null>(null);
  const [tema, setTema] = useState("");
  const [textoNino, setTextoNino] = useState("");
  const [textoTutor, setTextoTutor] = useState("");
  const [nivelMic, setNivelMic] = useState(0);
  const [sesionMurio, setSesionMurio] = useState(false);
  /** Cuando no es null, hay un visor abierto esperando que el niño dispare. */
  const [camara, setCamara] = useState<MediaStream | null>(null);
  /** Lo que hay escrito en la pizarra ahora. `null` = no hay tablero en pantalla:
      sale solo cuando hay algo que valga la pena mirar, no todo el rato. */
  const [cuadro, setCuadro] = useState<Cuadro | null>(null);
  /** La consigna del dibujo, cuando el tutor le pidió al niño que trace algo. */
  const [hoja, setHoja] = useState<string | null>(null);
  /** Por qué no se pudo abrir. Se muestra EN PANTALLA, no solo en consola:
      un fallo invisible deja al niño oyendo 'toca el botón' sin botón. */
  const [fallaCamara, setFallaCamara] = useState<string | null>(null);
  /** Aviso sobre el video sin cerrar el visor: 'espera y toca otra vez'. */
  const [avisoVisor, setAvisoVisor] = useState<string | null>(null);
  /** La foto salió: se confirma en pantalla antes de cerrar el visor. */
  const [fotoEnviada, setFotoEnviada] = useState(false);
  /** El tutor todavía no dijo nada sobre la foto. Se apaga cuando habla. */
  const [mirandoFoto, setMirandoFoto] = useState(false);
  /** ¿El tutor ya dijo algo desde que salió la foto? Si sí, no se le empuja. */
  const hablóTrasFotoRef = useRef(false);
  const avisadoRef = useRef(false);

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
  /** Para llegar a terminar() desde el callback de Gemini, que se arma antes. */
  const terminarRef = useRef<((interrumpida?: boolean) => Promise<void>) | null>(null);
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
    void api.reportarTurnos(sesion.sesion_id, lote).catch((e) => {
      if (e instanceof ErrorApi && e.sesionMurio) {
        // No se reintenta: no hay a dónde. Seguir acumulando turnos para una
        // sesión que ya no existe fue lo que dejó al niño hablando solo.
        setSesionMurio(true);
        return;
      }
      pendientesRef.current.unshift(...lote); // reintentar en el próximo
    });
  }, []);

  /* ── Tool calls ────────────────────────────────────────────────────────
     El modelo los pide; nosotros los resolvemos contra el backend. */

  /** Le cuenta algo al tutor por el canal de texto, fuera del ciclo de un tool. */
  const avisarAlTutor = useCallback((texto: string) => {
    try {
      liveRef.current?.sendClientContent({
        turns: { role: "user", parts: [{ text: texto }] },
        turnComplete: false,
      });
    } catch {
      /* si no se puede avisar, el tutor sigue hablando igual */
    }
  }, []);

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
        // Ejercicio nuevo, tablero limpio. Lo que estaba dibujado era de lo
        // ANTERIOR, y quedarse ahí confunde: un niño tuvo que preguntar
        // "¿por qué sigue apareciendo lo de las siete macetas si ya no estamos
        // hablando de eso?" (ses_6bccd98babcc).
        //
        // Se hace acá y no pidiéndoselo al tutor porque acá es GRATIS y no se
        // olvida. Que él pueda limpiarla a mano sigue existiendo, para cuando
        // cambia de tema conversando sin pedir ejercicio.
        setCuadro(null);

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
      // ── La pizarra ──────────────────────────────────────────────────────
      //
      // Se resuelven ACÁ, sin tocar el backend: dibujar es cosa del navegador.
      // Un salto a nuestra API serían ~5 ms más por nada, y este es justo el
      // camino donde no se regala latencia.
      //
      // Los dos tools son NON_BLOCKING (ver DECLARACIONES_TOOLS): el tutor
      // sigue hablando mientras esto pasa, que es lo que hace un profesor
      // cuando escribe en el tablero y explica al mismo tiempo.
      case "mostrar_en_pizarra": {
        if (args?.tipo === "limpiar") {
          setCuadro(null);
          setHoja(null);
          return { limpiada: true };
        }
        const cuadro = aCuadro(args);
        if (!cuadro) {
          // Que el tutor SEPA que no se dibujó, y qué hacer. Antes devolvía un
          // "error" pelado y el tutor le decía al niño "ahí te lo estoy
          // mostrando" sobre un tablero vacío (ses_697a02991605): el niño tuvo
          // que contestarle "no veo ninguna pizarra".
          console.warn("[pizarra] no se pudo armar la escena:", args);
          return {
            mostrado: false,
            que_hacer:
              "No se pudo dibujar eso: la pantalla del niño sigue vacía. NO le " +
              "digas que se lo estás mostrando. Probá otra vez con números más " +
              "chicos, o seguí explicándolo de palabra.",
          };
        }
        setHoja(null); // si había una hoja abierta, el tablero la reemplaza
        setCuadro(cuadro);
        return { mostrado: true };
      }

      case "pedir_dibujo": {
        setCuadro(null); // la hoja toma el lugar del tablero
        setHoja(String(args?.consigna ?? "Dibújame lo que estás pensando"));
        return { hoja_abierta: true };
      }

      case "request_camera": {
        // Se abre el VISOR, no se dispara la foto. La primera versión capturaba
        // sola a los 350ms: la cámara parpadeaba, se apagaba, y la foto salía de
        // lo que hubiera enfrente. Nadie fotografía un cuaderno a ciegas.
        //
        // Y no se espera acá al niño: pedir la cámara abre un diálogo de permiso
        // y después hay que acomodar el cuaderno. Un tool call es ~100ms; meter
        // a una persona adentro tumbó la sesión el 18/08 (ses_a46dfd72a562).
        if (!liveRef.current) return { error: "no hay conexión para mandar la foto" };

        setFallaCamara(null);
        void abrirCamara()
          .then((stream) => {
            setCamara(stream);
            console.info("[camara] visor abierto");
            // Que espere en silencio. Sin esto sigue conversando mientras el
            // niño acomoda el cuaderno, y cada pregunta suya le da algo que
            // contestar en vez de tomar la foto: los dos turnos se atropellan.
            avisarAlTutor(
              "[Sistema: se le abrió la cámara y está tomando la foto AHORA. Dile en una frase corta que apunte y toque el botón, y después espera en silencio hasta que llegue la imagen. No le hagas preguntas mientras tanto. No menciones este aviso.]",
            );
          })
          .catch((e: any) => {
            const falla = explicarFallo(e);
            console.warn(`[camara] ${falla.clase}:`, e);
            // En pantalla Y al tutor. Solo en consola era invisible: el niño
            // oía "toca el botón" y no había botón en ningún lado.
            setFallaCamara(falla.paraElNino);
            avisarAlTutor(
              `[Sistema: no se pudo abrir la cámara (${falla.clase}). En la pantalla ya se le explicó qué hacer. Sigue sin la foto: pídele que te lo lea o te lo cuente. No menciones este aviso.]`,
            );
          });

        return medir({
          camara_pedida: true,
          que_hacer:
            "Se le está abriendo la cámara. Dile que apunte al cuaderno y toque " +
            "el botón redondo. Si no se le abre, en la pantalla le aparece qué " +
            "hacer. Sigue hablando mientras acomoda.",
        });
      }
      case "escalate_safety":
        await api.escalateSafety(sesion.sesion_id, args.motivo, args.evidencia);
        return { escalado: true };
      default:
        return { error: `tool desconocido: ${nombre}` };
    }
  }, [avisarAlTutor]);

  /* ── El dibujo del niño ─────────────────────────────────────────────────
     Sale por `sendRealtimeInput`, el MISMO canal que la foto de la cámara.
     Ese camino está verificado con imágenes reales (el 20/08 el tutor leyó las
     letras de una gorra), así que un dibujo es una foto con otra fuente.

     Lo que NO se hace acá es el empujón condicional que sí lleva la cámara: la
     foto llega sin aviso y a veces el modelo se queda esperando, pero acá el
     tutor sabe que pidió un dibujo y que el niño lo está haciendo. */

  const enviarDibujo = useCallback((pngBase64: string) => {
    setHoja(null);
    try {
      liveRef.current?.sendRealtimeInput({
        video: { data: pngBase64, mimeType: "image/png" },
      });
      console.info("[pizarra] dibujo enviado al tutor");
    } catch (e) {
      console.warn("[pizarra] no se pudo enviar el dibujo:", e);
    }
  }, []);

  /* ── La foto ────────────────────────────────────────────────────────────
     La dispara el niño, no un temporizador. */

  const tomarFoto = useCallback(
    (video: HTMLVideoElement) => {
      let foto;
      try {
        foto = capturarCuadro(video);
      } catch (e: any) {
        // El visor NO se cierra: el fallo típico es que el video todavía no
        // tiene dimensiones, y en un segundo sí las tiene. Cerrarlo obligaría
        // al niño a pedirle la cámara al tutor otra vez por algo que se
        // arregla tocando de nuevo.
        const falla = explicarFallo(e);
        console.warn("[camara] no se pudo capturar:", e);
        setAvisoVisor(falla.paraElNino);
        return;
      }

      // POR `sendRealtimeInput`, y esto está verificado con una foto real: el
      // 18/08 el tutor describió correctamente una mano con cinco dedos que
      // llegó por acá.
      //
      // Se probó cambiarlo a `sendClientContent` con la imagen dentro de un
      // turno, razonando que era el canal "correcto" para contenido puntual.
      // El resultado fue que el tutor dejó de ver la foto y se quedaba
      // colgado. Se revirtió.
      //
      // Queda anotado porque el razonamiento sonaba bien y era falso: se
      // cambió algo que YA FUNCIONABA por un argumento sobre canales, sin una
      // sola prueba en contra. Lo verificado le gana a lo que parece correcto.
      try {
        liveRef.current?.sendRealtimeInput({
          video: { data: foto.base64, mimeType: foto.mimeType },
        });
        console.info("[camara] foto enviada al tutor");

        // EMPUJÓN CONDICIONAL. La imagen entra al stream y a veces el modelo
        // arranca solo; cuando arranca, mandarle algo lo interrumpe. Así que se
        // espera, y solo si NO dijo nada se le pide que mire.
        //
        // El error anterior fue empujar siempre: cortó un "A ver," que ya iba
        // en camino y dejó al tutor diciendo que no le llegó la foto.
        hablóTrasFotoRef.current = false;
        setTimeout(() => {
          if (hablóTrasFotoRef.current) {
            console.info("[camara] el tutor ya está contestando: no se empuja");
            return;
          }
          try {
            liveRef.current?.sendClientContent({
              turns: {
                role: "user",
                parts: [{ text: "¿Qué ves en la foto que te mandé?" }],
              },
              turnComplete: true,
            });
            console.info("[camara] no dijo nada: se le pide que mire");
          } catch (e) {
            // La imagen ya llegó igual; el niño puede preguntarle a viva voz.
            console.warn("[camara] no se pudo empujar:", e);
          }
        }, ESPERA_ANTES_DE_EMPUJAR_MS);

        // Confirmar ANTES de cerrar. Al tocar el botón el visor desaparecía de
        // golpe y lo único que quedaba era "cámara desactivada": el niño no
        // tenía cómo saber si la foto salió o si algo se rompió. Un disparo sin
        // acuse de recibo se siente como un error, aunque haya funcionado.
        setFotoEnviada(true);
        setMirandoFoto(true);
        setTimeout(() => {
          setFotoEnviada(false);
          setAvisoVisor(null);
          setFallaCamara(null);
          setCamara((s) => {
            cerrarCamara(s);
            return null;
          });
        }, 700);
        return;
      } catch (e) {
        console.error("[camara] no se pudo enviar:", e);
        avisarAlTutor(
          "[Sistema: la foto NO te llegó. No describas ninguna imagen: dile que no te llegó y que te lo cuente. No menciones este aviso.]",
        );
      }

      setAvisoVisor(null);
      setFallaCamara(null);
      setCamara((s) => {
        cerrarCamara(s);
        return null;
      });
    },
    [avisarAlTutor],
  );

  /**
   * Abrir la cámara sin que el tutor la pida.
   *
   * Sirve para dos cosas. Para el niño: mostrar algo cuando él quiere, sin
   * tener que pedir permiso de hablar. Y para nosotros: separa "la cámara del
   * navegador funciona" de "el flujo con el tutor funciona" — cuando falló el
   * 18/08 no había forma de saber cuál de las dos estaba rota.
   */
  const abrirCamaraManual = useCallback(() => {
    setFallaCamara(null);
    setAvisoVisor(null);
    setMirandoFoto(false);
    void abrirCamara()
      .then((stream) => {
        setCamara(stream);
        console.info("[camara] visor abierto (a pedido del niño)");
        avisarAlTutor(
          "[Sistema: abrió la cámara por su cuenta para mostrarte algo. Pregúntale qué te quiere enseñar. No menciones este aviso.]",
        );
      })
      .catch((e: any) => {
        const falla = explicarFallo(e);
        console.warn(`[camara] ${falla.clase}:`, e);
        setFallaCamara(falla.paraElNino);
      });
  }, [avisarAlTutor]);

  const cancelarFoto = useCallback(() => {
    setFallaCamara(null);
    setAvisoVisor(null);
    setCamara((s) => {
      cerrarCamara(s);
      return null;
    });
    avisarAlTutor(
      "[Sistema: cerró la cámara sin tomar la foto. No insistas: pídele que te lo cuente. No menciones este aviso.]",
    );
  }, [avisarAlTutor]);

  /* ── Soltar recursos ────────────────────────────────────────
     Micrófono, WebSocket y audio. Lo llaman terminar(), onerror y empezar():
     este último para que NUNCA queden dos sesiones vivas a la vez. */

  const soltarRecursos = useCallback(() => {
    setCamara((s) => {
      cerrarCamara(s); // que se acabe la sesión no puede dejarla encendida
      return null;
    });
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

  /* ── La sesión murió del lado del servidor ──────────────────────────────

     Cortar y decirlo. Callar es peor: el niño le sigue hablando a un tutor que
     no puede entregarle nada ni guardar lo que dice, y no tiene cómo saberlo.
     El 18/08 eso duró 99 segundos y se perdió la conversación entera. */

  useEffect(() => {
    if (!sesionMurio) return;
    console.warn("[sesion] el servidor ya no la reconoce: se corta");
    void terminar(true).then(() => {
      setError("Se cerró la sesión. Toca el botón y seguimos.");
      setEstado("error");
      setSesionMurio(false);
    });
  }, [sesionMurio, terminar]);

  /* ── Arranque ──────────────────────────────────────────────────────────── */

  const empezar = useCallback(async (modo: "guiado" | "pedido" = "guiado") => {
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
    setSesionMurio(false);
    avisadoRef.current = false;
    setEstado("conectando");

    try {
      const reproductor = new ReproductorContinuo();
      reproductor.iniciar(); // dentro del gesto del usuario
      reproductor.alTerminar = () => setEstado((e) => (e === "hablando" ? "escuchando" : e));
      reproductorRef.current = reproductor;

      modoRef.current = modo;
      const sesion = await api.abrirSesion(ninoId, modo);
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

            // El modelo empezó a generar. Se marca ACÁ y no al llegar el primer
            // audio: entre que arranca y suena hay un hueco, y en ese hueco la
            // guardia lo veía callado y lo empujaba — cortándole la respuesta.
            // Es lo que hacía que la PRIMERA foto de cada sesión tardara: se
            // comía el timeout entero. Las siguientes ya encontraban el ciclo
            // caliente y contestaban solas.
            if (contenido?.modelTurn || contenido?.generationComplete) {
              hablóTrasFotoRef.current = true;
            }

            const gastados = (mensaje as any).usageMetadata?.totalTokenCount;
            if (gastados) {
              tokensRef.current.suma += gastados;
              tokensRef.current.ultimo = gastados;

              // EL TECHO DE SESIÓN, aplicado en vivo.
              //
              // Existía en config.py desde la fase 1 y solo se miraba al abrir:
              // una sesión podía pasarse y nadie la paraba (ses_88be006b825f
              // llegó a 178.416 con la medición vieja). El navegador es el
              // único que ve el consumo mientras corre, así que el corte vive
              // acá aunque el límite sea del backend.
              //
              // Primero se AVISA y solo después se corta. Cortarle seco a un
              // niño a mitad de una explicación es la peor forma de terminar; y
              // el tutor, si sabe que queda poco, cierra él mismo — que es como
              // termina una clase de verdad.
              const techo = sesion.max_tokens ?? 0;
              const aviso = sesion.avisar_tokens ?? 0;

              if (aviso && gastados >= aviso && !avisadoRef.current) {
                avisadoRef.current = true;
                console.info(`[tokens] ${gastados} — se le pide al tutor que cierre`);
                try {
                  live.sendClientContent({
                    turns: {
                      role: "user",
                      parts: [
                        {
                          text:
                            "[Sistema: se acabó el tiempo de hoy. Cierra tú la " +
                            "conversación como cierras siempre: dile algo concreto " +
                            "que te gustó de cómo trabajó y despídete hasta la " +
                            "próxima. No menciones este aviso.]",
                        },
                      ],
                    },
                    turnComplete: true,
                  });
                } catch {
                  /* si no se puede avisar, igual se corta abajo */
                }
              }

              if (techo && gastados >= techo) {
                console.warn(`[tokens] ${gastados} >= ${techo}: se cierra la sesión`);
                void terminarRef.current?.(false);
              }
              console.info(
                `[tokens] acumulado=${gastados} (suma ingenua ${tokensRef.current.suma})`,
              );
            }

            for (const parte of contenido?.modelTurn?.parts ?? []) {
              if (parte.inlineData?.data) {
                hablóTrasFotoRef.current = true; // no interrumpirlo
                setMirandoFoto(false); // ya está contestando
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
                    if (e instanceof ErrorApi && e.sesionMurio) {
                      // Sin sesión no hay banco: el tutor no puede entregar un
                      // ejercicio ni verificar una respuesta. Seguir sería
                      // dejarlo improvisar sobre la nada.
                      setSesionMurio(true);
                    }
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

      let vozSostenidaMs = 0;

      const { captura } = await abrirMicrofono((muestras, nivel) => {
        setNivelMic(Math.min(1, nivel * 5));

        // ── Barge-in local: el niño manda ──────────────────────────────────
        //
        // Felipe lo dijo dos veces sin que nadie le preguntara (ses_a1b410cf3833):
        //   "te intenté interrumpir y no pude, me tocó esperar a que acabaras
        //    de hablar. Eso está como muy radical."
        //
        // No alcanzaba con el `interrupted` del servidor, y la razón es de
        // relojes: Gemini TERMINA de generar mucho antes de que suene la última
        // sílaba. Los chunks quedan encolados acá y se reproducen varios
        // segundos más. Cuando el niño por fin habla, del lado del servidor no
        // hay turno en curso — no hay nada que interrumpir, así que `interrupted`
        // nunca llega — pero en el parlante el tutor sigue hablando.
        //
        // O sea: la única que sabe que el tutor todavía está hablando es esta
        // máquina. Entonces la decisión se toma acá.
        //
        // El umbral va por encima del eco residual que deja la cancelación del
        // navegador, y se exige que se sostenga: un golpe en la mesa dura un
        // bloque, una sílaba dura varios.
        if (reproductor.hablando && nivel > UMBRAL_BARGE_IN) {
          vozSostenidaMs += (muestras.length / SAMPLE_RATE_ENTRADA) * 1000;
          if (vozSostenidaMs >= MS_PARA_CORTAR) {
            reproductor.detenerTodo();
            setEstado("escuchando");
            vozSostenidaMs = 0;
          }
        } else if (nivel <= UMBRAL_BARGE_IN) {
          vozSostenidaMs = 0;
        }

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

  // El callback de Gemini se arma antes que `terminar`, así que lo alcanza
  // por referencia en vez de por closure.
  terminarRef.current = terminar;

  useEffect(() => () => void terminar(true), [terminar]);

  return {
    estado,
    error,
    tema,
    textoNino,
    textoTutor,
    nivelMic,
    modo: modoRef.current,
    camara,
    fallaCamara,
    avisoVisor,
    fotoEnviada,
    mirandoFoto,
    abrirCamaraManual,
    tomarFoto,
    cancelarFoto,
    cuadro,
    hoja,
    enviarDibujo,
    cancelarDibujo: () => setHoja(null),
    empezar,
    terminar,
  };
}
