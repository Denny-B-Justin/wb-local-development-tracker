(function () {
  "use strict";

  var LDT = window.LDT;
  var el = LDT.el;
  var svg = LDT.svg;

  var W = 1440, H = 900, PX = 590, PW = W - 44 - PX;
  var c = function (name) { return "var(--color-" + name + ")"; };
  var INK = c("ink"), INK2 = c("ink-2"), MUTED = c("ink-muted"), LINE = c("border"), SOFT = c("nav-hover");
  var ACC = c("indigo-600"), ACC_SOFT = c("indigo-tint"), TEAL = c("teal-600"), TEAL_SOFT = c("teal-tint");
  var RAMP = ["ramp-1", "ramp-2", "ramp-3", "ramp-4", "ramp-5"].map(c);
  var LABEL = "font-size:14px;color:" + MUTED + ";letter-spacing:1.2px;text-transform:uppercase;font-weight:600";

  var SCENES = [["Explore", 2.5, 3], ["Open", 3.6, 4.5], ["Compare", 4.5, 5.5], ["Brief", 5, 6], ["Reset", 1.6, 2]];
  var LOOP = SCENES.reduce(function (s, x) { return s + x[1]; }, 0);
  var CUES = {};
  (function () { var at = 0; SCENES.forEach(function (s) { CUES[s[0]] = at; at += s[2]; }); })();
  function authored(real) {
    var rs = 0, ns = 0;
    for (var i = 0; i < SCENES.length; i++) {
      var s = SCENES[i];
      if (real < rs + s[1]) return ns + ((real - rs) * s[2]) / s[1];
      rs += s[1]; ns += s[2];
    }
    return ns;
  }
  var STILL_T = CUES.Compare + 3.4;

  var easeOutCubic = function (t) { return Math.pow(t - 1, 3) + 1; };
  var easeInOutCubic = function (t) { return t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1; };
  var easeOutBack = function (t) { return 1 + 2.70158 * Math.pow(t - 1, 3) + 1.70158 * Math.pow(t - 1, 2); };
  function tween(ease) {
    return function (from, to, start, end, T) { return T <= start ? from : T >= end ? to : from + (to - from) * ease((T - start) / (end - start)); };
  }
  var enter = tween(easeOutCubic), move = tween(easeInOutCubic), pop = tween(easeOutBack);
  function track(keys, T) {
    if (T <= keys[0][0]) return keys[0][1];
    for (var i = 0; i < keys.length - 1; i++) {
      var k0 = keys[i], k1 = keys[i + 1];
      if (T <= k1[0]) return [move(k0[1][0], k1[1][0], k0[0], k1[0], T), move(k0[1][1], k1[1][1], k0[0], k1[0], T)];
    }
    return keys[keys.length - 1][1];
  }
  function track1(keys, T) { return track(keys.map(function (k) { return [k[0], [k[1], 0]]; }), T)[0]; }

  var R = 20, HW = Math.sqrt(3) * R, COLS = 26, ROWS = 20, PAD = 4;
  var MAP_W = PAD * 2 + COLS * HW + HW / 2, MAP_H = PAD * 2 + (ROWS - 1) * 1.5 * R + 2 * R;
  var A_CELL = [14, 9], B_CELL = [15, 9];
  function hash(col, row) { var s = Math.sin(col * 127.1 + row * 311.7) * 43758.5453; return s - Math.floor(s); }
  function hexCenter(cell) { return [PAD + cell[0] * HW + (cell[1] % 2 ? HW / 2 : 0) + HW / 2, PAD + cell[1] * 1.5 * R + R]; }
  var HEX = [0, 1, 2, 3, 4, 5].map(function (i) { var a = (Math.PI / 180) * (60 * i - 90); return [Math.cos(a) * (R - 0.6), Math.sin(a) * (R - 0.6)]; });
  function hexPath(center) { return "M" + HEX.map(function (p) { return (center[0] + p[0]).toFixed(1) + "," + (center[1] + p[1]).toFixed(1); }).join("L") + "Z"; }
  var CELLS = [];
  for (var row = 0; row < ROWS; row++) {
    for (var col = 0; col < COLS; col++) {
      var ctr = hexCenter([col, row]);
      var nx = (ctr[0] - MAP_W / 2) / (MAP_W / 2), ny = (ctr[1] - MAP_H / 2) / (MAP_H / 2), th = Math.atan2(ny, nx);
      var lim = 0.84 + 0.1 * Math.sin(3 * th + 1) + 0.06 * Math.sin(5 * th + 2) + 0.04 * Math.cos(7 * th) + (hash(col, row) - 0.5) * 0.08;
      if (Math.hypot(nx, ny) > lim) continue;
      var score = 52 + 20 * Math.sin(col * 0.33 + 1) * Math.cos(row * 0.29) + 12 * Math.sin((col + row) * 0.21) + (hash(row, col) - 0.5) * 22;
      if (col === A_CELL[0] && row === A_CELL[1]) score = 68;
      if (col === B_CELL[0] && row === B_CELL[1]) score = 54;
      score = Math.max(8, Math.min(96, score));
      CELLS.push({ d: hexPath(ctr), fill: RAMP[Math.min(4, Math.floor(score / 20))] });
    }
  }
  var A_LOC = hexCenter(A_CELL), B_LOC = hexCenter(B_CELL);
  var FULL = { s: 0.95, x: (W - MAP_W * 0.95) / 2, y: 64 + (H - 64 - MAP_H * 0.95) / 2 + 6 };
  var DOCK = { s: 0.56, x: 44, y: 196 };
  function toStage(loc, m) { return [m.x + loc[0] * m.s, m.y + loc[1] * m.s]; }
  var A_FULL = toStage(A_LOC, FULL), B_DOCK = toStage(B_LOC, DOCK);
  var BTN = { x: W - 44 - 166, y: 104, w: 166, h: 46 }, BTN_C = [BTN.x + BTN.w / 2, BTN.y + BTN.h / 2];
  var GEN = { x: W - 44 - 166 - 12 - 186, y: 104, w: 186, h: 46 }, GEN_C = [GEN.x + GEN.w / 2, GEN.y + GEN.h / 2];
  var DATA = { A: { name: "Valmora", overall: 68, pillars: [74, 61, 69], trend: [59, 61, 64, 66, 68] }, B: { name: "Brenik", overall: 54, pillars: [49, 63, 50] } };
  var PILLARS = ["Prosperity", "Infrastructure", "Livability"];
  var SWOT = [
    ["Strengths", ACC, ACC_SOFT, ["Strong prosperity score (74)", "Score up every year since 2021"]],
    ["Weaknesses", c("warning"), c("warning-bg"), ["Infrastructure trails Brenik (61 vs 63)", "Below regional infrastructure average"]],
    ["Opportunities", TEAL, TEAL_SOFT, ["Shared infrastructure with Brenik", "Growing SME base to build on"]],
    ["Threats", c("amber-800"), c("amber-tint"), ["Rising demand on health & schools", "Uneven growth across the region"]],
  ];
  var INVEST = [["Road & water network upgrades", "Infrastructure", "High"], ["Joint transport link with Brenik", "Infrastructure", "Medium"], ["Public spaces & housing renewal", "Livability", "Medium"]];

  function box(css, children, text) {
    var node = el("div", {}, children || []);
    node.style.cssText = css;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function set(node, styles) { for (var k in styles) node.style[k] = styles[k]; }

  function buildArtboard() {
    var art = box("position:absolute;left:0;top:0;width:" + W + "px;height:" + H + "px;background:#fff;font-family:var(--font-display);overflow:hidden");
    var years = box("display:flex;gap:4px;background:" + SOFT + ";border-radius:8px;padding:4px", ["2021", "2022", "2023", "2024", "2025"].map(function (y) {
      return box("font-size:14px;padding:6px 12px;border-radius:6px;font-weight:500;color:" + (y === "2025" ? "#fff" : INK2) + ";background:" + (y === "2025" ? c("navy-800") : "transparent"), [], y);
    }));
    var mark = el("img", { src: "assets/img/brand/ldt-mark.png", alt: "", width: 28, height: 28 });
    var crumbs = box("font-size:16px;color:" + MUTED, [document.createTextNode("Workspaces / "), box("display:inline;color:" + INK2, [], "Country workspace")]);
    art.appendChild(box("position:absolute;left:0;top:0;width:" + W + "px;height:64px;border-bottom:1px solid " + LINE + ";display:flex;align-items:center;gap:28px;padding:0 44px;box-sizing:border-box", [
      box("display:flex;align-items:center;gap:10px", [mark, box("font-weight:700;font-size:22px;color:" + INK + ";letter-spacing:.3px", [], "LDT")]), crumbs, box("flex:1"), years,
    ]));

    var refs = {};
    refs.mapTitle = box("position:absolute;left:44px;top:96px", [box(LABEL + ";font-size:15px", [], "PIL Composite · 2025"), box("font-size:30px;color:" + INK + ";font-weight:700;margin-top:6px", [], "1,083 local governments")]);
    refs.legend = box("position:absolute;left:44px;bottom:44px;display:flex;flex-direction:column;gap:8px", [
      box("display:flex;gap:2px", RAMP.map(function (f) { return box("width:44px;height:12px;background:" + f); })),
      box("display:flex;justify-content:space-between;width:228px;font-size:13px;color:" + MUTED, [box("", [], "0"), box("", [], "50"), box("", [], "100")]),
    ]);
    refs.dockTitle = box("position:absolute;left:" + DOCK.x + "px;top:120px", [box(LABEL, [], "Northern Region"), box("font-size:22px;color:" + INK + ";font-weight:600;margin-top:4px", [], "Neighbouring areas")]);
    var stage = svg("svg", { width: W, height: H, style: "position:absolute;left:0;top:0;overflow:visible" });
    refs.group = svg("g", {});
    CELLS.forEach(function (cell) { refs.group.appendChild(svg("path", { d: cell.d, fill: cell.fill, stroke: "#fff", "stroke-width": 1.5 })); });
    refs.aOutline = svg("path", { d: hexPath(A_LOC), fill: "none", stroke: INK });
    refs.bCand = svg("path", { d: hexPath(B_LOC), fill: "none", stroke: TEAL, "stroke-width": 4 });
    refs.bSel = svg("path", { d: hexPath(B_LOC), fill: "none", stroke: TEAL, "stroke-width": 5 });
    refs.group.appendChild(refs.aOutline); refs.group.appendChild(refs.bCand); refs.group.appendChild(refs.bSel);
    stage.appendChild(refs.group);
    refs.tip = box("position:absolute;background:#fff;border:1px solid " + LINE + ";border-radius:10px;box-shadow:0 10px 30px rgba(20,26,51,.14);padding:12px 16px;display:flex;flex-direction:column;gap:4px;min-width:170px", [
      box("font-size:17px;font-weight:600;color:" + INK, [], DATA.A.name),
      box("display:flex;align-items:baseline;gap:6px", [box("font-size:26px;font-weight:700;color:" + ACC, [], "68"), box("font-size:14px;color:" + MUTED, [], "PIL Composite")]),
    ]);
    refs.hint = box("position:absolute;left:" + DOCK.x + "px;top:" + (DOCK.y + MAP_H * DOCK.s + 20) + "px;display:flex;align-items:center;gap:10px;background:" + TEAL_SOFT + ";color:" + c("teal-800") + ";border-radius:8px;padding:10px 14px;font-size:16px;font-weight:500", [
      box("width:10px;height:10px;border-radius:5px;background:" + TEAL), document.createTextNode("Select an area to compare"),
    ]);
    [refs.mapTitle, refs.legend, refs.dockTitle].forEach(function (n) { art.appendChild(n); });
    art.appendChild(stage);
    art.appendChild(refs.tip);
    art.appendChild(refs.hint);

    var score = function (label, color) {
      var value = box("font-size:96px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums;color:" + color, [], "0");
      return { node: box("", [box(LABEL, [], label), box("display:flex;align-items:baseline;gap:8px;margin-top:4px", [value, box("font-size:20px;color:" + MUTED, [], "/ 100")])]), value: value };
    };
    refs.aScore = score("PIL Composite", ACC);
    refs.bScore = score(DATA.B.name, TEAL);
    refs.bScoreWrap = box("position:absolute;left:480px;top:0", [refs.bScore.node]);
    var sw = PW - 480 - 16, sh = 90;
    var pts = DATA.A.trend.map(function (v, i) { return [(i / 4) * sw, sh - ((v - 55) / 15) * sh]; });
    var spark = svg("svg", { width: sw + 12, height: sh + 34, style: "margin-top:14px;overflow:visible" });
    refs.sparkPath = svg("path", { d: "M" + pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join("L"), fill: "none", stroke: ACC, "stroke-width": 3.5, "stroke-linecap": "round", "stroke-linejoin": "round", "stroke-dasharray": 400 });
    spark.appendChild(refs.sparkPath);
    refs.sparkDots = pts.map(function (p) { var dot = svg("circle", { cx: p[0], cy: p[1], r: 5, fill: "#fff", stroke: ACC, "stroke-width": 2.5 }); spark.appendChild(dot); return dot; });
    ["2021", "2025"].forEach(function (y, i) {
      var t = svg("text", { x: i ? sw : 0, y: sh + 30, "text-anchor": i ? "end" : "start", "font-size": 13, fill: MUTED, "font-family": "var(--font-display)" });
      t.textContent = y;
      spark.appendChild(t);
    });
    refs.spark = box("position:absolute;left:480px;top:0", [box(LABEL, [], "Trend 2021–2025"), spark]);
    var bar = function (color) {
      var fill = box("height:100%;border-radius:7px;background:" + color + ";width:0");
      return { node: box("height:14px;background:" + SOFT + ";border-radius:7px;overflow:hidden;width:100%", [fill]), fill: fill };
    };
    refs.rows = PILLARS.map(function (name) {
      var a = bar(ACC), b = bar(TEAL);
      var av = box("font-size:22px;font-weight:700;color:" + ACC + ";text-align:right;font-variant-numeric:tabular-nums", [], "0");
      var bv = box("font-size:22px;font-weight:700;color:" + TEAL + ";text-align:right;font-variant-numeric:tabular-nums", [], "0");
      var bWrap = box("", [b.node]);
      return { node: box("display:grid;grid-template-columns:160px minmax(0,1fr) 56px;column-gap:24px;row-gap:8px;align-items:center", [box("font-size:20px;color:" + INK + ";font-weight:500", [], name), a.node, av, box(""), bWrap, bv]), a: a, b: b, av: av, bv: bv, bWrap: bWrap };
    });
    refs.vs = box("display:flex;align-items:center;gap:14px", [box("font-size:22px;color:" + MUTED + ";font-weight:500", [], "vs"), box("font-size:44px;font-weight:700;color:" + TEAL, [], DATA.B.name)]);
    refs.compareBtnIcon = box("font-size:20px;line-height:20px", [], "+");
    refs.compareBtnText = document.createTextNode("Compare");
    refs.compareBtn = box("position:absolute;left:" + (BTN.x - PX) + "px;top:" + (BTN.y - 96) + "px;width:" + BTN.w + "px;height:" + BTN.h + "px;border-radius:10px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;gap:8px;font-size:17px;font-weight:600", [refs.compareBtnIcon, refs.compareBtnText]);
    refs.genSpin = box("width:16px;height:16px;border-radius:8px;border:2.5px solid rgba(255,255,255,.35);border-top-color:#fff;box-sizing:border-box");
    refs.genIcon = box("font-size:18px;line-height:18px", [], "✦");
    refs.genText = document.createTextNode("Generate brief");
    refs.genBtn = box("position:absolute;left:" + (GEN.x - PX) + "px;top:" + (GEN.y - 96) + "px;width:" + GEN.w + "px;height:" + GEN.h + "px;border-radius:10px;background:" + ACC + ";color:#fff;display:flex;align-items:center;justify-content:center;gap:10px;font-size:17px;font-weight:600;box-shadow:0 6px 16px rgba(67,67,168,.28)", [refs.genSpin, refs.genIcon, refs.genText]);
    refs.detail = box("position:absolute;left:" + PX + "px;top:96px;width:" + PW + "px;height:660px", [
      box("display:flex;align-items:center;gap:16px;height:62px", [box("font-size:44px;font-weight:700;color:" + INK, [], DATA.A.name), refs.vs]),
      box("font-size:17px;color:" + INK2 + ";margin-top:4px", [], "Municipality · Northern Region"),
      refs.compareBtn, refs.genBtn,
      box("position:absolute;left:0;top:150px;width:" + PW + "px", [refs.aScore.node, refs.spark, refs.bScoreWrap]),
      box("position:absolute;left:0;top:330px;width:" + PW + "px;border-top:1px solid " + LINE + ";padding-top:28px;display:flex;flex-direction:column;gap:30px", refs.rows.map(function (r) { return r.node; })),
    ]);
    art.appendChild(refs.detail);

    refs.skel = box("position:absolute;left:30px;top:84px;right:30px;display:flex;flex-direction:column;gap:14px", [100, 92, 70, 0, 48, 86, 80].map(function (w) {
      return box("height:" + (w ? 14 : 10) + "px;width:" + w + "%;border-radius:7px;background:" + SOFT);
    }));
    var fade = [];
    var at = function (node, t0) { fade.push([node, t0]); return node; };
    var summary = at(box("display:flex;flex-direction:column;gap:8px", [box(LABEL, [], "Summary"), box("font-size:18px;line-height:1.45;color:" + INK2)]), 1.9);
    summary.lastChild.innerHTML = 'Valmora leads Brenik on <b style="color:var(--color-ink)">Prosperity (+25)</b> and <b style="color:var(--color-ink)">Livability (+19)</b> but trails slightly on Infrastructure. Its PIL Composite has risen every year since 2021.';
    var swot = box("display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px", SWOT.map(function (q, i) {
      return at(box("background:" + q[2] + ";border-radius:10px;padding:12px 16px;display:flex;flex-direction:column;gap:6px", [box("font-size:15px;font-weight:700;letter-spacing:.4px;color:" + q[1], [], q[0])].concat(q[3].map(function (item) {
        return box("font-size:16px;color:" + INK + ";line-height:1.3", [], item);
      }))), 2.5 + i * 0.25);
    }));
    var invest = box("display:flex;flex-direction:column;gap:8px", [at(box(LABEL, [], "Recommended investment"), 3.6)].concat(INVEST.map(function (r, i) {
      var high = r[2] === "High";
      return at(box("display:grid;grid-template-columns:28px minmax(0,1fr) auto auto;align-items:center;column-gap:14px;padding:8px 0;border-top:1px solid " + LINE, [
        box("font-size:16px;font-weight:700;color:" + MUTED, [], String(i + 1)), box("font-size:17px;font-weight:500;color:" + INK, [], r[0]),
        box("font-size:14px;color:" + INK2 + ";background:" + SOFT + ";border-radius:6px;padding:4px 10px", [], r[1]),
        box("font-size:14px;font-weight:600;border-radius:6px;padding:4px 10px;min-width:58px;text-align:center;color:" + (high ? "#fff" : ACC) + ";background:" + (high ? ACC : ACC_SOFT), [], r[2]),
      ]), 3.8 + i * 0.22);
    })));
    refs.fade = fade;
    refs.brief = box("position:absolute;left:" + PX + "px;top:196px;width:" + PW + "px;height:" + (H - 32 - 196) + "px;box-sizing:border-box;background:#fff;border:1px solid " + LINE + ";border-radius:14px;box-shadow:0 24px 60px rgba(20,26,51,.16);padding:26px 30px;display:flex;flex-direction:column;gap:20px", [
      box("display:flex;align-items:baseline;justify-content:space-between", [box("font-size:24px;font-weight:700;color:" + INK, [], "Investment brief"), box("font-size:14px;color:" + MUTED, [], "Valmora vs Brenik · 2025 data")]),
      refs.skel, summary, swot, invest,
    ]);
    art.appendChild(refs.brief);

    refs.cursor = box("position:absolute;pointer-events:none");
    refs.ring = box("position:absolute;left:-28px;top:-28px;width:56px;height:56px;border-radius:28px;border:3px solid " + ACC + ";box-sizing:border-box");
    var arrow = svg("svg", { width: 30, height: 36, viewBox: "0 0 30 36", style: "position:absolute;left:-3px;top:-2px;transform-origin:3px 2px;filter:drop-shadow(0 3px 6px rgba(20,26,51,.3))" });
    arrow.appendChild(svg("path", { d: "M3 2 L3 28 L10 21.5 L14.5 32 L19 30 L14.5 19.8 L24 19.8 Z", fill: "var(--color-ink)", stroke: "#fff", "stroke-width": 2, "stroke-linejoin": "round" }));
    refs.arrow = arrow;
    refs.cursor.appendChild(refs.ring);
    refs.cursor.appendChild(arrow);
    art.appendChild(refs.cursor);
    return { art: art, refs: refs };
  }

  function update(refs, T) {
    var O = CUES.Open, C = CUES.Compare, Bf = CUES.Brief, Rs = CUES.Reset;
    var dock = track1([[O + 0.15, 0], [O + 1.15, 1], [Rs + 0.3, 1], [Rs + 1.4, 0]], T);
    var m = { s: FULL.s + (DOCK.s - FULL.s) * dock, x: FULL.x + (DOCK.x - FULL.x) * dock, y: FULL.y + (DOCK.y - FULL.y) * dock };
    var fadeSel = enter(1, 0, Rs, Rs + 0.6, T);
    var aHover = enter(0, 1, 2.0, 2.3, T), aSel = pop(0, 1, 2.75, 3.05, T) * fadeSel;
    var bCand = enter(0, 1, C + 0.7, C + 1.0, T) * enter(1, 0, C + 1.75, C + 1.9, T);
    var pulse = 0.5 + 0.5 * Math.sin(T * 9), bSel = pop(0, 1, C + 1.75, C + 2.05, T) * fadeSel;
    refs.mapTitle.style.opacity = 1 - dock;
    refs.legend.style.opacity = 1 - dock;
    refs.dockTitle.style.opacity = dock;
    refs.group.setAttribute("transform", "translate(" + m.x + "," + m.y + ") scale(" + m.s + ")");
    refs.aOutline.setAttribute("stroke-width", 3 / Math.max(m.s, 0.6));
    refs.aOutline.setAttribute("opacity", Math.max(aHover * (1 - aSel) * 0.6 * fadeSel, aSel));
    refs.aOutline.setAttribute("transform", "translate(" + A_LOC[0] + "," + A_LOC[1] + ") scale(" + (1 + 0.12 * aSel) + ") translate(" + -A_LOC[0] + "," + -A_LOC[1] + ")");
    refs.bCand.setAttribute("opacity", bCand * (0.45 + 0.55 * pulse));
    refs.bSel.setAttribute("opacity", bSel);
    refs.bSel.setAttribute("transform", "translate(" + B_LOC[0] + "," + B_LOC[1] + ") scale(" + (1 + 0.12 * bSel) + ") translate(" + -B_LOC[0] + "," + -B_LOC[1] + ")");
    set(refs.tip, { left: A_FULL[0] + 26 + "px", top: A_FULL[1] - 92 + enter(8, 0, 2.2, 2.5, T) + "px", opacity: enter(0, 1, 2.2, 2.5, T) * enter(1, 0, O + 0.05, O + 0.3, T) });
    refs.hint.style.opacity = enter(0, 1, C + 0.6, C + 0.9, T) * enter(1, 0, C + 1.8, C + 2.1, T);

    var out = enter(1, 0, Rs, Rs + 0.5, T);
    set(refs.detail, { opacity: enter(0, 1, O + 0.5, O + 1.2, T) * out, transform: "translateX(" + enter(60, 0, O + 0.5, O + 1.2, T) + "px)" });
    refs.aScore.value.textContent = String(Math.round(enter(0, DATA.A.overall, O + 0.9, O + 2.0, T)));
    var press = enter(0, 1, C + 0.45, C + 0.55, T) * enter(1, 0, C + 0.6, C + 0.75, T);
    var on = enter(0, 1, C + 0.55, C + 0.75, T) * out > 0.5;
    set(refs.compareBtn, { border: "1.5px solid " + (on ? INK : LINE), background: on ? INK : "#fff", color: on ? "#fff" : INK, transform: "scale(" + (1 - 0.06 * press) + ")" });
    refs.compareBtnIcon.textContent = on ? "✓" : "+";
    refs.compareBtnText.nodeValue = on ? "Comparing" : "Compare";
    var bIn = enter(0, 1, C + 1.95, C + 2.5, T);
    set(refs.vs, { opacity: bIn, transform: "translateX(" + (1 - bIn) * 16 + "px)" });
    set(refs.bScoreWrap, { opacity: bIn, transform: "translateY(" + (1 - bIn) * 12 + "px)" });
    refs.bScore.value.textContent = String(Math.round(enter(0, DATA.B.overall, C + 2.1, C + 3.0, T)));
    refs.spark.style.opacity = enter(1, 0, C + 1.8, C + 2.1, T);
    var draw = move(0, 1, O + 1.9, O + 3.0, T);
    refs.sparkPath.setAttribute("stroke-dashoffset", 400 * (1 - draw));
    refs.sparkDots.forEach(function (dot, i) { dot.setAttribute("opacity", draw >= i / 4 ? 1 : 0); });
    refs.rows.forEach(function (r, i) {
      var g = enter(0, 1, O + 1.2 + i * 0.18, O + 2.1 + i * 0.18, T), gb = enter(0, 1, C + 2.3 + i * 0.18, C + 3.2 + i * 0.18, T), showB = Math.min(1, gb * 4);
      r.a.fill.style.width = DATA.A.pillars[i] * g + "%";
      r.av.textContent = String(Math.round(DATA.A.pillars[i] * g));
      r.b.fill.style.width = DATA.B.pillars[i] * gb + "%";
      r.bv.textContent = String(Math.round(DATA.B.pillars[i] * gb));
      r.bWrap.style.opacity = showB;
      r.bv.style.opacity = showB;
    });
    var gpress = enter(0, 1, Bf + 0.75, Bf + 0.85, T) * enter(1, 0, Bf + 0.9, Bf + 1.05, T);
    var loading = T > Bf + 0.85 && T < Bf + 1.9, done = T >= Bf + 1.9 && out > 0.5;
    set(refs.genBtn, { opacity: enter(0, 1, C + 3.0, C + 3.5, T), transform: "scale(" + (1 - 0.06 * gpress) + ")" });
    refs.genSpin.style.display = loading ? "block" : "none";
    refs.genSpin.style.transform = "rotate(" + T * 720 + "deg)";
    refs.genIcon.style.display = loading ? "none" : "block";
    refs.genIcon.textContent = done ? "✓" : "✦";
    refs.genText.nodeValue = loading ? "Generating…" : done ? "Brief ready" : "Generate brief";

    var inO = enter(0, 1, Bf + 0.85, Bf + 1.25, T) * out;
    refs.brief.style.display = inO <= 0 ? "none" : "flex";
    if (inO > 0) {
      set(refs.brief, { opacity: inO, transform: "translateY(" + enter(30, 0, Bf + 0.85, Bf + 1.25, T) + "px)" });
      refs.skel.style.opacity = enter(1, 0, Bf + 1.7, Bf + 1.95, T);
      Array.prototype.forEach.call(refs.skel.children, function (bar, i) { bar.style.opacity = 0.6 + 0.4 * Math.sin(T * 6 - i * 0.6); });
      refs.fade.forEach(function (f) { var o = enter(0, 1, Bf + f[1], Bf + f[1] + 0.4, T); set(f[0], { opacity: o, transform: "translateY(" + (1 - o) * 10 + "px)" }); });
    }

    var pos = track([[0.6, [1200, 820]], [2.2, A_FULL], [O + 0.2, A_FULL], [O + 1.4, [980, 660]], [C - 0.4, [980, 660]], [C + 0.45, BTN_C], [C + 0.85, BTN_C], [C + 1.7, B_DOCK], [C + 2.0, B_DOCK],
      [C + 2.9, [1120, 740]], [Bf + 0.1, [1120, 740]], [Bf + 0.7, GEN_C], [Bf + 0.95, GEN_C], [Bf + 1.8, [1360, 840]], [Rs + 1.6, [1200, 820]]], T);
    var clicks = [2.85, C + 0.5, C + 1.85, Bf + 0.8];
    var pressed = clicks.some(function (a) { return T > a - 0.1 && T < a + 0.12; });
    var ring;
    clicks.forEach(function (a) { var k = (T - a) / 0.55; if (k > 0 && k < 1 && ring === undefined) ring = k; });
    set(refs.cursor, { left: pos[0] + "px", top: pos[1] + "px", opacity: enter(0, 1, 0.6, 1.0, T) * enter(1, 0, Rs + 0.4, Rs + 1.0, T) });
    refs.arrow.style.transform = "scale(" + (pressed ? 0.86 : 1) + ")";
    refs.ring.style.display = ring === undefined ? "none" : "block";
    if (ring !== undefined) set(refs.ring, { opacity: 1 - ring, transform: "scale(" + (0.3 + ring) + ")" });
  }

  LDT.widgets.hero = function (node) {
    var stage = node.querySelector(".hero-stage");
    var toggle = node.querySelector(".hero-toggle");
    if (!stage || stage.__hero) return;
    var built = buildArtboard();
    var holder = box("position:absolute;left:0;top:0;width:" + W + "px;height:" + H + "px;transform-origin:0 0");
    holder.appendChild(built.art);
    stage.appendChild(holder);
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var state = { elapsed: 0, last: null, raf: 0, paused: false, onScreen: false };
    stage.__hero = state;
    var fit = function () { holder.style.transform = "scale(" + stage.clientWidth / W + ")"; };
    new ResizeObserver(fit).observe(stage);
    fit();
    if (reduced) {
      update(built.refs, STILL_T);
      if (toggle) toggle.hidden = true;
      return;
    }
    update(built.refs, 0);
    var tick = function (now) {
      if (state.last !== null) state.elapsed = (state.elapsed + (now - state.last) / 1000) % LOOP;
      state.last = now;
      update(built.refs, authored(state.elapsed));
      state.raf = requestAnimationFrame(tick);
    };
    var start = function () { if (!state.raf && state.onScreen && !document.hidden && !state.paused && stage.isConnected) { state.last = null; state.raf = requestAnimationFrame(tick); } };
    var stop = function () { cancelAnimationFrame(state.raf); state.raf = 0; };
    new IntersectionObserver(function (entries) { state.onScreen = entries[0].isIntersecting; if (state.onScreen) start(); else stop(); }).observe(stage);
    document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });
    if (toggle) {
      toggle.addEventListener("click", function () {
        state.paused = !state.paused;
        toggle.setAttribute("aria-label", toggle.getAttribute(state.paused ? "data-play" : "data-pause"));
        toggle.firstChild.className = "i size-3-5 i-" + (state.paused ? "play" : "pause");
        if (state.paused) stop(); else start();
      });
    }
  };
})();
