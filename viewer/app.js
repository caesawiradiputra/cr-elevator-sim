// Elevator Algorithm Lab viewer.
// Runs the Python engine in the browser through Pyodide when it can, and
// falls back to the precomputed demo runs embedded at build time.
(function () {
  "use strict";
  const DATA = window.ELEVSIM || { sources: {}, presets: [], demo: null, strategies: [], metrics: {} };
  const $ = (id) => document.getElementById(id);
  const CFG_FIELDS = ["floors", "elevators", "capacity", "passengers", "arrival_rate", "seed", "traffic",
    "idle_parking", "floor_travel_time", "door_time", "board_time", "lobby_floor"];
  const NUMERIC = new Set(CFG_FIELDS.filter((f) => !["traffic", "idle_parking"].includes(f)));
  const DEFAULTS = Object.assign({
    floors: 10, elevators: 3, capacity: 8, passengers: 200, arrival_rate: 20, seed: 1, traffic: "uniform",
    idle_parking: "stay", floor_travel_time: 1.5, door_time: 2, board_time: 1, lobby_floor: 0,
  }, DATA.defaults || {});

  let py = null;            // Pyodide functions once loaded
  let strategies = DATA.strategies || [];
  let result = null;        // current run: {strategy, config, summary, trace}
  let derived = null;       // precomputed arrays for the current run
  let playT = 0, playing = false, lastTs = 0;

  // ---------------------------------------------------------------- engine
  function setEngine(state, text) {
    $("engine-dot").className = "dot " + state;
    $("engine-text").textContent = text;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src; s.onload = resolve; s.onerror = () => reject(new Error("could not load " + src));
      document.head.appendChild(s);
    });
  }

  async function loadEngine() {
    if (!DATA.pyodideBase) throw new Error("no Pyodide location configured");
    const base = new URL(DATA.pyodideBase, location.href).href;
    await loadScript(base + "pyodide.js");
    const pyodide = await window.loadPyodide({ indexURL: base });
    const root = "/home/pyodide/";
    for (const [path, src] of Object.entries(DATA.sources)) {
      const parts = path.split("/");
      let dir = root;
      for (const p of parts.slice(0, -1)) { dir += p + "/"; try { pyodide.FS.mkdir(dir); } catch (e) { /* exists */ } }
      pyodide.FS.writeFile(root + path, src);
    }
    pyodide.runPython(`import sys\nsys.path.insert(0, "${root}")\nfrom elevsim.api import run_json, compare_json, strategies_json`);
    py = {
      run: pyodide.globals.get("run_json"),
      compare: pyodide.globals.get("compare_json"),
      strategies: pyodide.globals.get("strategies_json"),
    };
    strategies = JSON.parse(py.strategies());
  }

  // ----------------------------------------------------------------- config
  function fillForm(cfg) {
    for (const f of CFG_FIELDS) if (cfg[f] !== undefined && $(f)) $(f).value = cfg[f];
  }
  function readForm() {
    const cfg = {};
    for (const f of CFG_FIELDS) {
      const v = $(f).value;
      cfg[f] = NUMERIC.has(f) ? Number(v) : v;
    }
    return cfg;
  }
  function validate(cfg) {
    if (!(cfg.floors >= 2 && cfg.floors <= 40)) return "Floors must be between 2 and 40.";
    if (!(cfg.elevators >= 1 && cfg.elevators <= 8)) return "Elevators must be between 1 and 8.";
    if (!(cfg.capacity >= 1)) return "Car capacity must be at least 1.";
    if (!(cfg.passengers >= 1 && cfg.passengers <= 3000)) return "Passengers must be between 1 and 3000.";
    if (!(cfg.arrival_rate > 0)) return "Arrivals per minute must be above 0.";
    if (!(cfg.lobby_floor >= 0 && cfg.lobby_floor < cfg.floors)) return "Lobby floor must be one of the building's floors (0 is the bottom).";
    return null;
  }

  function populateSelectors() {
    const preset = $("preset");
    const keep = preset.value;
    preset.innerHTML = "";
    const custom = new Option("Custom", "");
    preset.add(custom);
    (DATA.presets || []).forEach((p, i) => preset.add(new Option(p.name, String(i))));
    preset.value = keep || "";
    const strat = $("strategy");
    strat.innerHTML = "";
    strategies.forEach((s) => strat.add(new Option(s.label, s.name)));
    if (strategies.some((s) => s.name === "eta")) strat.value = "eta";
    updateStrategyNote();
    const metric = $("metric");
    metric.innerHTML = "";
    for (const [k, m] of Object.entries(DATA.metrics)) metric.add(new Option(m.label, k));
    metric.value = "avg_journey";
  }
  function updateStrategyNote() {
    const s = strategies.find((x) => x.name === $("strategy").value);
    $("strategy-note").textContent = s ? s.description : "";
  }

  // ------------------------------------------------------------ simulation
  // Precomputed scenario matching the form, for when the engine is unavailable.
  function demoForForm() {
    const p = DATA.presets[Number($("preset").value)];
    if ($("preset").value === "" || !p || !DATA.demo) return null;
    return DATA.demo.scenarios[p.id] || null;
  }
  function selectPreset(id) {
    const i = (DATA.presets || []).findIndex((p) => p.id === id);
    if (i < 0) return;
    $("preset").value = String(i);
    fillForm(Object.assign({}, DEFAULTS, DATA.presets[i].config));
  }

  async function runSimulation() {
    if (!py) {
      const d = demoForForm();
      const res = d && d.runs[$("strategy").value];
      if (!res) { $("run-hint").textContent = "Pick one of the precomputed scenarios: custom settings need the Python engine."; return; }
      setResult(res); play();
      return;
    }
    const cfg = readForm();
    const err = validate(cfg);
    if (err) { $("run-hint").textContent = err; return; }
    $("run-hint").textContent = "";
    $("run-btn").disabled = true;
    showOverlay("Simulating…");
    setEngine("busy", "Running the Python engine…");
    await new Promise((r) => setTimeout(r, 30));
    try {
      const res = JSON.parse(py.run(JSON.stringify(cfg), $("strategy").value));
      setResult(res);
      setEngine("ok", "Python engine ready");
      play();
    } catch (e) {
      $("run-hint").textContent = "The simulation failed: " + String(e.message || e).split("\n").slice(-2).join(" ");
      setEngine("ok", "Python engine ready");
    } finally {
      hideOverlay();
      $("run-btn").disabled = false;
    }
  }

  function setResult(res) {
    result = res;
    const ps = res.trace.passengers;
    const frames = res.trace.frames;
    const end = frames[frames.length - 1][0];
    // waiting count over time for the sparkline
    const ev = [];
    for (const p of ps) { ev.push([p[0], 1]); ev.push([p[3] == null ? Infinity : p[3], -1]); }
    ev.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const N = 400, series = new Array(N).fill(0);
    let i = 0, cur = 0;
    for (let k = 0; k < N; k++) {
      const t = (end * k) / (N - 1);
      while (i < ev.length && ev[i][0] <= t) cur += ev[i++][1];
      series[k] = cur;
    }
    derived = { end, series, maxSeries: Math.max(1, ...series) };
    $("scrub").max = String(Math.round(end * 10));
    playT = 0;
    renderFinal();
    resizeCanvas();
    draw();
  }

  // ---------------------------------------------------------------- frames
  function frameAt(t) {
    const fr = result.trace.frames;
    const dt = result.trace.frame_interval;
    let k = Math.min(fr.length - 1, Math.max(0, Math.floor(t / dt)));
    while (k > 0 && fr[k][0] > t) k--;
    while (k < fr.length - 1 && fr[k + 1][0] <= t) k++;
    const a = fr[k], b = fr[Math.min(k + 1, fr.length - 1)];
    const span = b[0] - a[0];
    const w = span > 0 ? Math.min(1, Math.max(0, (t - a[0]) / span)) : 0;
    return a[1].map((car, i) => {
      const nb = b[1][i];
      const pos = Math.abs(nb[0] - car[0]) <= 1.01 ? car[0] + (nb[0] - car[0]) * w : car[0];
      return { pos, state: car[1], dir: car[2], load: car[3] };
    });
  }

  function liveStats(t) {
    const longWait = result.config.long_wait;
    let waiting = 0, riding = 0, served = 0, waitSum = 0, boarded = 0, maxWait = 0, jSum = 0;
    for (const p of result.trace.passengers) {
      const [arr, , , board, alight] = p;
      if (arr > t) continue;
      if (board == null || board > t) { waiting++; maxWait = Math.max(maxWait, t - arr); continue; }
      boarded++; waitSum += board - arr; maxWait = Math.max(maxWait, board - arr);
      if (alight <= t) { served++; jSum += alight - arr; } else riding++;
    }
    return { waiting, riding, served, avgWait: boarded ? waitSum / boarded : 0, maxWait,
      avgJourney: served ? jSum / served : 0, longWait };
  }

  // ------------------------------------------------------------------ draw
  const canvas = $("building"), ctx = canvas.getContext("2d");
  let geom = null;

  function tokens() {
    const cs = getComputedStyle(document.documentElement);
    const g = (n) => cs.getPropertyValue(n).trim();
    return { bg: g("--bg"), panel: g("--panel"), ink: g("--ink"), muted: g("--muted"), line: g("--line"),
      steel: g("--steel"), shaft: g("--shaft"), car: g("--car"), carInk: g("--car-ink"), led: g("--led"),
      ledBg: g("--led-bg"), accent: g("--accent"), good: g("--good"), warn: g("--warn"), hot: g("--hot"),
      fontNum: g("--font-num"), fontLed: g("--font-led"), fontUi: g("--font-ui") };
  }

  function floorLabel(f, lobby) {
    if (f === lobby) return "L";
    return f > lobby ? String(f - lobby) : "B" + (lobby - f);
  }

  function resizeCanvas() {
    const wrap = $("canvas-wrap");
    const cfg = result ? result.config : readForm();
    const W = Math.max(300, wrap.clientWidth - 2);
    const headH = 46;
    const floorH = Math.max(22, Math.min(56, (wrap.clientHeight - headH - 12) / cfg.floors));
    const H = headH + floorH * cfg.floors + 10;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    canvas.style.width = W + "px"; canvas.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const labelW = 34;
    const E = cfg.elevators;
    const shaftW = Math.max(30, Math.min(78, (W - labelW - 120) / E - 8));
    const shaftsW = E * (shaftW + 8);
    const queueW = Math.max(90, W - labelW - shaftsW - 16);
    geom = { W, H, headH, floorH, labelW, shaftW, queueW, queueX: labelW, shaftX: labelW + queueW + 8, floors: cfg.floors, E };
  }

  function draw() {
    if (!geom) return;
    const c = tokens();
    const { W, H, headH, floorH, labelW, shaftW, queueW, queueX, shaftX, floors } = geom;
    ctx.clearRect(0, 0, W, H);
    if (!result) return;
    const cfg = result.config;
    const t = playT;
    const yOf = (pos) => headH + (floors - 1 - pos) * floorH;   // top of floor row

    // floors
    ctx.font = `600 13px ${c.fontNum}`;
    ctx.textBaseline = "middle";
    for (let f = 0; f < floors; f++) {
      const y = yOf(f);
      ctx.strokeStyle = c.line; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(0, y + floorH + 0.5); ctx.lineTo(W, y + floorH + 0.5); ctx.stroke();
      ctx.fillStyle = f === cfg.lobby_floor ? c.accent : c.muted;
      ctx.textAlign = "right";
      ctx.fillText(floorLabel(f, cfg.lobby_floor), labelW - 8, y + floorH / 2);
    }

    // waiting passengers per floor, split by direction
    const qUp = Array.from({ length: floors }, () => []), qDn = Array.from({ length: floors }, () => []);
    for (const p of result.trace.passengers) {
      const [arr, o, d, board] = p;
      if (arr <= t && (board == null || board > t)) (d > o ? qUp : qDn)[o].push(t - arr);
    }
    const r = Math.max(2.5, Math.min(5, floorH * 0.13));
    const colorFor = (w) => (w >= cfg.long_wait ? c.hot : w >= cfg.long_wait / 2 ? c.warn : c.good);
    for (let f = 0; f < floors; f++) {
      const y = yOf(f);
      const lampX = queueX + 6;
      const rows = [[qUp[f], "▲", y + floorH * 0.32], [qDn[f], "▼", y + floorH * 0.7]];
      for (const [q, glyph, cy] of rows) {
        ctx.font = `${Math.max(9, Math.min(13, floorH * 0.32))}px ${c.fontUi}`;
        ctx.textAlign = "left";
        ctx.fillStyle = q.length ? c.led : c.line;
        ctx.fillText(glyph, lampX, cy);
        const startX = lampX + 16, maxDots = Math.max(1, Math.floor((queueW - 52) / (r * 2 + 2)));
        q.sort((a, b) => b - a);
        for (let k = 0; k < Math.min(q.length, maxDots); k++) {
          ctx.fillStyle = colorFor(q[k]);
          ctx.beginPath(); ctx.arc(startX + r + k * (r * 2 + 2), cy, r, 0, Math.PI * 2); ctx.fill();
        }
        if (q.length > maxDots || q.length >= 4) {
          ctx.fillStyle = c.muted; ctx.font = `11px ${c.fontNum}`; ctx.textAlign = "right";
          ctx.fillText(String(q.length), queueX + queueW - 2, cy);
        }
      }
    }

    // shafts and cars
    const cars = frameAt(t);
    cars.forEach((car, i) => {
      const x = shaftX + i * (shaftW + 8);
      ctx.fillStyle = c.shaft;
      ctx.fillRect(x, headH, shaftW, floorH * floors);
      // indicator
      const ih = 30, iy = 8;
      ctx.fillStyle = c.ledBg;
      roundRect(x, iy, shaftW, ih, 3); ctx.fill();
      const fl = Math.round(car.pos);
      ctx.fillStyle = c.led;
      ctx.font = `${Math.min(20, shaftW * 0.36)}px ${c.fontLed}`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      const arrow = car.dir > 0 ? "▲" : car.dir < 0 ? "▼" : "";
      ctx.fillText(arrow + floorLabel(fl, cfg.lobby_floor), x + shaftW / 2, iy + ih / 2 + 1);
      // car
      const ch = floorH * 0.86, cy = yOf(car.pos) + (floorH - ch) / 2;
      const cw = shaftW - 6, cx = x + 3;
      ctx.fillStyle = c.car;
      roundRect(cx, cy, cw, ch, 3); ctx.fill();
      const open = car.state === 3 ? 1 : car.state === 2 || car.state === 4 ? 0.5 : 0;
      if (open > 0) {
        const gap = (cw - 6) * 0.5 * open;
        ctx.fillStyle = c.panel;
        ctx.fillRect(cx + cw / 2 - gap / 2, cy + 3, gap, ch - 6);
      } else {
        ctx.strokeStyle = c.carInk; ctx.globalAlpha = 0.35; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(cx + cw / 2, cy + 3); ctx.lineTo(cx + cw / 2, cy + ch - 3); ctx.stroke();
        ctx.globalAlpha = 1;
      }
      // load
      const fill = car.load / cfg.capacity;
      ctx.fillStyle = fill >= 1 ? c.hot : c.accent;
      ctx.fillRect(cx + 3, cy + ch - 4, (cw - 6) * Math.min(1, fill), 2.5);
      if (floorH >= 26) {
        ctx.fillStyle = open > 0 ? c.ink : c.carInk;
        ctx.font = `600 ${Math.min(13, floorH * 0.34)}px ${c.fontNum}`;
        ctx.fillText(String(car.load), cx + cw / 2, cy + ch / 2 - 1);
      }
    });
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  function drawSpark() {
    const cv = $("spark"), cx = cv.getContext("2d");
    const w = cv.clientWidth, h = cv.clientHeight, dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx.clearRect(0, 0, w, h);
    if (!derived) return;
    const c = tokens();
    const { series, maxSeries, end } = derived;
    const pad = 2, yOf = (v) => h - pad - (v / maxSeries) * (h - pad * 2 - 12);
    cx.strokeStyle = c.line; cx.lineWidth = 1;
    cx.beginPath(); cx.moveTo(0, h - pad + 0.5); cx.lineTo(w, h - pad + 0.5); cx.stroke();
    cx.beginPath(); cx.moveTo(0, h - pad);
    series.forEach((v, k) => cx.lineTo((k / (series.length - 1)) * w, yOf(v)));
    cx.lineTo(w, h - pad); cx.closePath();
    cx.fillStyle = c.steel; cx.globalAlpha = 0.35; cx.fill(); cx.globalAlpha = 1;
    cx.beginPath();
    series.forEach((v, k) => { const X = (k / (series.length - 1)) * w; k ? cx.lineTo(X, yOf(v)) : cx.moveTo(X, yOf(v)); });
    cx.strokeStyle = c.muted; cx.lineWidth = 1.2; cx.stroke();
    const px = (playT / end) * w;
    cx.strokeStyle = c.accent; cx.lineWidth = 2;
    cx.beginPath(); cx.moveTo(px, 0); cx.lineTo(px, h); cx.stroke();
    cx.fillStyle = c.muted; cx.font = `11px ${c.fontNum}`; cx.textAlign = "left"; cx.textBaseline = "top";
    cx.fillText("peak " + maxSeries, 4, 1);
  }

  // -------------------------------------------------------------- readouts
  const fmtT = (s) => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const num = (v, d = 1) => (typeof v === "number" ? v.toFixed(d) : String(v));

  function renderLive() {
    if (!result) return;
    const s = liveStats(playT);
    const total = result.trace.passengers.length;
    $("live").innerHTML = [
      ["Waiting now", s.waiting], ["Riding now", s.riding], ["Delivered", `${s.served} / ${total}`],
      ["Average wait so far", num(s.avgWait) + " s"], ["Longest wait so far", num(s.maxWait) + " s"],
      ["Average journey so far", num(s.avgJourney) + " s"],
    ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
    const cars = frameAt(playT);
    const names = ["idle", "moving", "doors opening", "loading", "doors closing"];
    $("cars").innerHTML = cars.map((car, i) =>
      `<div class="car-row"><span class="pill">${String.fromCharCode(65 + i)}</span>` +
      `<div class="bar" title="${car.load} of ${result.config.capacity} places used"><span style="width:${(100 * car.load) / result.config.capacity}%"></span></div>` +
      `<span class="n">${names[car.state]}</span></div>`).join("");
    $("clock").textContent = fmtT(playT);
    $("scrub").value = String(Math.round(playT * 10));
  }

  function renderFinal() {
    const s = result.summary;
    const label = (strategies.find((x) => x.name === result.strategy) || {}).label || result.strategy_label || result.strategy;
    $("run-name").textContent = label;
    const rows = [
      ["Average wait", num(s.avg_wait) + " s"], ["95th pct wait", num(s.p95_wait) + " s"],
      ["Maximum wait", num(s.max_wait) + " s"], ["Average travel", num(s.avg_travel) + " s"],
      ["Average journey", num(s.avg_journey) + " s"], ["Served", s.served], ["Utilization", num(s.utilization) + " %"],
      ["Idle time, all cars", num(s.idle_time, 0) + " s"], ["Floors travelled", s.floors_travelled], ["Stops", s.stops],
      ["Longest queue", s.max_queue], ["Bottleneck episodes", s.bottlenecks], ["Full-car pass-bys", s.left_behind],
    ];
    $("final").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  }

  // -------------------------------------------------------------- playback
  function tick(ts) {
    if (playing && result) {
      const dt = lastTs ? (ts - lastTs) / 1000 : 0;
      playT = Math.min(derived.end, playT + dt * Number($("speed").value));
      if (playT >= derived.end) pause();
    }
    lastTs = ts;
    if (result) { draw(); drawSpark(); renderLive(); }
    requestAnimationFrame(tick);
  }
  function play() {
    if (!result) return;
    if (playT >= derived.end) playT = 0;
    playing = true; $("play-btn").textContent = "Pause"; $("play-btn").setAttribute("aria-label", "Pause");
  }
  function pause() { playing = false; $("play-btn").textContent = "Play"; $("play-btn").setAttribute("aria-label", "Play"); }

  function showOverlay(text) { $("overlay").textContent = text; $("overlay").hidden = false; }
  function hideOverlay() { $("overlay").hidden = true; }

  // --------------------------------------------------------------- compare
  let compareData = null;
  async function runCompare() {
    if (!py) {
      const d = demoForForm();
      if (!d) { $("compare-hint").textContent = "Pick one of the precomputed scenarios on the Watch tab: custom settings need the Python engine."; return; }
      compareData = d.compare; renderCompare();
      $("compare-hint").textContent = `Showing the precomputed comparison (${d.compare.seeds.length} seeds).`;
      return;
    }
    const cfg = readForm();
    const err = validate(cfg);
    if (err) { $("compare-hint").textContent = err; return; }
    const seeds = Math.max(1, Math.min(30, Number($("seeds").value) || 5));
    $("compare-btn").disabled = true;
    const results = [];
    let meta = null;
    try {
      for (let i = 0; i < strategies.length; i++) {
        $("compare-hint").textContent = `Running ${strategies[i].label} (${i + 1} of ${strategies.length})…`;
        await new Promise((r) => setTimeout(r, 20));
        const out = JSON.parse(py.compare(JSON.stringify(cfg), JSON.stringify([strategies[i].name]), seeds));
        meta = out; results.push(out.results[0]);
      }
      compareData = Object.assign({}, meta, { results });
      $("compare-hint").textContent = `Done: ${strategies.length} algorithms × ${seeds} seeds on identical passengers.`;
      renderCompare();
    } catch (e) {
      $("compare-hint").textContent = "The comparison failed: " + String(e.message || e).split("\n").slice(-2).join(" ");
    } finally {
      $("compare-btn").disabled = !py;
    }
  }

  function better(key, a, b) {
    const lower = DATA.metrics[key].lower_is_better;
    if (lower == null) return false;
    return lower ? a < b : a > b;
  }

  function renderCompare() {
    if (!compareData) return;
    const res = compareData.results;
    const key = $("metric").value;
    const m = DATA.metrics[key];
    const vals = res.map((r) => r.metrics[key]);
    let bestIdx = 0;
    vals.forEach((v, i) => { if (better(key, v.mean, vals[bestIdx].mean)) bestIdx = i; });
    const max = Math.max(1e-9, ...vals.map((v) => v.mean + v.std));
    const order = res.map((_, i) => i).sort((a, b) => (m.lower_is_better === false ? vals[b].mean - vals[a].mean : vals[a].mean - vals[b].mean));
    $("bars-title").textContent = m.label + (m.unit ? ` (${m.unit === "s" ? "seconds" : m.unit})` : "");
    $("bars").innerHTML = order.map((i) => {
      const v = vals[i];
      const isBest = m.lower_is_better != null && i === bestIdx;
      const lo = Math.max(0, v.mean - v.std), hi = v.mean + v.std;
      return `<div class="bar-row${isBest ? " best" : ""}"><span>${res[i].label}</span>` +
        `<div class="bar-track"><div class="bar-fill" style="width:${(100 * v.mean) / max}%"></div>` +
        (v.std > 0 ? `<div class="bar-err" style="left:${(100 * lo) / max}%;width:${(100 * (hi - lo)) / max}%"></div>` : "") +
        `</div><span class="bar-val">${num(v.mean)}</span></div>`;
    }).join("");

    const cols = ["avg_wait", "p95_wait", "max_wait", "avg_travel", "avg_journey", "long_wait_pct", "utilization",
      "idle_time", "floors_travelled", "stops", "max_queue", "bottlenecks", "left_behind"];
    const bestOf = {};
    for (const k of cols) {
      let b = null;
      res.forEach((r, i) => { if (b === null || better(k, r.metrics[k].mean, res[b].metrics[k].mean)) b = i; });
      bestOf[k] = DATA.metrics[k].lower_is_better == null ? -1 : b;
    }
    const head = "<tr><th>Algorithm</th>" + cols.map((k) => `<th>${DATA.metrics[k].label}${DATA.metrics[k].unit ? ` (${DATA.metrics[k].unit})` : ""}</th>`).join("") + "<th></th></tr>";
    const body = res.map((r, i) => "<tr><td>" + r.label + "</td>" + cols.map((k) =>
      `<td class="${bestOf[k] === i ? "best" : ""}">${num(r.metrics[k].mean)}${r.metrics[k].std ? ` <span class="sd">±${num(r.metrics[k].std)}</span>` : ""}</td>`).join("") +
      `<td><button class="linkish" data-watch="${r.strategy}">Watch</button></td></tr>`).join("");
    $("table").innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;

    const byJourney = res.slice().sort((a, b) => a.metrics.avg_journey.mean - b.metrics.avg_journey.mean);
    const byMax = res.slice().sort((a, b) => a.metrics.max_wait.mean - b.metrics.max_wait.mean);
    const c = compareData.config;
    const gap = byJourney[byJourney.length - 1].metrics.avg_journey.mean - byJourney[0].metrics.avg_journey.mean;
    $("verdict").innerHTML = `For ${c.floors} floors, ${c.elevators} car${c.elevators > 1 ? "s" : ""} and ${c.traffic.replace("_", "-")} traffic at ${c.arrival_rate}/min, ` +
      `<strong>${byJourney[0].label}</strong> gives the shortest average journey (${num(byJourney[0].metrics.avg_journey.mean)} s, ` +
      `${num(gap)} s faster than ${byJourney[byJourney.length - 1].label}). ` +
      (byMax[0].strategy === byJourney[0].strategy ? "It also has the lowest worst-case wait." :
        `<strong>${byMax[0].label}</strong> has the lowest worst-case wait (${num(byMax[0].metrics.max_wait.mean)} s).`) +
      ` Averaged over ${compareData.seeds.length} seeded run${compareData.seeds.length > 1 ? "s" : ""}.`;
  }

  // ----------------------------------------------------------------- wiring
  function selectTab(name) {
    for (const n of ["watch", "compare"]) {
      $("tab-" + n).setAttribute("aria-selected", String(n === name));
      $("view-" + n).hidden = n !== name;
    }
    if (name === "watch") { resizeCanvas(); draw(); }
    if (name === "compare") renderCompare();
  }

  function wire() {
    $("tab-watch").onclick = () => selectTab("watch");
    $("tab-compare").onclick = () => selectTab("compare");
    $("strategy").onchange = () => { updateStrategyNote(); if (!py) runSimulation(); };
    $("preset").onchange = () => {
      const p = DATA.presets[Number($("preset").value)];
      if (p) fillForm(Object.assign({}, DEFAULTS, p.config));
      if (!py) { runSimulation(); runCompare(); }
    };
    for (const f of CFG_FIELDS) if ($(f)) $(f).addEventListener("input", () => { if (document.activeElement === $(f)) $("preset").value = ""; });
    $("run-btn").onclick = runSimulation;
    $("compare-btn").onclick = runCompare;
    $("metric").onchange = renderCompare;
    $("play-btn").onclick = () => (playing ? pause() : play());
    $("restart-btn").onclick = () => { playT = 0; play(); };
    $("scrub").oninput = () => { if (result) { playT = Number($("scrub").value) / 10; pause(); } };
    $("table").onclick = (ev) => {
      const name = ev.target.getAttribute && ev.target.getAttribute("data-watch");
      if (!name) return;
      $("strategy").value = name; updateStrategyNote();
      selectTab("watch"); runSimulation();
    };
    $("trace-file").onchange = async () => {
      const file = $("trace-file").files[0];
      if (!file) return;
      try {
        const res = JSON.parse(await file.text());
        if (!res.trace) throw new Error("this file has no animation trace; create one with: python -m elevsim run --trace out.json");
        fillForm(res.config); $("preset").value = "";
        setResult(res); play();
        $("run-hint").textContent = `Loaded ${file.name}.`;
      } catch (e) {
        $("run-hint").textContent = "Could not load that file: " + e.message;
      }
    };
    window.addEventListener("resize", () => { resizeCanvas(); draw(); });
  }

  async function init() {
    fillForm(DEFAULTS);
    populateSelectors();
    wire();
    const demo = DATA.demo && DATA.demo.default && DATA.demo.scenarios[DATA.demo.default];
    if (demo) {
      const first = demo.runs[DATA.demo.default_strategy] || Object.values(demo.runs)[0];
      selectPreset(DATA.demo.default);
      $("strategy").value = first.strategy; updateStrategyNote();
      setResult(first);
      compareData = demo.compare; renderCompare();
      playT = Math.min(derived.end, 120);
      play();
    }
    requestAnimationFrame(tick);
    try {
      await loadEngine();
      populateSelectors();
      if (result) { $("strategy").value = result.strategy; updateStrategyNote(); }
      $("run-btn").disabled = false; $("compare-btn").disabled = false;
      setEngine("ok", "Python engine ready");
      if (compareData) renderCompare();
    } catch (e) {
      console.warn(e);
      setEngine("err", "Showing precomputed runs");
      const ids = Object.keys((DATA.demo && DATA.demo.scenarios) || {});
      const names = (DATA.presets || []).filter((p) => ids.includes(p.id)).map((p) => p.name);
      const msg = "The Python engine can't load on this page, so it plays runs computed in advance" +
        (names.length ? ` for: ${names.join(", ")}.` : ".") +
        " For custom settings, run python3 -m elevsim viewer and open dist/viewer.html.";
      $("run-hint").textContent = msg; $("compare-hint").textContent = msg;
      $("run-btn").disabled = !ids.length; $("compare-btn").disabled = !ids.length;
    }
  }

  init();
})();
