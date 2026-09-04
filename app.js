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

  /* Dropdowns de nav en táctil */
  document.querySelectorAll(".nav-trigger").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      var panel = btn.nextElementSibling;
      if (!panel) return;
      var open = panel.style.opacity === "1";
      document.querySelectorAll(".nav-panel").forEach(function (p) {
        p.style.opacity = ""; p.style.visibility = ""; p.style.transform = "";
      });
      if (!open) {
        panel.style.opacity = "1";
        panel.style.visibility = "visible";
        panel.style.transform = "translateX(-50%) translateY(0)";
        btn.setAttribute("aria-expanded", "true");
      } else {
        btn.setAttribute("aria-expanded", "false");
      }
      e.stopPropagation();
    });
  });
  document.addEventListener("click", function () {
    document.querySelectorAll(".nav-panel").forEach(function (p) {
      p.style.opacity = ""; p.style.visibility = ""; p.style.transform = "";
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
