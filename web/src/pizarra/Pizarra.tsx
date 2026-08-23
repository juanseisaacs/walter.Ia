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
import { dibujoDe } from "./emojis";
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
    case "lista":
      return <VistaLista e={escena} />;
  }
}

/**
 * Las palabras, una debajo de otra, cada una de su color.
 *
 * El color acá hace trabajo: son cosas distintas y separadas, y con todas del
 * mismo tinte la lista se lee como un párrafo. Aparecen una por una —el niño
 * las va viendo escribirse— pero al final quedan TODAS, que es el punto.
 */
function VistaLista({ e }: { e: import("./escenas").Lista }) {
  const n = e.palabras.length;
  const alto = Math.min(62, (ALTO - 50) / n);
  const y0 = (ALTO - alto * (n - 1)) / 2 - 6;
  // Que la más larga entre siempre: el ancho manda sobre el alto.
  const masLarga = Math.max(...e.palabras.map((p) => p.length));
  const tam = Math.max(26, Math.min(alto * 0.78, (ANCHO - 50) / (masLarga * 0.58)));

  return (
    <>
      {e.palabras.map((palabra, i) => (
        <Trazo key={`${i}-${palabra}`} paso={i}>
          <text
            x={ANCHO / 2}
            y={y0 + i * alto}
            className={`pz-grande pz-lista-${(i % 4) + 1}`}
            style={{ fontSize: `${tam}px` }}
          >
            {palabra}
          </text>
        </Trazo>
      ))}
    </>
  );
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
  // Cuántos van en cada caja. Sin `cantidades` son todas iguales, que es la
  // multiplicación de siempre; con ellas, cada caja lleva lo suyo y la escena
  // sirve para sumar (ses_97d5b112a122).
  const cuantos = e.cantidades?.length ? e.cantidades : Array<number>(e.grupos).fill(e.porGrupo);
  const cols = Math.min(cuantos.length, 5);
  const filas = Math.ceil(cuantos.length / cols);
  const cajaAncho = Math.min(120, (ANCHO - 60) / cols - 12);
  const cajaAlto = Math.min(90, (ALTO - 110) / filas - 12);
  const x0 = (ANCHO - (cajaAncho + 12) * cols + 12) / 2;
  const y0 = 70;

  // Si el tutor dijo "gallinas", que salgan gallinas. Lo pidió Juan con esas
  // palabras — ver `emojis.ts`. Sin coincidencia, el punto de siempre.
  const dibujo = dibujoDe(e.nombre);

  return (
    <>
      <Trazo paso={0}>
        <text x={ANCHO / 2} y={44} className="pz-rotulo">
          {/* Con cantidades distintas el rótulo ES la cuenta: "5 + 3 + 6
              pollitos". Decir "3 grupos de 5" sobre cajas desiguales sería
              describirle mal lo que tiene delante. */}
          {e.cantidades?.length
            ? `${e.cantidades.join(" + ")} ${e.nombre ?? "en total"}`
            : `${e.grupos} ${e.nombre ?? "grupos"} de ${e.porGrupo}`}
        </text>
      </Trazo>

      {cuantos.map((cuantas, g) => {
        const cx = x0 + (g % cols) * (cajaAncho + 12);
        const cy = y0 + Math.floor(g / cols) * (cajaAlto + 12);
        // Con pocas cosas se dibujan y el niño las cuenta; con muchas va el
        // número adentro: 45 puntos apretados no son un dibujo, son una mancha.
        // Se decide POR CAJA, que es lo que permite mezclar 3 con 20.
        const conPuntos = cuantas <= MAX_PUNTOS_CONTABLES;
        const pCols = Math.ceil(Math.sqrt(cuantas));
        const pFilas = Math.ceil(cuantas / pCols);
        return (
          <Trazo key={g} paso={g + 1}>
            <g className={`pz-grupo-${g % 5}`}>
            <rect x={cx} y={cy} width={cajaAncho} height={cajaAlto} rx="8" className="pz-caja" />
            {conPuntos ? (
              Array.from({ length: cuantas }, (_, p) => {
                const px = cx + (cajaAncho / (pCols + 1)) * ((p % pCols) + 1);
                const py = cy + (cajaAlto / (pFilas + 1)) * (Math.floor(p / pCols) + 1);
                // El emoji se ancla por su centro; el punto, por el suyo. Sin
                // el `dy` los dibujitos quedan medio renglón por encima de
                // donde estaban los puntos.
                return dibujo ? (
                  <text key={p} x={px} y={py} dy="0.35em" className="pz-dibujo">
                    {dibujo}
                  </text>
                ) : (
                  <circle key={p} cx={px} cy={py} r="6" className="pz-punto" />
                );
              })
            ) : (
              <text x={cx + cajaAncho / 2} y={cy + cajaAlto / 2 + 12} className="pz-en-caja">
                {cuantas}
              </text>
            )}
            </g>
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

/**
 * Dos fracciones lado a lado, cada una de su color. Comparar es EL uso.
 *
 * Se dibujan siempre como tortas y del MISMO tamaño: si una fuera más grande
 * que la otra, el dibujo estaría contestando la pregunta antes que el niño.
 */
function VistaComparacion({ e }: { e: import("./escenas").Fraccion }) {
  const b = e.comparar!;
  const r = 82;
  const cy = 190;

  const porcion = (cx: number, i: number, partes: number) => {
    const a0 = (i / partes) * 2 * Math.PI - Math.PI / 2;
    const a1 = ((i + 1) / partes) * 2 * Math.PI - Math.PI / 2;
    const grande = a1 - a0 > Math.PI ? 1 : 0;
    return `M ${cx} ${cy} L ${cx + r * Math.cos(a0)} ${cy + r * Math.sin(a0)} A ${r} ${r} 0 ${grande} 1 ${cx + r * Math.cos(a1)} ${cy + r * Math.sin(a1)} Z`;
  };

  const torta = (
    cx: number,
    num: number,
    den: number,
    clase: string,
    desde: number,
  ) => (
    <g key={cx}>
      <Trazo paso={desde}>
        <text x={cx} y={cy - r - 26} className={`pz-rotulo-comp ${clase}-texto`}>
          {num}/{den}
        </text>
      </Trazo>
      {Array.from({ length: den }, (_, i) => (
        <Trazo key={i} paso={desde + i + 1}>
          <path d={porcion(cx, i, den)} className={i < num ? clase : "pz-porcion"} />
        </Trazo>
      ))}
    </g>
  );

  const izq = ANCHO / 2 - 118;
  const der = ANCHO / 2 + 118;

  return (
    <>
      {torta(izq, e.numerador, e.denominador, "pz-porcion-a", 0)}
      {torta(der, b.numerador, b.denominador, "pz-porcion-b", e.denominador + 1)}
    </>
  );
}

function VistaFraccion({ e }: { e: import("./escenas").Fraccion }) {
  if (e.comparar) return <VistaComparacion e={e} />;

  // Cuántos enteros hacen falta. Una fracción impropia como 5/3 son DOS
  // pasteles: uno entero y dos tercios del otro. Dibujar uno solo es imposible
  // —no caben cinco tercios en un pastel de tres— y era lo que hacía que el
  // tablero quedara vacío cuando el niño pedía justo el caso donde más ayuda.
  const enteros = Math.max(1, Math.ceil(e.numerador / e.denominador));

  /** ¿La porción `i` del entero `n` está pintada? Se llenan en orden. */
  const llena = (n: number, i: number) => n * e.denominador + i < e.numerador;

  const rotulo = (
    <Trazo paso={0}>
      <text x={ANCHO / 2} y={40} className="pz-rotulo">
        {e.numerador}/{e.denominador}
        {enteros > 1 && e.numerador % e.denominador === 0 && ` = ${e.numerador / e.denominador}`}
      </text>
    </Trazo>
  );

  if (e.forma === "torta") {
    // Los pasteles se achican para que entren todos, con su hueco entre uno y otro.
    const r = Math.min(78, (ANCHO - 40) / (enteros * 2.3));
    const separacion = r * 2.3;
    const x0 = (ANCHO - separacion * (enteros - 1)) / 2;
    const cy = 165;

    const porcion = (cx: number, i: number) => {
      const a0 = (i / e.denominador) * 2 * Math.PI - Math.PI / 2;
      const a1 = ((i + 1) / e.denominador) * 2 * Math.PI - Math.PI / 2;
      const grande = a1 - a0 > Math.PI ? 1 : 0;
      return `M ${cx} ${cy} L ${cx + r * Math.cos(a0)} ${cy + r * Math.sin(a0)} A ${r} ${r} 0 ${grande} 1 ${cx + r * Math.cos(a1)} ${cy + r * Math.sin(a1)} Z`;
    };

    return (
      <>
        {rotulo}
        {Array.from({ length: enteros }, (_, n) =>
          Array.from({ length: e.denominador }, (_, i) => (
            <Trazo key={`${n}-${i}`} paso={n * e.denominador + i + 1}>
              <path
                d={porcion(x0 + n * separacion, i)}
                className={llena(n, i) ? "pz-porcion-llena" : "pz-porcion"}
              />
            </Trazo>
          )),
        )}
      </>
    );
  }

  // Barra: los enteros van uno debajo del otro, como renglones.
  const ancho = ANCHO - 80;
  const alto = Math.min(74, (ALTO - 120) / enteros - 10);
  const x0 = 40;
  const paso = ancho / e.denominador;

  return (
    <>
      {rotulo}
      {Array.from({ length: enteros }, (_, n) =>
        Array.from({ length: e.denominador }, (_, i) => (
          <Trazo key={`${n}-${i}`} paso={n * e.denominador + i + 1}>
            <rect
              x={x0 + i * paso}
              y={70 + n * (alto + 10)}
              width={paso}
              height={alto}
              className={llena(n, i) ? "pz-porcion-llena" : "pz-porcion"}
            />
          </Trazo>
        )),
      )}
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
      return e.cantidades?.length
        ? `${e.cantidades.join(" más ")} ${e.nombre ?? "cosas"}`
        : `${e.grupos} grupos de ${e.porGrupo}`;
    case "recta":
      return `recta numérica del ${e.desde} al ${e.hasta}`;
    case "fraccion":
      return `${e.numerador} de ${e.denominador}`;
    case "texto":
      return e.contenido;
    case "lista":
      return e.palabras.join(", ");
  }
}
