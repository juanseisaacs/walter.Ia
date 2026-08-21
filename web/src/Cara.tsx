/**
 * La cara del tutor. Dos ojos y una boca.
 *
 * Deliberadamente mínima. No es el personaje final — es lo justo para que el
 * niño sienta que le habla alguien y no una bolita de color. Un personaje de
 * verdad se diseña, y todavía no está diseñado; poner uno a medias sería peor
 * que este, porque un dibujo feo sí se nota.
 *
 * No sabe NADA de la voz: recibe si está hablando y cuánto suena el micrófono.
 * Se puede mirar y ajustar sin abrir una sesión, y si se rompe no arrastra a
 * nadie.
 *
 * La boca se mueve con una animación de CSS y no con el audio real. Se pensó
 * medir el volumen de salida para sincronizarla, y se descartó: habría que
 * meter un analizador en el camino del audio, que es justo donde no se regala
 * nada. Una boca que se mueve al hablar y se queda quieta al escuchar ya
 * comunica todo lo que tiene que comunicar.
 */

import "./Cara.css";

export default function Cara({
  hablando,
  /** 0 a 1. Late un poquito con la voz del niño mientras escucha. */
  nivelMic = 0,
}: {
  hablando: boolean;
  nivelMic?: number;
}) {
  // Al escuchar, la cara respira con la voz del niño: le devuelve la señal de
  // que lo están oyendo. Al hablar, queda quieta — el movimiento es la boca.
  const escala = hablando ? 1.04 : 1 + nivelMic * 0.12;

  return (
    <svg
      viewBox="0 0 100 100"
      className={`cara ${hablando ? "cara-hablando" : "cara-escuchando"}`}
      style={{ transform: `scale(${escala})` }}
      role="img"
      aria-label={hablando ? "tu tutor está hablando" : "tu tutor te escucha"}
    >
      <circle cx="50" cy="50" r="46" className="cara-cabeza" />

      {/* Los ojos parpadean cada tanto. Cuesta dos líneas de CSS y es lo que
          más hace que se sienta vivo en vez de dibujado. */}
      <g className="cara-ojos">
        <circle cx="35" cy="42" r="6" className="cara-ojo" />
        <circle cx="65" cy="42" r="6" className="cara-ojo" />
      </g>

      {/* Una sola boca que cambia de forma. Callada es una sonrisa; hablando,
          se abre y se cierra. Dos elementos que se alternan darían un salto. */}
      <path className="cara-boca" d="M36 66 Q50 76 64 66" />
      <ellipse className="cara-boca-abierta" cx="50" cy="68" rx="13" ry="9" />
    </svg>
  );
}
