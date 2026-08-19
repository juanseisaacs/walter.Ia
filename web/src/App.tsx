/**
 * Pantalla del niño.
 *
 * MINIMALISTA A PROPÓSITO: un botón grande y lo que se está diciendo. Sin
 * personaje, sin ilustración, sin animaciones. Primero saber cómo se usa de
 * verdad; el diseño viene después.
 *
 * Ningún color ni tamaño está escrito acá: todo sale de estilos/tokens.css.
 */

import { useState } from "react";

import "./App.css";
import Onboarding from "./Onboarding";
import { ninoActual } from "./nino";
import { useTutor } from "./voz/useTutor";

export default function App() {
  // El id puede nacer a mitad de sesión, cuando el papá termina el onboarding.
  const [ninoId, setNinoId] = useState<string | null>(ninoActual);
  const [registrando, setRegistrando] = useState(false);

  if (registrando) {
    return (
      <Onboarding
        alTerminar={(id) => {
          localStorage.setItem("rbh.nino", id);
          setNinoId(id);
          setRegistrando(false);
        }}
      />
    );
  }

  if (!ninoId) return <SinNino alRegistrar={() => setRegistrando(true)} />;
  return <Tutor ninoId={ninoId} />;
}

/** Quien llega sin enlace: puede ser el niño, o el papá que viene a registrarlo. */
function SinNino({ alRegistrar }: { alRegistrar: () => void }) {
  return (
    <main className="pantalla">
      <div className="centro">
        <h1 className="titulo">¡Hola!</h1>
        <p className="tenue">Pídele a tu mamá o a tu papá el enlace para entrar.</p>
        <button className="boton boton-chico" onClick={alRegistrar}>
          Soy el papá o la mamá
        </button>
      </div>
    </main>
  );
}

function Tutor({ ninoId }: { ninoId: string }) {
  const { estado, error, tema, textoNino, textoTutor, nivelMic, modo, empezar, terminar } =
    useTutor(ninoId);

  const enSesion = estado === "escuchando" || estado === "hablando";

  return (
    <main className="pantalla">
      {enSesion && (
        <p className="tema">{modo === "pedido" ? "Tu tarea" : tema ? `Hoy: ${tema}` : ""}</p>
      )}

      <div className="centro">
        {estado === "inicio" && (
          <>
            <h1 className="titulo">¿Empezamos?</h1>
            <button className="boton" onClick={() => void empezar("guiado")}>
              Hablar con mi tutor
            </button>
            {/* El modo Pedido existía completo en el backend y no había forma
                de llegar a él: la mitad del producto, construida y cerrada.
                Es donde vive la promesa que nos separa del "ChatGPT para la
                tarea" — y el método socrático ahí es MÁS estricto, no menos. */}
            <button className="boton boton-segundo" onClick={() => void empezar("pedido")}>
              Traigo una tarea
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
            <button className="boton" onClick={() => void empezar(modo)}>
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
