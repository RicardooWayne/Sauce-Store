/* ===================================================================
   SAUCE STORE — buscador (marca / modelo, tolerante a errores de tipeo)
   =================================================================== */
(function () {
  "use strict";
  var btn = document.getElementById("searchBtn");
  var overlay = document.getElementById("searchOverlay");
  var closeBtn = document.getElementById("searchClose");
  var input = document.getElementById("searchInput");
  var results = document.getElementById("searchResults");
  var hint = document.getElementById("searchHint");
  if (!btn || !overlay) return;

  var fuse = null;
  var loading = null;

  function loadIndex() {
    if (loading) return loading;
    loading = fetch("search.json")
      .then(function (r) { return r.json(); })
      .then(function (docs) {
        fuse = new Fuse(docs, {
          keys: [
            { name: "name", weight: 0.5 },
            { name: "cat", weight: 0.2 },
            { name: "kw", weight: 0.3 },
          ],
          threshold: 0.38,
          distance: 60,
          ignoreLocation: true,
          minMatchCharLength: 2,
        });
        return docs;
      })
      .catch(function () { results.innerHTML = "<p class=\"search-empty\">No se pudo cargar el catalogo.</p>"; });
    return loading;
  }

  function render(items) {
    if (!items.length) {
      results.innerHTML = '<p class="search-empty">Sin resultados. Prueba con otra palabra.</p>';
      return;
    }
    results.innerHTML = items.slice(0, 24).map(function (d) {
      return '<a class="sr-item" href="' + d.url + '">' +
        '<div class="sr-media"><img loading="lazy" src="' + d.img + '" alt=""></div>' +
        '<div class="sr-info"><p class="sr-name">' + d.name + '</p>' +
        '<p class="sr-cat">' + d.cat + (d.price ? " &#8226; " + d.price : "") + '</p></div>' +
        '</a>';
    }).join("");
  }

  function search(q) {
    q = q.trim();
    if (!fuse) { return; }
    if (!q) { results.innerHTML = ""; hint.hidden = false; return; }
    hint.hidden = true;
    var found = fuse.search(q).map(function (r) { return r.item; });
    render(found);
  }

  var t;
  input.addEventListener("input", function () {
    clearTimeout(t);
    var v = input.value;
    t = setTimeout(function () { search(v); }, 120);
  });

  function open() {
    overlay.classList.add("open");
    document.body.classList.add("search-open");
    loadIndex();
    setTimeout(function () { input.focus(); }, 60);
  }
  function close() {
    overlay.classList.remove("open");
    document.body.classList.remove("search-open");
  }

  btn.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
    if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); open();
    }
  });
})();
