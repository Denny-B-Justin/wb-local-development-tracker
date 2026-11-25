(function () {
  "use strict";

  var LDT = window.LDT;
  var el = LDT.el;
  var svg = LDT.svg;
  var TICKS = [0, 25, 50, 75, 100];

  function linear(d0, d1, r0, r1) {
    return function (v) { return r0 + ((v - d0) / (d1 - d0)) * (r1 - r0); };
  }

  function observeSize(node, draw) {
    if (node.__resize) node.__resize.disconnect();
    var frame = 0;
    node.__resize = new ResizeObserver(function () {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(draw);
    });
    node.__resize.observe(node);
    draw();
  }

  /* ---------- compare scatterplot ---------- */

  LDT.widgets.scatter = function (node, config) {
    var M = { top: 20, right: 28, bottom: 48, left: 56 };
    var hover = null;
    var points = config.points.map(function (p) {
      return { id: p[0], name: p[1], area: p[2], x: p[3], y: p[4], size: p[5], selected: p[6] === 1 };
    });
    var sizes = points.map(function (p) { return p.size; }).filter(function (v) { return v !== null && v > 0; }).sort(function (a, b) { return a - b; });
    var cap = sizes[Math.floor(sizes.length * 0.95)] || 1;
    var radius = function (p) {
      if (!config.size) return 5;
      if (p.size === null) return 4;
      var t = Math.sqrt(Math.min(Math.max(p.size, 0), cap) / cap);
      return 2.5 + t * 12.5;
    };
    var text = config.text;
    var fmt = function (v) { return LDT.number(v, 1, text.decimal); };
    var fmtSize = function (v) {
      if (v === null || v === undefined) return "–";
      return config.sizeKind === "area" ? LDT.number(Math.round(v), 0, text.decimal, text.group) + " km²" : LDT.number(Math.round(v), 0, text.decimal, text.group);
    };
    node.innerHTML = "";
    var tooltip = el("div", { className: "chart-tooltip", role: "status", hidden: true });
    node.appendChild(tooltip);
    var root = null;

    function draw() {
      var width = Math.max(260, node.clientWidth || 800);
      var height = Math.max(320, node.clientHeight || 520);
      var x = linear(0, 100, M.left, width - M.right);
      var y = linear(0, 100, height - M.bottom, M.top);
      if (root) root.remove();
      root = svg("svg", { width: width, height: height, role: "img", "aria-label": text.aria, class: "chart-svg" });
      TICKS.forEach(function (tick) {
        root.appendChild(svg("line", { x1: x(tick), x2: x(tick), y1: M.top, y2: height - M.bottom, class: "grid" }));
        root.appendChild(svg("line", { x1: M.left, x2: width - M.right, y1: y(tick), y2: y(tick), class: "grid" }));
        var tx = svg("text", { x: x(tick), y: height - M.bottom + 18, "text-anchor": "middle", class: "tick" });
        tx.textContent = tick;
        root.appendChild(tx);
        var ty = svg("text", { x: M.left - 10, y: y(tick), dy: "0.32em", "text-anchor": "end", class: "tick" });
        ty.textContent = tick;
        root.appendChild(ty);
      });
      var ax = svg("text", { x: (M.left + width - M.right) / 2, y: height - 8, "text-anchor": "middle", class: "axis" });
      ax.textContent = text.axis.replace("{label}", config.x);
      root.appendChild(ax);
      var ay = svg("text", { transform: "translate(16 " + (M.top + height - M.bottom) / 2 + ") rotate(-90)", "text-anchor": "middle", class: "axis" });
      ay.textContent = text.axis.replace("{label}", config.y);
      root.appendChild(ay);

      config.baselines.forEach(function (base) {
        var cls = base.tone === "area" ? "base-area" : "base-national";
        var g = svg("g", { "pointer-events": "none" });
        if (base.x !== null) {
          g.appendChild(svg("line", { x1: x(base.x), x2: x(base.x), y1: M.top, y2: height - M.bottom, class: cls, "stroke-width": 1.5, "stroke-dasharray": "5 4" }));
          var label = svg("text", { x: x(base.x) + 4, y: M.top + (base.tone === "area" ? 10 : 24), class: cls + "-label halo" });
          label.textContent = base.label;
          g.appendChild(label);
        }
        if (base.y !== null) g.appendChild(svg("line", { x1: M.left, x2: width - M.right, y1: y(base.y), y2: y(base.y), class: cls, "stroke-width": 1.5, "stroke-dasharray": "5 4" }));
        root.appendChild(g);
      });

      var ordered = points.slice().sort(function (a, b) { return Number(a.selected) - Number(b.selected) || radius(b) - radius(a); });
      ordered.forEach(function (p) {
        var isHover = hover === p.id;
        var circle = svg("circle", {
          cx: x(p.x), cy: y(p.y), r: radius(p),
          class: "pt" + (p.selected ? " is-selected" : isHover ? " is-hover" : ""),
          "fill-opacity": p.selected || isHover ? 1 : 0.7,
          "stroke-width": p.selected ? 2 : 0,
        });
        circle.addEventListener("mouseenter", function () { hover = p.id; showTip(p, x, y, width); circle.setAttribute("class", "pt" + (p.selected ? " is-selected" : " is-hover")); circle.setAttribute("fill-opacity", 1); });
        circle.addEventListener("mouseleave", function () { if (hover === p.id) hover = null; tooltip.hidden = true; circle.setAttribute("class", "pt" + (p.selected ? " is-selected" : "")); circle.setAttribute("fill-opacity", p.selected ? 1 : 0.7); });
        circle.addEventListener("click", function () {
          if (!p.selected && config.full) return;
          LDT.toggleCompare(p.id);
        });
        circle.addEventListener("dblclick", function () { LDT.navigate(config.openHref.replace("__ID__", p.id), { replace: false }); });
        root.appendChild(circle);
      });
      points.filter(function (p) { return p.selected; }).forEach(function (p) {
        var label = svg("text", { x: x(p.x) + radius(p) + 5, y: y(p.y), dy: "0.32em", "pointer-events": "none", class: "pt-label halo" });
        label.textContent = p.name;
        root.appendChild(label);
      });
      node.insertBefore(root, tooltip);
    }

    function showTip(p, x, y, width) {
      tooltip.innerHTML = "";
      var rows = [[config.x, fmt(p.x)], [config.y, fmt(p.y)]];
      if (config.size) rows.push([config.size, fmtSize(p.size)]);
      var dl = el("dl", { className: "tip-grid" });
      rows.forEach(function (r) {
        dl.appendChild(el("dt", { text: r[0] }));
        dl.appendChild(el("dd", { text: r[1] }));
      });
      tooltip.appendChild(el("div", { className: "tip-name", text: p.name }));
      tooltip.appendChild(el("div", { className: "tip-area", text: p.area }));
      tooltip.appendChild(dl);
      tooltip.appendChild(el("div", { className: "tip-hint", text: p.selected ? text.remove : text.select }));
      tooltip.style.left = Math.min(x(p.x) + 12, width - 200) + "px";
      tooltip.style.top = Math.max(y(p.y) - 70, 4) + "px";
      tooltip.hidden = false;
    }

    observeSize(node, draw);
  };

  /* ---------- profile trend line chart ---------- */

  LDT.widgets.line = function (node, config) {
    var H = 260;
    var M = { top: 12, right: 16, bottom: 28, left: 36 };
    node.innerHTML = "";
    var holder = el("div", { className: "line-holder" });
    var legend = el("figcaption", { className: "line-legend" });
    config.series.forEach(function (s) {
      var key = svg("svg", { width: 22, height: 8, "aria-hidden": "true" });
      key.appendChild(svg("line", { x1: 0, x2: 22, y1: 4, y2: 4, class: "tone-" + s.tone, "stroke-width": 2.5, "stroke-dasharray": s.dash || null }));
      legend.appendChild(el("span", { className: "line-key" }, [key, el("span", { className: s.emphasis ? "font-semibold" : "", text: s.label })]));
    });
    node.appendChild(el("figure", { className: "line-figure" }, [holder, legend]));

    function draw() {
      var width = Math.max(200, holder.clientWidth || 640);
      holder.innerHTML = "";
      var n = config.x.length;
      var step = (width - M.left - M.right) / (n - 1 + 0.6);
      var x = function (i) { return M.left + step * (0.3 + i); };
      var y = linear(0, 100, H - M.bottom, M.top);
      var root = svg("svg", { width: width, height: H, role: "img", "aria-label": config.title, class: "chart-svg" });
      TICKS.forEach(function (tick) {
        root.appendChild(svg("line", { x1: M.left, x2: width - M.right, y1: y(tick), y2: y(tick), class: "grid" }));
        var label = svg("text", { x: M.left - 8, y: y(tick), dy: "0.32em", "text-anchor": "end", class: "tick" });
        label.textContent = tick;
        root.appendChild(label);
      });
      config.x.forEach(function (year, i) {
        var label = svg("text", { x: x(i), y: H - 8, "text-anchor": "middle", class: "tick-x" });
        label.textContent = year;
        root.appendChild(label);
      });
      config.series.forEach(function (s) {
        var d = "";
        s.values.forEach(function (v, i) {
          if (v === null) return;
          d += (i === 0 || s.values[i - 1] === null ? "M" : "L") + x(i) + "," + y(v);
        });
        root.appendChild(svg("path", { d: d, fill: "none", class: "tone-" + s.tone, "stroke-width": s.emphasis ? 2.5 : 1.75, "stroke-dasharray": s.dash || null, "stroke-linejoin": "round" }));
        s.values.forEach(function (v, i) {
          if (v !== null) root.appendChild(svg("circle", { cx: x(i), cy: y(v), r: s.emphasis ? 3.5 : 2.5, class: "fill-" + s.tone }));
        });
      });
      holder.appendChild(root);
    }
    observeSize(holder, draw);
  };

  /* ---------- unit search (compare "+ Add", brief scope) ---------- */

  LDT.widgets["unit-search"] = function (node, config) {
    node.innerHTML = "";
    var units = config.units.map(function (u) { return { id: u[0], name: u[1], area: u[2], hay: LDT.fold(u[1] + " " + u[2]) }; });
    var input = el("input", { type: "search", className: "search-input sm", placeholder: config.placeholder, "aria-label": config.placeholder, maxlength: "80", autocomplete: "off" });
    var list = el("ul", { className: "search-results" });

    function choose(id) {
      var details = node.closest("details");
      if (details) details.removeAttribute("open");
      if (config.mode === "append") {
        var ids = LDT.compareIds();
        if (ids.indexOf(id) < 0 && ids.length < 5) ids.push(id);
        LDT.setCompare(ids);
      } else {
        LDT.setParam(config.param, id, { replace: false });
      }
    }

    function render() {
      var words = LDT.fold(input.value).split(/\s+/).filter(Boolean);
      var matches = units.filter(function (u) { return words.every(function (w) { return u.hay.indexOf(w) >= 0; }); }).slice(0, config.limit || 8);
      list.innerHTML = "";
      matches.forEach(function (u) {
        var button = el("button", { type: "button", className: "search-hit" + (u.id === config.current ? " is-current" : ""), "aria-current": u.id === config.current ? "true" : null, onclick: function () { choose(u.id); } }, [
          el("span", { className: "hit-name", text: u.name }),
          el("span", { className: "hit-area", text: u.area }),
        ]);
        list.appendChild(el("li", {}, [button]));
      });
      if (!matches.length) list.appendChild(el("li", { className: "search-empty", text: config.empty }));
      node.__first = matches[0] ? matches[0].id : null;
    }

    input.addEventListener("input", render);
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && node.__first) {
        event.preventDefault();
        choose(node.__first);
      }
    });
    node.appendChild(el("label", { className: "search-box sm" }, [el("span", { className: "i i-search search-icon sm", "aria-hidden": "true" }), input]));
    node.appendChild(list);
    render();
  };
})();
