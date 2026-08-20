import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./estilos/tokens.css";
import Banco from "./pizarra/Banco";

// La pizarra se prueba en /pizarra, aislada de todo. Es un `if`, no un router:
// una dependencia nueva para una pantalla de pruebas no se justifica, y así
// `App` no importa una sola línea de la pizarra hasta que decidamos integrarla.
const enPruebasDePizarra = window.location.pathname.replace(/\/$/, "") === "/pizarra";

createRoot(document.getElementById("root")!).render(
  <StrictMode>{enPruebasDePizarra ? <Banco /> : <App />}</StrictMode>,
);
