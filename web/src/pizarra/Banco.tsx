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

import Personaje from "../personaje/Personaje";
import type { Animo } from "../personaje/animo";
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
    rotulo: "Fracción impropia (5/3)",
    dice: "Cinco tercios son más de un pastel: uno entero y dos pedazos del otro.",
    cuadro: { escena: { tipo: "fraccion", numerador: 5, denominador: 3, forma: "torta" } },
  },
  {
    rotulo: "Fracción en torta",
    dice: "La mitad de la pizza.",
    cuadro: { escena: { tipo: "fraccion", numerador: 1, denominador: 2, forma: "torta" } },
  },
  {
    rotulo: "Comparar 1/2 y 1/3",
    dice: "¿Cuál pedazo es más grande? El naranja o el azul.",
    cuadro: {
      escena: {
        tipo: "fraccion",
        numerador: 1,
        denominador: 2,
        comparar: { numerador: 1, denominador: 3 },
      },
    },
  },
  {
    rotulo: "Comparar 3/4 y 2/6",
    dice: "Dos fracciones cualquiera, del mismo tamaño para poder mirarlas.",
    cuadro: {
      escena: {
        tipo: "fraccion",
        numerador: 3,
        denominador: 4,
        comparar: { numerador: 2, denominador: 6 },
      },
    },
  },
  {
    rotulo: "Tres palabras con V",
    dice: "Vaca, vela, viento. Las tres a la vez, cada una de su color.",
    cuadro: { escena: { tipo: "lista", palabras: ["vaca", "vela", "viento"] } },
  },
  {
    rotulo: "Cuatro palabras",
    dice: "Hasta cuatro entran sin que deje de leerse de un vistazo.",
    cuadro: { escena: { tipo: "lista", palabras: ["mesa", "silla", "ventana", "puerta"] } },
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

/** El repertorio entero del personaje. Si se le agrega un ánimo y no aparece
    acá, no hay forma de mirarlo: por eso la lista va junto al banco. */
const ANIMOS: [Animo, string][] = [
  ["hablando", "🗣 Hablando"],
  ["escuchando", "👂 Escuchando"],
  ["esperando", "⏳ El niño no contesta"],
  ["mirando", "🔍 Mirando una foto"],
  ["saludando", "👋 Llegando"],
  ["reposo", "😌 En reposo"],
];

export default function Banco() {
  const [i, setI] = useState(0);
  const [dibujando, setDibujando] = useState(false);
  const [abecedario, setAbecedario] = useState(false);
  const [animo, setAnimo] = useState<Animo>("hablando");
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
          {/* El personaje de verdad, el mismo que ve el niño. Los botones
              recorren su repertorio entero sin abrir una sesión ni gastar un
              peso de cuota: es la única forma de opinar sobre un dibujo. */}
          <Personaje animo={animo} nivelMic={animo === "escuchando" ? 0.4 : 0} />
          <div className="banco-animos">
            {ANIMOS.map(([valor, rotulo]) => (
              <button
                key={valor}
                className={`banco-boton ${animo === valor ? "banco-boton-activo" : ""}`}
                onClick={() => setAnimo(valor)}
              >
                {rotulo}
              </button>
            ))}
          </div>
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
