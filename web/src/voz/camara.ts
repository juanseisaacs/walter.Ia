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

/** Ancho al que se manda. Suficiente para leer un cuaderno, sin gastar de más. */
const ANCHO_MAX = 1024;

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
  const escala = Math.min(1, ANCHO_MAX / (video.videoWidth || ANCHO_MAX));
  const lienzo = document.createElement("canvas");
  lienzo.width = Math.round(video.videoWidth * escala);
  lienzo.height = Math.round(video.videoHeight * escala);

  const ctx = lienzo.getContext("2d");
  if (!ctx) throw new Error("No pude preparar la imagen.");
  ctx.drawImage(video, 0, 0, lienzo.width, lienzo.height);

  // 0.8: el texto a lápiz sigue legible y pesa la mitad que sin comprimir.
  const url = lienzo.toDataURL("image/jpeg", 0.8);
  return { base64: url.split(",")[1] ?? "", mimeType: "image/jpeg" };
}
