/**
 * La cámara para mostrarle el cuaderno al tutor.
 *
 * NO GRABA, y no queda prendida. El tutor pide ver algo, se abre un visor con
 * un botón, el niño apunta y dispara. Al disparar —o al cancelar— la cámara se
 * apaga. Una foto, decidida por el niño.
 *
 * La primera versión capturaba SOLA: abría la cámara, esperaba 350 ms, tomaba
 * el cuadro y cerraba. Se veía como que la cámara parpadeaba y se apagaba, y
 * la foto salía de lo que hubiera enfrente — la mesa, el techo. Nadie puede
 * fotografiar un cuaderno a ciegas: hace falta ver para apuntar.
 *
 * Este módulo NO dibuja nada: abre el stream y saca un cuadro cuando se lo
 * piden. El visor es un componente aparte.
 */

/**
 * Ancho al que se manda la foto.
 *
 * 768 y no 1024, y el número no es arbitrario: los modelos de visión procesan
 * la imagen en mosaicos, y hasta 768 px cabe en el mínimo. Pasado ese punto se
 * parte en más mosaicos — más tokens que leer antes de poder contestar, y el
 * niño esperando con el cuaderno en la mano.
 *
 * Un cuaderno de primaria con letra de niño se lee perfecto a 768. Lo que se
 * gana en nitidez arriba de eso no lo necesita nadie; lo que se pierde en
 * tiempo de respuesta se nota en cada foto.
 */
const ANCHO_MAX = 768;

/** Un fallo de cámara con algo que el niño pueda leer y hacer. */
export class ErrorCamara extends Error {
  constructor(
    readonly clase: "sin_soporte" | "sin_permiso" | "sin_camara" | "ocupada" | "otro",
    readonly paraElNino: string,
  ) {
    super(paraElNino);
    this.name = "ErrorCamara";
  }
}

/** Traduce el error del navegador a algo accionable. */
export function explicarFallo(e: any): ErrorCamara {
  if (e instanceof ErrorCamara) return e;
  switch (e?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return new ErrorCamara(
        "sin_permiso",
        "No tengo permiso para la cámara. Toca el candado 🔒 al lado de la dirección y permite la cámara.",
      );
    case "NotFoundError":
    case "OverconstrainedError":
      return new ErrorCamara("sin_camara", "No encuentro ninguna cámara en este equipo.");
    case "NotReadableError":
    case "AbortError":
      return new ErrorCamara(
        "ocupada",
        "La cámara la está usando otro programa. Ciérralo y volvemos a intentar.",
      );
    default:
      return new ErrorCamara("otro", e?.message ?? "No pude abrir la cámara.");
  }
}

export interface FotoTomada {
  base64: string;
  mimeType: "image/jpeg";
}

/**
 * Enciende la cámara y devuelve el stream para mostrarlo en pantalla.
 *
 * Tira si el permiso se niega o no hay cámara. Quien llama TIENE que manejarlo:
 * el tutor no puede quedarse esperando una foto que no va a llegar.
 */
export async function abrirCamara(): Promise<MediaStream> {
  // `mediaDevices` no existe fuera de un contexto seguro (https o localhost) ni
  // en algunos navegadores embebidos. Sin este chequeo el fallo es un
  // "cannot read property of undefined" que no le dice nada a nadie.
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new ErrorCamara(
      "sin_soporte",
      "Este navegador no me deja usar la cámara. Prueba abriendo la página en Chrome.",
    );
  }

  return navigator.mediaDevices.getUserMedia({
    // La de atrás si existe — el niño apunta al cuaderno. `ideal` y no `exact`:
    // en un portátil solo hay cámara frontal y con `exact` fallaría entero.
    video: { facingMode: { ideal: "environment" }, width: { ideal: ANCHO_MAX } },
    audio: false,
  });
}

/** Apaga la cámara. Siempre, pase lo que pase: es el cuarto de un niño. */
export function cerrarCamara(stream: MediaStream | null): void {
  stream?.getTracks().forEach((t) => t.stop());
}

/** Saca un cuadro del video que se está viendo. Lo dispara el niño. */
export function capturarCuadro(video: HTMLVideoElement): FotoTomada {
  // Si el video todavía no tiene dimensiones, el canvas sale de 0x0 y el
  // base64 queda vacío: se "toma" una foto que no existe, sin error, y el
  // tutor termina describiendo una imagen en blanco.
  if (!video.videoWidth || !video.videoHeight) {
    throw new ErrorCamara(
      "otro",
      "La cámara todavía se está encendiendo. Espera un segundito y vuelve a tocar el botón.",
    );
  }

  const escala = Math.min(1, ANCHO_MAX / (video.videoWidth || ANCHO_MAX));
  const lienzo = document.createElement("canvas");
  lienzo.width = Math.round(video.videoWidth * escala);
  lienzo.height = Math.round(video.videoHeight * escala);

  const ctx = lienzo.getContext("2d");
  if (!ctx) throw new Error("No pude preparar la imagen.");
  ctx.drawImage(video, 0, 0, lienzo.width, lienzo.height);

  // 0.75: el lápiz sigue legible y el archivo baja otro tanto. Cada kB es
  // tiempo que el niño pasa esperando.
  const url = lienzo.toDataURL("image/jpeg", 0.75);
  const base64 = url.split(",")[1] ?? "";
  if (base64.length < 1000) {
    // Un JPEG de un cuaderno pesa decenas de kB. Menos de 1 kB es un cuadro
    // negro o vacío — mandarlo sería peor que no mandar nada, porque el tutor
    // recibiría "una imagen" y hablaría de ella.
    throw new ErrorCamara("otro", "La foto salió vacía. Vuelve a intentarlo.");
  }
  console.info(`[camara] cuadro ${lienzo.width}x${lienzo.height}, ${Math.round(base64.length / 1024)} kB`);
  return { base64, mimeType: "image/jpeg" };
}
