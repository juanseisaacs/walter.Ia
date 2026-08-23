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
import { tokenActual } from "../nino";
import { aCuadro, describir } from "../pizarra/desdeElTutor";
import type { Cuadro } from "../pizarra/escenas";

export type Estado = "inicio" | "conectando" | "escuchando" | "hablando" | "error";

/** Qué mostrar cuando la sesión se cierra sin haber llegado a abrirse.
 *
 * El texto lo lee un NIÑO, así que dice qué pasa y qué hacer — nunca un código
 * de error. El detalle técnico va a la consola, que es donde sirve. */
export function mensajeDeCierre(evento: any): string {
  const motivo: string = evento?.reason ?? "";
  if (/credit|quota|billing|exhaust|depleted/i.test(motivo)) {
    // Este es el que costó una tarde: la sesión no abre y no es culpa de nadie
    // acá. Que se pueda LEER en la pantalla en vez de adivinarlo.
    return "El tutor se quedó sin cupo por hoy. Avísale a un adulto.";
  }
  if (/permission|unauthorized|token|expired/i.test(motivo)) {
    return "El enlace ya no sirve. Pídele uno nuevo a un adulto.";
  }
  return "No pude conectarme con el tutor. Revisa el internet y vuelve a intentar.";
}

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
/** Cuánto se calla el micro esperando que el tutor mire una imagen.

    Es un PISO de seguridad, no el caso normal: lo normal es que conteste en
    menos y el micro vuelva ahí mismo. Dos segundos porque el niño que acaba de
    mandar un dibujo suele quedarse mirando la pantalla — y si igual habla, el
    VAD lo toma en cuanto vuelve. */
export const MS_ESPERANDO_MIRADA = 2000;

/** Lo que viaja junto al dibujo del niño. Es prompt, y por eso se prueba. */
export const AVISO_DEL_DIBUJO =
  "[Sistema: este es el dibujo que acaba de hacer el niño. ARRANCA diciendo " +
  "qué ves —la forma, los trazos, hacia dónde van— y recién después dile si " +
  "está o no está bien. Si le pediste una letra y dibujó otra, o le quedó al " +
  "revés, o no se entiende, DÍSELO: corregir es para lo que estás. Un 'te " +
  "quedó súper bien' sin haber descrito nada le enseña que da igual cómo lo " +
  "haga. No menciones este aviso.]";

const MS_PARA_CORTAR = 200;

/**
 * Cuánto se le aguanta al tutor sin decir nada después de que el niño terminó
 * de hablar, antes de darlo por mudo.
 *
 * Diez segundos es una eternidad en una conversación —el tutor real contesta
 * en uno o dos— y esa holgura es a propósito: este reloj no está para apurarlo,
 * está para que un silencio que ya no va a terminar no dure para siempre.
 */
export const MS_MUDEZ = 10_000;

/** Cuántos empujones antes de aceptar que no vuelve. */
export const EMPUJONES_ANTES_DE_RENDIRSE = 2;

/** El empujón. Es prompt —lo lee el modelo—, y por eso se prueba. */
export const AVISO_DE_MUDEZ =
  "[Sistema: el niño terminó de hablar hace rato y tú no has dicho nada. " +
  "Retoma tú AHORA: dile en una frase corta que se te fue el sonido un " +
  "momentico y pregúntale en qué iban. No inventes por qué pasó y no " +
  "menciones este aviso.]";

/** Lo que queda escrito en la transcripción cuando el tutor se calla.
 *
 * Sin esto la mudez es el único fallo del producto que no deja rastro: la
 * transcripción se ve igual que una donde el niño se aburrió y se fue. Va con
 * el prefijo entre corchetes que ya usan las marcas de sistema, así el Analista
 * la lee como evento y no como algo que alguien dijo. */
export const MARCA_DE_MUDEZ = "[el tutor no contestó: se quedó callado]";

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
  const avisadoRef = useRef(false);

  const sesionRef = useRef<SesionAbierta | null>(null);
  const liveRef = useRef<any>(null);
  const micRef = useRef<CapturaMicrofono | null>(null);
  const reproductorRef = useRef<ReproductorContinuo | null>(null);
  /** Espejo de `cuadro`: el tool corre en un closure y el estado le llega viejo. */
  const cuadroRef = useRef<Cuadro | null>(null);
  /** Cuándo se transcribió la última sílaba del niño. Para medir la espera. */
  const callóRef = useRef<number | null>(null);
  /** Puente al efecto de la sesión, que se monta una vez y no ve los callbacks. */
  const cerrarTurnoAcumuladoRef = useRef<(() => void) | null>(null);
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
  /** ¿El cierre que viene lo pedimos nosotros? Ver `terminar()` y `onclose`. */
  const cerrandoRef = useRef(false);
  /** Mientras se espera que el tutor mire una imagen, el micro no manda nada.
      Ver `mostrarleAlTutor`. */
  const esperandoMiradaRef = useRef(false);
  /** Los dos relojes de la sesión: avisar al 90% del tiempo, cortar al 100%. */
  const relojesRef = useRef<ReturnType<typeof setTimeout>[]>([]);

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
  /**
   * Vuelca a la transcripción lo que va acumulado, y la deja en orden.
   *
   * Normalmente lo hace `turnComplete`. Pero una imagen del niño se encola
   * apenas sale, y si el turno anterior todavía no cerró se cuela ANTES: en
   * `ses_cdb0b7fae50f` la marca "[le muestra un dibujo]" quedó dos turnos
   * arriba de la hoja que lo produjo. La transcripción es lo único que se lee
   * después —la usa el Analista y la usamos nosotros para auditar—, y una
   * transcripción desordenada hace concluir cosas que no pasaron.
   */
  const cerrarTurnoAcumulado = useCallback(() => {
    const dichoNino = acumNinoRef.current;
    const dichoTutor = acumTutorRef.current;
    acumNinoRef.current = "";
    acumTutorRef.current = "";
    if (dichoNino) encolar({ quien: "nino", texto: dichoNino });
    if (dichoTutor) encolar({ quien: "tutor", texto: dichoTutor });
    setTextoNino("");
  }, [encolar]);

  cerrarTurnoAcumuladoRef.current = cerrarTurnoAcumulado;

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

  /* ── El vigilante de la mudez ───────────────────────────────────────────

     PASÓ DE VERDAD, `ses_87aba17c8c6c` (22/08). El niño dictó su tarea —"5 + 5,
     3 - 4, 8 - 7"— y el tutor no volvió a hablar nunca. La sesión seguía viva:
     el micrófono mandaba, Gemini transcribía, y en la transcripción quedó el
     niño solo, preguntándole a nadie *"¿por qué no estás aquí? ¿qué te pasó?
     ¿por qué te fuiste?"*. En la pantalla no decía nada. En nuestros logs
     tampoco: el backend no está en el camino del audio y no se enteró.

     La causa no se pudo determinar —la única evidencia vivía en la consola del
     navegador, que se cerró con la pestaña—, y ese es justamente el punto: hay
     por lo menos tres formas conocidas de que el modelo se quede sin hablar
     (una tool que nunca recibe respuesta, un turno que el VAD no cierra, un
     socket que se murió callado), todas se ven IGUAL desde acá, y ninguna se
     arregla sola. Lo que faltaba no era la causa: era que alguien mirara el
     reloj.

     Dos fases, y la segunda importa tanto como la primera:
       1. Empujar. Un turno de texto que le pide retomar. Destraba el caso del
          VAD y el del turno perdido, que son los baratos.
       2. Rendirse. Si tras `EMPUJONES_ANTES_DE_RENDIRSE` sigue mudo, se cierra
          la sesión y se le DICE al niño. Un tutor que no vuelve es malo; un
          niño hablándole a una pantalla que no le avisa es peor. Es la misma
          regla que hizo hablar a `onclose`.

     Y las dos dejan marca en la transcripción: ver `MARCA_DE_MUDEZ`. */

  const mudezRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const empujonesRef = useRef(0);

  /** El tutor dio señales de vida: audio, turno cerrado o un tool pedido. */
  const tutorContesto = useCallback(() => {
    if (mudezRef.current) {
      clearTimeout(mudezRef.current);
      mudezRef.current = null;
    }
    empujonesRef.current = 0;
  }, []);

  /** Arranca (o reinicia) la cuenta. La llama todo lo que espera respuesta. */
  const vigilarMudez = useCallback(() => {
    if (mudezRef.current) clearTimeout(mudezRef.current);

    mudezRef.current = setTimeout(() => {
      mudezRef.current = null;
      if (!liveRef.current) return; // la sesión ya no existe: no hay a quién empujar

      if (empujonesRef.current >= EMPUJONES_ANTES_DE_RENDIRSE) {
        console.error("[mudez] el tutor no volvió: se cierra la sesión");
        cerrarTurnoAcumulado();
        encolar({ quien: "tutor", texto: MARCA_DE_MUDEZ });
        void terminarRef.current?.(true).then(() => {
          // Lo lee un niño: qué pasó y qué hacer, sin código de error.
          setError("El tutor se quedó callado. Toca para volver a empezar.");
          setEstado("error");
        });
        return;
      }

      empujonesRef.current += 1;
      console.warn(`[mudez] ${MS_MUDEZ} ms sin respuesta: empujón ${empujonesRef.current}`);
      // Primero se cierra lo que hay acumulado, para que la marca quede DESPUÉS
      // del turno que se quedó sin contestar y no encima de él.
      cerrarTurnoAcumulado();
      encolar({ quien: "tutor", texto: MARCA_DE_MUDEZ });
      try {
        liveRef.current.sendClientContent({
          turns: { role: "user", parts: [{ text: AVISO_DE_MUDEZ }] },
          turnComplete: true,
        });
      } catch (e) {
        console.warn("[mudez] no se pudo empujar:", e);
      }
      vigilarMudezRef.current?.(); // y se sigue mirando el reloj
    }, MS_MUDEZ);
  }, [cerrarTurnoAcumulado, encolar]);

  /** Para llamarse a sí misma sin depender del orden de los closures. */
  const vigilarMudezRef = useRef<(() => void) | null>(null);
  vigilarMudezRef.current = vigilarMudez;

  /**
   * Le muestra una imagen al tutor. La ÚNICA puerta: dibujo y foto entran igual.
   *
   * La imagen va DENTRO del turno, junto al texto que la acompaña, y no por
   * `sendRealtimeInput({video})`. Eso último es un canal de streaming de
   * cámara: el frame suelto se descarta y el modelo contesta describiendo lo
   * que esperaba ver. Medido el 21/08 con controles:
   *
   *   | se le mandó        | por realtime            | dentro del turno        |
   *   |--------------------|-------------------------|-------------------------|
   *   | un 7 gigante       | "un círculo, dos líneas"| "veo el número siete"   |
   *   | un triángulo       | "un círculo, dos líneas"| —                       |
   *   | cuaderno con 8+5   | "veo 5 + 3 y 10 - 4"    | "ocho más cinco"        |
   *
   * Cuatro de cuatro inventadas por realtime; exactas por turno. La respuesta
   * era IDÉNTICA con una línea y con dos: no veía mal, no veía.
   *
   * El código decía lo contrario ("verificado: leyó una gorra, contó cinco
   * dedos") y por eso el cambio se había revertido una vez. Una mano tiene
   * cinco dedos siempre: esa verificación no distinguía ver de adivinar. Para
   * eso está el control con el 7 — nadie adivina un 7 cuando espera una torta.
   *
   * El cuelgue de aquel intento sí era real, y era otra cosa: si el modelo YA
   * está hablando, el turno con la imagen queda detrás del anterior y la
   * respuesta no llega nunca. Por eso se corta antes.
   */
  const mostrarleAlTutor = useCallback((jpegBase64: string, aviso: string): boolean => {
    const live = liveRef.current;
    if (!live) return false;
    try {
      // Si está hablando, su turno tapa al nuestro. Mismo corte que el barge-in.
      reproductorRef.current?.detenerTodo();

      // Y SE CALLA EL MICRÓFONO hasta que conteste.
      //
      // El micro manda audio sin parar, también cuando nadie habla. Para el VAD
      // del servidor ese flujo mantiene ABIERTO el turno del niño, así que el
      // `turnComplete` de la imagen no dispara nada: el modelo sigue esperando.
      //
      // Se vio entero en ses_6b430731226f. El niño mandó una letra, el tutor no
      // volvió, el niño tuvo que decir "ya la envié" — y recién ahí, al cerrar
      // el VAD por su voz, el modelo contestó: "¡Uy, ya la veo! Te quedó súper
      // bien". Nunca había mirado nada; le contestó a la voz.
      esperandoMiradaRef.current = true;
      live.sendClientContent({
        turns: {
          role: "user",
          parts: [
            { inlineData: { mimeType: "image/jpeg", data: jpegBase64 } },
            { text: aviso },
          ],
        },
        turnComplete: true,
      });
      console.info(`[imagen] enviada dentro del turno (${jpegBase64.length} b64)`);

      // Acá el niño se calla a propósito (el micro se apaga), así que no va a
      // llegar transcripción que arranque la cuenta. Se arranca a mano: este es
      // justo el camino donde el tutor ya se quedó mudo dos veces
      // (ses_6b430731226f, ses_50d5fa00b5d8).
      vigilarMudez();

      // Y VUELVE PASE LO QUE PASE.
      //
      // El micro se reabre en cuanto el tutor arranca a hablar (lo hace
      // `onmessage`), pero si no arranca nunca el niño se queda MUDO — peor que
      // el cuelgue que esto viene a arreglar. Este reloj es el piso: dos
      // segundos y el micro vuelve, haya contestado o no.
      const reloj = setTimeout(() => {
        if (esperandoMiradaRef.current) {
          console.warn("[imagen] el tutor no contestó en 2 s: se reabre el micrófono");
          esperandoMiradaRef.current = false;
        }
      }, MS_ESPERANDO_MIRADA);
      relojesRef.current.push(reloj);
      return true;
    } catch (e) {
      esperandoMiradaRef.current = false;
      console.warn("[imagen] no se pudo enviar:", e);
      return false;
    }
  }, [vigilarMudez]);

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
      case "verify_language": {
        // El gemelo del de arriba, para lectura y escritura. Sin esto el tutor
        // llamaba a `verify_arithmetic` en una sesión de sílabas —seis veces en
        // ses_50d5fa00b5d8—, recibía "no puedo juzgar esto" y juzgaba él: a un
        // niño que separó "prim-o" le contestó "¡Perfecto!". Lo cazó el niño:
        // «podrías revisar una forma de calificar mejor».
        return medir(
          await api.verifyLanguage(
            String(args.palabra ?? ""),
            String(args.que ?? ""),
            String(args.respuesta_nino ?? ""),
            String(args.palabra2 ?? ""),
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
          cuadroRef.current = null;
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
        const habia = cuadroRef.current !== null;
        setCuadro(cuadro);
        cuadroRef.current = cuadro;
        // Se le devuelve QUÉ quedó en pantalla, no un "ok". Con el "ok" pelado
        // el tutor afirmaba de memoria: mandó un medio, después un tercio, y
        // preguntó "¿ahí ya puedes ver las dos?" con una sola en el tablero.
        return {
          mostrado: true,
          en_pantalla: describir(cuadro),
          ...(habia
            ? {
                ojo:
                  "La pizarra muestra UNA cosa a la vez: esto borró lo que " +
                  "había antes. Si necesitas que el niño vea dos fracciones " +
                  "juntas, mándalas en UNA sola llamada con `comparar_con`.",
              }
            : {}),
        };
      }

      case "pedir_dibujo": {
        setCuadro(null); // la hoja toma el lugar del tablero
        cuadroRef.current = null;
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

  /* ── El dibujo del niño ───────────────────────────────────────────────── */

  const enviarDibujo = useCallback(
    (jpegBase64: string) => {
      setHoja(null);
      const salio = mostrarleAlTutor(
        jpegBase64,
        AVISO_DEL_DIBUJO,
      );

      // Queda en la transcripción, que es lo único que se puede leer después de
      // la sesión. Sin esto, "el tutor dijo que estaba bien" no se distingue de
      // "el tutor nunca recibió nada". Se cierra primero el turno en curso para
      // que la marca no se cuele antes de la hoja que la produjo.
      if (salio) {
        cerrarTurnoAcumulado();
        encolar({ quien: "nino", texto: "[le muestra al tutor un dibujo que hizo]" });
      }
    },
    [mostrarleAlTutor, encolar, cerrarTurnoAcumulado],
  );

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

      // Misma puerta que el dibujo: la imagen va DENTRO del turno.
      //
      // Acá vivía el argumento contrario —"verificado: leyó una gorra, contó
      // cinco dedos"— y sostenía todo el camino de la cámara. Era falso: el
      // 21/08 se le mostró un cuaderno con "8 + 5" y "12 - 7" y contestó "veo
      // 5 + 3 y 10 - 4". Un tutor de matemáticas inventándole al niño la
      // cuenta que trajo es lo peor que puede pasar acá.
      //
      // Se va con esto el EMPUJÓN CONDICIONAL: existía porque la imagen entraba
      // al stream sin abrir turno y a veces el modelo se quedaba esperando. Un
      // turno completo dispara la respuesta solo, así que el timeout de 1200 ms
      // y su guardia sobran — y con ellos se va la espera de la primera foto.
      if (!mostrarleAlTutor(foto.base64, "Mira lo que te estoy mostrando y dime qué ves.")) {
        avisarAlTutor(
          "[Sistema: la foto NO te llegó. No describas ninguna imagen: dile que no te llegó y que te lo cuente. No menciones este aviso.]",
        );
        setAvisoVisor(null);
        setFallaCamara(null);
        setCamara((st) => {
          cerrarCamara(st);
          return null;
        });
        return;
      }

      // Confirmar ANTES de cerrar. Al tocar el botón el visor desaparecía de
      // golpe y lo único que quedaba era "cámara desactivada": el niño no tenía
      // cómo saber si la foto salió o si algo se rompió. Un disparo sin acuse de
      // recibo se siente como un error, aunque haya funcionado.
      setFotoEnviada(true);
      setMirandoFoto(true);
      setTimeout(() => {
        setFotoEnviada(false);
        setAvisoVisor(null);
        setFallaCamara(null);
        setCamara((st) => {
          cerrarCamara(st);
          return null;
        });
      }, 700);
    },
    [mostrarleAlTutor, avisarAlTutor],
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
    // Un reloj que sobrevive a la sesión corta la SIGUIENTE a destiempo.
    for (const reloj of relojesRef.current) clearTimeout(reloj);
    relojesRef.current = [];
    // Y esta bandera menos: dejaría el micrófono mudo en la sesión siguiente.
    esperandoMiradaRef.current = false;
    // El vigilante de la mudez tampoco sobrevive: cerraría la sesión siguiente.
    if (mudezRef.current) {
      clearTimeout(mudezRef.current);
      mudezRef.current = null;
    }
    empujonesRef.current = 0;
  }, []);

  /* ── Cierre ────────────────────────────────────────────────────────────── */

  const terminar = useCallback(
    async (interrumpida = false) => {
      // Este cierre lo pedimos NOSOTROS: que `onclose` no lo confunda con una
      // sesión que se murió sola. Se marca antes de soltar el socket, porque
      // soltarlo es lo que dispara `onclose`.
      cerrandoRef.current = true;
      soltarRecursos();

      const sesion = sesionRef.current;
      if (sesion) {
        /* Lo que se estaba diciendo JUSTO cuando se cerró también cuenta.
           Hasta el 22/08 estas dos líneas se limpiaban más abajo sin encolarse,
           así que el último turno de cada sesión se perdía siempre — y en una
           sesión corta ese turno puede ser el único que hubo. Se vio con el
           e2e: el tutor saludaba, se le daba a Terminar, y la transcripción
           quedaba en 0 bytes pese a que había hablado.

           Se empujan a mano en vez de llamar a `cerrarTurnoAcumulado()` porque
           ese dispara su propio reporte en paralelo si llega al lote, y acá
           interesa que salga todo junto en la última llamada. */
        if (acumNinoRef.current) {
          pendientesRef.current.push({ quien: "nino", texto: acumNinoRef.current });
        }
        if (acumTutorRef.current) {
          pendientesRef.current.push({ quien: "tutor", texto: acumTutorRef.current });
        }

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
      cerrandoRef.current = false;
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
      const sesion = await api.abrirSesion(ninoId, modo, tokenActual());
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

            // Contestó: el niño puede volver a hablar. Ver `mostrarleAlTutor`.
            if (esperandoMiradaRef.current && contenido) {
              esperandoMiradaRef.current = false;
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
                // EL NÚMERO QUE FALTABA. "Se siente lento" se discutió tres
                // veces sin un solo dato, y las tres el problema estaba en otro
                // lado. Esto mide lo que el niño de verdad siente: desde su
                // última sílaba hasta que el tutor suena. Adentro va el VAD
                // (`silencioMs`), la red y el modelo — si el número es alto y
                // se parece al VAD, el silencio lo estamos poniendo nosotros.
                if (callóRef.current !== null) {
                  const espera = Math.round(performance.now() - callóRef.current);
                  callóRef.current = null;
                  console.info(`[latencia] ${espera} ms de silencio antes de contestar`);
                }
                setMirandoFoto(false); // ya está contestando
                setEstado("hablando");
                tutorContesto();
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
              // El reloj del silencio. La última sílaba transcripta es lo más
              // cerca que estamos de "el niño terminó de hablar".
              callóRef.current = performance.now();
              // Y el que mira si el tutor contesta. Se reinicia con cada sílaba:
              // mientras el niño habla no hay nada que esperar.
              vigilarMudez();
            }

            if (contenido?.turnComplete) {
              tutorContesto();
              const dichoTutor = acumTutorRef.current;

              // Lo que el Analista va a LEER, visible en el momento. La
              // transcripción es su único insumo: un "dos" que llega como "32"
              // se ve acá y no dos días después, en la ficha del niño.
              if (acumNinoRef.current) console.info(`[niño] ${acumNinoRef.current}`);
              if (dichoTutor) console.info(`[tutor] ${dichoTutor}`);

              cerrarTurnoAcumuladoRef.current?.();
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
              // Pedir una herramienta ES contestar: el turno sigue vivo. Y el
              // tope de `MS_TOPE_TOOL` garantiza que la respuesta sale, así que
              // la cuenta se reinicia recién cuando el modelo vuelva a hablar.
              tutorContesto();
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
          onclose: (evento: any) => {
            // Google manda POR QUÉ cerró, y hasta el 22/08 lo tirábamos: un
            // `onclose` sin `onerror` previo devolvía la pantalla a "inicio" en
            // silencio. Cuando se acabaron los créditos de la cuenta, el niño
            // tocaba el botón, veía "Un segundito...", y volvía al principio —
            // una y otra vez, sin que nadie se enterara de nada. El motivo real
            // («1011 Your prepayment credits are depleted») venía en este
            // evento y no lo leía nadie.
            const motivo = evento?.reason || "";
            if (motivo) console.error("[live] la sesión se cerró:", evento?.code, motivo);

            if (cerrandoRef.current) return; // lo pedimos nosotros

            setEstado((estadoPrevio) => {
              if (estadoPrevio === "error" || estadoPrevio === "inicio") return estadoPrevio;

              // CUALQUIER cierre que no lo haya pedido el niño se dice.
              //
              // La primera versión de esto solo cubría "conectando" —el que
              // nunca abre—, y dejaba pasar el peor caso: la sesión que se
              // muere A MITAD. Pasó en ses_50d5fa00b5d8: el niño mandó un
              // dibujo, el tutor no volvió nunca, y la pantalla no dijo nada.
              // El niño se quedó esperando a alguien que ya no estaba.
              //
              // `terminar()` pone el estado en "inicio" ANTES de cerrar el
              // socket, así que un cierre pedido por el niño ya salió arriba.
              soltarRecursos();
              setError(mensajeDeCierre(evento));
              return "error";
            });
          },
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

        // Callado mientras el tutor mira una imagen: este flujo le mantendría
        // el turno abierto y no contestaría nunca. Ver `mostrarleAlTutor`.
        if (esperandoMiradaRef.current) return;

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

      /* QUE HABLE EL TUTOR PRIMERO.
         Hasta el 22/08 acá no pasaba nada: la sesión quedaba abierta esperando
         a que el niño rompiera el silencio. Medido sobre 71 transcripciones
         reales — el niño abre la conversación en las 52 que tienen contenido,
         el tutor en NINGUNA, y 19 quedaron vacías. Una de cada cuatro sesiones
         moría antes de la primera palabra: el chico entraba, veía una cara que
         no le decía nada, y se iba.

         El texto no está acá a propósito: viene del backend (`sesion.apertura`)
         y vive en `knowledge/prompts/apertura*.md`, distinto el primer día que
         los siguientes. Cambiar cómo saluda el tutor no puede pedir un build
         del front.

         Va DESPUÉS del micrófono: si el niño contesta encima del saludo, el
         barge-in ya está escuchando. Y si esto falla, la sesión sigue viva —
         un saludo perdido es mucho menos grave que no poder hablar. */
      if (sesion.apertura) {
        try {
          live.sendClientContent({
            turns: { role: "user", parts: [{ text: sesion.apertura }] },
            turnComplete: true,
          });
        } catch (e) {
          console.warn("[apertura] el tutor no pudo saludar primero:", e);
        }
      }

      /* EL RELOJ DE LA SESIÓN.
         `MAX_MINUTOS_SESION = 45` existía desde la fase 5 con test propio y
         cero llamadores: nunca cortó nada. El backend ya manda los dos
         números; el navegador es el único que puede cerrar a tiempo, igual
         que con el techo de tokens.

         No es una restricción arbitraria: a los 45 minutos un chico de 7 años
         hace rato que no está aprendiendo. Y una sesión abierta y olvidada
         sigue gastando — hay una de 117,7 minutos con cero turnos en la base.

         Mismo criterio que los tokens: primero se le pide al tutor que cierre
         él, y solo después se corta. Cortarle seco a un niño a mitad de una
         explicación es la peor forma de terminar. */
      const avisarMin = sesion.avisar_minutos ?? 0;
      const maxMin = sesion.max_minutos ?? 0;

      if (avisarMin > 0) {
        relojesRef.current.push(
          setTimeout(
            () => {
              console.info(`[tiempo] ${avisarMin} min — se le pide al tutor que cierre`);
              try {
                liveRef.current?.sendClientContent({
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
                /* si no se puede avisar, el corte de abajo llega igual */
              }
            },
            avisarMin * 60_000,
          ),
        );
      }

      if (maxMin > 0) {
        relojesRef.current.push(
          setTimeout(() => {
            console.warn(`[tiempo] ${maxMin} min: se cierra la sesión`);
            void terminarRef.current?.(false);
          }, maxMin * 60_000),
        );
      }
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
  }, [ninoId, atenderTool, encolar, terminar, soltarRecursos, vigilarMudez, tutorContesto]);

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
