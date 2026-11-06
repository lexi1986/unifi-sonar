/* UniFi Sonar — dashboard (vanilla JS, geen build-stap) */
(function () {
  "use strict";
  const C = { cyan: "#39D8F4", violet: "#9C84FF", mint: "#48E0B4", amber: "#FFBE5C", rose: "#FB7185" };
  const BAND_COLOR = { "2.4": C.cyan, "5": C.violet, "6": C.mint };

  // ------------------------------------------------------------------ iconen (Lucide, outline)
  const ICONS = {
    wifi: '<path d="M12 20h.01"/><path d="M2 8.82a15 15 0 0 1 20 0"/><path d="M5 12.86a10 10 0 0 1 14 0"/><path d="M8.5 16.43a5 5 0 0 1 7 0"/>',
    router: '<rect width="20" height="8" x="2" y="14" rx="2"/><path d="M6.01 18H6"/><path d="M10.01 18H10"/><path d="M15 10v4"/><path d="M17.84 7.17a4 4 0 0 0-5.66 0"/><path d="M20.66 4.34a8 8 0 0 0-11.31 0"/>',
    switch: '<rect width="20" height="8" x="2" y="8" rx="2"/><path d="M6 12h.01"/><path d="M10 12h.01"/><path d="M14 12h.01"/><path d="M18 12h.01"/>',
    ap: '<circle cx="12" cy="12" r="3"/><path d="M5.6 5.6a9 9 0 0 0 0 12.8"/><path d="M18.4 18.4a9 9 0 0 0 0-12.8"/><path d="M8.5 8.5a5 5 0 0 0 0 7"/><path d="M15.5 15.5a5 5 0 0 0 0-7"/>',
    laptop: '<path d="M20 16V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9m16 0H4m16 0 1.28 2.55a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45L4 16"/>',
    cable: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    octagon: '<path d="M12 16h.01"/><path d="M12 8v4"/><path d="M15.31 2a2 2 0 0 1 1.42.59l4.68 4.68A2 2 0 0 1 22 8.69v6.62a2 2 0 0 1-.59 1.42l-4.68 4.68a2 2 0 0 1-1.42.59H8.69a2 2 0 0 1-1.42-.59l-4.68-4.68A2 2 0 0 1 2 15.31V8.69a2 2 0 0 1 .59-1.42l4.68-4.68A2 2 0 0 1 8.69 2z"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    check: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-6 9H2"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    bulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    roam: '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
    power: '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
    plug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    "arrow-up-right": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "arrow-down-left": '<path d="M17 7 7 17"/><path d="M17 17H7V7"/>',
    gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    radar: '<path d="M19.07 4.93A10 10 0 0 0 6.99 3.34"/><path d="M4 6h.01"/><path d="M2.29 9.62A10 10 0 1 0 21.31 8.35"/><path d="M16.24 7.76A6 6 0 1 0 8.23 16.67"/><path d="M12 18h.01"/><path d="M17.99 11.66A6 6 0 0 1 15.77 16.67"/><circle cx="12" cy="12" r="2"/><path d="m13.41 10.59 5.66-5.66"/>',
    settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    key: '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>',
    eye: '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    layers: '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    home: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .71-1.53l7-6a2 2 0 0 1 2.58 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  };
  const icon = (n, cls = "") => `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;
  const devIcon = (t) => ({ gateway: "router", switch: "switch", ap: "ap" }[t] || "router");
  const SOURCE_LABEL = { "legacy-key": "uitgebreide API", "legacy-login": "uitgebreide API (account)", integration: "officiële API (beperkt)", mock: "demodata" };
  const SEV = { critical: ["Kritiek", "octagon"], warning: ["Waarschuwing", "alert"], info: ["Info", "info"] };
  const CAT = { wifi: "Wifi", switch: "Switch", device: "Apparaat", wan: "Internet", security: "Beveiliging", config: "Configuratie", new: "Nieuw apparaat" };
  const DAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"];

  // ------------------------------------------------------------------ helpers
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const nf = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString("nl-NL", { maximumFractionDigits: d, minimumFractionDigits: d }));
  function dur(sec) {
    if (sec == null) return "–";
    sec = Math.max(0, Math.round(sec));
    const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
    if (d) return `${d} d ${h} u`;
    if (h) return `${h} u ${m} m`;
    return m ? `${m} m` : `${sec} s`;
  }
  const ago = (ts) => (ts ? dur(Date.now() / 1000 - ts) : "–");
  const hhmm = (ts) => new Date(ts * 1000).toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
  // "14:32", "gisteren 14:32" of "ma 3 nov 14:32"
  const stamp = (ts) => {
    const d = new Date(ts * 1000), day = (x) => new Date(x).setHours(0, 0, 0, 0);
    const diff = Math.round((day(Date.now()) - day(d)) / 86400000);
    const pre = diff === 0 ? "" : diff === 1 ? "gisteren " : d.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" }) + " ";
    return pre + hhmm(ts);
  };
  const fullStamp = (ts) => new Date(ts * 1000).toLocaleString("nl-NL", { dateStyle: "full", timeStyle: "short" });
  function bps(v) {
    if (v == null) return "–";
    const u = ["bit/s", "kbit/s", "Mbit/s", "Gbit/s"];
    let i = 0;
    while (v >= 1000 && i < 3) { v /= 1000; i++; }
    return `${nf(v, v < 10 ? 1 : 0)} ${u[i]}`;
  }
  const speed = (mb) => (!mb ? "–" : mb >= 1000 ? `${nf(mb / 1000, mb % 1000 ? 1 : 0)} Gbit/s` : `${nf(mb)} Mbit/s`);
  const proto = (p) => ({ be: "Wi-Fi 7", ax: "Wi-Fi 6", ac: "Wi-Fi 5", n: "Wi-Fi 4", g: "Wi-Fi 3", a: "802.11a" }[p] || p || "–");
  const badge = (sev, text, ic) => `<span class="badge ${sev}">${ic ? icon(ic) : ""}${esc(text)}</span>`;
  const sevBadge = (s) => badge(s, SEV[s][0], SEV[s][1]);

  const sigLimits = (band) => (band === "2.4" ? [state.th.client_signal_warn_24, state.th.client_signal_crit_24] : [state.th.client_signal_warn, state.th.client_signal_crit]);
  function level(metric, v, band) {
    const t = state.th;
    if (v == null) return "";
    if (metric === "signal") { const [w, c] = sigLimits(band); return v <= c ? "critical" : v <= w ? "warning" : "ok"; }
    if (metric === "retry") return v >= t.client_retry_crit ? "critical" : v >= t.client_retry_warn ? "warning" : "ok";
    if (metric === "sat") return v < t.client_satisfaction_crit ? "critical" : v < t.client_satisfaction_warn ? "warning" : "ok";
    if (metric === "cu") return v >= t.radio_cu_crit ? "critical" : v >= t.radio_cu_warn ? "warning" : "ok";
    return "";
  }
  function signalBars(sig, band) {
    if (sig == null) return "–";
    const n = sig >= -60 ? 4 : sig >= -67 ? 3 : sig >= -75 ? 2 : 1;
    const lv = level("signal", sig, band);
    return `<span class="sig"><span class="bars ${lv}" aria-hidden="true">${[1, 2, 3, 4].map((i) => `<i class="${i <= n ? "on" : ""}"></i>`).join("")}</span><span class="num ${lv !== "ok" ? "t-" + lv : ""}">${nf(sig)} dBm</span></span>`;
  }
  const meter = (pct, lv) => `<div class="meter" role="meter" aria-valuenow="${Math.round(pct || 0)}" aria-valuemin="0" aria-valuemax="100"><span class="${lv || ""}" style="width:${Math.min(100, Math.max(0, pct || 0))}%"></span></div>`;
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  function worstSev(mac, withClients) {
    const sev = state.issues.filter((i) => !i.resolved_at && i.device_mac === mac && (withClients || !i.client_mac)).map((i) => i.severity);
    return sev.includes("critical") ? "critical" : sev.includes("warning") ? "warning" : "info";
  }
  const scoreLabel = (s) => (s >= 85 ? ["Goed", "ok"] : s >= 60 ? ["Aandacht nodig", "warning"] : ["Slecht", "critical"]);

  async function api(path) {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  }
  const store = {
    get(k, d) { try { const v = localStorage.getItem("ui." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("ui." + k, JSON.stringify(v)); } catch { /* geen opslag */ } },
  };

  // ------------------------------------------------------------------ state
  const state = {
    snap: null, status: null, issues: [], th: {},
    hours: store.get("hours", 6),
    issueSev: "all", issueCat: "all", showResolved: false, showMuted: false, expanded: new Set(),
    cq: "", ckind: store.get("ckind", "all"), cuplink: "", csort: store.get("csort", { key: "issues", dir: -1 }),
    ekind: "all",
    drawer: null,
  };
  const devByMac = () => Object.fromEntries((state.snap?.devices || []).map((d) => [d.mac, d]));
  const cliByMac = () => Object.fromEntries((state.snap?.clients || []).map((c) => [c.mac, c]));
  const devName = (mac) => devByMac()[mac]?.name || mac || "–";

  // ------------------------------------------------------------------ data
  async function refresh() {
    try {
      const status = await api("/api/status");
      state.status = status;
      if (status.setup_required) { if ($("#view").dataset.mounted !== "wizard") showWizard(); return; }
      if ($("#view").dataset.mounted === "wizard") return;   // wizard open voor een wijziging: niet overschrijven
      document.body.classList.remove("setup");
      if (current === "instellingen") { renderStatus(); UPDATERS.instellingen(); }
      let snap;
      try { snap = await api("/api/snapshot"); }
      catch (e) {   // net gekoppeld: eerste meting loopt nog
        $("#status").innerHTML = `<span class="dot warn"></span>Eerste meting wordt opgehaald…`;
        if (current !== "instellingen") $("#view").innerHTML = `<div class="card empty" style="margin-top:40px">${icon("radar")}<div>Eerste meting wordt opgehaald…</div><div class="muted" style="font-size:13px;margin-top:4px">${esc(status.last_error || "Dit duurt meestal een paar seconden.")}</div></div>`;
        $("#view").dataset.mounted = "";
        setTimeout(refresh, 4000);
        return;
      }
      const issues = await api(`/api/issues?state=${state.showResolved ? "all" : "open"}`);
      state.snap = snap; state.issues = issues; state.th = status.thresholds;
      renderStatus();
      update();
    } catch (e) {
      $("#status").innerHTML = `<span class="dot err"></span>Geen data: ${esc(e.message)}`;
      if (!state.snap) $("#view").innerHTML = `<div class="banner err">${icon("octagon")}Kan geen gegevens ophalen: ${esc(e.message)}</div>`;
    }
  }

  function renderStatus() {
    const s = state.status, h = state.snap?.health || {};
    const stale = s.last_ok && Date.now() / 1000 - s.last_ok > s.poll_seconds * 3;
    const dot = s.last_error || stale ? "err" : s.mode === "mock" ? "warn" : "";
    const src = s.mode === "mock" ? "Demodata" : `Live · ${SOURCE_LABEL[s.source] || s.source || "?"}`;
    $("#status").innerHTML = `<span class="dot ${dot}"></span>${esc(src)} · ${ago(s.last_ok)} geleden`;
    const top = (state.issues || []).filter((i) => !i.group && !i.resolved_at && !i.muted);
    const cnt = $("#nav-issues");
    cnt.textContent = top.length;
    cnt.className = "count" + (h.critical ? " crit" : "");
  }

  // ------------------------------------------------------------------ router
  const routes = { overzicht: mountOverview, issues: mountIssues, apparaten: mountDevices, clients: mountClients, internet: mountInternet, wereld: mountWorld, beveiliging: mountSecurity, tijdlijn: mountTimeline, instellingen: mountSettings };
  let current = null;
  function route() {
    const [name, id] = location.hash.replace(/^#\/?/, "").split("/");
    current = routes[name] ? name : "overzicht";
    state.pendingOpen = id ? decodeURIComponent(id) : null;   // deep link naar een detailpaneel
    document.querySelectorAll(".nav a, .iconlink").forEach((a) => { if (a.dataset.route === current) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    update();
    $("#view").focus({ preventScroll: true });
  }
  function update() {
    if (current === "instellingen" && state.status && !state.status.setup_required) {
      if ($("#view").dataset.mounted !== "instellingen") mountSettings();
      UPDATERS.instellingen();
      return;
    }
    if (!state.snap) return;
    const v = $("#view");
    if (v.dataset.mounted !== current) routes[current]();
    UPDATERS[current]?.();
    if (state.pendingOpen) {
      const id = state.pendingOpen;
      state.pendingOpen = null;
      if (devByMac()[id]) openDrawer("device", id);
      else if (cliByMac()[id]) openDrawer("client", id);
    }
  }
  const UPDATERS = {};
  function mount(name, html) {
    const v = $("#view");
    v.dataset.mounted = name;
    v.innerHTML = html;
    hydrateIcons(v);
  }
  function hydrateIcons(root) {
    root.querySelectorAll("[data-icon]").forEach((n) => { n.innerHTML = icon(n.dataset.icon); n.removeAttribute("data-icon"); });
  }
  const rangeSeg = (id) => `<div class="seg" role="group" aria-label="Periode" id="${id}">${[1, 6, 24].map((h) => `<button data-h="${h}" aria-pressed="${state.hours === h}">${h} u</button>`).join("")}</div>`;
  function bindRange(id, cb) {
    $("#" + id)?.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-h]");
      if (!b) return;
      state.hours = +b.dataset.h; store.set("hours", state.hours);
      document.querySelectorAll(`#${id} button`).forEach((x) => x.setAttribute("aria-pressed", x === b));
      cb();
    });
  }

  // ------------------------------------------------------------------ issue rendering
  const reconnectBtn = (mac) => `<button class="linkbtn" data-reconnect="${esc(mac)}">Opnieuw verbinden</button>`;
  // ---- internet pauzeren: blokkeert het apparaat in UniFi tot een tijdstip
  const PAUSES = [["30", "30 minuten"], ["60", "1 uur"], ["120", "2 uur"], ["morning", "Tot morgen 07:00"], ["", "Tot ik hervat"]];
  const pauseMenu = (mac) => `<details class="mute pause"><summary class="btn">${icon("power")}Pauzeren</summary><div class="mute-menu" role="group" aria-label="Pauzeren voor">
      ${PAUSES.map(([v, l]) => `<button data-pause="${esc(mac)}" data-for="${v}">${l}</button>`).join("")}</div></details>`;
  function pauseUntil(v) {
    if (!v) return null;
    if (v === "morning") { const d = new Date(); d.setDate(d.getDate() + (d.getHours() >= 7 ? 1 : 0)); d.setHours(7, 0, 0, 0); return Math.floor(d / 1000); }
    return Math.floor(Date.now() / 1000) + +v * 60;
  }
  async function pauseAction(e) {
    const b = e.target.closest("[data-pause]"), r = e.target.closest("[data-resume]");
    if (!b && !r) return false;
    e.preventDefault();
    try {
      if (b) {
        await post(`/api/clients/${encodeURIComponent(b.dataset.pause)}/pause`, { until: pauseUntil(b.dataset.for) });
        if (state.drawer) closeDrawer();
      } else {
        r.disabled = true;
        await post(`/api/clients/${encodeURIComponent(r.dataset.resume)}/resume`, {});
      }
    } catch (err) { alert(err.message); }
    await refresh();
    if (current === "clients") loadPauses();
    return true;
  }
  async function reconnectAction(e) {
    const b = e.target.closest("[data-reconnect]");
    if (!b) return false;
    e.preventDefault();
    b.disabled = true;
    b.textContent = "Bezig…";
    try {
      const r = await fetch(`/api/clients/${encodeURIComponent(b.dataset.reconnect)}/reconnect`, { method: "POST" });
      const body = await r.json().catch(() => ({}));
      b.textContent = r.ok ? (body.demo ? "Gedaan (demo)" : "Verbindt opnieuw…") : `Mislukt: ${body.detail || r.status}`;
      if (r.ok) setTimeout(async () => { await refresh(); if (state.drawer) renderDrawer(); }, 8000);
    } catch (err) {
      b.textContent = "Mislukt";
    }
    return true;
  }
  function entityAction(i) {
    if (i.client_mac) return `<button class="linkbtn" data-open="client" data-id="${esc(i.client_mac)}">Bekijk client</button>`;
    if (i.device_mac) return `<button class="linkbtn" data-open="device" data-id="${esc(i.device_mac)}">Bekijk ${esc(devName(i.device_mac))}</button>`;
    return "";
  }
  // Wanneer kwam dit het laatst voor? Bij een voorval (herstart, blokkade, linkverlies) het tijdstip daarvan;
  // bij een toestand (zwak signaal, hoge CPU) de laatste meting waarin het nog zo was.
  function issueWhen(i) {
    const last = i.last_ts || (i.resolved_at ? i.last_seen : null);
    const at = (ts) => `<time datetime="${new Date(ts * 1000).toISOString()}" title="${esc(fullStamp(ts))}">${stamp(ts)}</time>`;
    const parts = [];
    if (last) parts.push(`Laatst ${at(last)}${i.resolved_at ? "" : ` · ${ago(last)} geleden`}`);
    else if (i.last_seen) parts.push(Date.now() / 1000 - i.last_seen < 180 ? "Speelt nu" : `Laatst gezien ${at(i.last_seen)}`);
    if (i.resolved_at) parts.push(`opgelost ${at(i.resolved_at)}`);
    else if (i.first_seen) parts.push(`melding sinds ${ago(i.first_seen)}`);
    return parts.map((p) => `<span>${p}</span>`).join("");
  }
  function muteCtlHTML(i) {
    const k = esc(i.key);
    return i.muted
      ? `<button class="mutebtn" data-unmute="${k}">Niet meer negeren</button>`
      : `<details class="mute"><summary class="mutebtn">Negeren</summary><div class="mute-menu" role="group" aria-label="Negeren voor">
           ${[[1, "1 dag"], [7, "1 week"], [30, "30 dagen"], ["", "Altijd"]].map(([d, l]) => `<button data-mute="${k}" data-days="${d}">${l}</button>`).join("")}</div></details>`;
  }
  function issueHTML(i, all, flat) {
    const members = all.filter((m) => m.group === i.key);
    const open = state.expanded.has(i.key);
    const byClient = {};
    members.forEach((m) => (byClient[m.client_mac || m.key] ||= []).push(m));
    const memberHTML = members.length ? `
      <button class="toggle" aria-expanded="${open}" data-expand="${esc(i.key)}">${icon("chevron")}${open ? "Verberg" : "Toon"} onderliggende meldingen (${members.length})</button>
      ${open ? `<div class="members">${Object.values(byClient).map((ms) => `<div class="m">${sevBadge(ms[0].severity)}<div><b>${esc(ms[0].title.split(":")[0])}</b><span>${esc(ms.map((m) => m.detail.split(" op ")[0]).join(" · "))}</span></div><span class="m-act">${ms[0].reconnect ? reconnectBtn(ms[0].client_mac) : ""}${ms[0].client_mac ? `<button class="linkbtn" data-open="client" data-id="${esc(ms[0].client_mac)}">details</button>` : ""}</span></div>`).join("")}</div>` : ""}` : "";
    const when = issueWhen(i);
    const k = esc(i.key);
    const approveBtn = i.approve && !i.resolved_at ? `<button class="btn small" data-approve="${esc(i.approve)}">${icon("check")}Ken ik</button>` : "";
    const muteCtl = flat || i.resolved_at || i.group || i.approve ? "" : muteCtlHTML(i);
    const mutedBadge = i.muted ? badge("", i.muted_until ? `Genegeerd t/m ${new Date(i.muted_until * 1000).toLocaleDateString("nl-NL", { day: "numeric", month: "short" })}` : "Genegeerd (altijd)") : "";
    return `<article class="issue ${flat ? "flat" : ""} ${i.resolved_at ? "resolved" : ""} ${i.muted ? "muted" : ""}">
      <div class="sev ${i.severity}" aria-hidden="true">${icon(SEV[i.severity][1])}</div>
      <div>
        <div class="title">${esc(i.title)}</div>
        <div class="detail">${esc(i.detail)}</div>
        ${flat ? "" : `<div class="advice">${icon("bulb")}<span>${esc(i.advice)}</span></div>`}
        ${memberHTML}
      </div>
      <div class="meta">${i.resolved_at ? badge("ok", "Opgelost", "check") : sevBadge(i.severity)}${mutedBadge}${when}${approveBtn}${entityAction(i)}${muteCtl}</div>
    </article>`;
  }
  async function muteAction(e) {
    const m = e.target.closest("[data-mute]"), u = e.target.closest("[data-unmute]");
    if (!m && !u) return false;
    e.preventDefault();
    try {
      if (m) await fetch("/api/mute", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: m.dataset.mute, days: m.dataset.days ? +m.dataset.days : null }) });
      else await fetch("/api/unmute", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: u.dataset.unmute }) });   // geen DELETE: wordt door de UXG-IPS geblokkeerd
    } finally {
      await refresh();
      if (state.drawer) renderDrawer();
    }
    return true;
  }
  async function approveAction(e) {
    const b = e.target.closest("[data-approve]");
    if (!b) return false;
    e.preventDefault();
    b.disabled = true;
    try { await post(`/api/clients/${encodeURIComponent(b.dataset.approve)}/approve`, {}); await refresh(); if (state.drawer) renderDrawer(); }
    catch (err) { b.disabled = false; alert(err.message); }
    return true;
  }
  function bindIssueActions(root, rerender) {
    root.addEventListener("click", async (e) => {
      if (await approveAction(e)) return;
      if (await reconnectAction(e)) return;
      if (await muteAction(e)) return;
      const x = e.target.closest("[data-expand]");
      if (x) { const k = x.dataset.expand; state.expanded.has(k) ? state.expanded.delete(k) : state.expanded.add(k); rerender(); return; }
      const o = e.target.closest("[data-open]");
      if (o) openDrawer(o.dataset.open, o.dataset.id, o);
    });
  }

  // ------------------------------------------------------------------ overzicht
  function mountOverview() {
    mount("overzicht", `
      <div class="page-head"><div><h1>Netwerkoverzicht</h1><p class="subtitle" id="ov-sub"></p></div>${rangeSeg("ov-range")}</div>
      <div id="ov-banner"></div>
      <section class="grid kpis" id="ov-kpis" aria-label="Kerncijfers"></section>
      <section class="card me-card" id="ov-me" hidden aria-label="Dit apparaat"></section>
      <section class="grid cols-main" style="margin-bottom:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">Wat vraagt aandacht</h2><a href="#/issues" class="linkbtn">Alle issues</a></div><div class="issue-list" id="ov-issues"></div></div>
        <div class="card"><div class="card-head"><h2 style="margin:0">Netwerk</h2><span class="muted" id="ov-topo-sub"></span></div><div class="topo" id="ov-topo"></div></div>
      </section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h2 style="margin:0">Wifi per access point</h2><span class="muted">gemiddelden over 15 minuten · drempel bezetting ${nf(state.th.radio_cu_warn)}%</span></div><div class="table-wrap" style="border:0;background:none" id="ov-aps"></div></section>
      <section class="grid cols-2">
        <div class="card"><div class="card-head"><h3>Internetlatency</h3><span class="muted" id="ov-lat-sub"></span></div><div id="ch-lat"></div></div>
        <div class="card"><div class="card-head"><h3>Gemiddelde wifi-ervaring</h3><span class="muted">satisfaction-score 0–100</span></div><div id="ch-sat"></div></div>
      </section>`);
    bindRange("ov-range", loadOverviewCharts);
    bindIssueActions($("#ov-issues"), () => UPDATERS.overzicht());
    $("#ov-topo").addEventListener("click", (e) => { const n = e.target.closest("[data-open]"); if (n) openDrawer("device", n.dataset.id, n); });
    $("#ov-aps").addEventListener("click", (e) => { const n = e.target.closest("[data-open]"); if (n) openDrawer("device", n.dataset.id, n); });
    $("#ov-me").addEventListener("click", async (e) => {
      if (await reconnectAction(e)) return;
      const n = e.target.closest("[data-open]");
      if (n) openDrawer(n.dataset.open, n.dataset.id, n);
    });
  }
  // ---- het apparaat waarmee je kijkt (herkend aan je IP-adres)
  async function loadMe() {
    let d;
    try { d = await api("/api/me"); } catch (e) { return; }
    const el = $("#ov-me");
    if (!el || current !== "overzicht") return;
    if (!d.found) { el.hidden = true; return; }
    const c = d.client, up = d.uplink || {};
    const stat = (k, v) => `<div class="me-stat"><div class="k">${k}</div><div class="v">${v}</div></div>`;
    const where = c.wired
      ? stat("Bedraad via", `${up.mac ? `<button class="linkbtn plain" data-open="device" data-id="${esc(up.mac)}">${esc(up.name || "–")}</button>` : "–"}${c.sw_port ? ` <span class="muted">poort ${c.sw_port}</span>` : ""}`)
      : stat("Verbonden met", up.mac ? `<button class="linkbtn plain" data-open="device" data-id="${esc(up.mac)}">${esc(up.name || "–")}</button>` : "–") +
        stat("Band", `${esc(c.band || "–")} GHz <span class="muted">· kanaal ${esc(c.channel ?? "–")}</span>`) +
        stat("Signaal", signalBars(c.signal, c.band)) +
        stat("Snelheid", `${nf(c.tx_rate_mbps)} <span class="muted">/ ${nf(c.rx_rate_mbps)} Mbit/s</span>`);
    const roams = d.roams_today || [];
    const tip = !c.wired && c.band === "2.4" && c.signal != null && c.signal >= -60
      ? `<div class="me-hint">${icon("bulb")}<span>Je zit op 2.4 GHz terwijl het signaal sterk is. Kan dit apparaat ook 5 of 6 GHz, dan helpt <b>Opnieuw verbinden</b> vaak: het kiest dan opnieuw.</span></div>` : "";
    el.hidden = false;
    el.innerHTML = `<div class="me-row">
        <div class="me-id"><span class="me-ic">${icon(c.wired ? "cable" : "wifi")}</span><div>
          <div class="me-label">Dit apparaat${d.demo ? ` <span class="badge">demo</span>` : ""}</div>
          <div class="me-name">${esc(c.name)}</div>
          <div class="cell-sub">${esc(c.ip)}${c.ssid ? ` · ${esc(c.ssid)}` : ""}${c.assoc_ts ? ` · verbonden sinds ${stamp(c.assoc_ts)}` : ""}</div></div></div>
        <div class="me-stats">${where}${stat("Ervaring", c.satisfaction == null ? "–" : nf(c.satisfaction))}
          ${c.wired ? "" : stat("AP-wissels vandaag", `${roams.length}${roams[0] ? ` <span class="muted" title="${esc(roams.slice(0, 5).map((r) => `${hhmm(r.ts)} ${r.message.split(": ").pop()}`).join("\n"))}">laatst ${hhmm(roams[0].ts)}</span>` : ""}`)}</div>
        <div class="me-act"><button class="btn" data-open="client" data-id="${esc(c.mac)}">Details</button>${c.wired ? "" : `<button class="btn" data-reconnect="${esc(c.mac)}">Opnieuw verbinden</button>`}</div>
      </div>${tip}${d.issues?.length ? `<div class="me-issues">${d.issues.map((i) => sevBadge(i.severity) + `<span>${esc(i.title)}</span>`).join("")}</div>` : ""}`;
  }
  UPDATERS.overzicht = function () {
    loadMe();
    const s = state.snap, h = s.health;
    const devs = s.devices, online = devs.filter((d) => d.state === "online").length;
    const wifi = s.clients.filter((c) => !c.wired).length;
    const [lbl, lv] = scoreLabel(h.score);
    const types = { gateway: 0, switch: 0, ap: 0 };
    devs.forEach((d) => (types[d.type] = (types[d.type] || 0) + 1));
    $("#ov-sub").textContent = `${s.wan.isp || "Internet"} · ${devs.length} apparaten · ${s.clients.length} clients`;
    $("#ov-banner").innerHTML = state.status.mode === "mock"
      ? `<div class="banner">${icon("info")}<span>Je bekijkt <b>demodata</b> met een paar ingebouwde problemen. <a href="#/instellingen">Koppel je eigen UniFi-controller</a> om je eigen netwerk te zien.</span></div>`
      : state.status.last_error ? `<div class="banner err">${icon("octagon")}<span>Laatste poging mislukt: ${esc(state.status.last_error)}</span></div>` : "";
    $("#ov-kpis").innerHTML = `
      <div class="card compact kpi"><div class="label">${icon("gauge")}Netwerkscore</div><div class="value">${h.score}<small>/100</small></div>
        <div class="sub">${badge(lv, lbl)}</div><div class="scorebar"><span style="width:${h.score}%;background:var(--me-${lv === "ok" ? "success" : lv === "warning" ? "warning" : "danger"})"></span></div></div>
      <div class="card compact kpi clickable" data-go="issues" tabindex="0" role="link"><div class="label">${icon("alert")}Open issues</div><div class="value">${h.critical + h.warning + h.info}</div>
        <div class="sub">${h.critical ? badge("critical", `${h.critical} kritiek`) : ""}${h.warning ? badge("warning", `${h.warning} waarschuwing`) : ""}${h.info ? badge("info", `${h.info} info`) : ""}${!h.critical && !h.warning && !h.info ? badge("ok", "Alles in orde", "check") : ""}${h.muted ? badge("", `${h.muted} genegeerd`) : ""}</div></div>
      <div class="card compact kpi clickable" data-go="apparaten" tabindex="0" role="link"><div class="label">${icon("router")}Apparaten online</div><div class="value">${online}<small>/ ${devs.length}</small></div>
        <div class="sub"><span>${types.gateway} gateway</span><span>${types.switch} switches</span><span>${types.ap} AP's</span></div></div>
      <div class="card compact kpi clickable" data-go="clients" tabindex="0" role="link"><div class="label">${icon("users")}Clients</div><div class="value">${s.clients.length}</div>
        <div class="sub"><span>${icon("wifi")} ${wifi} wifi</span><span>${icon("cable")} ${s.clients.length - wifi} bedraad</span></div></div>
      <div class="card compact kpi clickable" data-go="internet" tabindex="0" role="link"><div class="label">${icon("globe")}Internet</div><div class="value">${s.wan.latency_ms == null ? "–" : nf(s.wan.latency_ms)}<small>ms</small></div>
        <div class="sub">${s.wan.up === false ? badge("critical", "Offline", "octagon") : badge("ok", "Online", "check")}<span>verlies ${nf(s.wan.loss_pct, 1)}%</span></div></div>`;
    $("#ov-kpis").querySelectorAll("[data-go]").forEach((n) => {
      const go = () => (location.hash = "#/" + n.dataset.go);
      n.onclick = go; n.onkeydown = (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), go());
    });

    const top = state.issues.filter((i) => !i.group && !i.resolved_at && !i.muted).slice(0, 6);
    $("#ov-issues").innerHTML = top.length ? top.map((i) => issueHTML(i, state.issues, true)).join("")
      : `<div class="empty">${icon("check")}<div>Geen problemen gevonden</div></div>`;

    // topologie
    const kids = {};
    devs.forEach((d) => (kids[d.uplink_mac || "root"] ||= []).push(d));
    const order = { gateway: 0, switch: 1, ap: 2 };
    const roots = devs.filter((d) => !d.uplink_mac || !devByMac()[d.uplink_mac]);
    let html = "";
    const walk = (d, lvl) => {
      const st = d.state !== "online" ? badge("critical", "Offline", "octagon")
        : d.issue_count ? badge(worstSev(d.mac), `${d.issue_count} issue${d.issue_count > 1 ? "s" : ""}`)
        : badge("ok", "OK", "check");
      html += `<div class="node clickable l${Math.min(lvl, 3)}" data-open data-id="${esc(d.mac)}" tabindex="0" role="button">
        <span class="ico">${icon(devIcon(d.type))}</span>
        <div><div class="name">${esc(d.name)}</div><div class="sub">${esc(d.model)} · ${d.num_clients} clients${d.client_issue_count ? ` · <span class="t-warning">${d.client_issue_count} client-meldingen</span>` : ""}</div></div>
        <div class="right">${st}</div></div>`;
      (kids[d.mac] || []).sort((a, b) => order[a.type] - order[b.type] || a.name.localeCompare(b.name)).forEach((k) => walk(k, lvl + 1));
    };
    roots.sort((a, b) => order[a.type] - order[b.type]).forEach((r) => walk(r, 0));
    $("#ov-topo").innerHTML = html;
    $("#ov-topo").querySelectorAll(".node").forEach((n) => (n.onkeydown = (e) => e.key === "Enter" && openDrawer("device", n.dataset.id, n)));
    $("#ov-topo-sub").textContent = `uptime gateway ${dur(devs.find((d) => d.type === "gateway")?.uptime)}`;

    // AP-tabel
    const aps = devs.filter((d) => d.type === "ap");
    const radioCell = (d, band) => {
      const r = d.radios.find((x) => x.radio === band);
      if (!r) return `<td class="muted">–</td>`;
      const lv = level("cu", r.cu_total);
      return `<td><div style="display:flex;gap:10px;align-items:center">${meter(r.cu_total, lv)}<span class="num ${lv !== "ok" ? "t-" + lv : ""}">${nf(r.cu_total)}%</span></div><div class="cell-sub">kanaal ${r.channel ?? "–"} · storing ${nf(r.interference)}% · retries ${nf(r.retry_pct, 1)}%</div></td>`;
    };
    $("#ov-aps").innerHTML = `<table><thead><tr><th>Access point</th><th class="r">Clients</th><th>2.4 GHz bezetting</th><th>5 GHz bezetting</th><th class="r">Ervaring</th><th>Status</th></tr></thead><tbody>
      ${aps.map((d) => `<tr data-open data-id="${esc(d.mac)}" tabindex="0"><td><div class="cell-name">${esc(d.name)}</div><div class="cell-sub">${esc(d.model)}</div></td>
        <td class="r num">${d.num_clients}</td>${radioCell(d, "2.4")}${radioCell(d, "5")}
        <td class="r num ${level("sat", d.satisfaction) !== "ok" ? "t-" + level("sat", d.satisfaction) : ""}">${nf(d.satisfaction)}</td>
        <td>${d.issue_count || d.client_issue_count ? badge(worstSev(d.mac, true), plural(d.issue_count + d.client_issue_count, "melding", "meldingen")) : badge("ok", "OK", "check")}</td></tr>`).join("")}
      </tbody></table>`;
    $("#ov-aps").querySelectorAll("tr[data-open]").forEach((n) => (n.onkeydown = (e) => e.key === "Enter" && openDrawer("device", n.dataset.id, n)));
    loadOverviewCharts();
  };
  async function loadOverviewCharts() {
    const d = await api(`/api/history/overview?hours=${state.hours}`);
    const lat = d.wan.map((p) => [p.t, p.latency_ms]);
    const vals = lat.map((p) => p[1]).filter((v) => v != null);
    $("#ov-lat-sub").textContent = vals.length ? `gem. ${nf(vals.reduce((a, b) => a + b, 0) / vals.length)} ms · max ${nf(Math.max(...vals))} ms` : "";
    MEcharts.lineChart($("#ch-lat"), { series: [{ name: "Latency", color: C.cyan, data: lat }], unit: " ms", yMin: 0, bucket: d.bucket,
      threshold: { value: state.th.wan_latency_warn, label: `drempel ${nf(state.th.wan_latency_warn)} ms` }, label: "Internetlatency in milliseconden" });
    MEcharts.lineChart($("#ch-sat"), { series: [{ name: "Ervaring", color: C.violet, data: d.clients.map((p) => [p.t, p.sat]) }], yMin: 0, yMax: 100, bucket: d.bucket,
      threshold: { value: state.th.client_satisfaction_warn, label: `drempel ${nf(state.th.client_satisfaction_warn)}` }, label: "Gemiddelde wifi-ervaring" });
  }

  // ------------------------------------------------------------------ issues
  function mountIssues() {
    const chips = (name, opts, cur) => opts.map(([v, l]) => `<button class="chip" data-${name}="${v}" aria-pressed="${cur === v}">${l}</button>`).join("");
    mount("issues", `
      <div class="page-head"><div><h1>Issues</h1><p class="subtitle">Automatisch gevonden problemen, met uitleg en advies. Gelijksoortige meldingen zijn samengevoegd tot één oorzaak.</p></div>
        <div class="chips"><button class="chip" id="is-muted" aria-pressed="${state.showMuted}">Genegeerd <span class="num" id="is-muted-n"></span></button>
        <button class="chip" id="is-resolved" aria-pressed="${state.showResolved}">${icon("clock")}Ook opgeloste tonen</button></div></div>
      <div class="toolbar">
        <div class="chips" role="group" aria-label="Ernst">${chips("sev", [["all", "Alles"], ["critical", "Kritiek"], ["warning", "Waarschuwing"], ["info", "Info"]], state.issueSev)}</div>
        <div class="chips" role="group" aria-label="Categorie">${chips("cat", [["all", "Alle categorieën"], ["wifi", "Wifi"], ["switch", "Switch"], ["device", "Apparaat"], ["wan", "Internet"], ["security", "Beveiliging"], ["config", "Configuratie"]], state.issueCat)}</div>
      </div>
      <div class="issue-list" id="is-list"></div>`);
    $("#view").querySelector(".toolbar").addEventListener("click", (e) => {
      const b = e.target.closest(".chip");
      if (!b) return;
      if (b.dataset.sev) state.issueSev = b.dataset.sev;
      if (b.dataset.cat) state.issueCat = b.dataset.cat;
      b.parentElement.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === b));
      UPDATERS.issues();
    });
    $("#is-resolved").onclick = async (e) => {
      state.showResolved = !state.showResolved;
      e.currentTarget.setAttribute("aria-pressed", state.showResolved);
      state.issues = await api(`/api/issues?state=${state.showResolved ? "all" : "open"}`);
      UPDATERS.issues();
    };
    $("#is-muted").onclick = (e) => {
      state.showMuted = !state.showMuted;
      e.currentTarget.setAttribute("aria-pressed", state.showMuted);
      UPDATERS.issues();
    };
    bindIssueActions($("#is-list"), () => UPDATERS.issues());
  }
  UPDATERS.issues = function () {
    const all = state.issues;
    const nMuted = all.filter((i) => i.muted && !i.group && !i.resolved_at).length;
    $("#is-muted-n").textContent = nMuted ? `(${nMuted})` : "";
    const list = all.filter((i) => !i.group || (i.resolved_at && !all.some((g) => g.key === i.group)))
      .filter((i) => (state.showMuted ? i.muted : !i.muted))
      .filter((i) => state.issueSev === "all" || i.severity === state.issueSev)
      .filter((i) => state.issueCat === "all" || i.category === state.issueCat);
    $("#is-list").innerHTML = list.length ? list.map((i) => issueHTML(i, all, false)).join("")
      : `<div class="card empty">${icon("check")}<div>${state.showMuted ? "Geen genegeerde meldingen" : "Geen issues voor deze filter"}</div></div>`;
  };

  // ------------------------------------------------------------------ apparaten
  const devView = { mode: store.get("dv.mode", "map"), clients: store.get("dv.clients", false) };
  function mountDevices() {
    mount("apparaten", `<div class="page-head"><div><h1>Apparaten</h1><p class="subtitle">Gateway, switches en access points. Klik voor details en historie.</p></div>
        <div class="w-head-r"><button class="chip" id="dv-cl" aria-pressed="${devView.clients}" ${devView.mode === "map" ? "" : "hidden"}>${icon("users")}Clients tonen</button>
        <div class="seg" role="group" aria-label="Weergave" id="dv-mode">${[["map", "Kaart"], ["list", "Lijst"]].map(([k, l]) => `<button data-m="${k}" aria-pressed="${devView.mode === k}">${l}</button>`).join("")}</div></div></div>
      <div id="dv-map" class="topo-scroll"></div><div id="dv-list"></div>`);
    for (const id of ["#dv-list", "#dv-map"]) {
      $(id).addEventListener("click", (e) => { const n = e.target.closest("[data-open]"); if (n) openDrawer(n.dataset.open === "client" ? "client" : "device", n.dataset.id, n); });
      $(id).addEventListener("keydown", (e) => { const n = e.target.closest("[data-open]"); if (n && e.key === "Enter") openDrawer(n.dataset.open === "client" ? "client" : "device", n.dataset.id, n); });
    }
    $("#dv-mode").addEventListener("click", (e) => {
      const b = e.target.closest("[data-m]"); if (!b) return;
      devView.mode = b.dataset.m; store.set("dv.mode", devView.mode);
      $("#dv-mode").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      $("#dv-cl").hidden = devView.mode !== "map";
      UPDATERS.apparaten();
    });
    $("#dv-cl").addEventListener("click", () => {
      devView.clients = !devView.clients; store.set("dv.clients", devView.clients);
      $("#dv-cl").setAttribute("aria-pressed", devView.clients);
      renderTopo();
    });
  }
  // ---- netwerkkaart: boom vanaf de gateway, per verbinding de poort en snelheid
  const linkTxt = (mb) => (!mb ? "" : mb >= 1000 ? `${mb % 1000 ? (mb / 1000).toFixed(1) : mb / 1000}G` : `${mb}M`);
  function renderTopo() {
    const el = $("#dv-map");
    if (!el || !state.snap) return;
    const devs = state.snap.devices, byMac = devByMac();
    const kids = {}, roots = [];
    devs.forEach((d) => { if (d.uplink_mac && byMac[d.uplink_mac] && d.uplink_mac !== d.mac) (kids[d.uplink_mac] ||= []).push(d); else roots.push(d); });
    Object.values(kids).forEach((a) => a.sort((x, y) => (x.uplink_port || 99) - (y.uplink_port || 99) || x.name.localeCompare(y.name)));
    roots.sort((a, b) => (a.type === "gateway" ? -1 : b.type === "gateway" ? 1 : 0));
    const cl = {};
    if (devView.clients) state.snap.clients.forEach((c) => { const m = c.wired ? c.sw_mac : c.ap_mac; if (m) (cl[m] ||= []).push(c); });
    const NW = 158, NH = 60, PER = 9, DOT = 12, MAXC = 36;
    let slot = 0, maxDepth = 0;
    const pos = {}, rows = {};
    const walk = (d, depth) => {
      maxDepth = Math.max(maxDepth, depth);
      const ch = kids[d.mac] || [];
      if (!ch.length) pos[d.mac] = { s: slot++, depth };
      else { ch.forEach((c) => walk(c, depth + 1)); const xs = ch.map((c) => pos[c.mac].s); pos[d.mac] = { s: (Math.min(...xs) + Math.max(...xs)) / 2, depth }; }
      const n = Math.min((cl[d.mac] || []).length, MAXC);
      rows[depth] = Math.max(rows[depth] || 0, Math.ceil(n / PER));
    };
    roots.forEach((r) => walk(r, 0));
    const ys = [];
    let yy = 8;
    for (let k = 0; k <= maxDepth; k++) { ys[k] = yy; yy += NH + 64 + (rows[k] ? rows[k] * (DOT + 4) + 8 : 0); }
    const W = Math.max(el.clientWidth - 2, slot * (NW + 26)), H = yy - 40;
    const colW = W / Math.max(1, slot);
    const X = (m) => colW * (pos[m].s + 0.5), Y = (m) => ys[pos[m].depth];
    const dotsH = (m) => { const n = Math.min((cl[m] || []).length, MAXC); return n ? Math.ceil(n / PER) * (DOT + 4) + 10 : 0; };
    const links = [], labels = [];
    for (const d of devs) {
      const p = d.uplink_mac && pos[d.uplink_mac] && pos[d.mac] ? byMac[d.uplink_mac] : null;
      if (!p) continue;
      const x1 = X(p.mac), y1 = Y(p.mac) + NH + dotsH(p.mac), x2 = X(d.mac), y2 = Y(d.mac), my = (y1 + y2) / 2;
      const wireless = d.uplink_type === "wireless";
      const slow = !wireless && d.uplink_speed && d.uplink_speed < 1000;
      const cls = d.state !== "online" ? "down" : slow ? "slow" : wireless ? "mesh" : "";
      links.push(`<path class="tl ${cls}" d="M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}"/>`);
      const txt = [d.uplink_port ? `poort ${d.uplink_port}` : "", wireless ? "draadloos" : linkTxt(d.uplink_speed)].filter(Boolean).join(" · ");
      if (txt) labels.push(`<div class="tlabel ${cls}" style="left:${x2}px;top:${y2 - 22}px">${esc(txt)}</div>`);
    }
    const sevCls = (d) => (d.state !== "online" ? "critical" : d.issue_count ? worstSev(d.mac) : "ok");
    const nodes = devs.filter((d) => pos[d.mac]).map((d) => {
      const x = X(d.mac) - NW / 2, y = Y(d.mac);
      const sub = d.type === "ap" ? `${d.num_clients} clients` : d.type === "switch" ? `${d.ports.filter((p) => p.up).length}/${d.ports.length} poorten · ${d.num_clients} clients` : d.model;
      const cs = (cl[d.mac] || []).slice().sort((a, b) => (a.signal ?? 0) - (b.signal ?? 0));
      const dots = cs.slice(0, MAXC).map((c, i) => {
        const lv = c.wired ? "wired" : level("signal", c.signal, c.band);
        const left = (i % PER) * (DOT + 4) - ((Math.min(cs.length, PER) * (DOT + 4) - 4) / 2) + NW / 2;
        return `<button class="tdot ${lv}" style="left:${left}px;top:${NH + 10 + Math.floor(i / PER) * (DOT + 4)}px" data-open="client" data-id="${esc(c.mac)}" title="${esc(c.name)}${c.wired ? " · bedraad" : ` · ${nf(c.signal)} dBm`}" aria-label="${esc(c.name)}"></button>`;
      }).join("") + (cs.length > MAXC ? `<span class="tmore" style="top:${NH + 10 + Math.ceil(MAXC / PER) * (DOT + 4)}px">+${cs.length - MAXC}</span>` : "");
      return `<div class="tnode sev-${sevCls(d)}" style="left:${x}px;top:${y}px;width:${NW}px">
        <button class="tcard" data-open="device" data-id="${esc(d.mac)}" aria-label="${esc(d.name)}"><span class="ico">${icon(devIcon(d.type))}</span>
          <span class="tt"><b>${esc(d.name)}</b><small>${esc(sub)}</small></span></button>${dots}</div>`;
    }).join("");
    el.innerHTML = `<div class="topo-map" style="width:${W}px;height:${H}px"><svg width="${W}" height="${H}" aria-hidden="true">${links.join("")}</svg>${labels.join("")}${nodes}</div>
      <div class="legend-row topo-legend"><span><i class="sw" style="background:var(--me-border-strong)"></i>bedraad</span><span><i class="sw" style="background:var(--me-warning)"></i>trager dan 1 Gbit/s</span>
        <span><i class="sw" style="background:var(--me-violet)"></i>draadloos (mesh)</span><span><i class="sw" style="background:var(--me-danger)"></i>offline</span>
        ${devView.clients ? `<span><i class="sw" style="background:var(--me-success)"></i>goed signaal</span><span><i class="sw" style="background:var(--me-warning)"></i>matig</span><span><i class="sw" style="background:var(--me-danger)"></i>zwak</span>` : ""}</div>`;
    hydrateIcons(el);
  }
  UPDATERS.apparaten = function () {
    const map = devView.mode === "map";
    $("#dv-map").hidden = !map; $("#dv-list").hidden = map;
    if (map) { renderTopo(); return; }
    const groups = [["gateway", "Gateway"], ["switch", "Switches"], ["ap", "Access points"]];
    $("#dv-list").innerHTML = groups.map(([t, label]) => {
      const ds = state.snap.devices.filter((d) => d.type === t);
      if (!ds.length) return "";
      return `<div class="section-title">${icon(devIcon(t))}${label} <span class="badge">${ds.length}</span></div>
        <div class="grid cards">${ds.map(deviceCard).join("")}</div>`;
    }).join("");
    markSelected();
  };
  function deviceCard(d) {
    const st = d.state !== "online" ? badge("critical", d.state, "octagon") : d.issue_count ? badge(worstSev(d.mac), `${d.issue_count} issue${d.issue_count > 1 ? "s" : ""}`, "alert") : badge("ok", "Online", "check");
    let extra = "";
    if (d.type === "ap") {
      extra = d.radios.map((r) => { const lv = level("cu", r.cu_total); return `<div style="display:grid;grid-template-columns:56px 1fr 44px;gap:8px;align-items:center;margin-top:8px"><span class="muted" style="font-size:12px">${r.radio} GHz</span>${meter(r.cu_total, lv)}<span class="num ${lv !== "ok" ? "t-" + lv : ""}" style="font-size:12px;text-align:right">${nf(r.cu_total)}%</span></div>`; }).join("");
      extra = `<div style="margin-top:14px"><div class="muted" style="font-size:12px">Kanaalbezetting</div>${extra}</div>`;
    } else if (d.type === "switch") {
      const up = d.ports.filter((p) => p.up).length;
      extra = `<div style="margin-top:14px"><div class="muted" style="font-size:12px;margin-bottom:6px">${up} van ${d.ports.length} poorten actief${d.poe_budget_w ? ` · PoE ${nf(d.poe_used_w)} / ${nf(d.poe_budget_w)} W` : ""}</div>${portGrid(d, true)}</div>`;
    } else if (d.type === "gateway") {
      const w = state.snap.wan;
      extra = `<div class="stats" style="margin-top:8px"><div class="stat"><div class="k">Latency</div><div class="v">${nf(w.latency_ms)} ms</div></div><div class="stat"><div class="k">Download</div><div class="v">${nf(w.xput_down)} Mb</div></div><div class="stat"><div class="k">Upload</div><div class="v">${nf(w.xput_up)} Mb</div></div></div>`;
    }
    return `<article class="card dev-card clickable" data-open data-id="${esc(d.mac)}" tabindex="0" role="button" aria-label="${esc(d.name)}">
      <div class="top"><span class="ico">${icon(devIcon(d.type))}</span><div style="min-width:0;flex:1"><h3>${esc(d.name)}</h3><div class="muted" style="font-size:12px">${esc(d.model)} · ${esc(d.ip)}</div></div>${st}</div>
      <div class="stats"><div class="stat"><div class="k">Clients</div><div class="v">${d.num_clients}</div></div><div class="stat"><div class="k">Uptime</div><div class="v">${dur(d.uptime)}</div></div><div class="stat"><div class="k">CPU / geh.</div><div class="v">${nf(d.cpu)}% / ${nf(d.mem)}%</div></div></div>
      ${extra}</article>`;
  }
  function portIssues(d) {
    const m = {};
    state.issues.filter((i) => !i.resolved_at && i.entity_type === "port" && i.entity_id.startsWith(d.mac + "#")).forEach((i) => {
      (m[+i.entity_id.split("#")[1]] ||= []).push(i);
    });
    return m;
  }
  function portGrid(d, compact) {
    const pi = portIssues(d);
    const cells = d.ports.map((p) => {
      const iss = pi[p.idx] || [];
      const cls = iss.some((i) => i.key.startsWith("port_flap") || i.key.startsWith("port_err")) ? "bad" : iss.length ? "slow" : p.up ? "up" : "";
      const tip = `${p.name} · ${p.up ? speed(p.speed) : "geen link"}${p.poe_w ? ` · PoE ${nf(p.poe_w, 1)} W` : ""}${iss.length ? " · " + iss.map((i) => i.title.split(": ").pop()).join(", ") : ""}`;
      return `<span class="port ${cls} ${p.media.startsWith("SFP") ? "sfp" : ""}" title="${esc(tip)}" ${compact ? "" : 'tabindex="0"'} aria-label="${esc(tip)}">${p.idx}${p.poe_w > 0 ? '<i class="poe"></i>' : ""}</span>`;
    }).join("");
    return `<div class="ports">${cells}</div>`;
  }

  // ------------------------------------------------------------------ clients
  function mountClients() {
    const uplinks = state.snap.devices.filter((d) => d.type !== "gateway");
    mount("clients", `
      <div class="page-head"><div><h1>Clients</h1><p class="subtitle" id="cl-sub"></p></div></div>
      <section class="card paused-card" id="cl-paused" hidden></section>
      <div class="toolbar">
        <label class="search"><span class="sr-only">Zoeken</span>${icon("search")}<input class="input" id="cl-q" placeholder="Zoek op naam, IP, MAC of fabrikant" value="${esc(state.cq)}"></label>
        <div class="chips" role="group" aria-label="Type" id="cl-kind">${[["all", "Alle"], ["wifi", "Wifi"], ["wired", "Bedraad"], ["issues", "Met problemen"]].map(([v, l]) => `<button class="chip" data-k="${v}" aria-pressed="${state.ckind === v}">${l}</button>`).join("")}</div>
        <label><span class="sr-only">Verbonden met</span><select class="input" id="cl-up"><option value="">Alle AP's en switches</option>${uplinks.map((d) => `<option value="${esc(d.mac)}" ${state.cuplink === d.mac ? "selected" : ""}>${esc(d.name)}</option>`).join("")}</select></label>
      </div>
      <div class="table-wrap" id="cl-table"></div>`);
    $("#cl-q").addEventListener("input", (e) => { state.cq = e.target.value; UPDATERS.clients(); });
    $("#cl-kind").addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      state.ckind = b.dataset.k; store.set("ckind", state.ckind);
      $("#cl-kind").querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === b));
      UPDATERS.clients();
    });
    $("#cl-up").addEventListener("change", (e) => { state.cuplink = e.target.value; UPDATERS.clients(); });
    $("#cl-table").addEventListener("click", (e) => {
      const s = e.target.closest("th button");
      if (s) { const k = s.dataset.sort; state.csort = { key: k, dir: state.csort.key === k ? -state.csort.dir : (k === "name" || k === "uplink" ? 1 : -1) }; store.set("csort", state.csort); UPDATERS.clients(); return; }
      const r = e.target.closest("tr[data-id]"); if (r) openDrawer("client", r.dataset.id, r);
    });
    $("#cl-table").addEventListener("keydown", (e) => { const r = e.target.closest("tr[data-id]"); if (r && e.key === "Enter") openDrawer("client", r.dataset.id, r); });
  }
  async function loadPauses() {
    let d;
    try { d = await api("/api/pauses"); } catch (e) { return; }
    const el = $("#cl-paused");
    if (!el || current !== "clients") return;
    el.hidden = !d.pauses.length;
    el.innerHTML = `<div class="card-head"><h2 style="margin:0">${icon("power")}Gepauzeerd</h2><span class="muted">geen internet of netwerk tot de tijd om is</span></div>
      ${d.pauses.map((p) => `<div class="rank-row paused-row"><div class="rank-main"><div class="rank-name">${esc(p.name)}</div>
        <div class="cell-sub">${p.until ? `tot ${stamp(p.until)} · nog ${dur(p.until - d.now)}` : "tot je hervat"} · sinds ${stamp(p.created)}</div></div>
        <button class="btn small" data-resume="${esc(p.mac)}">${icon("check")}Hervatten</button></div>`).join("")}`;
  }
  UPDATERS.clients = function () {
    loadPauses();
    const dm = devByMac();
    const q = state.cq.trim().toLowerCase();
    const uplinkName = (c) => (c.wired ? `${dm[c.sw_mac]?.name || "–"} · poort ${c.sw_port ?? "?"}`
      : c.connected === false ? `niet verbonden · laatst via ${dm[c.last_ap_mac]?.name || "?"}` : `${dm[c.ap_mac]?.name || "–"}`);
    let rows = state.snap.clients.filter((c) =>
      (state.ckind === "all" || (state.ckind === "wifi" && !c.wired) || (state.ckind === "wired" && c.wired) || (state.ckind === "issues" && c.issue_count))
      && (!state.cuplink || c.ap_mac === state.cuplink || c.sw_mac === state.cuplink)
      && (!q || [c.name, c.ip, c.mac, c.vendor].some((v) => (v || "").toLowerCase().includes(q))));
    const key = {
      name: (c) => c.name.toLowerCase(), uplink: (c) => uplinkName(c).toLowerCase(), signal: (c) => c.signal ?? 999,
      retry: (c) => c.retry_pct ?? -1, sat: (c) => c.satisfaction ?? 999, rate: (c) => c.tx_rate_mbps ?? -1,
      issues: (c) => (c.issue_count || 0) * 1000 - (c.satisfaction ?? 100),
    }[state.csort.key] || ((c) => c.name);
    rows.sort((a, b) => { const x = key(a), y = key(b); return (x < y ? -1 : x > y ? 1 : 0) * state.csort.dir; });
    const wifi = state.snap.clients.filter((c) => !c.wired).length;
    const bad = state.snap.clients.filter((c) => c.issue_count).length;
    $("#cl-sub").textContent = `${state.snap.clients.length} verbonden · ${wifi} wifi · ${state.snap.clients.length - wifi} bedraad · ${bad} met problemen`;
    const th = (k, l, cls = "") => `<th class="${cls}" ${state.csort.key === k ? `aria-sort="${state.csort.dir > 0 ? "ascending" : "descending"}"` : ""}><button data-sort="${k}">${l}${state.csort.key === k ? (state.csort.dir > 0 ? " ↑" : " ↓") : ""}</button></th>`;
    $("#cl-table").innerHTML = rows.length ? `<table><thead><tr>${th("name", "Naam")}${th("uplink", "Verbonden met")}${th("signal", "Signaal")}${th("retry", "Retries", "r")}${th("sat", "Ervaring", "r")}${th("rate", "Snelheid", "r")}<th>IP</th>${th("issues", "Status")}</tr></thead><tbody>
      ${rows.map((c) => {
        const rl = level("retry", c.retry_pct), sl = level("sat", c.satisfaction);
        return `<tr data-id="${esc(c.mac)}" tabindex="0" ${state.drawer?.id === c.mac ? 'aria-selected="true"' : ""}>
          <td><div class="cell-name">${esc(c.name)}</div><div class="cell-sub">${esc(c.vendor || c.mac)}</div></td>
          <td><div style="display:flex;gap:8px;align-items:center">${icon(c.wired ? "cable" : "wifi")}<div><div>${esc(uplinkName(c))}</div><div class="cell-sub">${c.wired ? "bedraad" : c.connected === false ? `${c.last_seen ? ago(c.last_seen) + " geleden gezien" : "even weg"}` : `${c.band} GHz · kanaal ${c.channel} · ${proto(c.proto)}`}</div></div></div></td>
          <td>${c.wired ? '<span class="muted">–</span>' : signalBars(c.signal, c.band)}</td>
          <td class="r num ${rl && rl !== "ok" ? "t-" + rl : ""}">${c.retry_pct == null ? "–" : nf(c.retry_pct, 1) + "%"}</td>
          <td class="r num ${sl && sl !== "ok" ? "t-" + sl : ""}">${nf(c.satisfaction)}</td>
          <td class="r num">${c.wired ? "–" : nf(c.tx_rate_mbps) + " Mbit/s"}</td>
          <td class="num muted">${esc(c.ip)}</td>
          <td>${c.connected === false ? badge("", "Niet verbonden") : c.issue_count ? badge(c.score < 70 ? "critical" : "warning", `${c.issue_count} probleem${c.issue_count > 1 ? "en" : ""}`, "alert") : badge("ok", "OK", "check")}</td></tr>`;
      }).join("")}</tbody></table>` : `<div class="empty">Geen clients gevonden</div>`;
  };

  // ------------------------------------------------------------------ internet
  const net = { hours: store.get("net.hours", 24), live: [], timer: null, data: null, last: null, wasRunning: false,
                usage: null, usagePeriod: store.get("net.usage", "day") };
  const mb = (bps) => (bps == null ? null : bps / 1e6);
  const mbTxt = (v) => (v == null ? "–" : nf(v, v < 10 ? 1 : 0));
  const dateTxt = (t, withTime) => new Date(t * 1000).toLocaleString("nl-NL", withTime ? { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "short" });
  function mountInternet() {
    mount("internet", `
      <div class="page-head"><div><h1>Internet</h1><p class="subtitle" id="net-sub">Live verkeer en de snelheid van je verbinding.</p></div>
        <div class="seg" role="group" aria-label="Periode" id="net-range">${[[6, "6 u"], [24, "24 u"], [168, "7 d"]].map(([h, l]) => `<button data-h="${h}" aria-pressed="${net.hours === h}">${l}</button>`).join("")}</div></div>
      <div id="net-banner"></div>
      <section class="grid kpis net-kpis" id="net-kpis" aria-label="Internet nu"></section>
      <section class="grid cols-main" style="margin-bottom:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">Live verkeer</h2><span class="muted" id="net-live-sub"></span></div><div id="net-live"></div>
          <p class="help" style="margin:8px 0 0">De gateway geeft zijn tellers om de 10 à 45 seconden door aan UniFi; daarom springt de lijn in stapjes.</p></div>
        <div class="card" id="net-test" aria-live="polite"></div>
      </section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h3>Internetverkeer</h3><span class="muted" id="net-hist-sub"></span></div><div id="net-hist"></div></section>
      <section class="card" style="margin-bottom:16px" id="net-usage"><div class="card-head"><h3>Datagebruik</h3>
          <div class="seg" role="group" aria-label="Per dag of per maand" id="net-usage-seg">${[["day", "Per dag"], ["month", "Per maand"]].map(([k, l]) => `<button data-p="${k}" aria-pressed="${net.usagePeriod === k}">${l}</button>`).join("")}</div></div>
        <div class="usage-kpis" id="net-usage-kpis"></div><div id="net-usage-chart"></div>
        <p class="help" id="net-usage-note" style="margin:8px 0 0"></p></section>
      <section class="card"><div class="card-head"><h3>Speedtests</h3><span class="muted" id="net-st-sub">afgelopen 90 dagen</span></div><div id="net-st-chart"></div>
        <div class="table-wrap" style="border:0;margin-top:12px" id="net-st-table"></div></section>`);
    $("#net-range").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-h]"); if (!b) return;
      net.hours = +b.dataset.h; store.set("net.hours", net.hours);
      $("#net-range").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      loadInternet();
    });
    $("#net-test").addEventListener("click", (e) => { if (e.target.closest("[data-st=start]")) startSpeedtest(); });
    $("#net-usage-seg").addEventListener("click", (e) => {
      const b = e.target.closest("[data-p]"); if (!b) return;
      net.usagePeriod = b.dataset.p; store.set("net.usage", net.usagePeriod);
      $("#net-usage-seg").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      renderUsage();
    });
    net.live = []; net.last = null;
    api("/api/internet?hours=0.25").then((d) => {   // de live-grafiek begint met het laatste kwartier
      net.live = d.series.filter((p) => p.rx != null).map((p) => ({ t: p.t + 30, rx: mb(p.rx), tx: mb(p.tx) }));
      drawLive();
    }).catch(() => {});
    liveLoop();
  }
  UPDATERS.internet = () => loadInternet();
  async function loadInternet() {
    let d;
    try { d = await api(`/api/internet?hours=${net.hours}`); } catch (e) { return; }
    if (current !== "internet") return;
    net.data = d;
    const w = d.wan || {};
    $("#net-sub").textContent = [w.isp, w.link_mbps ? `WAN-poort ${speed(w.link_mbps)}` : null, "live verkeer en snelheid"].filter(Boolean).join(" · ");
    $("#net-banner").innerHTML = d.available ? "" : `<div class="banner err">${icon("info")}<span>Live verkeer en speedtests zijn alleen beschikbaar via de uitgebreide UniFi-API (API-key of lokaal account).</span></div>`;
    $("#net-hist-sub").textContent = `gemiddeld per ${d.bucket >= 3600 ? d.bucket / 3600 + " uur" : d.bucket / 60 + " min"}`;
    MEcharts.lineChart($("#net-hist"), { series: [
      { name: "Download", color: C.cyan, data: d.series.map((p) => [p.t, mb(p.rx)]) },
      { name: "Upload", color: C.violet, data: d.series.map((p) => [p.t, mb(p.tx)]) }],
      unit: " Mbit/s", yMin: 0, bucket: d.bucket, label: "Internetverkeer in Mbit/s",
      xfmt: net.hours > 48 ? (t) => dateTxt(t) : undefined });
    const st = d.speedtests;
    $("#net-st-sub").textContent = st.length ? `${plural(st.length, "test", "tests")} in de afgelopen 90 dagen` : "afgelopen 90 dagen";
    MEcharts.lineChart($("#net-st-chart"), { series: [
      { name: "Download", color: C.cyan, data: st.map((r) => [r.ts, r.down]) },
      { name: "Upload", color: C.violet, data: st.map((r) => [r.ts, r.up]) }],
      unit: " Mbit/s", yMin: 0, bucket: 86400 * 4, markers: true, label: "Speedtest-resultaten",
      xfmt: (t) => dateTxt(t), tfmt: (t) => dateTxt(t, true) });
    $("#net-st-table").innerHTML = st.length ? `<table><thead><tr><th>Wanneer</th><th class="r">Download</th><th class="r">Upload</th><th class="r">Ping</th><th>Server</th></tr></thead><tbody>
      ${st.slice(-10).reverse().map((r) => `<tr style="cursor:default"><td class="num">${dateTxt(r.ts, true)}</td><td class="r num">${mbTxt(r.down)} Mbit/s</td><td class="r num">${mbTxt(r.up)} Mbit/s</td><td class="r num">${r.latency == null ? "–" : nf(r.latency) + " ms"}</td><td class="muted">${esc(r.server || "–")}</td></tr>`).join("")}</tbody></table>`
      : `<div class="empty">Nog geen speedtests. Start er hierboven een.</div>`;
    renderNetKpis(); renderTest(); loadUsage();
  }
  async function loadUsage() {
    try { net.usage = await api("/api/usage"); } catch (e) { return; }
    if (current === "internet") renderUsage();
  }
  const gb = (b) => (b == null ? "–" : b >= 1e12 ? `${nf(b / 1e12, 2)} TB` : b >= 1e9 ? `${nf(b / 1e9, b >= 1e11 ? 0 : 1)} GB` : `${nf(b / 1e6)} MB`);
  function renderUsage() {
    const u = net.usage;
    if (!u || !$("#net-usage-chart")) return;
    const tile = (label, v, sub) => `<div class="usage-kpi"><div class="k">${label}</div><div class="v">${v ? gb(v.rx + v.tx) : "–"}</div><div class="cell-sub">${v ? `↓ ${gb(v.rx)} · ↑ ${gb(v.tx)}` : ""}${sub ? ` · ${sub}` : ""}</div></div>`;
    const tm = u.this_month, lm = u.last_month;
    const pace = tm && u.avg_day ? (() => {   // verwachting voor de hele maand op basis van het gemiddelde per dag
      const d = new Date(), days = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
      return `verwacht ~${gb((u.avg_day.rx + u.avg_day.tx) * days)}`;
    })() : "";
    $("#net-usage-kpis").innerHTML = tile("Vandaag", u.today, "tot nu") + tile("Deze maand", tm, pace) + tile("Vorige maand", lm) +
      tile("Gemiddeld per dag", u.avg_day, "laatste 30 dagen");
    const rows = net.usagePeriod === "month" ? u.months.slice(-24) : u.days.slice(-60);
    const running = rows.length && rows[rows.length - 1].ts === (net.usagePeriod === "month" ? u.month0 : u.day0) ? rows.length - 1 : -1;
    const toGb = (b) => b / 1e9;
    MEcharts.barChart($("#net-usage-chart"), {
      labels: rows.map((r) => r.ts), highlight: running, height: 210,
      series: [{ name: "Download", color: C.cyan, data: rows.map((r) => toGb(r.rx)) }, { name: "Upload", color: C.violet, data: rows.map((r) => toGb(r.tx)) }],
      fmt: (v) => `${nf(v, v < 10 && v > 0 ? 1 : 0)} GB`, label: `Datagebruik ${net.usagePeriod === "month" ? "per maand" : "per dag"}`,
      xfmt: (t) => new Date(t * 1000).toLocaleDateString("nl-NL", net.usagePeriod === "month" ? { month: "short", year: "2-digit" } : { day: "numeric", month: "short" }),
      tfmt: (t) => new Date(t * 1000).toLocaleDateString("nl-NL", net.usagePeriod === "month" ? { month: "long", year: "numeric" } : { weekday: "long", day: "numeric", month: "long" }),
    });
    $("#net-usage-note").textContent = u.error ? `Ophalen lukte niet: ${u.error}`
      : u.since ? `Gegevens van je gateway sinds ${new Date(u.since * 1000).toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" })}. Sonar bewaart ze zelf, dus de historie groeit vanaf nu.` : "";
  }
  const normal = (key) => {   // wat is normaal voor deze verbinding: mediaan van de tests
    const v = (net.data?.speedtests || []).map((r) => r[key]).filter(Boolean).sort((a, b) => a - b);
    return v.length ? v[Math.floor(v.length / 2)] : null;
  };
  function renderNetKpis() {
    const L = net.last, d = net.data;
    if (!$("#net-kpis") || !d) return;
    const last = d.speedtests[d.speedtests.length - 1];
    const fresh = L ? Math.max(0, Math.round(L.now - L.updated)) : null;
    const kpi = (ic, label, v, unit, ref, sub) => {
      const pct = ref && v != null ? Math.min(100, (100 * v) / ref) : null;
      return `<div class="card compact kpi"><div class="label">${icon(ic)}${label}</div><div class="value">${mbTxt(v)}<small>${unit}</small></div>
        ${pct != null ? `<div class="scorebar" title="${nf(pct)}% van wat de verbinding haalt"><span style="width:${pct}%"></span></div>` : ""}<div class="sub">${sub}</div></div>`;
    };
    const live = L ? `<span class="live-dot" aria-hidden="true"></span>${fresh < 5 ? "zojuist" : `${dur(fresh)} geleden`}` : "laden…";
    $("#net-kpis").innerHTML =
      kpi("activity", "Download nu", mb(L?.rx_bps), "Mbit/s", normal("down"), live) +
      kpi("activity", "Upload nu", mb(L?.tx_bps), "Mbit/s", normal("up"), normal("up") ? `van ~${mbTxt(normal("up"))} Mbit/s` : "") +
      `<div class="card compact kpi"><div class="label">${icon("clock")}Latency</div><div class="value">${L?.latency_ms == null ? "–" : nf(L.latency_ms)}<small>ms</small></div><div class="sub">naar internet</div></div>` +
      `<div class="card compact kpi"><div class="label">${icon("gauge")}Laatste speedtest</div><div class="value">${last ? mbTxt(last.down) : "–"}<small>/ ${last ? mbTxt(last.up) : "–"} Mbit/s</small></div>
        <div class="sub">${last ? `${dateTxt(last.ts, true)} · ping ${nf(last.latency)} ms` : "nog niet gemeten"}</div></div>`;
  }
  const PHASES = [["ping", "Ping"], ["download", "Download"], ["upload", "Upload"]];
  function renderTest() {
    const root = $("#net-test");
    if (!root || !net.data) return;
    const t = net.last?.test || net.data.speedtest || {};
    const g = net.last?.speedtest || {};
    const last = net.data.speedtests[net.data.speedtests.length - 1];
    const nd = normal("down");
    if (t.running) {
      const at = PHASES.findIndex(([k]) => k === g.phase);
      root.innerHTML = `<div class="card-head"><h2 style="margin:0">Speedtest</h2><span class="badge info"><span class="live-dot"></span>bezig</span></div>
        <ol class="st-steps">${PHASES.map(([k, l], i) => {
          const val = i < at ? (k === "ping" ? (g.latency != null ? `${nf(g.latency)} ms` : "") : g[k === "download" ? "down" : "up"] != null ? `${mbTxt(g[k === "download" ? "down" : "up"])} Mbit/s` : "") : "";
          return `<li class="${at < 0 ? (i === 0 ? "active" : "") : i < at ? "done" : i === at ? "active" : ""}">${i < at ? icon("check") : `<span>${i + 1}</span>`}${l}${val ? `<b class="num st-val">${val}</b>` : ""}</li>`;
        }).join("")}</ol>
        <p class="muted">Je gateway meet nu de snelheid van je internetverbinding. Dit duurt 15 tot 30 seconden.</p>`;
      return;
    }
    const res = last ? `<div class="st-result"><div><div class="k">Download</div><div class="v">${mbTxt(last.down)}<small>Mbit/s</small></div></div>
        <div><div class="k">Upload</div><div class="v">${mbTxt(last.up)}<small>Mbit/s</small></div></div>
        <div><div class="k">Ping</div><div class="v">${last.latency == null ? "–" : nf(last.latency)}<small>ms</small></div></div></div>
        <p class="muted" style="margin:6px 0 0">${dateTxt(last.ts, true)}${nd && last.down < 0.8 * nd ? ` · <span class="t-warning">lager dan normaal (~${mbTxt(nd)} Mbit/s)</span>` : nd ? ` · normaal ~${mbTxt(nd)} Mbit/s` : ""}</p>` : "";
    root.innerHTML = `<div class="card-head"><h2 style="margin:0">Speedtest</h2></div>${res}
      ${t.error ? `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(t.error)}</span></div>` : ""}
      <div class="wiz-actions" style="margin-top:16px"><button class="btn primary" data-st="start" ${net.data.available ? "" : "disabled"}>${icon("gauge")}Start speedtest</button></div>
      <p class="help">De test draait op je gateway zelf en meet dus je echte internetverbinding, los van wifi of dit apparaat. Duurt 15 tot 30 seconden en gebruikt even je volledige bandbreedte.</p>`;
  }
  async function startSpeedtest() {
    const b = $("[data-st=start]");
    if (b) { b.disabled = true; b.textContent = "Starten…"; }
    try {
      await post("/api/speedtest", {});
      net.last = { ...(net.last || {}), test: { running: true }, speedtest: { phase: "ping" } };
      net.wasRunning = true;
      renderTest(); liveLoop();
    } catch (e) {
      net.data.speedtest = { error: e.message };
      if (net.last) net.last.test = { error: e.message };
      renderTest();
    }
  }
  function drawLive() {
    if (!$("#net-live")) return;
    const cut = Date.now() / 1000 - 15 * 60;
    net.live = net.live.filter((p) => p.t >= cut);
    MEcharts.lineChart($("#net-live"), { series: [
      { name: "Download", color: C.cyan, data: net.live.map((p) => [p.t, p.rx]) },
      { name: "Upload", color: C.violet, data: net.live.map((p) => [p.t, p.tx]) }],
      unit: " Mbit/s", yMin: 0, bucket: 60, label: "Live internetverkeer in Mbit/s", tfmt: (t) => new Date(t * 1000).toLocaleTimeString("nl-NL") });
    $("#net-live-sub").textContent = "laatste 15 minuten";
  }
  async function liveLoop() {
    clearTimeout(net.timer);
    if (current !== "internet") return;
    try {
      const L = await api("/api/live/wan");
      const prev = net.last;
      net.last = L;
      if (!prev || prev.updated !== L.updated) { net.live.push({ t: L.updated, rx: mb(L.rx_bps), tx: mb(L.tx_bps) }); drawLive(); }
      renderNetKpis();
      if (net.wasRunning && !L.test.running) { net.wasRunning = false; loadInternet(); }
      else if (L.test.running) { net.wasRunning = true; renderTest(); }
    } catch (e) {
      $("#net-live-sub").textContent = e.message;
    }
    net.timer = setTimeout(liveLoop, net.last?.test?.running ? 1500 : 3000);
  }

  // ------------------------------------------------------------------ beveiliging
  const secState = { hours: store.get("sec.hours", 24), scope: "all", ignored: false };
  const ignMenu = (opts) => `<details class="mute ign"><summary class="mutebtn">Negeren</summary><div class="mute-menu" role="group" aria-label="Negeren">${opts.map(([l, o]) => `<button data-ign="${esc(JSON.stringify(o))}">${l}</button>`).join("")}</div></details>`;
  const catLabel = (c) => (c || "").replace(/^emerging-/, "").replace(/-/g, " ");
  function mountSecurity() {
    mount("beveiliging", `
      <div class="page-head"><div><h1>Beveiliging</h1><p class="subtitle">Wat de IPS op je gateway tegenhield, wat er openstaat naar internet en hoe je netwerken van elkaar gescheiden zijn. Aanvallen van buiten zijn normaal; blokkades van <b>eigen apparaten</b> verdienen aandacht.</p></div>
        <div class="seg" role="group" aria-label="Periode" id="sec-range">${[[24, "24 u"], [168, "7 d"], [336, "14 d"]].map(([h, l]) => `<button data-h="${h}" aria-pressed="${secState.hours === h}">${l}</button>`).join("")}</div></div>
      <div id="sec-banner"></div>
      <section class="grid kpis" id="sec-kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))"></section>
      <section class="grid cols-2" style="margin-bottom:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">Meest geraakte regels</h2></div><div class="rank" id="sec-sigs"></div></div>
        <div class="card"><div class="card-head"><h2 style="margin:0">Bronnen</h2></div><div class="rank" id="sec-srcs"></div></div>
      </section>
      <section class="card" style="margin-bottom:16px" id="sec-seg-card"><div class="card-head"><h2 style="margin:0">Netwerkscheiding</h2><span class="muted" id="sec-seg-sub"></span></div>
        <div class="seg-nets" id="sec-seg-nets"></div><div id="sec-seg-matrix"></div><div id="sec-seg-issues"></div></section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h2 style="margin:0">Open naar internet</h2><span class="muted" id="sec-expo-sub"></span></div><div id="sec-expo"></div></section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h3>Blokkades in de tijd</h3><span class="muted" id="sec-bucket"></span></div><div id="sec-chart"></div></section>
      <div class="toolbar"><div class="chips" role="group" aria-label="Bron" id="sec-scope">${[["all", "Alles"], ["internal", "Eigen apparaten"], ["external", "Van buiten"]].map(([v, l]) => `<button class="chip" data-s="${v}" aria-pressed="${secState.scope === v}">${l}</button>`).join("")}</div>
        <button class="chip" id="sec-ignored" aria-pressed="${secState.ignored}">Genegeerde tonen <span class="num" id="sec-ignored-n"></span></button></div>
      <div class="table-wrap" id="sec-table"></div>
      <section class="card" style="margin-top:16px" id="sec-ign-card" hidden><div class="card-head"><h3>Negeerregels</h3><span class="muted">tellen niet mee in de cijfers en geven geen meldingen</span></div><div id="sec-ign"></div></section>`);
    $("#sec-range").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-h]"); if (!b) return;
      secState.hours = +b.dataset.h; store.set("sec.hours", secState.hours);
      $("#sec-range").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      UPDATERS.beveiliging();
    });
    $("#sec-scope").addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      secState.scope = b.dataset.s;
      $("#sec-scope").querySelectorAll(".chip").forEach((x) => x.setAttribute("aria-pressed", x === b));
      UPDATERS.beveiliging();
    });
    $("#sec-ignored").onclick = (e) => { secState.ignored = !secState.ignored; e.currentTarget.setAttribute("aria-pressed", secState.ignored); UPDATERS.beveiliging(); };
    bindIssueActions($("#sec-seg-issues"), renderSegIssues);
    bindFlow($("#sec-seg-matrix"));
  }
  // ------------------------------------------------------------------ netwerkscheiding
  let segData = null;
  const SEG_KIND = { main: ["Hoofdnetwerk", "home"], iot: ["Slimme apparaten", "plug"], other: ["Apart netwerk", "layers"], guest: ["Gasten", "users"] };
  async function loadSegments() {
    try { segData = await api("/api/segments"); } catch { segData = null; }
    if (current !== "beveiliging") return;
    renderSegments();
  }
  function segIssues() {
    return (state.issues || []).filter((i) => (i.key.startsWith("segment:") || i.key.startsWith("segment_open:")) && !i.resolved_at)
      .sort((a, b) => (a.muted - b.muted) || (a.key.startsWith("segment_open:") ? -1 : 0));
  }
  function renderSegIssues() {
    const el = $("#sec-seg-issues"); if (!el || !segData || !segData.available) return;
    const all = segIssues(), open = all.filter((i) => !i.muted), muted = all.length - open.length;
    const hasApart = segData.segments.some((s) => s.kind === "iot" || s.kind === "other");
    const shown = state.segShowMuted ? all : open;
    el.innerHTML = `<div class="seg-sub-head"><h3>${hasApart ? "Slimme apparaten op je hoofdnetwerk" : "Advies"}</h3>
        ${muted ? `<button class="chip" id="seg-muted" aria-pressed="${!!state.segShowMuted}">Genegeerde tonen <span class="num">(${muted})</span></button>` : ""}</div>
      ${shown.length ? segListHTML(shown, all)
        : `<div class="empty">${icon("check")}<div>${hasApart ? "Alle herkende slimme apparaten staan op een apart netwerk" : "Niets te melden"}</div></div>`}`;
    const b = $("#seg-muted");
    if (b) b.onclick = () => { state.segShowMuted = !state.segShowMuted; renderSegIssues(); };
  }
  // Per apparaat één regel; het (steeds gelijke) verhuisadvies staat er één keer boven.
  function segListHTML(shown, all) {
    const general = shown.filter((i) => !i.key.startsWith("segment:") || i.key === "segment:none");
    const devs = shown.filter((i) => !general.includes(i));
    const cli = cliByMac();
    const target = (segData.segments.find((s) => s.kind === "iot") || segData.segments.find((s) => s.kind === "other") || {}).name || "het aparte netwerk";
    return `${general.length ? `<div class="issue-list" style="margin-bottom:12px">${general.map((i) => issueHTML(i, all)).join("")}</div>` : ""}
      ${devs.length ? `<div class="advice seg-advice">${icon("bulb")}<span><b>Verhuizen naar ${esc(target)}:</b> wifi-apparaten in UniFi bij het apparaat → Settings → Virtual Network Override (kan op dezelfde SSID). Daarna stellen alle access points zich opnieuw in en valt de wifi ongeveer een minuut weg, dus verhuis ze in één keer. Bekabelde apparaten via de switchpoort (Port Manager → Native VLAN/Network). Pas daarna het nieuwe IP-adres aan in Home Assistant of de app die het aanstuurt. Hoort een apparaat bewust hier? Kies Negeren → Altijd.</span></div>
      <div class="seg-devs">${devs.map((i) => {
        const c = cli[i.client_mac] || {};
        const why = (i.detail.match(/\(([^)]+)\)/) || [])[1] || "";
        const via = c.wired ? `bekabeld · ${devName(c.sw_mac)}${c.sw_port ? ` poort ${c.sw_port}` : ""}` : c.ap_mac ? `wifi · ${devName(c.ap_mac)}` : "";
        return `<div class="seg-dev ${i.muted ? "muted" : ""}"><span class="seg-dev-ico">${icon(c.wired ? "cable" : "wifi")}</span>
          <div style="min-width:0"><div class="seg-name">${esc(c.name || i.title.replace(" staat op je hoofdnetwerk", ""))}</div><div class="cell-sub">${esc([why, via, c.ip].filter(Boolean).join(" · "))}</div></div>
          <div class="seg-dev-act">${i.muted ? badge("", "Genegeerd") : ""}${i.client_mac ? `<button class="linkbtn" data-open="client" data-id="${esc(i.client_mac)}">Bekijk</button>` : ""}${muteCtlHTML(i)}</div></div>`;
      }).join("")}</div>` : ""}`;
  }
  function ruleText(r) {
    const what = r.targets.length ? r.targets.join(", ") : r.to === "any" ? "alles" : r.to;
    const port = r.port ? ` · poort ${r.port}${r.proto ? " " + r.proto : ""}` : r.proto ? ` · ${r.proto}` : "";
    if (r.forward) return `${r.upnp ? "UPnP-mapping" : "port forward"} naar ${what}${port}`;
    const from = r.sources && r.sources.length ? ` · alleen vanaf ${r.sources.join(", ")}` : "";
    return `${r.action === "allow" ? "toegestaan" : "geblokkeerd"} naar ${what}${port}${from}`;
  }
  function renderSegments() {
    const d = segData;
    if (!d || !d.available) {
      $("#sec-seg-sub").textContent = "";
      $("#sec-seg-nets").innerHTML = `<p class="muted">Netwerken en firewallzones zijn alleen te zien via de uitgebreide UniFi-API (API-key of lokaal account).</p>`;
      $("#sec-seg-issues").innerHTML = $("#sec-seg-matrix").innerHTML = "";
      return;
    }
    const nets = d.segments;
    $("#sec-seg-sub").textContent = `${nets.length} netwerk${nets.length === 1 ? "" : "en"}${d.matrix ? ` · ${d.matrix.zones.length} firewallzones` : ""}`;
    $("#sec-seg-nets").innerHTML = nets.map((n) => {
      const [label, ic] = SEG_KIND[n.kind] || SEG_KIND.other;
      const iso = n.isolated === true ? badge("ok", "Afgeschermd", "lock") : n.isolated === false ? badge("warning", "Niet afgeschermd", "alert") : "";
      return `<div class="seg-net">
        <div class="seg-net-head"><span class="seg-ico">${icon(ic)}</span><div style="min-width:0"><div class="seg-name">${esc(n.name)}</div><div class="cell-sub">${esc(label)}</div></div></div>
        <div class="seg-facts"><span>VLAN <b class="num">${n.vlan ?? "1"}</b></span>${n.subnet ? `<span class="num">${esc(n.subnet)}</span>` : ""}${n.zone ? `<span>zone <b>${esc(n.zone)}</b></span>` : ""}</div>
        <div class="seg-count"><span class="num">${nf(n.clients)}</span> apparaten<span class="muted"> · ${nf(n.wifi)} wifi · ${nf(n.wired)} bekabeld</span></div>
        <div class="seg-badges">${iso}${n.smart ? `<span class="muted">${nf(n.smart)} herkend als slim apparaat</span>` : ""}</div></div>`;
    }).join("");
    renderSegIssues();
    renderFlowBlock();
  }
  function matrixHTML(m) {
    const srcs = m.zones.filter((z) => z.networks && z.key !== "external");
    const cell = (a, b) => m.cells[`${a.id}>${b.id}`];
    const rows = srcs.map((a) => `<tr style="cursor:default"><th scope="row">${esc(a.name)}</th>${m.zones.map((b) => {
      const c = cell(a, b);
      if (a.id === b.id && a.networks < 2) return `<td class="mx-na" title="Binnen één netwerk gaat verkeer niet via de firewall">–</td>`;
      if (!c || !c.effective) return `<td class="mx-na">?</td>`;
      const n = c.rules.filter((r) => r.enabled).length;
      const lbl = c.effective === "allow" ? "Open" : "Dicht";
      const tip = `${a.name} → ${b.name}: ${c.effective === "allow" ? "toegestaan" : "geblokkeerd"}${n ? `, met ${n} eigen regel${n > 1 ? "s" : ""}` : ""}`;
      return `<td class="mx ${c.effective}" title="${esc(tip)}"><span class="mx-pill">${c.effective === "block" ? icon("lock") : ""}${lbl}</span>${n ? `<span class="mx-n">+${n}</span>` : ""}</td>`;
    }).join("")}</tr>`).join("");
    const exc = [];
    srcs.forEach((a) => m.zones.forEach((b) => { const c = cell(a, b); if (c && c.rules.length) exc.push([a, b, c]); }));
    return `<p class="cell-sub" style="margin:0 0 8px">Per firewallzone · rij = van, kolom = naar · standaard plus je eigen regels</p>
      <div class="table-wrap mx-wrap"><table class="mx-table"><thead><tr><th scope="col"><span class="sr-only">Van</span></th>${m.zones.map((z) => `<th scope="col">${esc(z.key === "external" ? "Internet" : z.name)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>
      ${exc.length ? `<div class="mx-exc">${exc.map(([a, b, c]) => `<div class="mx-exc-row"><div class="mx-exc-pair">${esc(a.name)} → ${esc(b.key === "external" ? "Internet" : b.name)}<div class="cell-sub">standaard ${c.default === "allow" ? "open" : "dicht"}</div></div>
        <ul>${c.rules.map((r) => `<li class="${r.enabled ? "" : "off"}"><b>${esc(r.name)}</b> <span class="muted">${esc(ruleText(r))}${r.enabled ? "" : " · uitgeschakeld"}</span></li>`).join("")}</ul></div>`).join("")}</div>` : ""}`;
  }

  // ------------------------------------------------------------------ toegang tussen netwerken (diagram)
  const FL = { sel: store.get("fl.sel", null), edge: null, view: store.get("fl.view", "diagram"), key: "", ro: null, w: 0 };
  const FL_ICON = { main: "home", iot: "plug", other: "layers", guest: "users", vpn: "key", gateway: "router", internet: "globe" };
  const FL_SUB = { main: "hoofdnetwerk", iot: "slimme apparaten", other: "apart netwerk", guest: "gasten", vpn: "VPN", gateway: "router", internet: "buitenwereld" };
  const FL_ST = { allow: ["mag", "check"], partial: ["deels", "alert"], block: ["geblokkeerd", "x"] };
  const trunc = (t, n) => (t.length > n ? t.slice(0, n - 1) + "…" : t);

  function renderFlowBlock() {
    const el = $("#sec-seg-matrix"), d = segData;
    if (!el || !d || !d.available) return;
    if (!d.matrix || !d.flows) {
      FL.key = "";
      el.innerHTML = `<p class="muted" style="margin-top:16px">Wat er tussen je netwerken mag, is alleen te zien met de zone-gebaseerde firewall (UniFi Network 9 of nieuwer).</p>`;
      return;
    }
    const key = FL.view + JSON.stringify(d.flows) + (FL.view === "tabel" ? JSON.stringify(d.matrix) : "");
    if (key === FL.key && el.firstChild) return;   // niets veranderd: laat selectie en animatie staan
    FL.key = key;
    el.innerHTML = `
      <div class="seg-sub-head"><div><h3>Toegang tussen netwerken</h3>
          <div class="cell-sub">Wat er mag bij een nieuwe verbinding, nagerekend uit je firewallregels op volgorde. Kies een netwerk voor zijn pijlen, of een pijl voor de regels die het bepalen.</div></div>
        <div class="seg" role="group" aria-label="Weergave" id="fl-view">${[["diagram", "Diagram"], ["tabel", "Tabel"]].map(([v, l]) => `<button data-flview="${v}" aria-pressed="${FL.view === v}">${l}</button>`).join("")}</div></div>
      ${FL.view === "tabel" ? matrixHTML(d.matrix) : `<div class="fl-canvas" id="fl-canvas"></div>
        <div class="fl-legend" aria-hidden="true">${["allow", "partial", "block"].map((st) => `<span class="fl-leg ${st}"><svg width="34" height="10" viewBox="0 0 34 10"><path d="M1 5 H${st === "block" ? 30 : 27}"/>${st === "block" ? `<rect x="30" y="0" width="3" height="10" rx="1"/>` : `<path class="hd" d="M25 1 L33 5 L25 9 z"/>`}</svg>${icon(FL_ST[st][1])}${FL_ST[st][0]}</span>`).join("")}</div>
        <div class="fl-detail" id="fl-detail" aria-live="polite"></div>`}`;
    if (FL.view !== "tabel") {
      drawFlow();
      if (FL.ro) FL.ro.disconnect();
      FL.ro = new ResizeObserver(() => { const c = $("#fl-canvas"); if (c && Math.abs(c.clientWidth - FL.w) > 4) drawFlow(); });
      FL.ro.observe($("#fl-canvas"));
    }
  }

  // Het gekozen netwerk staat in het midden, de rest in een vaste volgorde in een ring eromheen (internet boven).
  // Alle pijlen zijn dan stralen vanuit het midden en kruisen geen blokken. Smal scherm: gekozen netwerk links,
  // de rest in een kolom rechts.
  const FL_ORDER = { internet: 0, gateway: 1, main: 2, iot: 3, other: 4, guest: 5, vpn: 6 };
  function flLayout(nodes, W, sel) {
    const ring = nodes.filter((n) => n.id !== sel).sort((a, b) => (FL_ORDER[a.kind] ?? 9) - (FL_ORDER[b.kind] ?? 9));
    const pos = {}, N = ring.length;
    if (W < 560) {
      const nw = Math.min(150, Math.floor((W - 64) / 2)), nh = 52, gap = 66;
      ring.forEach((n, i) => { pos[n.id] = [W - nw / 2 - 9, nh / 2 + 9 + i * gap]; });
      const H = nh + 18 + (N - 1) * gap;
      pos[sel] = [nw / 2 + 9, H / 2];
      return { pos, H, nw, nh, center: pos[sel] };
    }
    const nw = 156, nh = 58, cx = W / 2;
    const rx = Math.min(W / 2 - nw / 2 - 16, 340), ry = Math.max(150, Math.min(230, N * 34)), cy = nh / 2 + 6 + ry;
    ring.forEach((n, i) => {
      const t = (-90 + i * 360 / Math.max(1, N)) * Math.PI / 180;
      pos[n.id] = [cx + rx * Math.cos(t), cy + ry * Math.sin(t)];
    });
    pos[sel] = [cx, cy];
    return { pos, H: cy + ry + nh / 2 + 6, nw, nh, center: pos[sel] };
  }
  function flClip(p, w, h, t) {   // punt op de rand van een blok (met wat lucht) in de richting van t
    const dx = t[0] - p[0], dy = t[1] - p[1];
    const s = Math.min(1, dx ? (w / 2 + 7) / Math.abs(dx) : Infinity, dy ? (h / 2 + 7) / Math.abs(dy) : Infinity);
    return [p[0] + dx * s, p[1] + dy * s];
  }
  function flPath(a, b, both, w, h) {   // heen en terug buigen vanzelf naar verschillende kanten
    const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L, half = both ? 13 : 5;
    const c = [(a[0] + b[0]) / 2 + nx * half * 2, (a[1] + b[1]) / 2 + ny * half * 2];
    const p0 = flClip(a, w, h, c), p1 = flClip(b, w, h, c), f = (v) => v.toFixed(1);
    return { d: `M${f(p0[0])},${f(p0[1])} Q${f(c[0])},${f(c[1])} ${f(p1[0])},${f(p1[1])}`, len: L };
  }

  function flNodeHTML(n, x, y, nw, nh, on, compact) {
    const sub = n.kind !== "vpn" && n.kind !== "gateway" && n.kind !== "internet" && n.clients != null
      ? `${nf(n.clients)} apparaten` : FL_SUB[n.kind] || "";
    const tx = compact ? 13 : 51, maxc = Math.floor((nw - tx - (n.isolated ? 24 : 8)) / 7.4);
    return `<g class="fl-node ${n.kind}${on ? " sel" : ""}" data-node="${esc(n.id)}" tabindex="0" role="button" aria-pressed="${on}"
        aria-label="${esc(`${n.name}${n.isolated ? ", afgeschermd" : ""}`)}" style="transform:translate(${(x - nw / 2).toFixed(1)}px,${(y - nh / 2).toFixed(1)}px)">
      <title>${esc(n.name)}${n.subnet ? ` · ${esc(n.subnet)}` : ""}</title>
      <rect width="${nw}" height="${nh}" rx="14"/>
      ${compact ? "" : `<rect class="fl-ico-bg" x="11" y="${nh / 2 - 15}" width="30" height="30" rx="9"/>
      <svg class="fl-ico" x="17" y="${nh / 2 - 9}" width="18" height="18" viewBox="0 0 24 24">${ICONS[FL_ICON[n.kind]] || ""}</svg>`}
      <text class="fl-name" x="${tx}" y="${nh / 2 - 2}">${esc(trunc(n.name, maxc))}</text>
      <text class="fl-sub" x="${tx}" y="${nh / 2 + 14}">${esc(trunc(sub, Math.floor((nw - tx - 6) / 6.3)))}</text>
      ${n.isolated ? `<svg class="fl-lock" x="${nw - 21}" y="8" width="13" height="13" viewBox="0 0 24 24"><title>Afgeschermd</title>${ICONS.lock}</svg>` : ""}
    </g>`;
  }

  function drawFlow(animate) {
    const canvas = $("#fl-canvas"), fl = segData && segData.flows;
    if (!canvas || !fl) return;
    const W = Math.max(260, canvas.clientWidth);
    FL.w = canvas.clientWidth;
    const byId = Object.fromEntries(fl.nodes.map((n) => [n.id, n]));
    if (!byId[FL.sel]) FL.sel = (fl.nodes.find((n) => n.kind === "main") || fl.nodes[0]).id;
    const sel = FL.sel;
    const { pos, H, nw, nh } = flLayout(fl.nodes, W, sel);
    const edges = fl.edges.map((e, i) => ({ ...e, i })).filter((e) => e.from === sel || e.to === sel);
    if (FL.edge != null && !edges.some((e) => e.i === FL.edge)) FL.edge = null;
    const pairs = new Set(edges.map((e) => `${e.from}>${e.to}`));
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    edges.sort((a, b) => (a.i === FL.edge) - (b.i === FL.edge));
    const lines = edges.map((e) => {
      const { d, len } = flPath(pos[e.from], pos[e.to], pairs.has(`${e.to}>${e.from}`), nw, nh);
      const lbl = `${byId[e.from].name} naar ${byId[e.to].name}: ${FL_ST[e.status][0]}`;
      return `<g class="fl-edge ${e.status}${e.i === FL.edge ? " on" : ""}">
        <path class="fl-line" d="${d}" marker-end="url(#fl-m-${e.status})"/>
        ${!reduce && e.status !== "block" ? `<circle class="fl-dot" r="2.6"><animateMotion dur="${(len / 75 + 1.2).toFixed(1)}s" repeatCount="indefinite" path="${d}"/></circle>` : ""}
        <path class="fl-hit" d="${d}" data-edge="${e.i}" tabindex="0" role="button" aria-label="${esc(lbl)}"><title>${esc(lbl)}</title></path></g>`;
    }).join("");
    const svg = canvas.querySelector("svg.fl-svg");
    const same = svg && +svg.dataset.w === W && svg.dataset.nodes === fl.nodes.map((n) => n.id).join("|");
    if (same && animate && !reduce) {
      // Blokken schuiven naar hun nieuwe plek; de pijlen komen er daarna bij.
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("height", H.toFixed(0));
      svg.querySelectorAll(".fl-node").forEach((g) => {
        const id = g.dataset.node, [x, y] = pos[id], on = id === sel;
        g.style.transform = `translate(${(x - nw / 2).toFixed(1)}px,${(y - nh / 2).toFixed(1)}px)`;
        g.classList.toggle("sel", on); g.setAttribute("aria-pressed", on);
      });
      const eg = svg.querySelector(".fl-edges");
      eg.classList.add("hidden");
      clearTimeout(FL.t);
      FL.t = setTimeout(() => { eg.innerHTML = lines; eg.classList.toggle("has-on", FL.edge != null); eg.classList.remove("hidden"); }, 420);
    } else if (same) {
      const eg = svg.querySelector(".fl-edges");
      eg.innerHTML = lines; eg.classList.toggle("has-on", FL.edge != null); eg.classList.remove("hidden");
    } else {
      canvas.innerHTML = `<svg class="fl-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H.toFixed(0)}" data-w="${W}" data-nodes="${esc(fl.nodes.map((n) => n.id).join("|"))}" role="group" aria-label="Toegang tussen netwerken">
        <defs>${["allow", "partial"].map((st) => `<marker id="fl-m-${st}" class="fl-mk ${st}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="10" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto"><path d="M0,1 L9,5 L0,9 z"/></marker>`).join("")}
          <marker id="fl-m-block" class="fl-mk block" viewBox="0 0 10 12" refX="8" refY="6" markerWidth="10" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><rect x="6" y="0" width="3" height="12" rx="1.5"/></marker></defs>
        <g class="fl-edges${FL.edge != null ? " has-on" : ""}">${lines}</g>
        <g class="fl-nodes">${fl.nodes.map((n) => flNodeHTML(n, pos[n.id][0], pos[n.id][1], nw, nh, n.id === sel, W < 560)).join("")}</g></svg>`;
    }
    renderFlowDetail(fl, byId, edges);
  }

  function renderFlowDetail(fl, byId, edges) {
    const el = $("#fl-detail"); if (!el) return;
    const pill = (st) => `<span class="fl-pill ${st}">${icon(FL_ST[st][1])}${FL_ST[st][0]}</span>`;
    const e = edges.find((x) => x.i === FL.edge);
    if (e) {
      const a = byId[e.from], b = byId[e.to], wn = flWelNiet(e, b);
      const col = (kind, title, items) => `<div class="fl-wn ${kind}"><div class="fl-wn-h">${icon(kind === "wel" ? "check" : "x")}${title}</div>
        <ul>${items.map((it) => `<li><span>${esc(it.what)}</span>${it.how ? `<span class="fl-how">${esc(it.how)}</span>` : ""}${it.name ? `<div class="cell-sub">regel: ${esc(it.name)}</div>` : ""}</li>`).join("")}</ul></div>`;
      el.innerHTML = `<div class="fl-det-head"><b>${esc(a.name)} → ${esc(b.name)}</b>${pill(e.status)}<button class="linkbtn" data-fl-close>Sluiten</button></div>
        <div class="fl-wn-grid">${col("wel", "Wel", wn.wel)}${col("niet", "Niet", wn.niet)}</div>
        <div class="cell-sub" style="margin-top:10px">Standaard ${e.default === "allow" ? "toegestaan" : "geblokkeerd"}${a.zone && b.zone ? ` (zone ${esc(a.zone)} → ${esc(b.zone)})` : ""}${e.rules.length ? `, aangevuld met ${e.rules.length} eigen regel${e.rules.length > 1 ? "s" : ""}.` : ", zonder eigen regels."}
          ${wn.base === "block" ? ` Antwoorden op verbindingen die ${esc(b.name)} zelf begint, komen wel terug.` : ""}</div>`;
      return;
    }
    const n = byId[FL.sel];
    const group = (list, dirTo) => ["allow", "partial", "block"].map((st) => {
      const xs = list.filter((x) => x.status === st);
      if (!xs.length) return "";
      const names = xs.map((x) => {
        const other = byId[dirTo ? x.to : x.from].name;
        if (st !== "partial") return esc(other);
        const wn = flWelNiet(x, byId[x.to]);
        const short = (wn.base === "block" ? wn.wel : wn.niet).map((it) => it.what + (it.how ? ` ${it.how}` : "")).join(", ");
        return `${esc(other)} <span class="muted">(${wn.base === "block" ? "alleen" : "behalve"} ${esc(short)})</span>`;
      });
      return `<div class="fl-sum-row">${pill(st)}<span>${names.join(", ")}</span></div>`;
    }).join("");
    const out = edges.filter((x) => x.from === n.id), inc = edges.filter((x) => x.to === n.id);
    el.innerHTML = `<div class="fl-sum">
      ${out.length ? `<div><div class="fl-sum-h">Vanaf ${esc(n.name)} naar</div>${group(out, true)}</div>` : ""}
      ${inc.length ? `<div><div class="fl-sum-h">Naar ${esc(n.name)} vanaf</div>${group(inc, false)}</div>` : ""}</div>`;
  }

  // Wat mag er wel en niet over deze pijl? Uit de standaard plus de regels op volgorde.
  function flWelNiet(e, b) {
    const isWhole = (r) => !r.forward && !r.ips.length && !(r.src_ips || []).length && !r.port && !r.proto;
    const whole = e.rules.find(isWhole);
    const base = whole ? whole.action : e.default;
    const item = (r) => ({
      what: r.targets && r.targets.length ? r.targets.join(", ") : r.to === "any" ? `alles in ${b.name}` : r.to,
      how: [r.port ? `poort ${r.port}${r.proto ? " " + r.proto : ""}` : r.proto || "",
            r.sources && r.sources.length ? `alleen vanaf ${r.sources.join(", ")}` : "",
            r.forward ? (r.upnp ? "UPnP" : "port forward") : ""].filter(Boolean).join(" · "),
      name: r.forward ? r.name : r.name });
    const exc = e.rules.filter((r) => r !== whole);
    const rest = { what: exc.length ? "al het andere" : `alles naar ${b.name}`, how: "", name: whole ? whole.name : "" };
    const wel = exc.filter((r) => r.action === "allow").map(item), niet = exc.filter((r) => r.action === "block").map(item);
    if (base === "allow") wel.push(rest); else niet.push(rest);
    return { base, wel: wel.length ? wel : [{ what: "niets", how: "", name: "" }], niet: niet.length ? niet : [{ what: "niets", how: "", name: "" }] };
  }

  function bindFlow(root) {
    const act = (t) => {
      const v = t.closest("[data-flview]");
      if (v) { FL.view = v.dataset.flview; store.set("fl.view", FL.view); FL.key = ""; renderFlowBlock(); return true; }
      const n = t.closest("[data-node]");
      if (n) { const moved = FL.sel !== n.dataset.node; FL.sel = n.dataset.node; FL.edge = null; store.set("fl.sel", FL.sel); drawFlow(moved); return true; }
      const e = t.closest("[data-edge]");
      if (e) { FL.edge = FL.edge === +e.dataset.edge ? null : +e.dataset.edge; drawFlow(); return true; }
      if (t.closest("[data-fl-close]")) { FL.edge = null; drawFlow(); return true; }
      return false;
    };
    root.addEventListener("click", (ev) => { if (act(ev.target)) ev.preventDefault(); });
    root.addEventListener("keydown", (ev) => {
      if ((ev.key === "Enter" || ev.key === " ") && ev.target.closest("[data-node],[data-edge]") && act(ev.target)) ev.preventDefault();
      if (ev.key === "Escape" && FL.edge != null) { FL.edge = null; drawFlow(); }
    });
  }
  $("#view").addEventListener("click", async (e) => { if (current === "clients") await pauseAction(e); });
  $("#view").addEventListener("click", async (e) => {   // één keer gebonden; #view blijft bestaan
    const g = e.target.closest("[data-ign]"), u = e.target.closest("[data-unign]");
    if ((!g && !u) || current !== "beveiliging") return;
    e.preventDefault();
    try {
      if (g) await post("/api/ips/ignore", JSON.parse(g.dataset.ign));
      else await post("/api/ips/unignore", { id: +u.dataset.unign });
    } catch (err) { alert(err.message); }
    UPDATERS.beveiliging();
  });
  function exposureHTML(x) {
    if (!x) return `<p class="muted">Port forwards en UPnP zijn alleen te zien via de uitgebreide UniFi-API (API-key of lokaal account).</p>`;
    const f = x.forwards;
    if (!f.length) return `<div class="empty">${icon("check")}<div>Geen port forwards en geen actieve UPnP-mappings</div></div>`;
    return `<div class="table-wrap" style="border:0"><table><thead><tr><th>Naam</th><th>Poort op internet</th><th>Naar</th><th>Soort</th><th class="r">Aanvallen</th><th>Status</th></tr></thead><tbody>
      ${f.map((r) => `<tr style="cursor:default" class="${r.enabled ? "" : "off"}"><td class="cell-name">${esc(r.name)}</td>
        <td class="num">${esc(r.port)}<span class="muted"> ${esc(r.proto)}</span></td>
        <td>${esc(r.target_name || r.fwd_ip)}<div class="cell-sub">${esc(r.fwd_ip)}:${esc(r.fwd_port || r.port)}</div></td>
        <td>${r.upnp ? badge("info", "UPnP") : badge("", "Vast")}${r.src && r.src !== "any" ? `<div class="cell-sub">alleen ${esc(r.src)}</div>` : ""}</td>
        <td class="r num ${r.attacks >= 10 ? "t-warning" : ""}">${r.enabled ? nf(r.attacks) : "–"}</td>
        <td>${r.enabled ? badge("warning", "Open", "globe") : badge("", "Uit")}</td></tr>`).join("")}</tbody></table></div>`;
  }
  const srcLabel = (e) => `${esc(e.src_name && e.src_name !== e.src_ip ? e.src_name : e.src_ip)}${e.src_name && e.src_name !== e.src_ip ? `<div class="cell-sub">${esc(e.src_ip)}</div>` : ""}`;
  UPDATERS.beveiliging = async function () {
    loadSegments();
    const d = await api(`/api/ips?hours=${secState.hours}&scope=${secState.scope}&ignored=${secState.ignored}`);
    if (current !== "beveiliging") return;
    const s = d.summary;
    $("#sec-banner").innerHTML = d.available === false
      ? `<div class="banner err">${icon("info")}<span>IPS-gegevens zijn alleen beschikbaar via de uitgebreide UniFi-API (API-key of lokaal account).</span></div>` : "";
    const per = secState.hours <= 24 ? "24 uur" : secState.hours <= 168 ? "7 dagen" : "14 dagen";
    $("#sec-kpis").innerHTML = `
      <div class="card compact kpi"><div class="label">${icon("shield")}Blokkades</div><div class="value">${nf(s.total)}</div><div class="sub">afgelopen ${per}</div></div>
      <div class="card compact kpi"><div class="label">${icon("globe")}Van buiten</div><div class="value">${nf(s.external)}</div><div class="sub">tegengehouden door de IPS</div></div>
      <div class="card compact kpi"><div class="label">${icon("home")}Van eigen apparaten</div><div class="value">${nf(s.internal)}</div>
        <div class="sub">${s.internal ? badge("warning", "Bekijken", "alert") : badge("ok", "Geen", "check")}</div></div>
      <div class="card compact kpi"><div class="label">${icon("users")}Unieke bronnen</div><div class="value">${nf(s.sources)}</div><div class="sub">IP-adressen</div></div>`;
    const max1 = Math.max(1, ...d.by_signature.map((x) => x.count)), max2 = Math.max(1, ...d.by_source.map((x) => x.count));
    const srcName = (x) => (x.name && x.name !== x.ip ? `${x.name} (${x.ip})` : x.ip);
    $("#sec-sigs").innerHTML = d.by_signature.length ? d.by_signature.map((x) => `
      <div class="rank-row"><div class="rank-main"><div class="rank-name" title="${esc(x.signature)}">${esc(x.signature)}</div><div class="cell-sub">${esc(catLabel(x.category))}${x.sid ? ` · SID ${x.sid}` : ""}</div></div>
        <div class="rank-bar">${meter(100 * x.count / max1)}</div><span class="num rank-n">${x.count}</span>
        <span>${x.sid ? ignMenu([["Negeer deze regel", { sid: x.sid, label: x.signature }]]) : ""}</span></div>`).join("")
      : `<div class="empty">${icon("check")}<div>Niets geblokkeerd in deze periode</div></div>`;
    $("#sec-srcs").innerHTML = d.by_source.length ? d.by_source.map((x) => `
      <div class="rank-row"><div class="rank-main"><div class="rank-name">${esc(srcName(x))}</div><div class="cell-sub">${x.internal ? badge("warning", "eigen netwerk", "home") : badge("", "internet", "globe")} ${esc(x.net || "")}</div></div>
        <div class="rank-bar">${meter(100 * x.count / max2, x.internal ? "warning" : "")}</div><span class="num rank-n">${x.count}</span>
        <span>${ignMenu([["Negeer dit adres", { ip: x.ip, label: srcName(x) }]])}</span></div>`).join("")
      : `<div class="empty">Geen bronnen</div>`;
    $("#sec-expo-sub").textContent = d.exposure ? (d.exposure.upnp_enabled ? "UPnP staat aan" : d.exposure.upnp_enabled === false ? "UPnP staat uit" : "") + ` · aanvallen in de afgelopen ${per}` : "";
    $("#sec-expo").innerHTML = exposureHTML(d.exposure);
    $("#sec-ignored-n").textContent = s.ignored ? `(${s.ignored})` : "";
    $("#sec-ign-card").hidden = !d.ignores.length;
    $("#sec-ign").innerHTML = d.ignores.map((r) => `<div class="rank-row ign-row"><div class="rank-main"><div class="rank-name">${esc(r.label || (r.ip || "") + (r.sid ? " SID " + r.sid : ""))}</div>
      <div class="cell-sub">${r.ip && r.sid ? `regel ${r.sid} voor ${esc(r.ip)}` : r.ip ? `alle regels voor ${esc(r.ip)}` : `regel ${r.sid}, alle adressen`} · sinds ${new Date(r.created * 1000).toLocaleDateString("nl-NL", { day: "numeric", month: "short" })}</div></div>
      <button class="linkbtn" data-unign="${r.id}">Niet meer negeren</button></div>`).join("");
    $("#sec-bucket").textContent = d.bucket === 3600 ? "per uur" : "per 6 uur";
    MEcharts.lineChart($("#sec-chart"), { series: [
      { name: "Van buiten", color: C.cyan, data: d.series.map((p) => [p.t, p.external]) },
      { name: "Eigen apparaten", color: C.amber, data: d.series.map((p) => [p.t, p.internal]) }],
      yMin: 0, bucket: d.bucket, fmt: (v) => nf(v), label: "Aantal IPS-blokkades" });
    const ev = d.events;
    $("#sec-table").innerHTML = ev.length ? `<table><thead><tr><th>Tijd</th><th>Bron</th><th>Doel</th><th>Regel</th><th>Risico</th><th><span class="sr-only">Acties</span></th></tr></thead><tbody>
      ${ev.map((e) => `<tr style="cursor:default"><td class="num"><div>${hhmm(e.ts)}</div><div class="cell-sub">${new Date(e.ts * 1000).toLocaleDateString("nl-NL", { day: "numeric", month: "short" })}</div></td>
        <td>${e.internal ? `<span class="t-warning">${icon("home", "")}</span> ` : ""}${srcLabel(e)}<div class="cell-sub">${esc(e.src_net || "")}</div></td>
        <td>${esc(e.dst_name || e.dst_ip)}${e.dst_port ? `<span class="muted">:${e.dst_port}</span>` : ""}<div class="cell-sub">${esc([e.proto, e.service].filter(Boolean).join(" · "))}</div></td>
        <td style="white-space:normal;min-width:240px"><div>${esc(e.signature)}</div><div class="cell-sub">${esc(catLabel(e.category))}${e.sid ? ` · SID ${e.sid}` : ""}</div></td>
        <td>${badge(e.risk === "high" ? "critical" : e.risk === "medium" ? "warning" : "", e.risk || "–")}${e.ignored ? ` ${badge("", "genegeerd")}` : ""}</td>
        <td>${e.ignored ? "" : ignMenu([...(e.sid ? [["Deze regel voor dit adres", { ip: e.src_ip, sid: e.sid, label: `${e.signature} · ${e.src_name || e.src_ip}` }], ["Deze regel overal", { sid: e.sid, label: e.signature }]] : []), ["Dit adres", { ip: e.src_ip, label: e.src_name || e.src_ip }]])}</td></tr>`).join("")}</tbody></table>`
      : `<div class="empty">${icon("check")}<div>Geen blokkades voor deze filter</div></div>`;
  };

  // ------------------------------------------------------------------ setup-wizard
  const wiz = { step: 1, address: "", api_key: "", username: "", password: "", site: "default", verify_tls: false,
                current_api_key: "", result: null, error: null, busy: false, info: null };
  async function showWizard(step) {
    document.body.classList.add("setup");
    $("#status").innerHTML = `<span class="dot off"></span>Nog niet gekoppeld`;
    wiz.info = await api("/api/setup").catch(() => ({}));
    if (step) wiz.step = step;
    if (wiz.info.configured && wiz.step === 2 && !wiz.address) {
      wiz.address = (wiz.info.controller_url || "").replace(/^https:\/\//, "");
      wiz.site = wiz.info.site || "default";
      wiz.verify_tls = !!wiz.info.verify_tls;
    }
    $("#view").dataset.mounted = "wizard";
    renderWizard();
  }
  const field = (id, label, input, help) => `<div class="field"><label for="${id}">${label}</label>${input}${help ? `<div class="help">${help}</div>` : ""}</div>`;
  function renderWizard() {
    const steps = ["Welkom", "Koppelen", "Controleren"];
    const reconf = wiz.info?.configured;
    const head = `<div class="wiz-brand"><span class="logo">${icon("radar")}</span><div><div class="wiz-title">UniFi Sonar</div><div class="muted">${reconf ? "Koppeling wijzigen" : "Eerste keer instellen"}</div></div></div>
      <ol class="wiz-steps" aria-label="Stappen">${steps.map((s, i) => `<li ${i + 1 === wiz.step ? 'aria-current="step"' : ""} class="${i + 1 < wiz.step ? "done" : ""}"><span>${i + 1}</span>${s}</li>`).join("")}</ol>`;
    let body = "";
    if (wiz.step === 1) {
      body = `<h1>Welkom</h1>
        <p class="lead">UniFi Sonar houdt je UniFi-netwerk in de gaten en vertelt in gewone taal waar het misgaat: zwak wifi-signaal, veel retries, drukke kanalen, kabelproblemen, apparaten die op de verkeerde AP blijven hangen en wat de IPS tegenhoudt.</p>
        <p class="muted">Je hebt nodig: het IP-adres van je UniFi-console (UDM, UCG, Cloud Gateway of UniFi OS Server) en een API-key. Alles blijft op dit apparaat; er gaat niets naar internet.</p>
        <div class="wiz-actions"><button class="btn primary" data-wiz="2">Koppel mijn UniFi-controller</button><button class="btn" data-wiz="demo">Eerst rondkijken met demodata</button></div>`;
    } else if (wiz.step === 2) {
      body = `<h1>Koppel je controller</h1>
        <form id="wiz-form" novalidate>
        ${field("w-addr", "Adres van je UniFi-console", `<input class="input" id="w-addr" name="address" required autocomplete="off" spellcheck="false" placeholder="192.168.1.1" value="${esc(wiz.address)}">`,
          "Het IP-adres of de hostnaam. Poort 443 en 11443 (UniFi OS Server) worden allebei geprobeerd; een andere poort vul je zo in: <code>192.168.1.10:8443</code>.")}
        ${field("w-key", "API-key", `<div class="pw"><input class="input" id="w-key" name="api_key" type="password" autocomplete="off" spellcheck="false" placeholder="Plak hier je API-key" value="${esc(wiz.api_key)}"><button type="button" class="btn ghost" data-show="w-key" aria-label="Toon API-key">${icon("eye")}</button></div>`,
          `<details><summary>Waar vind ik de API-key?</summary><ol><li>Open <b>UniFi Network</b> op je console.</li><li>Ga naar <b>Instellingen → Control Plane → Integrations</b>.</li><li>Kies <b>Create API Key</b>, geef hem een naam (bijv. "UniFi Sonar") en kopieer de sleutel. Je ziet hem maar één keer.</li></ol></details>`)}
        ${reconf && wiz.info.needs_confirmation ? field("w-cur", "Huidige API-key (ter bevestiging)", `<input class="input" id="w-cur" name="current_api_key" type="password" autocomplete="off" value="${esc(wiz.current_api_key)}">`, "Alleen nodig als je een andere API-key invult. Zo kan niet iedereen in je netwerk de koppeling omzetten.") : ""}
        <details class="adv"><summary>Geavanceerd</summary>
          ${field("w-site", "Site", `<input class="input" id="w-site" name="site" value="${esc(wiz.site)}" spellcheck="false">`, "Meestal <code>default</code>.")}
          <label class="check"><input type="checkbox" id="w-tls" name="verify_tls" ${wiz.verify_tls ? "checked" : ""}> Certificaat controleren <span class="muted">(alleen met een geldig certificaat; UniFi gebruikt standaard een eigen certificaat)</span></label>
          <p class="help" style="margin-top:14px">Geeft je API-key alleen beperkte gegevens (geen signaal en retries)? Vul dan een lokaal account met <b>View Only</b>-rechten in. Dat wordt alleen gebruikt als het nodig is.</p>
          ${field("w-user", "Gebruikersnaam (optioneel)", `<input class="input" id="w-user" name="username" autocomplete="off" value="${esc(wiz.username)}">`)}
          ${field("w-pass", "Wachtwoord (optioneel)", `<input class="input" id="w-pass" name="password" type="password" autocomplete="off" value="${esc(wiz.password)}">`)}
        </details>
        ${wiz.error ? `<div class="banner err" role="alert">${icon("octagon")}<div><b>${esc(wiz.error.error)}</b>${wiz.error.hint ? `<div>${esc(wiz.error.hint)}</div>` : ""}</div></div>` : ""}
        <div class="wiz-actions"><button type="submit" class="btn primary" ${wiz.busy ? "disabled" : ""}>${wiz.busy ? "Bezig met testen…" : "Verbinding testen"}</button>
          <button type="button" class="btn ghost" data-wiz="${reconf ? "cancel" : "1"}">${reconf ? "Annuleren" : "Terug"}</button></div>
        </form>`;
    } else if (wiz.step === 3) {
      const r = wiz.result;
      const row = (ok, text) => `<li>${icon(ok ? "check" : "alert", ok ? "t-ok" : "t-warning")}<span>${text}</span></li>`;
      body = `<h1>Gelukt</h1><p class="lead">De verbinding werkt. Dit is wat ik zie:</p>
        <ul class="checks">
          ${row(true, `Bereikbaar op <b>${esc(r.url)}</b>`)}
          ${row(r.source !== "integration", `Ingelogd via de ${esc(SOURCE_LABEL[r.source] || r.source)}`)}
          ${r.gateway ? row(true, `Gateway: <b>${esc(r.gateway)}</b>`) : ""}
          ${row(r.devices > 0, `<b>${r.devices}</b> UniFi-apparaten en <b>${r.clients}</b> clients`)}
        </ul>
        ${r.warnings.map((w) => `<div class="banner">${icon("info")}<span>${esc(w)}</span></div>`).join("")}
        ${wiz.error ? `<div class="banner err" role="alert">${icon("octagon")}<span>${esc(wiz.error.error)}</span></div>` : ""}
        <div class="wiz-actions"><button class="btn primary" data-wiz="save" ${wiz.busy ? "disabled" : ""}>${wiz.busy ? "Opslaan…" : "Opslaan en starten"}</button><button class="btn ghost" data-wiz="2">Terug</button></div>`;
    }
    $("#view").innerHTML = `<div class="wizard">${head}<div class="card wiz-card">${body}</div><p class="wiz-foot muted">Je API-key wordt alleen op dit apparaat opgeslagen en nooit teruggestuurd naar de browser.</p></div>`;
    const form = $("#wiz-form");
    if (form) {
      form.addEventListener("submit", (e) => { e.preventDefault(); wizTest(); });
      (wiz.address ? $("#w-key") : $("#w-addr")).focus();
    }
  }
  function readForm() {
    const f = $("#wiz-form");
    if (!f) return;
    wiz.address = f.address.value.trim(); wiz.api_key = f.api_key.value.trim();
    wiz.site = (f.site.value || "default").trim(); wiz.verify_tls = f.verify_tls.checked;
    wiz.username = f.username.value.trim(); wiz.password = f.password.value;
    if (f.current_api_key) wiz.current_api_key = f.current_api_key.value.trim();
  }
  const wizBody = () => ({ address: wiz.address, api_key: wiz.api_key, username: wiz.username, password: wiz.password,
                           site: wiz.site, verify_tls: wiz.verify_tls, current_api_key: wiz.current_api_key });
  async function post(path, body) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || r.statusText);
    return j;
  }
  async function wizTest() {
    readForm();
    wiz.error = null;
    if (!wiz.address) { wiz.error = { error: "Vul het adres van je UniFi-console in." }; return renderWizard(); }
    if (!wiz.api_key && !(wiz.username && wiz.password)) { wiz.error = { error: "Vul een API-key in." }; return renderWizard(); }
    wiz.busy = true; renderWizard();
    try {
      const r = await post("/api/setup/test", wizBody());
      if (r.ok) { wiz.result = r; wiz.step = 3; } else wiz.error = r;
    } catch (e) { wiz.error = { error: e.message }; }
    wiz.busy = false; renderWizard();
  }
  async function wizSave() {
    wiz.busy = true; wiz.error = null; renderWizard();
    try {
      await post("/api/setup/save", wizBody());
      Object.assign(wiz, { step: 1, api_key: "", password: "", current_api_key: "", result: null });
      location.hash = "#/overzicht";
      document.body.classList.remove("setup");
      $("#view").dataset.mounted = "";
      await refresh();
    } catch (e) { wiz.error = { error: e.message }; wiz.busy = false; renderWizard(); }
  }
  async function wizDemo() {
    try {
      await post("/api/setup/demo", { current_api_key: wiz.current_api_key });
      location.hash = "#/overzicht"; document.body.classList.remove("setup"); $("#view").dataset.mounted = "";
      await refresh();
    } catch (e) { alert(e.message); }
  }
  $("#view").addEventListener("click", (e) => {
    const b = e.target.closest("[data-wiz]");
    const s = e.target.closest("[data-show]");
    if (s) { const i = $("#" + s.dataset.show); i.type = i.type === "password" ? "text" : "password"; return; }
    if (!b) return;
    const v = b.dataset.wiz;
    if (v === "save") return wizSave();
    if (v === "demo") return wizDemo();
    if (v === "cancel") { document.body.classList.remove("setup"); $("#view").dataset.mounted = ""; wiz.step = 1; return route(); }
    if (wiz.step === 2) readForm();
    wiz.error = null; wiz.step = +v; renderWizard();
  });

  // ------------------------------------------------------------------ instellingen
  function mountSettings() {
    mount("instellingen", `<div class="page-head"><div><h1>Instellingen</h1><p class="subtitle">Koppeling, meldingen naar je telefoon, toegang en probleemoplossing.</p></div></div>
      <div class="settings">
        <section class="card" aria-labelledby="h-conn"><h2 id="h-conn">Koppeling</h2><div id="set-conn"></div></section>
        <section class="card" aria-labelledby="h-notify"><h2 id="h-notify">Meldingen versturen</h2>
          <p class="help" style="margin:-4px 0 4px">Krijg een bericht als er iets misgaat: via Home Assistant, ntfy, Discord, Slack of een eigen webhook.</p><div id="set-notify"></div></section>
        <section class="card" aria-labelledby="h-mqtt"><h2 id="h-mqtt">Home Assistant (MQTT)</h2>
          <p class="help" style="margin:-4px 0 4px">Zet de netwerkscore, meldingen, internetsnelheid, datagebruik en een speedtest-knop in Home Assistant. HA herkent alles vanzelf via MQTT-discovery.</p><div id="set-mqtt"></div></section>
        <section class="card" aria-labelledby="h-access"><h2 id="h-access">Toegang</h2><div id="set-access"></div></section>
        <section class="card" aria-labelledby="h-debug"><h2 id="h-debug">Probleemoplossing</h2><div id="set-debug"></div></section>
      </div>
      <p class="muted" style="font-size:12px;margin-top:16px">UniFi Sonar is een onofficieel hobbyproject en niet verbonden aan Ubiquiti.</p>`);
    $("#set-conn").addEventListener("click", (e) => {
      const b = e.target.closest("[data-act]");
      if (!b) return;
      if (b.dataset.act === "change") { wiz.step = 2; wiz.address = ""; showWizard(2); }
      if (b.dataset.act === "demo") { wiz.step = 1; showWizard(1); }
    });
    loadNotify(); loadMqtt(); loadAccess(); loadDebug();
    $("#set-mqtt").addEventListener("click", (e) => { const b = e.target.closest("[data-mq]"); if (b) mqttAction(b.dataset.mq, b); });
  }
  UPDATERS.instellingen = async function () {   // alleen de koppeling ververst; formulieren blijven staan
    const info = await api("/api/setup").catch(() => ({}));
    const s = state.status || {};
    if (current !== "instellingen" || !$("#set-conn")) return;
    const live = info.mode === "live";
    $("#set-conn").innerHTML = `
      ${kv([["Modus", live ? badge("ok", "Live", "check") : badge("info", "Demodata")],
            ["Controller", live ? esc(info.controller_url) : "–"], ["Site", live ? esc(info.site) : "–"],
            ["Bron", esc(SOURCE_LABEL[s.source] || s.source || "–")], ["Laatste meting", s.last_ok ? `${ago(s.last_ok)} geleden` : "–"],
            ["API-key", info.has_api_key ? "opgeslagen (verborgen)" : "–"]])}
      ${s.last_error ? `<div class="banner err" style="margin-top:16px">${icon("octagon")}<span>${esc(s.last_error)}</span></div>` : ""}
      <div class="wiz-actions" style="margin-top:20px"><button class="btn primary" data-act="change">${live ? "Koppeling wijzigen" : "Koppel mijn UniFi-controller"}</button>
      ${live ? `<button class="btn" data-act="demo">Overschakelen naar demodata</button>` : ""}</div>`;
  };

  // ---- meldingen versturen
  const KIND = {
    homeassistant: ["Home Assistant", "http://homeassistant.local:8123/api/webhook/unifi-sonar",
      "Maak in Home Assistant een automatisering met als trigger <b>Webhook</b> (bijv. ID <code>unifi-sonar</code>) en plak hier de webhook-URL. In de automatisering heb je <code>trigger.json.title</code>, <code>.message</code>, <code>.severity</code> en <code>.event</code>."],
    ntfy: ["ntfy", "https://ntfy.sh/kies-een-lastig-te-raden-naam",
      "Installeer de ntfy-app, abonneer je op een topic met een lastig te raden naam en vul die URL hier in. Eigen ntfy-server met login? Vul dan ook een toegangstoken in."],
    discord: ["Discord", "https://discord.com/api/webhooks/…",
      "In Discord: Serverinstellingen → Integraties → Webhooks → Nieuwe webhook → Webhook-URL kopiëren."],
    slack: ["Slack", "https://hooks.slack.com/services/…", "Maak een <b>Incoming Webhook</b> aan in Slack en plak de URL hier."],
    webhook: ["Eigen webhook", "https://…",
      "Krijgt een POST met JSON: <code>event</code>, <code>severity</code>, <code>title</code>, <code>message</code>, <code>url</code> en <code>key</code>. Handig voor n8n of Node-RED."],
  };
  const nfy = { cfg: null, msg: {}, saving: false, banner: null };
  // ---- Home Assistant via MQTT
  async function loadMqtt() {
    let m;
    try { m = await api("/api/mqtt"); } catch (e) { return; }
    const el = $("#set-mqtt");
    if (!el) return;
    const st = m.status || {};
    const stTxt = !m.enabled ? "" : st.connected ? `<span class="badge ok">${icon("check")}Verbonden${st.last_publish ? ` · bijgewerkt ${ago(st.last_publish)} geleden` : ""}</span>`
      : st.error ? `<span class="badge critical">${icon("octagon")}${esc(st.error)}</span>` : `<span class="badge info">verbinden…</span>`;
    el.innerHTML = `<form class="form-grid" id="mq-form" onsubmit="return false">
        <div class="field" style="grid-column:1/-1"><label class="check"><input type="checkbox" name="enabled" ${m.enabled ? "checked" : ""}> Koppeling aan</label></div>
        <div class="field"><label for="mq-host">Broker</label><input class="input" id="mq-host" name="host" value="${esc(m.host)}" placeholder="bijv. 192.168.1.20 of homeassistant.local"></div>
        <div class="field"><label for="mq-port">Poort</label><input class="input" id="mq-port" name="port" type="number" min="1" max="65535" value="${esc(m.port)}"></div>
        <div class="field"><label for="mq-user">Gebruikersnaam</label><input class="input" id="mq-user" name="username" autocomplete="off" value="${esc(m.username)}"></div>
        <div class="field"><label for="mq-pw">Wachtwoord</label><input class="input" id="mq-pw" name="password" type="password" autocomplete="new-password" placeholder="${m.has_password ? "opgeslagen (leeg laten = behouden)" : ""}"></div>
      </form>
      <div class="wiz-actions" style="margin-top:14px;align-items:center"><button class="btn primary" data-mq="save">Opslaan</button><button class="btn" data-mq="test">Verbinding testen</button><span id="mq-msg">${stTxt}</span></div>
      <p class="help">Gebruik je de Mosquitto-add-on, maak dan in Home Assistant een gewone gebruiker aan voor Sonar en vul die hier in. Na het opslaan verschijnt <b>UniFi Sonar</b> als apparaat onder Instellingen → Apparaten → MQTT.</p>`;
    hydrateIcons(el);
  }
  async function mqttAction(act, b) {
    const f = $("#mq-form"), msg = $("#mq-msg");
    const body = { enabled: f.enabled.checked, host: f.host.value, port: +f.port.value || 1883, username: f.username.value, password: f.password.value || null };
    b.disabled = true;
    try {
      if (act === "test") {
        const r = await post("/api/mqtt/test", body);
        msg.innerHTML = r.ok ? `<span class="badge ok">${icon("check")}Broker bereikbaar en inloggen gelukt</span>` : `<span class="badge critical">${icon("octagon")}${esc(r.error)}</span>`;
      } else {
        await post("/api/mqtt/save", body);
        msg.innerHTML = `<span class="badge ok">${icon("check")}Opgeslagen</span>`;
        setTimeout(loadMqtt, 3000);
      }
    } catch (err) { msg.innerHTML = `<span class="badge critical">${icon("octagon")}${esc(err.message)}</span>`; }
    b.disabled = false;
  }
  async function loadNotify() {
    try { nfy.cfg = await api("/api/notify"); } catch (e) { nfy.cfg = null; }
    if (nfy.cfg && !nfy.cfg.base_url) nfy.cfg.base_url = location.origin;
    renderNotify();
  }
  function readNotify() {
    const root = $("#set-notify");
    if (!root || !nfy.cfg) return;
    nfy.cfg.delay_min = +root.querySelector("#n-delay").value;
    const dh = root.querySelector("#n-digest").value;
    nfy.cfg.digest_hour = dh === "" ? null : +dh;
    nfy.cfg.base_url = root.querySelector("#n-base").value.trim();
    root.querySelectorAll("[data-ch]").forEach((n) => {
      const c = nfy.cfg.channels[+n.dataset.ch];
      c.kind = n.querySelector("[name=kind]").value;
      c.url = n.querySelector("[name=url]").value.trim();
      const t = n.querySelector("[name=token]");
      if (t && t.value) c.token = t.value.trim();
      c.min_severity = n.querySelector("[name=sev]").value;
      c.resolved = n.querySelector("[name=resolved]").checked;
      c.enabled = n.querySelector("[name=enabled]").checked;
    });
  }
  function channelHTML(c, i) {
    const [label, ph, help] = KIND[c.kind] || KIND.webhook;
    const st = c.status || {};
    const msg = nfy.msg[i];
    const stat = msg ? `<span class="${msg.ok ? "t-ok" : "t-critical"}">${esc(msg.text)}</span>`
      : st.error ? `<span class="t-critical">Laatste poging mislukt: ${esc(st.error)}</span>`
      : st.ok ? `<span class="muted">Laatst verstuurd ${ago(st.ok)} geleden</span>` : "";
    return `<div class="channel" data-ch="${i}">
      <div class="channel-head"><b>${esc(label)}</b>
        <label class="check" style="margin:0"><input type="checkbox" name="enabled" ${c.enabled !== false ? "checked" : ""}> Aan</label>
        <button type="button" class="linkbtn" data-n="remove" data-i="${i}">Verwijderen</button></div>
      <div class="form-grid">
        <div class="field"><label for="n-kind-${i}">Soort</label><select class="input" id="n-kind-${i}" name="kind">${Object.entries(KIND).map(([k, v]) => `<option value="${k}" ${k === c.kind ? "selected" : ""}>${v[0]}</option>`).join("")}</select></div>
        <div class="field"><label for="n-sev-${i}">Vanaf</label><select class="input" id="n-sev-${i}" name="sev">${[["critical", "Alleen kritiek"], ["warning", "Waarschuwing en kritiek"], ["info", "Alles, ook info"]].map(([k, l]) => `<option value="${k}" ${k === (c.min_severity || "warning") ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      </div>
      <div class="field"><label for="n-url-${i}">Webhook-adres</label><input class="input" id="n-url-${i}" name="url" autocomplete="off" spellcheck="false" value="${esc(c.url || "")}" placeholder="${esc(c.url_masked ? c.url_masked + "  (leeg laten = behouden)" : ph)}">
        <div class="help">${help}</div></div>
      ${c.kind === "ntfy" ? `<div class="field"><label for="n-tok-${i}">Toegangstoken (optioneel)</label><input class="input" id="n-tok-${i}" name="token" type="password" autocomplete="off" placeholder="${c.has_token ? "opgeslagen (leeg laten = behouden)" : "tk_…"}"></div>` : ""}
      <label class="check"><input type="checkbox" name="resolved" ${c.resolved !== false ? "checked" : ""}> Ook een bericht als het weer is opgelost</label>
      <div class="channel-foot"><button type="button" class="btn" data-n="test" data-i="${i}">Testbericht sturen</button>${stat}</div>
    </div>`;
  }
  function renderNotify() {
    const root = $("#set-notify");
    if (!root) return;
    if (!nfy.cfg) { root.innerHTML = `<p class="muted">Beschikbaar zodra UniFi Sonar is gekoppeld.</p>`; return; }
    const c = nfy.cfg;
    root.innerHTML = `
      ${c.channels.length ? c.channels.map(channelHTML).join("") : `<p class="muted">Nog geen kanalen. Voeg er een toe om meldingen te krijgen.</p>`}
      <div class="wiz-actions" style="margin-top:12px"><button type="button" class="btn" data-n="add" ${c.channels.length >= 5 ? "disabled" : ""}>Kanaal toevoegen</button></div>
      <div class="form-grid" style="margin-top:8px">
        <div class="field"><label for="n-delay">Pas melden na</label><select class="input" id="n-delay">${[0, 2, 5, 10, 15, 30].map((m) => `<option value="${m}" ${m === c.delay_min ? "selected" : ""}>${m ? m + " minuten" : "direct"}</option>`).join("")}</select>
          <div class="help">Een probleem moet zo lang aanhouden; voorkomt berichten bij één uitschieter.</div></div>
        <div class="field"><label for="n-digest">Dagoverzicht</label><select class="input" id="n-digest"><option value="">Uit</option>${[6, 7, 8, 9, 12, 17, 18, 19, 20, 21].map((h) => `<option value="${h}" ${h === c.digest_hour ? "selected" : ""}>Elke dag om ${String(h).padStart(2, "0")}:00</option>`).join("")}</select>
          <div class="help">Eén bericht met de netwerkscore en alle open meldingen.</div></div>
      </div>
      <div class="field"><label for="n-base">Adres van dit dashboard</label><input class="input" id="n-base" value="${esc(c.base_url || "")}" spellcheck="false"><div class="help">Voor de link in elk bericht.</div></div>
      ${nfy.banner ? `<div class="banner ${nfy.banner.ok ? "" : "err"}" role="status" style="margin-top:16px">${icon(nfy.banner.ok ? "check" : "octagon")}<span>${esc(nfy.banner.text)}</span></div>` : ""}
      <div class="wiz-actions"><button type="button" class="btn primary" data-n="save" ${nfy.saving ? "disabled" : ""}>${nfy.saving ? "Opslaan…" : "Meldingen opslaan"}</button></div>`;
  }
  const chBody = (c) => ({ id: c.id || "", kind: c.kind, name: c.name || "", url: c.url || "", token: c.token ?? null,
    min_severity: c.min_severity || "warning", resolved: c.resolved !== false, enabled: c.enabled !== false });
  async function notifyAction(e) {
    const b = e.target.closest("[data-n]");
    if (!b || !nfy.cfg) return;
    readNotify();
    const act = b.dataset.n, i = +b.dataset.i;
    nfy.banner = null;
    if (act === "add") { nfy.cfg.channels.push({ kind: "homeassistant", min_severity: "warning", resolved: true, enabled: true }); nfy.msg = {}; }
    if (act === "remove") { nfy.cfg.channels.splice(i, 1); nfy.msg = {}; }
    if (act === "test") {
      b.disabled = true; b.textContent = "Versturen…";
      try { await post("/api/notify/test", { channel: chBody(nfy.cfg.channels[i]), base_url: nfy.cfg.base_url }); nfy.msg[i] = { ok: true, text: "Verstuurd, kijk of het aankomt." }; }
      catch (err) { nfy.msg[i] = { ok: false, text: err.message }; }
    }
    if (act === "save") {
      nfy.saving = true; renderNotify();
      try {
        await post("/api/notify/save", { channels: nfy.cfg.channels.map(chBody), delay_min: nfy.cfg.delay_min, digest_hour: nfy.cfg.digest_hour, base_url: nfy.cfg.base_url });
        nfy.cfg = await api("/api/notify"); nfy.msg = {};
        nfy.banner = { ok: true, text: "Opgeslagen. Wat nu al openstaat wordt niet alsnog verstuurd; nieuwe problemen wel." };
      } catch (err) { nfy.banner = { ok: false, text: err.message }; }
      nfy.saving = false;
    }
    renderNotify();
  }
  $("#view").addEventListener("click", (e) => { if (e.target.closest("#set-notify")) notifyAction(e); });
  $("#view").addEventListener("change", (e) => {   // andere soort → andere velden en uitleg
    if (e.target.name === "kind" && e.target.closest("#set-notify")) { readNotify(); renderNotify(); }
  });

  // ---- toegang
  async function loadAccess(msg) {
    const root = $("#set-access");
    if (!root) return;
    const a = await api("/api/access").catch(() => null);
    if (!a) { root.innerHTML = `<p class="muted">Niet beschikbaar.</p>`; return; }
    root.innerHTML = `<p class="help" style="margin-top:-4px">Het dashboard heeft geen login. Het werkt via een IP-adres, <code>localhost</code> en lokale namen zoals <code>sonar.local</code> of <code>sonar.lan</code>. Andere hostnamen worden geweigerd, zodat een website in je browser het dashboard niet stiekem kan aansturen (DNS-rebinding). Gebruik je een eigen naam of een reverse proxy, zet die hieronder.</p>
      <div class="field"><label for="a-hosts">Extra hostnamen</label><input class="input" id="a-hosts" spellcheck="false" placeholder="sonar.mijndomein.nl, sonar.tailnet.ts.net" value="${esc((a.allowed_hosts || []).join(", "))}">
        <div class="help">Gescheiden door komma's, precies zoals in de adresbalk.${a.env_hosts.length ? ` Al toegestaan via de service: <code>${esc(a.env_hosts.join(", "))}</code>.` : ""} Je bent nu verbonden via <code>${esc(a.current_host)}</code>.</div></div>
      ${msg ? `<div class="banner ${msg.ok ? "" : "err"}" role="status" style="margin-top:16px">${icon(msg.ok ? "check" : "octagon")}<span>${esc(msg.text)}</span></div>` : ""}
      <div class="wiz-actions"><button type="button" class="btn" id="a-save">Opslaan</button></div>`;
    $("#a-save").onclick = async () => {
      const hosts = $("#a-hosts").value.split(/[,\s]+/).map((h) => h.trim()).filter(Boolean);
      try { await post("/api/access", { allowed_hosts: hosts }); loadAccess({ ok: true, text: "Opgeslagen." }); }
      catch (err) { loadAccess({ ok: false, text: err.message }); }
    };
  }

  // ---- probleemoplossing
  async function loadDebug() {
    const root = $("#set-debug");
    if (!root) return;
    const d = await api("/api/debug").catch((e) => ({ text: "Kon geen debug-info ophalen: " + e.message }));
    root.innerHTML = `<p class="help" style="margin-top:-4px">Werkt er iets niet? Kopieer deze gegevens en plak ze in een issue op GitHub. IP-adressen, namen, MAC-adressen en sleutels zijn eruit gehaald.</p>
      <pre class="debug" id="dbg-text" tabindex="0">${esc(d.text)}</pre>
      <div class="wiz-actions" style="margin-top:12px"><button type="button" class="btn" id="dbg-copy">Debug-info kopiëren</button><button type="button" class="btn ghost" id="dbg-reload">Vernieuwen</button><span class="muted" id="dbg-msg" role="status"></span></div>`;
    $("#dbg-reload").onclick = loadDebug;
    $("#dbg-copy").onclick = async () => {
      const text = $("#dbg-text").textContent;
      try { await navigator.clipboard.writeText(text); $("#dbg-msg").textContent = "Gekopieerd."; }
      catch {   // geen clipboard-API (http): selecteer de tekst zodat ⌘C/Ctrl+C werkt
        const r = document.createRange(); r.selectNodeContents($("#dbg-text"));
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
        $("#dbg-msg").textContent = "Geselecteerd: druk op Ctrl+C of ⌘C.";
      }
    };
  }

  // ------------------------------------------------------------------ tijdlijn
  const EV = {
    device_offline: ["octagon", "bad"], device_online: ["check", "good"], device_reboot: ["power", "bad"], device_upgrade: ["check", "good"],
    port_down: ["plug", "bad"], port_up: ["plug", "good"], roam: ["roam", "roam"], client_join: ["wifi", "good"], client_leave: ["wifi", ""],
    config: ["settings", "cfg"],
  };
  const EKIND = { all: null, config: ["config"], device: ["device_offline", "device_online", "device_reboot", "device_upgrade"], port: ["port_down", "port_up"], roam: ["roam"], client: ["client_join", "client_leave"] };
  function eventsHTML(evts) {
    let day = "", out = "";
    evts.forEach((e) => {
      const d = new Date(e.ts * 1000).toLocaleDateString("nl-NL", { weekday: "long", day: "numeric", month: "long" });
      if (d !== day) { out += `<div class="day">${d}</div>`; day = d; }
      const [ic, cls] = EV[e.kind] || ["activity", ""];
      out += `<div class="event"><span class="time">${hhmm(e.ts)}</span><span class="eico ${cls}">${icon(ic)}</span><span>${esc(e.message)}</span></div>`;
    });
    return out || `<div class="empty">Geen gebeurtenissen in deze periode</div>`;
  }
  function mountTimeline() {
    mount("tijdlijn", `
      <div class="page-head"><div><h1>Tijdlijn</h1><p class="subtitle">Wat er in je netwerk gebeurde: herstarts, links die wegvallen, roaming en clients die komen en gaan.</p></div>${rangeSeg("tl-range")}</div>
      <div class="toolbar"><div class="chips" role="group" aria-label="Soort" id="tl-kind">${[["all", "Alles"], ["config", "Instellingen"], ["device", "Apparaten"], ["port", "Poorten"], ["roam", "Roaming"], ["client", "Clients"]].map(([v, l]) => `<button class="chip" data-k="${v}" aria-pressed="${state.ekind === v}">${l}</button>`).join("")}</div></div>
      <div class="card"><div class="events" id="tl-list"></div></div>`);
    bindRange("tl-range", UPDATERS.tijdlijn);
    $("#tl-kind").addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      state.ekind = b.dataset.k;
      $("#tl-kind").querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === b));
      UPDATERS.tijdlijn();
    });
  }
  UPDATERS.tijdlijn = async function () {
    const evts = await api(`/api/events?hours=${state.hours}&limit=1000`);
    const kinds = EKIND[state.ekind];
    $("#tl-list").innerHTML = eventsHTML(kinds ? evts.filter((e) => kinds.includes(e.kind)) : evts);
  };

  // ------------------------------------------------------------------ drawer
  let lastFocus = null;
  function markSelected() {
    document.querySelectorAll("[data-open][data-id], tr[data-id]").forEach((n) => {
      if (state.drawer && n.dataset.id === state.drawer.id) n.setAttribute("aria-selected", "true"); else n.removeAttribute("aria-selected");
    });
  }
  function openDrawer(type, id, from) {
    lastFocus = from || document.activeElement;
    state.drawer = { type, id };
    hm.mac = null;   // patroon opnieuw ophalen
    history.replaceState(null, "", `#/${current}/${encodeURIComponent(id)}`);   // deelbare link
    $("#drawer").classList.add("open"); $("#scrim").classList.add("open");
    $("#drawer").setAttribute("aria-hidden", "false");
    renderDrawer();
    markSelected();
    if (from) setTimeout(() => $("#drawer-close").focus(), 50);   // bij een deep link de focus niet wegtrekken
  }
  function closeDrawer() {
    state.drawer = null;
    history.replaceState(null, "", `#/${current}`);
    $("#drawer").classList.remove("open"); $("#scrim").classList.remove("open");
    $("#drawer").setAttribute("aria-hidden", "true");
    markSelected();
    lastFocus?.focus?.();
  }
  function renderDrawer() {
    const { type, id } = state.drawer;
    if (type === "device") renderDeviceDrawer(devByMac()[id]); else renderClientDrawer(cliByMac()[id]);
  }
  const kv = (pairs) => `<div class="kv">${pairs.map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${v}</div></div>`).join("")}</div>`;
  function relatedIssues(filter) {
    const list = state.issues.filter((i) => !i.resolved_at && filter(i));   // incl. genegeerd, zodat je het hier terug kunt zetten
    return list.length ? `<div class="card"><h3 style="margin-bottom:8px">Issues</h3>${list.map((i) => issueHTML(i, state.issues, false).replace('class="issue ', 'class="issue flat ')).join("")}</div>` : "";
  }

  async function renderDeviceDrawer(d) {
    if (!d) return closeDrawer();
    $("#drawer-icon").innerHTML = icon(devIcon(d.type));
    $("#drawer-title").textContent = d.name;
    $("#drawer-sub").textContent = `${d.model} · ${d.ip} · ${d.mac}`;
    const dm = devByMac();
    const up = d.uplink_mac ? `${esc(dm[d.uplink_mac]?.name || d.uplink_mac)}${d.uplink_port ? ` · poort ${d.uplink_port}` : ""}` : "–";
    let body = kv([
      ["Status", d.state === "online" ? badge("ok", "Online", "check") : badge("critical", d.state, "octagon")],
      ["Firmware", `${esc(d.version)}${d.upgradable ? ` ${badge("info", "update " + (d.upgrade_to || ""))}` : ""}`],
      ["Uptime", dur(d.uptime)], ["CPU", `${nf(d.cpu)}%`], ["Geheugen", `${nf(d.mem)}%`], ["Temperatuur", d.temp == null ? "–" : `${nf(d.temp)} °C`],
      ["Clients", d.num_clients], ["Uplink", up], ["Score", `${d.score}/100`],
    ]);
    body = `<div class="card">${body}</div>` + relatedIssues((i) => i.device_mac === d.mac && !i.client_mac && !i.group);
    if (d.client_issue_count) body += `<div class="banner">${icon("users")}<span>${d.client_issue_count} meldingen bij clients op dit apparaat. <button class="linkbtn" id="dr-goclients">Bekijk deze clients</button></span></div>`;
    if (d.type === "gateway") {
      const w = state.snap.wan;
      body += `<div class="card"><h3 style="margin-bottom:12px">Internet</h3>${kv([["Provider", esc(w.isp || "–")], ["WAN-IP", esc(w.wan_ip || "–")], ["Latency", `${nf(w.latency_ms)} ms`], ["Pakketverlies", `${nf(w.loss_pct, 1)}%`], ["Download (test)", `${nf(w.xput_down)} Mbit/s`], ["Upload (test)", `${nf(w.xput_up)} Mbit/s`]])}</div>`;
    }
    if (d.radios.length) {
      body += `<div class="card"><h3 style="margin-bottom:12px">Radio's</h3><div class="table-wrap" style="border:0"><table><thead><tr><th>Band</th><th class="r">Kanaal</th><th class="r">Clients</th><th>Bezetting</th><th class="r">Storing</th><th class="r">Retries</th><th class="r">Ervaring</th></tr></thead><tbody>
        ${d.radios.map((r) => { const lv = level("cu", r.cu_total); return `<tr style="cursor:default"><td><b>${r.radio} GHz</b><div class="cell-sub">${r.width ? r.width + " MHz" : ""}${r.tx_power ? ` · ${r.tx_power} dBm` : ""}</div></td><td class="r num">${r.channel ?? "–"}</td><td class="r num">${r.num_clients}</td>
          <td><div style="display:flex;gap:8px;align-items:center">${meter(r.cu_total, lv)}<span class="num ${lv !== "ok" ? "t-" + lv : ""}">${nf(r.cu_total)}%</span></div></td>
          <td class="r num">${nf(r.interference)}%</td><td class="r num">${nf(r.retry_pct, 1)}%</td><td class="r num">${nf(r.satisfaction)}</td></tr>`; }).join("")}
        </tbody></table></div></div>
        <div class="card"><div class="card-head"><h3>Kanaalbezetting per band</h3>${rangeSeg("dr-range")}</div><div id="dr-ch-cu"></div></div>
        <div class="card"><div class="card-head"><h3>Retries per band</h3></div><div id="dr-ch-rt"></div></div>
        <div class="card"><div class="card-head"><h3>Drukte per uur van de week</h3><span class="muted">afgelopen 7 dagen</span></div>
          <div class="toolbar" style="margin-bottom:12px"><div class="seg" role="group" aria-label="Band" id="dr-hm-band">${d.radios.map((r) => `<button data-b="${r.radio}" aria-pressed="${r.radio === (hm.mac === d.mac ? hm.band : d.radios[0].radio)}">${r.radio} GHz</button>`).join("")}</div>
          <div class="seg" role="group" aria-label="Meting" id="dr-hm-metric">${[["cu", "Bezetting"], ["interference", "Storing"], ["clients", "Clients"]].map(([k, l]) => `<button data-m="${k}" aria-pressed="${k === hm.metric}">${l}</button>`).join("")}</div></div>
          <div id="dr-heat"><div class="chart-empty">Laden…</div></div></div>`;
      const cl = state.snap.clients.filter((c) => c.ap_mac === d.mac).sort((a, b) => (a.satisfaction ?? 100) - (b.satisfaction ?? 100));
      body += `<div class="card"><h3 style="margin-bottom:8px">Clients op dit access point</h3><div class="table-wrap" style="border:0"><table><thead><tr><th>Naam</th><th>Band</th><th>Signaal</th><th class="r">Retries</th><th class="r">Ervaring</th></tr></thead><tbody>
        ${cl.map((c) => `<tr data-id="${esc(c.mac)}" data-client tabindex="0"><td class="cell-name">${esc(c.name)}</td><td>${c.band} GHz</td><td>${signalBars(c.signal, c.band)}</td><td class="r num ${level("retry", c.retry_pct) !== "ok" ? "t-" + level("retry", c.retry_pct) : ""}">${nf(c.retry_pct, 1)}%</td><td class="r num">${nf(c.satisfaction)}</td></tr>`).join("")}
        </tbody></table></div></div>`;
    }
    if (d.ports.length && d.type === "switch") {
      const cm = Object.fromEntries(state.snap.clients.filter((c) => c.sw_mac === d.mac).map((c) => [c.sw_port, c]));
      const apm = Object.fromEntries(state.snap.devices.filter((x) => x.uplink_mac === d.mac).map((x) => [x.uplink_port, x]));
      const pi = portIssues(d);
      body += `<div class="card"><div class="card-head"><h3>Poorten</h3>${d.poe_budget_w ? `<span class="muted">PoE ${nf(d.poe_used_w)} / ${nf(d.poe_budget_w)} W</span>` : ""}</div>
        ${d.poe_budget_w ? `<div style="margin-bottom:14px">${meter(100 * d.poe_used_w / d.poe_budget_w, 100 * d.poe_used_w / d.poe_budget_w >= state.th.poe_budget_warn ? "warning" : "")}</div>` : ""}
        ${portGrid(d, false)}
        <div class="legend-row"><span><i class="sw" style="background:var(--me-success)"></i>Actief</span><span><i class="sw" style="background:var(--me-warning)"></i>Aandacht</span><span><i class="sw" style="background:var(--me-danger)"></i>Fouten / flapt</span><span><i class="sw" style="background:var(--me-elevated);border:1px solid var(--me-border)"></i>Geen link</span><span><i class="sw" style="background:var(--me-warning);border-radius:50%;width:6px;height:6px"></i>PoE</span></div>
        <div class="table-wrap" style="border:0;margin-top:12px"><table><thead><tr><th class="r">#</th><th>Aangesloten</th><th>Snelheid</th><th class="r">PoE</th><th>Status</th></tr></thead><tbody>
        ${d.ports.filter((p) => p.up || pi[p.idx]).map((p) => {
          const who = cm[p.idx]?.name || apm[p.idx]?.name || p.name;
          const iss = pi[p.idx] || [];
          return `<tr style="cursor:default"><td class="r num">${p.idx}</td><td>${esc(who)}${p.is_uplink ? ' <span class="badge">uplink</span>' : ""}</td><td class="num">${p.up ? speed(p.speed) : "geen link"}</td><td class="r num">${p.poe_w ? nf(p.poe_w, 1) + " W" : "–"}</td><td>${iss.length ? iss.map((i) => badge(i.severity, i.title.split(": ").pop())).join(" ") : badge("ok", "OK")}</td></tr>`;
        }).join("")}</tbody></table></div></div>`;
    }
    body += `<div class="card"><div class="card-head"><h3>CPU en geheugen</h3>${d.radios.length ? "" : rangeSeg("dr-range")}</div><div id="dr-ch-sys"></div></div>
      <div class="card"><h3 style="margin-bottom:8px">Gebeurtenissen</h3><div class="events" id="dr-events"></div></div>`;
    $("#drawer-body").innerHTML = body;
    $("#dr-goclients")?.addEventListener("click", () => { state.cuplink = d.mac; state.ckind = "issues"; closeDrawer(); location.hash = "#/clients"; $("#view").dataset.mounted = ""; update(); });
    bindRange("dr-range", () => loadDeviceHistory(d));
    if (d.radios.length) loadDevicePattern(d);
    await loadDeviceHistory(d);
  }

  // ------------------------------------------------------------------ patronen (heatmaps)
  const hm = { band: null, metric: "cu", data: null, mac: null };
  function heatmap(grid, { min, max, fmt, what }) {
    const vals = grid.flat().filter((v) => v != null);
    if (!vals.length) return `<div class="chart-empty">Nog te weinig historie: na een dag meten verschijnt hier een patroon.</div>`;
    const top = max ?? (Math.max(...vals) || 1);
    const bottom = Math.min(min ?? Math.min(...vals), top - 1e-9);   // schaal op de eigen waarden: patroon zichtbaar
    let hi = null, lo = null;
    grid.forEach((row, d) => row.forEach((v, h) => {
      if (v == null) return;
      if (!hi || v > hi[2]) hi = [d, h, v];
      if (!lo || v < lo[2]) lo = [d, h, v];
    }));
    const at = ([d, h]) => `${DAYS[d]} ${String(h).padStart(2, "0")}:00`;
    const cells = grid.map((row, d) => `<span class="hm-day">${DAYS[d]}</span>` + row.map((v, h) => {
      const tip = `${at([d, h])} · ${v == null ? "geen meting" : fmt(v)}`;
      return `<span class="hm-c ${v == null ? "na" : ""}" data-tip="${esc(tip)}" style="${v == null ? "" : `background:rgba(57,216,244,${(0.07 + 0.78 * Math.max(0, Math.min(1, (v - bottom) / (top - bottom)))).toFixed(3)})`}"></span>`;
    }).join("")).join("");
    const hours = `<span></span>` + Array.from({ length: 24 }, (_, h) => `<span class="hm-h">${h % 6 === 0 ? h : ""}</span>`).join("");
    const flat = hi[2] - lo[2] < 0.05 * top;
    const summary = flat ? (what === "presence" ? (lo[2] >= 0.95 ? "Altijd verbonden" : `Elk uur ongeveer even vaak verbonden (${fmt(hi[2])})`) : `Elk uur ongeveer gelijk (${fmt(hi[2])})`)
      : `${what === "presence" ? "Meest verbonden" : "Drukst"}: ${at(hi)} (${fmt(hi[2])}) · ${what === "presence" ? "minst" : "rustigst"}: ${at(lo)} (${fmt(lo[2])})`;
    return `<div class="heat" role="img" aria-label="${esc(summary)}">${cells}${hours}</div>
      <div class="hm-foot"><span class="hm-read" aria-hidden="true">${esc(summary)}</span>
        <span class="hm-legend" aria-hidden="true">${fmt(bottom)}<i></i>${fmt(top)}</span></div>`;
  }
  $("#drawer-body").addEventListener("mouseover", (e) => {
    const c = e.target.closest(".hm-c");
    const read = c?.closest(".card")?.querySelector(".hm-read");
    if (c && read) read.textContent = c.dataset.tip;
  });
  async function loadClientPattern(c) {
    const p = await api(`/api/patterns/client/${encodeURIComponent(c.mac)}?days=7`).catch(() => null);
    const root = $("#dr-pattern");
    if (!root || state.drawer?.id !== c.mac || !p) return;
    let html = "";
    const total = p.aps.reduce((a, x) => a + x.seconds, 0);
    if (!c.wired && p.aps.length && total > 0) {
      const fav = p.aps[0];
      html += `<p style="margin:0 0 10px">Meestal op <b>${esc(fav.name)}</b> (${Math.round(fav.share * 100)}% van de tijd)${p.switches ? `, ${p.switches}× van AP gewisseld` : ", nooit van AP gewisseld"}.</p>
        <div class="ap-share">${p.aps.slice(0, 6).map((a) => `<div class="ap-row"><span class="cell-name">${esc(a.name)}</span>${meter(a.share * 100)}<span class="num">${Math.round(a.share * 100)}%</span><span class="muted num">${dur(a.seconds)}</span><span>${signalBars(a.signal, c.band)}</span></div>`).join("")}</div>
        <h4 class="sub-h">Wanneer verbonden</h4>`;
    }
    html += heatmap(p.presence, { min: 0, max: 1, fmt: (v) => `${Math.round(v * 100)}%`, what: "presence" });
    if (p.since && p.since > Date.now() / 1000 - p.days * 86400 + 6 * 3600) html += `<p class="help">Historie sinds ${new Date(p.since * 1000).toLocaleDateString("nl-NL", { weekday: "long", day: "numeric", month: "long" })}.</p>`;
    root.innerHTML = html;
  }
  async function loadDevicePattern(d) {
    if (hm.mac !== d.mac) { hm.mac = d.mac; hm.band = d.radios[0].radio; hm.data = null; }
    const draw = () => {
      const root = $("#dr-heat");
      if (!root || !hm.data) return;
      const g = hm.data.radios[hm.band];
      const unit = hm.metric === "clients" ? "" : "%";
      root.innerHTML = g ? heatmap(g[hm.metric], { fmt: (v) => `${nf(v, hm.metric === "clients" && v < 10 ? 1 : 0)}${unit}`, what: hm.metric })
        : `<div class="chart-empty">Geen historie voor deze band</div>`;
    };
    const seg = (id, key, attr) => $(id)?.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      hm[key] = b.dataset[attr];
      $(id).querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      draw();
    });
    seg("#dr-hm-band", "band", "b"); seg("#dr-hm-metric", "metric", "m");
    if (!hm.data) hm.data = await api(`/api/patterns/device/${encodeURIComponent(d.mac)}?days=7`).catch(() => null);
    if (state.drawer?.id === d.mac) draw();
  }
  async function loadDeviceHistory(d) {
    const h = await api(`/api/history/device/${encodeURIComponent(d.mac)}?hours=${state.hours}`);
    if (state.drawer?.id !== d.mac) return;
    const bands = Object.keys(h.radios).sort();
    if ($("#dr-ch-cu")) {
      MEcharts.lineChart($("#dr-ch-cu"), { series: bands.map((b) => ({ name: `${b} GHz`, color: BAND_COLOR[b], data: h.radios[b].map((p) => [p.t, p.cu_total]) })), unit: "%", yMin: 0, yMax: 100, bucket: h.bucket,
        threshold: { value: state.th.radio_cu_warn, label: `drempel ${nf(state.th.radio_cu_warn)}%` } });
      MEcharts.lineChart($("#dr-ch-rt"), { series: bands.map((b) => ({ name: `${b} GHz`, color: BAND_COLOR[b], data: h.radios[b].map((p) => [p.t, p.retry_pct]) })), unit: "%", yMin: 0, bucket: h.bucket,
        threshold: { value: state.th.radio_retry_warn, label: `drempel ${nf(state.th.radio_retry_warn)}%` } });
    }
    MEcharts.lineChart($("#dr-ch-sys"), { series: [{ name: "CPU", color: C.cyan, data: h.device.map((p) => [p.t, p.cpu]) }, { name: "Geheugen", color: C.violet, data: h.device.map((p) => [p.t, p.mem]) }], unit: "%", yMin: 0, yMax: 100, bucket: h.bucket });
    $("#dr-events").innerHTML = eventsHTML(h.events.slice(0, 60));
  }

  async function renderClientDrawer(c) {
    if (!c) return closeDrawer();
    const dm = devByMac();
    $("#drawer-icon").innerHTML = icon(c.wired ? "cable" : "laptop");
    $("#drawer-title").textContent = c.name;
    $("#drawer-sub").textContent = `${c.vendor || ""} · ${c.ip} · ${c.mac}`;
    const conn = c.wired ? `${esc(dm[c.sw_mac]?.name || "–")} · poort ${c.sw_port ?? "?"}` : esc(dm[c.ap_mac]?.name || "–");
    let body = `<div class="card">${kv(c.wired
      ? [["Verbonden met", conn], ["Type", "Bedraad"], ["Netwerk", esc(c.network || "–")], ["Verbonden sinds", dur(c.uptime)], ["IP", esc(c.ip)], ["Score", `${c.score}/100`]]
      : [["Verbonden met", conn], ["Band", `${c.band} GHz · kanaal ${c.channel}`], ["Standaard", proto(c.proto)], ["Signaal", signalBars(c.signal, c.band)], ["Ruis", `${nf(c.noise)} dBm`],
        ["Retries", `${nf(c.retry_pct, 1)}%`], ["Ervaring", nf(c.satisfaction)], ["Snelheid", `${nf(c.tx_rate_mbps)} / ${nf(c.rx_rate_mbps)} Mbit/s`],
        ["Met deze AP sinds", c.assoc_ts ? new Date(c.assoc_ts * 1000).toLocaleString("nl-NL", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : dur(c.uptime)]])}
      <div style="margin-top:14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        ${c.wired ? "" : reconnectBtn(c.mac).replace('class="linkbtn"', 'class="btn"')}${pauseMenu(c.mac)}
        <span class="muted" style="font-size:12px">${c.wired ? "" : "Opnieuw verbinden: kort los, daarna kiest het zelf de beste AP. "}Pauzeren: geen internet of netwerk tot de tijd om is.</span></div></div>`;
    body += relatedIssues((i) => i.client_mac === c.mac);
    if (!c.wired) {
      body += `<div class="card"><div class="card-head"><h3>Signaalsterkte</h3>${rangeSeg("dr-range")}</div><div id="dr-ch-sig"></div></div>
        <div class="card"><div class="card-head"><h3>Retries</h3><span class="muted">% opnieuw verstuurde pakketten</span></div><div id="dr-ch-rt"></div></div>
        <div class="card"><div class="card-head"><h3>Wifi-ervaring</h3></div><div id="dr-ch-sat"></div></div>`;
    }
    body += `<div class="card"><div class="card-head"><h3>Patroon</h3><span class="muted">afgelopen 7 dagen</span></div><div id="dr-pattern"><div class="chart-empty">Laden…</div></div></div>`;
    if (!c.wired) body += `<div class="card"><h3 style="margin-bottom:8px">Roaming en verbindingen</h3><div class="events" id="dr-events"></div></div>`;
    $("#drawer-body").innerHTML = body;
    loadClientPattern(c);
    if (!c.wired) { bindRange("dr-range", () => loadClientHistory(c)); await loadClientHistory(c); }
  }
  async function loadClientHistory(c) {
    const h = await api(`/api/history/client/${encodeURIComponent(c.mac)}?hours=${state.hours}`);
    if (state.drawer?.id !== c.mac) return;
    const s = h.series;
    MEcharts.lineChart($("#dr-ch-sig"), { series: [{ name: "Signaal", color: C.cyan, data: s.map((p) => [p.t, p.signal]) }], unit: " dBm", bucket: h.bucket,
      threshold: { value: sigLimits(c.band)[0], label: `drempel ${nf(sigLimits(c.band)[0])} dBm (${c.band} GHz)` } });
    MEcharts.lineChart($("#dr-ch-rt"), { series: [{ name: "Retries", color: C.violet, data: s.map((p) => [p.t, p.retry_pct]) }], unit: "%", yMin: 0, bucket: h.bucket,
      threshold: { value: state.th.client_retry_warn, label: `drempel ${nf(state.th.client_retry_warn)}%` } });
    MEcharts.lineChart($("#dr-ch-sat"), { series: [{ name: "Ervaring", color: C.mint, data: s.map((p) => [p.t, p.satisfaction]) }], yMin: 0, yMax: 100, bucket: h.bucket,
      threshold: { value: state.th.client_satisfaction_warn, label: `drempel ${nf(state.th.client_satisfaction_warn)}` } });
    $("#dr-events").innerHTML = eventsHTML(h.events.slice(0, 60));
  }

  // ------------------------------------------------------------------ wereld
  const world = { hours: store.get("world.hours", 6), show: store.get("world.show", { out: true, in: true, blocked: true }),
                  mode: store.get("world.mode", "flat"), globe: null,
                  data: null, after: 0, timer: null, seen: new Set(), focus: null,
                  conn: { dir: "all", sort: "last", q: "", cc: null, limit: 50 } };
  const DIR = { out: ["Uitgaand", C.cyan, "arrow-up-right"], in: ["Inkomend", C.violet, "arrow-down-left"], blocked: ["Geblokkeerd", C.rose, "octagon"] };
  const ccName = (() => {
    let dn = null;
    try { dn = new Intl.DisplayNames(["nl"], { type: "region" }); } catch (e) { /* oude browser */ }
    return (cc) => { try { return (cc && dn?.of(cc)) || cc || "Onbekend"; } catch (e) { return cc; } };
  })();
  function bytes(b) {
    if (b == null) return "–";
    const u = ["B", "kB", "MB", "GB", "TB"];
    let i = 0;
    while (b >= 1000 && i < 4) { b /= 1000; i++; }
    return `${nf(b, b < 10 && i ? 1 : 0)} ${u[i]}`;
  }
  const reduceMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  function arcPath(a, b, kind) {   // boog van a naar b; de bolling verschilt per soort zodat ze niet samenvallen
    const [x1, y1] = a, [x2, y2] = b;
    const d = Math.hypot(x2 - x1, y2 - y1);
    const lift = d * ({ out: 0.28, in: 0.2, blocked: 0.36 }[kind] || 0.28);
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - lift;
    return `M${x1},${y1} Q${mx.toFixed(1)},${my.toFixed(1)} ${x2},${y2}`;
  }
  function mountWorld() {
    const W = window.WORLD;
    world.view = null;
    world.globe?.destroy(); world.globe = null;
    mount("wereld", `
      <div class="page-head"><div><h1>Wereld</h1><p class="subtitle">Met welke landen je netwerk praat, live uit het verkeerslogboek van je gateway.</p></div>
        <div class="seg" role="group" aria-label="Periode" id="w-range">${[[1, "1 u"], [6, "6 u"], [24, "24 u"], [48, "48 u"]].map(([h, l]) => `<button data-h="${h}" aria-pressed="${world.hours === h}">${l}</button>`).join("")}</div></div>
      <div id="w-banner"></div>
      <section class="grid kpis" id="w-kpis" aria-label="Samenvatting"></section>
      <section class="card world-card">
        <div class="card-head"><div class="chips" role="group" aria-label="Soort verkeer" id="w-show">${Object.entries(DIR).map(([k, [l, col]]) => `<button class="chip" data-k="${k}" aria-pressed="${!!world.show[k]}"><i class="sw" style="background:${col}"></i>${l}</button>`).join("")}</div>
          <div class="w-head-r"><div class="seg" role="group" aria-label="Weergave" id="w-mode">${[["flat", "Plat"], ["globe", "Globe"]].map(([k, l]) => `<button data-m="${k}" aria-pressed="${world.mode === k}">${l}</button>`).join("")}</div>
          <span class="muted" id="w-live-sub"><span class="live-dot" aria-hidden="true"></span>live</span></div></div>
        <div class="world-wrap" id="w-map">
          <div class="globe-host" id="w-globe" hidden></div>
          <svg viewBox="0 0 ${W.w} ${W.h}" role="img" aria-labelledby="w-map-title" preserveAspectRatio="xMidYMid meet">
            <title id="w-map-title">Wereldkaart met verbindingen per land</title>
            <g class="land">${Object.entries(W.countries).filter(([, c]) => c.d).map(([cc, c]) => `<path data-cc="${cc}" d="${c.d}"/>`).join("")}</g>
            <g class="arcs" id="w-arcs"></g><g class="pulses" id="w-pulses"></g><g id="w-home"></g><g class="marks" id="w-marks"></g><g class="labels" id="w-labels"></g>
          </svg>
          <div class="zoom-ctl" role="group" aria-label="Zoomen">
            <button data-z="in" aria-label="Inzoomen" title="Inzoomen">+</button>
            <button data-z="out" aria-label="Uitzoomen" title="Uitzoomen">−</button>
            <button data-z="reset" aria-label="Hele wereld" title="Hele wereld">${icon("globe")}</button>
          </div>
          <div class="tooltip" id="w-tip"></div>
        </div>
        <div class="legend-row" id="w-legend"></div>
      </section>
      <section class="grid cols-2" style="margin-top:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">Landen</h2><span class="muted" id="w-cty-sub"></span></div><div class="rank w-rank" id="w-cty"></div></div>
        <div class="card"><div class="card-head"><h2 style="margin:0">Live</h2><span class="muted">nieuwste eerst</span></div><ol class="ticker" id="w-ticker" aria-live="off"></ol></div>
      </section>
      <section class="card" id="w-conn" style="margin-top:16px">
        <div class="card-head"><h2 style="margin:0">Verbindingen</h2><span class="muted" id="w-conn-sub"></span></div>
        <div class="toolbar">
          <div class="chips" role="group" aria-label="Richting" id="w-conn-dir">${[["all", "Alles", null], ["out", "Uitgaand", C.cyan], ["in", "Inkomend", C.violet], ["blocked", "Geblokkeerd", C.rose]].map(([k, l, col]) => `<button class="chip" data-d="${k}" aria-pressed="${world.conn.dir === k}">${col ? `<i class="sw" style="background:${col}"></i>` : ""}${l}</button>`).join("")}</div>
          <span id="w-conn-cc"></span>
          <div class="seg" role="group" aria-label="Sorteren" id="w-conn-sort">${[["last", "Laatst"], ["bytes", "Meeste data"], ["count", "Vaakst"]].map(([k, l]) => `<button data-s="${k}" aria-pressed="${world.conn.sort === k}">${l}</button>`).join("")}</div>
          <label class="search"><span class="sr-only">Zoeken in verbindingen</span>${icon("search")}<input class="input" id="w-conn-q" type="search" placeholder="Apparaat, domein, land of poort" value="${esc(world.conn.q)}"></label>
        </div>
        <div class="table-wrap" id="w-conn-table"></div>
        <div class="wiz-actions" style="margin-top:12px;justify-content:center" id="w-conn-more"></div>
      </section>
      <section class="grid cols-2" style="margin-top:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">Apparaten</h2><span class="muted">meeste internetverkeer</span></div><div class="rank w-rank" id="w-cli"></div></div>
        <div class="card"><div class="card-head"><h2 style="margin:0">Bestemmingen</h2><span class="muted">meeste data</span></div><div class="rank w-rank" id="w-dom"></div></div>
      </section>`);
    $("#w-range").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-h]"); if (!b) return;
      world.hours = +b.dataset.h; store.set("world.hours", world.hours);
      $("#w-range").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      loadWorld();
    });
    $("#w-show").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-k]"); if (!b) return;
      world.show[b.dataset.k] = !world.show[b.dataset.k]; store.set("world.show", world.show);
      b.setAttribute("aria-pressed", world.show[b.dataset.k]);
      renderWorld(); renderTicker();
    });
    const map = $("#w-map"), tip = $("#w-tip");
    map.addEventListener("mousemove", (e) => {
      if (world.drag || world.mode === "globe") return;
      const t = e.target.closest("[data-cc]");
      const cc = t?.dataset.cc;
      if (!cc || !world.byCc?.[cc]) { tip.classList.remove("show"); setFocus(null); return; }
      setFocus(cc);
      tip.innerHTML = countryTip(world.byCc[cc]);
      const r = map.getBoundingClientRect();
      const x = Math.min(e.clientX - r.left + 14, r.width - tip.offsetWidth - 4);
      tip.style.left = `${Math.max(4, x)}px`; tip.style.top = `${Math.max(4, e.clientY - r.top - tip.offsetHeight - 12)}px`;
      tip.classList.add("show");
    });
    map.addEventListener("mouseleave", () => { tip.classList.remove("show"); setFocus(null); });
    $("#w-mode").addEventListener("click", (e) => { const b = e.target.closest("[data-m]"); if (b) setMode(b.dataset.m); });
    if (world.mode === "globe") setMode("globe");
    $("#w-cty").addEventListener("mouseover", (e) => setFocus(e.target.closest("[data-cc]")?.dataset.cc || null));
    $("#w-cty").addEventListener("focusin", (e) => setFocus(e.target.closest("[data-cc]")?.dataset.cc || null));
    $("#w-cty").addEventListener("mouseleave", () => setFocus(null));
    $("#w-cty").addEventListener("click", (e) => { const r = e.target.closest("[data-cc]"); if (r) { zoomTo(r.dataset.cc); setConn({ cc: r.dataset.cc }); } });
    $("#w-kpis").addEventListener("click", (e) => {
      const b = e.target.closest("[data-kpi]"); if (!b) return;
      const k = b.dataset.kpi;
      if (k === "countries") { $("#w-cty").closest(".card").scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" }); return; }
      setConn(k === "bytes" ? { dir: "all", sort: "bytes", cc: null } : { dir: k, sort: "last", cc: null }, true);
    });
    $("#w-conn-dir").addEventListener("click", (e) => { const b = e.target.closest("[data-d]"); if (b) setConn({ dir: b.dataset.d }); });
    $("#w-conn-sort").addEventListener("click", (e) => { const b = e.target.closest("[data-s]"); if (b) setConn({ sort: b.dataset.s }); });
    $("#w-conn-cc").addEventListener("click", (e) => { if (e.target.closest("[data-clear-cc]")) setConn({ cc: null }); });
    $("#w-conn-more").addEventListener("click", (e) => { if (e.target.closest("button")) { world.conn.limit += 100; loadConn(); } });
    let qt;
    $("#w-conn-q").addEventListener("input", (e) => { clearTimeout(qt); qt = setTimeout(() => setConn({ q: e.target.value.trim() }), 250); });
    $("#w-cty").addEventListener("keydown", (e) => { const r = e.target.closest("[data-cc]"); if (r && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); zoomTo(r.dataset.cc); } });
    initZoom();
    $("#w-conn-table").addEventListener("click", (e) => { const n = e.target.closest("[data-open]"); if (n) openDrawer("client", n.dataset.id, n); });
    $("#w-cli").addEventListener("click", (e) => { const n = e.target.closest("[data-open]"); if (n) openDrawer("client", n.dataset.id, n); });
    world.after = 0; world.seen = new Set();
    loadWorld(); worldLoop();
  }
  UPDATERS.wereld = () => loadWorld();
  // ---- zoomen en verschuiven: we passen alleen de viewBox aan, de kaart blijft één SVG
  const ZMAX = 12;
  function applyView() {
    const W = window.WORLD, svg = $("#w-map svg");
    if (!svg) return;
    const v = world.view;
    svg.setAttribute("viewBox", `${v.x.toFixed(2)} ${v.y.toFixed(2)} ${v.w.toFixed(2)} ${v.h.toFixed(2)}`);
    const z = W.w / v.w;                       // 1 = hele wereld
    svg.style.setProperty("--s", (1 / z).toFixed(4));
    $("#w-map").classList.toggle("zoomed", z > 1.01);
    $("#w-labels")?.classList.toggle("show", z >= 2.4);
    const zo = $("#w-map [data-z=out]"), zr = $("#w-map [data-z=reset]"), zi = $("#w-map [data-z=in]");
    if (zo) { zo.disabled = z <= 1.01; zr.disabled = z <= 1.01; zi.disabled = z >= ZMAX - 0.01; }
  }
  function clampView(v) {
    const W = window.WORLD;
    v.w = Math.min(W.w, Math.max(W.w / ZMAX, v.w));
    v.h = v.w * W.h / W.w;
    v.x = Math.min(W.w - v.w, Math.max(0, v.x));
    v.y = Math.min(W.h - v.h, Math.max(0, v.y));
    return v;
  }
  function zoomAt(factor, px, py) {   // px/py: punt in kaartcoördinaten dat op zijn plek blijft
    const v = world.view, nw = v.w / factor;
    const W = window.WORLD;
    const cw = Math.min(W.w, Math.max(W.w / ZMAX, nw));
    const f = v.w / cw;
    world.view = clampView({ x: px - (px - v.x) / f, y: py - (py - v.y) / f, w: cw, h: 0 });
    applyView();
  }
  function toMap(e) {
    const r = $("#w-map svg").getBoundingClientRect(), v = world.view;
    return [v.x + (e.clientX - r.left) / r.width * v.w, v.y + (e.clientY - r.top) / r.height * v.h];
  }
  function zoomTo(cc) {
    if (world.globe) { world.globe.zoomTo(cc); setFocus(cc); $("#w-tip").classList.remove("show"); return; }
    const W = window.WORLD, c = W.countries[cc]?.c;
    if (!c) return;
    const p = document.querySelector(`#w-map .land path[data-cc="${cc}"]`);
    let w = W.w / 5;
    if (p) {   // zo ver inzoomen dat het land goed in beeld is (grote landen minder ver)
      const b = p.getBBox();
      w = Math.max(W.w / ZMAX, Math.min(W.w / 1.6, Math.max(b.width, b.height * W.w / W.h) * 3));
    }
    world.view = clampView({ x: c[0] - w / 2, y: c[1] - (w * W.h / W.w) / 2, w, h: 0 });
    applyView();
    $("#w-tip").classList.remove("show");
    setFocus(cc);
    $("#w-map").scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "nearest" });
  }
  function initZoom() {
    const W = window.WORLD, map = $("#w-map"), svg = map.querySelector("svg");
    world.view = world.view || { x: 0, y: 0, w: W.w, h: W.h };
    applyView();
    map.querySelector(".zoom-ctl").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-z]"); if (!b) return;
      if (world.globe) {
        if (b.dataset.z === "reset") world.globe.reset(); else world.globe.zoomBy(b.dataset.z === "in" ? 1.6 : 1 / 1.6);
        return;
      }
      const v = world.view, cx = v.x + v.w / 2, cy = v.y + v.h / 2;
      if (b.dataset.z === "reset") { world.view = { x: 0, y: 0, w: W.w, h: W.h }; applyView(); }
      else zoomAt(b.dataset.z === "in" ? 1.6 : 1 / 1.6, cx, cy);
    });
    svg.addEventListener("wheel", (e) => {
      const z = W.w / world.view.w;
      if (e.deltaY > 0 && z <= 1.01) return;   // helemaal uitgezoomd: laat de pagina gewoon scrollen
      e.preventDefault();
      const [px, py] = toMap(e);
      zoomAt(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0018)), px, py);
    }, { passive: false });
    svg.addEventListener("click", (e) => {
      if (world.drag) return;
      const cc = e.target.closest("[data-cc]")?.dataset.cc;
      if (cc && world.byCc?.[cc]) { $("#w-tip").classList.remove("show"); setConn({ cc }, true); }
    });
    svg.addEventListener("dblclick", (e) => { e.preventDefault(); const [px, py] = toMap(e); zoomAt(2, px, py); });
    // slepen (muis) en knijpen (touch) met pointer events
    const pts = new Map();
    let last = null, pinch = null;
    svg.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 && e.pointerType === "mouse") return;
      pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      last = { x: e.clientX, y: e.clientY };
      if (pts.size === 2) {
        pts.forEach((_, id) => { try { svg.setPointerCapture(id); } catch (err) { /* al los */ } });
        const [a, b] = [...pts.values()];
        pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) };
      }
    });
    svg.addEventListener("pointermove", (e) => {
      if (!pts.has(e.pointerId)) return;
      pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      const r = svg.getBoundingClientRect();
      if (pts.size === 2 && pinch) {
        const [a, b] = [...pts.values()];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        const [px, py] = toMap({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 });
        if (pinch.d > 0) zoomAt(d / pinch.d, px, py);
        pinch.d = d;
        return;
      }
      const dx = e.clientX - last.x, dy = e.clientY - last.y;
      if (!world.drag && Math.hypot(dx, dy) < 4) return;   // klein beetje bewegen is nog een klik
      if (!world.drag) { try { svg.setPointerCapture(e.pointerId); } catch (err) { /* al los */ } }
      world.drag = true;
      map.classList.add("dragging");
      $("#w-tip").classList.remove("show");
      const v = world.view;
      world.view = clampView({ x: v.x - dx / r.width * v.w, y: v.y - dy / r.height * v.h, w: v.w, h: 0 });
      last = { x: e.clientX, y: e.clientY };
      applyView();
    });
    const end = (e) => {
      pts.delete(e.pointerId);
      if (pts.size < 2) pinch = null;
      if (!pts.size) { setTimeout(() => { world.drag = false; }, 0); map.classList.remove("dragging"); }
    };
    svg.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", end);
  }
  function setFocus(cc) {
    if (world.focus === cc) return;
    world.focus = cc;
    world.globe?.setFocus(cc);
    $("#w-map")?.classList.toggle("focusing", !!cc);
    document.querySelectorAll("#w-map [data-cc]").forEach((n) => n.classList.toggle("hl", n.dataset.cc === cc));   // land, boog, stip en naam
    document.querySelectorAll("#w-cty [data-cc]").forEach((n) => n.classList.toggle("hl", n.dataset.cc === cc));
  }
  const blockWhat = (b) => {   // "Telnet (poort 23)" of de naam van de IPS-regel
    const svc = b.what && !/^(OTHER|Onbekend)$/i.test(b.what) ? b.what.replace(/_/g, " ") : null;
    return svc ? (b.port ? `${svc} (poort ${b.port})` : svc) : b.port ? `poort ${b.port}` : "verbinding";
  };
  function countryTip(c) {
    const row = (k, l, v) => (v ? `<div class="tt-row"><span><i class="sw" style="background:${DIR[k][1]}"></i>${l}</span><b>${v}</b></div>` : "");
    return `<div class="tt-time">${esc(ccName(c.cc))}</div>
      ${row("out", "Uitgaand", c.out_n ? `${nf(c.out_n)} × · ${bytes(c.bytes_out ?? c.up + c.down)}` : "")}
      ${row("in", "Inkomend", c.in_n ? `${nf(c.in_n)} ×` : "")}
      ${row("blocked", "Geblokkeerd", c.blocked_n ? `${nf(c.blocked_n)} ×` : "")}
      ${c.blocked?.length ? `<div class="tt-list tt-blocked">${c.blocked.slice(0, 4).map((b) => `<div>
        <div>${esc(blockWhat(b))} → ${esc(b.target)}</div>
        <div class="muted">${nf(b.n)}× · ${esc(b.by)}${b.sources > 1 ? ` · ${b.sources} adressen` : ""} · laatst ${stamp(b.last)}</div></div>`).join("")}</div>` : ""}
      ${c.domains?.length ? `<div class="tt-list">${c.domains.slice(0, 3).map((d) => `<div>${esc(d.name)} <span class="muted">${bytes(d.bytes)}</span></div>`).join("")}</div>` : ""}
      ${c.clients?.length ? `<div class="tt-list muted">${c.clients.slice(0, 3).map((x) => esc(x.name)).join(" · ")}</div>` : ""}
      <div class="tt-hint">Klik voor alle verbindingen</div>`;
  }
  async function loadWorld() {
    let d;
    try { d = await api(`/api/world?hours=${world.hours}`); } catch (e) { return; }
    if (current !== "wereld") return;
    world.data = d;
    world.byCc = Object.fromEntries(d.countries.map((c) => [c.cc, c]));
    $("#w-banner").innerHTML = d.available === false ? `<div class="banner err">${icon("info")}<span>Verbindingen zijn alleen beschikbaar via de uitgebreide UniFi-API (API-key of lokaal account).</span></div>`
      : d.error ? `<div class="banner err">${icon("info")}<span>Verbindingen ophalen lukte niet: ${esc(d.error)}</span></div>` : "";
    const t = d.totals, per = world.hours === 1 ? "het afgelopen uur" : `de afgelopen ${world.hours} uur`;
    const kpi = (k, ic, label, v, sub, hint) => `<button class="card compact kpi kpi-link" data-kpi="${k}" title="${hint}"><div class="label">${icon(ic)}${label}${icon("chevron", "kpi-go")}</div><div class="value">${v}</div><div class="sub">${sub}</div></button>`;
    $("#w-kpis").innerHTML =
      kpi("countries", "globe", "Landen", nf(t.countries), per, "Naar de landenlijst") +
      kpi("out", "arrow-up-right", "Uitgaand", nf(t.out_n), "verbindingen", "Toon de uitgaande verbindingen") +
      kpi("in", "arrow-down-left", "Inkomend", nf(t.in_n), "van internet naar binnen", "Toon de inkomende verbindingen") +
      kpi("bytes", "activity", "Data", bytes(t.bytes), "op en neer", "Toon de verbindingen met de meeste data") +
      kpi("blocked", "octagon", "Geblokkeerd", nf(t.blocked_n), "door IPS en firewall", "Toon wat er geblokkeerd is");
    renderWorld(); renderWorldLists(); loadConn();
  }
  function renderWorld() {
    const d = world.data, W = window.WORLD;
    if (!d || !$("#w-arcs")) return;
    const home = W.countries[d.home]?.c || [512, 60];
    const max = Math.max(1, ...d.countries.map((c) => c.bytes));
    const lvl = (b) => (b > 0 ? Math.log10(1 + b) / Math.log10(1 + max) : 0);
    document.querySelectorAll("#w-map .land path").forEach((p) => {
      const c = world.byCc[p.dataset.cc];
      const on = c && ((world.show.out && c.out_n) || (world.show.in && c.in_n) || (world.show.blocked && c.blocked_n));
      p.style.fill = on && c.bytes ? `rgba(57, 216, 244, ${(0.12 + 0.5 * lvl(c.bytes)).toFixed(3)})` : on ? "rgba(251, 113, 133, 0.10)" : "";
      p.classList.toggle("home", p.dataset.cc === d.home);
    });
    const maxN = Math.max(1, ...d.countries.map((c) => Math.max(c.out_n, c.in_n, c.blocked_n || 0)));
    const arcs = [];
    for (const c of d.countries) {
      const to = W.countries[c.cc]?.c;
      if (!to || c.cc === d.home) continue;
      for (const k of ["out", "in", "blocked"]) {
        const n = c[`${k}_n`] || 0;
        if (!n || !world.show[k]) continue;
        const w = 0.6 + 2.4 * (k === "out" ? lvl(c.bytes) : Math.log10(1 + n) / Math.log10(1 + maxN));
        const path = k === "out" ? arcPath(home, to, k) : arcPath(to, home, k);
        arcs.push(`<path data-cc="${c.cc}" class="arc ${k}" d="${path}" style="stroke:${DIR[k][1]};stroke-width:${w.toFixed(2)}"/>`);
      }
    }
    $("#w-arcs").innerHTML = arcs.join("");
    // kleine landen (Hongkong, Singapore, Malta…) hebben op deze schaal geen vorm: een stip om aan te wijzen
    $("#w-marks").innerHTML = d.countries.filter((c) => W.countries[c.cc]?.c && !W.countries[c.cc].d && c.cc !== d.home).map((c) => {
      const [x, y] = W.countries[c.cc].c;
      const col = c.out_n || c.in_n ? `rgba(57, 216, 244, ${(0.35 + 0.5 * lvl(c.bytes)).toFixed(3)})` : "rgba(251, 113, 133, 0.6)";
      return `<circle class="cmark" data-cc="${c.cc}" cx="${x}" cy="${y}" style="fill:${col}"><title>${esc(ccName(c.cc))}</title></circle>`;
    }).join("");
    $("#w-labels").innerHTML = d.countries.filter((c) => W.countries[c.cc]?.c).map((c) => {
      const [x, y] = W.countries[c.cc].c;
      const small = !W.countries[c.cc].d;
      return `<text data-cc="${c.cc}" x="${x}" y="${y}" dy="${small ? "-0.8em" : "0"}">${esc(ccName(c.cc))}</text>`;
    }).join("");
    $("#w-home").innerHTML = `<circle class="home-ring" cx="${home[0]}" cy="${home[1]}" r="7"/><circle class="home-dot" cx="${home[0]}" cy="${home[1]}" r="3"/>`;
    $("#w-legend").innerHTML = `<span><i class="sw" style="background:${C.cyan}"></i>Uitgaand: eigen apparaat → internet</span><span><i class="sw" style="background:${C.violet}"></i>Inkomend: internet → eigen apparaat</span>
      <span><i class="sw" style="background:${C.rose}"></i>Geblokkeerd: tegengehouden door IPS of firewall</span><span>Kleur van een land: hoeveel data, dikte van de boog: hoeveel verkeer</span>`;
    if (world.focus) { const f = world.focus; world.focus = null; setFocus(f); }
    if (world.globe) {
      const ga = [];
      for (const c of d.countries) {
        if (c.cc === d.home) continue;
        for (const k of ["out", "in", "blocked"]) {
          const n = c[`${k}_n`] || 0;
          if (n && world.show[k]) ga.push({ cc: c.cc, kind: k, w: 0.8 + 2.6 * (k === "out" ? lvl(c.bytes) : Math.log10(1 + n) / Math.log10(1 + maxN)) });
        }
      }
      const G = window.WORLD_GEO, has = new Set(G.features.map((f) => f.id));
      world.globe.setData({ home: d.home, byCc: world.byCc, show: world.show, lvl, name: ccName, arcs: ga,
        dots: d.countries.filter((c) => c.cc !== d.home && G.labels[c.cc] && !has.has(c.cc)).map((c) => c.cc) });
    }
  }
  // ---- globe: pas laden als je hem kiest (d3-geo + landsgrenzen in graden)
  let globeLoad = null;
  function loadScript(src) {
    return new Promise((ok, fail) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => fail(new Error(src)); document.head.appendChild(s); });
  }
  function ensureGlobe() {
    globeLoad ||= (async () => {
      if (!window.d3?.geoOrthographic) { await loadScript("vendor/d3-array.min.js"); await loadScript("vendor/d3-geo.min.js"); }
      if (!window.WORLD_GEO) await loadScript("world-geo.js");
      if (!window.SonarGlobe) await loadScript("globe.js");
    })();
    return globeLoad;
  }
  async function setMode(m) {
    world.mode = m; store.set("world.mode", m);
    $("#w-mode")?.querySelectorAll("[data-m]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.m === m));
    const map = $("#w-map"), host = $("#w-globe"), tip = $("#w-tip");
    if (!map) return;
    tip.classList.remove("show");
    if (m !== "globe") {
      world.globe?.destroy(); world.globe = null;
      host.hidden = true; map.classList.remove("globe-mode");
      applyView();
      return;
    }
    map.classList.add("globe-mode"); host.hidden = false;
    try { await ensureGlobe(); } catch (e) { host.innerHTML = `<div class="empty">De globe kon niet laden.</div>`; return; }
    if (world.mode !== "globe" || world.globe || !host.isConnected) return;
    world.globe = window.SonarGlobe.mount(host, {
      onHover(cc, x, y) {
        const c = world.byCc?.[cc]; if (!c) return;
        setFocus(cc);
        tip.innerHTML = countryTip(c);
        const r = map.getBoundingClientRect();
        tip.style.left = `${Math.max(4, Math.min(x - r.left + 14, r.width - tip.offsetWidth - 4))}px`;
        tip.style.top = `${Math.max(4, y - r.top - tip.offsetHeight - 12)}px`;
        tip.classList.add("show");
      },
      onLeave() { tip.classList.remove("show"); setFocus(null); },
      onClick(cc) { if (world.byCc?.[cc]) { tip.classList.remove("show"); setConn({ cc }, true); } },
    });
    renderWorld();
  }
  function renderWorldLists() {
    const d = world.data;
    if (!d) return;
    const cs = d.countries.filter((c) => c.cc !== d.home || c.out_n).sort((a, b) => b.bytes - a.bytes || (b.blocked_n || 0) - (a.blocked_n || 0));
    const max = Math.max(1, ...cs.map((c) => c.bytes));
    const unk = d.totals.unknown_n || 0;
    $("#w-cty-sub").textContent = `${plural(cs.length, "land", "landen")}${unk ? ` · ${nf(unk)} verbindingen zonder land` : ""}`;
    $("#w-cty-sub").title = unk ? "UniFi geeft niet bij elke verbinding een land mee, bijvoorbeeld bij DNS naar publieke resolvers." : "";
    $("#w-cty").innerHTML = cs.length ? cs.slice(0, 25).map((c) => `
      <div class="rank-row w-row" data-cc="${c.cc}" tabindex="0" title="Klik om in te zoomen op ${esc(ccName(c.cc))}"><div class="rank-main"><div class="rank-name"><span class="cc">${esc(c.cc)}</span>${esc(ccName(c.cc))}${c.cc === d.home ? ` <span class="muted">(thuis)</span>` : ""}</div>
        <div class="cell-sub">${[c.out_n ? `${nf(c.out_n)} uit` : "", c.in_n ? `${nf(c.in_n)} in` : "", c.blocked_n ? `<span class="t-critical">${nf(c.blocked_n)} geblokkeerd</span>` : ""].filter(Boolean).join(" · ")}${c.domains?.[0] ? ` · ${esc(c.domains[0].name)}` : c.blocked?.[0] ? ` · ${esc(blockWhat(c.blocked[0]))} → ${esc(c.blocked[0].target)}` : ""}</div></div>
        <div class="rank-bar">${meter(100 * c.bytes / max)}</div><span class="num rank-n">${bytes(c.bytes)}</span></div>`).join("")
      : `<div class="empty">Nog geen verbindingen in deze periode.</div>`;
    const cmax = Math.max(1, ...d.clients.map((c) => c.bytes));
    $("#w-cli").innerHTML = d.clients.length ? d.clients.map((c) => `
      <div class="rank-row"><div class="rank-main"><div class="rank-name">${c.mac && cliByMac()[c.mac] ? `<button class="linkbtn plain" data-open="client" data-id="${esc(c.mac)}">${esc(c.name || c.mac)}</button>` : esc(c.name || "–")}</div>
        <div class="cell-sub">${nf(c.n)} verbindingen · ${plural(c.countries, "land", "landen")}</div></div>
        <div class="rank-bar">${meter(100 * c.bytes / cmax)}</div><span class="num rank-n">${bytes(c.bytes)}</span></div>`).join("") : `<div class="empty">Geen gegevens</div>`;
    const dmax = Math.max(1, ...d.domains.map((x) => x.bytes));
    $("#w-dom").innerHTML = d.domains.length ? d.domains.map((x) => `
      <div class="rank-row"><div class="rank-main"><div class="rank-name">${esc(x.name)}</div><div class="cell-sub">${x.cc ? `<span class="cc">${esc(x.cc)}</span>${esc(ccName(x.cc))} · ` : ""}${nf(x.n)} verbindingen</div></div>
        <div class="rank-bar">${meter(100 * x.bytes / dmax)}</div><span class="num rank-n">${bytes(x.bytes)}</span></div>`).join("") : `<div class="empty">Geen gegevens</div>`;
  }
  function setConn(patch, scroll) {
    Object.assign(world.conn, patch, { limit: 50 });
    const c = world.conn;
    $("#w-conn-dir")?.querySelectorAll("[data-d]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.d === c.dir));
    $("#w-conn-sort")?.querySelectorAll("[data-s]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.s === c.sort));
    if (scroll) $("#w-conn").scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });
    loadConn();
  }
  async function loadConn() {
    const c = world.conn;
    if (!$("#w-conn-table")) return;
    const qs = new URLSearchParams({ hours: world.hours, dir: c.dir, sort: c.sort, limit: c.limit });
    if (c.cc) qs.set("cc", c.cc);
    if (c.q) qs.set("q", c.q);
    let d;
    try { d = await api(`/api/world/connections?${qs}`); } catch (e) { return; }
    if (current !== "wereld") return;
    $("#w-conn-cc").innerHTML = c.cc ? `<button class="chip" aria-pressed="true" data-clear-cc title="Filter op land weghalen"><span class="cc">${esc(c.cc)}</span>${esc(ccName(c.cc))} ${icon("x")}</button>` : "";
    hydrateIcons($("#w-conn-cc"));
    const per = world.hours === 1 ? "afgelopen uur" : `afgelopen ${world.hours} uur`;
    $("#w-conn-sub").textContent = `${nf(d.total)} ${d.total === 1 ? "groep" : "groepen"} · ${per} · gelijke verbindingen samengevoegd`;
    const svc = (r) => {
      const s = r.service && !/^(OTHER)$/i.test(r.service) ? r.service.replace(/_/g, " ") : null;
      return s && r.port ? `${s} · ${r.port}` : s || (r.port ? `poort ${r.port}` : "–");
    };
    const other = (r) => r.dir === "out"
      ? `<div class="rank-name">${esc(r.dest || "–")}</div><div class="cell-sub">${r.cc ? `<span class="cc">${esc(r.cc)}</span>${esc(ccName(r.cc))}` : "land onbekend"}</div>`
      : `<div class="rank-name">${r.cc ? `<span class="cc">${esc(r.cc)}</span>${esc(ccName(r.cc))}` : "onbekend"}</div><div class="cell-sub">${plural(r.remotes || 0, "adres", "adressen")}</div>`;
    const dirTxt = (r) => r.dir === "blocked" ? `<span class="t-critical">${esc(r.by || "Geblokkeerd")}</span>` : DIR[r.dir][0];
    $("#w-conn-table").innerHTML = d.rows.length ? `<table class="conn-table"><thead><tr><th>Laatst</th><th>Richting</th><th>Eigen apparaat</th><th>Andere kant</th><th>Dienst</th><th class="r">Aantal</th><th class="r">Data</th></tr></thead><tbody>
      ${d.rows.map((r) => `<tr style="cursor:default"><td class="num" title="${esc(fullStamp(r.last))}">${stamp(r.last)}</td>
        <td><span class="dir"><i class="sw" style="background:${DIR[r.dir][1]}"></i>${dirTxt(r)}</span></td>
        <td>${r.client_mac && cliByMac()[r.client_mac] ? `<button class="linkbtn plain" data-open="client" data-id="${esc(r.client_mac)}">${esc(r.client || "–")}</button>` : esc(r.client || "–")}</td>
        <td>${other(r)}</td><td class="muted">${esc(svc(r))}</td>
        <td class="r num">${nf(r.n)}</td><td class="r num">${r.bytes ? bytes(r.bytes) : "–"}</td></tr>`).join("")}</tbody></table>`
      : `<div class="empty">Geen verbindingen gevonden${c.q || c.cc ? " met dit filter" : " in deze periode"}.</div>`;
    $("#w-conn-more").innerHTML = d.rows.length < d.total ? `<button class="btn">Toon meer (${nf(d.total - d.rows.length)} over)</button>` : "";
  }
  function renderTicker() {
    const el = $("#w-ticker");
    if (!el) return;
    const rows = (world.live || []).filter((f) => world.show[f.dir]).slice(0, 18);
    el.innerHTML = rows.length ? rows.map((f) => {
      const [l, col] = DIR[f.dir];
      const what = f.dir === "blocked" ? `${esc(f.service || "IPS-regel")}` : `${esc(f.domain || (f.port ? `poort ${f.port}` : "–"))}`;
      const who = f.dir === "out" ? `${esc(f.client_name || "–")} → ${what}`
        : f.dir === "in" ? `${esc(ccName(f.cc))} → ${esc(f.client_name || "–")}${f.port ? ` <span class="muted">poort ${f.port}</span>` : ""}`
        : `${what}${f.port ? ` <span class="muted">→ poort ${f.port}</span>` : ""}`;
      return `<li><span class="num muted">${hhmm(f.ts)}</span><i class="sw" style="background:${col}" title="${l}"></i>
        <span class="t-main">${who}</span><span class="t-cc" title="${esc(ccName(f.cc))}">${esc(f.cc || "–")}</span><span class="num muted t-b">${f.up + f.down ? bytes(f.up + f.down) : ""}</span></li>`;
    }).join("") : `<li class="empty">Wachten op verbindingen…</li>`;
  }
  function pulse(f) {
    if (world.globe) { if (world.show[f.dir]) world.globe.pulse(f.dir, f.cc); return; }
    const W = window.WORLD, d = world.data;
    if (!d || reduceMotion() || !world.show[f.dir] || f.cc === d.home) return;
    const home = W.countries[d.home]?.c, far = W.countries[f.cc]?.c, g = $("#w-pulses");
    if (!home || !far || !g) return;
    const path = f.dir === "out" ? arcPath(home, far, "out") : arcPath(far, home, f.dir);
    const ns = "http://www.w3.org/2000/svg";
    const c = document.createElementNS(ns, "circle");
    c.setAttribute("r", "2.6"); c.setAttribute("fill", DIR[f.dir][1]); c.setAttribute("class", "pulse");
    c.style.r = `calc(2.6px * var(--s, 1))`;
    const m = document.createElementNS(ns, "animateMotion");
    m.setAttribute("dur", "1.8s"); m.setAttribute("path", path); m.setAttribute("fill", "freeze"); m.setAttribute("begin", "indefinite");
    c.appendChild(m); g.appendChild(c);
    m.beginElement();
    setTimeout(() => c.remove(), 1900);
  }
  async function worldLoop() {
    clearTimeout(world.timer);
    if (current !== "wereld") return;
    try {
      const r = await api(`/api/world/live?after=${world.after}&limit=60`);
      const fresh = r.flows.filter((f) => !world.seen.has(f.id));
      fresh.forEach((f) => world.seen.add(f.id));
      if (world.seen.size > 5000) world.seen = new Set(r.flows.map((f) => f.id));
      world.live = [...fresh, ...(world.live || [])].sort((a, b) => b.ts - a.ts).slice(0, 60);
      if (world.after) fresh.slice(0, 14).forEach((f, i) => setTimeout(() => pulse(f), i * 350));   // eerste keer niet alles tegelijk
      world.after = Math.max(world.after, r.now - 600);
      renderTicker();
    } catch (e) { /* volgende ronde opnieuw */ }
    world.timer = setTimeout(worldLoop, 8000);
  }
  // ------------------------------------------------------------------ init
  hydrateIcons(document);
  $("#drawer-close").onclick = closeDrawer;
  $("#scrim").onclick = closeDrawer;
  $("#drawer-body").addEventListener("click", async (e) => {
    if (await pauseAction(e)) return;
    if (await approveAction(e)) return;
    if (await reconnectAction(e)) return;
    if (await muteAction(e)) return;
    const x = e.target.closest("[data-expand]");
    if (x) { const k = x.dataset.expand; state.expanded.has(k) ? state.expanded.delete(k) : state.expanded.add(k); renderDrawer(); return; }
    const o = e.target.closest("[data-open]");
    if (o) return openDrawer(o.dataset.open, o.dataset.id, lastFocus);
    const r = e.target.closest("tr[data-client]");
    if (r) openDrawer("client", r.dataset.id, lastFocus);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.drawer) closeDrawer();
    if (e.key === "Tab" && state.drawer) {  // focus binnen de drawer houden
      const f = [...$("#drawer").querySelectorAll('button, [href], input, select, [tabindex]:not([tabindex="-1"])')].filter((n) => n.offsetParent !== null);
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { f[f.length - 1].focus(); e.preventDefault(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { f[0].focus(); e.preventDefault(); }
    }
  });
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if (current === "overzicht") loadOverviewCharts(); if (current === "internet") { loadInternet(); drawLive(); renderUsage(); } if (current === "wereld") renderWorld(); if (current === "apparaten" && devView.mode === "map") renderTopo(); if (state.drawer) renderDrawer(); }, 250); });
  window.addEventListener("hashchange", route);
  route();
  refresh();
  setInterval(refresh, 30000);
})();
