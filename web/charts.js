/* Lichtgewicht SVG-lijngrafiek in Midnight Electric-stijl.
   lineChart(el, { series:[{name, color, data:[[t, v], ...]}], unit, fmt, yMin, yMax, threshold:{value,label}, height,
                   bucket, xfmt (aslabels), tfmt (tooltip-tijd), markers }) */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const SERIES = ["#39D8F4", "#9C84FF", "#48E0B4", "#FFBE5C", "#FB7185"];
  const EN = document.documentElement.lang === "en";
  const L = (nl, en) => (EN ? en : nl);
  const LOC = L("nl-NL", "en-GB");

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  function niceTicks(min, max, count) {
    if (min === max) { min -= 1; max += 1; }
    const span = max - min;
    const step0 = span / count;
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0;
    const lo = Math.floor(min / step) * step;
    const hi = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = lo; v <= hi + step / 2; v += step) ticks.push(+v.toFixed(6));
    return ticks;
  }

  const hhmm = (t) => new Date(t * 1000).toLocaleTimeString(LOC, { hour: "2-digit", minute: "2-digit" });
  const dayTime = (t) => new Date(t * 1000).toLocaleString(LOC, { weekday: "short", hour: "2-digit", minute: "2-digit" });

  function lineChart(container, opts) {
    const series = opts.series.filter((s) => s.data && s.data.some((p) => p[1] != null));
    container.innerHTML = "";
    container.classList.add("chart");
    if (!series.length) {
      container.innerHTML = `<div class="chart-empty">${L("Nog geen meetgegevens in deze periode", "No readings in this period yet")}</div>`;
      return;
    }
    const fmt = opts.fmt || ((v) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)).replace(".", ","));
    const unit = opts.unit || "";

    if (series.length >= 2) {
      const lg = document.createElement("div");
      lg.className = "chart-legend";
      series.forEach((s) => {
        const sp = document.createElement("span");
        sp.innerHTML = `<i style="background:${s.color}"></i>`;
        sp.append(s.name);
        lg.appendChild(sp);
      });
      container.appendChild(lg);
    }

    const W = Math.max(260, container.clientWidth || 600);
    const H = opts.height || 180;
    const m = { l: 44, r: 12, t: 10, b: 24 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;

    const ts = [...new Set(series.flatMap((s) => s.data.map((p) => p[0])))].sort((a, b) => a - b);
    const vals = series.flatMap((s) => s.data.map((p) => p[1]).filter((v) => v != null));
    let lo = opts.yMin != null ? opts.yMin : Math.min(...vals);
    let hi = opts.yMax != null ? opts.yMax : Math.max(...vals);
    if (opts.threshold) { lo = Math.min(lo, opts.threshold.value); hi = Math.max(hi, opts.threshold.value); }
    if (opts.yMin == null && lo > 0 && lo < hi * 0.3) lo = 0;
    const yt = niceTicks(lo, hi, 4);
    const y0 = opts.yMin != null ? Math.min(opts.yMin, yt[0]) : yt[0];
    const y1 = opts.yMax != null ? Math.max(opts.yMax, yt[yt.length - 1]) : yt[yt.length - 1];
    const t0 = ts[0], t1 = ts[ts.length - 1] === t0 ? t0 + 60 : ts[ts.length - 1];
    const x = (t) => m.l + ((t - t0) / (t1 - t0)) * iw;
    const y = (v) => m.t + ih - ((v - y0) / (y1 - y0 || 1)) * ih;

    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img",
      "aria-label": opts.label || series.map((s) => s.name).join(", ") });
    container.appendChild(svg);

    yt.filter((v) => v >= y0 && v <= y1).forEach((v) => {
      el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: "grid-line" }, svg);
      const tx = el("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", class: "axis-label" }, svg);
      tx.textContent = Number.isInteger(v) ? v.toLocaleString(LOC) : fmt(v);
    });
    const nx = Math.max(2, Math.min(6, Math.floor(iw / 110)));
    for (let i = 0; i <= nx; i++) {
      const t = t0 + ((t1 - t0) * i) / nx;
      const tx = el("text", { x: x(t), y: H - 6, "text-anchor": i === 0 ? "start" : i === nx ? "end" : "middle", class: "axis-label" }, svg);
      tx.textContent = (opts.xfmt || hhmm)(t);
    }
    if (opts.threshold) {
      const ty = y(opts.threshold.value);
      el("line", { x1: m.l, x2: W - m.r, y1: ty, y2: ty, class: "thr" }, svg);
      const tl = el("text", { x: W - m.r, y: ty - 5, "text-anchor": "end", class: "thr-label" }, svg);
      tl.textContent = opts.threshold.label || `${L("drempel", "threshold")} ${fmt(opts.threshold.value)}${unit}`;
    }

    const gap = (opts.bucket || 60) * 3;
    series.forEach((s, idx) => {
      const color = s.color || SERIES[idx];
      let d = "", area = "", prevT = null, segStart = null;
      const pts = s.data.filter((p) => p[1] != null);
      pts.forEach((p, i) => {
        const X = x(p[0]).toFixed(1), Y = y(p[1]).toFixed(1);
        const brk = prevT == null || p[0] - prevT > gap;
        if (brk) {
          if (segStart != null && series.length === 1) area += `L${x(prevT).toFixed(1)},${y(y0)}L${segStart},${y(y0)}Z`;
          d += `M${X},${Y}`; area += `M${X},${Y}`; segStart = X;
        } else { d += `L${X},${Y}`; area += `L${X},${Y}`; }
        prevT = p[0];
        if (i === pts.length - 1 && series.length === 1) area += `L${X},${y(y0)}L${segStart},${y(y0)}Z`;
      });
      if (series.length === 1) el("path", { d: area, fill: color, "fill-opacity": 0.1, stroke: "none" }, svg);
      el("path", { d, class: "line", stroke: color }, svg);
      if (opts.markers) pts.forEach((p) => el("circle", { cx: x(p[0]), cy: y(p[1]), r: 3.5, fill: color, stroke: "#131C2B", "stroke-width": 2 }, svg));
    });

    // hover-laag
    const cross = el("line", { y1: m.t, y2: m.t + ih, class: "cross", visibility: "hidden" }, svg);
    const dots = series.map((s, i) => el("circle", { r: 4, fill: s.color || SERIES[i], stroke: "#131C2B", "stroke-width": 2, visibility: "hidden" }, svg));
    const hit = el("rect", { x: m.l, y: m.t, width: iw, height: ih, class: "hit", tabindex: 0,
      "aria-label": L("Grafiek: gebruik pijltjestoetsen om waarden te bekijken", "Chart: use the arrow keys to browse values") }, svg);
    const tip = document.createElement("div");
    tip.className = "tooltip";
    container.appendChild(tip);
    const lookup = series.map((s) => new Map(s.data.map((p) => [p[0], p[1]])));
    let cur = -1;

    function show(i) {
      cur = Math.max(0, Math.min(ts.length - 1, i));
      const t = ts[cur], X = x(t);
      cross.setAttribute("x1", X); cross.setAttribute("x2", X); cross.setAttribute("visibility", "visible");
      let rows = "";
      series.forEach((s, k) => {
        const v = lookup[k].get(t);
        if (v == null) { dots[k].setAttribute("visibility", "hidden"); return; }
        dots[k].setAttribute("cx", X); dots[k].setAttribute("cy", y(v)); dots[k].setAttribute("visibility", "visible");
        rows += `<div class="tt-row"><span><i class="sw" style="background:${s.color || SERIES[k]};width:8px;height:8px;border-radius:2px"></i>${s.name}</span><b>${fmt(v)}${unit}</b></div>`;
      });
      tip.innerHTML = `<div class="tt-time">${(opts.tfmt || dayTime)(t)}</div>${rows}`;
      tip.classList.add("show");
      const scale = container.clientWidth / W;
      const px = X * scale;
      const tw = tip.offsetWidth;
      tip.style.left = (px + 14 + tw > container.clientWidth ? px - tw - 14 : px + 14) + "px";
      tip.style.top = (container.querySelector(".chart-legend") ? 28 : 4) + "px";
    }
    function hide() {
      cross.setAttribute("visibility", "hidden");
      dots.forEach((d) => d.setAttribute("visibility", "hidden"));
      tip.classList.remove("show");
    }
    function nearest(evt) {
      const r = svg.getBoundingClientRect();
      const t = t0 + (((evt.clientX - r.left) * (W / r.width) - m.l) / iw) * (t1 - t0);
      let best = 0;
      for (let i = 1; i < ts.length; i++) if (Math.abs(ts[i] - t) < Math.abs(ts[best] - t)) best = i;
      return best;
    }
    hit.addEventListener("pointermove", (e) => show(nearest(e)));
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("blur", hide);
    hit.addEventListener("focus", () => show(cur < 0 ? ts.length - 1 : cur));
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") { show(cur - 1); e.preventDefault(); }
      if (e.key === "ArrowRight") { show(cur + 1); e.preventDefault(); }
      if (e.key === "Escape") hit.blur();
    });
  }

  /* Gestapelde staafgrafiek: barChart(el, { series:[{name, color, data:[v, ...]}], labels:[t, ...], unit, fmt,
     xfmt (aslabel), tfmt (tooltip-kop), height, label, highlight (index die als 'lopend' getoond wordt) }) */
  function barChart(container, opts) {
    const series = opts.series;
    const n = opts.labels.length;
    container.innerHTML = "";
    container.classList.add("chart");
    if (!n) { container.innerHTML = `<div class="chart-empty">${L("Nog geen gegevens", "No data yet")}</div>`; return; }
    const fmt = opts.fmt || ((v) => v.toLocaleString(LOC));
    if (series.length >= 2) {
      const lg = document.createElement("div");
      lg.className = "chart-legend";
      series.forEach((s) => { const sp = document.createElement("span"); sp.innerHTML = `<i style="background:${s.color}"></i>`; sp.append(s.name); lg.appendChild(sp); });
      container.appendChild(lg);
    }
    const W = Math.max(260, container.clientWidth || 600);
    const H = opts.height || 200;
    const m = { l: 44, r: 12, t: 10, b: 24 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const totals = opts.labels.map((_, i) => series.reduce((a, s) => a + (s.data[i] || 0), 0));
    const yt = niceTicks(0, Math.max(...totals, 1), 4);
    const y1 = yt[yt.length - 1];
    const y = (v) => m.t + ih - (v / y1) * ih;
    const slot = iw / n, bw = Math.max(2, Math.min(28, slot * 0.72));
    const xc = (i) => m.l + slot * i + slot / 2;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": opts.label || L("Staafgrafiek", "Bar chart") });
    container.appendChild(svg);
    yt.forEach((v) => {
      el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: "grid-line" }, svg);
      const tx = el("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", class: "axis-label" }, svg);
      tx.textContent = fmt(v);
    });
    const step = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(iw / 70))));
    for (let i = n - 1; i >= 0; i -= step) {   // vanaf rechts, zodat de laatste periode altijd een label heeft
      const tx = el("text", { x: xc(i), y: H - 6, "text-anchor": "middle", class: "axis-label" }, svg);
      tx.textContent = opts.xfmt(opts.labels[i]);
    }
    const bars = [];
    for (let i = 0; i < n; i++) {
      const g = el("g", { class: "bar" + (i === opts.highlight ? " running" : "") }, svg);
      let base = 0;
      const segs = series.map((s) => s.data[i] || 0);
      const top = segs.reduce((k, v, j) => (v > 0 ? j : k), -1);
      segs.forEach((v, j) => {
        if (v <= 0) return;
        const yTop = y(base + v), yBot = y(base), x0 = xc(i) - bw / 2, h = Math.max(0, yBot - yTop - (j > 0 ? 2 : 0));
        const r = j === top ? Math.min(4, bw / 2, h) : 0;   // afgeronde bovenkant, 2px ruimte tussen de lagen
        const yb = yTop + h;
        el("path", { d: `M${x0},${yb}V${yTop + r}Q${x0},${yTop} ${x0 + r},${yTop}H${x0 + bw - r}Q${x0 + bw},${yTop} ${x0 + bw},${yTop + r}V${yb}Z`,
          fill: series[j].color }, g);
        base += v;
      });
      bars.push(g);
    }
    const tip = document.createElement("div");
    tip.className = "tooltip";
    container.appendChild(tip);
    const hit = el("rect", { x: m.l, y: m.t, width: iw, height: ih, class: "hit", tabindex: 0,
      "aria-label": L("Grafiek: gebruik pijltjestoetsen om waarden te bekijken", "Chart: use the arrow keys to browse values") }, svg);
    let cur = -1;
    function show(i) {
      cur = Math.max(0, Math.min(n - 1, i));
      bars.forEach((b, k) => b.classList.toggle("dim", k !== cur));
      tip.innerHTML = `<div class="tt-time">${opts.tfmt(opts.labels[cur])}${cur === opts.highlight ? L(" · nog bezig", " · in progress") : ""}</div>` +
        series.map((s) => `<div class="tt-row"><span><i class="sw" style="background:${s.color};width:8px;height:8px;border-radius:2px"></i>${s.name}</span><b>${fmt(s.data[cur] || 0)}</b></div>`).join("") +
        `<div class="tt-row"><span>Totaal</span><b>${fmt(totals[cur])}</b></div>`;
      tip.classList.add("show");
      const px = xc(cur) * (container.clientWidth / W), tw = tip.offsetWidth;
      tip.style.left = (px + 14 + tw > container.clientWidth ? px - tw - 14 : px + 14) + "px";
      tip.style.top = (container.querySelector(".chart-legend") ? 28 : 4) + "px";
    }
    function hide() { bars.forEach((b) => b.classList.remove("dim")); tip.classList.remove("show"); }
    hit.addEventListener("pointermove", (e) => {
      const r = svg.getBoundingClientRect();
      show(Math.floor((((e.clientX - r.left) * (W / r.width)) - m.l) / slot));
    });
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("blur", hide);
    hit.addEventListener("focus", () => show(cur < 0 ? n - 1 : cur));
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") { show(cur - 1); e.preventDefault(); }
      if (e.key === "ArrowRight") { show(cur + 1); e.preventDefault(); }
      if (e.key === "Escape") hit.blur();
    });
  }

  window.MEcharts = { lineChart, barChart, SERIES };
})();
