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
 * Y envuelve TAMBIÉN la app entera, con `respaldo`. Esta red existía solo
 * alrededor del tablero —la lección se aprendió ahí y se aplicó solo ahí—, así
 * que un error en el personaje, en el visor de la cámara o en el propio `App`
 * seguía blanqueando la pantalla. Es la mitad técnica de «al final
 * desapareció»: donde no hay límite de error, React desmonta todo y el niño se
 * queda mirando blanco sin saber qué pasó.
 *
 * Va como clase porque los límites de error en React todavía no existen como
 * hook. Es la única clase del proyecto y es por eso.
 */

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Qué mostrar en vez de nada. Para el tablero va `null` —se apaga y ya—,
      pero cuando esto envuelve la app entera, `null` ES la pantalla en blanco
      que hay que evitar. Ver el comentario de arriba. */
  respaldo?: ReactNode;
  /** De dónde salió el error, para el log. */
  donde?: string;
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
    console.error(`[${this.props.donde ?? "pizarra"}] reventó al dibujarse:`, error);
  }

  componentDidUpdate(anteriores: Props) {
    // La escena siguiente merece su oportunidad: si la que rompió ya no está,
    // el tablero vuelve. Sin esto, un solo fallo lo apagaba por toda la sesión.
    if (this.state.rompio && anteriores.children !== this.props.children) {
      this.setState({ rompio: false });
    }
  }

  render() {
    if (!this.state.rompio) return this.props.children;
    return this.props.respaldo ?? null;
  }
}
