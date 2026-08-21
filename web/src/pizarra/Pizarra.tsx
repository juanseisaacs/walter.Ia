/**
 * El tablero del tutor.
 *
 * SVG y no Canvas 2D, y la razón importa:
 *
 *   · Se adapta solo. Un `viewBox` y la misma escena se ve bien en un celular
 *     y en un portátil. Con canvas habría que recalcular y redibujar a mano en
 *     cada cambio de tamaño.
 *   · El texto es texto. Nítido a cualquier zoom, y un lector de pantalla lo lee.
 *   · La animación de "se está escribiendo" sale con CSS. Sin bucle de dibujo,
 *     sin `requestAnimationFrame`, sin un frame de trabajo por cuadro.
 *
 * Nada de esto toca la voz. El tablero solo recibe una escena y la pinta.
 */

import { useEffect, useState } from "react";

import "./Pizarra.css";
import { TrazosDeTexto, anchoEscrito, contarTrazos } from "./Escritura";
import { ALTO_GLIFO, seEscribeAMano } from "./trazos";
import {
  MAX_PUNTOS_CONTABLES,
  MS_ENTRE_TRAZOS,
  type Anotacion,
  type Cuadro,
  type Escena,
} from "./escenas";

/** Lienzo lógico. Todo se dibuja acá adentro y el SVG lo escala solo. */
const ANCHO = 400;
const ALTO = 300;

export default function Pizarra({ cuadro }: { cuadro: Cuadro | null }) {
  // Se remonta el contenido al cambiar de escena para que las animaciones
  // vuelvan a correr desde cero. Sin esto, la segunda escena aparece de golpe.
  const [generacion, setGeneracion] = useState(0);
  useEffect(() => setGeneracion((g) => g + 1), [cuadro]);

  if (!cuadro) {
    // El tablero sale solo cuando hay algo que valga la pena mirar. Vacío no
    // compite por la atención del niño: no está.
    return null;
  }

  return (
    <div className="pizarra" aria-live="polite">
      <svg
        key={generacion}
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        className="pizarra-lienzo"
        role="img"
        aria-label={describir(cuadro.escena)}
      >
        <Cuadricula />
        <Dibujo escena={cuadro.escena} />
        {cuadro.anotaciones?.map((a, i) => (
          <Marca key={i} anotacion={a} escena={cuadro.escena} orden={i} />
        ))}
      </svg>
    </div>
  );
}

/** La cuadrícula del cuaderno, apenas visible. Da la sensación de hoja. */
function Cuadricula() {
  return (
    <>
      <defs>
        <pattern id="cuadros" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M20 0 L0 0 0 20" fill="none" stroke="var(--pizarra-renglon)" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width={ANCHO} height={ALTO} fill="url(#cuadros)" />
    </>
  );
}

function Dibujo({ escena }: { escena: Escena }) {
  switch (escena.tipo) {
    case "operacion":
      return <VistaOperacion e={escena} />;
    case "grupos":
      return <VistaGrupos e={escena} />;
    case "recta":
      return <VistaRecta e={escena} />;
    case "fraccion":
      return <VistaFraccion e={escena} />;
    case "texto":
      return <VistaTexto e={escena} />;
  }
}

/** Un trazo que aparece en su turno. `paso` es el lugar en la secuencia. */
function Trazo({ paso, children }: { paso: number; children: React.ReactNode }) {
  return (
    <g className="trazo" style={{ animationDelay: `${paso * MS_ENTRE_TRAZOS}ms` }}>
      {children}
    </g>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Escena: la cuenta en columna
// ─────────────────────────────────────────────────────────────────────────────
//
// Alineada a la derecha por columnas, como en el cuaderno. Las coordenadas de
// cada columna se calculan acá y se reusan para las anotaciones: por eso el
// tutor puede decir "resaltá las unidades" sin saber dónde cayeron.

const COL_ANCHO = 46;
const COL_DERECHA = 300;
const FILA_A = 120;
const FILA_B = 180;
const FILA_RESULTADO = 250;

/** Centro en X de la columna `i` contando desde la derecha (0 = unidades). */
function columnaX(i: number): number {
  return COL_DERECHA - i * COL_ANCHO;
}

function digitos(n: number): string[] {
  return Math.abs(n).toString().split("");
}

function VistaOperacion({ e }: { e: import("./escenas").Operacion }) {
  const da = digitos(e.a);
  const db = digitos(e.b);
  const ancho = Math.max(da.length, db.length, e.resultado ? digitos(e.resultado).length : 0);
  const izquierda = columnaX(ancho - 1) - COL_ANCHO / 2;

  let paso = 0;
  return (
    <>
      {e.llevada !== undefined && (
        <Trazo paso={paso++}>
          <text x={columnaX(1)} y={FILA_A - 42} className="pz-llevada">
            {e.llevada}
          </text>
        </Trazo>
      )}

      {da.map((d, i) => (
        <Trazo key={`a${i}`} paso={paso++}>
          <text x={columnaX(da.length - 1 - i)} y={FILA_A} className="pz-digito">
            {d}
          </text>
        </Trazo>
      ))}

      <Trazo paso={paso++}>
        <text x={izquierda - 34} y={FILA_B} className="pz-signo">
          {e.op}
        </text>
      </Trazo>

      {db.map((d, i) => (
        <Trazo key={`b${i}`} paso={paso++}>
          <text x={columnaX(db.length - 1 - i)} y={FILA_B} className="pz-digito">
            {d}
          </text>
        </Trazo>
      ))}

      <Trazo paso={paso++}>
        <line
          x1={izquierda - 44}
          y1={FILA_B + 22}
          x2={COL_DERECHA + COL_ANCHO / 2}
          y2={FILA_B + 22}
          className="pz-linea"
        />
      </Trazo>

      {e.resultado !== undefined &&
        digitos(e.resultado).map((d, i, arr) => (
          <Trazo key={`r${i}`} paso={paso++}>
            <text x={columnaX(arr.length - 1 - i)} y={FILA_RESULTADO} className="pz-digito">
              {d}
            </text>
          </Trazo>
        ))}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Escena: grupos iguales
// ─────────────────────────────────────────────────────────────────────────────

function VistaGrupos({ e }: { e: import("./escenas").Grupos }) {
  const cols = Math.min(e.grupos, 5);
  const filas = Math.ceil(e.grupos / cols);
  const cajaAncho = Math.min(120, (ANCHO - 60) / cols - 12);
  const cajaAlto = Math.min(90, (ALTO - 110) / filas - 12);
  const x0 = (ANCHO - (cajaAncho + 12) * cols + 12) / 2;
  const y0 = 70;

  // Con pocas cosas por grupo se dibujan los puntos y el niño los cuenta. Con
  // muchas se escribe el número adentro: 45 puntos apretados en una cajita no
  // son un dibujo, son una mancha, y nadie cuenta 135.
  const conPuntos = e.porGrupo <= MAX_PUNTOS_CONTABLES;
  const pCols = Math.ceil(Math.sqrt(e.porGrupo));
  const pFilas = Math.ceil(e.porGrupo / pCols);

  return (
    <>
      <Trazo paso={0}>
        <text x={ANCHO / 2} y={44} className="pz-rotulo">
          {e.grupos} {e.nombre ?? "grupos"} de {e.porGrupo}
        </text>
      </Trazo>

      {Array.from({ length: e.grupos }, (_, g) => {
        const cx = x0 + (g % cols) * (cajaAncho + 12);
        const cy = y0 + Math.floor(g / cols) * (cajaAlto + 12);
        return (
          <Trazo key={g} paso={g + 1}>
            <rect x={cx} y={cy} width={cajaAncho} height={cajaAlto} rx="8" className="pz-caja" />
            {conPuntos ? (
              Array.from({ length: e.porGrupo }, (_, p) => (
                <circle
                  key={p}
                  cx={cx + (cajaAncho / (pCols + 1)) * ((p % pCols) + 1)}
                  cy={cy + (cajaAlto / (pFilas + 1)) * (Math.floor(p / pCols) + 1)}
                  r="6"
                  className="pz-punto"
                />
              ))
            ) : (
              <text x={cx + cajaAncho / 2} y={cy + cajaAlto / 2 + 12} className="pz-en-caja">
                {e.porGrupo}
              </text>
            )}
          </Trazo>
        );
      })}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Escena: recta numérica
// ─────────────────────────────────────────────────────────────────────────────

function VistaRecta({ e }: { e: import("./escenas").Recta }) {
  const x0 = 40;
  const x1 = ANCHO - 40;
  const y = 170;
  const total = Math.max(1, e.hasta - e.desde);
  // Con muchos números no caben todos los rótulos: se muestran salteados.
  const cada = Math.ceil(total / 10);
  const aX = (n: number) => x0 + ((n - e.desde) / total) * (x1 - x0);

  return (
    <>
      <Trazo paso={0}>
        <line x1={x0} y1={y} x2={x1} y2={y} className="pz-linea" />
      </Trazo>

      {Array.from({ length: total + 1 }, (_, i) => e.desde + i).map((n, i) => (
        <Trazo key={n} paso={1 + Math.floor(i / 4)}>
          <line x1={aX(n)} y1={y - 8} x2={aX(n)} y2={y + 8} className="pz-tick" />
          {(n - e.desde) % cada === 0 && (
            <text x={aX(n)} y={y + 34} className="pz-numerito">
              {n}
            </text>
          )}
        </Trazo>
      ))}

      {e.marca !== undefined && (
        <Trazo paso={6}>
          <circle cx={aX(e.marca)} cy={y} r="9" className="pz-marca" />
        </Trazo>
      )}

      {e.marca !== undefined && e.saltaA !== undefined && (
        <Trazo paso={7}>
          <path
            d={`M ${aX(e.marca)} ${y - 14} Q ${(aX(e.marca) + aX(e.saltaA)) / 2} ${y - 76} ${aX(e.saltaA)} ${y - 14}`}
            className="pz-salto"
            markerEnd="url(#punta)"
          />
          <text x={(aX(e.marca) + aX(e.saltaA)) / 2} y={y - 82} className="pz-rotulo-chico">
            {e.saltaA > e.marca ? "+" : "−"}
            {Math.abs(e.saltaA - e.marca)}
          </text>
        </Trazo>
      )}
      <Punta />
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Escena: fracción
// ─────────────────────────────────────────────────────────────────────────────

function VistaFraccion({ e }: { e: import("./escenas").Fraccion }) {
  const llenas = Math.max(0, Math.min(e.numerador, e.denominador));

  if (e.forma === "torta") {
    const cx = ANCHO / 2;
    const cy = 160;
    const r = 88;
    const porción = (i: number) => {
      const a0 = (i / e.denominador) * 2 * Math.PI - Math.PI / 2;
      const a1 = ((i + 1) / e.denominador) * 2 * Math.PI - Math.PI / 2;
      const grande = a1 - a0 > Math.PI ? 1 : 0;
      return `M ${cx} ${cy} L ${cx + r * Math.cos(a0)} ${cy + r * Math.sin(a0)} A ${r} ${r} 0 ${grande} 1 ${cx + r * Math.cos(a1)} ${cy + r * Math.sin(a1)} Z`;
    };
    return (
      <>
        <Trazo paso={0}>
          <text x={ANCHO / 2} y={44} className="pz-rotulo">
            {e.numerador}/{e.denominador}
          </text>
        </Trazo>
        {Array.from({ length: e.denominador }, (_, i) => (
          <Trazo key={i} paso={i + 1}>
            <path d={porción(i)} className={i < llenas ? "pz-porcion-llena" : "pz-porcion"} />
          </Trazo>
        ))}
      </>
    );
  }

  const ancho = ANCHO - 80;
  const alto = 90;
  const x0 = 40;
  const y0 = 110;
  const paso = ancho / e.denominador;

  return (
    <>
      <Trazo paso={0}>
        <text x={ANCHO / 2} y={70} className="pz-rotulo">
          {e.numerador}/{e.denominador}
        </text>
      </Trazo>
      {Array.from({ length: e.denominador }, (_, i) => (
        <Trazo key={i} paso={i + 1}>
          <rect
            x={x0 + i * paso}
            y={y0}
            width={paso}
            height={alto}
            className={i < llenas ? "pz-porcion-llena" : "pz-porcion"}
          />
        </Trazo>
      ))}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Escena: texto grande
// ─────────────────────────────────────────────────────────────────────────────

function VistaTexto({ e }: { e: import("./escenas").Texto }) {
  // Si sabemos trazar TODOS sus caracteres, se escribe a mano: el niño ve por
  // dónde empieza el lápiz y hacia dónde va, que es justo lo que necesita para
  // aprender a escribirla. Si aparece uno que no tenemos, cae a la letra
  // impresa de siempre — mostrarla bien y quieta le gana a no mostrarla.
  if (seEscribeAMano(e.contenido)) {
    // Se escala para llenar el alto disponible sin pasarse del ancho, y se
    // centra. Todo con un `transform` en el MISMO lienzo: sin envoltorios.
    const alto = e.pie ? 170 : 200;
    const anchoNatural = anchoEscrito(e.contenido);
    const escala = Math.min(alto / ALTO_GLIFO, (ANCHO - 60) / anchoNatural);
    const x = (ANCHO - anchoNatural * escala) / 2;
    const y = e.pie ? 45 : 60;

    return (
      <>
        <g transform={`translate(${x} ${y}) scale(${escala})`}>
          <TrazosDeTexto texto={e.contenido} />
        </g>
        {e.pie && (
          <Trazo paso={contarTrazos(e.contenido) + 1}>
            <text x={ANCHO / 2} y={268} className="pz-rotulo-chico">
              {e.pie}
            </text>
          </Trazo>
        )}
      </>
    );
  }
  return <TextoImpreso e={e} />;
}

function TextoImpreso({ e }: { e: import("./escenas").Texto }) {
  // Cuanto más largo, más chico — pero nunca por debajo de lo que un chico de
  // 7 lee cómodo a un brazo de distancia.
  const tam = Math.max(40, Math.min(140, 420 / Math.max(1, e.contenido.length)));
  return (
    <>
      <Trazo paso={0}>
        <text
          x={ANCHO / 2}
          y={e.pie ? 165 : 185}
          className="pz-grande"
          style={{ fontSize: `${tam}px` }}
        >
          {e.contenido}
        </text>
      </Trazo>
      {e.pie && (
        <Trazo paso={1}>
          <text x={ANCHO / 2} y={225} className="pz-rotulo-chico">
            {e.pie}
          </text>
        </Trazo>
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Anotaciones: el marcador del profe encima de lo ya escrito
// ─────────────────────────────────────────────────────────────────────────────
//
// Traduce un ancla ("unidades") a la caja que ocupa en pantalla. Es lo único
// que sabe de coordenadas — el tutor nunca las ve.

function caja(ancla: Anotacion["ancla"], escena: Escena) {
  if (escena.tipo === "operacion") {
    const alto = 86;
    const porColumna = (i: number) => ({
      x: columnaX(i) - COL_ANCHO / 2,
      y: FILA_A - 40,
      w: COL_ANCHO,
      h: alto,
    });
    switch (ancla) {
      case "unidades":
        return porColumna(0);
      case "decenas":
        return porColumna(1);
      case "centenas":
        return porColumna(2);
      case "llevada":
        return { x: columnaX(1) - 20, y: FILA_A - 68, w: 40, h: 36 };
      case "resultado":
        return { x: 100, y: FILA_RESULTADO - 40, w: 230, h: 52 };
      case "primero":
        return { x: 100, y: FILA_A - 40, w: 230, h: 52 };
      case "segundo":
        return { x: 100, y: FILA_B - 40, w: 230, h: 52 };
    }
  }
  return { x: 24, y: 24, w: ANCHO - 48, h: ALTO - 48 };
}

function Marca({
  anotacion,
  escena,
  orden,
}: {
  anotacion: Anotacion;
  escena: Escena;
  orden: number;
}) {
  const c = caja(anotacion.ancla, escena);
  const clase = `pz-anot pz-anot-${anotacion.tono ?? "neutro"}`;
  // Entran DESPUÉS de la escena: primero se lee lo escrito, después la marca.
  const retraso = { animationDelay: `${900 + orden * MS_ENTRE_TRAZOS}ms` };

  if (anotacion.gesto === "tachado") {
    return (
      <g className="trazo" style={retraso}>
        <line x1={c.x} y1={c.y + c.h} x2={c.x + c.w} y2={c.y} className={clase} />
      </g>
    );
  }

  if (anotacion.gesto === "flecha") {
    return (
      <g className="trazo" style={retraso}>
        <line
          x1={c.x + c.w / 2}
          y1={c.y - 42}
          x2={c.x + c.w / 2}
          y2={c.y - 8}
          className={clase}
          markerEnd="url(#punta)"
        />
        <Punta />
      </g>
    );
  }

  return (
    <g className="trazo" style={retraso}>
      <ellipse
        cx={c.x + c.w / 2}
        cy={c.y + c.h / 2}
        rx={c.w / 2 + 6}
        ry={c.h / 2 + 4}
        className={clase}
        fill="none"
      />
    </g>
  );
}

function Punta() {
  return (
    <defs>
      <marker id="punta" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L7,3 z" fill="var(--pizarra-marca)" />
      </marker>
    </defs>
  );
}

/** Para quien no ve el tablero: lo mismo, dicho. */
function describir(e: Escena): string {
  switch (e.tipo) {
    case "operacion":
      return `${e.a} ${e.op} ${e.b}${e.resultado !== undefined ? ` = ${e.resultado}` : ""}`;
    case "grupos":
      return `${e.grupos} grupos de ${e.porGrupo}`;
    case "recta":
      return `recta numérica del ${e.desde} al ${e.hasta}`;
    case "fraccion":
      return `${e.numerador} de ${e.denominador}`;
    case "texto":
      return e.contenido;
  }
}
