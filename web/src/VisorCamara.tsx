/**
 * El visor de la cámara: lo que el niño ve para apuntar al cuaderno.
 *
 * Va flotando encima de la sesión, no en otra pantalla: el tutor le está
 * hablando mientras acomoda el cuaderno, y sacarlo de la conversación para
 * tomar una foto corta justamente lo que hace que esto funcione.
 *
 * Un botón grande y uno chico. El grande es el que va a usar, y va abajo al
 * centro, donde el pulgar ya está.
 */

import { useEffect, useRef } from "react";

export default function VisorCamara({
  stream,
  alTomar,
  alCancelar,
}: {
  stream: MediaStream;
  alTomar: (video: HTMLVideoElement) => void;
  alCancelar: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.srcObject = stream;
    void video.play().catch(() => {
      /* si el navegador lo bloquea, el niño ve el visor negro y puede cancelar */
    });
  }, [stream]);

  // Escape cancela: si el niño se arrepiente, la cámara se apaga ya.
  useEffect(() => {
    const alTecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") alCancelar();
    };
    window.addEventListener("keydown", alTecla);
    return () => window.removeEventListener("keydown", alTecla);
  }, [alCancelar]);

  return (
    <div className="visor" role="dialog" aria-label="Cámara">
      <div className="visor-marco">
        <video ref={videoRef} className="visor-video" muted playsInline />
        <p className="visor-ayuda">Apunta a tu cuaderno</p>
      </div>

      <div className="visor-botones">
        <button className="visor-cancelar" onClick={alCancelar} aria-label="Cerrar la cámara">
          Ahora no
        </button>
        <button
          className="visor-disparo"
          onClick={() => videoRef.current && alTomar(videoRef.current)}
          aria-label="Tomar la foto"
        >
          <span className="visor-disparo-punto" aria-hidden />
        </button>
        {/* Ocupa el mismo ancho que "Ahora no" para que el botón de disparo
            quede centrado de verdad, y no un poco corrido. */}
        <span className="visor-equilibrio" aria-hidden />
      </div>
    </div>
  );
}
