/**
 * La hoja en blanco: el turno del niño.
 *
 * El tutor dice "dibujá la N" y acá el niño traza, con el dedo o con el mouse.
 *
 * Lo importante para el resto del sistema: cuando toca "listo", esto entrega un
 * PNG. Es exactamente lo que ya produce la cámara, así que viaja por el MISMO
 * camino que ya está peleado y funcionando (`sendRealtimeInput` con la imagen,
 * directo a Gemini). No hay que construir nada nuevo para que el tutor lo vea:
 * es la cámara con otra fuente.
 *
 * `pointer` y no `mouse`/`touch` por separado: un solo juego de eventos cubre
 * dedo, lápiz y ratón. Menos código y no se olvida ningún dispositivo.
 */

import { useRef, useState } from "react";

import "./HojaDelNino.css";

/** Lienzo interno. Fijo, para que el PNG salga siempre del mismo tamaño. */
const ANCHO = 640;
const ALTO = 420;
const GROSOR = 7;

type Punto = { x: number; y: number };

export default function HojaDelNino({
  consigna,
  alEnviar,
  alCancelar,
}: {
  consigna: string;
  /** Recibe el PNG en base64, sin el prefijo `data:` — igual que la cámara. */
  alEnviar: (pngBase64: string) => void;
  alCancelar?: () => void;
}) {
  const lienzoRef = useRef<HTMLCanvasElement | null>(null);
  const dibujandoRef = useRef(false);
  // Los trazos se guardan para poder deshacer: un canvas solo no recuerda nada.
  const trazosRef = useRef<Punto[][]>([]);
  const [hayAlgo, setHayAlgo] = useState(false);

  function repintar() {
    const c = lienzoRef.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;

    ctx.fillStyle = leerToken("--pizarra-fondo", "#fffdf7");
    ctx.fillRect(0, 0, ANCHO, ALTO);

    ctx.strokeStyle = leerToken("--pizarra-tinta", "#33312c");
    ctx.lineWidth = GROSOR;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    for (const trazo of trazosRef.current) {
      if (trazo.length === 0) continue;
      ctx.beginPath();
      ctx.moveTo(trazo[0].x, trazo[0].y);
      // Un punto suelto (un toque) también se ve: si no, tocar no hace nada.
      if (trazo.length === 1) ctx.lineTo(trazo[0].x + 0.1, trazo[0].y);
      for (const p of trazo.slice(1)) ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
    setHayAlgo(trazosRef.current.length > 0);
  }

  /** De coordenadas de pantalla a coordenadas del lienzo. */
  function aLienzo(e: React.PointerEvent): Punto {
    const c = lienzoRef.current!;
    const r = c.getBoundingClientRect();
    return {
      x: ((e.clientX - r.left) / r.width) * ANCHO,
      y: ((e.clientY - r.top) / r.height) * ALTO,
    };
  }

  return (
    <div className="hoja">
      <p className="hoja-consigna">{consigna}</p>

      <canvas
        ref={(el) => {
          lienzoRef.current = el;
          if (el && trazosRef.current.length === 0) repintar();
        }}
        width={ANCHO}
        height={ALTO}
        className="hoja-lienzo"
        // Sin esto el navegador hace scroll con el dedo en vez de dejar dibujar.
        style={{ touchAction: "none" }}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          dibujandoRef.current = true;
          trazosRef.current.push([aLienzo(e)]);
          repintar();
        }}
        onPointerMove={(e) => {
          if (!dibujandoRef.current) return;
          trazosRef.current[trazosRef.current.length - 1].push(aLienzo(e));
          repintar();
        }}
        onPointerUp={() => {
          dibujandoRef.current = false;
        }}
        onPointerLeave={() => {
          dibujandoRef.current = false;
        }}
      />

      <div className="hoja-botones">
        <button
          className="hoja-boton"
          disabled={!hayAlgo}
          onClick={() => {
            trazosRef.current.pop();
            repintar();
          }}
        >
          Borrar lo último
        </button>

        <button
          className="hoja-boton"
          disabled={!hayAlgo}
          onClick={() => {
            trazosRef.current = [];
            repintar();
          }}
        >
          Empezar de nuevo
        </button>

        {alCancelar && (
          <button className="hoja-boton" onClick={alCancelar}>
            Ahora no
          </button>
        )}

        <button
          className="hoja-boton hoja-boton-listo"
          disabled={!hayAlgo}
          onClick={() => {
            const png = lienzoRef.current!.toDataURL("image/png");
            alEnviar(png.split(",")[1]);
          }}
        >
          Listo, mira
        </button>
      </div>
    </div>
  );
}

/** El canvas no entiende `var(--…)`: hay que resolverlo antes de pintar. */
function leerToken(nombre: string, siFalta: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
  return v || siFalta;
}
