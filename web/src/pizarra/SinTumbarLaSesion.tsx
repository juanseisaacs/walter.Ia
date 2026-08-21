/**
 * Red de seguridad del tablero.
 *
 * Si algo revienta al dibujar, React desmonta el árbol entero: el niño se queda
 * con la pantalla en blanco Y sin tutor, por un error en la parte decorativa de
 * la sesión. Eso no puede pasar — la voz es el producto, la pizarra es ayuda.
 *
 * Con esto, un fallo al dibujar apaga el tablero y nada más. El tutor sigue
 * hablando y el niño ni se entera.
 *
 * Va como clase porque los límites de error en React todavía no existen como
 * hook. Es la única clase del proyecto y es por eso.
 */

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface Estado {
  rompio: boolean;
}

export default class SinTumbarLaSesion extends Component<Props, Estado> {
  state: Estado = { rompio: false };

  static getDerivedStateFromError(): Estado {
    return { rompio: true };
  }

  componentDidCatch(error: unknown) {
    // A consola sí: que no se vea en pantalla no significa que no haya que
    // arreglarlo. Sin este renglón, un glifo roto es invisible para siempre.
    console.error("[pizarra] la escena reventó al dibujarse:", error);
  }

  componentDidUpdate(anteriores: Props) {
    // La escena siguiente merece su oportunidad: si la que rompió ya no está,
    // el tablero vuelve. Sin esto, un solo fallo lo apagaba por toda la sesión.
    if (this.state.rompio && anteriores.children !== this.props.children) {
      this.setState({ rompio: false });
    }
  }

  render() {
    return this.state.rompio ? null : this.props.children;
  }
}
