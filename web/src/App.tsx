/**
 * Pantalla del niño.
 *
 * MINIMALISTA A PROPÓSITO: un botón grande, el tutor y lo que se está
 * diciendo. Nada más en pantalla compite con eso.
 *
 * Ningún color ni tamaño está escrito acá: todo sale de estilos/tokens.css.
 */

import { useState } from "react";

import "./App.css";
import Onboarding from "./Onboarding";
import Personaje from "./personaje/Personaje";
import { animoDesde } from "./personaje/animo";
import VisorCamara from "./VisorCamara";
import HojaDelNino from "./pizarra/HojaDelNino";
import Pizarra from "./pizarra/Pizarra";
import SinTumbarLaSesion from "./pizarra/SinTumbarLaSesion";
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
  const {
    estado,
    error,
    tema,
    textoNino,
    textoTutor,
    nivelMic,
    modo,
    camara,
    fallaCamara,
    avisoVisor,
    fotoEnviada,
    mirandoFoto,
    abrirCamaraManual,
    tomarFoto,
    cancelarFoto,
    cuadro,
    hoja,
    dibujoEnviado,
    enviarDibujo,
    cancelarDibujo,
    empezar,
    terminar,
  } = useTutor(ninoId);

  const enSesion = estado === "escuchando" || estado === "hablando";
  // El tablero COMPARTE pantalla: no tapa al tutor, se pone al lado. Y sale
  // solo cuando hay algo que mostrar — vacío le competiría la atención al niño.
  const hayTablero = enSesion && (cuadro !== null || hoja !== null);

  return (
    <main className={`pantalla ${hayTablero ? "con-tablero" : ""}`}>
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
            <Personaje animo={animoDesde({ estado, mirandoFoto })} nivelMic={nivelMic} />
            <p className="tenue">
              {mirandoFoto
                ? "Está mirando tu foto..."
                : estado === "hablando"
                  ? "Tu tutor está hablando"
                  : "Te escucho"}
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

      {hayTablero && (
        <section className="tablero">
          {/* Si dibujar revienta, se apaga el tablero y NADA MÁS. La voz es el
              producto; la pizarra es ayuda. Un glifo roto no puede dejar al
              niño con la pantalla en blanco y sin tutor. */}
          <SinTumbarLaSesion>
            {hoja !== null ? (
              <HojaDelNino
                consigna={hoja}
                referencia={cuadro}
                alEnviar={enviarDibujo}
                alCancelar={cancelarDibujo}
                enviado={dibujoEnviado}
              />
            ) : (
              <Pizarra cuadro={cuadro} />
            )}
          </SinTumbarLaSesion>
        </section>
      )}

      {enSesion && (
        <div className="dialogo">
          {textoTutor && <p className="dice-tutor">{textoTutor}</p>}
          {textoNino && <p className="dice-nino">{textoNino}</p>}
        </div>
      )}

      {enSesion && !camara && !fallaCamara && (
        <button
          className="camara-boton"
          onClick={abrirCamaraManual}
          aria-label="Mostrarle algo con la cámara"
          title="Mostrarle algo"
        >
          📷
        </button>
      )}

      {enSesion && (
        <button className="salir" onClick={() => void terminar()}>
          Terminar
        </button>
      )}

      {/* Flota encima de la sesión: el tutor le sigue hablando mientras
          acomoda el cuaderno. */}
      {(camara || fallaCamara) && (
        <VisorCamara
          stream={camara}
          falla={fallaCamara}
          aviso={avisoVisor}
          enviada={fotoEnviada}
          alTomar={tomarFoto}
          alCancelar={cancelarFoto}
        />
      )}
    </main>
  );
}
