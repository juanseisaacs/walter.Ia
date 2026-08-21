/**
 * Escribe un texto a mano, trazo por trazo.
 *
 * El truco entero cabe en dos líneas de CSS. Cada trazo es un `<path>` con
 * `pathLength="1"`, lo que normaliza su longitud a 1 sea cual sea su forma.
 * Entonces `stroke-dasharray: 1` lo convierte en "una raya del largo total más
 * un hueco del largo total", y animar `stroke-dashoffset` de 1 a 0 corre esa
 * raya de punta a punta: la línea se dibuja sola.
 *
 * Lo importante de hacerlo así y no con un canvas: no hay bucle de animación,
 * no hay `requestAnimationFrame`, no hay un solo frame de JavaScript
 * compitiendo con el audio del tutor. Lo anima el compositor del navegador.
 *
 * ── Por qué se exporta un `<g>` y no un `<svg>` ──────────────────────────────
 *
 * La primera versión devolvía un `<svg>` propio, y para meterlo en el tablero
 * lo envolvía en un `<foreignObject>`. Eso es un SVG adentro de un objeto
 * extranjero adentro de otro SVG: `foreignObject` está pensado para HTML, y con
 * contenido SVG el navegador no dibuja nada.
 *
 * En `ses_afce08f934ea` el niño pidió "muéstrame cómo se escribe la m de mamá"
 * y contestó "no vi nada, no hay ninguna pizarra". Las demás escenas —cajas,
 * puntos— se veían bien: la única que pasaba por `foreignObject` era esta.
 *
 * Los trazos YA son SVG. Envolverlos era el error. Ahora se dibujan derecho en
 * el lienzo del tablero, con un `translate`/`scale`, y para la pantalla suelta
 * hay un envoltorio aparte.
 */

import "./Escritura.css";
import { ALTO_GLIFO, ANCHO_GLIFO, MS_POR_TRAZO, trazosDe } from "./trazos";

/** Cuánto avanza el lápiz de un glifo al siguiente. */
const AVANCE = ANCHO_GLIFO * 0.86;
const ESPACIO = ANCHO_GLIFO * 0.5;

/** Cuánto mide el texto escrito, en unidades de glifo. */
export function anchoEscrito(texto: string): number {
  let x = 0;
  for (const c of texto) x += c === " " ? ESPACIO : trazosDe(c) ? AVANCE : 0;
  return Math.max(x, ANCHO_GLIFO);
}

/** Cuántos trazos lleva escribir esto. Sirve para encadenar animaciones. */
export function contarTrazos(texto: string): number {
  return [...texto].reduce((n, c) => n + (trazosDe(c)?.length ?? 0), 0);
}

/**
 * Los trazos, para poner DENTRO de un SVG que ya existe.
 *
 * Se dibuja en la caja natural de los glifos (`anchoEscrito` × `ALTO_GLIFO`);
 * quien lo usa lo coloca y lo escala con un `transform`.
 */
export function TrazosDeTexto({
  texto,
  desdeElTrazo = 0,
}: {
  texto: string;
  /** Desde qué trazo cuenta el retraso, para encadenar con lo demás. */
  desdeElTrazo?: number;
}) {
  let x = 0;
  let trazo = desdeElTrazo;

  return (
    <>
      {[...texto].map((c, i) => {
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
      })}
    </>
  );
}

/** El mismo texto, pero con su propio lienzo. Para usarlo fuera del tablero. */
export default function Escritura({ texto }: { texto: string }) {
  const ancho = anchoEscrito(texto);
  return (
    <svg
      viewBox={`-4 0 ${ancho + 8} ${ALTO_GLIFO}`}
      className="escritura"
      role="img"
      aria-label={texto}
    >
      <TrazosDeTexto texto={texto} />
    </svg>
  );
}
