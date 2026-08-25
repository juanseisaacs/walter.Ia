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

import {
  ErrorApi,
  MI_BUILD,
  api,
  recargarSiEstoyViejo,
  type Ejercicio,
  type SesionAbierta,
  type Turno,
} from "../api";
import {
  MIME_ENTRADA,
  ReproductorContinuo,
  SAMPLE_RATE_ENTRADA,
  aPcm16Base64,
  silencioPcm16Base64,
} from "./audio";
import { abrirCamara, capturarCuadro, cerrarCamara, explicarFallo } from "./camara";
import { pasarPorLaCola, sigueEnDuda, vozSostenida } from "./colaDelMicrofono";
import { Diario } from "./diario";
import {
  AVISO_DEL_DIBUJO,
  AVISO_DE_MUDEZ,
  BLOQUES_RETENIDOS,
  EMPUJONES_ANTES_DE_RENDIRSE,
  MARCA_DE_MUDEZ,
  MARCA_DE_SORDERA,
  MARCA_DE_VOZ_MUDA,
  MS_COLA_ECO,
  MS_ENTRE_CHEQUEOS_DE_VOZ,
  MS_ESPERANDO_MIRADA,
  MS_ESPERA_CORTE_SERVIDOR,
  MS_MUDEZ,
  MS_MUDEZ_TRAS_EMPUJON,
  MS_PARA_CORTAR,
  MS_RETENER_APERTURA,
  MS_SIN_EL_NINO,
  MS_VOZ_MUDA,
  MS_VOZ_SIN_ACUSE,
  RECONEXIONES_ANTES_DE_RENDIRSE,
  TURNOS_POR_REPORTE,
  UMBRAL_BARGE_IN,
} from "./perillas";
import { abrirMicrofono, type CapturaMicrofono } from "./microfono";
import { tokenActual } from "../nino";
import { aCuadro, describir } from "../pizarra/desdeElTutor";
import type { Cuadro } from "../pizarra/escenas";

export type Estado = "inicio" | "conectando" | "escuchando" | "hablando" | "error";

// Se re-exportan: las perillas se mudaron a `perillas.ts` (ver el porqué allá),
// pero varios tests y el medidor de fluidez las venían leyendo desde acá.
export * from "./perillas";

/** Qué mostrar cuando la sesión se cierra sin haber llegado a abrirse.
 *
 * El texto lo lee un NIÑO, así que dice qué pasa y qué hacer — nunca un código
 * de error. El detalle técnico va a la consola, que es donde sirve. */
export function mensajeDeCierre(evento: any): string {
  const motivo: string = evento?.reason ?? "";
  if (/credit|quota|billing|exhaust|depleted/i.test(motivo)) {
    // Este es el que costó una tarde: la sesión no abre y no es culpa de nadie
    // acá. Que se pueda LEER en la pantalla en vez de adivinarlo.
    // NO dice "sin cupo por hoy", que es lo que decía antes. Esa frase es
    // indistinguible del tope diario del niño —tres sesiones, por diseño y
    // saludable— cuando esto es lo contrario: el producto CAÍDO por
    // facturación. El 24/08 esa ambigüedad mandó a buscar un bug que no
    // existía mientras los cuatro enlaces entregados fallaban por créditos
    // agotados de Google. Un mensaje que se confunde con lo normal esconde lo
    // grave.
    return "Al tutor se le acabó la batería. Un adulto tiene que recargarla.";
  }
  if (/permission|unauthorized|token|expired/i.test(motivo)) {
    return "El enlace ya no sirve. Pídele uno nuevo a un adulto.";
  }
  return "No pude conectarme con el tutor. Revisa el internet y vuelve a intentar.";
}


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
  /** ¿La hoja abierta ya se la mandó al tutor? Cambia los botones y evita que
      el niño crea que no salió. Ver `enviarDibujo`. */
  const [dibujoEnviado, setDibujoEnviado] = useState(false);
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
  const terminarRef = useRef<
    ((interrumpida?: boolean, motivo?: string) => Promise<void>) | null
  >(null);
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
  /** Hasta cuándo se retiene el micro esperando el saludo (`Date.now()` + techo).
      0 = no se está esperando. Ver `MS_RETENER_APERTURA`. */
  const retenerHastaRef = useRef(0);
  /** Cuándo el barge-in calló al tutor (`Date.now()`), o 0 si no hay nada
      abortado. Mientras esté puesto, el audio que siga llegando de ESE turno no
      va al parlante. Ver `MS_ESPERA_CORTE_SERVIDOR`. */
  const turnoAbortadoRef = useRef(0);
  /** Lo que llegó del tutor después de que lo callaron, sin reproducir. Vuelve
      si el servidor no confirma el corte — o sea, si el barge-in se equivocó. */
  const enDudaRef = useRef<string[]>([]);
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
  /** Reconexiones gastadas en esta sesión. A diferencia de los empujones, NO se
      reinicia cuando el tutor vuelve: ver `RECONEXIONES_ANTES_DE_RENDIRSE`. */
  const reconexionesRef = useRef(0);
  /** Para llamar a `empezar` desde acá sin depender del orden de declaración:
      `empezar` se define mucho más abajo y necesita a `vigilarMudez`. */
  const empezarRef = useRef<((modo: "guiado" | "pedido") => Promise<void>) | null>(null);
  /** ¿Este arranque es una reconexión sobre la sesión que ya está viva?
   *
   *  Lo pone `vigilarMudez` justo antes de reintentar. Cambia tres cosas de
   *  `empezar` y ninguna más: de dónde sale el token, que la sesión del backend
   *  NO se cierre, y que el banco de ejercicios no se pise. */
  const reconectandoRef = useRef(false);
  /** Cuándo se oyó al niño por última vez. Ver `MS_SIN_EL_NINO`. */
  const ultimaVozRef = useRef(Date.now());
  /** Espejos de `hoja` y de la cámara, para leerlos desde un `setInterval` sin
      volver a montarlo en cada cambio. */
  const hojaRef = useRef<string | null>(null);
  const camaraAbiertaRef = useRef(false);
  /** Cuánta voz del niño salió sin que volviera una sola sílaba transcripta.
      Ver `MS_VOZ_SIN_ACUSE`: es el vigilante del lado del niño. */
  const vozSinAcuseRef = useRef(0);
  /** Cuántas veces se intentó destrabar el oído del tutor en esta sesión. */
  const rescatesDeOidoRef = useRef(0);
  /** El diario de la voz. Ver `diario.ts`: nunca en el camino del audio. */
  const diarioRef = useRef<Diario | null>(null);
  /** El reloj del vigilante de la voz. Ver `MS_VOZ_MUDA`. */
  const vozRef = useRef<ReturnType<typeof setInterval> | null>(null);
  /** Cuántas veces se intentó recuperar la voz en esta sesión. Al segundo
      intento fallido se le dice al niño: seguir intentando en silencio es
      exactamente lo que lo dejaba media sesión hablándole a nadie. */
  const rescatesDeVozRef = useRef(0);

  /** Anota en el diario de la voz. Barato y a prueba de todo: si no hay diario
      —la sesión todavía no abrió— se pierde el evento y no pasa nada. */
  const anotar = useCallback((evento: { t: string; [k: string]: unknown }) => {
    diarioRef.current?.anota(evento);
  }, []);

  /** El tutor dio señales de vida: audio, turno cerrado o un tool pedido. */
  const tutorContesto = useCallback(() => {
    if (mudezRef.current) {
      clearTimeout(mudezRef.current);
      mudezRef.current = null;
    }
    empujonesRef.current = 0;
  }, []);

  /** Arranca (o reinicia) la cuenta. La llama todo lo que espera respuesta. */
  const vigilarMudez = useCallback((espera: number = MS_MUDEZ) => {
    if (mudezRef.current) clearTimeout(mudezRef.current);

    mudezRef.current = setTimeout(() => {
      mudezRef.current = null;
      if (!liveRef.current) return; // la sesión ya no existe: no hay a quién empujar

      if (empujonesRef.current >= EMPUJONES_ANTES_DE_RENDIRSE) {
        cerrarTurnoAcumulado();
        encolar({ quien: "tutor", texto: MARCA_DE_MUDEZ });

        // ── ANTES DE RENDIRSE, RECONECTAR ────────────────────────────────
        //
        // El empujón destraba al modelo cuando el canal está sano. Si tras el
        // empujón sigue mudo, lo más probable es que el canal esté roto — y un
        // canal roto no se arregla hablándole más fuerte.
        //
        // Hasta acá esto cerraba la sesión y le ponía al niño «toca para
        // volver a empezar». Empezar de nuevo le costaba TODO: los ejercicios
        // cargados, los turnos, la habilidad del día y el hilo de la
        // conversación. En `ses_02805f3edba1` Juan quedó con dos mudeces y la
        // pantalla muerta después de pedirle una rima — «te estoy esperando».
        //
        // La sesión del backend está sana: lo único roto es el socket. Se pide
        // un token nuevo sobre la MISMA sesión y el tutor vuelve sabiendo de
        // qué hablaban (`SessionOrchestrator._recap`).
        //
        // UNA SOLA VEZ. `reconexionesRef` no se reinicia con `tutorContesto`, a
        // diferencia de los empujones: si el canal se cae dos veces en la misma
        // sesión, el problema no es el socket y reintentar sería dejar al niño
        // en un ciclo de silencios. Ahí sí se cierra y se le dice.
        if (reconexionesRef.current < RECONEXIONES_ANTES_DE_RENDIRSE) {
          reconexionesRef.current += 1;
          console.warn(`[mudez] canal roto: reconexión ${reconexionesRef.current}`);
          anotar({ t: "reconexion", intento: reconexionesRef.current });
          reconectandoRef.current = true;
          setEstado("conectando");
          void empezarRef.current?.(modoRef.current)
            .catch((e) => {
              console.error("[mudez] la reconexión falló:", e);
              void terminarRef.current?.(true, "reconexion_fallo").then(() => {
                setError("El tutor se quedó callado. Toca para volver a empezar.");
                setEstado("error");
              });
            })
            .finally(() => {
              reconectandoRef.current = false;
            });
          return;
        }

        console.error("[mudez] el tutor no volvió ni reconectando: se cierra");
        void terminarRef.current?.(true, "mudez").then(() => {
          // Lo lee un niño: qué pasó y qué hacer, sin código de error.
          setError("El tutor se quedó callado. Toca para volver a empezar.");
          setEstado("error");
        });
        return;
      }

      empujonesRef.current += 1;
      console.warn(`[mudez] ${MS_MUDEZ} ms sin respuesta: empujón ${empujonesRef.current}`);
      anotar({ t: "mudez", empujon: empujonesRef.current });
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
      vigilarMudezRef.current?.(MS_MUDEZ_TRAS_EMPUJON); // y se sigue mirando el reloj
    }, espera);
  }, [cerrarTurnoAcumulado, encolar, anotar]);

  /** Para llamarse a sí misma sin depender del orden de los closures. */
  const vigilarMudezRef = useRef<((espera?: number) => void) | null>(null);
  vigilarMudezRef.current = vigilarMudez;

  /**
   * El niño lleva segundos hablando y no volvió ni una sílaba. Destrabar.
   *
   * Primero el flush, que es lo que receta la propia Live API para este cuadro:
   *
   *   «when the audio stream is paused… an `audioStreamEnd` event should be
   *    sent to flush any cached audio.»
   *
   * El turno del niño puede quedarse colgado en el buffer del servidor sin
   * cerrarse nunca —y un turno que no se cierra es un turno que no se contesta.
   * `audioStreamEnd` lo cierra y el modelo responde a lo que ya tenía. Es
   * barato, no destruye nada y el stream se reanuda solo con el bloque
   * siguiente.
   *
   * Si después de eso el niño sigue hablando sin que nadie le conteste, lo roto
   * ya no es el turno sino el canal, y eso se arregla con un socket nuevo sobre
   * la misma sesión — el mismo camino que usa la mudez.
   */
  const destrabarElOido = useCallback(() => {
    rescatesDeOidoRef.current += 1;
    console.warn(`[oído] el niño habla y no llega nada: intento ${rescatesDeOidoRef.current}`);
    anotar({ t: "sordera", intento: rescatesDeOidoRef.current });
    cerrarTurnoAcumuladoRef.current?.();
    encolar({ quien: "nino", texto: MARCA_DE_SORDERA });

    if (rescatesDeOidoRef.current === 1) {
      try {
        liveRef.current?.sendRealtimeInput({ audioStreamEnd: true });
      } catch (e) {
        console.warn("[oído] no se pudo cerrar el stream:", e);
      }
      // Y desde acá alguien mira el reloj, que es lo que faltaba: si el flush
      // no destraba nada, la mudez toma el relevo y empuja o reconecta.
      vigilarMudezRef.current?.();
      return;
    }

    // El flush no alcanzó. Se dispara la escalera de la mudez SIN ESPERA: ella
    // ya sabe empujar primero y, si eso tampoco destraba, reconectar sobre la
    // MISMA sesión sin perderle al niño los ejercicios ni el hilo. Duplicar esa
    // escalera acá sería tener dos formas distintas de reaccionar al mismo
    // silencio, y una de las dos se iba a quedar vieja.
    console.error("[oído] el flush no alcanzó: se dispara la escalera de la mudez");
    vigilarMudezRef.current?.(0);
  }, [encolar, anotar]);

  /**
   * EL VIGILANTE DE LA VOZ: ¿el niño está oyendo lo que el tutor dice?
   *
   * Vigila el síntoma, no la causa — hay trozos programados y ninguno suena—,
   * porque las tres veces que pasó fue por un motivo distinto y la próxima será
   * por un cuarto. Ver `MS_VOZ_MUDA`.
   *
   * La recuperación es contundente a propósito: tirar el contexto de audio y
   * hacer uno nuevo. Un `resume()` no saca de todos los estados —el dispositivo
   * que se fue con los audífonos, el sink que ya no existe—, y acá el costo de
   * pasarse es cortar media frase mientras que el costo de quedarse corto es
   * que el niño no oiga nada el resto de la sesión.
   *
   * Y pase lo que pase queda MARCA en la transcripción. Sin ella una sesión que
   * el niño no oyó se ve idéntica a una sana, porque el texto llega por otro
   * camino que el audio. Eso es lo que hizo falta descubrir hablando tres
   * veces.
   */
  const vigilarVoz = useCallback(() => {
    if (vozRef.current) clearInterval(vozRef.current);
    rescatesDeVozRef.current = 0;
    vozRef.current = setInterval(() => {
      // Con la pestaña de fondo el navegador suspende el audio a propósito y no
      // hay nadie oyendo: acá no hay nada roto que arreglar. Vigilar igual sería
      // recrear el contexto cada vez que el niño mira otra ventana.
      if (document.hidden) return;
      const reproductor = reproductorRef.current;
      if (!reproductor?.vozMuda(MS_VOZ_MUDA)) return;

      rescatesDeVozRef.current += 1;
      console.error(
        `[voz] hay audio programado y no suena: rescate ${rescatesDeVozRef.current}`,
      );
      anotar({ t: "voz_muda", rescate: rescatesDeVozRef.current });
      // Que quede en la transcripción, y por lo tanto en `revisar_sesion`.
      cerrarTurnoAcumuladoRef.current?.();
      encolar({ quien: "tutor", texto: MARCA_DE_VOZ_MUDA });

      const revivio = reproductor.reiniciar();
      console.info(`[voz] contexto recreado · ${revivio ? "anda" : "sigue suspendido"}`);
      if (revivio) return;

      // El navegador no deja sonar nada sin un gesto nuevo. Decírselo es lo
      // único que queda, y es mucho mejor que dejarlo mirando a un tutor mudo.
      if (rescatesDeVozRef.current >= 2) {
        setError("No se oye a Walter. Toca para volver a empezar.");
        setEstado("error");
      }
    }, MS_ENTRE_CHEQUEOS_DE_VOZ);
  }, [encolar, anotar]);

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

      // Y ANTES DE MANDAR NADA, SE CIERRA EL STREAM DE AUDIO.
      //
      // Esta es la única pausa DELIBERADA del micrófono que queda (hasta 8 s,
      // ver `MS_ESPERANDO_MIRADA`), y la Live API pide cerrarla explícitamente:
      //
      //   «when the audio stream is paused for more than a second (for example,
      //    because the user switched off the microphone), an `audioStreamEnd`
      //    event should be sent to flush any cached audio.»
      //
      // Sin esto, lo que el niño alcanzó a decir antes de mandar la foto queda
      // cacheado del lado del servidor y se pega con lo que hable DESPUÉS, como
      // si no hubieran pasado ocho segundos en el medio. Es la misma familia de
      // bug que el `return` pelado del micrófono (`ses_02805f3edba1`): el
      // servidor no mide el tiempo, mide el audio que le llega.
      try {
        live.sendRealtimeInput({ audioStreamEnd: true });
      } catch (e) {
        // Que no se pueda cerrar el stream no justifica perder la imagen.
        console.warn("[imagen] no se pudo cerrar el stream de audio:", e);
      }

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
      // El diario lo anota el LLAMADOR, para que ningún tool quede fuera: acá
      // solo pasan los que devuelven por este helper. Ver el `Promise.all`.
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
      // ⚠️ ESTOS DOS TOOLS **BLOQUEAN**, y el comentario que había acá decía
      // exactamente lo contrario: «son NON_BLOCKING, el tutor sigue hablando
      // mientras esto pasa». Se quedó viejo cuando `voice.py` sacó el flag
      // —medido: con NON_BLOCKING, 8 de 8 turnos con tool salieron MUDOS— y
      // mandó a buscar el silencio de la pizarra al lado equivocado.
      //
      // Lo que pasa de verdad: el tutor SE CALLA mientras esto se resuelve. Es
      // rápido —se hace acá, sin tocar el backend— pero si la escena no se
      // puede armar, el niño oye un hueco. Por eso la declaración del tool le
      // pide decir una frase ANTES de llamarla, y por eso ese hueco es el que
      // Juan leyó como «¿me escuchas? estás como trabado» (`ses_0a6036dedf55`).
      //
      // Si algún día vuelve NON_BLOCKING, se vuelve a medir primero.
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
          anotar({ t: "pizarra_fallo", args: JSON.stringify(args) });

          // Y QUEDA ESCRITO. Hasta hoy, una pizarra que no dibujaba solo dejaba
          // este `console.warn`: se iba con la pestaña, el backend no se
          // enteraba —esto se resuelve acá, sin red— y la transcripción no
          // decía nada. Tres sesiones seguidas con la pizarra rota y cero
          // evidencia; lo único que quedaba era el niño quejándose.
          //
          // Va como turno del sistema, con los argumentos crudos: es lo que
          // permite reproducirlo después sin tener que adivinar qué pidió.
          cerrarTurnoAcumulado();
          encolar({
            quien: "tutor",
            texto: `[la pizarra no supo dibujar esto: ${JSON.stringify(args)}]`,
          });

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
        // QUÉ QUEDÓ EN PANTALLA, Y CUÁNDO. El auditor del método juzga si el
        // tutor «afirmó algo falso» sobre la pizarra, y hasta acá lo hacía
        // leyendo la conversación — o sea, adivinando el estado de la pantalla.
        // En `ses_60ea3b164f17` leyó «¿podrías mostrarme las estrellas?» como
        // un desmentido cuando era una PETICIÓN, y acusó al tutor de mentir
        // sobre unas estrellas que sí dibujó. Un falso positivo acá pesa: el
        // porcentaje del panel del papá sale de estos veredictos.
        anotar({ t: "pizarra", que: describir(cuadro) });
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
        // El tablero NO se borra: lo que hay en él es justo lo que el niño va a
        // copiar. Se lo borrábamos en el momento exacto en que lo necesitaba —
        // «no me sale el tablero», ses_445f4c33db41— y el tutor, que no ve la
        // pantalla, no tenía cómo entender qué le estaba pasando.
        setDibujoEnviado(false);
        setHoja(String(args?.consigna ?? "Dibújame lo que estás pensando"));
        return {
          hoja_abierta: true,
          ...(cuadroRef.current
            ? { ojo: "Lo que tenías en la pizarra le queda arriba de la hoja, para copiarlo." }
            : {}),
        };
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

        // OJO CON LO QUE DICE ACÁ: este texto y el aviso de arriba llegan los
        // dos, uno detrás del otro, y si los dos le piden lo mismo el tutor lo
        // dice DOS VECES. Pasó en `ses_eadfa6137a37` y lo cazó el niño:
        //
        //   tutor: «...apunta a tu cuaderno y toca el botón. Y ahí me quedo en
        //           silencio.¡De una, Juan! ...Toca el botón redondo que se te
        //           abrió para tomarle una foto, ¿listo?»
        //   nino:  «Primero me dijiste ahí se te abre la camarita y luego que
        //           toque el botón. Era solo la de que se toque el botón.»
        //
        // La instrucción al niño va en UN solo lugar, y es el aviso de arriba:
        // sale cuando el visor ESTÁ abierto, no cuando lo pedimos. Acá solo se
        // le dice que espere.
        return medir({
          camara_pedida: true,
          que_hacer:
            "Se está abriendo. NO le digas todavía qué hacer: te aviso yo en " +
            "cuanto esté abierta y ahí se lo dices UNA vez. Mientras tanto, " +
            "sigue con lo que estabas diciendo.",
        });
      }
      case "escalate_safety":
        await api.escalateSafety(sesion.sesion_id, args.motivo, args.evidencia);
        return { escalado: true };
      default:
        return { error: `tool desconocido: ${nombre}` };
    }
  }, [avisarAlTutor, cerrarTurnoAcumulado, encolar, anotar]);

  /* ── El dibujo del niño ───────────────────────────────────────────────── */

  const enviarDibujo = useCallback(
    (jpegBase64: string) => {
      // LA HOJA NO SE BORRA. Lo pidió el niño con todas las letras
      // (`ses_74b6cc7667ae`): «cuando yo te envío algo que escribí en el
      // tablero, no se desaparezca».
      //
      // Se borraba en el mismo instante en que la mandaba, así que escuchaba
      // «fíjate que el palito de la h tiene que subir un poco más» mirando una
      // hoja en blanco — sin la letra de la que le estaban hablando. Peor: el
      // tutor le pedía corregirla y él ya no la tenía.
      //
      // Queda, y sigue siendo EDITABLE, que es lo que hace falta para
      // corregirla encima. Se cierra sola cuando el tutor manda otra cosa a la
      // pizarra, o cuando el niño toca "Cerrar".
      setDibujoEnviado(true);
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

  /**
   * @param conservarAudio  No cerrar el AudioContext, solo callar lo que suena.
   *
   * EL AUDIOCONTEXT NO SOBREVIVE A UN `new AudioContext()` FUERA DE UN GESTO.
   * `ReproductorContinuo.iniciar()` lo dice en su primera línea: si no se llama
   * dentro de un gesto del usuario, el navegador lo deja **suspendido**.
   *
   * Una reconexión no viene de un gesto —viene del reloj de la mudez— así que
   * cerrar el reproductor y crear otro deja al niño con un contexto muerto: los
   * chunks se programan contra un reloj detenido y no suena nada. El personaje
   * se sigue animando, porque lo mueve el estado y no el sonido.
   *
   * Es lo que pasó en `ses_6c6fb58aafbb`, y el niño lo describió mejor que
   * cualquier log: *«solo veo como al muñeco hablar, pero no estás hablando»*,
   * *«se cerró y ahora ya no te escucho, solo te puedo leer»*.
   *
   * El contexto que se creó al empezar SÍ nació en un gesto. Se conserva.
   */
  const soltarRecursos = useCallback((conservarAudio = false) => {
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
    if (conservarAudio) {
      // Callar lo que quedó programado —es de la conversación que se cayó— sin
      // tocar el contexto, que es lo único que no se puede volver a crear.
      reproductorRef.current?.detenerTodo();
    } else {
      reproductorRef.current?.cerrar();
      reproductorRef.current = null;
    }
    // Un reloj que sobrevive a la sesión corta la SIGUIENTE a destiempo.
    for (const reloj of relojesRef.current) clearTimeout(reloj);
    relojesRef.current = [];
    if (vozRef.current) {
      clearInterval(vozRef.current);
      vozRef.current = null;
    }
    // EL LOTE QUE FALTA ES SIEMPRE EL QUE EXPLICA POR QUÉ SE CAYÓ. Se drena
    // antes de soltar nada más: lo que quedó pendiente es el final de la
    // sesión, que es justo el tramo que después hace falta leer.
    diarioRef.current?.drena();
    // Y esta bandera menos: dejaría el micrófono mudo en la sesión siguiente.
    esperandoMiradaRef.current = false;
    retenerHastaRef.current = 0;
    // Un turno abortado que sobreviva se traga el primer audio de la sesión
    // siguiente, que es el saludo — el turno más caro de perder.
    turnoAbortadoRef.current = 0;
    enDudaRef.current.length = 0;
    vozSinAcuseRef.current = 0;
    rescatesDeOidoRef.current = 0;
    // EL TABLERO TAMPOCO SOBREVIVE.
    //
    // `ses_97d5b112a122` empezó así, antes de que nadie dijera nada:
    //   nino: «¿Por qué abres esto? De mamá, ¿por qué pones esto? No entiendo.»
    // Era la pizarra de la sesión ANTERIOR, que había terminado con la palabra
    // "mamá" escrita. El tutor nuevo no sabía nada de eso —su contexto arranca
    // limpio— así que tuvo que adivinar, y adivinó mal dos veces.
    //
    // Es el mismo bug que `get_next_problem` ya arreglaba DENTRO de la sesión
    // (ses_6bccd98babcc, "las siete macetas"), un nivel más arriba: lo que
    // quedó en pantalla no puede sobrevivir a la conversación que lo puso ahí.
    setCuadro(null);
    cuadroRef.current = null;
    setHoja(null);
    // El vigilante de la mudez tampoco sobrevive: cerraría la sesión siguiente.
    if (mudezRef.current) {
      clearTimeout(mudezRef.current);
      mudezRef.current = null;
    }
    empujonesRef.current = 0;
  }, []);

  /* ── Cierre ────────────────────────────────────────────────────────────── */

  const terminar = useCallback(
    async (interrumpida = false, motivo = "nino_termino") => {
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
          .cerrarSesion(sesion.sesion_id, interrumpida, tokensRef.current.ultimo, motivo)
          .catch(() => {});
      }
      sesionRef.current = null;
      acumNinoRef.current = "";
      acumTutorRef.current = "";
      bancoRef.current = [];
      entregadosRef.current = new Set();
      tokensRef.current = { suma: 0, ultimo: 0 };
      // Acá y no en `soltarRecursos`: una reconexión pasa por soltarRecursos y
      // reiniciar el contador ahí lo volvería inútil — el niño podría quedar en
      // un ciclo de caída-reconexión sin fin. `terminar` solo corre cuando la
      // sesión de verdad se cierra, que es cuando el contador tiene que volver
      // a cero.
      reconexionesRef.current = 0;
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
      void terminar(true, "otra_pestana").then(() => {
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
    const queEs = reconectandoRef.current ? "reconexión" : "arranque";
    console.info(
      `[sesion] ${queEs} #${arranquesRef.current} en la pestaña ${pestanaRef.current}`,
    );
    // Una reconexión ES un arranque más, y decirle "ya había arrancado antes"
    // manda a buscar el bug de los dos tutores donde no está.
    if (arranquesRef.current > 1 && !reconectandoRef.current) {
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
    //
    // SALVO EN UNA RECONEXIÓN, que es justo lo contrario: la sesión del backend
    // es lo único que queremos conservar. Lo que está roto es el canal de voz.
    // Cerrarla acá le haría perder al niño los ejercicios, los turnos y el
    // objetivo del día por un socket caído.
    if (reconectandoRef.current) {
      // Los turnos que quedaron a medio decir se reportan antes de soltar: si
      // no, el último tramo de la conversación —el que explica POR QUÉ se cayó—
      // se pierde, y es el que después hace falta para entender qué pasó.
      const sesion = sesionRef.current;
      if (sesion) {
        if (acumNinoRef.current) {
          pendientesRef.current.push({ quien: "nino", texto: acumNinoRef.current });
        }
        if (acumTutorRef.current) {
          pendientesRef.current.push({ quien: "tutor", texto: acumTutorRef.current });
        }
        if (pendientesRef.current.length) {
          await api
            .reportarTurnos(sesion.sesion_id, pendientesRef.current.splice(0))
            .catch(() => {});
        }
      }
      acumNinoRef.current = "";
      acumTutorRef.current = "";
      // Que `onclose` no lea este cierre como "la sesión se murió sola" y le
      // ponga al niño un cartel de error encima de la reconexión en curso.
      cerrandoRef.current = true;
      soltarRecursos(true); // y el AudioContext se conserva: ver soltarRecursos
      cerrandoRef.current = false;
    } else if (sesionRef.current) {
      await terminar(true, "arranque_nuevo");
    }

    setError(null);
    setSesionMurio(false);
    avisadoRef.current = false;
    setEstado("conectando");

    try {
      // EL QUE YA ESTÁ VIVO SE REUSA. Solo se crea uno nuevo si no hay.
      //
      // `iniciar()` tiene que correr dentro del gesto del usuario o el navegador
      // deja el contexto suspendido, y una reconexión no tiene gesto: la
      // dispara el reloj de la mudez. Crear uno nuevo ahí es crear uno muerto
      // — `ses_6c6fb58aafbb`, «solo veo al muñeco hablar, pero no estás
      // hablando». Ver `soltarRecursos`.
      const reproductor = reproductorRef.current ?? new ReproductorContinuo();
      reproductor.iniciar(); // dentro del gesto del usuario (o ya iniciado)
      reproductor.alTerminar = () => setEstado((e) => (e === "hablando" ? "escuchando" : e));
      reproductorRef.current = reproductor;
      // Desde acá alguien mira que lo que el tutor dice se OIGA, no solo que
      // llegue. Ver `MS_VOZ_MUDA`.
      vigilarVoz();

      modoRef.current = modo;
      ultimaVozRef.current = Date.now(); // arranca limpio el reloj del silencio

      // ANTES DE NADA: ¿esta pestaña es la versión que el servidor sirve?
      //
      // Si no lo es, se recarga y vuelve a empezar sola. Se hace acá y no al
      // montar la app porque una pestaña puede quedar abierta horas: el momento
      // en que importa es cuando el niño toca "empezar", no cuando abrió la
      // página. Ver `recargarSiEstoyViejo` — sale de `ses_4ed4e930e60f`.
      if (await recargarSiEstoyViejo()) return;

      // En una reconexión no se abre sesión: se vuelve a firmar un token sobre
      // la que ya está viva. No cobra cupo ni replanifica — el objetivo del día
      // no cambia porque se haya caído un socket.
      const previa = sesionRef.current;
      const sesion =
        reconectandoRef.current && previa
          ? await api.reconectar(previa.sesion_id)
          : await api.abrirSesion(ninoId, modo, tokenActual());
      sesionRef.current = sesion;
      // El diario de la voz arranca con la sesión y muere con ella. Sale sin
      // esperar respuesta y con su propio catch: es diagnóstico, y no puede
      // costarle nada al niño ni romper la sesión si el POST falla.
      diarioRef.current = new Diario((eventos) => {
        void api.anotarDiario(sesion.sesion_id, eventos).catch(() => {});
      });
      anotar({ t: reconectandoRef.current ? "reconectada" : "abierta", build: MI_BUILD });
      // El banco solo se reemplaza si vino uno. Al reconectar llega vacío A
      // PROPÓSITO: el navegador ya lo tiene y puede haber usado la mitad —
      // pisarlo le devolvería al niño ejercicios que ya resolvió.
      if (sesion.ejercicios?.length) {
        bancoRef.current = sesion.ejercicios;
        entregadosRef.current = new Set();
      }
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
                void terminarRef.current?.(false, "techo_tokens");
              }
              console.info(
                `[tokens] acumulado=${gastados} (suma ingenua ${tokensRef.current.suma})`,
              );
            }

            // ── ¿ESTE AUDIO TODAVÍA TIENE DERECHO A SONAR? ──────────────────
            //
            // El barge-in calló al tutor, pero Gemini sigue mandando el resto
            // del turno: esos bloques iban derecho al reproductor y **el tutor
            // volvía a sonar encima del niño** medio segundo después de que lo
            // callaron. Es la mitad de «al mismo tiempo que me escucha, está
            // hablando» (`ses_31593f90ab26`, 25/08).
            //
            // No se tiran: se guardan. Si el barge-in fue un falso positivo el
            // servidor no va a confirmar nada, y tirar sería dejar al tutor
            // mudo a mitad de frase — peor que el bug. Ver
            // `MS_ESPERA_CORTE_SERVIDOR`.
            if (
              turnoAbortadoRef.current &&
              !sigueEnDuda(turnoAbortadoRef.current, Date.now(), MS_ESPERA_CORTE_SERVIDOR)
            ) {
              // El servidor nunca cortó: no había a quién oír. El tutor retoma
              // donde iba, y el falso positivo costó una pausa.
              console.info("[barge-in] el servidor no confirmó: el tutor retoma");
              anotar({ t: "barge_in_falso" });
              turnoAbortadoRef.current = 0;
              for (const guardado of enDudaRef.current.splice(0)) {
                reproductor.programar(guardado);
              }
            }

            for (const parte of contenido?.modelTurn?.parts ?? []) {
              if (parte.inlineData?.data) {
                if (turnoAbortadoRef.current) {
                  enDudaRef.current.push(parte.inlineData.data);
                  continue;
                }
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
                  anotar({ t: "latencia", ms: espera });
                }
                setMirandoFoto(false); // ya está contestando
                setEstado("hablando");
                tutorContesto();
                // Y RECIÉN ACÁ vuelve el micrófono.
                //
                // Antes se reabría con CUALQUIER mensaje del servidor —incluida
                // la transcripción de lo que el propio niño acababa de decir—,
                // así que en la práctica no esperaba nada: volvía enseguida y le
                // cortaba el turno al modelo mientras miraba la imagen. El
                // único mensaje que prueba que el tutor ya contestó es su voz.
                esperandoMiradaRef.current = false;
                // Ya hay voz: desde acá el que retiene es el reproductor.
                retenerHastaRef.current = 0;
                reproductor.programar(parte.inlineData.data);
              }
            }

            // El niño habló encima: cortar YA todo lo programado.
            if (contenido?.interrupted) {
              anotar({ t: "interrupted" });
              reproductor.detenerTodo();
              // El servidor confirma lo que el barge-in ya había decidido acá:
              // lo que quedó en duda era el turno que el niño cortó y no vuelve.
              turnoAbortadoRef.current = 0;
              enDudaRef.current.length = 0;
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
              ultimaVozRef.current = Date.now(); // y el reloj de la inactividad
              // Llegó: el oído del tutor funciona. Ver `MS_VOZ_SIN_ACUSE`.
              vozSinAcuseRef.current = 0;
              rescatesDeOidoRef.current = 0;
              // Y el que mira si el tutor contesta. Se reinicia con cada sílaba:
              // mientras el niño habla no hay nada que esperar.
              vigilarMudez();
            }

            if (contenido?.turnComplete) {
              tutorContesto();
              // ── `turnComplete` PRUEBA QUE EL SERVIDOR NO CORTÓ NADA ────────
              //
              // Y por eso lo que quedó en duda hay que SOLTARLO, no tirarlo.
              // Acá estuvo el error que dejó a Juan leyendo al tutor sin oírlo
              // (`ses_660ce383567d`, 25/08): esta rama descartaba el audio
              // retenido «porque el turno ya terminó». Pero si el turno terminó
              // entero es justamente porque nadie lo interrumpió — o sea, el
              // barge-in se equivocó, y lo que se estaba tirando era la frase
              // del tutor que el niño nunca llegó a oír.
              //
              // El resultado se retroalimentaba solo: el niño no oía, hablaba
              // más fuerte para preguntar si seguía ahí, eso disparaba otro
              // barge-in, y el turno siguiente también se perdía. La
              // transcripción llegaba igual, así que en pantalla el tutor
              // hablaba y hablaba. «Estoy viendo que estás hablando y hablando
              // y como que no se escucha, solo leo lo que estás diciendo.»
              //
              // El único mensaje que autoriza a descartar es `interrupted`: ahí
              // el servidor confirma que el niño habló encima de verdad.
              if (enDudaRef.current.length) {
                console.info("[barge-in] el turno terminó entero: se suelta lo retenido");
                for (const guardado of enDudaRef.current.splice(0)) {
                  reproductor.programar(guardado);
                }
              }
              turnoAbortadoRef.current = 0;
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
              esperandoMiradaRef.current = false; // ya reaccionó a la imagen
              void Promise.all(
                llamadas.map(async (fc: any) => {
                  let respuesta: object;
                  // Se mide ACÁ y no adentro de cada `case`. La primera versión
                  // anotaba en un helper que solo envolvía los `return` de los
                  // tools de red, así que los de la pizarra —los que dibujan, y
                  // los que RBH sospechaba de tardar— no aparecían en el diario.
                  // Un instrumento con agujeros manda a buscar el problema al
                  // lado equivocado, que es peor que no tenerlo.
                  const desde = performance.now();
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
                  anotar({
                    t: "tool",
                    nombre: fc.name,
                    ms: Math.round(performance.now() - desde),
                  });
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
      /** La línea de retardo del micrófono. NO es una copia del audio que ya
          salió: es el único camino por el que sale. Ver `BLOQUES_RETENIDOS`. */
      const retenidos: Float32Array[] = [];
      /** ¿Lo que sale de la cola es una interrupción confirmada, o eco a callar? */
      let interrumpioDeVerdad = false;

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
        // `hablando` PELADO, y no `sonandoHace`. Cortar al tutor es una decisión
        // sobre lo que está sonando AHORA: la cola de guarda existe para el
        // otro problema —que el eco no viaje— y estirar el barge-in hasta ahí
        // fue dejar que la cola acústica del parlante decidiera cortes.
        //
        // Se probó al revés el 25/08 por la mañana, con el argumento de que el
        // niño que arranca a hablar pegado al final del turno quedaba en tierra
        // de nadie. El argumento era falso: sus primeras sílabas ya no se
        // pierden, y no porque el barge-in las rescate sino porque al dejar de
        // retener la cola se suelta entera con su audio (`pasarPorLaCola`). Lo
        // único que agregó la ventana extra fueron cortes falsos.
        const tutorSonando = reproductor.hablando;

        if (tutorSonando && nivel > UMBRAL_BARGE_IN) {
          vozSostenidaMs = vozSostenida(vozSostenidaMs, {
            hayVoz: true,
            bloqueMs: (muestras.length / SAMPLE_RATE_ENTRADA) * 1000,
          });
          if (vozSostenidaMs >= MS_PARA_CORTAR) {
            // El nivel va al log para poder calibrar el umbral con un número la
            // próxima vez, en vez de moverlo a ojo: si acá aparecen cortes con
            // niveles apenas por encima de 0,045, es eco y el umbral sube.
            console.info(`[barge-in] corta al tutor · nivel ${nivel.toFixed(3)}`);
            anotar({ t: "barge_in", nivel: Number(nivel.toFixed(3)) });
            reproductor.detenerTodo(); // desde acá `hablando` es false
            // Y lo que el servidor siga mandando de ESTE turno no vuelve al
            // parlante: el tutor no puede resucitar encima del niño.
            turnoAbortadoRef.current = Date.now();
            setEstado("escuchando");
            vozSostenidaMs = 0;
            interrumpioDeVerdad = true;
          }
        } else if (nivel <= UMBRAL_BARGE_IN) {
          // DECAE, no se resetea. Una frase no es un tono continuo: entre
          // sílabas hay bloques de 64 ms por debajo del umbral, y ponerlo en
          // cero con cada uno hacía que el contador casi nunca llegara a
          // `MS_PARA_CORTAR`. El niño hablaba encima del tutor y el barge-in no
          // se confirmaba nunca — su audio se iba al silencio mientras él veía
          // que no lo escuchaban. Un golpe suelto sigue sin alcanzar: decae al
          // mismo ritmo que sube. Ver `vozSostenida`.
          vozSostenidaMs = vozSostenida(vozSostenidaMs, {
            hayVoz: false,
            bloqueMs: (muestras.length / SAMPLE_RATE_ENTRADA) * 1000,
          });
        }

        // Callado mientras el tutor mira una imagen: este flujo le mantendría
        // el turno abierto y no contestaría nunca. Ver `mostrarleAlTutor`.
        if (esperandoMiradaRef.current) return;

        // ── MIENTRAS EL TUTOR HABLA, EL AUDIO NO SALE ──────────────────────
        //
        // Esta es la causa de que el tutor se cortara a mitad de frase, y de la
        // que se quejó RBH: «se corta y no terminas de hablar».
        //
        // Medido sobre las últimas 8 transcripciones: **20 de 99 turnos del
        // tutor (uno de cada cinco) quedaron a mitad de palabra** —«¡Ah, ya lo
        // veo! Mira,», «está en la pizarrita blanca justo»—.
        //
        // El micrófono mandaba SIEMPRE, también mientras el tutor sonaba. Del
        // otro lado, el VAD del servidor corre con `START_SENSITIVITY_HIGH`
        // —puesta a propósito, para que el niño que habla bajito abra turno— y
        // con esa sensibilidad el eco del propio tutor por los parlantes cuenta
        // como "el niño empezó a hablar". El servidor entonces CORTA LA
        // GENERACIÓN: por eso la frase queda partida también en la
        // transcripción, no solo en el parlante.
        //
        // El barge-in local no lo evitaba: solo callaba el altavoz de acá.
        //
        // Y el stream TAMPOCO se corta, que fue el arreglo del 24/08. Va
        // silencio, no "nada". La Live API: «`silenceDurationMs` only works
        // within a continuous stream — it measures quiet periods, not stream
        // interruptions.» Sin audio el reloj del VAD se detiene, el turno del
        // niño se queda colgado sin cerrar, y al volver el micrófono lo nuevo
        // se pega con lo viejo (`ses_02805f3edba1`: 25 turnos, la sesión
        // muerta).
        //
        // ── UN BLOQUE ENTRA, UN BLOQUE SALE ────────────────────────────────
        //
        // Todo el audio del micrófono pasa por `retenidos`, que NO es una copia
        // de respaldo: es el camino. Por cada bloque capturado se envía
        // exactamente uno —silencio si era eco del tutor, el audio de verdad si
        // el barge-in confirmó que abajo estaba el niño—, y así el stream avanza
        // al mismo ritmo que el reloj de pared.
        //
        // ESA INVARIANTE ES EL ARREGLO DEL 25/08, y lo que faltaba de los otros
        // dos. Hasta acá se mandaba silencio Y ADEMÁS se guardaba una copia del
        // bloque; al confirmarse la interrupción, la copia salía ENCIMA del
        // silencio que ya había ocupado su lugar en el tiempo. Cada barge-in le
        // metía al stream medio segundo de audio de más y dejaba al servidor
        // medio segundo atrás. **No se recuperaba nunca**: se sumaba
        // interrupción tras interrupción hasta que el tutor contestaba a un
        // turno viejo mientras el niño ya estaba en otro. `ses_31593f90ab26`,
        // 25/08: «mi audio le llega tarde, y al mismo tiempo que escucha está
        // hablando».
        //
        // `sonandoHace` y no `hablando`: el eco se escapaba por dos huecos
        // —entre chunk y chunk, y la cola del parlante después de la última
        // muestra— y por ahí siguió cortándose el tutor (`ses_0a6036dedf55`).
        // Y el saludo entra por la otra mitad de la condición: hasta que el
        // tutor suelte su primer bloque no hay reproductor que retenga nada, y
        // ese es justo el turno que se partió. Ver `MS_RETENER_APERTURA`.
        const esperandoElSaludo = retenerHastaRef.current > Date.now();
        const reteniendo = reproductor.sonandoHace(MS_COLA_ECO) || esperandoElSaludo;

        // La regla vive en `colaDelMicrofono`, aparte y con sus propios tests:
        // acá un error no se ve, se SIENTE tres turnos después.
        const aEnviar = pasarPorLaCola(retenidos, muestras, {
          reteniendo,
          interrumpio: interrumpioDeVerdad,
          fondo: BLOQUES_RETENIDOS,
        });

        try {
          for (const bloque of aEnviar) {
            const data = bloque.mudo
              ? silencioPcm16Base64(bloque.muestras.length)
              : aPcm16Base64(bloque.muestras);
            live.sendRealtimeInput({ audio: { data, mimeType: MIME_ENTRADA } });
          }
        } catch {
          /* sesión cerrada a mitad de un lote */
        }

        // ── ¿ALGUIEN ESTÁ OYENDO AL NIÑO? ─────────────────────────────────
        //
        // Se cuenta solo la voz que SALE de verdad —no la que va muda por el
        // eco del tutor— y solo por encima del umbral. Si se juntan segundos de
        // eso sin que vuelva una sola sílaba transcripta, el camino de entrada
        // está roto: el niño está hablándole a nadie.
        //
        // Nadie lo miraba, y no por descuido: `vigilarMudez` se arma CUANDO
        // LLEGA la transcripción del niño, así que el vigilante del silencio
        // dependía justo de lo que acá falla. Ver `MS_VOZ_SIN_ACUSE`.
        if (!reteniendo && nivel > UMBRAL_BARGE_IN) {
          vozSinAcuseRef.current += (muestras.length / SAMPLE_RATE_ENTRADA) * 1000;
          if (vozSinAcuseRef.current >= MS_VOZ_SIN_ACUSE) {
            vozSinAcuseRef.current = 0;
            destrabarElOido();
          }
        }

        if (!reteniendo) {
          retenerHastaRef.current = 0; // el techo venció: el saludo no llegó
          // Se apaga con la cola vacía, nunca antes: si sobreviviera al próximo
          // turno del tutor, el eco de ESE turno saldría como si fuera el niño.
          interrumpioDeVerdad = false;
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
        // El micrófono queda retenido hasta que el tutor suene. Se pone ANTES
        // del envío: el hueco que partía el saludo empieza en el instante en
        // que el modelo recibe el turno, no cuando contesta.
        retenerHastaRef.current = Date.now() + MS_RETENER_APERTURA;
        try {
          live.sendClientContent({
            turns: { role: "user", parts: [{ text: sesion.apertura }] },
            turnComplete: true,
          });
        } catch (e) {
          console.warn("[apertura] el tutor no pudo saludar primero:", e);
          // Si el saludo ni salió, no hay nada que esperar: el micro vuelve ya.
          retenerHastaRef.current = 0;
        }

        // Y ALGUIEN MIRA EL RELOJ desde el primer segundo.
        //
        // El vigilante de la mudez se armaba solo cuando llegaba transcripción
        // del niño. O sea: si el tutor no abría la boca y el niño tampoco,
        // nadie estaba mirando y la sesión se quedaba en silencio para siempre
        // — que es la forma que tienen de verse las 19 sesiones vacías de las
        // 71 que se midieron el 22/08.
        //
        // Importa más todavía al reconectar: ahí el saludo es el recap, y si no
        // llega, el niño se queda con «conectando» en la pantalla y el tutor no
        // vuelve nunca.
        vigilarMudez();
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
            void terminarRef.current?.(false, "techo_tiempo");
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
  }, [
    ninoId,
    atenderTool,
    encolar,
    terminar,
    soltarRecursos,
    vigilarMudez,
    vigilarVoz,
    destrabarElOido,
    tutorContesto,
  ]);

  // El callback de Gemini se arma antes que `terminar`, así que lo alcanza
  // por referencia en vez de por closure. Lo mismo `empezar`, que el vigilante
  // de la mudez necesita para reconectar y que se define después que él.
  terminarRef.current = terminar;
  empezarRef.current = empezar;

  useEffect(() => () => void terminar(true, "desmontaje"), [terminar]);

  /* CUANDO LA PESTAÑA SE VA, NO HAY REACT QUE LIMPIE.
     El `useEffect` de arriba corre al DESMONTAR: sirve para navegar dentro de
     la app, no para que el navegador se lleve la página. Al cerrar la pestaña
     —o al matarla el sistema— React no ejecuta nada y un `fetch` a medio vuelo
     se cancela.

     Resultado: `ses_610e057cfd91` quedó `activa`, sin `fin` y con 0 tokens. En
     el log no hay `/cerrar`. Para el backend esa sesión sigue viva hoy.

     `pagehide` y no `beforeunload`: es el único que dispara de forma confiable
     en móvil, donde el sistema mata pestañas de fondo sin avisar. Y `keepalive`
     no alcanza — por eso `sendBeacon`, que el navegador entrega aunque la
     página ya no exista.

     Es la capa de ADENTRO. La de afuera es el reaper del backend, que agarra
     lo que esto no puede: un crash, una suspensión, quedarse sin internet. */
  /* SI EL NIÑO SE FUE, SE APAGA EL MICRÓFONO.
     Lo pidió RBH con todas las letras: «no vuelva a pasar eso de las sesiones
     abiertas y que botemos plata a la basura».

     El reaper del backend NO sirve para esto: cierra la fila en la base, pero
     la pestaña sigue viva y el micrófono sigue mandando audio a Google, que
     sigue cobrando. Los dos vigilantes hacen falta y miran cosas distintas —
     uno la pestaña muerta, este el niño ausente con la pestaña viva.

     Se cierra desde acá, que es el único lado que puede callar el micrófono. */
  useEffect(() => {
    const reloj = setInterval(() => {
      if (!sesionRef.current) return;
      // Trabajando en silencio: dibujando en la hoja, o acomodando el cuaderno
      // para la foto. Cerrarle la sesión ahí sería el arreglo peor que el bug —
      // es la misma trampa que casi se comete con el reaper.
      const hayAlguienTrabajando =
        hojaRef.current !== null || camaraAbiertaRef.current || esperandoMiradaRef.current;
      if (hayAlguienTrabajando) {
        ultimaVozRef.current = Date.now();
        return;
      }
      if (Date.now() - ultimaVozRef.current < MS_SIN_EL_NINO) return;

      console.warn(`[inactividad] ${MS_SIN_EL_NINO / 1000}s sin el niño: se cierra`);
      void terminarRef.current?.(true, "nino_inactivo").then(() => {
        // Un niño que vuelve tiene que entender qué pasó y poder seguir.
        setError("Como no te oí por un ratico, cerré la clase. Toca para seguir.");
        setEstado("error");
      });
    }, 30_000);
    return () => clearInterval(reloj);
  }, []);

  // Los espejos, para poder leerlos desde el `setInterval` de arriba sin que
  // el intervalo se vuelva a montar con cada trazo del niño.
  hojaRef.current = hoja;
  camaraAbiertaRef.current = camara !== null;

  /* EL LATIDO. Es lo que le da ojos al vigilante de afuera.
     20 s: con el margen del reaper en 180 s hacen falta nueve seguidos perdidos
     para que dé una sesión por muerta, y eso aguanta el estrangulamiento de
     timers que el navegador aplica a las pestañas de fondo. */
  useEffect(() => {
    const reloj = setInterval(() => {
      const sesion = sesionRef.current;
      if (sesion) void api.latido(sesion.sesion_id);
    }, 20_000);
    return () => clearInterval(reloj);
  }, []);

  useEffect(() => {
    const alIrse = () => {
      const sesion = sesionRef.current;
      if (!sesion) return;
      // `tokensRef.current.ultimo` es lo último que reportó Gemini; sin esto la
      // sesión se cierra con 0 gastado y el presupuesto del niño miente.
      if (api.cerrarConBeacon(sesion.sesion_id, tokensRef.current.ultimo)) {
        // Que el `terminar()` del desmonte no la cierre por segunda vez.
        sesionRef.current = null;
      }
    };
    window.addEventListener("pagehide", alIrse);
    return () => window.removeEventListener("pagehide", alIrse);
  }, []);

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
    dibujoEnviado,
    empezar,
    terminar,
  };
}
