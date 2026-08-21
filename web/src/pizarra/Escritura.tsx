/**
 * Escribe un texto a mano, trazo por trazo.
 *
 * El truco entero cabe en dos líneas de CSS. Cada trazo lleva `pathLength="1"`,
 * lo que normaliza su longitud a 1 sea cual sea su forma. Entonces
 * `stroke-dasharray: 1` lo convierte en "una raya del largo total más un hueco
 * del largo total", y animar `stroke-dashoffset` de 1 a 0 corre esa raya de
 * punta a punta: la línea se dibuja sola.
 *
 * Lo importante de hacerlo así y no con un canvas: no hay bucle de animación,
 * no hay `requestAnimationFrame`, no hay un solo frame de JavaScript
 * compitiendo con el audio del tutor. Lo anima el compositor del navegador.
 */

import "./Escritura.css";
import { ALTO_GLIFO, ANCHO_GLIFO, MS_POR_TRAZO, trazosDe } from "./trazos";

/** Cuánto se solapa un glifo con el siguiente. Sin esto las letras van sueltas. */
const AVANCE = ANCHO_GLIFO * 0.86;
const ESPACIO = ANCHO_GLIFO * 0.5;

export default function Escritura({
  texto,
  /** Desde qué trazo empieza a contar el retraso, para encadenar con lo demás. */
  desdeElTrazo = 0,
}: {
  texto: string;
  desdeElTrazo?: number;
}) {
  const caracteres = [...texto];
  let x = 0;
  let trazo = desdeElTrazo;

  const glifos = caracteres.map((c, i) => {
    if (c === " ") {
      x += ESPACIO;
      return null;
    }
    const trazos = trazosDe(c);
    if (!trazos) return null;
    const enX = x;
    x += AVANCE;
    return (
      <g key={i} transform={`translate(${enX} 0)`}>
        {trazos.map((d, t) => (
          <path
            key={t}
            d={d}
            pathLength="1"
            className="escritura-trazo"
            style={{ animationDelay: `${trazo++ * MS_POR_TRAZO}ms` }}
          />
        ))}
      </g>
    );
  });

  // El ancho real se conoce recién después de recorrer todo: el viewBox se
  // ajusta al texto, y el SVG lo escala para que ocupe lo que le den.
  const ancho = Math.max(x, ANCHO_GLIFO);

  return (
    <svg
      viewBox={`-4 0 ${ancho + 8} ${ALTO_GLIFO}`}
      className="escritura"
      role="img"
      aria-label={texto}
    >
      {glifos}
    </svg>
  );
}

/** Cuántos trazos lleva escribir esto. Sirve para encadenar animaciones. */
export function contarTrazos(texto: string): number {
  return [...texto].reduce((n, c) => n + (trazosDe(c)?.length ?? 0), 0);
}
