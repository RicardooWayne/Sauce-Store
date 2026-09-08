/* ===================================================================
   SAUCE STORE — interacciones
   =================================================================== */
(function () {
  "use strict";

  /* Header sólido al hacer scroll */
  var header = document.getElementById("siteHeader");
  var onScroll = function () {
    if (!header) return;
    header.classList.toggle("solid", window.scrollY > 40);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* Menú móvil */
  var burger = document.getElementById("burger");
  if (burger) {
    burger.addEventListener("click", function () {
      document.body.classList.toggle("menu-open");
    });
    document.querySelectorAll("#mobileMenu a").forEach(function (a) {
      a.addEventListener("click", function () {
        document.body.classList.remove("menu-open");
      });
    });
    /* cada grupo (Tenis, Ropa...) se abre/cierra al tocarlo */
    document.querySelectorAll(".m-trigger").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var g = btn.parentElement;
        var open = g.classList.toggle("open");
        btn.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });
  }

  /* Dropdowns de nav en táctil (en desktop ya abren solos con :hover) */
  document.querySelectorAll(".nav-trigger").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      var panel = btn.nextElementSibling;
      if (!panel) return;
      var open = panel.classList.contains("force-open");
      document.querySelectorAll(".nav-panel").forEach(function (p) {
        p.classList.remove("force-open");
      });
      if (!open) {
        panel.classList.add("force-open");
        btn.setAttribute("aria-expanded", "true");
      } else {
        btn.setAttribute("aria-expanded", "false");
      }
      e.stopPropagation();
    });
  });
  document.addEventListener("click", function () {
    document.querySelectorAll(".nav-panel").forEach(function (p) {
      p.classList.remove("force-open");
    });
  });

  /* Reveal on scroll */
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revs = document.querySelectorAll(".reveal");
  if (reduce || !("IntersectionObserver" in window)) {
    revs.forEach(function (el) { el.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    revs.forEach(function (el) { io.observe(el); });
  }

  /* Pausar videos fuera de viewport */
  if ("IntersectionObserver" in window) {
    var vio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var v = en.target;
        if (en.isIntersecting) { var p = v.play(); if (p) p.catch(function () {}); }
        else { v.pause(); }
      });
    }, { threshold: 0.15 });
    document.querySelectorAll("video").forEach(function (v) { vio.observe(v); });
  }

  /* Riel horizontal de categorías: flechas + arrastrar con mouse + rueda */
  var rail = document.getElementById("catRail");
  if (rail) {
    var step = function () { return Math.round(rail.clientWidth * 0.85); };
    document.querySelectorAll("[data-rail]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        rail.scrollBy({ left: btn.dataset.rail === "next" ? step() : -step() });
      });
    });
    rail.addEventListener("wheel", function (e) {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        rail.scrollLeft += e.deltaY;
        e.preventDefault();
      }
    }, { passive: false });
    var dragging = false, startX = 0, startScroll = 0, moved = false;
    rail.addEventListener("pointerdown", function (e) {
      dragging = true; moved = false;
      startX = e.clientX; startScroll = rail.scrollLeft;
      rail.classList.add("dragging");
    });
    window.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      var dx = e.clientX - startX;
      if (Math.abs(dx) > 4) moved = true;
      rail.scrollLeft = startScroll - dx;
    });
    window.addEventListener("pointerup", function () {
      dragging = false;
      rail.classList.remove("dragging");
    });
    // evita que un arrastre dispare el link de la tarjeta
    rail.addEventListener("click", function (e) {
      if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; }
    }, true);
  }

  /* Galería de detalle */
  var main = document.getElementById("gMain");
  if (main) {
    document.querySelectorAll(".g-thumb").forEach(function (t) {
      t.addEventListener("click", function () {
        main.src = t.dataset.src;
        document.querySelectorAll(".g-thumb").forEach(function (x) {
          x.classList.remove("is-active");
        });
        t.classList.add("is-active");
      });
    });
  }

  /* Lightbox de referencias (portada) */
  if (window.GLightbox && document.querySelector(".ref-item")) {
    GLightbox({ selector: ".ref-item", loop: true, touchNavigation: true });
  }

  /* Lightbox (GLightbox) */
  if (window.GLightbox) {
    var lb = GLightbox({ selector: ".glink", loop: true, touchNavigation: true });
    var zoom = document.getElementById("gZoom");
    if (zoom) {
      zoom.addEventListener("click", function () {
        var links = document.querySelectorAll(".glink");
        var cur = main ? main.getAttribute("src") : null;
        var idx = 0;
        links.forEach(function (l, i) {
          if (cur && l.getAttribute("href") === cur) idx = i;
        });
        lb.openAt(idx);
      });
    }
    document.querySelectorAll(".g-main").forEach(function (m) {
      m.style.cursor = "zoom-in";
      m.addEventListener("click", function () { lb.openAt(0); });
    });
  }

  /* ================= La prenda del dia (-10%) =================
     Se sortea un producto por la FECHA de hoy en hora de Mexico: todos
     los visitantes ven el mismo ese dia y a las 00:00 (MX) cambia solo.
     El mismo calculo lo hacen cart.js y el servidor (pedido.js), asi el
     descuento del carrito y del ticket siempre coinciden. */
  window.SauceDeal = {
    mxDate: function () {
      try {
        return new Intl.DateTimeFormat("en-CA", {
          timeZone: "America/Mexico_City",
          year: "numeric", month: "2-digit", day: "2-digit"
        }).format(new Date());
      } catch (e) {
        return new Date().toISOString().slice(0, 10);
      }
    },
    hash: function (s) {
      var h = 5381;
      for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
      return h;
    },
    idFor: function (catalog) {
      var ids = Object.keys(catalog || {});
      if (!ids.length) return null;
      return ids[this.hash(this.mxDate()) % ids.length];
    },
    OFF: 0.10
  };

  var dealBox = document.getElementById("dealDay");
  if (dealBox) {
    fetch("productos.json").then(function (r) { return r.json(); }).then(function (cat) {
      var id = window.SauceDeal.idFor(cat);
      var p = id && cat[id];
      if (!p) return;
      var base = p.price;
      var lows = [];
      (Array.isArray(p.options) ? p.options : p.options ? [p.options] : []).forEach(function (g) {
        (g.choices || []).forEach(function (c) {
          if (typeof c.price === "number") lows.push(c.price);
        });
      });
      if (lows.length) base = Math.min.apply(null, lows);
      var nuevo = Math.round(base * (1 - window.SauceDeal.OFF));
      var money = function (n) { return "$" + Number(n).toLocaleString("es-MX") + " MXN"; };
      document.getElementById("dealImg").src = p.img;
      document.getElementById("dealImg").alt = p.name;
      document.getElementById("dealCat").textContent = p.cat;
      document.getElementById("dealName").textContent = p.name;
      document.getElementById("dealOld").textContent = money(base);
      document.getElementById("dealNew").textContent = money(nuevo);
      document.getElementById("dealCard").href = p.url;
      dealBox.hidden = false;
      startDealTimer();
    }).catch(function () {});
  }

  /* Cuenta regresiva hasta las 00:00 hora de Mexico. Cuando llega a cero
     recarga para traer la prenda del dia nueva. */
  function mxSecondsToday() {
    try {
      var parts = new Intl.DateTimeFormat("en-GB", {
        timeZone: "America/Mexico_City", hour12: false,
        hour: "2-digit", minute: "2-digit", second: "2-digit"
      }).formatToParts(new Date());
      var h = 0, m = 0, s = 0;
      parts.forEach(function (p) {
        if (p.type === "hour") h = parseInt(p.value, 10) % 24;
        if (p.type === "minute") m = parseInt(p.value, 10);
        if (p.type === "second") s = parseInt(p.value, 10);
      });
      return h * 3600 + m * 60 + s;
    } catch (e) {
      var d = new Date();
      return d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds();
    }
  }
  function startDealTimer() {
    var el = document.getElementById("dealTimer");
    if (!el) return;
    var tick = function () {
      var rem = 86400 - mxSecondsToday();
      if (rem <= 0) { location.reload(); return; }
      var h = Math.floor(rem / 3600);
      var m = Math.floor((rem % 3600) / 60);
      var s = rem % 60;
      var pad = function (n) { return n < 10 ? "0" + n : "" + n; };
      el.textContent = pad(h) + ":" + pad(m) + ":" + pad(s);
    };
    tick();
    setInterval(tick, 1000);
  }
})();
