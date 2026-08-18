/**
 * Pantalla del niño.
 *
 * MINIMALISTA A PROPÓSITO: un botón grande y lo que se está diciendo. Sin
 * personaje, sin ilustración, sin animaciones. Primero saber cómo se usa de
 * verdad; el diseño viene después.
 *
 * Ningún color ni tamaño está escrito acá: todo sale de estilos/tokens.css.
 */

import "./App.css";
import { ninoActual } from "./nino";
import { useTutor } from "./voz/useTutor";

const NINO_ID = ninoActual();

export default function App() {
  const { estado, error, tema, textoNino, textoTutor, nivelMic, empezar, terminar } =
    useTutor(NINO_ID ?? "");

  const enSesion = estado === "escuchando" || estado === "hablando";

  // Sin id no hay a quién enseñarle. Se dice, no se falla en silencio ni se
  // cae en un niño por defecto — que fue lo que hizo que durante semanas todo
  // el tráfico de prueba se acumulara sobre el mismo chico.
  if (!NINO_ID) {
    return (
      <main className="pantalla">
        <div className="centro">
          <h1 className="titulo">¡Hola!</h1>
          <p className="tenue">
            Pídele a tu mamá o a tu papá el enlace para entrar.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="pantalla">
      {tema && enSesion && <p className="tema">Hoy: {tema}</p>}

      <div className="centro">
        {estado === "inicio" && (
          <>
            <h1 className="titulo">¿Empezamos?</h1>
            <button className="boton" onClick={() => void empezar()}>
              Hablar con mi tutor
            </button>
          </>
        )}

        {estado === "conectando" && <p className="tenue">Un segundito...</p>}

        {enSesion && (
          <>
            <div
              className={`indicador ${estado === "hablando" ? "es-tutor" : "es-nino"}`}
              style={{ transform: `scale(${1 + (estado === "escuchando" ? nivelMic * 0.3 : 0.15)})` }}
              aria-hidden
            />
            <p className="tenue">
              {estado === "hablando" ? "Tu tutor está hablando" : "Te escucho"}
            </p>
          </>
        )}

        {estado === "error" && (
          <>
            <p className="error">{error}</p>
            <button className="boton" onClick={() => void empezar()}>
              Probar de nuevo
            </button>
          </>
        )}
      </div>

      {enSesion && (
        <div className="dialogo">
          {textoTutor && <p className="dice-tutor">{textoTutor}</p>}
          {textoNino && <p className="dice-nino">{textoNino}</p>}
        </div>
      )}

      {enSesion && (
        <button className="salir" onClick={() => void terminar()}>
          Terminar
        </button>
      )}
    </main>
  );
}
