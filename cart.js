/* ===================================================================
   SAUCE STORE — carrito y sistema de tickets

   El carrito SOLO guarda {id, size, qty}. Nombre, precio e imagen se
   resuelven contra productos.json, y el total definitivo lo recalcula
   el servidor: nada de lo que se guarde aqui puede alterar un precio.
   =================================================================== */
(function () {
  "use strict";

  var KEY = "sauce_cart";
  var TICKET_KEY = "sauce_ticket";
  var REENVIO_APARTADO = 200;   // $ extra si apartas y pides envio
  var COMISION_TARJETA = 0.05;  // 5% si paga con tarjeta

  /* ---------------- almacenamiento ---------------- */
  function read() {
    try {
      var v = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(v) ? v : [];
    } catch (e) { return []; }
  }
  function write(items) {
    try { localStorage.setItem(KEY, JSON.stringify(items)); } catch (e) {}
    paintCount();
  }
  function count() {
    return read().reduce(function (n, it) { return n + (it.qty || 1); }, 0);
  }

  /* ---------------- catalogo ---------------- */
  var catalog = null, catalogLoad = null;
  function loadCatalog() {
    if (catalogLoad) return catalogLoad;
    catalogLoad = fetch("productos.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { catalog = data; return data; });
    return catalogLoad;
  }

  function money(n) {
    return "$" + Math.round(n).toLocaleString("es-MX") + " MXN";
  }

  /* Une el carrito con el catalogo. Descarta lo que ya no exista. */
  function resolve() {
    return loadCatalog().then(function (cat) {
      var out = [];
      read().forEach(function (it) {
        var p = cat[it.id];
        if (!p) return;
        var qty = Math.min(Math.max(parseInt(it.qty, 10) || 1, 1), 10);
        var opt = it.opt || "";
        var price = p.price;
        if (opt && p.options && p.options.choices) {
          var ch = p.options.choices.filter(function (c) { return c.name === opt; })[0];
          if (ch && typeof ch.price === "number") price = ch.price;
        }
        out.push({
          id: it.id, size: it.size || "", opt: opt, qty: qty,
          name: p.name, cat: p.cat, price: price, img: p.img, url: p.url,
          line: price * qty
        });
      });
      return out;
    });
  }

  function totals(items, modo, entrega, pago) {
    var subtotal = items.reduce(function (s, i) { return s + i.line; }, 0);
    var reenvio = (modo === "apartado" && entrega === "envio") ? REENVIO_APARTADO : 0;
    var base = subtotal + reenvio;
    var comision = pago === "tarjeta" ? Math.round(base * COMISION_TARJETA) : 0;
    var total = base + comision;
    var ahora = modo === "apartado" ? Math.round(subtotal / 2) + reenvio + comision : total;
    return {
      subtotal: subtotal, reenvio: reenvio, comision: comision,
      total: total, ahora: ahora,
      resta: modo === "apartado" ? total - ahora : 0
    };
  }

  /* ---------------- contador del header ---------------- */
  function paintCount() {
    var el = document.getElementById("cartCount");
    if (!el) return;
    var n = count();
    el.textContent = n;
    el.hidden = n === 0;
  }

  /* ---------------- aviso flotante ---------------- */
  function toast(msg) {
    var t = document.createElement("div");
    t.className = "cart-toast";
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add("in"); });
    setTimeout(function () {
      t.classList.remove("in");
      setTimeout(function () { t.remove(); }, 300);
    }, 2200);
  }

  function addItem(id, size, opt, qty) {
    opt = opt || "";
    var items = read();
    var found = items.filter(function (i) {
      return i.id === id && i.size === size && (i.opt || "") === opt;
    })[0];
    if (found) { found.qty = Math.min((found.qty || 1) + (qty || 1), 10); }
    else { items.push({ id: id, size: size, opt: opt, qty: qty || 1 }); }
    write(items);
  }

  /* ===================================================================
     Pagina de producto: elegir talla + agregar
     =================================================================== */
  function initDetail() {
    var btn = document.getElementById("addToCart");
    if (!btn) return;
    var chips = document.getElementById("sizeChips");
    var free = document.getElementById("sizeFree");
    var optChips = document.getElementById("optChips");
    var dPrice = document.getElementById("dPrice");
    var picked = "";
    var pickedOpt = "";

    if (chips) {
      chips.addEventListener("click", function (e) {
        var c = e.target.closest(".size-chip");
        if (!c) return;
        chips.querySelectorAll(".size-chip").forEach(function (x) {
          x.classList.remove("is-active");
        });
        c.classList.add("is-active");
        picked = c.dataset.size;
        chips.classList.remove("needs-pick");
      });
    }

    if (optChips) {
      optChips.addEventListener("click", function (e) {
        var c = e.target.closest(".size-chip");
        if (!c) return;
        optChips.querySelectorAll(".size-chip").forEach(function (x) {
          x.classList.remove("is-active");
        });
        c.classList.add("is-active");
        pickedOpt = c.dataset.opt;
        optChips.classList.remove("needs-pick");
        if (dPrice && c.dataset.optPrice) {
          dPrice.textContent = money(parseInt(c.dataset.optPrice, 10));
        }
      });
    }

    btn.addEventListener("click", function () {
      if (optChips && !pickedOpt) {
        optChips.classList.add("needs-pick");
        toast("Primero elige una opcion");
        return;
      }
      var size = chips ? picked : (free ? free.value.trim() : "");
      if (!size) {
        if (chips) chips.classList.add("needs-pick");
        if (free) free.classList.add("needs-pick");
        toast("Primero elige tu talla");
        return;
      }
      addItem(btn.dataset.id, size, pickedOpt, 1);
      toast("Agregado al carrito" + (pickedOpt ? " — " + pickedOpt : "") + " — talla " + size);
    });
  }

  /* Tarjetas de categoria sin pagina de detalle (cadenas) */
  function initCards() {
    document.querySelectorAll(".pc-add").forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.preventDefault();
        addItem(b.dataset.id, b.dataset.size || "Unitalla", "", 1);
        toast("Agregado al carrito");
      });
    });
  }

  /* ===================================================================
     Pagina del carrito
     =================================================================== */
  function initCart() {
    var list = document.getElementById("cartItems");
    if (!list) return;
    var side = document.getElementById("cartSide");
    var empty = document.getElementById("cartEmpty");
    var summary = document.getElementById("cartSummary");

    function paint() {
      resolve().then(function (items) {
        if (!items.length) {
          list.innerHTML = "";
          side.hidden = true;
          empty.hidden = false;
          summary.textContent = "0 productos";
          return;
        }
        empty.hidden = true;
        side.hidden = false;
        var t = totals(items, "liquidar", "gdl", "transferencia");
        summary.textContent = items.length + (items.length === 1 ? " producto" : " productos");
        document.getElementById("sumCount").textContent = String(count());
        document.getElementById("sumTotal").textContent = money(t.subtotal);

        list.innerHTML = items.map(function (i, idx) {
          return '<div class="ci-row" data-idx="' + idx + '">' +
            '<div class="ci-media"><img loading="lazy" src="' + i.img + '" alt=""></div>' +
            '<div class="ci-info">' +
              '<p class="ci-name">' + esc(i.name) + '</p>' +
              '<p class="ci-meta">' + esc(i.cat) +
                (i.opt ? ' &#8226; ' + esc(i.opt) : '') +
                ' &#8226; Talla ' + esc(i.size) + '</p>' +
              '<p class="ci-price">' + money(i.price) + '</p>' +
            '</div>' +
            '<div class="ci-qty">' +
              '<button type="button" data-act="menos" aria-label="Quitar uno">&minus;</button>' +
              '<span>' + i.qty + '</span>' +
              '<button type="button" data-act="mas" aria-label="Agregar uno">+</button>' +
            '</div>' +
            '<div class="ci-line">' + money(i.line) + '</div>' +
            '<button type="button" class="ci-del" data-act="quitar" aria-label="Eliminar">&times;</button>' +
          '</div>';
        }).join("");
      });
    }

    list.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]");
      if (!b) return;
      var row = b.closest(".ci-row");
      var idx = parseInt(row.dataset.idx, 10);
      var items = read();
      if (!items[idx]) return;
      var act = b.dataset.act;
      if (act === "mas") items[idx].qty = Math.min((items[idx].qty || 1) + 1, 10);
      if (act === "menos") items[idx].qty = (items[idx].qty || 1) - 1;
      if (act === "quitar" || items[idx].qty < 1) items.splice(idx, 1);
      write(items);
      paint();
    });

    paint();
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ===================================================================
     Checkout
     =================================================================== */
  function initCheckout() {
    var form = document.getElementById("checkoutForm");
    if (!form) return;

    var linesEl = document.getElementById("coLines");
    var totalsEl = document.getElementById("coTotals");
    var address = document.getElementById("coAddress");
    var errorEl = document.getElementById("coError");
    var submit = document.getElementById("coSubmit");
    var envioNota = document.getElementById("envioNota");
    var openedAt = Date.now();
    var current = [];

    function val(name) {
      var el = form.querySelector('[name="' + name + '"]:checked') ||
               form.querySelector('[name="' + name + '"]');
      return el ? el.value : "";
    }

    function paint() {
      resolve().then(function (items) {
        current = items;
        if (!items.length) {
          location.replace("carrito.html");
          return;
        }
        var modo = val("modo"), entrega = val("entrega"), pago = val("pago");
        address.hidden = entrega !== "envio";
        envioNota.textContent = modo === "apartado"
          ? "Se suman $200 de reenvio al apartar."
          : "Gratis: se liquida el total y llega a tu domicilio.";

        linesEl.innerHTML = items.map(function (i) {
          return '<div class="co-line"><span>' + i.qty + '&times; ' + esc(i.name) +
                 (i.opt ? ' (' + esc(i.opt) + ')' : '') +
                 ' <i>Talla ' + esc(i.size) + '</i></span><b>' + money(i.line) + '</b></div>';
        }).join("");

        var t = totals(items, modo, entrega, pago);
        var rows = '<div class="d-row"><span>Subtotal</span><b>' + money(t.subtotal) + '</b></div>';
        if (t.reenvio) rows += '<div class="d-row"><span>Reenvio</span><b>' + money(t.reenvio) + '</b></div>';
        if (t.comision) rows += '<div class="d-row"><span>Comision tarjeta 5%</span><b>' + money(t.comision) + '</b></div>';
        rows += '<div class="d-row"><span>Total</span><b>' + money(t.total) + '</b></div>';
        rows += '<div class="d-row d-row-hi"><span>' +
                (modo === "apartado" ? "Pagas ahora (50%)" : "Pagas ahora") +
                '</span><b>' + money(t.ahora) + '</b></div>';
        if (t.resta) rows += '<div class="d-row"><span>Liquidas al recibir</span><b>' + money(t.resta) + '</b></div>';
        totalsEl.innerHTML = rows;
      });
    }

    form.addEventListener("change", paint);
    paint();

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      errorEl.hidden = true;

      var entrega = val("entrega");
      var payload = {
        modo: val("modo"),
        entrega: entrega,
        pago: val("pago"),
        nombre: val("nombre").trim(),
        whatsapp: val("whatsapp").replace(/\D/g, ""),
        items: read(),
        hp: val("apellido2"),
        ms: Date.now() - openedAt
      };
      if (entrega === "envio") {
        payload.direccion = {
          estado: val("estado").trim(), ciudad: val("ciudad").trim(),
          calle: val("calle").trim(), colonia: val("colonia").trim(),
          numero: val("numero").trim(), entrecalles: val("entrecalles").trim(),
          cp: val("cp").trim(), referencias: val("referencias").trim()
        };
      }

      // Chequeo rapido para dar feedback; el servidor vuelve a validar TODO.
      var faltan = [];
      if (payload.nombre.length < 2) faltan.push("tu nombre");
      if (payload.whatsapp.length !== 10) faltan.push("tu WhatsApp a 10 digitos");
      if (entrega === "envio") {
        ["estado", "ciudad", "calle", "colonia", "numero", "entrecalles"].forEach(function (k) {
          if (!payload.direccion[k]) faltan.push("tu " + k);
        });
      }
      if (faltan.length) {
        errorEl.textContent = "Falta " + faltan.slice(0, 3).join(", ") + ".";
        errorEl.hidden = false;
        return;
      }

      submit.disabled = true;
      submit.textContent = "Generando…";

      fetch("/api/pedido", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error(res.d && res.d.error ? res.d.error : "No se pudo enviar el pedido.");
          try {
            localStorage.setItem(TICKET_KEY, JSON.stringify(res.d.ticket));
            localStorage.removeItem(KEY);
          } catch (err) {}
          location.href = "ticket.html";
        })
        .catch(function (err) {
          errorEl.textContent = err.message || "No se pudo enviar. Intenta de nuevo.";
          errorEl.hidden = false;
          submit.disabled = false;
          submit.textContent = "Generar mi ticket";
        });
    });
  }

  /* ===================================================================
     Ticket
     =================================================================== */
  function initTicket() {
    var wrap = document.getElementById("ticketWrap");
    if (!wrap) return;
    var data = null;
    try { data = JSON.parse(localStorage.getItem(TICKET_KEY) || "null"); } catch (e) {}
    if (!data) return;

    document.getElementById("ticketEmpty").hidden = true;
    wrap.hidden = false;
    document.getElementById("tkFolio").textContent = data.folio;
    document.getElementById("tkDate").textContent =
      new Date(data.fecha).toLocaleString("es-MX", { dateStyle: "long", timeStyle: "short" });

    document.getElementById("tkLines").innerHTML = (data.items || []).map(function (i) {
      return '<div class="co-line"><span>' + i.qty + '&times; ' + esc(i.name) +
             (i.opt ? ' (' + esc(i.opt) + ')' : '') +
             ' <i>Talla ' + esc(i.size) + '</i></span><b>' + money(i.line) + '</b></div>';
    }).join("");

    var t = data.totales || {};
    var rows = '<div class="d-row"><span>Subtotal</span><b>' + money(t.subtotal) + '</b></div>';
    if (t.reenvio) rows += '<div class="d-row"><span>Reenvio</span><b>' + money(t.reenvio) + '</b></div>';
    if (t.comision) rows += '<div class="d-row"><span>Comision tarjeta 5%</span><b>' + money(t.comision) + '</b></div>';
    rows += '<div class="d-row"><span>Total</span><b>' + money(t.total) + '</b></div>';
    rows += '<div class="d-row d-row-hi"><span>' +
            (data.modo === "apartado" ? "Pagas ahora (50%)" : "Pagas ahora") +
            '</span><b>' + money(t.ahora) + '</b></div>';
    if (t.resta) rows += '<div class="d-row"><span>Liquidas al recibir</span><b>' + money(t.resta) + '</b></div>';
    document.getElementById("tkTotals").innerHTML = rows;

    var pagos = { transferencia: "Transferencia", oxxo: "Deposito OXXO", tarjeta: "Tarjeta (+5%)" };
    var cli = '<div class="d-row"><span>Nombre</span><b>' + esc(data.nombre) + '</b></div>' +
              '<div class="d-row"><span>WhatsApp</span><b>' + esc(data.whatsapp) + '</b></div>' +
              '<div class="d-row"><span>Entrega</span><b>' +
              (data.entrega === "envio" ? "Envio a domicilio" : "Entrega en Guadalajara") + '</b></div>' +
              '<div class="d-row"><span>Pago</span><b>' + (pagos[data.pago] || esc(data.pago)) + '</b></div>';
    if (data.direccion) {
      var d = data.direccion;
      cli += '<div class="d-row d-row-wrap"><span>Direccion</span><b>' +
             esc([d.calle, d.numero, d.colonia, d.ciudad, d.estado, d.cp].filter(Boolean).join(", ")) +
             (d.entrecalles ? "<br>Entre calles: " + esc(d.entrecalles) : "") +
             '</b></div>';
    }
    document.getElementById("tkClient").innerHTML = cli;

    var print = document.getElementById("tkPrint");
    if (print) print.addEventListener("click", function () { window.print(); });

    // Liquidar siempre da derecho a envio gratis, sea cliente de GDL o no.
    document.getElementById("tkPayNote").textContent = data.modo === "apartado"
      ? "Apartado: pagas " + money(t.ahora) + " ahora y " + money(t.resta) + " al recibir."
      : "Pedido liquidado: " + money(t.ahora) + ". Envio gratis a tu domicilio.";
  }

  /* ---------------- arranque ---------------- */
  paintCount();
  initDetail();
  initCards();
  initCart();
  initCheckout();
  initTicket();
})();
