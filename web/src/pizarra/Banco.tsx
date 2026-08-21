/**
 * Banco de pruebas de la pizarra. Se abre en /pizarra.
 *
 * NO se conecta con nada: sin voz, sin backend, sin Gemini, sin base de datos.
 * Son botones y datos de mentira. La pantalla del tutor no importa este archivo,
 * así que romper algo acá es imposible que se note allá.
 *
 * Existe para poder mirar el tablero y opinar ANTES de decidir si entra.
 *
 * El layout imita cómo se vería de verdad: el tutor a la izquierda, el tablero
 * a la derecha, compartiendo pantalla. En pantalla angosta el tablero pasa
 * abajo, que es lo que corresponde en un celular.
 */

import { useState } from "react";

import Cara from "../Cara";
import "./Banco.css";
import HojaDelNino from "./HojaDelNino";
import Pizarra from "./Pizarra";
import Escritura from "./Escritura";
import type { Cuadro } from "./escenas";
import { CARACTERES_CONOCIDOS } from "./trazos";

/** Cada botón es un momento real de una sesión, no una demo de features. */
const MOMENTOS: { rotulo: string; dice: string; cuadro: Cuadro }[] = [
  {
    rotulo: "Suma con llevada",
    dice: "Mira: seis más ocho son catorce. Escribo el cuatro y me llevo una.",
    cuadro: {
      escena: { tipo: "operacion", a: 56, b: 38, op: "+", llevada: 1 },
      anotaciones: [{ ancla: "unidades", gesto: "circulo" }],
    },
  },
  {
    rotulo: "La cuenta resuelta",
    dice: "Y ahí está: noventa y cuatro.",
    cuadro: {
      escena: { tipo: "operacion", a: 56, b: 38, op: "+", llevada: 1, resultado: 94 },
      anotaciones: [{ ancla: "resultado", gesto: "circulo", tono: "exito" }],
    },
  },
  {
    rotulo: "Se equivocó",
    dice: "Mmm, ese no es. Fíjate otra vez en las decenas.",
    cuadro: {
      escena: { tipo: "operacion", a: 56, b: 38, op: "+", resultado: 84 },
      anotaciones: [
        { ancla: "resultado", gesto: "tachado", tono: "alerta" },
        { ancla: "decenas", gesto: "flecha" },
      ],
    },
  },
  {
    rotulo: "Grupos iguales",
    dice: "Tengo cinco cajas y en cada una hay cuatro lápices.",
    cuadro: { escena: { tipo: "grupos", grupos: 5, porGrupo: 4, nombre: "cajas" } },
  },
  {
    rotulo: "Recta numérica",
    dice: "Estamos en el siete y damos un salto de cinco. ¿Dónde caemos?",
    cuadro: { escena: { tipo: "recta", desde: 0, hasta: 20, marca: 7, saltaA: 12 } },
  },
  {
    rotulo: "Fracción en barra",
    dice: "De las cuatro partes, pintamos tres.",
    cuadro: { escena: { tipo: "fraccion", numerador: 3, denominador: 4 } },
  },
  {
    rotulo: "Fracción en torta",
    dice: "La mitad de la pizza.",
    cuadro: { escena: { tipo: "fraccion", numerador: 1, denominador: 2, forma: "torta" } },
  },
  {
    rotulo: "✍️ La letra ñ",
    dice: "Mira cómo se escribe la eñe. Fíjate por dónde empieza el lápiz.",
    cuadro: { escena: { tipo: "texto", contenido: "ñ", pie: "la eñe" } },
  },
  {
    rotulo: "✍️ Una palabra",
    dice: "Léela conmigo, despacio.",
    cuadro: { escena: { tipo: "texto", contenido: "casa" } },
  },
  {
    rotulo: "✍️ Un número",
    dice: "Así se escribe el ocho: sin levantar el lápiz.",
    cuadro: { escena: { tipo: "texto", contenido: "8" } },
  },
];

export default function Banco() {
  const [i, setI] = useState(0);
  const [dibujando, setDibujando] = useState(false);
  const [abecedario, setAbecedario] = useState(false);
  const [hablando, setHablando] = useState(true);
  const [ultimoDibujo, setUltimoDibujo] = useState<string | null>(null);

  const momento = MOMENTOS[i];

  return (
    <div className="banco">
      <header className="banco-cabecera">
        <h1>Pizarra — banco de pruebas</h1>
        <p>
          Pantalla suelta. No toca la voz, ni el backend, ni la base. Apretá los botones y mirá
          cómo queda.
        </p>
      </header>

      <div className="banco-botones">
        {MOMENTOS.map((m, n) => (
          <button
            key={m.rotulo}
            className={`banco-boton ${n === i && !dibujando ? "banco-boton-activo" : ""}`}
            onClick={() => {
              setDibujando(false);
              setI(n);
            }}
          >
            {m.rotulo}
          </button>
        ))}
        <button
          className={`banco-boton ${dibujando ? "banco-boton-activo" : ""}`}
          onClick={() => {
            setAbecedario(false);
            setDibujando(true);
          }}
        >
          ✏️ Que dibuje el niño
        </button>
        <button
          className={`banco-boton ${abecedario ? "banco-boton-activo" : ""}`}
          onClick={() => {
            setDibujando(false);
            setAbecedario(true);
          }}
        >
          🔤 Ver todos los trazos
        </button>
      </div>

      {/* Así se vería de verdad: el tutor y el tablero compartiendo pantalla. */}
      {!abecedario && (
      <div className="banco-escena">
        <aside className="banco-tutor">
          {/* La cara de verdad, la misma que ve el niño. El botón la pone a
              hablar para poder mirarla sin abrir una sesión. */}
          <Cara hablando={hablando} />
          <button className="banco-boton" onClick={() => setHablando((h) => !h)}>
            {hablando ? "⏸ Que se calle" : "▶ Que hable"}
          </button>
          <p className="banco-dice">{dibujando ? "Dibújame la letra ñ." : momento.dice}</p>
          <p className="banco-nota">
            Acá va el tutor de voz, tal como está hoy. La pizarra vive al lado y no lo interrumpe.
          </p>
        </aside>

        <main className="banco-tablero">
          {dibujando ? (
            <HojaDelNino
              consigna="Dibújame la letra ñ"
              alCancelar={() => setDibujando(false)}
              alEnviar={(png) => {
                setUltimoDibujo(png);
                setDibujando(false);
              }}
            />
          ) : (
            <Pizarra cuadro={momento.cuadro} />
          )}
        </main>
      </div>
      )}

      {abecedario && (
        <section className="banco-abecedario">
          <h2>Todos los trazos, escribiéndose</h2>
          <p>
            Cada uno se dibuja como lo trazaría una mano. Decime cuáles quedaron
            feos y los corrijo — son datos en <code>trazos.ts</code>, una línea
            por carácter.
          </p>
          <div className="banco-grilla">
            {CARACTERES_CONOCIDOS.map((c) => (
              <figure key={c} className="banco-glifo">
                <Escritura texto={c} />
                <figcaption>{c}</figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      {ultimoDibujo && (
        <section className="banco-enviado">
          <h2>Lo que le llegaría al tutor</h2>
          <p>
            Es un JPEG, el mismo formato y el mismo camino que la foto de la cámara — que es
            lo único verificado con imágenes reales. Acá solo se muestra; no se manda a ningún lado.
          </p>
          <img src={`data:image/jpeg;base64,${ultimoDibujo}`} alt="lo que dibujó el niño" />
        </section>
      )}
    </div>
  );
}
