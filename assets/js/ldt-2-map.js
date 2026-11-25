(function () {
  "use strict";

  var LDT = window.LDT;
  var el = LDT.el;
  var BREAKS = [100 / 6, 200 / 6, 300 / 6, 400 / 6, 500 / 6];
  var geometryCache = {};
  var contextCache = {};
  var maplibrePromise = null;

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue("--color-" + name).trim();
  }

  function asset(path) {
    return new URL(path, window.location.href).href;
  }

  function loadMaplibre() {
    if (!maplibrePromise) {
      maplibrePromise = import(asset("assets/vendor/maplibre/maplibre-gl.mjs")).then(function (module) {
        var lib = module.default || module;
        lib.setWorkerUrl(asset("assets/vendor/maplibre/maplibre-gl-worker.mjs"));
        return lib;
      });
      maplibrePromise.catch(function () { maplibrePromise = null; });
    }
    return maplibrePromise;
  }

  function loadGeometry(iso3) {
    if (!geometryCache[iso3]) {
      geometryCache[iso3] = fetch("api/geometry/" + encodeURIComponent(iso3), { credentials: "same-origin" }).then(function (response) {
        if (!response.ok) throw new Error("geometry " + response.status);
        return response.json();
      });
      geometryCache[iso3].catch(function () { delete geometryCache[iso3]; });
    }
    return geometryCache[iso3];
  }

  function loadContext(slug) {
    if (!contextCache[slug]) {
      contextCache[slug] = fetch(asset("assets/geo/context/" + encodeURIComponent(slug) + ".json"))
        .then(function (response) { return response.ok ? response.json() : null; })
        .catch(function () { return null; });
    }
    return contextCache[slug];
  }

  function hatch(line, background) {
    var size = 16;
    var canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = line;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, size);
    ctx.lineTo(size, 0);
    ctx.moveTo(-size / 2, size / 2);
    ctx.lineTo(size / 2, -size / 2);
    ctx.moveTo(size / 2, size * 1.5);
    ctx.lineTo(size * 1.5, size / 2);
    ctx.stroke();
    return ctx.getImageData(0, 0, size, size);
  }

  function unitIndex(config) {
    var index = {};
    config.units.forEach(function (u) { index[u[0]] = { value: u[1], inContext: u[2] === 1 }; });
    return index;
  }

  function contextKey(config) {
    return config.units.filter(function (u) { return u[2] === 1; }).map(function (u) { return u[0]; }).sort().join(",");
  }

  function build(node) {
    node.innerHTML = "";
    var state = { node: node };
    state.canvas = el("div", { className: "map-canvas" });
    state.overlay = el("div", { className: "map-overlay" }, [el("span", { className: "map-overlay-text", role: "status" })]);
    state.tooltip = el("div", { className: "map-tooltip", hidden: true }, [el("div", { className: "map-tip-name" }), el("div", { className: "map-tip-value" })]);
    var button = function (icon, action, labelKey) {
      return el("button", { type: "button", className: "map-btn", "data-label": labelKey, onclick: action }, [el("span", { className: "i i-" + icon + " size-3-5", "aria-hidden": "true" })]);
    };
    state.controls = el("div", { className: "map-controls" }, [
      button("plus", function () { if (state.map) state.map.zoomIn(); }, "zoomIn"),
      button("minus", function () { if (state.map) state.map.zoomOut(); }, "zoomOut"),
      button("maximize-2", function () { fit(state, true); }, "fit"),
    ]);
    node.appendChild(el("div", { className: "map-canvas-wrap" }, [state.canvas]));
    node.appendChild(state.overlay);
    node.appendChild(state.tooltip);
    node.appendChild(state.controls);
    return state;
  }

  function setOverlay(state, text) {
    state.overlay.hidden = !text;
    state.overlay.firstChild.textContent = text || "";
  }

  function bounds(state) {
    var result = null;
    if (!state.geometry) return null;
    state.geometry.features.forEach(function (feature) {
      var unit = state.units[feature.properties.id];
      if (!unit || !unit.inContext) return;
      var b = feature.properties.bbox;
      result = result ? [Math.min(result[0], b[0]), Math.min(result[1], b[1]), Math.max(result[2], b[2]), Math.max(result[3], b[3])] : b.slice();
    });
    return result;
  }

  function fit(state, animate) {
    var b = bounds(state);
    if (b && state.map) state.map.fitBounds(b, { padding: 24, duration: animate ? 450 : 0, maxZoom: state.config.maxZoom || 11 });
  }

  function applyState(state) {
    var map = state.map;
    if (!map || !map.getSource("units")) return;
    state.geometry.features.forEach(function (feature) {
      var id = feature.properties.id;
      var unit = state.units[id];
      var inContext = Boolean(unit && unit.inContext);
      var hasValue = Boolean(unit && unit.value !== null && unit.value !== undefined);
      map.setFeatureState({ source: "units", id: id }, { inContext: inContext, hasValue: hasValue, value: hasValue ? unit.value : 0, gap: inContext && !hasValue, selected: id === state.config.selected });
    });
    var hasData = state.config.units.some(function (u) { return u[2] === 1 && u[1] !== null; });
    setOverlay(state, hasData ? "" : state.config.text.noData);
  }

  function create(state) {
    var config = state.config;
    setOverlay(state, config.text.loading);
    Promise.all([loadMaplibre(), loadGeometry(config.iso3), loadContext(config.slug)]).then(function (loaded) {
      if (!state.node.isConnected) return;
      var lib = loaded[0];
      var geometry = loaded[1];
      var surroundings = loaded[2];
      state.geometry = geometry;
      var ramp = [1, 2, 3, 4, 5, 6].map(function (i) { return token("ramp-" + i); });
      var noData = token("no-data");
      var map = new lib.Map({
        container: state.canvas,
        style: { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": token(surroundings ? "map-sea" : "surface") } }] },
        maxBounds: surroundings ? surroundings.bbox : undefined,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        doubleClickZoom: false,
        renderWorldCopies: false,
      });
      map.touchZoomRotate.disableRotation();
      state.map = map;

      map.on("load", function () {
        map.addImage("hatch", hatch(token("ink-faint"), noData), { pixelRatio: 2 });
        if (surroundings) {
          map.addSource("surroundings", { type: "geojson", data: surroundings });
          map.addLayer({ id: "surroundings-land", type: "fill", source: "surroundings", paint: { "fill-color": token("map-land") } });
          map.addLayer({ id: "surroundings-border", type: "line", source: "surroundings", paint: { "line-color": token("map-border"), "line-width": 0.8 } });
          var labels = [];
          surroundings.features.forEach(function (feature) {
            var spots = feature.properties.labels;
            if (!spots || !spots.length) return;
            var label = el("span", { className: "map-country-label", "aria-hidden": "true", text: feature.properties.name });
            var marker = new lib.Marker({ element: label }).setLngLat(spots[0]).addTo(map);
            labels.push({ element: label, marker: marker, spots: spots });
          });
          var fits = function (element, frame) {
            var box = element.getBoundingClientRect();
            var x0 = box.left - frame.left - 4, y0 = box.top - frame.top - 4, x1 = box.right - frame.left + 4, y1 = box.bottom - frame.top + 4;
            if (x0 < 0 || y0 < 0 || x1 > frame.width || y1 > frame.height) return false;
            return map.queryRenderedFeatures([[x0, y0], [x1, y1]], { layers: ["units-fill"] }).length === 0;
          };
          map.on("idle", function () {
            var frame = map.getContainer().getBoundingClientRect();
            labels.forEach(function (item) {
              var found = item.spots.some(function (spot) {
                item.marker.setLngLat(spot);
                return fits(item.element, frame);
              });
              item.element.style.visibility = found ? "visible" : "hidden";
            });
          });
        }
        map.addSource("units", { type: "geojson", data: geometry, promoteId: "id" });
        var step = ["step", ["to-number", ["feature-state", "value"], 0], ramp[0]];
        BREAKS.forEach(function (value, index) { step.push(value, ramp[index + 1]); });
        map.addLayer({ id: "units-fill", type: "fill", source: "units", paint: { "fill-color": ["case", ["all", ["boolean", ["feature-state", "inContext"], false], ["boolean", ["feature-state", "hasValue"], false]], step, noData] } });
        map.addLayer({ id: "units-gap", type: "fill", source: "units", paint: { "fill-pattern": "hatch", "fill-opacity": ["case", ["boolean", ["feature-state", "gap"], false], 1, 0] } });
        map.addLayer({ id: "units-line", type: "line", source: "units", paint: { "line-color": token("surface"), "line-width": ["case", ["boolean", ["feature-state", "inContext"], false], 0.6, 0.3] } });
        map.addLayer({ id: "units-hover", type: "line", source: "units", paint: { "line-color": token("indigo-800"), "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 1.5, 0] } });
        map.addLayer({ id: "units-selected", type: "line", source: "units", paint: { "line-color": token("highlight"), "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 2.5, 0] } });
        applyState(state);
        fit(state, false);
        state.ready = true;
        state.fitKey = contextKey(state.config);
      });

      var hovered = null;
      var setHover = function (id) {
        if (hovered === id) return;
        if (hovered) map.setFeatureState({ source: "units", id: hovered }, { hover: false });
        hovered = id;
        if (id) map.setFeatureState({ source: "units", id: id }, { hover: true });
      };
      var featureAt = function (event) {
        return map.queryRenderedFeatures([event.point.x, event.point.y], { layers: ["units-fill"] })[0];
      };
      map.on("mousemove", function (event) {
        var feature = featureAt(event);
        var id = feature ? feature.properties.id : null;
        setHover(id);
        var unit = id ? state.units[id] : null;
        map.getCanvas().style.cursor = unit && unit.inContext ? "pointer" : "";
        if (!feature) {
          state.tooltip.hidden = true;
          return;
        }
        var text = state.config.text;
        state.tooltip.firstChild.textContent = feature.properties.name;
        state.tooltip.lastChild.textContent = !unit || !unit.inContext ? text.outside : unit.value === null ? text.none : text.tooltip.replace("{value}", LDT.number(unit.value, 1, text.decimal));
        state.tooltip.style.left = event.point.x + 12 + "px";
        state.tooltip.style.top = event.point.y + 12 + "px";
        state.tooltip.hidden = false;
      });
      map.on("mouseout", function () {
        setHover(null);
        state.tooltip.hidden = true;
      });
      map.on("click", function (event) {
        var feature = featureAt(event);
        var id = feature ? feature.properties.id : null;
        if (!id || !state.units[id] || !state.units[id].inContext) return;
        LDT.setParam("selected", id === state.config.selected ? null : id, { replace: true });
      });
      map.on("dblclick", function (event) {
        var feature = featureAt(event);
        var id = feature ? feature.properties.id : null;
        if (id && state.units[id] && state.units[id].inContext) LDT.navigate(state.config.openHref.replace("__ID__", id), { replace: false });
      });
      new ResizeObserver(function () { map.resize(); }).observe(state.canvas);
    }).catch(function () {
      setOverlay(state, config.text.error);
    });
  }

  LDT.widgets.map = function (node, config) {
    var state = node.__map;
    if (!state || state.iso3 !== config.iso3 || !node.contains(state.canvas)) {
      if (state && state.map) state.map.remove();
      state = node.__map = build(node);
      state.iso3 = config.iso3;
      state.config = config;
      state.units = unitIndex(config);
      state.controls.querySelectorAll(".map-btn").forEach(function (b) {
        var label = config.text[b.getAttribute("data-label")];
        b.setAttribute("aria-label", label);
        b.setAttribute("title", label);
      });
      create(state);
      return;
    }
    state.config = config;
    state.units = unitIndex(config);
    if (!state.ready) return;
    applyState(state);
    var key = contextKey(config);
    if (key !== state.fitKey) {
      state.fitKey = key;
      fit(state, true);
    }
  };
})();
