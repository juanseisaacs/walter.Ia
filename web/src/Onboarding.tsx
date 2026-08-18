/**
 * La entrevista con el papá, que es cómo nace un niño en el sistema.
 *
 * NO ES UN FORMULARIO, y es a propósito. Un papá contesta con matices —"le
 * cuesta concentrarse cuando se frustra", "le encantan los dinosaurios pero se
 * aburre con las sumas"— que ninguna lista desplegable captura, y esos matices
 * son lo que el tutor usa desde la primera sesión. Un formulario devuelve
 * campos; una conversación devuelve un niño.
 *
 * El backend lleva el hilo: acá solo se muestra lo que pregunta y se manda lo
 * que el papá responde.
 */

import { useEffect, useRef, useState } from "react";

import { api } from "./api";

type Estado = "abriendo" | "conversando" | "enviando" | "listo" | "error";

interface Dicho {
  quien: "tutor" | "papa";
  texto: string;
}

export default function Onboarding({ alTerminar }: { alTerminar: (ninoId: string) => void }) {
  const [estado, setEstado] = useState<Estado>("abriendo");
  const [dichos, setDichos] = useState<Dicho[]>([]);
  const [borrador, setBorrador] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cierre, setCierre] = useState<{ nombre: string; ninoId: string } | null>(null);

  const idRef = useRef<string | null>(null);
  const finalRef = useRef<HTMLDivElement>(null);
  const campoRef = useRef<HTMLTextAreaElement>(null);

  // Arranca una sola vez. El guard sobrevive al doble montaje de StrictMode,
  // que si no abriría dos entrevistas y descartaría la primera.
  useEffect(() => {
    if (idRef.current) return;
    idRef.current = "pendiente";

    void api
      .iniciarOnboarding()
      .then((r) => {
        idRef.current = r.onboarding_id;
        setDichos([{ quien: "tutor", texto: r.pregunta }]);
        setEstado("conversando");
      })
      .catch((e) => {
        idRef.current = null;
        setError(e?.message ?? "No pude empezar la conversación.");
        setEstado("error");
      });
  }, []);

  useEffect(() => {
    // `block: "nearest"` y no `"end"`: si algún día el contenedor vuelve a
    // quedar sin alto, esto no arrastra la conversación fuera de la pantalla.
    finalRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    if (estado === "conversando") campoRef.current?.focus();
  }, [dichos, estado]);

  const responder = async () => {
    const texto = borrador.trim();
    if (!texto || !idRef.current || estado !== "conversando") return;

    setDichos((d) => [...d, { quien: "papa", texto }]);
    setBorrador("");
    setEstado("enviando");

    try {
      const r = await api.responderOnboarding(idRef.current, texto);
      console.info("[onboarding] respuesta:", r);

      if (r.listo && r.nino_id) {
        if (r.mensaje) setDichos((d) => [...d, { quien: "tutor", texto: r.mensaje! }]);
        setCierre({ nombre: r.nombre ?? "tu hijo", ninoId: r.nino_id });
        setEstado("listo");
        return;
      }

      setDichos((d) => [...d, { quien: "tutor", texto: r.pregunta ?? "…" }]);
      setEstado("conversando");
    } catch (e: any) {
      console.error("[onboarding] falló el turno:", e);
      setError(e?.message ?? "Se cortó la conversación.");
      setEstado("error");
    }
  };

  if (estado === "abriendo") {
    return (
      <main className="pantalla">
        <div className="centro">
          <p className="tenue">Un segundito...</p>
        </div>
      </main>
    );
  }

  if (estado === "error") {
    return (
      <main className="pantalla">
        <div className="centro">
          <p className="error">{error}</p>
          <button className="boton" onClick={() => window.location.reload()}>
            Volver a intentar
          </button>
        </div>
      </main>
    );
  }

  // El enlace se muestra en pantalla y no solo se manda por correo: el papá
  // acaba de dedicarle cinco minutos a esto y tiene que poder seguir ahora.
  if (estado === "listo" && cierre) {
    const enlace = `${window.location.origin}/?nino=${cierre.ninoId}`;
    return (
      <main className="pantalla">
        <div className="centro">
          <h1 className="titulo">Listo</h1>
          <p className="tenue">
            Ya podemos empezar con {cierre.nombre}. Este es su enlace — guárdalo:
          </p>
          <p className="enlace-nino">{enlace}</p>
          <button className="boton" onClick={() => alTerminar(cierre.ninoId)}>
            Empezar ahora
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="pantalla pantalla-charla">
      <div className="charla">
        {dichos.map((d, i) => (
          <p key={i} className={d.quien === "tutor" ? "dice-tutor" : "dice-nino"}>
            {d.texto}
          </p>
        ))}
        {estado === "enviando" && <p className="tenue">Pensando...</p>}
        <div ref={finalRef} />
      </div>

      <div className="responder">
        <textarea
          ref={campoRef}
          className="campo"
          rows={2}
          value={borrador}
          placeholder="Escribe tu respuesta"
          disabled={estado !== "conversando"}
          onChange={(e) => setBorrador(e.target.value)}
          onKeyDown={(e) => {
            // Enter envía; Shift+Enter hace párrafo. Es lo que un papá espera
            // de un chat, y esto es una conversación, no un formulario.
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void responder();
            }
          }}
        />
        <button
          className="boton boton-chico"
          disabled={estado !== "conversando" || !borrador.trim()}
          onClick={() => void responder()}
        >
          Enviar
        </button>
      </div>
    </main>
  );
}
