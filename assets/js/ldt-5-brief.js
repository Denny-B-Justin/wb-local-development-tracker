(function () {
  "use strict";

  var LDT = window.LDT;
  var OUTPUTS = ["narrative", "alignment", "swot", "recommendations"];
  var ORDER = ["indicator_narrative", "national_plan_context", "province_plan_context", "web_context_search", "plan_alignment", "swot_analysis", "investment_recommendations"];
  var DOCUMENTS = ["national_plan_context", "province_plan_context"];

  function expand(outputs, localPlan) {
    var set = {};
    outputs.forEach(function (o) { set[o] = true; });
    if (set.recommendations) set.swot = true;
    if (set.swot) { set.alignment = true; set.narrative = true; }
    if (!localPlan) { delete set.alignment; delete set.swot; delete set.recommendations; }
    return OUTPUTS.filter(function (o) { return set[o]; });
  }

  function planStages(outputs, web, localPlan) {
    var expanded = expand(outputs, localPlan);
    var stages = {};
    if (expanded.indexOf("narrative") >= 0) stages.indicator_narrative = true;
    if (expanded.indexOf("alignment") >= 0) { stages.national_plan_context = true; stages.province_plan_context = true; stages.plan_alignment = true; }
    if (expanded.indexOf("swot") >= 0) stages.swot_analysis = true;
    if (expanded.indexOf("recommendations") >= 0) stages.investment_recommendations = true;
    if (web && Object.keys(stages).length) stages.web_context_search = true;
    return ORDER.filter(function (s) { return stages[s]; });
  }

  function setRun(data) {
    if (window.dash_clientside && window.dash_clientside.set_props) window.dash_clientside.set_props("brief-run", { data: data });
  }

  function post(path, body) {
    return fetch(path, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (json) {
        if (!response.ok) throw new Error(json.error || "Request failed (" + response.status + ")");
        return json;
      });
    });
  }

  LDT.widgets.brief = function (node, config) {
    var state = { outputs: OUTPUTS.slice(), web: config.web, running: null, nonce: 0 };
    node.__brief = state;
    var setup = node.querySelector(".brief-setup");
    var button = node.querySelector(".js-generate");
    var text = config.text;

    function cached() {
      var holder = node.querySelector("[data-cached]");
      try { return holder ? JSON.parse(holder.getAttribute("data-cached")) : []; } catch (e) { return []; }
    }

    function setCheck(row, checked, disabled, hint) {
      if (!row) return;
      row.setAttribute("aria-checked", String(checked));
      row.setAttribute("aria-disabled", String(disabled));
      row.classList.toggle("is-disabled", disabled);
      row.tabIndex = disabled ? -1 : 0;
      var box = row.querySelector(".check-box");
      box.classList.toggle("is-checked", checked);
      box.classList.toggle("is-disabled", disabled);
      var hintNode = row.querySelector(".check-hint");
      if (hint === undefined) return;
      if (!hint && hintNode) hintNode.remove();
      if (hint) {
        if (!hintNode) { hintNode = LDT.el("span", { className: "check-hint" }); row.querySelector(".check-label").parentNode.appendChild(hintNode); }
        hintNode.textContent = hint;
      }
    }

    function refresh() {
      var effective = expand(state.outputs, config.localPlan);
      OUTPUTS.forEach(function (o) {
        var row = setup.querySelector('[data-key="output:' + o + '"]');
        var needsPlan = o !== "narrative" && !config.localPlan;
        var implied = effective.indexOf(o) >= 0 && state.outputs.indexOf(o) < 0;
        setCheck(row, effective.indexOf(o) >= 0, needsPlan || implied || Boolean(state.running), needsPlan ? text.needsPlan : implied ? text.implied : null);
      });
      setCheck(setup.querySelector('[data-key="evidence:local"]'), config.localPlan && effective.indexOf("alignment") >= 0, true);
      setCheck(setup.querySelector('[data-key="evidence:national"]'), effective.indexOf("alignment") >= 0, true);
      var web = setup.querySelector('[data-key="web"]');
      if (web && config.web) setCheck(web, state.web, Boolean(state.running));
      var stages = planStages(state.outputs, state.web, config.localPlan);
      var done = cached();
      var complete = stages.length > 0 && stages.every(function (s) { return done.indexOf(s) >= 0; });
      var blocked = config.blocked || (stages.length ? null : text.noOutputs);
      button.disabled = Boolean(blocked) || Boolean(state.running);
      button.classList.toggle("is-running", Boolean(state.running));
      button.classList.toggle("is-complete", complete && !state.running);
      button.querySelector(".gen-label").textContent = state.running ? text.generating : complete ? text.regenerate : text.generate;
      var blockedNode = setup.querySelector(".js-blocked");
      blockedNode.hidden = !blocked;
      blockedNode.textContent = blocked || "";
      setup.querySelector(".js-regen-note").hidden = !(complete && !blocked);
      state.stages = stages;
      state.complete = complete;
    }

    if (!node.__briefBound) {
      node.__briefBound = true;
      var toggle = function (row) {
        var current = node.__brief;
        if (!row || row.getAttribute("aria-disabled") === "true" || current.running) return;
        var key = row.getAttribute("data-key");
        if (key === "web") current.web = !current.web;
        else if (key && key.indexOf("output:") === 0) {
          var name = key.slice(7);
          var at = current.outputs.indexOf(name);
          if (at >= 0) current.outputs.splice(at, 1);
          else current.outputs.push(name);
        }
        current.refresh();
      };
      node.addEventListener("click", function (event) {
        var row = event.target.closest(".check-row[data-key]");
        if (row) { event.preventDefault(); toggle(row); }
        if (event.target.closest(".js-generate")) node.__brief.generate();
      });
      node.addEventListener("keydown", function (event) {
        var row = event.target.closest && event.target.closest(".check-row[data-key]");
        if (row && (event.key === " " || event.key === "Enter")) { event.preventDefault(); toggle(row); }
      });
      new MutationObserver(function () { if (node.__brief) node.__brief.refresh(); }).observe(node, { subtree: true, attributes: true, attributeFilter: ["data-cached"] });
    }

    state.refresh = refresh;
    state.generate = function () {
      if (state.running || button.disabled) return;
      var stages = state.stages.slice();
      var regenerate = state.complete;
      var errors = {};
      var search = window.location.search;
      var step = function (index) {
        if (index >= stages.length || node.__brief !== state) {
          state.running = null;
          setRun({ planned: stages, running: null, errors: errors, nonce: ++state.nonce });
          refresh();
          return;
        }
        var stage = stages[index];
        state.running = stage;
        setRun({ planned: stages, running: stage, errors: errors, nonce: ++state.nonce });
        refresh();
        var mode = regenerate && DOCUMENTS.indexOf(stage) < 0 ? "regenerate" : "generate";
        post("api/brief/stage", { search: search, stage: stage, mode: mode }).then(function (result) {
          if (result.status !== "completed") {
            errors[stage] = result.errorMessage || "";
            if (stage !== "web_context_search") index = stages.length - 1;
          }
          step(index + 1);
        }, function (error) {
          errors[stage] = String(error.message || error);
          step(stages.length);
        });
      };
      step(0);
    };
    refresh();
    if (config.scope && config.scope.charAt(0) !== ":") {
      post("api/brief/load", { search: window.location.search }).then(function (result) {
        if (result && result.arrived) setRun({ planned: [], running: null, errors: {}, nonce: ++state.nonce });
      }, function () {});
    }
  };
})();
