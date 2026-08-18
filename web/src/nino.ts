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
 * No es autenticación y no pretende serlo. Es identidad, que es lo que falta
 * para que dos niños puedan usar el producto. La sesión del papá SÍ está
 * autenticada, con enlace mágico y vencimiento — ahí es donde viven los datos
 * que hay que proteger.
 */

const CLAVE = "rbh.nino";

export function ninoActual(): string | null {
  const deLaUrl = new URLSearchParams(window.location.search).get("nino");
  if (deLaUrl) {
    localStorage.setItem(CLAVE, deLaUrl);
    // Se limpia de la barra: un enlace con el id a la vista se comparte por
    // accidente, y quien lo abra entra como ese niño.
    window.history.replaceState({}, "", window.location.pathname);
    return deLaUrl;
  }
  return localStorage.getItem(CLAVE);
}
