/**
 * De quién es esta sesión.
 *
 * Hasta el 18/08 esto era `const NINO_ID = "n1"` en App.tsx: la aplicación
 * servía exactamente a un niño, el que se había creado a mano en la base.
 *
 * El id llega por la URL (`?nino=n_abc123`), que es el enlace que el papá
 * recibe al terminar el onboarding, y queda guardado para que el niño no
 * dependa de tenerlo a mano cada vez. Un enlace nuevo pisa al anterior: así el
 * segundo hijo se registra desde el mismo navegador sin borrar nada.
 *
 * El id es IDENTIDAD, no autenticación: viaja en la URL y se comparte por
 * accidente. La credencial es el `t` que va en el mismo enlace, y desde el
 * 22/08 el backend la exige para abrir sesión — antes bastaba con conocer un
 * `nino_id` para quemarle la cuota a un niño ajeno y llevarse un token de voz.
 *
 * No vence: es cómo entra cada día, no una sesión. La del papá sí caduca a las
 * 24 horas, porque ahí es donde viven los datos que hay que proteger.
 */

const CLAVE = "rbh.nino";
const CLAVE_TOKEN = "rbh.token";

export function ninoActual(): string | null {
  const params = new URLSearchParams(window.location.search);
  const deLaUrl = params.get("nino");
  if (deLaUrl) {
    localStorage.setItem(CLAVE, deLaUrl);
    // La credencial viene en el mismo enlace. Desde el 22/08 el backend la
    // exige para abrir sesión: sin ella, `nino_id` daba acceso a cualquiera
    // que lo conociera.
    const token = params.get("t");
    if (token) localStorage.setItem(CLAVE_TOKEN, token);
    // Se limpia de la barra: un enlace a la vista se comparte por accidente,
    // y ahora lleva la credencial además del id.
    window.history.replaceState({}, "", window.location.pathname);
    return deLaUrl;
  }
  return localStorage.getItem(CLAVE);
}

/** La credencial del niño. Sin ella el backend no abre sesión. */
export function tokenActual(): string | null {
  return localStorage.getItem(CLAVE_TOKEN);
}
