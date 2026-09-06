/**
 * Bloquea /catalog.json  (archivo de build, no para el publico).
 * _redirects no sirve para rutas que SI existen como archivo; una Function si.
 * El frontend solo usa /productos.json y /search.json.
 */
export async function onRequest() {
  return new Response("Not found", {
    status: 404,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
