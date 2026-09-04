/**
 * Bloquea /tools/* .
 *
 * Cloudflare Pages publica todo el repositorio, asi que los scripts internos
 * (el generador, la guia de configuracion, el script de la hoja) quedarian a
 * la vista de cualquiera. No son secretos, pero le dan a un atacante el mapa
 * de como esta hecho el sitio.
 *
 * El archivo _redirects no sirve aqui: solo aplica a rutas que NO existen como
 * archivo. Una Function si intercepta la ruta antes de servir el archivo.
 */
export async function onRequest() {
  return new Response("Not found", {
    status: 404,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
