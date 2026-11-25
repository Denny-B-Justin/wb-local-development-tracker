(function () {
  "use strict";

  var LDT = (window.LDT = window.LDT || {});
  var widgets = (LDT.widgets = LDT.widgets || {});
  var COMPARE_MAX = 5;

  LDT.params = function () {
    return new URLSearchParams(window.location.search);
  };

  LDT.navigate = function (href, opts) {
    opts = opts || {};
    var target = new URL(href, window.location.href);
    var now = LDT.params();
    var next = target.searchParams;
    var samePage = (now.get("page") || "home") === (next.get("page") || "home") && now.get("country") === next.get("country") && now.get("unit") === next.get("unit");
    var replace = opts.replace !== undefined ? opts.replace : samePage;
    var url = target.pathname + target.search + target.hash;
    if (replace) window.history.replaceState(null, "", url);
    else window.history.pushState(null, "", url);
    window.dispatchEvent(new CustomEvent("_dashprivate_pushstate"));
    if (!samePage && !target.hash) window.scrollTo(0, 0);
  };

  LDT.setParam = function (key, value, opts) {
    var params = LDT.params();
    if (value === null || value === undefined || value === "") params.delete(key);
    else params.set(key, value);
    var query = params.toString().replace(/%2C/g, ",");
    LDT.navigate("?" + query, opts);
  };

  LDT.number = function (value, digits, decimal, group) {
    if (value === null || value === undefined || !isFinite(value)) return "–";
    var text = Math.abs(value).toFixed(digits);
    var parts = text.split(".");
    if (group) parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, group);
    var sign = value < 0 && Number(text) !== 0 ? "-" : "";
    return sign + parts[0] + (parts[1] ? (decimal || ".") + parts[1] : "");
  };

  LDT.fold = function (value) {
    return String(value || "")
      .replace(/[đĐ]/g, function (c) { return c === "đ" ? "d" : "D"; })
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  };

  LDT.el = function (tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      var value = attrs[key];
      if (value === null || value === undefined || value === false) return;
      if (key === "className") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.slice(0, 2) === "on") node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : value);
    });
    (children || []).forEach(function (child) {
      if (child !== null && child !== undefined) node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  };

  LDT.svg = function (tag, attrs) {
    var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (attrs[key] !== null && attrs[key] !== undefined) node.setAttribute(key, attrs[key]);
    });
    return node;
  };

  /* ---------- compare tray (URL + localStorage) ---------- */

  function storageKey(slug) {
    return "ldt:compare:" + slug;
  }

  function readStorage(slug) {
    try {
      var value = JSON.parse(window.localStorage.getItem(storageKey(slug)) || "[]");
      return Array.isArray(value) ? value.filter(function (v) { return /^[a-f0-9]{12}$/.test(v); }).slice(0, COMPARE_MAX) : [];
    } catch (e) {
      return [];
    }
  }

  function writeStorage(slug, ids) {
    try {
      window.localStorage.setItem(storageKey(slug), JSON.stringify(ids));
    } catch (e) {}
  }

  LDT.compareIds = function () {
    return (LDT.params().get("compare") || "").split(",").filter(function (v) { return /^[a-f0-9]{12}$/.test(v); });
  };

  LDT.setCompare = function (ids) {
    var slug = LDT.params().get("country");
    if (slug) writeStorage(slug, ids);
    LDT.setParam("compare", ids.join(","), { replace: true });
  };

  LDT.toggleCompare = function (id) {
    var ids = LDT.compareIds();
    var at = ids.indexOf(id);
    if (at >= 0) ids.splice(at, 1);
    else if (ids.length < COMPARE_MAX) ids.push(id);
    LDT.setCompare(ids);
  };

  var hydrated = {};
  function syncCompare() {
    var frame = document.querySelector(".ws-frame[data-country]");
    if (!frame) return;
    var slug = frame.getAttribute("data-country");
    var ids = LDT.compareIds();
    if (!hydrated[slug]) {
      hydrated[slug] = true;
      if (!ids.length) {
        var stored = readStorage(slug);
        if (stored.length) {
          LDT.setParam("compare", stored.join(","), { replace: true });
          return;
        }
      }
    }
    if (ids.length) writeStorage(slug, ids);
    var badge = frame.querySelector("[data-compare-count]");
    if (badge) {
      var count = ids.length || readStorage(slug).length;
      badge.hidden = count === 0;
      if (badge.firstChild) badge.firstChild.nodeValue = String(count);
    }
  }

  /* ---------- dropdowns (details/summary) ---------- */

  function closeMenus(except) {
    document.querySelectorAll("details.dd[open]").forEach(function (node) {
      if (!except || (node !== except && !node.contains(except))) node.removeAttribute("open");
    });
  }

  document.addEventListener(
    "toggle",
    function (event) {
      var node = event.target;
      if (!(node instanceof HTMLDetailsElement) || !node.classList.contains("dd") || !node.open) return;
      closeMenus(node);
      var input = node.querySelector(".dd-panel input");
      if (input) setTimeout(function () { input.focus(); }, 0);
      var checked = node.querySelector(".dd-item.is-checked");
      if (checked) checked.scrollIntoView({ block: "nearest" });
    },
    true
  );

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!(target instanceof Element)) return;
    if (!target.closest("details.dd")) closeMenus();

    var link = target.closest("a[data-nav]");
    if (link && !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      var href = link.getAttribute("href") || "";
      if (href.charAt(0) === "?") {
        event.preventDefault();
        if (link.classList.contains("is-disabled")) return;
        closeMenus();
        document.body.classList.remove("menu-open");
        var lang = link.getAttribute("data-lang");
        if (lang) {
          LDT.setParam("lang", lang === "en" ? null : lang, { replace: false });
          return;
        }
        LDT.navigate(href, link.getAttribute("data-nav") === "push" ? {} : { replace: true });
        return;
      }
    }

    var disabledLink = target.closest("a.is-disabled");
    if (disabledLink) {
      event.preventDefault();
      return;
    }

    var toggle = target.closest(".js-compare-toggle");
    if (toggle && !toggle.disabled) {
      LDT.toggleCompare(toggle.getAttribute("data-unit"));
      return;
    }
    if (target.closest(".js-compare-clear")) {
      LDT.setCompare([]);
      return;
    }

    var share = target.closest(".js-share");
    if (share) {
      copyLink(share);
      return;
    }

    if (target.closest(".js-menu")) {
      setMenu(!document.body.classList.contains("menu-open"));
      return;
    }
    if (target.closest(".js-menu-close")) {
      setMenu(false);
      return;
    }
    if (target.closest(".js-print")) {
      if (!target.closest(".js-print").disabled) window.print();
      return;
    }

    var group = target.closest(".js-group-toggle");
    if (group) {
      toggleGroup(group.closest("table"), group.getAttribute("data-group"));
      return;
    }
    var all = target.closest(".js-expand-all");
    if (all) {
      var table = all.closest("table");
      var buttons = table.querySelectorAll(".js-group-toggle");
      var open = Array.prototype.every.call(buttons, function (b) { return b.getAttribute("aria-expanded") === "true"; });
      buttons.forEach(function (b) { setGroup(table, b.getAttribute("data-group"), !open); });
      all.textContent = all.getAttribute(open ? "data-expand" : "data-collapse");
      return;
    }

    var sort = target.closest(".js-inv-sort");
    if (sort) {
      sortInventory(sort);
    }
  });

  document.addEventListener("keydown", function (event) {
    var open = document.querySelector("details.dd[open]");
    if (event.key === "Escape") {
      if (open) {
        open.removeAttribute("open");
        var summary = open.querySelector("summary");
        if (summary) summary.focus();
      }
      if (document.body.classList.contains("menu-open")) setMenu(false);
      return;
    }
    if (open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      var items = Array.prototype.slice.call(open.querySelectorAll(".dd-panel a, .dd-panel button, .dd-panel input"));
      if (!items.length) return;
      event.preventDefault();
      var index = items.indexOf(document.activeElement);
      var next = event.key === "ArrowDown" ? (index + 1) % items.length : (index - 1 + items.length) % items.length;
      items[index < 0 ? 0 : next].focus();
    }
    var radio = event.target instanceof Element ? event.target.closest(".segmented [role=radio], .ptabs [role=tab], .theme-switch [role=radio]") : null;
    if (radio && (event.key === "ArrowRight" || event.key === "ArrowLeft")) {
      var siblings = Array.prototype.slice.call(radio.parentNode.querySelectorAll("[role=radio], [role=tab]"));
      var at = siblings.indexOf(radio);
      var to = siblings[(at + (event.key === "ArrowRight" ? 1 : -1) + siblings.length) % siblings.length];
      event.preventDefault();
      to.focus();
      to.click();
    }
  });

  function setMenu(open) {
    document.body.classList.toggle("menu-open", open);
    var button = document.querySelector(".js-menu");
    if (button) {
      button.setAttribute("aria-expanded", String(open));
      button.setAttribute("aria-label", button.getAttribute(open ? "data-close" : "data-open"));
    }
  }

  function copyLink(button) {
    var label = button.querySelector(".share-text");
    var done = function () {
      button.classList.add("is-copied");
      if (label) label.textContent = button.getAttribute("data-copied");
      setTimeout(function () {
        button.classList.remove("is-copied");
        if (label) label.textContent = button.getAttribute("data-label");
      }, 2000);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(window.location.href).then(done, function () {
        window.prompt(button.getAttribute("data-prompt"), window.location.href);
      });
    } else {
      window.prompt(button.getAttribute("data-prompt"), window.location.href);
    }
  }

  function setGroup(table, group, open) {
    table.querySelectorAll('tr[data-group="' + group + '"]').forEach(function (row) { row.classList.toggle("is-open", open); });
    var button = table.querySelector('.js-group-toggle[data-group="' + group + '"]');
    if (button) button.setAttribute("aria-expanded", String(open));
  }

  function toggleGroup(table, group) {
    var button = table.querySelector('.js-group-toggle[data-group="' + group + '"]');
    setGroup(table, group, button.getAttribute("aria-expanded") !== "true");
    var all = table.querySelector(".js-expand-all");
    var buttons = table.querySelectorAll(".js-group-toggle");
    var everyOpen = Array.prototype.every.call(buttons, function (b) { return b.getAttribute("aria-expanded") === "true"; });
    if (all) all.textContent = all.getAttribute(everyOpen ? "data-collapse" : "data-expand");
  }

  /* ---------- strategy inventory table (client-side filters and sort) ---------- */

  function filterInventory(root) {
    var filters = {};
    root.querySelectorAll("[data-filter]").forEach(function (input) { filters[input.getAttribute("data-filter")] = input.value; });
    var query = LDT.fold(filters.query || "");
    var rows = root.querySelectorAll("tr.inv-row");
    var shown = 0;
    rows.forEach(function (row) {
      var ok =
        (!query || row.getAttribute("data-search").indexOf(query) >= 0) &&
        (!filters["inv-year"] || filters["inv-year"] === "all" || row.getAttribute("data-year") === filters["inv-year"]) &&
        (!filters["inv-readiness"] || filters["inv-readiness"] === "all" || row.getAttribute("data-readiness") === filters["inv-readiness"]) &&
        (!filters["inv-type"] || filters["inv-type"] === "all" || row.getAttribute("data-type") === filters["inv-type"]) &&
        (!filters["inv-translation"] || filters["inv-translation"] === "all" || row.getAttribute("data-translation") === filters["inv-translation"]);
      row.hidden = !ok;
      if (ok) shown += 1;
    });
    var label = root.querySelector(".inv-showing");
    if (label) label.textContent = label.getAttribute("data-template").replace("{shown}", shown).replace("{total}", rows.length);
  }

  function sortInventory(button) {
    var table = button.closest("table");
    var key = button.getAttribute("data-key");
    var dir = button.getAttribute("data-dir") === "asc" ? "desc" : "asc";
    table.querySelectorAll(".js-inv-sort").forEach(function (b) {
      b.setAttribute("data-dir", "");
      b.classList.remove("is-active");
      b.parentNode.removeAttribute("aria-sort");
    });
    button.setAttribute("data-dir", dir);
    button.classList.add("is-active");
    button.parentNode.setAttribute("aria-sort", dir === "asc" ? "ascending" : "descending");
    var body = table.tBodies[0];
    var rows = Array.prototype.slice.call(body.rows);
    var attr = "data-sort-" + key;
    var numeric = key === "publication_year" || key === "readiness";
    rows.sort(function (a, b) {
      var left = a.getAttribute(attr) || "";
      var right = b.getAttribute(attr) || "";
      if (!left) return right ? 1 : 0;
      if (!right) return -1;
      var order = numeric ? Number(left) - Number(right) : left.localeCompare(right);
      return dir === "asc" ? order : -order;
    });
    rows.forEach(function (row) { body.appendChild(row); });
  }

  document.addEventListener("input", function (event) {
    var root = event.target instanceof Element ? event.target.closest(".js-inventory") : null;
    if (root) filterInventory(root);
  });
  document.addEventListener("change", function (event) {
    var root = event.target instanceof Element ? event.target.closest(".js-inventory") : null;
    if (root) filterInventory(root);
  });

  widgets.inventory = function (node) {
    var slot = node.querySelector(".inv-query-slot");
    if (!slot || slot.firstChild) return;
    slot.appendChild(LDT.el("input", { type: "search", maxlength: "80", autocomplete: "off", className: "search-input sm", "data-filter": "query", placeholder: slot.getAttribute("data-placeholder"), "aria-label": slot.getAttribute("data-placeholder") }));
  };

  /* ---------- landing feature list ---------- */

  function activateFeature(button) {
    var root = button.closest(".js-features");
    var index = button.getAttribute("data-index");
    root.querySelectorAll(".js-feature").forEach(function (b) {
      var on = b.getAttribute("data-index") === index;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-pressed", String(on));
    });
    root.querySelectorAll(".fl-shot").forEach(function (img) {
      var on = img.getAttribute("data-index") === index;
      img.classList.toggle("is-active", on);
      img.setAttribute("aria-hidden", String(!on));
      img.setAttribute("alt", on ? img.getAttribute("data-alt") : "");
    });
  }
  ["mouseover", "focusin", "click"].forEach(function (type) {
    document.addEventListener(type, function (event) {
      var button = event.target instanceof Element ? event.target.closest(".js-feature") : null;
      if (button) activateFeature(button);
    });
  });

  /* ---------- page lifecycle ---------- */

  function openFromHash() {
    var id = window.location.hash.slice(1);
    if (!id) return;
    var node = document.getElementById(id);
    if (node instanceof HTMLDetailsElement) {
      node.open = true;
      node.scrollIntoView({ block: "start" });
    }
  }
  window.addEventListener("hashchange", openFromHash);

  function applyMeta() {
    var meta = document.getElementById("page-meta");
    if (!meta) return;
    var title = meta.getAttribute("data-title");
    if (title && document.title !== title) document.title = title;
    var lang = meta.getAttribute("data-lang");
    if (lang && document.documentElement.lang !== lang) document.documentElement.lang = lang;
  }

  function mountWidgets() {
    document.querySelectorAll("[data-widget]").forEach(function (node) {
      var kind = node.getAttribute("data-widget");
      var widget = widgets[kind];
      if (!widget) return;
      var config = node.getAttribute("data-config") || "{}";
      if (node.__ldtConfig === config) return;
      node.__ldtConfig = config;
      try {
        widget(node, JSON.parse(config));
      } catch (error) {
        if (window.console) console.error("LDT widget " + kind + " failed", error);
      }
    });
  }

  var scheduled = false;
  var lastPage = null;
  function afterRender() {
    scheduled = false;
    applyMeta();
    mountWidgets();
    syncCompare();
    var meta = document.getElementById("page-meta");
    var key = meta ? meta.getAttribute("data-page") : null;
    if (key && key !== lastPage) {
      lastPage = key;
      openFromHash();
    }
  }
  function schedule() {
    if (!scheduled) {
      scheduled = true;
      window.requestAnimationFrame(afterRender);
    }
  }

  function watchPending() {
    var page = document.getElementById("page");
    document.documentElement.classList.toggle("ldt-pending", Boolean(page && page.getAttribute("data-dash-is-loading") === "true"));
  }

  function boot() {
    new MutationObserver(function (records) {
      for (var i = 0; i < records.length; i += 1) {
        if (records[i].type === "attributes" && records[i].attributeName === "data-dash-is-loading") watchPending();
      }
      schedule();
    }).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-config", "data-dash-is-loading", "data-cached"] });
    schedule();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  /* ---------- Dash clientside callbacks ---------- */

  window.dash_clientside = Object.assign({}, window.dash_clientside, {
    ldt: {
      syncSearch: function (value) {
        var params = LDT.params();
        var text = String(value || "").trim().slice(0, 80);
        if (text) params.set("q", text);
        else params.delete("q");
        params.delete("limit");
        window.history.replaceState(null, "", "?" + params.toString().replace(/%2C/g, ","));
        return window.dash_clientside.no_update;
      },
    },
  });
})();
