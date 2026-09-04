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

  /* Cuadro de referencias: una a la vez, va rotando sola */
  var refImg = document.getElementById("refRotator");
  var refData = document.getElementById("refData");
  var refCount = document.getElementById("refCount");
  if (refImg && refData && !reduce) {
    var refList = JSON.parse(refData.textContent);
    var refIdx = 0;
    if (refList.length > 1) {
      setInterval(function () {
        refIdx = (refIdx + 1) % refList.length;
        refImg.style.opacity = "0";
        setTimeout(function () {
          refImg.src = refList[refIdx];
          refImg.style.opacity = "1";
          if (refCount) {
            refCount.textContent = String(refIdx + 1).padStart(2, "0") + "/" + String(refList.length).padStart(2, "0");
          }
        }, 400);
      }, 3200);
    }
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
})();
