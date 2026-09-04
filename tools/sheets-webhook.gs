/**
 * SAUCE STORE — registro de pedidos en Google Sheets
 * ==================================================
 * Esto NO va en la pagina web. Se pega en Google Apps Script.
 *
 * PASOS:
 *  1. Ve a https://sheets.new y nombra la hoja "Pedidos Sauce Store".
 *  2. Menu  Extensiones > Apps Script.
 *  3. Borra lo que haya y pega TODO este archivo.
 *  4. Cambia SECRETO por una palabra tuya (la misma que pondras en Cloudflare).
 *  5. Boton "Implementar" > "Nueva implementacion".
 *       - Tipo: Aplicacion web
 *       - Ejecutar como: Yo
 *       - Quien tiene acceso: Cualquier persona
 *  6. Copia la URL que te da (termina en /exec) -> esa es SHEETS_WEBHOOK_URL.
 *
 * Para bajarla como Excel: Archivo > Descargar > Microsoft Excel (.xlsx)
 */

const SECRETO = "cambia-esta-palabra";

const COLUMNAS = [
  "Fecha", "Folio", "Nombre", "WhatsApp", "Modalidad", "Entrega", "Pago",
  "Productos", "Subtotal", "Reenvio", "Comision", "Total", "Cobrar ahora",
  "Resta", "Estado", "Ciudad", "Calle", "Colonia", "Numero", "Entre calles",
  "CP", "Referencias",
];

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);

    // Solo acepta peticiones que traigan la palabra secreta
    if (d.secret !== SECRETO) {
      return salida({ error: "no autorizado" });
    }

    const hoja = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];

    // Encabezados la primera vez
    if (hoja.getLastRow() === 0) {
      hoja.appendRow(COLUMNAS);
      hoja.getRange(1, 1, 1, COLUMNAS.length)
        .setFontWeight("bold")
        .setBackground("#0E0E0E")
        .setFontColor("#F4F1EA");
      hoja.setFrozenRows(1);
    }

    hoja.appendRow([
      new Date(d.fecha || Date.now()),
      d.folio || "", d.nombre || "", "'" + (d.whatsapp || ""),
      d.modalidad || "", d.entrega || "", d.pago || "",
      d.productos || "",
      d.subtotal || 0, d.reenvio || 0, d.comision || 0,
      d.total || 0, d.cobrar_ahora || 0, d.resta || 0,
      d.estado || "", d.ciudad || "", d.calle || "", d.colonia || "",
      d.numero || "", d.entrecalles || "", d.cp || "", d.referencias || "",
    ]);

    return salida({ ok: true });
  } catch (err) {
    return salida({ error: String(err) });
  }
}

function salida(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
