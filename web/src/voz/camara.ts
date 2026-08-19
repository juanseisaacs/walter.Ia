/**
 * Una foto del cuaderno, cuando el tutor la pide.
 *
 * UNA FOTO, NO VIDEO. La diferencia importa y es deliberada: hay un niño del
 * otro lado. Video continuo significa una cámara encendida en el cuarto de un
 * chico durante toda la sesión; una foto puntual, disparada porque el tutor
 * necesita ver la tarea, es lo mínimo que resuelve el problema. También es
 * muchísimo más barato en tokens.
 *
 * La cámara se abre, toma el cuadro y se cierra en el mismo suspiro. Nunca
 * queda prendida esperando.
 *
 * `request_camera` era un stub que devolvía `{pedido: true}` sin abrir nada: el
 * tutor le decía al niño "muéstrame tu cuaderno" y se quedaba esperando una
 * foto que no iba a llegar nunca. Sin ver la tarea, ayudar con ella es adivinar
 * — y ese es justo el modo donde el método tiene que ser MÁS estricto.
 */

/** Ancho al que se manda. Suficiente para leer un cuaderno, sin gastar de más. */
const ANCHO_MAX = 1024;

/** Si no hay imagen en este tiempo, algo se trabó y el tutor tiene que seguir. */
const ESPERA_MAX_MS = 6000;

export interface FotoTomada {
  base64: string;
  mimeType: "image/jpeg";
}

/**
 * Pide la cámara, captura un cuadro y la apaga.
 *
 * Tira si el permiso se niega o si la cámara no entrega imagen a tiempo. Quien
 * llama TIENE que manejarlo: el tutor no puede quedarse mudo esperando.
 */
export async function capturarFoto(): Promise<FotoTomada> {
  const stream = await navigator.mediaDevices.getUserMedia({
    // La de atrás si existe (el niño apunta al cuaderno); si no, la que haya.
    video: { facingMode: { ideal: "environment" }, width: { ideal: ANCHO_MAX } },
    audio: false,
  });

  try {
    const video = document.createElement("video");
    video.srcObject = stream;
    video.muted = true;
    video.playsInline = true;
    await video.play();

    // El primer cuadro suele salir negro: la cámara todavía está midiendo luz.
    await esperarCuadroUtil(video);

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
  } finally {
    // Pase lo que pase, la cámara se apaga. Dejarla prendida en el cuarto de un
    // niño por un error nuestro no es una opción.
    stream.getTracks().forEach((t) => t.stop());
  }
}

/** Espera a que el video tenga dimensiones y algún cuadro dibujable. */
function esperarCuadroUtil(video: HTMLVideoElement): Promise<void> {
  return new Promise((resolver, rechazar) => {
    const vencimiento = setTimeout(() => {
      rechazar(new Error("La cámara no respondió a tiempo."));
    }, ESPERA_MAX_MS);

    const listo = () => {
      if (!video.videoWidth) return false;
      clearTimeout(vencimiento);
      // Un respiro para el balance de blancos: sin esto la foto sale oscura y
      // el tutor "ve" un cuaderno negro, que es peor que no ver nada.
      setTimeout(resolver, 350);
      return true;
    };

    if (listo()) return;
    video.addEventListener("loadeddata", () => listo(), { once: true });
  });
}
