/**
 * La hoja en blanco: el turno del niño.
 *
 * El tutor dice "dibujá la N" y acá el niño traza, con el dedo o con el mouse.
 *
 * Lo importante para el resto del sistema: cuando toca "listo", esto entrega un
 * JPEG — el MISMO formato y el MISMO camino que la foto de la cámara
 * (`sendRealtimeInput`, directo a Gemini), que es lo único verificado con
 * imágenes reales. El dibujo es la cámara con otra fuente, y conviene que se
 * parezca a la cámara hasta en el formato.
 *
 * `pointer` y no `mouse`/`touch` por separado: un solo juego de eventos cubre
 * dedo, lápiz y ratón. Menos código y no se olvida ningún dispositivo.
 */

import { useRef, useState } from "react";

import Pizarra from "./Pizarra";
import type { Cuadro } from "./escenas";
import "./HojaDelNino.css";

/** Lienzo interno. Fijo, para que la imagen salga siempre del mismo tamaño. */
const ANCHO = 640;
const ALTO = 420;
const GROSOR = 7;

type Punto = { x: number; y: number };

export default function HojaDelNino({
  consigna,
  referencia,
  alEnviar,
  alCancelar,
  enviado = false,
}: {
  consigna: string;
  /** Lo que quedó en la pizarra cuando se abrió la hoja: el MODELO A COPIAR.
   *
   * `ses_445f4c33db41`: el tutor le mostró la W en el tablero, le abrió la hoja
   * para que la trazara, y la hoja tapó la W. El niño lo dijo enseguida —«a
   * ver, okay, sí, pero no me sale el tablero»— y el tutor, que no puede ver la
   * pantalla, le contestó "déjame lo mando otra vez" y volvió a no aparecer.
   *
   * Copiar una letra que ya no está en pantalla es de memoria, no de copia. */
  referencia?: Cuadro | null;
  /** Recibe el JPEG en base64, sin el prefijo `data:` — igual que la cámara. */
  alEnviar: (jpegBase64: string) => void;
  alCancelar?: () => void;
  /** ¿Ya se la mandó al tutor? LO QUE PIDIÓ EL NIÑO (`ses_74b6cc7667ae`):
   *
   *    «Sería bueno que cuando yo te envío algo que yo escribí en el tablero,
   *     NO SE DESAPAREZCA, sino que tú me corrijas encima de la palabra.»
   *
   *  Se borraba en el instante en que la mandaba, así que el niño escuchaba
   *  «la h tiene que subir un poco más» mirando una hoja vacía — sin la letra
   *  de la que le estaban hablando. Ahora queda, y **sigue siendo editable**:
   *  eso es justo lo que hace falta para corregirla. */
  enviado?: boolean;
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

      {/* El modelo, chiquito y arriba. Si no hay, la hoja queda igual que
          siempre: `Pizarra` devuelve null con `cuadro` vacío. */}
      {referencia ? (
        <div className="hoja-modelo">
          <Pizarra cuadro={referencia} />
        </div>
      ) : null}

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
            {enviado ? "Cerrar" : "Ahora no"}
          </button>
        )}

        <button
          className="hoja-boton hoja-boton-listo"
          disabled={!hayAlgo}
          onClick={() => {
            // JPEG y no PNG, aunque un dibujo de líneas pida PNG a gritos.
            //
            // La foto de la cámara viaja como `image/jpeg` y ESO está
            // verificado con imágenes reales: el tutor leyó las letras de una
            // gorra y contó cinco dedos. El dibujo salía en PNG por el mismo
            // canal, y el tutor decía "te quedó genial" sobre trazos que nunca
            // vio (ses_d333d1fc37ce).
            //
            // Es la lección que ya está escrita en `tomarFoto`: lo verificado
            // le gana a lo que parece correcto. Un dibujo es negro sobre
            // blanco; a calidad 0,9 el JPEG lo entrega perfectamente legible.
            const jpeg = lienzoRef.current!.toDataURL("image/jpeg", 0.9);
            alEnviar(jpeg.split(",")[1]);
          }}
        >
          {enviado ? "Mándasela otra vez" : "Listo, mira"}
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
