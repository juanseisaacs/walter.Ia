/**
 * El tutor, dibujado. Un oso de anteojos.
 *
 * ── Por qué un oso de anteojos ──────────────────────────────────────────────
 * Es andino y colombiano de verdad, así que el niño ve un animal de su tierra
 * y no una mascota importada. Sus manchas claras alrededor de los ojos son un
 * rasgo real de la especie, y acá hacen un trabajo doble: enmarcan la mirada,
 * que es de lejos lo que más hace que un dibujo se sienta alguien.
 *
 * No es humano a propósito. Un tutor humano obliga a elegirle piel, pelo y
 * género, y cada una de esas elecciones le dice algo distinto a cada niño que
 * abre la app. Un oso no le dice nada a nadie, y se deja querer por todos.
 *
 * ── Qué puede y qué NO puede hacer ──────────────────────────────────────────
 * La Constitución (§8.4) dice que el tutor «nunca finge cuerpo, familia,
 * infancia, ni vida fuera de la app». Un dibujo no viola eso —un dibujo es un
 * dibujo— pero el repertorio sí podría empujar al tutor a mentir. Por eso el
 * oso solo hace cosas que la app hace de verdad: escuchar, hablar, mirar una
 * foto, esperar. **No come, no duerme, no se cansa, no se va.** Si alguna vez
 * se le agrega un gesto, esa es la vara.
 *
 * Y no celebra a lo grande. Un personaje que salta y tira confeti cada vez que
 * el niño acierta es elogio inflado dibujado, que está prohibido por las
 * mismas razones que el hablado: le enseña al niño que su valor depende de
 * rendir.
 *
 * ── Cómo está hecho, y por qué así ──────────────────────────────────────────
 * SVG por capas, animado con CSS. Nada de JS por frame.
 *
 * Esto NO es una preferencia estética: este navegador está procesando audio
 * PCM en tiempo real en el mismo hilo. Un runtime de animación (Rive, Lottie)
 * hace un tick por frame ahí adentro, y sería el primer sospechoso la próxima
 * vez que la sesión se sienta lenta. `transform` y `opacity` los resuelve el
 * compositor, fuera del hilo principal: el personaje cuesta cero.
 *
 * Es el mismo truco que ya usa `pizarra/trazos.ts` para escribir las letras.
 *
 * Cada `<g>` es una articulación, con su `transform-origin` en el pivote. Lo
 * que da vida no es mover el dibujo: es mover las articulaciones.
 *
 * No sabe NADA de la voz ni de la red. Recibe un ánimo y un número. Se puede
 * mirar entero en `/pizarra` sin abrir una sesión ni gastar cuota, y si se
 * rompe no arrastra a nadie.
 *
 * La boca NO va sincronizada con el audio real. Se pensó medir el volumen de
 * salida, y se descartó: habría que meter un analizador justo en el camino
 * donde no se regala nada. Tres formas alternándose se leen como habla
 * articulada, y nadie mira una boca buscando fonemas.
 */

import { type Animo, comoSeLee, respiro } from "./animo";
import "./Personaje.css";

export default function Personaje({
  animo,
  /** 0 a 1. El personaje respira con la voz del niño mientras lo escucha. */
  nivelMic = 0,
}: {
  animo: Animo;
  nivelMic?: number;
}) {
  return (
    <svg
      viewBox="0 0 100 118"
      className={`pj pj-${animo}`}
      style={{ transform: `scale(${respiro(animo, nivelMic)})` }}
      role="img"
      aria-label={comoSeLee(animo)}
    >
      {/* El aura dice de quién es el turno sin que nadie tenga que leerlo:
          verde cuando habla el tutor, azul cuando habla el niño. Va detrás y
          no encima porque el oso tiene que quedar oscuro sobre claro. */}
      <circle className="pj-aura" cx="50" cy="46" r="42" />

      {/* Los brazos van DETRÁS del torso: asoman a los lados. Así el saludo se
          ve sin tener que dibujar manos, hombros ni codos. */}
      <g className="pj-brazo pj-brazo-izq">
        <ellipse cx="24" cy="93" rx="9" ry="15" />
      </g>
      <g className="pj-brazo pj-brazo-der">
        <ellipse cx="76" cy="93" rx="9" ry="15" />
      </g>

      {/* El torso respira SIEMPRE, en todos los ánimos. Un personaje
          perfectamente quieto se lee como una imagen pegada; el respiro es lo
          que lo vuelve alguien que está ahí. */}
      <g className="pj-torso">
        <ellipse className="pj-pelaje" cx="50" cy="96" rx="27" ry="21" />
        <ellipse className="pj-claro" cx="50" cy="101" rx="16" ry="14" />
      </g>

      {/* La cabeza pivota en el cuello (50, 66), no en su centro. Ladearla
          desde el centro se ve como un dibujo que gira; desde el cuello se ve
          como alguien que presta atención. */}
      <g className="pj-cabeza">
        <g className="pj-oreja">
          <circle className="pj-pelaje" cx="21" cy="25" r="11" />
          <circle className="pj-claro" cx="21" cy="25" r="5.5" />
        </g>
        <g className="pj-oreja">
          <circle className="pj-pelaje" cx="79" cy="25" r="11" />
          <circle className="pj-claro" cx="79" cy="25" r="5.5" />
        </g>

        <circle className="pj-pelaje" cx="50" cy="44" r="32" />

        {/* Los anteojos: la mancha real de la especie. Inclinadas hacia
            adentro, que es lo que le da la expresión amable de base. */}
        <ellipse className="pj-claro" cx="37" cy="38" rx="12.5" ry="14" transform="rotate(-12 37 38)" />
        <ellipse className="pj-claro" cx="63" cy="38" rx="12.5" ry="14" transform="rotate(12 63 38)" />

        {/* Las cejas hacen casi toda la expresión y cuestan dos paths. */}
        <g className="pj-cejas">
          <path className="pj-ceja" d="M28 23 Q37 19 45 23" />
          <path className="pj-ceja" d="M55 23 Q63 19 72 23" />
        </g>

        {/* El parpadeo achata el grupo entero un instante. Dos líneas de CSS,
            y es lo que más se nota si falta. */}
        <g className="pj-ojos">
          <circle className="pj-ojo" cx="37" cy="40" r="7" />
          <circle className="pj-ojo" cx="63" cy="40" r="7" />

          {/* Las pupilas se TRASLADAN: eso es la mirada. Mira al niño mientras
              lo escucha y baja al papel cuando le llega una foto. */}
          <g className="pj-pupilas">
            <circle className="pj-pupila" cx="37" cy="40" r="3.8" />
            <circle className="pj-pupila" cx="63" cy="40" r="3.8" />
            <circle className="pj-brillo" cx="38.6" cy="38.3" r="1.3" />
            <circle className="pj-brillo" cx="64.6" cy="38.3" r="1.3" />
          </g>
        </g>

        {/* El hocico baja un pelo con cada sílaba. Es lo que convierte "una
            boca que cambia de forma" en "alguien que está hablando". */}
        <g className="pj-hocico">
          <ellipse className="pj-claro" cx="50" cy="60" rx="16" ry="12" />
          <ellipse className="pj-nariz" cx="50" cy="54" rx="5.5" ry="4" />

          {/* Cuatro bocas superpuestas, que se turnan con opacidad. Una sola
              boca estirándose se ve masticando; formas distintas se leen como
              sílabas. Y cambiar el `d` de un path por keyframes no lo anima el
              compositor — la opacidad sí. */}
          <path className="pj-boca pj-boca-quieta" d="M42 63 Q50 70 58 63" />
          <path className="pj-boca pj-boca-ancha" d="M39 62 Q50 73 61 62" />
          <ellipse className="pj-boca-llena pj-boca-a" cx="50" cy="66" rx="7.5" ry="6" />
          <ellipse className="pj-boca-llena pj-boca-o" cx="50" cy="66" rx="4.5" ry="5.5" />
        </g>
      </g>
    </svg>
  );
}
