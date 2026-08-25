import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./estilos/tokens.css";
import Banco from "./pizarra/Banco";
import SinTumbarLaSesion from "./pizarra/SinTumbarLaSesion";

// La pizarra se prueba en /pizarra, aislada de todo. Es un `if`, no un router:
// una dependencia nueva para una pantalla de pruebas no se justifica, y así
// `App` no importa una sola línea de la pizarra hasta que decidamos integrarla.
const enPruebasDePizarra = window.location.pathname.replace(/\/$/, "") === "/pizarra";

/* LA RED DE AFUERA DE TODO.
   Existía solo alrededor del tablero, porque ahí fue donde aprendimos que un
   error de render blanquea la pantalla entera. Pero el personaje, el visor de
   la cámara y el propio `App` seguían sin red: cualquier excepción al dibujar
   y el niño se queda mirando blanco, sin tutor y sin saber qué pasó.

   Es la mitad visible de «al final desapareció». La otra mitad —que el backend
   ni se entere— la resuelve el reaper.

   El respaldo no es una pantalla de error de programador: es una frase que un
   niño de siete años puede leer, y un botón que hace lo único que sirve. */
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SinTumbarLaSesion
      donde="app"
      respaldo={
        <div className="pantalla">
          <p>Se me trabó la pantalla. Toca aquí y volvemos a empezar.</p>
          <button className="boton" onClick={() => window.location.reload()}>
            Volver a empezar
          </button>
        </div>
      }
    >
      {enPruebasDePizarra ? <Banco /> : <App />}
    </SinTumbarLaSesion>
  </StrictMode>,
);
