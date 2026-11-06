/* UniFi Sonar – 3D-globe voor de Wereld-pagina.
   Canvas + d3-geo (orthografische projectie). Wordt pas geladen als je de globe kiest.
   SonarGlobe.mount(host, { onHover(cc, x, y), onLeave(), onClick(cc) }) → globe met
   setData(data), pulse(dir, cc), setFocus(cc), zoomBy(f), zoomTo(cc), reset(), destroy(). */
(function () {
  "use strict";
  const COL = { out: "#39D8F4", in: "#9C84FF", blocked: "#FB7185", text: "#F3F7FC", border: "#090E18", land: "#1D2A3D" };
  const LIFT = { out: 1, in: 0.8, blocked: 1.25 };   // verschillende hoogte zodat bogen niet samenvallen
  const RGB = { out: "57,216,244", in: "156,132,255", blocked: "251,113,133" };
  const SHIELD = 0.86;   // waar geblokkeerd verkeer op het schild vóór thuis stukloopt (deel van de boog)
  const RIPPLE = 750;    // ms: rimpeling of uiteenspatten na een live puls
  const seedOf = (s) => { let h = 7; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 9973; return h / 9973; };
  const fade = (f) => Math.max(0, Math.min(1, f / 0.08, (1 - f) / 0.08));   // komeet komt zacht op en verdwijnt zacht
  const rad = Math.PI / 180;
  const reduce = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  function vec([lon, lat]) {
    const l = lon * rad, p = lat * rad;
    return [Math.cos(p) * Math.cos(l), Math.cos(p) * Math.sin(l), Math.sin(p)];
  }
  function lonlat([x, y, z]) {
    return [Math.atan2(y, x) / rad, Math.asin(Math.max(-1, Math.min(1, z))) / rad];
  }

  function mount(host, cb = {}) {
    const G = window.WORLD_GEO, d3 = window.d3;
    const canvas = document.createElement("canvas");
    canvas.className = "globe-canvas";
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", document.documentElement.lang === "en" ? "Rotating globe with connections per country" : "Draaiende wereldbol met verbindingen per land");
    host.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    const bg = document.createElement("canvas");   // sterren en nevel: één keer per formaat tekenen
    const feats = Object.fromEntries(G.features.map((f) => [f.id, f]));
    const graticule = d3.geoGraticule10();
    const projection = d3.geoOrthographic().clipAngle(90).precision(0.4);
    const path = d3.geoPath(projection, ctx);
    const st = {
      w: 0, h: 0, dpr: 1, R0: 1, R: 1, rot: [0, -25, 0], data: null, focus: null, pulses: [],
      stars: [], idleAt: 0, drag: null, anim: null, raf: 0, alive: true, last: performance.now(),
    };

    // ------------------------------------------------------------ maat en achtergrond
    function resize() {
      const r = host.getBoundingClientRect();
      const w = Math.max(280, Math.round(r.width)), h = Math.max(300, Math.round(r.height));
      st.dpr = Math.min(2, window.devicePixelRatio || 1);
      for (const c of [canvas, bg]) { c.width = w * st.dpr; c.height = h * st.dpr; }
      canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
      const k = st.R / st.R0 || 1;
      st.w = w; st.h = h; st.R0 = Math.min(w, h) * 0.42; st.R = st.R0 * k;
      drawBackground();
      draw();
    }
    function drawBackground() {
      const b = bg.getContext("2d"), { w, h, dpr } = st;
      b.setTransform(dpr, 0, 0, dpr, 0, 0);
      b.fillStyle = "#05080F";
      b.fillRect(0, 0, w, h);
      // zachte nevel in de huisstijlkleuren
      for (const [x, y, r, c] of [[0.18, 0.25, 0.55, "156,132,255"], [0.85, 0.75, 0.6, "57,216,244"], [0.6, 0.1, 0.35, "72,224,180"]]) {
        const g = b.createRadialGradient(x * w, y * h, 0, x * w, y * h, r * Math.max(w, h));
        g.addColorStop(0, `rgba(${c},0.07)`); g.addColorStop(1, `rgba(${c},0)`);
        b.fillStyle = g; b.fillRect(0, 0, w, h);
      }
      // een melkweg-band: veel kleine sterren rond een schuine lijn
      let seed = 7;
      const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      st.stars = [];
      const n = Math.round((w * h) / 900);
      for (let i = 0; i < n; i++) {
        let x = rnd() * w, y = rnd() * h;
        if (i % 3 === 0) {   // een derde dicht bij de band
          const t = rnd();
          x = t * w; y = h * (0.85 - 0.7 * t) + (rnd() - 0.5) * h * 0.18;
        }
        const big = rnd() < 0.06;
        const s = { x, y, r: big ? 1 + rnd() * 0.8 : 0.3 + rnd() * 0.6, a: 0.25 + rnd() * 0.6, tw: big || rnd() < 0.08 ? rnd() * 6.28 : null };
        if (s.tw == null) { b.globalAlpha = s.a; b.fillStyle = "#fff"; b.beginPath(); b.arc(x, y, s.r, 0, 6.283); b.fill(); }
        else st.stars.push(s);   // fonkelende sterren tekenen we per frame
      }
      b.globalAlpha = 1;
    }

    // ------------------------------------------------------------ bogen
    function arcPoints(from, to, kind) {
      const a = vec(from), b = vec(to);
      const dot = Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]));
      const ang = Math.acos(dot);
      if (ang < 0.01) return null;
      const hmax = Math.min(0.28, 0.05 + ang * 0.11) * (LIFT[kind] || 1);
      const n = Math.max(12, Math.round(ang * 40)), out = [];
      for (let i = 0; i <= n; i++) {
        const t = i / n, s1 = Math.sin((1 - t) * ang) / Math.sin(ang), s2 = Math.sin(t * ang) / Math.sin(ang);
        const p = [a[0] * s1 + b[0] * s2, a[1] * s1 + b[1] * s2, a[2] * s1 + b[2] * s2];
        out.push({ ll: lonlat(p), h: 1 + hmax * Math.sin(Math.PI * t) });
      }
      return out;
    }
    const rotation = () => d3.geoRotation(st.rot);
    function screen(pt, rotf) {   // punt op hoogte h boven de bol → schermcoördinaat + zichtbaar?
      const [lon, lat] = rotf(pt.ll);
      const v = vec([lon, lat]), k = st.R * pt.h;
      const x = st.w / 2 + k * v[1], y = st.h / 2 - k * v[2];
      const behind = v[0] < 0 && Math.hypot(x - st.w / 2, y - st.h / 2) < st.R;
      return { x, y, vis: !behind };
    }

    // ------------------------------------------------------------ datastroom
    function at(sp, f) {   // schermpunt op deel f (0–1) van een boog, of null achter de bol
      const fi = Math.max(0, Math.min(1, f)) * (sp.length - 1), i = Math.floor(fi);
      const a = sp[i], b = sp[Math.min(sp.length - 1, i + 1)];
      if (!a.vis || !b.vis) return null;
      const u = fi - i;
      return [a.x + (b.x - a.x) * u, a.y + (b.y - a.y) * u];
    }
    function comet(sp, f, kind, size, alpha = 1, tail = 1) {
      const rgb = RGB[kind], len = 0.1 * tail, N = 12;
      let prev = null;
      for (let j = N; j >= 0; j--) {   // staart: van dun en vaag naar dik en fel
        const p = at(sp, f - (j / N) * len);
        if (p && prev) {
          const q = 1 - j / N;
          ctx.strokeStyle = `rgba(${rgb},${(0.6 * q * q * alpha).toFixed(3)})`;
          ctx.lineWidth = size * (0.2 + 0.8 * q);
          ctx.beginPath(); ctx.moveTo(prev[0], prev[1]); ctx.lineTo(p[0], p[1]); ctx.stroke();
        }
        prev = p;
      }
      const h = at(sp, f);
      if (!h) return;
      const g = ctx.createRadialGradient(h[0], h[1], 0, h[0], h[1], size * 4.5);
      g.addColorStop(0, `rgba(${rgb},${(0.6 * alpha).toFixed(3)})`); g.addColorStop(1, `rgba(${rgb},0)`);
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(h[0], h[1], size * 4.5, 0, 6.283); ctx.fill();
      ctx.fillStyle = `rgba(255,255,255,${(0.9 * alpha).toFixed(3)})`;
      ctx.beginPath(); ctx.arc(h[0], h[1], size * 0.5, 0, 6.283); ctx.fill();
    }
    function burst(sp, q, alpha, scale) {   // geblokkeerd: schild licht op, vonken spatten weg
      const p = at(sp, SHIELD), b = at(sp, SHIELD - 0.03);
      if (!p || !b) return;
      const dir = Math.atan2(p[1] - b[1], p[0] - b[0]), a = (1 - q) * alpha, rgb = RGB.blocked;
      ctx.strokeStyle = `rgba(${rgb},${(0.9 * a).toFixed(3)})`; ctx.lineWidth = 1.6 * scale;
      ctx.beginPath(); ctx.arc(p[0] + Math.cos(dir) * 5 * scale, p[1] + Math.sin(dir) * 5 * scale, 8 * scale, dir + Math.PI - 0.9, dir + Math.PI + 0.9); ctx.stroke();
      ctx.lineWidth = scale;
      for (let i = 0; i < 6; i++) {
        const ang = dir + Math.PI + (i - 2.5) * 0.45, r1 = (3 + 9 * q) * scale, r2 = r1 + 4 * scale * (1 - q);
        ctx.beginPath();
        ctx.moveTo(p[0] + Math.cos(ang) * r1, p[1] + Math.sin(ang) * r1);
        ctx.lineTo(p[0] + Math.cos(ang) * r2, p[1] + Math.sin(ang) * r2);
        ctx.stroke();
      }
      const g = ctx.createRadialGradient(p[0], p[1], 0, p[0], p[1], 10 * scale);
      g.addColorStop(0, `rgba(${rgb},${(0.5 * a).toFixed(3)})`); g.addColorStop(1, `rgba(${rgb},0)`);
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p[0], p[1], 10 * scale, 0, 6.283); ctx.fill();
    }
    function ripple(sp, q, kind) {   // aankomst: twee ringen die uitdijen en vervagen
      const p = at(sp, 1);
      if (!p) return;
      for (const [d, r] of [[0, 16], [0.25, 10]]) {
        const u = Math.max(0, Math.min(1, (q - d) / (1 - d)));
        if (!u) continue;
        ctx.strokeStyle = `rgba(${RGB[kind]},${(0.8 * (1 - u)).toFixed(3)})`; ctx.lineWidth = 1.4;
        ctx.beginPath(); ctx.arc(p[0], p[1], 3 + r * u, 0, 6.283); ctx.stroke();
      }
    }

    // ------------------------------------------------------------ tekenen
    function draw(now = performance.now()) {
      const { w, h, dpr, R } = st;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.drawImage(bg, 0, 0, w, h);
      const t = now / 1000;
      for (const s of st.stars) {
        ctx.globalAlpha = reduce() ? s.a : s.a * (0.55 + 0.45 * Math.sin(t * 1.3 + s.tw));
        ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
      projection.translate([w / 2, h / 2]).scale(R).rotate(st.rot);
      const cx = w / 2, cy = h / 2;
      // dampkring (subtiel) en oceaan
      const atm = ctx.createRadialGradient(cx, cy, R * 0.98, cx, cy, R * 1.14);
      atm.addColorStop(0, "rgba(57,216,244,0.20)"); atm.addColorStop(1, "rgba(57,216,244,0)");
      ctx.fillStyle = atm; ctx.beginPath(); ctx.arc(cx, cy, R * 1.14, 0, 6.283); ctx.fill();
      const sea = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.4, R * 0.1, cx, cy, R);
      sea.addColorStop(0, "#17253D"); sea.addColorStop(1, "#0A1220");
      ctx.fillStyle = sea; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.283); ctx.fill();
      ctx.beginPath(); path(graticule); ctx.strokeStyle = "rgba(148,164,186,0.07)"; ctx.lineWidth = 0.6; ctx.stroke();
      // landen
      const D = st.data, by = D?.byCc || {}, show = D?.show || {};
      ctx.beginPath();
      for (const f of G.features) path(f);
      ctx.fillStyle = COL.land; ctx.fill();
      for (const f of G.features) {
        const c = by[f.id];
        if (!c) continue;
        const on = (show.out && c.out_n) || (show.in && c.in_n) || (show.blocked && c.blocked_n);
        if (!on) continue;
        ctx.beginPath(); path(f);
        ctx.fillStyle = c.bytes ? `rgba(57,216,244,${(0.14 + 0.5 * D.lvl(c.bytes)).toFixed(3)})` : "rgba(251,113,133,0.14)";
        ctx.fill();
      }
      ctx.beginPath();
      for (const f of G.features) path(f);
      ctx.strokeStyle = COL.border; ctx.lineWidth = 0.6; ctx.stroke();
      const hl = st.focus && feats[st.focus];
      if (hl) { ctx.beginPath(); path(hl); ctx.strokeStyle = COL.text; ctx.lineWidth = 1.2; ctx.stroke(); }
      if (D?.home && feats[D.home]) { ctx.beginPath(); path(feats[D.home]); ctx.strokeStyle = COL.out; ctx.lineWidth = 1; ctx.stroke(); }
      // rand van de bol
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.283); ctx.strokeStyle = "rgba(57,216,244,0.25)"; ctx.lineWidth = 1; ctx.stroke();

      const rotf = rotation();
      const homeLL = D && G.labels[D.home];
      // bogen
      if (D && homeLL) {
        const anim = !reduce();
        ctx.save();
        ctx.globalCompositeOperation = "lighter";   // licht telt op: gloed zonder grijze randen
        ctx.lineCap = "round"; ctx.lineJoin = "round";
        for (const a of D.arcs) {
          const pts = a.pts || (a.pts = arcPoints(a.kind === "out" ? homeLL : G.labels[a.cc], a.kind === "out" ? G.labels[a.cc] : homeLL, a.kind));
          a.sp = pts && pts.map((p) => screen(p, rotf));   // de punten lopen altijd in de stroomrichting
          if (!a.sp) continue;
          const sp = a.sp, rgb = RGB[a.kind], k = st.focus && st.focus !== a.cc ? 0.25 : 1;
          ctx.beginPath();
          let pen = false;
          for (const s of sp) {
            if (!s.vis) { pen = false; continue; }
            if (pen) ctx.lineTo(s.x, s.y); else { ctx.moveTo(s.x, s.y); pen = true; }
          }
          // buitenste gloed, dan een kern die naar de bestemming toe feller wordt
          ctx.strokeStyle = `rgba(${rgb},${(0.06 * k).toFixed(3)})`; ctx.lineWidth = a.w + 6; ctx.stroke();
          const s0 = sp[0], s1 = sp[sp.length - 1], g = ctx.createLinearGradient(s0.x, s0.y, s1.x, s1.y);
          g.addColorStop(0, `rgba(${rgb},${(0.06 * k).toFixed(3)})`); g.addColorStop(1, `rgba(${rgb},${(0.5 * k).toFixed(3)})`);
          ctx.strokeStyle = g; ctx.lineWidth = Math.max(0.8, a.w * 0.7);
          if (a.kind === "blocked") { ctx.setLineDash([3, 6]); ctx.lineDashOffset = anim ? -t * 14 : 0; }
          ctx.stroke();
          ctx.setLineDash([]);
        }
        // de datastroom: kometen die continu over elke boog lopen, meer naarmate er meer verkeer is
        if (anim) {
          for (const a of D.arcs) {
            if (!a.sp) continue;
            const dim = st.focus && st.focus !== a.cc;
            const n = dim ? 1 : Math.max(1, Math.min(5, Math.round(a.w * 1.3)));
            const dur = 2.4 + a.sp.length / 30;   // langere bogen duren langer: overal ongeveer even snel
            for (let i = 0; i < n; i++) {
              const f = (t / dur + i / n + (a.seed ??= seedOf(a.cc + a.kind))) % 1;
              if (a.kind === "blocked") {   // loopt op het schild vóór thuis stuk
                if (f < 0.8) comet(a.sp, (f / 0.8) * SHIELD, a.kind, 1.9, dim ? 0.3 : 1);
                else burst(a.sp, (f - 0.8) / 0.2, dim ? 0.3 : 1, 0.7);
              } else comet(a.sp, f, a.kind, 1.6 + a.w * 0.35, dim ? 0.3 : fade(f));
            }
          }
        }
        ctx.restore();
        ctx.setLineDash([]); ctx.globalAlpha = 1;
        // kleine landen zonder vorm: een stip
        for (const cc of D.dots) {
          const s = screen({ ll: G.labels[cc], h: 1 }, rotf);
          if (!s.vis) continue;
          const c = by[cc];
          ctx.fillStyle = c.out_n || c.in_n ? COL.out : COL.blocked;
          ctx.globalAlpha = st.focus === cc ? 1 : 0.85;
          ctx.beginPath(); ctx.arc(s.x, s.y, st.focus === cc ? 4.5 : 3.2, 0, 6.283); ctx.fill();
          ctx.strokeStyle = COL.border; ctx.lineWidth = 1; ctx.stroke();
        }
        ctx.globalAlpha = 1;
        // thuis
        const hs = screen({ ll: homeLL, h: 1 }, rotf);
        if (hs.vis) {
          const ph = reduce() ? 0.5 : (t % 2.4) / 2.4;
          ctx.strokeStyle = `rgba(57,216,244,${(0.8 * (1 - ph)).toFixed(3)})`; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(hs.x, hs.y, 4 + 10 * ph, 0, 6.283); ctx.stroke();
          ctx.fillStyle = COL.out; ctx.beginPath(); ctx.arc(hs.x, hs.y, 3, 0, 6.283); ctx.fill();
        }
        // pulsen: een live verbinding als felle komeet, met een rimpeling waar hij aankomt
        st.pulses = st.pulses.filter((p) => now - p.t0 < p.dur + RIPPLE);
        ctx.save();
        ctx.globalCompositeOperation = "lighter";
        for (const p of st.pulses) {
          p.pts ||= arcPoints(p.dir === "out" ? homeLL : G.labels[p.cc], p.dir === "out" ? G.labels[p.cc] : homeLL, p.dir);
          if (!p.pts) continue;
          const sp = p.pts.map((x) => screen(x, rotf)), end = p.dir === "blocked" ? SHIELD : 1;
          const f = (now - p.t0) / p.dur;
          if (f < 1) comet(sp, f * end, p.dir, 3.2, 1, 2.2);
          else if (p.dir === "blocked") burst(sp, (now - p.t0 - p.dur) / RIPPLE, 1, 1.4);
          else ripple(sp, (now - p.t0 - p.dur) / RIPPLE, p.dir);
        }
        ctx.restore();
        // namen bij ingezoomd
        if (R > st.R0 * 1.5) {
          ctx.font = "500 11px Inter, system-ui, sans-serif"; ctx.textAlign = "center";
          for (const cc of Object.keys(by)) {
            const ll = G.labels[cc];
            if (!ll) continue;
            const s = screen({ ll, h: 1 }, rotf);
            if (!s.vis) continue;
            const name = D.name(cc);
            ctx.lineWidth = 3; ctx.strokeStyle = COL.border; ctx.strokeText(name, s.x, s.y - (feats[cc] ? 0 : 8));
            ctx.fillStyle = COL.text; ctx.fillText(name, s.x, s.y - (feats[cc] ? 0 : 8));
          }
        }
      }
    }

    // ------------------------------------------------------------ animatie
    function frame(now) {
      if (!st.alive) return;
      if (!canvas.isConnected) { destroy(); return; }
      const dt = Math.min(100, now - st.last);
      st.last = now;
      if (st.anim) {   // naar een land draaien
        const a = st.anim, f = Math.min(1, (now - a.t0) / a.dur), e = f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2;
        st.rot = [a.from[0] + (a.to[0] - a.from[0]) * e, a.from[1] + (a.to[1] - a.from[1]) * e, 0];
        st.R = a.r0 + (a.r1 - a.r0) * e;
        if (f >= 1) st.anim = null;
      } else if (!st.drag && !reduce() && now - st.idleAt > 5000 && !st.focus) {
        st.rot[0] += dt * 0.0015;   // langzaam meedraaien als je niets doet (ca. 4 minuten per rondje)
      }
      if (!document.hidden) draw(now);
      st.raf = requestAnimationFrame(frame);
    }

    // ------------------------------------------------------------ interactie
    function local(e) { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
    function hit(x, y) {
      const D = st.data;
      if (!D) return null;
      const rotf = rotation();
      for (const cc of D.dots) {
        const s = screen({ ll: G.labels[cc], h: 1 }, rotf);
        if (s.vis && Math.hypot(s.x - x, s.y - y) < 8) return cc;
      }
      if (Math.hypot(x - st.w / 2, y - st.h / 2) > st.R) return null;
      const ll = projection.invert([x, y]);
      if (!ll) return null;
      for (const cc of Object.keys(D.byCc)) if (feats[cc] && d3.geoContains(feats[cc], ll)) return cc;
      return null;
    }
    canvas.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 && e.pointerType === "mouse") return;
      st.drag = { x: e.clientX, y: e.clientY, moved: false, id: e.pointerId };
      st.anim = null; st.idleAt = performance.now();
    });
    canvas.addEventListener("pointermove", (e) => {
      const d = st.drag;
      if (d && d.id === e.pointerId) {
        const dx = e.clientX - d.x, dy = e.clientY - d.y;
        if (!d.moved && Math.hypot(dx, dy) < 4) return;
        if (!d.moved) { d.moved = true; try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* al los */ } cb.onLeave?.(); }
        const k = 0.25 * st.R0 / st.R;
        st.rot = [st.rot[0] + dx * k, Math.max(-85, Math.min(85, st.rot[1] - dy * k)), 0];
        d.x = e.clientX; d.y = e.clientY; st.idleAt = performance.now();
        canvas.classList.add("dragging");
        return;
      }
      const [x, y] = local(e), cc = hit(x, y);
      if (cc !== st.hover) { st.hover = cc; }
      if (cc) { cb.onHover?.(cc, e.clientX, e.clientY); st.idleAt = performance.now(); } else cb.onLeave?.();
      canvas.style.cursor = cc ? "pointer" : "grab";
    });
    const end = (e) => {
      const d = st.drag;
      st.drag = null; canvas.classList.remove("dragging");
      if (d && !d.moved && e.type === "pointerup") {
        const [x, y] = local(e), cc = hit(x, y);
        if (cc) cb.onClick?.(cc);
      }
    };
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
    canvas.addEventListener("pointerleave", () => { if (!st.drag) cb.onLeave?.(); });
    canvas.addEventListener("wheel", (e) => {
      if (e.deltaY > 0 && st.R <= st.R0 * 1.01) return;   // helemaal uitgezoomd: pagina mag scrollen
      e.preventDefault();
      zoomBy(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0018)));
    }, { passive: false });
    const ro = new ResizeObserver(() => resize());
    ro.observe(host);

    // ------------------------------------------------------------ api
    function zoomBy(f) {
      st.anim = null; st.idleAt = performance.now();
      st.R = Math.max(st.R0, Math.min(st.R0 * 5, st.R * f));
      cb.onZoom?.(st.R / st.R0);
    }
    function rotateTo(ll, zoom, dur = 900) {
      const from = [...st.rot], to = [-ll[0], Math.max(-70, Math.min(70, -ll[1] + 10))];
      to[0] = from[0] + ((((to[0] - from[0]) % 360) + 540) % 360) - 180;   // kortste weg rond
      st.anim = { from, to, r0: st.R, r1: st.R0 * zoom, t0: performance.now(), dur: reduce() ? 1 : dur };
      st.idleAt = performance.now();
      cb.onZoom?.(zoom);
    }
    function setData(D) {
      const first = !st.data && D.home && G.labels[D.home];
      st.data = D;
      if (first) st.rot = [-G.labels[D.home][0] + 25, -G.labels[D.home][1] + 18, 0];
    }
    function destroy() {
      st.alive = false; cancelAnimationFrame(st.raf); ro.disconnect();
      canvas.remove();
    }
    resize();
    st.raf = requestAnimationFrame(frame);
    return {
      setData,
      pulse(dir, cc) { if (!reduce() && st.data && G.labels[cc] && cc !== st.data.home) st.pulses.push({ dir, cc, t0: performance.now(), dur: 1800 }); },
      setFocus(cc) { st.focus = cc; },
      zoomBy,
      zoomTo(cc) { const ll = G.labels[cc]; if (ll) rotateTo(ll, feats[cc] ? 2 : 3); },
      reset() { const h = st.data && G.labels[st.data.home]; rotateTo(h ? [h[0] - 25, h[1] - 8] : [0, 25], 1); },   // = beginstand
      zoomLevel: () => st.R / st.R0,
      destroy,
    };
  }
  window.SonarGlobe = { mount };
})();
