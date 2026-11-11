/* UniFi Sonar — dashboard (vanilla JS, geen build-stap) */
(function () {
  "use strict";
  // ------------------------------------------------------------------ taal: L("Nederlands", "English")
  const LANG = document.documentElement.lang === "en" ? "en" : "nl";
  const L = (nl, en) => (LANG === "en" ? en : nl);
  const LOC = L("nl-NL", "en-GB");
  // Kiezen: in de bovenbalk (NL/EN) en bij Instellingen. Geldt voor de hele app, dus ook meldingen en Home Assistant.
  const langSwitch = (full) => `<div class="seg lang-seg" role="group" aria-label="${L("Taal", "Language")}">${[["nl", "Nederlands", "NL"], ["en", "English", "EN"]]
    .map(([k, name, code]) => `<button type="button" data-lang="${k}" lang="${k}" aria-pressed="${LANG === k}"${full ? "" : ` title="${name}" aria-label="${name}"`}>${full ? name : code}</button>`).join("")}</div>`;
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
  const SOURCE_LABEL = { "legacy-key": L("uitgebreide API", "extended API"), "legacy-login": L("uitgebreide API (account)", "extended API (account)"),
    integration: L("officiële API (beperkt)", "official API (limited)"), mock: L("demodata", "demo data") };
  const SEV = { critical: [L("Kritiek", "Critical"), "octagon"], warning: [L("Waarschuwing", "Warning"), "alert"], info: ["Info", "info"] };
  const CAT = { wifi: "Wifi", switch: "Switch", device: L("Apparaat", "Device"), wan: "Internet", security: L("Beveiliging", "Security"),
    config: L("Configuratie", "Configuration"), new: L("Nieuw apparaat", "New device") };
  const DAYS = L("ma di wo do vr za zo", "Mon Tue Wed Thu Fri Sat Sun").split(" ");

  // ------------------------------------------------------------------ helpers
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const nf = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString(LOC, { maximumFractionDigits: d, minimumFractionDigits: d }));
  function dur(sec) {
    if (sec == null) return "–";
    sec = Math.max(0, Math.round(sec));
    const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
    if (d) return L(`${d} d ${h} u`, `${d} d ${h} h`);
    if (h) return L(`${h} u ${m} m`, `${h} h ${m} m`);
    return m ? `${m} m` : `${sec} s`;
  }
  const ago = (ts) => (ts ? dur(Date.now() / 1000 - ts) : "–");
  const hhmm = (ts) => new Date(ts * 1000).toLocaleTimeString(LOC, { hour: "2-digit", minute: "2-digit" });
  // "14:32", "gisteren 14:32" of "ma 3 nov 14:32"
  const stamp = (ts) => {
    const d = new Date(ts * 1000), day = (x) => new Date(x).setHours(0, 0, 0, 0);
    const diff = Math.round((day(Date.now()) - day(d)) / 86400000);
    const pre = diff === 0 ? "" : diff === 1 ? L("gisteren ", "yesterday ") : d.toLocaleDateString(LOC, { weekday: "short", day: "numeric", month: "short" }) + " ";
    return pre + hhmm(ts);
  };
  const fullStamp = (ts) => new Date(ts * 1000).toLocaleString(LOC, { dateStyle: "full", timeStyle: "short" });
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
  const scoreLabel = (s) => (s >= 85 ? [L("Goed", "Good"), "ok"] : s >= 60 ? [L("Aandacht nodig", "Needs attention"), "warning"] : [L("Slecht", "Poor"), "critical"]);

  async function api(path) {
    const r = await fetch(path, { cache: "no-store" });
    if (r.status === 401) throw needLogin();
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  }
  const store = {
    get(k, d) { try { const v = localStorage.getItem("ui." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("ui." + k, JSON.stringify(v)); } catch { /* geen opslag */ } },
  };

  // ------------------------------------------------------------------ inloggen
  // Passkeys: de browser werkt met binaire velden, de server met base64url.
  const b64uDec = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
  const b64uEnc = (b) => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const passkeyPossible = () => !!window.PublicKeyCredential && window.isSecureContext && !/^[\d.]+$|:/.test(location.hostname);
  const passkeyError = (e) => (e.name === "NotAllowedError" || e.name === "AbortError" ? L("Geannuleerd of niet gelukt.", "Cancelled or not successful.") : e.name === "InvalidStateError" ? L("Dit apparaat heeft al een passkey voor Sonar.", "This device already has a passkey for Sonar.") : e.message);
  async function passkeyLogin() {
    const { id, options: o } = await post("/api/auth/passkey/login/options", {});
    o.challenge = b64uDec(o.challenge);
    (o.allowCredentials || []).forEach((c) => { c.id = b64uDec(c.id); });
    const c = await navigator.credentials.get({ publicKey: o });
    await post("/api/auth/passkey/login", { id, credential: { id: c.id, rawId: b64uEnc(c.rawId), type: c.type, clientExtensionResults: c.getClientExtensionResults(),
      response: { clientDataJSON: b64uEnc(c.response.clientDataJSON), authenticatorData: b64uEnc(c.response.authenticatorData), signature: b64uEnc(c.response.signature), userHandle: c.response.userHandle ? b64uEnc(c.response.userHandle) : null } } });
  }
  async function passkeyAdd(name, password) {
    const { id, options: o } = await post("/api/auth/passkey/register/options", { name, password });
    o.challenge = b64uDec(o.challenge);
    o.user.id = b64uDec(o.user.id);
    (o.excludeCredentials || []).forEach((c) => { c.id = b64uDec(c.id); });
    const c = await navigator.credentials.create({ publicKey: o });
    await post("/api/auth/passkey/register", { id, credential: { id: c.id, rawId: b64uEnc(c.rawId), type: c.type, clientExtensionResults: c.getClientExtensionResults(),
      response: { clientDataJSON: b64uEnc(c.response.clientDataJSON), attestationObject: b64uEnc(c.response.attestationObject), transports: c.response.getTransports?.() || [] } } });
  }
  function needLogin() {
    showLogin();
    return Object.assign(new Error(L("Inloggen nodig", "Login required")), { auth: true });
  }
  const recoveryHTML = (code) => `<div class="recovery" role="status"><h3>${L("Bewaar deze herstelcode", "Save this recovery code")}</h3>
    <p>${L("Je UniFi-backups worden versleuteld. Openen kan met je wachtwoord of met deze code. Je ziet hem maar één keer, en zonder wachtwoord én code zijn de backups niet meer te openen. Zet hem in je wachtwoordmanager.", "Your UniFi backups are encrypted. You can open them with your password or with this code. It is shown only once, and without both the password and the code the backups can no longer be opened. Put it in your password manager.")}</p>
    <code>${esc(code)}</code></div>`;

  function showLogin() {
    const v = $("#view");
    if (v.dataset.mounted === "login") return;
    if (state.drawer) closeDrawer();    // alleen als hij open is: dit schrijft het adres over, en de pagina moet na het inloggen blijven
    stopKiosk();
    document.body.classList.remove("kiosk", "kiosk-paper");
    document.body.classList.add("setup");
    document.body.classList.add("logged-out");   // de taal wisselen kan pas na het inloggen
    v.dataset.mounted = "login";
    v.innerHTML = `<div class="wizard login"><div class="wiz-brand"><span class="logo">${icon("radar")}</span><div><div class="wiz-title">UniFi Sonar</div><div class="muted">${L("Log in om verder te gaan", "Log in to continue")}</div></div></div>
      <form class="card" id="login-form" onsubmit="return false">
        <div class="field"><label for="login-pw">${L("Wachtwoord", "Password")}</label><input class="input" id="login-pw" type="password" autocomplete="current-password" required></div>
        <div id="login-msg" role="alert"></div>
        <div class="wiz-actions"><button class="btn primary" id="login-go" type="submit">${L("Inloggen", "Log in")}</button><button class="btn" id="login-pk" type="button" hidden>${L("Inloggen met passkey", "Log in with a passkey")}</button></div>
      </form></div>`;
    $("#status").innerHTML = `<span class="dot off"></span>${L("Niet ingelogd", "Not logged in")}`;
    const loggedIn = async () => {
      document.body.classList.remove("logged-out");
      v.dataset.mounted = "";
      document.body.classList.remove("setup");
      route();
      await refresh();
    };
    const firstPassword = (min) => {
      v.innerHTML = `<div class="wizard login"><div class="wiz-brand"><span class="logo">${icon("radar")}</span><div><div class="wiz-title">UniFi Sonar</div><div class="muted">${L("Kies een wachtwoord voor dit dashboard", "Choose a password for this dashboard")}</div></div></div>
        <form class="card" id="first-form" onsubmit="return false">
          <div class="field"><label for="first-code">${L("Eenmalige code", "One-time code")}</label><input class="input" id="first-code" autocomplete="off" spellcheck="false" required>
            <div class="help">${L("Zo weet Sonar dat jij de eigenaar bent. De code stond in beeld na het installeren. Kwijt? Op de machine zelf: <code>cat /var/lib/unifi-sonar/setup-code</code>", "This shows Sonar that you are the owner. The code was displayed after installing. Lost it? On the machine itself: <code>cat /var/lib/unifi-sonar/setup-code</code>")}</div></div>
          <div class="field"><label for="first-pw">${L("Wachtwoord", "Password")}</label><input class="input" id="first-pw" type="password" autocomplete="new-password" minlength="${min}" required></div>
          <div class="field"><label for="first-rep">${L("Herhaal wachtwoord", "Repeat password")}</label><input class="input" id="first-rep" type="password" autocomplete="new-password" required></div>
          <div id="first-msg" role="alert"></div>
          <div class="wiz-actions"><button class="btn primary" id="first-go" type="submit">${L("Wachtwoord instellen", "Set password")}</button></div>
        </form></div>`;
      const fail = (text) => { $("#first-msg").innerHTML = `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(text)}</span></div>`; };
      $("#first-form").addEventListener("submit", async () => {
        if ($("#first-pw").value !== $("#first-rep").value) return fail(L("De twee wachtwoorden zijn niet gelijk.", "The two passwords do not match."));
        const b = $("#first-go");
        b.disabled = true;
        try {
          const r = await post("/api/auth/setup", { code: $("#first-code").value, password: $("#first-pw").value });
          v.innerHTML = `<div class="wizard login"><div class="wiz-brand"><span class="logo">${icon("radar")}</span><div><div class="wiz-title">UniFi Sonar</div></div></div><div class="card">${recoveryHTML(r.recovery_code)}<div class="wiz-actions"><button class="btn primary" id="first-done">${L("Ik heb de code bewaard", "I have saved the code")}</button></div></div></div>`;
          $("#first-done").addEventListener("click", loggedIn);
          $("#first-done").focus();
        } catch (e) { fail(e.message); b.disabled = false; }
      });
      $("#first-code").focus();
    };
    api("/api/auth/state").then((a) => {
      if (a.setup_needed) return firstPassword(a.min_length);
      if (passkeyPossible() && a.passkeys && $("#login-pk")) $("#login-pk").hidden = false;
    }).catch(() => {});
    $("#login-pk").addEventListener("click", async () => {
      try { await passkeyLogin(); await loggedIn(); }
      catch (e) { $("#login-msg").innerHTML = `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(passkeyError(e))}</span></div>`; }
    });
    $("#login-form").addEventListener("submit", async () => {
      const b = $("#login-go");
      b.disabled = true;
      try {
        await post("/api/auth/login", { password: $("#login-pw").value });
        await loggedIn();
      } catch (e) {
        $("#login-msg").innerHTML = `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(e.message)}</span></div>`;
        b.disabled = false;
        $("#login-pw").select();
      }
    });
    $("#login-pw").focus();
  }

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
    if ($("#view").dataset.mounted === "login") return;
    try {
      const status = await api("/api/status");
      state.status = status;
      if (status.setup_required) { if ($("#view").dataset.mounted !== "wizard") showWizard(); return; }
      if ($("#view").dataset.mounted === "wizard") return;   // wizard open voor een wijziging: niet overschrijven
      document.body.classList.remove("setup");
      if (current === "instellingen") {   // ook zonder meting bereikbaar, bijvoorbeeld om een veranderd certificaat te bevestigen
        renderStatus();
        if ($("#view").dataset.mounted !== "instellingen") mountSettings();
        UPDATERS.instellingen();
      }
      let snap;
      try { snap = await api("/api/snapshot"); }
      catch (e) {   // net gekoppeld: eerste meting loopt nog
        $("#status").innerHTML = `<span class="dot warn"></span>${L("Eerste meting wordt opgehaald…", "Fetching first reading…")}`;
        if (current !== "instellingen") $("#view").innerHTML = `<div class="card empty" style="margin-top:40px">${icon("radar")}<div>${L("Eerste meting wordt opgehaald…", "Fetching first reading…")}</div><div class="muted" style="font-size:13px;margin-top:4px">${esc(status.last_error || L("Dit duurt meestal een paar seconden.", "This usually takes a few seconds."))}</div></div>`;
        if (current !== "instellingen") $("#view").dataset.mounted = "";   // instellingen blijft staan: daar los je dit juist op
        setTimeout(refresh, 4000);
        return;
      }
      const issues = await api(`/api/issues?state=${state.showResolved ? "all" : "open"}`);
      state.snap = snap; state.issues = issues; state.th = status.thresholds;
      renderStatus();
      update();
    } catch (e) {
      if (e.auth) return;
      $("#status").innerHTML = `<span class="dot err"></span>${L("Geen data", "No data")}: ${esc(e.message)}`;
      if (!state.snap) $("#view").innerHTML = `<div class="banner err">${icon("octagon")}${L("Kan geen gegevens ophalen", "Cannot fetch data")}: ${esc(e.message)}</div>`;
    }
  }

  function renderStatus() {
    const s = state.status, h = state.snap?.health || {};
    const stale = s.last_ok && Date.now() / 1000 - s.last_ok > s.poll_seconds * 3;
    const dot = s.last_error || stale ? "err" : s.mode === "mock" ? "warn" : "";
    const src = s.mode === "mock" ? L("Demodata", "Demo data") : `Live · ${SOURCE_LABEL[s.source] || s.source || "?"}`;
    const age = L(`${ago(s.last_ok)} geleden`, `${ago(s.last_ok)} ago`);
    $("#status").innerHTML = `<span class="dot ${dot}"></span><span class="st-src">${esc(src)} · </span><span class="st-age">${age}</span>`;
    $("#status").title = `${src} · ${age}`;
    const top = (state.issues || []).filter((i) => !i.group && !i.resolved_at && !i.muted);
    [$("#nav-issues"), $("#tab-issues")].forEach((cnt) => {
      cnt.textContent = top.length;
      cnt.hidden = false;
      cnt.className = "count" + (h.critical ? " crit" : "");
    });
  }

  // ------------------------------------------------------------------ router
  const routes = { overzicht: mountOverview, issues: mountIssues, apparaten: mountDevices, clients: mountClients, internet: mountInternet, wereld: mountWorld, beveiliging: mountSecurity, tijdlijn: mountTimeline, instellingen: mountSettings, kiosk: mountKiosk };
  let current = null;
  const MORE_ROUTES = ["apparaten", "internet", "wereld", "tijdlijn", "instellingen"];
  function closeMore() { $("#more-sheet").hidden = true; $("#tab-more").setAttribute("aria-expanded", "false"); }
  function route() {
    const [name, id] = location.hash.replace(/^#\/?/, "").split("/");
    const before = current;
    current = routes[name] ? name : "overzicht";
    if (before && before !== current) window.scrollTo(0, 0);   // een andere pagina begint bovenaan
    closeMore();
    $("#tab-more").classList.toggle("on", MORE_ROUTES.includes(current));
    state.pendingOpen = id && current !== "kiosk" ? decodeURIComponent(id) : null;   // deep link naar een detailpaneel
    const kmode = current === "kiosk" && (id === "globe" || id === "paper") ? id : "";
    if (current !== "kiosk") stopKiosk();
    else if (kmode !== kio.mode) { stopKiosk(); kio.mode = kmode; $("#view").dataset.mounted = ""; }
    document.body.classList.toggle("kiosk", current === "kiosk");
    document.body.classList.toggle("kiosk-paper", current === "kiosk" && kio.mode === "paper");
    document.querySelectorAll(".nav a, .iconlink, .tabbar a, .more-sheet a").forEach((a) => { if (a.dataset.route === current) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
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
  const rangeSeg = (id) => `<div class="seg" role="group" aria-label="${L("Periode", "Period")}" id="${id}">${[1, 6, 24].map((h) => `<button data-h="${h}" aria-pressed="${state.hours === h}">${h} ${L("u", "h")}</button>`).join("")}</div>`;
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
  const reconnectBtn = (mac) => `<button class="linkbtn" data-reconnect="${esc(mac)}">${L("Opnieuw verbinden", "Reconnect")}</button>`;
  // ---- internet pauzeren: blokkeert het apparaat in UniFi tot een tijdstip
  const PAUSES = [["30", L("30 minuten", "30 minutes")], ["60", L("1 uur", "1 hour")], ["120", L("2 uur", "2 hours")],
    ["morning", L("Tot morgen 07:00", "Until tomorrow 07:00")], ["", L("Tot ik hervat", "Until I resume")]];
  // wie het precies is: naam, IP en MAC, zodat je zeker weet welk apparaat je blokkeert
  const whoLine = (mac, ip) => {
    const c = (state.snap?.clients || []).find((x) => x.mac === mac);
    const addr = [c?.ip || ip, mac].filter(Boolean).join(" · ");
    return `<div class="menu-who">${c?.name ? `<b>${esc(c.name)}</b>` : ""}<span>${esc(addr)}</span></div>`;
  };
  const pauseMenu = (mac) => `<details class="mute pause"><summary class="btn">${icon("power")}${L("Pauzeren", "Pause")}</summary><div class="mute-menu" role="group" aria-label="${L("Pauzeren voor", "Pause for")}">
      ${whoLine(mac)}${PAUSES.map(([v, l]) => `<button data-pause="${esc(mac)}" data-for="${v}">${l}</button>`).join("")}</div></details>`;
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
  // ---- quarantaine: blokkeren tot je het zelf vrijgeeft, met de reden erbij
  let qSeq = 0;
  const quarantineMenu = (mac, reason = "", small = false, ip = null) => {
    const id = `q-${++qSeq}`;
    return `<details class="mute pause qmenu"><summary class="btn${small ? " small" : ""} danger">${icon("shield")}${L("Quarantaine", "Quarantine")}</summary>
      <div class="mute-menu q-menu" role="group" aria-label="${L("In quarantaine zetten", "Put in quarantine")}">
        ${whoLine(mac, ip)}<p>${L("Sonar blokkeert het apparaat in UniFi: geen internet en geen netwerk, tot je het zelf vrijgeeft. Een schema laat het niet los.",
          "Sonar blocks the device in UniFi: no internet and no network until you release it. A schedule won't let it go.")}</p>
        <label for="${id}">${L("Reden", "Reason")}</label>
        <input class="input" id="${id}" maxlength="300" value="${esc(reason)}" placeholder="${L("bijv. malware gevonden", "e.g. malware found")}">
        <button class="btn small danger" data-quarantine="${esc(mac)}">${icon("shield")}${L("In quarantaine zetten", "Put in quarantine")}</button></div></details>`;
  };
  // het menu opent naar de kant waar ruimte is (rechts uitgelijnd tenzij de knop links op het scherm staat)
  document.addEventListener("toggle", (e) => {
    const d = e.target;
    if (!(d instanceof HTMLDetailsElement) || !d.classList.contains("qmenu") || !d.open) return;
    const m = d.querySelector(".q-menu"), r = d.getBoundingClientRect();
    const left = r.right < Math.min(340, window.innerWidth - 32) + 16;
    m.style.left = left ? "0" : "auto"; m.style.right = left ? "auto" : "0";
    m.querySelector("input")?.focus();
  }, true);
  const releaseBtn = (mac) => `<button class="btn small" data-release="${esc(mac)}">${icon("check")}${L("Vrijgeven", "Release")}</button>`;
  async function quarantineAction(e) {
    const b = e.target.closest("[data-quarantine]"), r = e.target.closest("[data-release]");
    if (!b && !r) return false;
    e.preventDefault();
    try {
      if (b) {
        const inp = b.parentElement.querySelector("input");
        if (!inp.value.trim()) { inp.focus(); return true; }
        b.disabled = true;
        await post(`/api/clients/${encodeURIComponent(b.dataset.quarantine)}/quarantine`, { reason: inp.value.trim() });
        if (state.drawer) closeDrawer();
      } else {
        const p = (await api("/api/pauses").catch(() => ({ pauses: [] }))).pauses.find((x) => x.mac === r.dataset.release);
        const who = p ? `${p.name}${p.ip ? ` (${p.ip})` : ""}` : r.dataset.release;
        if (!confirm(L(`${who} vrijgeven? Heb je het apparaat nagekeken? Het krijgt weer internet en netwerk.`, `Release ${who}? Have you checked the device? It gets internet and network back.`))) return true;
        r.disabled = true;
        await post(`/api/clients/${encodeURIComponent(r.dataset.release)}/resume`, {});
      }
    } catch (err) { alert(err.message); b && (b.disabled = false); }
    await refresh();
    if (current === "clients") loadPauses();
    if (current === "security") loadAdGuard();
    return true;
  }
  // ---- een naam geven (in UniFi)
  const nameForm = (mac, value) => `<form class="name-form" data-name-form="${esc(mac)}" novalidate>
      <label class="sr-only" for="nm-${esc(mac)}">${L("Naam", "Name")}</label>
      <input class="input" id="nm-${esc(mac)}" maxlength="60" value="${esc(value)}" placeholder="${L("Naam", "Name")}">
      <button class="btn small" type="submit">${L("Naam geven", "Set name")}</button></form>`;
  const CONF = { high: ["ok", () => L("Zeker", "Certain")], medium: ["info", () => L("Waarschijnlijk", "Likely")], low: ["", () => L("Gok", "Guess")] };
  const confBadge = (g) => g ? badge(CONF[g.confidence][0], CONF[g.confidence][1]()) : "";
  document.addEventListener("submit", async (e) => {
    const f = e.target.closest("[data-name-form]");
    if (!f) return;
    e.preventDefault();
    const inp = f.querySelector("input"), btn = f.querySelector("button");
    if (!inp.value.trim()) { inp.focus(); return; }
    btn.disabled = true;
    try {
      const r = await post(`/api/clients/${encodeURIComponent(f.dataset.nameForm)}/name`, { name: inp.value.trim() });
      btn.textContent = L("Opgeslagen", "Saved");
      if (state.drawer?.id === f.dataset.nameForm) $("#drawer-title").textContent = r.name;
      await refresh();
      if (current === "clients") loadIdentify();
    } catch (err) { alert(err.message); btn.disabled = false; }
  });
  async function reconnectAction(e) {
    const b = e.target.closest("[data-reconnect]");
    if (!b) return false;
    e.preventDefault();
    b.disabled = true;
    b.textContent = L("Bezig…", "Working…");
    try {
      const r = await fetch(`/api/clients/${encodeURIComponent(b.dataset.reconnect)}/reconnect`, { method: "POST" });
      const body = await r.json().catch(() => ({}));
      b.textContent = r.ok ? (body.demo ? L("Gedaan (demo)", "Done (demo)") : L("Verbindt opnieuw…", "Reconnecting…")) : `${L("Mislukt", "Failed")}: ${body.detail || r.status}`;
      if (r.ok) setTimeout(async () => { await refresh(); if (state.drawer) renderDrawer(); }, 8000);
    } catch (err) {
      b.textContent = L("Mislukt", "Failed");
    }
    return true;
  }
  // meldingen over de hele site: de plek in Sonar waar de details staan
  const ISSUE_TARGETS = [
    [/^vuln:outside_stale/, "beveiliging", "#h-vuln", () => L("Bekijk poort", "View port"), ".vuln-port.stale"],
    [/^vuln:/, "beveiliging", "#h-vuln", () => L("Bekijk bevinding", "View finding"), ".vuln-port.finding"],
    [/^advisory:/, "beveiliging", "#sec-adv", () => L("Bekijk advies", "View advisory")],
    [/^(adguard:|dns_new:|dns_bypass:|dns_threat:)/, "beveiliging", "#h-dns", () => L("Bekijk DNS", "View DNS")],
    [/^(fw_|segment)/, "beveiliging", "#sec-seg-card", () => L("Bekijk netwerkscheiding", "View segmentation")],
    [/^(pf_|upnp_|vpn_open)/, "beveiliging", "#sec-expo", () => L("Bekijk wat open staat", "View what's open")],
    [/^(wan_|speed_low|bufferbloat)/, "internet", null, () => L("Bekijk internet", "View internet")],
    [/^backup_stale/, "instellingen", "#h-backups", () => L("Bekijk backups", "View backups")],
    [/^cfg_(quieter|ch24)/, "apparaten", null, () => L("Bekijk apparaten", "View devices")],
    [/^mac_rotate/, "clients", null, () => L("Bekijk clients", "View clients")],
  ];
  // ---- springknoppen op lange pagina's: plakken onder de kopbalk en volgen waar je bent
  const jumpBar = (page, items) => `<nav class="jumpbar" aria-label="${L("Op deze pagina", "On this page")}">${items.map(([sel, l, quiet]) =>
    `<button class="chip" data-section="${page}" data-sel="${sel}"${quiet ? " data-quiet" : ""} aria-pressed="false">${esc(l)}</button>`).join("")}</nav>`;
  const stickyTop = () => ($(".topbar")?.offsetHeight || 0) + ($("#view .jumpbar")?.offsetHeight || 0);
  let spyQueued = false;
  function jumpSpy() {
    spyQueued = false;
    const bar = $("#view .jumpbar"); if (!bar) return;
    const line = stickyTop() + 40;
    let on = null;
    bar.querySelectorAll("button").forEach((b) => {
      const t = $(b.dataset.sel), box = t && (t.closest("section") || t);
      b.hidden = !box || box.hidden || box.offsetParent === null;
      if (!b.hidden && (box.getBoundingClientRect().top <= line || !on)) on = b;
    });
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) on = [...bar.querySelectorAll("button:not([hidden])")].pop() || on;
    bar.querySelectorAll("button").forEach((b) => {
      const is = b === on;
      if ((b.getAttribute("aria-pressed") === "true") !== is) {
        b.setAttribute("aria-pressed", is);
        if (is && bar.scrollWidth > bar.clientWidth) bar.scrollTo({ left: b.offsetLeft - bar.clientWidth / 2 + b.offsetWidth / 2, behavior: "auto" });
      }
    });
  }
  const queueSpy = () => { if (!spyQueued) { spyQueued = true; requestAnimationFrame(jumpSpy); } };
  window.addEventListener("scroll", queueSpy, { passive: true });
  window.addEventListener("resize", queueSpy);
  setInterval(queueSpy, 1500);      // kaarten laden na: knoppen van verborgen onderdelen bijwerken
  async function goSection(page, sel, fine, quiet) {
    if (state.drawer) closeDrawer();
    if (current !== page) location.hash = "#/" + page;
    const find = () => (current === page && sel ? $(sel) : null);
    if (!sel) { window.scrollTo(0, 0); return; }
    let el = find();
    for (let n = 0; !el && n < 40; n++) { await new Promise((r) => setTimeout(r, 75)); el = find(); }
    if (!el) return;
    let box = el.closest("section") || el;
    const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let gap = 12;   // bij een rij extra ruimte, zodat de kop erboven (welk apparaat) zichtbaar blijft
    // korte sprongen vloeiend, lange direct: schermen lang voorbij zien vliegen helpt niemand
    let smooth = false;
    const align = (instant) => {
      const top = box.getBoundingClientRect().top + window.scrollY - stickyTop() - gap;
      smooth = !instant && !calm && Math.abs(top - window.scrollY) < window.innerHeight * 1.5;
      window.scrollTo({ top, behavior: smooth ? "smooth" : "auto" });
    };
    align();
    box.setAttribute("tabindex", "-1");
    box.focus({ preventScroll: true });
    const flash = (n) => { n.classList.remove("section-flash"); void n.offsetWidth; n.classList.add("section-flash"); setTimeout(() => n.classList.remove("section-flash"), 2200); };
    if (!quiet) flash(box);
    if (fine) {     // de precieze rij: die wordt soms nog geladen
      let row = box.querySelector(fine);
      for (let n = 0; !row && n < 40 && current === page; n++) { await new Promise((r) => setTimeout(r, 75)); row = box.querySelector(fine); }
      if (row) {
        for (let d = row.closest("details"); d; d = d.parentElement?.closest("details")) d.open = true;
        box.classList.remove("section-flash");
        box = row;
        gap = 72;
        align();
        flash(row);
      }
    }
    // kaarten erboven laden nog en duwen hem weg: één keer bijstellen, tenzij je zelf al scrolt
    let moved = false;
    const stop = () => { moved = true; };
    window.addEventListener("wheel", stop, { once: true, passive: true });
    window.addEventListener("touchstart", stop, { once: true, passive: true });
    let fixed = false;
    const fix = () => {
      if (fixed) return;
      fixed = true;
      if (!moved && current === page) align(true);
      window.removeEventListener("wheel", stop); window.removeEventListener("touchstart", stop);
    };
    // nooit bijstellen terwijl een vloeiende scroll nog loopt: die schiet dan door
    if (smooth && "onscrollend" in window) {
      window.addEventListener("scrollend", () => setTimeout(fix, 200), { once: true });
      setTimeout(() => { fixed = true; window.removeEventListener("wheel", stop); window.removeEventListener("touchstart", stop); }, 4000);
    } else setTimeout(fix, smooth ? 1500 : 800);
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-section]");
    if (!b) return;
    e.preventDefault();
    goSection(b.dataset.section, b.dataset.sel || null, b.dataset.fine || null, "quiet" in b.dataset);
  });
  function entityAction(i) {
    if (i.client_mac && i.key.startsWith("quarantine:")) return "";   // geblokkeerd: UniFi toont hem niet meer als client
    if (i.client_mac) return `<button class="linkbtn" data-open="client" data-id="${esc(i.client_mac)}">${L("Bekijk client", "View client")}</button>`;
    const t = ISSUE_TARGETS.find(([rx]) => rx.test(i.key));
    if (t) return `<button class="linkbtn" data-section="${t[1]}"${t[2] ? ` data-sel="${t[2]}"` : ""}${t[4] ? ` data-fine="${t[4]}"` : ""}>${t[3]()}</button>`;
    if (i.device_mac) return `<button class="linkbtn" data-open="device" data-id="${esc(i.device_mac)}">${L("Bekijk", "View")} ${esc(devName(i.device_mac))}</button>`;
    return "";
  }
  // Wanneer kwam dit het laatst voor? Bij een voorval (herstart, blokkade, linkverlies) het tijdstip daarvan;
  // bij een toestand (zwak signaal, hoge CPU) de laatste meting waarin het nog zo was.
  function issueWhen(i) {
    const last = i.last_ts || (i.resolved_at ? i.last_seen : null);
    const at = (ts) => `<time datetime="${new Date(ts * 1000).toISOString()}" title="${esc(fullStamp(ts))}">${stamp(ts)}</time>`;
    const parts = [];
    if (last) parts.push(`${L("Laatst", "Last")} ${at(last)}${i.resolved_at ? "" : ` · ${L(`${ago(last)} geleden`, `${ago(last)} ago`)}`}`);
    else if (i.last_seen) parts.push(Date.now() / 1000 - i.last_seen < 180 ? L("Speelt nu", "Happening now") : `${L("Laatst gezien", "Last seen")} ${at(i.last_seen)}`);
    if (i.resolved_at) parts.push(`${L("opgelost", "resolved")} ${at(i.resolved_at)}`);
    else if (i.first_seen) parts.push(L(`melding sinds ${ago(i.first_seen)}`, `open for ${ago(i.first_seen)}`));
    return parts.map((p) => `<span>${p}</span>`).join("");
  }
  function muteCtlHTML(i) {
    const k = esc(i.key);
    return i.muted
      ? `<button class="mutebtn" data-unmute="${k}">${L("Niet meer negeren", "Stop ignoring")}</button>`
      : `<details class="mute"><summary class="mutebtn">${L("Negeren", "Ignore")}</summary><div class="mute-menu" role="group" aria-label="${L("Negeren voor", "Ignore for")}">
           ${[[1, L("1 dag", "1 day")], [7, L("1 week", "1 week")], [30, L("30 dagen", "30 days")], ["", L("Altijd", "Always")]].map(([d, l]) => `<button data-mute="${k}" data-days="${d}">${l}</button>`).join("")}</div></details>`;
  }
  function issueQuarantine(i) {
    if (i.resolved_at || !i.client_mac) return "";
    if (i.key.startsWith("quarantine:")) return releaseBtn(i.client_mac);
    if (i.key.startsWith("dns_threat:")) return quarantineMenu(i.client_mac, i.title, true);
    return "";
  }
  // advies: bij kritiek en waarschuwing meteen zichtbaar, bij info achter één klik (dat scheelt veel scrollen)
  function adviceHTML(i) {
    const box = `<div class="advice">${icon("bulb")}<span>${esc(i.advice)}</span></div>`;
    if (i.severity !== "info" || i.resolved_at) return box;
    const k = `adv:${i.key}`, open = state.expanded.has(k);
    return `<button class="toggle" aria-expanded="${open}" data-expand="${esc(k)}">${icon("chevron")}${open ? L("Verberg advies", "Hide advice") : L("Wat kun je doen?", "What can you do?")}</button>${open ? box : ""}`;
  }
  function issueHTML(i, all, flat) {
    const members = all.filter((m) => m.group === i.key);
    const open = state.expanded.has(i.key);
    const byClient = {};
    members.forEach((m) => (byClient[m.client_mac || m.key] ||= []).push(m));
    const memberHTML = members.length ? `
      <button class="toggle" aria-expanded="${open}" data-expand="${esc(i.key)}">${icon("chevron")}${open ? L("Verberg", "Hide") : L("Toon", "Show")} ${L("onderliggende meldingen", "underlying issues")} (${members.length})</button>
      ${open ? `<div class="members">${Object.values(byClient).map((ms) => `<div class="m">${sevBadge(ms[0].severity)}<div><b>${esc(ms[0].title.split(":")[0])}</b><span>${esc(ms.map((m) => m.detail.split(L(" op ", " on "))[0]).join(" · "))}</span></div><span class="m-act">${ms[0].reconnect ? reconnectBtn(ms[0].client_mac) : ""}${ms[0].client_mac ? `<button class="linkbtn" data-open="client" data-id="${esc(ms[0].client_mac)}">details</button>` : ""}</span></div>`).join("")}</div>` : ""}` : "";
    const when = issueWhen(i);
    const k = esc(i.key);
    const approveBtn = i.approve && !i.resolved_at ? `<button class="btn small" data-approve="${esc(i.approve)}">${icon("check")}${L("Ken ik", "I know this")}</button>` : "";
    const muteCtl = flat || i.resolved_at || i.group || i.approve ? "" : muteCtlHTML(i);
    const mutedBadge = i.muted ? badge("", i.muted_until ? `${L("Genegeerd t/m", "Ignored until")} ${new Date(i.muted_until * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short" })}` : L("Genegeerd (altijd)", "Ignored (always)")) : "";
    return `<article class="issue ${flat ? "flat" : ""} ${i.resolved_at ? "resolved" : ""} ${i.muted ? "muted" : ""}">
      <div class="sev ${i.severity}" aria-hidden="true">${icon(SEV[i.severity][1])}</div>
      <div>
        <div class="title">${esc(i.title)}</div>
        <div class="detail">${esc(i.detail)}</div>
        ${flat ? "" : adviceHTML(i)}
        ${memberHTML}
      </div>
      <div class="meta">${i.resolved_at ? badge("ok", L("Opgelost", "Resolved"), "check") : sevBadge(i.severity)}${mutedBadge}${when}${approveBtn}${issueQuarantine(i)}${entityAction(i)}${muteCtl}</div>
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
      <div class="page-head"><div><h1>${L("Netwerkoverzicht", "Network overview")}</h1><p class="subtitle" id="ov-sub"></p></div>${rangeSeg("ov-range")}</div>
      <div id="ov-banner"></div>
      <section class="grid kpis" id="ov-kpis" aria-label="${L("Kerncijfers", "Key figures")}"></section>
      <section class="card me-card" id="ov-me" hidden aria-label="${L("Dit apparaat", "This device")}"></section>
      <section class="grid cols-main" style="margin-bottom:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">${L("Wat vraagt aandacht", "Needs attention")}</h2><a href="#/issues" class="linkbtn">${L("Alle issues", "All issues")}</a></div><div class="issue-list" id="ov-issues"></div></div>
        <div class="card"><div class="card-head"><h2 style="margin:0">${L("Netwerk", "Network")}</h2><span class="muted" id="ov-topo-sub"></span></div><div class="topo" id="ov-topo"></div></div>
      </section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h2 style="margin:0">${L("Wifi per access point", "Wifi per access point")}</h2><span class="muted">${L(`gemiddelden over 15 minuten · drempel bezetting ${nf(state.th.radio_cu_warn)}%`, `15-minute averages · utilization threshold ${nf(state.th.radio_cu_warn)}%`)}</span></div><div class="table-wrap" style="border:0;background:none" id="ov-aps"></div><p class="help" id="ov-conn" style="margin:10px 0 0"></p></section>
      <section class="grid cols-2">
        <div class="card"><div class="card-head"><h3>${L("Internetlatency", "Internet latency")}</h3><span class="muted" id="ov-lat-sub"></span></div><div id="ch-lat"></div></div>
        <div class="card"><div class="card-head"><h3>${L("Gemiddelde wifi-ervaring", "Average wifi experience")}</h3><span class="muted">${L("satisfaction-score 0–100", "satisfaction score 0–100")}</span></div><div id="ch-sat"></div></div>
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
      ? stat(L("Bedraad via", "Wired via"), `${up.mac ? `<button class="linkbtn plain" data-open="device" data-id="${esc(up.mac)}">${esc(up.name || "–")}</button>` : "–"}${c.sw_port ? ` <span class="muted">${L("poort", "port")} ${c.sw_port}</span>` : ""}`)
      : stat(L("Verbonden met", "Connected to"), up.mac ? `<button class="linkbtn plain" data-open="device" data-id="${esc(up.mac)}">${esc(up.name || "–")}</button>` : "–") +
        stat("Band", `${esc(c.band || "–")} GHz <span class="muted">· ${L("kanaal", "channel")} ${esc(c.channel ?? "–")}</span>`) +
        stat(L("Signaal", "Signal"), signalBars(c.signal, c.band)) +
        stat(L("Snelheid", "Speed"), `${nf(c.tx_rate_mbps)} <span class="muted">/ ${nf(c.rx_rate_mbps)} Mbit/s</span>`);
    const roams = d.roams_today || [];
    const tip = !c.wired && c.band === "2.4" && c.signal != null && c.signal >= -60
      ? `<div class="me-hint">${icon("bulb")}<span>${L("Je zit op 2.4 GHz terwijl het signaal sterk is. Kan dit apparaat ook 5 of 6 GHz, dan helpt <b>Opnieuw verbinden</b> vaak: het kiest dan opnieuw.", "You are on 2.4 GHz while the signal is strong. If this device can also do 5 or 6 GHz, <b>Reconnect</b> often helps: it then chooses again.")}</span></div>` : "";
    el.hidden = false;
    el.innerHTML = `<div class="me-row">
        <div class="me-id"><span class="me-ic">${icon(c.wired ? "cable" : "wifi")}</span><div>
          <div class="me-label">${L("Dit apparaat", "This device")}${d.demo ? ` <span class="badge">demo</span>` : ""}</div>
          <div class="me-name">${esc(c.name)}</div>
          <div class="cell-sub">${esc(c.ip)}${c.ssid ? ` · ${esc(c.ssid)}` : ""}${c.assoc_ts ? ` · ${L("verbonden sinds", "connected since")} ${stamp(c.assoc_ts)}` : ""}</div></div></div>
        <div class="me-stats">${where}${stat(L("Ervaring", "Experience"), c.satisfaction == null ? "–" : nf(c.satisfaction))}
          ${c.wired ? "" : stat(L("AP-wissels vandaag", "AP switches today"), `${roams.length}${roams[0] ? ` <span class="muted" title="${esc(roams.slice(0, 5).map((r) => `${hhmm(r.ts)} ${r.message.split(": ").pop()}`).join("\n"))}">${L("laatst", "last")} ${hhmm(roams[0].ts)}</span>` : ""}`)}</div>
        <div class="me-act"><button class="btn" data-open="client" data-id="${esc(c.mac)}">Details</button>${c.wired ? "" : `<button class="btn" data-reconnect="${esc(c.mac)}">${L("Opnieuw verbinden", "Reconnect")}</button>`}</div>
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
    $("#ov-sub").textContent = `${s.wan.isp || "Internet"} · ${devs.length} ${L("apparaten", "devices")} · ${s.clients.length} clients`;
    $("#ov-banner").innerHTML = state.status.mode === "mock"
      ? `<div class="banner">${icon("info")}<span>${L(`Je bekijkt <b>demodata</b> met een paar ingebouwde problemen. <a href="#/instellingen">Koppel je eigen UniFi-controller</a> om je eigen netwerk te zien.`, `You are viewing <b>demo data</b> with a few built-in problems. <a href="#/instellingen">Connect your own UniFi controller</a> to see your own network.`)}</span></div>`
      : state.status.last_error ? `<div class="banner err">${icon("octagon")}<span>${L("Laatste poging mislukt", "Last attempt failed")}: ${esc(state.status.last_error)}</span></div>` : "";
    $("#ov-kpis").innerHTML = `
      <div class="card compact kpi"><div class="label">${icon("gauge")}${L("Netwerkscore", "Network score")}</div><div class="value">${h.score}<small>/100</small></div>
        <div class="sub">${badge(lv, lbl)}</div><div class="scorebar"><span style="width:${h.score}%;background:var(--me-${lv === "ok" ? "success" : lv === "warning" ? "warning" : "danger"})"></span></div></div>
      <div class="card compact kpi clickable" data-go="issues" tabindex="0" role="link"><div class="label">${icon("alert")}${L("Open issues", "Open issues")}</div><div class="value">${h.critical + h.warning + h.info}</div>
        <div class="sub">${h.critical ? badge("critical", `${h.critical} ${L("kritiek", "critical")}`) : ""}${h.warning ? badge("warning", `${h.warning} ${L("waarschuwing", "warning")}`) : ""}${h.info ? badge("info", `${h.info} info`) : ""}${!h.critical && !h.warning && !h.info ? badge("ok", L("Alles in orde", "All good"), "check") : ""}${h.muted ? badge("", `${h.muted} ${L("genegeerd", "ignored")}`) : ""}</div></div>
      <div class="card compact kpi clickable" data-go="apparaten" tabindex="0" role="link"><div class="label">${icon("router")}${L("Apparaten online", "Devices online")}</div><div class="value">${online}<small>/ ${devs.length}</small></div>
        <div class="sub"><span>${types.gateway} gateway</span><span>${types.switch} switches</span><span>${types.ap} ${L("AP's", "APs")}</span></div></div>
      <div class="card compact kpi clickable" data-go="clients" tabindex="0" role="link"><div class="label">${icon("users")}Clients</div><div class="value">${s.clients.length}</div>
        <div class="sub"><span>${icon("wifi")} ${wifi} wifi</span><span>${icon("cable")} ${s.clients.length - wifi} ${L("bedraad", "wired")}</span></div></div>
      <div class="card compact kpi clickable" data-go="internet" tabindex="0" role="link"><div class="label">${icon("globe")}Internet</div><div class="value">${s.wan.latency_ms == null ? "–" : nf(s.wan.latency_ms)}<small>ms</small></div>
        <div class="sub">${s.wan.up === false ? badge("critical", "Offline", "octagon") : badge("ok", "Online", "check")}<span>${L("verlies", "loss")} ${nf(s.wan.loss_pct, 1)}%</span></div></div>`;
    $("#ov-kpis").querySelectorAll("[data-go]").forEach((n) => {
      const go = () => (location.hash = "#/" + n.dataset.go);
      n.onclick = go; n.onkeydown = (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), go());
    });

    const top = state.issues.filter((i) => !i.group && !i.resolved_at && !i.muted).slice(0, 6);
    $("#ov-issues").innerHTML = top.length ? top.map((i) => issueHTML(i, state.issues, true)).join("")
      : `<div class="empty">${icon("check")}<div>${L("Geen problemen gevonden", "No problems found")}</div></div>`;

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
        <div><div class="name">${esc(d.name)}</div><div class="sub">${esc(d.model)} · ${d.num_clients} clients${d.client_issue_count ? ` · <span class="t-warning">${d.client_issue_count} ${L("client-meldingen", "client issues")}</span>` : ""}</div></div>
        <div class="right">${st}</div></div>`;
      (kids[d.mac] || []).sort((a, b) => order[a.type] - order[b.type] || a.name.localeCompare(b.name)).forEach((k) => walk(k, lvl + 1));
    };
    roots.sort((a, b) => order[a.type] - order[b.type]).forEach((r) => walk(r, 0));
    $("#ov-topo").innerHTML = html;
    $("#ov-topo").querySelectorAll(".node").forEach((n) => (n.onkeydown = (e) => e.key === "Enter" && openDrawer("device", n.dataset.id, n)));
    $("#ov-topo-sub").textContent = `${L("uptime gateway", "gateway uptime")} ${dur(devs.find((d) => d.type === "gateway")?.uptime)}`;

    // AP-tabel
    const aps = devs.filter((d) => d.type === "ap");
    const radioCell = (d, band) => {
      const r = d.radios.find((x) => x.radio === band);
      if (!r) return `<td class="muted">–</td>`;
      const lv = level("cu", r.cu_total);
      return `<td><div style="display:flex;gap:10px;align-items:center">${meter(r.cu_total, lv)}<span class="num ${lv !== "ok" ? "t-" + lv : ""}">${nf(r.cu_total)}%</span></div><div class="cell-sub">${L("kanaal", "channel")} ${r.channel ?? "–"} · ${L("storing", "interference")} ${nf(r.interference)}% · retries ${nf(r.retry_pct, 1)}%</div></td>`;
    };
    $("#ov-aps").innerHTML = `<table><thead><tr><th>Access point</th><th class="r">Clients</th><th>${L("2.4 GHz bezetting", "2.4 GHz utilization")}</th><th>${L("5 GHz bezetting", "5 GHz utilization")}</th><th class="r">${L("Ervaring", "Experience")}</th><th>Status</th></tr></thead><tbody>
      ${aps.map((d) => `<tr data-open data-id="${esc(d.mac)}" tabindex="0"><td><div class="cell-name">${esc(d.name)}</div><div class="cell-sub">${esc(d.model)}</div></td>
        <td class="r num">${d.num_clients}</td>${radioCell(d, "2.4")}${radioCell(d, "5")}
        <td class="r num ${level("sat", d.satisfaction) !== "ok" ? "t-" + level("sat", d.satisfaction) : ""}">${nf(d.satisfaction)}</td>
        <td>${d.issue_count || d.client_issue_count ? badge(worstSev(d.mac, true), plural(d.issue_count + d.client_issue_count, L("melding", "issue"), L("meldingen", "issues"))) : badge("ok", "OK", "check")}</td></tr>`).join("")}
      </tbody></table>`;
    $("#ov-aps").querySelectorAll("tr[data-open]").forEach((n) => (n.onkeydown = (e) => e.key === "Enter" && openDrawer("device", n.dataset.id, n)));
    loadOverviewCharts(); loadConnectivity();
  };
  async function loadConnectivity() {   // verbindingspogingen van het afgelopen etmaal, per band
    let d;
    try { d = await api("/api/wifi/connectivity"); } catch (e) { return; }
    const el = $("#ov-conn"), a = d.bands.all; if (!el) return;
    if (!a || !a.attempts) { el.textContent = ""; return; }
    const per = ["2.4", "5", "6"].filter((b) => d.bands[b]?.attempts).map((b) => `${b} GHz ${nf(d.bands[b].success, 0)}%`).join(" · ");
    el.innerHTML = `${icon(a.success < 90 ? "alert" : "check", a.success < 90 ? "t-warning" : "t-ok")} ${L(`Verbinden lukte in het afgelopen etmaal ${nf(a.success, 1)}% van de ${a.attempts} keer${a.failed ? ` (${a.failed} mislukt)` : ""}`,
      `Connecting succeeded ${nf(a.success, 1)}% of ${a.attempts} times in the past day${a.failed ? ` (${a.failed} failed)` : ""}`)} · ${per}`;
  }
  async function loadOverviewCharts() {
    const d = await api(`/api/history/overview?hours=${state.hours}`);
    const lat = d.wan.map((p) => [p.t, p.latency_ms]);
    const vals = lat.map((p) => p[1]).filter((v) => v != null);
    $("#ov-lat-sub").textContent = vals.length ? `${L("gem.", "avg.")} ${nf(vals.reduce((a, b) => a + b, 0) / vals.length)} ms · max ${nf(Math.max(...vals))} ms` : "";
    MEcharts.lineChart($("#ch-lat"), { series: [{ name: "Latency", color: C.cyan, data: lat }], unit: " ms", yMin: 0, bucket: d.bucket,
      threshold: { value: state.th.wan_latency_warn, label: `${L("drempel", "threshold")} ${nf(state.th.wan_latency_warn)} ms` }, label: L("Internetlatency in milliseconden", "Internet latency in milliseconds") });
    MEcharts.lineChart($("#ch-sat"), { series: [{ name: L("Ervaring", "Experience"), color: C.violet, data: d.clients.map((p) => [p.t, p.sat]) }], yMin: 0, yMax: 100, bucket: d.bucket,
      threshold: { value: state.th.client_satisfaction_warn, label: `${L("drempel", "threshold")} ${nf(state.th.client_satisfaction_warn)}` }, label: L("Gemiddelde wifi-ervaring", "Average wifi experience") });
  }

  // ------------------------------------------------------------------ issues
  function mountIssues() {
    const chips = (name, opts, cur) => opts.map(([v, l]) => `<button class="chip" data-${name}="${v}" aria-pressed="${cur === v}">${l}</button>`).join("");
    mount("issues", `
      <div class="page-head"><div><h1>Issues</h1><p class="subtitle">${L("Automatisch gevonden problemen, met uitleg en advies. Gelijksoortige meldingen zijn samengevoegd tot één oorzaak.", "Automatically detected problems, with explanation and advice. Similar issues are merged into one cause.")}</p></div>
        <div class="chips"><button class="chip" id="is-muted" aria-pressed="${state.showMuted}">${L("Genegeerd", "Ignored")} <span class="num" id="is-muted-n"></span></button>
        <button class="chip" id="is-resolved" aria-pressed="${state.showResolved}">${icon("clock")}${L("Ook opgeloste tonen", "Show resolved too")}</button></div></div>
      <div class="toolbar">
        <div class="chips" role="group" aria-label="${L("Ernst", "Severity")}">${chips("sev", [["all", L("Alles", "All")], ["critical", SEV.critical[0]], ["warning", SEV.warning[0]], ["info", "Info"]], state.issueSev)}</div>
        <div class="chips" role="group" aria-label="${L("Categorie", "Category")}">${chips("cat", [["all", L("Alle categorieën", "All categories")], ...["wifi", "switch", "device", "wan", "security", "config"].map((k) => [k, CAT[k]])], state.issueCat)}</div>
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
      : `<div class="card empty">${icon("check")}<div>${state.showMuted ? L("Geen genegeerde meldingen", "No ignored issues") : L("Geen issues voor deze filter", "No issues for this filter")}</div></div>`;
  };

  // ------------------------------------------------------------------ apparaten
  const devView = { mode: store.get("dv.mode", "map"), clients: store.get("dv.clients", false) };
  function mountDevices() {
    mount("apparaten", `<div class="page-head"><div><h1>${L("Apparaten", "Devices")}</h1><p class="subtitle">${L("Gateway, switches en access points. Klik voor details en historie.", "Gateway, switches and access points. Click for details and history.")}</p></div>
        <div class="w-head-r"><button class="chip" id="dv-cl" aria-pressed="${devView.clients}" ${devView.mode === "map" ? "" : "hidden"}>${icon("users")}${L("Clients tonen", "Show clients")}</button>
        <div class="seg" role="group" aria-label="${L("Weergave", "View")}" id="dv-mode">${[["map", L("Kaart", "Map")], ["list", L("Lijst", "List")]].map(([k, l]) => `<button data-m="${k}" aria-pressed="${devView.mode === k}">${l}</button>`).join("")}</div></div></div>
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
      const txt = [d.uplink_port ? `${L("poort", "port")} ${d.uplink_port}` : "", wireless ? L("draadloos", "wireless") : linkTxt(d.uplink_speed)].filter(Boolean).join(" · ");
      if (txt) labels.push(`<div class="tlabel ${cls}" style="left:${x2}px;top:${y2 - 22}px">${esc(txt)}</div>`);
    }
    const sevCls = (d) => (d.state !== "online" ? "critical" : d.issue_count ? worstSev(d.mac) : "ok");
    const nodes = devs.filter((d) => pos[d.mac]).map((d) => {
      const x = X(d.mac) - NW / 2, y = Y(d.mac);
      const sub = d.type === "ap" ? `${d.num_clients} clients` : d.type === "switch" ? `${d.ports.filter((p) => p.up).length}/${d.ports.length} ${L("poorten", "ports")} · ${d.num_clients} clients` : d.model;
      const cs = (cl[d.mac] || []).slice().sort((a, b) => (a.signal ?? 0) - (b.signal ?? 0));
      const dots = cs.slice(0, MAXC).map((c, i) => {
        const lv = c.wired ? "wired" : level("signal", c.signal, c.band);
        const left = (i % PER) * (DOT + 4) - ((Math.min(cs.length, PER) * (DOT + 4) - 4) / 2) + NW / 2;
        return `<button class="tdot ${lv}" style="left:${left}px;top:${NH + 10 + Math.floor(i / PER) * (DOT + 4)}px" data-open="client" data-id="${esc(c.mac)}" title="${esc(c.name)}${c.wired ? ` · ${L("bedraad", "wired")}` : ` · ${nf(c.signal)} dBm`}" aria-label="${esc(c.name)}"></button>`;
      }).join("") + (cs.length > MAXC ? `<span class="tmore" style="top:${NH + 10 + Math.ceil(MAXC / PER) * (DOT + 4)}px">+${cs.length - MAXC}</span>` : "");
      return `<div class="tnode sev-${sevCls(d)}" style="left:${x}px;top:${y}px;width:${NW}px">
        <button class="tcard" data-open="device" data-id="${esc(d.mac)}" aria-label="${esc(d.name)}"><span class="ico">${icon(devIcon(d.type))}</span>
          <span class="tt"><b>${esc(d.name)}</b><small>${esc(sub)}</small></span></button>${dots}</div>`;
    }).join("");
    el.innerHTML = `<div class="topo-map" style="width:${W}px;height:${H}px"><svg width="${W}" height="${H}" aria-hidden="true">${links.join("")}</svg>${labels.join("")}${nodes}</div>
      <div class="legend-row topo-legend"><span><i class="sw" style="background:var(--me-border-strong)"></i>${L("bedraad", "wired")}</span><span><i class="sw" style="background:var(--me-warning)"></i>${L("trager dan 1 Gbit/s", "slower than 1 Gbit/s")}</span>
        <span><i class="sw" style="background:var(--me-violet)"></i>${L("draadloos (mesh)", "wireless (mesh)")}</span><span><i class="sw" style="background:var(--me-danger)"></i>offline</span>
        ${devView.clients ? `<span><i class="sw" style="background:var(--me-success)"></i>${L("goed signaal", "good signal")}</span><span><i class="sw" style="background:var(--me-warning)"></i>${L("matig", "fair")}</span><span><i class="sw" style="background:var(--me-danger)"></i>${L("zwak", "weak")}</span>` : ""}</div>`;
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
      extra = `<div style="margin-top:14px"><div class="muted" style="font-size:12px">${L("Kanaalbezetting", "Channel utilization")}</div>${extra}</div>`;
    } else if (d.type === "switch") {
      const up = d.ports.filter((p) => p.up).length;
      extra = `<div style="margin-top:14px"><div class="muted" style="font-size:12px;margin-bottom:6px">${L(`${up} van ${d.ports.length} poorten actief`, `${up} of ${d.ports.length} ports active`)}${d.poe_budget_w ? ` · PoE ${nf(d.poe_used_w)} / ${nf(d.poe_budget_w)} W` : ""}</div>${portGrid(d, true)}</div>`;
    } else if (d.type === "gateway") {
      const w = state.snap.wan;
      extra = `<div class="stats" style="margin-top:8px"><div class="stat"><div class="k">Latency</div><div class="v">${nf(w.latency_ms)} ms</div></div><div class="stat"><div class="k">Download</div><div class="v">${nf(w.xput_down)} Mb</div></div><div class="stat"><div class="k">Upload</div><div class="v">${nf(w.xput_up)} Mb</div></div></div>`;
    }
    return `<article class="card dev-card clickable" data-open data-id="${esc(d.mac)}" tabindex="0" role="button" aria-label="${esc(d.name)}">
      <div class="top"><span class="ico">${icon(devIcon(d.type))}</span><div style="min-width:0;flex:1"><h3>${esc(d.name)}</h3><div class="muted" style="font-size:12px">${esc(d.model)} · ${esc(d.ip)}</div></div>${st}</div>
      <div class="stats"><div class="stat"><div class="k">Clients</div><div class="v">${d.num_clients}</div></div><div class="stat"><div class="k">Uptime</div><div class="v">${dur(d.uptime)}</div></div><div class="stat"><div class="k">${L("CPU / geh.", "CPU / mem.")}</div><div class="v">${nf(d.cpu)}% / ${nf(d.mem)}%</div></div></div>
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
      const tip = `${p.name} · ${p.up ? speed(p.speed) : L("geen link", "no link")}${p.poe_w ? ` · PoE ${nf(p.poe_w, 1)} W` : ""}${iss.length ? " · " + iss.map((i) => i.title.split(": ").pop()).join(", ") : ""}`;
      return `<span class="port ${cls} ${p.media.startsWith("SFP") ? "sfp" : ""}" title="${esc(tip)}" ${compact ? "" : 'tabindex="0"'} aria-label="${esc(tip)}">${p.idx}${p.poe_w > 0 ? '<i class="poe"></i>' : ""}</span>`;
    }).join("");
    return `<div class="ports">${cells}</div>`;
  }

  // ------------------------------------------------------------------ clients
  function mountClients() {
    const uplinks = state.snap.devices.filter((d) => d.type !== "gateway");
    mount("clients", `
      <div class="page-head"><div><h1>Clients</h1><p class="subtitle" id="cl-sub"></p></div>
        <div class="seg" role="group" aria-label="${L("Onderdeel", "Section")}" id="cl-tabs"></div></div>
      <div id="cl-pane-names" hidden>
        <section class="card" id="cl-identify" style="margin-bottom:16px" hidden></section></div>
      <div id="cl-pane-pause" hidden>
        <section class="card paused-card" id="cl-paused" hidden></section>
        <section class="card" id="cl-sched" style="margin-bottom:16px"></section></div>
      <div id="cl-pane-list">
      <div class="toolbar">
        <label class="search"><span class="sr-only">${L("Zoeken", "Search")}</span>${icon("search")}<input class="input" id="cl-q" placeholder="${L("Zoek op naam, IP, MAC of fabrikant", "Search by name, IP, MAC or vendor")}" value="${esc(state.cq)}"></label>
        <div class="chips" role="group" aria-label="Type" id="cl-kind">${[["all", L("Alle", "All")], ["wifi", "Wifi"], ["wired", L("Bedraad", "Wired")], ["issues", L("Met problemen", "With problems")]].map(([v, l]) => `<button class="chip" data-k="${v}" aria-pressed="${state.ckind === v}">${l}</button>`).join("")}</div>
        <label><span class="sr-only">${L("Verbonden met", "Connected to")}</span><select class="input" id="cl-up"><option value="">${L("Alle AP's en switches", "All APs and switches")}</option>${uplinks.map((d) => `<option value="${esc(d.mac)}" ${state.cuplink === d.mac ? "selected" : ""}>${esc(d.name)}</option>`).join("")}</select></label>
      </div>
      <div class="table-wrap" id="cl-table"></div></div>`);
    $("#cl-tabs").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-tab]"); if (!b) return;
      clTab.now = b.dataset.tab; store.set("cltab", clTab.now); renderClTabs();
    });
    renderClTabs();
    $("#cl-q").addEventListener("input", (e) => { state.cq = e.target.value; UPDATERS.clients(); });
    $("#cl-kind").addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      state.ckind = b.dataset.k; store.set("ckind", state.ckind);
      $("#cl-kind").querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === b));
      UPDATERS.clients();
    });
    $("#cl-up").addEventListener("change", (e) => { state.cuplink = e.target.value; UPDATERS.clients(); });
    $("#cl-identify").addEventListener("click", (e) => {
      if (e.target.closest("[data-id-all]")) { idState.all = !idState.all; renderIdentify(); return; }
      const o = e.target.closest("[data-open]"); if (o) openDrawer("client", o.dataset.id, o);
    });
    loadIdentify();
    $("#cl-table").addEventListener("click", (e) => {
      const s = e.target.closest("th button");
      if (s) { const k = s.dataset.sort; state.csort = { key: k, dir: state.csort.key === k ? -state.csort.dir : (k === "name" || k === "uplink" ? 1 : -1) }; store.set("csort", state.csort); UPDATERS.clients(); return; }
      const r = e.target.closest("tr[data-id]"); if (r) openDrawer("client", r.dataset.id, r);
    });
    $("#cl-table").addEventListener("keydown", (e) => { const r = e.target.closest("tr[data-id]"); if (r && e.key === "Enter") openDrawer("client", r.dataset.id, r); });
  }
  // ---- tabs: de lijst eerst; naamloze apparaten en pauzes staan erachter
  const clTab = { now: store.get("cltab", "list"), names: 0, paused: 0 };
  function renderClTabs() {
    const el = $("#cl-tabs"); if (!el) return;
    if (clTab.now === "names" && !clTab.names) clTab.now = "list";
    const tabs = [["list", L("Lijst", "List"), state.snap?.clients.length || 0, true], ["names", L("Zonder naam", "No name"), clTab.names, clTab.names > 0],
      ["pause", L("Pauzes", "Pauses"), clTab.paused, true]];
    const html = tabs.filter((t) => t[3]).map(([k, l, n]) => `<button data-tab="${k}" aria-pressed="${clTab.now === k}">${l}${k === "pause" && !n ? "" : ` <span class="tab-n${k === "pause" && n ? " warn" : ""}">${n}</span>`}</button>`).join("");
    if (el.innerHTML !== html) el.innerHTML = html;     // niet onnodig vervangen: de focus blijft dan staan
    for (const k of ["list", "names", "pause"]) $(`#cl-pane-${k}`).hidden = clTab.now !== k;
  }
  const idState = { data: null, all: false };
  async function loadIdentify() {
    try { idState.data = (await api("/api/identify")).devices; } catch (e) { return; }
    renderIdentify();
  }
  function renderIdentify() {
    const el = $("#cl-identify");
    if (!el || !idState.data) return;
    const all = idState.data, shown = idState.all ? all : all.slice(0, 6);
    el.hidden = !all.length;
    clTab.names = all.length; renderClTabs();
    const row = (d) => {
      const g = d.guess;
      const what = g ? `<b>${esc(g.label)}</b> · ${esc(g.kind_label)}` : L("Sonar weet het niet", "Sonar doesn't know");
      const sub = [d.ip, d.hostname && d.hostname !== d.name ? d.hostname : ""].filter(Boolean).join(" · ");
      return `<div class="id-row"><div class="id-main">
          <div class="id-title">${`<button class="linkbtn plain rank-name" data-open="client" data-id="${esc(d.mac)}">${esc(d.name)}</button>`}${confBadge(g)}</div>
          <div class="cell-sub">${what}${sub ? ` · ${esc(sub)}` : ""}</div>
          ${g ? `<div class="cell-sub">${esc(g.evidence.join(" · "))}</div>` : ""}
          ${g?.hint ? `<div class="cell-sub id-hint">${icon("bulb")}${esc(g.hint)}</div>` : ""}</div>
        ${nameForm(d.mac, g?.name || "")}</div>`;
    };
    el.innerHTML = `<div class="card-head"><h2 style="margin:0">${icon("search")}${L("Apparaten zonder naam", "Devices without a name")} <span class="muted">(${all.length})</span></h2>
        <span class="muted">${L("herkend aan wat ze opzoeken, hun fabrikant en hostnaam", "recognised by what they look up, their vendor and hostname")}</span></div>
      ${shown.map(row).join("")}
      ${all.length > 6 ? `<button class="linkbtn" data-id-all style="margin-top:10px">${idState.all ? L("Minder tonen", "Show fewer") : L(`Alle ${all.length} tonen`, `Show all ${all.length}`)}</button>` : ""}
      <p class="help" style="margin:12px 0 0">${L("De naam komt in UniFi zelf, dus ook de UniFi-app ziet hem. Controleer het voorstel even: het is een gok op basis van het verkeer van de afgelopen week.",
        "The name goes into UniFi itself, so the UniFi app sees it too. Check the suggestion first: it's a guess based on the past week's traffic.")}</p>`;
    hydrateIcons(el);
  }
  async function loadPauses() {
    let d, s;
    try { [d, s] = await Promise.all([api("/api/pauses"), api("/api/schedules")]); } catch (e) { return; }
    const el = $("#cl-paused");
    if (!el || current !== "clients") return;
    sched.data = s;
    if (!sched.edit) renderSchedules();
    const bySched = Object.entries(s.paused || {}).filter(([m]) => !d.pauses.some((p) => p.mac === m));
    el.hidden = !d.pauses.length && !bySched.length;
    clTab.paused = d.pauses.length + bySched.length; renderClTabs();
    const q = d.pauses.some((p) => p.reason);
    el.innerHTML = `<div class="card-head"><h2 style="margin:0">${icon(q ? "shield" : "power")}${q ? L("Gepauzeerd en in quarantaine", "Paused and in quarantine") : L("Gepauzeerd", "Paused")}</h2><span class="muted">${q ? L("geen internet of netwerk tot de tijd om is of je het vrijgeeft", "no internet or network until the time is up or you release it") : L("geen internet of netwerk tot de tijd om is", "no internet or network until the time is up")}</span></div>
      ${d.pauses.map((p) => p.reason ? `<div class="rank-row paused-row"><div class="rank-main"><div class="rank-name">${esc(p.name)} ${badge("critical", L("Quarantaine", "Quarantine"), "shield")}</div>
        <div class="cell-sub">${p.ip ? `${esc(p.ip)} · ` : ""}${esc(p.reason)} · ${L("sinds", "since")} ${stamp(p.created)}</div></div>${releaseBtn(p.mac)}</div>`
        : `<div class="rank-row paused-row"><div class="rank-main"><div class="rank-name">${esc(p.name)}</div>
        <div class="cell-sub">${p.ip ? `${esc(p.ip)} · ` : ""}${p.until ? L(`tot ${stamp(p.until)} · nog ${dur(p.until - d.now)}`, `until ${stamp(p.until)} · ${dur(p.until - d.now)} left`) : L("tot je hervat", "until you resume")} · ${L("sinds", "since")} ${stamp(p.created)}</div></div>
        <button class="btn small" data-resume="${esc(p.mac)}">${icon("check")}${L("Hervatten", "Resume")}</button></div>`).join("")}
      ${bySched.map(([m, a]) => `<div class="rank-row paused-row"><div class="rank-main"><div class="rank-name">${esc(a.name)}</div>
        <div class="cell-sub">${((sn) => L(`volgens '${sn}' tot ${stamp(a.until)}`, `by '${sn}' until ${stamp(a.until)}`))(esc(s.schedules.find((x) => x.id === a.id)?.name || ""))}</div></div>
        <span class="badge">${icon("clock")}${L("Schema", "Schedule")}</span></div>`).join("")}`;
  }
  // ---- vaste pauzetijden
  const sched = { data: null, edit: null, q: "" };
  const dayNames = () => DAYS;
  const schedDays = (days) => (days.length === 7 ? L("elke dag", "every day") : days.join() === "0,1,2,3,4" ? L("ma–vr", "Mon–Fri")
    : days.join() === "5,6" ? L("weekend", "weekend") : days.map((d) => DAYS[d]).join(" "));
  function renderSchedules() {
    const el = $("#cl-sched"); if (!el || !sched.data) return;
    const e = sched.edit;
    const head = `<div class="card-head"><h2 style="margin:0">${icon("clock")}${L("Vaste pauzetijden", "Fixed pause times")}</h2>
      ${e ? "" : `<button class="btn small" data-sch="new">${L("Nieuw schema", "New schedule")}</button>`}</div>`;
    if (!e) {
      el.innerHTML = head + (sched.data.schedules.length ? sched.data.schedules.map((s) => `<div class="rank-row sched-row">
          <div class="rank-main"><div class="rank-name">${esc(s.name)} ${s.until ? badge("warning", L(`actief tot ${stamp(s.until)}`, `active until ${stamp(s.until)}`)) : ""}${s.enabled ? "" : ` ${badge("", L("uit", "off"))}`}</div>
          <div class="cell-sub">${schedDays(s.days)} · ${esc(s.start)}–${esc(s.stop)} · ${esc(s.devices.map((x) => x.name).slice(0, 4).join(", "))}${s.devices.length > 4 ? ` +${s.devices.length - 4}` : ""}</div></div>
          <button class="linkbtn" data-sch="edit" data-id="${s.id}">${L("Wijzigen", "Edit")}</button></div>`).join("")
        : `<p class="muted" style="margin:0">${L("Bijvoorbeeld: de apparaten van de kinderen op schooldagen van 21:00 tot 07:00 zonder internet. Sonar blokkeert ze dan in UniFi en laat ze daarna vanzelf weer toe.", "For example: the kids' devices without internet on school nights from 21:00 to 07:00. Sonar blocks them in UniFi and lets them back in afterwards.")}</p>`);
      hydrateIcons(el);
      return;
    }
    const q = sched.q.toLowerCase();
    const all = [...state.snap.clients.map((c) => ({ mac: c.mac, name: c.name, sub: c.vendor || c.ip }))];
    e.devices.forEach((x) => { if (!all.some((c) => c.mac === x.mac)) all.push({ mac: x.mac, name: x.name, sub: L("niet verbonden", "not connected") }); });
    const list = all.filter((c) => !q || `${c.name} ${c.sub}`.toLowerCase().includes(q) || e.macs.includes(c.mac))
      .sort((a, b) => (e.macs.includes(b.mac) - e.macs.includes(a.mac)) || a.name.localeCompare(b.name));
    el.innerHTML = head + `<form class="sched-form" onsubmit="return false">
      <div class="form-grid"><div class="field"><label for="sch-name">${L("Naam", "Name")}</label><input class="input" id="sch-name" maxlength="60" value="${esc(e.name)}" placeholder="${L("bijv. Kinderen", "e.g. Kids")}"></div>
        <div class="field sched-times"><label>${L("Tijd", "Time")}</label><div><input class="input" type="time" id="sch-start" value="${esc(e.start)}"> – <input class="input" type="time" id="sch-stop" value="${esc(e.stop)}"></div></div></div>
      <div class="field"><label>${L("Dagen", "Days")}</label><div class="chips" id="sch-days">${dayNames().map((n, i) => `<button type="button" class="chip" data-day="${i}" aria-pressed="${e.days.includes(i)}">${n}</button>`).join("")}</div>
        <div class="help">${L("Een schema over middernacht hoort bij de dag waarop het begint.", "A schedule past midnight belongs to the day it starts.")}</div></div>
      <div class="field"><label for="sch-q">${L("Apparaten", "Devices")} <span class="muted">(${e.macs.length})</span></label>
        <input class="input" id="sch-q" placeholder="${L("Zoek een apparaat", "Search a device")}" value="${esc(sched.q)}">
        <div class="sched-devs">${list.slice(0, 60).map((c) => `<label class="check"><input type="checkbox" data-mac="${esc(c.mac)}" ${e.macs.includes(c.mac) ? "checked" : ""}> ${esc(c.name)} <span class="muted">${esc(c.sub || "")}</span></label>`).join("")}</div></div>
      <label class="check" style="margin-top:12px"><input type="checkbox" id="sch-on" ${e.enabled ? "checked" : ""}> ${L("Schema aan", "Schedule on")}</label>
      ${sched.err ? `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(sched.err)}</span></div>` : ""}
      <div class="wiz-actions"><button type="button" class="btn primary" data-sch="save">${L("Opslaan", "Save")}</button><button type="button" class="btn ghost" data-sch="cancel">${L("Annuleren", "Cancel")}</button>
        ${e.id ? `<button type="button" class="btn ghost" data-sch="delete">${L("Verwijderen", "Delete")}</button>` : ""}</div></form>`;
    hydrateIcons(el);
  }
  function readSchedule() {
    const e = sched.edit; if (!e) return;
    e.name = $("#sch-name").value; e.start = $("#sch-start").value; e.stop = $("#sch-stop").value; e.enabled = $("#sch-on").checked;
  }
  $("#view").addEventListener("input", (ev) => { if (ev.target.id === "sch-q") { readSchedule(); sched.q = ev.target.value; renderSchedules(); const q = $("#sch-q"); q.focus(); q.setSelectionRange(q.value.length, q.value.length); } });
  $("#view").addEventListener("change", (ev) => {
    const c = ev.target.closest("[data-mac]"); if (!c || !sched.edit) return;
    const m = c.dataset.mac, e = sched.edit;
    e.macs = c.checked ? [...new Set([...e.macs, m])] : e.macs.filter((x) => x !== m);
    if (c.checked && !e.devices.some((x) => x.mac === m)) e.devices.push({ mac: m, name: cliByMac()[m]?.name || m });
    const lbl = $("#cl-sched .field label[for=sch-q] .muted"); if (lbl) lbl.textContent = `(${e.macs.length})`;
  });
  $("#view").addEventListener("click", async (ev) => {
    const d = ev.target.closest("[data-day]");
    if (d && sched.edit) { const i = +d.dataset.day, e = sched.edit; e.days = e.days.includes(i) ? e.days.filter((x) => x !== i) : [...e.days, i].sort(); d.setAttribute("aria-pressed", e.days.includes(i)); return; }
    const b = ev.target.closest("[data-sch]"); if (!b) return;
    const act = b.dataset.sch;
    sched.err = null;
    if (act === "new") { sched.edit = { name: "", start: "21:00", stop: "07:00", days: [0, 1, 2, 3, 4], macs: [], devices: [], enabled: true }; sched.q = ""; }
    if (act === "edit") { const s = sched.data.schedules.find((x) => x.id === +b.dataset.id); sched.edit = JSON.parse(JSON.stringify(s)); sched.q = ""; }
    if (act === "cancel") sched.edit = null;
    if (act === "save" || act === "delete") {
      readSchedule();
      try {
        if (act === "save") await post("/api/schedules/save", { id: sched.edit.id || null, name: sched.edit.name, macs: sched.edit.macs, days: sched.edit.days, start: sched.edit.start, stop: sched.edit.stop, enabled: sched.edit.enabled });
        else if (confirm(L("Dit schema verwijderen?", "Delete this schedule?"))) await post("/api/schedules/delete", { id: sched.edit.id });
        else return;
        sched.edit = null;
        await loadPauses();
        await refresh();
      } catch (err) { sched.err = err.message; }
    }
    renderSchedules();
  });

  UPDATERS.clients = function () {
    loadPauses();
    const dm = devByMac();
    const q = state.cq.trim().toLowerCase();
    const uplinkName = (c) => (c.wired ? `${dm[c.sw_mac]?.name || "–"} · ${L("poort", "port")} ${c.sw_port ?? "?"}`
      : c.connected === false ? L(`niet verbonden · laatst via ${dm[c.last_ap_mac]?.name || "?"}`, `not connected · last via ${dm[c.last_ap_mac]?.name || "?"}`) : `${dm[c.ap_mac]?.name || "–"}`);
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
    $("#cl-sub").textContent = L(`${state.snap.clients.length} verbonden · ${wifi} wifi · ${state.snap.clients.length - wifi} bedraad · ${bad} met problemen`,
      `${state.snap.clients.length} connected · ${wifi} wifi · ${state.snap.clients.length - wifi} wired · ${bad} with problems`);
    const th = (k, l, cls = "") => `<th class="${cls}" ${state.csort.key === k ? `aria-sort="${state.csort.dir > 0 ? "ascending" : "descending"}"` : ""}><button data-sort="${k}">${l}${state.csort.key === k ? (state.csort.dir > 0 ? " ↑" : " ↓") : ""}</button></th>`;
    $("#cl-table").innerHTML = rows.length ? `<table><thead><tr>${th("name", L("Naam", "Name"))}${th("uplink", L("Verbonden met", "Connected to"))}${th("signal", L("Signaal", "Signal"))}${th("retry", "Retries", "r")}${th("sat", L("Ervaring", "Experience"), "r")}${th("rate", L("Snelheid", "Speed"), "r")}<th>IP</th>${th("issues", "Status")}</tr></thead><tbody>
      ${rows.map((c) => {
        const rl = level("retry", c.retry_pct), sl = level("sat", c.satisfaction);
        return `<tr data-id="${esc(c.mac)}" tabindex="0" ${state.drawer?.id === c.mac ? 'aria-selected="true"' : ""}>
          <td><div class="cell-name">${esc(c.name)}</div><div class="cell-sub">${esc(c.vendor || c.mac)}</div></td>
          <td><div style="display:flex;gap:8px;align-items:center">${icon(c.wired ? "cable" : "wifi")}<div><div>${esc(uplinkName(c))}</div><div class="cell-sub">${c.wired ? L("bedraad", "wired") : c.connected === false ? `${c.last_seen ? L(`${ago(c.last_seen)} geleden gezien`, `seen ${ago(c.last_seen)} ago`) : L("even weg", "briefly away")}` : `${c.band} GHz · ${L("kanaal", "channel")} ${c.channel} · ${proto(c.proto)}`}</div></div></div></td>
          <td>${c.wired ? '<span class="muted">–</span>' : signalBars(c.signal, c.band)}</td>
          <td class="r num ${rl && rl !== "ok" ? "t-" + rl : ""}">${c.retry_pct == null ? "–" : nf(c.retry_pct, 1) + "%"}</td>
          <td class="r num ${sl && sl !== "ok" ? "t-" + sl : ""}">${nf(c.satisfaction)}</td>
          <td class="r num">${c.wired ? "–" : nf(c.tx_rate_mbps) + " Mbit/s"}</td>
          <td class="num muted">${esc(c.ip)}</td>
          <td>${c.connected === false ? badge("", L("Niet verbonden", "Not connected")) : c.issue_count ? badge(c.score < 70 ? "critical" : "warning", plural(c.issue_count, L("probleem", "problem"), L("problemen", "problems")), "alert") : badge("ok", "OK", "check")}</td></tr>`;
      }).join("")}</tbody></table>` : `<div class="empty">${L("Geen clients gevonden", "No clients found")}</div>`;
  };

  // ------------------------------------------------------------------ internet
  const net = { hours: store.get("net.hours", 24), live: [], timer: null, data: null, last: null, wasRunning: false,
                usage: null, usagePeriod: store.get("net.usage", "day"), cuPeriod: store.get("net.cu", "day"), self: { busy: false } };
  const mb = (bps) => (bps == null ? null : bps / 1e6);
  const mbTxt = (v) => (v == null ? "–" : nf(v, v < 10 ? 1 : 0));
  const dateTxt = (t, withTime) => new Date(t * 1000).toLocaleString(LOC, withTime ? { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "short" });
  function mountInternet() {
    mount("internet", `
      <div class="page-head"><div><h1>Internet</h1><p class="subtitle" id="net-sub">${L("Live verkeer en de snelheid van je verbinding.", "Live traffic and the speed of your connection.")}</p></div>
        <div class="seg" role="group" aria-label="${L("Periode", "Period")}" id="net-range">${[[6, L("6 u", "6 h")], [24, L("24 u", "24 h")], [168, "7 d"]].map(([h, l]) => `<button data-h="${h}" aria-pressed="${net.hours === h}">${l}</button>`).join("")}</div></div>
      <div id="net-banner"></div>
      <section class="grid kpis net-kpis" id="net-kpis" aria-label="${L("Internet nu", "Internet now")}"></section>
      <section class="grid cols-main" style="margin-bottom:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">${L("Live verkeer", "Live traffic")}</h2><span class="muted" id="net-live-sub"></span></div><div id="net-live"></div>
          <p class="help" style="margin:8px 0 0">${L("De gateway geeft zijn tellers om de 10 à 45 seconden door aan UniFi; daarom springt de lijn in stapjes.", "The gateway passes its counters to UniFi every 10 to 45 seconds; that is why the line moves in steps.")}</p></div>
        <div class="card" id="net-test" aria-live="polite"></div>
      </section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h3>${L("Internetverkeer", "Internet traffic")}</h3><span class="muted" id="net-hist-sub"></span></div><div id="net-hist"></div></section>
      <section class="card" style="margin-bottom:16px" id="net-usage"><div class="card-head"><h3>${L("Datagebruik", "Data usage")}</h3>
          <div class="seg" role="group" aria-label="${L("Per dag of per maand", "Per day or per month")}" id="net-usage-seg">${[["day", L("Per dag", "Per day")], ["month", L("Per maand", "Per month")]].map(([k, l]) => `<button data-p="${k}" aria-pressed="${net.usagePeriod === k}">${l}</button>`).join("")}</div></div>
        <div class="usage-kpis" id="net-usage-kpis"></div><div id="net-usage-chart"></div>
        <p class="help" id="net-usage-note" style="margin:8px 0 0"></p></section>
      <section class="card" style="margin-bottom:16px" id="net-cu"><div class="card-head"><h3>${L("Verbruik per apparaat", "Usage per device")}</h3>
          <div class="seg" role="group" aria-label="${L("Periode", "Period")}" id="net-cu-seg">${[["day", L("Vandaag", "Today")], ["week", L("7 dagen", "7 days")], ["month", L("30 dagen", "30 days")]].map(([k, l]) => `<button data-p="${k}" aria-pressed="${net.cuPeriod === k}">${l}</button>`).join("")}</div></div>
        <div class="rank" id="net-cu-list"></div><p class="help" id="net-cu-note" style="margin:8px 0 0"></p></section>
      <section class="grid cols-2" style="margin-bottom:16px">
        <div class="card" id="net-out"><div class="card-head"><h3>${L("Storingen en beschikbaarheid", "Outages and availability")}</h3><span class="muted" id="net-out-sub"></span></div><div id="net-out-body"></div></div>
        <div class="card" id="net-self" aria-live="polite"><div class="card-head"><h3>${L("Wifi-snelheid op deze plek", "Wifi speed at this spot")}</h3></div><div id="net-self-body"></div></div>
      </section>
      <section class="card"><div class="card-head"><h3>${L("Speedtests", "Speed tests")}</h3><span class="muted" id="net-st-sub">${L("afgelopen 90 dagen", "past 90 days")}</span></div><div id="net-st-chart"></div>
        <div class="table-wrap" style="border:0;margin-top:12px" id="net-st-table"></div></section>`);
    $("#net-range").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-h]"); if (!b) return;
      net.hours = +b.dataset.h; store.set("net.hours", net.hours);
      $("#net-range").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      loadInternet();
    });
    $("#net-test").addEventListener("click", (e) => { if (e.target.closest("[data-st=start]")) startSpeedtest(); });
    $("#net-cu-seg").addEventListener("click", (e) => {
      const b = e.target.closest("[data-p]"); if (!b) return;
      net.cuPeriod = b.dataset.p; store.set("net.cu", net.cuPeriod);
      $("#net-cu-seg").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      loadClientUsage();
    });
    $("#net-cu-list").addEventListener("click", (e) => { const n = e.target.closest("[data-open]"); if (n) openDrawer("client", n.dataset.id, n); });
    $("#net-self").addEventListener("click", (e) => { if (e.target.closest("[data-self=start]")) runSelftest(); });
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
    $("#net-sub").textContent = [w.isp, w.link_mbps ? `${L("WAN-poort", "WAN port")} ${speed(w.link_mbps)}` : null, L("live verkeer en snelheid", "live traffic and speed")].filter(Boolean).join(" · ");
    $("#net-banner").innerHTML = d.available ? "" : `<div class="banner err">${icon("info")}<span>${L("Live verkeer en speedtests zijn alleen beschikbaar via de uitgebreide UniFi-API (API-key of lokaal account).", "Live traffic and speed tests are only available via the extended UniFi API (API key or local account).")}</span></div>`;
    $("#net-hist-sub").textContent = `${L("gemiddeld per", "average per")} ${d.bucket >= 3600 ? d.bucket / 3600 + L(" uur", " h") : d.bucket / 60 + " min"}`;
    MEcharts.lineChart($("#net-hist"), { series: [
      { name: "Download", color: C.cyan, data: d.series.map((p) => [p.t, mb(p.rx)]) },
      { name: "Upload", color: C.violet, data: d.series.map((p) => [p.t, mb(p.tx)]) }],
      unit: " Mbit/s", yMin: 0, bucket: d.bucket, label: L("Internetverkeer in Mbit/s", "Internet traffic in Mbit/s"),
      xfmt: net.hours > 48 ? (t) => dateTxt(t) : undefined });
    const st = d.speedtests;
    $("#net-st-sub").textContent = st.length ? `${plural(st.length, "test", "tests")} ${L("in de afgelopen 90 dagen", "in the past 90 days")}` : L("afgelopen 90 dagen", "past 90 days");
    MEcharts.lineChart($("#net-st-chart"), { series: [
      { name: "Download", color: C.cyan, data: st.map((r) => [r.ts, r.down]) },
      { name: "Upload", color: C.violet, data: st.map((r) => [r.ts, r.up]) }],
      unit: " Mbit/s", yMin: 0, bucket: 86400 * 4, markers: true, label: L("Speedtest-resultaten", "Speed test results"),
      xfmt: (t) => dateTxt(t), tfmt: (t) => dateTxt(t, true) });
    $("#net-st-table").innerHTML = st.length ? `<table><thead><tr><th>${L("Wanneer", "When")}</th><th class="r">Download</th><th class="r">Upload</th><th class="r">Ping</th><th>Server</th></tr></thead><tbody>
      ${st.slice(-10).reverse().map((r) => `<tr style="cursor:default"><td class="num">${dateTxt(r.ts, true)}</td><td class="r num">${mbTxt(r.down)} Mbit/s</td><td class="r num">${mbTxt(r.up)} Mbit/s</td><td class="r num">${r.latency == null ? "–" : nf(r.latency) + " ms"}</td><td class="muted">${esc(r.server || "–")}</td></tr>`).join("")}</tbody></table>`
      : `<div class="empty">${L("Nog geen speedtests. Start er hierboven een.", "No speed tests yet. Start one above.")}</div>`;
    renderNetKpis(); renderTest(); loadUsage(); loadClientUsage(); loadOutages(); if (!net.self.busy) loadSelftests();
  }
  // ---- verbruik per apparaat
  async function loadClientUsage() {
    let d;
    try { d = await api(`/api/usage/clients?period=${net.cuPeriod}`); } catch (e) { return; }
    const el = $("#net-cu-list"); if (!el) return;
    const max = Math.max(1, ...d.rows.map((r) => r.total));
    el.innerHTML = d.rows.length ? d.rows.slice(0, 15).map((r) => `<div class="rank-row cu-row"><div class="rank-main">
        <div class="rank-name">${cliByMac()[r.mac] ? `<button class="linkbtn plain" data-open="client" data-id="${esc(r.mac)}">${esc(r.name)}</button>` : esc(r.name)}</div>
        <div class="cell-sub">↓ ${gb(r.down)} · ↑ ${gb(r.up)}${r.cats.length ? ` · ${r.cats.map((c) => esc(c.cat)).join(", ")}` : ""}</div></div>
        <div class="rank-bar">${meter(100 * r.total / max)}</div><span class="num rank-n">${gb(r.total)}</span></div>`).join("")
      : `<div class="empty">${d.error ? `${L("Ophalen lukte niet", "Fetching failed")}: ${esc(d.error)}` : L("Nog geen gegevens; UniFi levert ze per uur.", "No data yet; UniFi delivers it hourly.")}</div>`;
    $("#net-cu-note").textContent = d.rows.length ? L(`${d.devices} apparaten. Het gaat om al het verkeer, dus ook binnen je netwerk (bijvoorbeeld camera's naar je NAS).${d.dpi ? "" : " Per categorie (video, games…) ziet Sonar het pas als 'Traffic Identification' in UniFi aanstaat."}`,
      `${d.devices} devices. This is all traffic, including within your network (for example cameras to your NAS).${d.dpi ? "" : " Per category (video, games…) is only shown once 'Traffic Identification' is on in UniFi."}`) : "";
  }
  // ---- internetstoringen
  async function loadOutages() {
    let d;
    try { d = await api("/api/outages"); } catch (e) { return; }
    const el = $("#net-out-body"); if (!el) return;
    if (!d.available) {
      el.innerHTML = `<p class="muted">${d.error ? esc(d.error) : L("Storingen zijn alleen te zien via de uitgebreide UniFi-API.", "Outages are only available via the extended UniFi API.")}</p>`;
      return;
    }
    const pct = (v) => `${nf(v, v >= 99.995 ? 0 : v >= 99.9 ? 3 : 2)}%`;
    const tile = (k, v) => `<div class="usage-kpi"><div class="k">${k}</div><div class="v ${v < 99.5 ? "t-warning" : ""}">${pct(v)}</div></div>`;
    $("#net-out-sub").textContent = d.isp || "";
    const fmtDur = (s) => (s < 90 ? `${s} s` : dur(s));
    el.innerHTML = `<div class="usage-kpis">${tile(L("24 uur", "24 hours"), d.uptime.day)}${tile(L("7 dagen", "7 days"), d.uptime.week)}${tile(L("30 dagen", "30 days"), d.uptime.month)}${tile(L("90 dagen", "90 days"), d.uptime.quarter)}</div>
      <div class="out-months">${d.months.map((m) => `<div class="out-month" title="${esc(`${m.n} ${L("storingen", "outages")} · ${fmtDur(m.seconds)}`)}"><span>${new Date(m.ts * 1000).toLocaleDateString(LOC, { month: "short" })}</span>
        <b class="num ${m.uptime < 99.5 ? "t-warning" : ""}">${pct(m.uptime)}</b><small class="muted">${m.n ? `${m.n}× · ${fmtDur(m.seconds)}` : L("geen", "none")}</small></div>`).join("")}</div>
      ${d.outages.length ? `<div class="table-wrap" style="border:0;margin-top:10px"><table><thead><tr><th>${L("Begin", "Start")}</th><th class="r">${L("Duur", "Duration")}</th><th>${L("Verbinding", "Connection")}</th></tr></thead><tbody>
        ${d.outages.slice(0, 12).map((o) => `<tr style="cursor:default"><td class="num" title="${esc(fullStamp(o.ts))}">${dateTxt(o.ts, true)}</td><td class="r num">${fmtDur(o.seconds)}</td><td class="muted">${esc(o.wan)}</td></tr>`).join("")}</tbody></table></div>`
        : `<div class="empty">${icon("check")}<div>${L("Geen storingen in de afgelopen 90 dagen", "No outages in the past 90 days")}</div></div>`}
      <p class="help" style="margin:8px 0 0">${L("UniFi zelf toont internetgebeurtenissen maar 24 uur; Sonar bewaart de storingen, handig als je je provider wilt bellen.", "UniFi itself only shows internet events for 24 hours; Sonar keeps the outages, handy if you want to call your provider.")}</p>`;
    hydrateIcons(el);
  }
  // ---- wifi-snelheid meten vanaf dit apparaat (naar Sonar, dus over je eigen netwerk)
  async function loadSelftests(result) {
    let d;
    try { d = await api("/api/selftests"); } catch (e) { return; }
    const el = $("#net-self-body"); if (!el || net.self.busy) return;
    if (result) net.self.last = result;
    const r = net.self.last;
    el.innerHTML = `${r ? `<div class="st-result"><div><div class="k">Download</div><div class="v">${mbTxt(r.down)}<small>Mbit/s</small></div></div>
        <div><div class="k">Upload</div><div class="v">${mbTxt(r.up)}<small>Mbit/s</small></div></div>
        <div><div class="k">Ping</div><div class="v">${r.ping == null ? "–" : nf(r.ping)}<small>ms</small></div></div></div>
        <p class="muted" style="margin:6px 0 0">${esc([r.name, r.ap, r.band ? `${r.band} GHz` : null, r.signal != null ? `${r.signal} dBm` : null].filter(Boolean).join(" · "))}</p>` : ""}
      <div class="self-form"><label class="sr-only" for="self-room">${L("Kamer", "Room")}</label>
        <input class="input" id="self-room" maxlength="40" placeholder="${L("Waar ben je? (bijv. zolder)", "Where are you? (e.g. attic)")}" value="${esc(store.get("self.room", ""))}">
        <button class="btn primary" data-self="start">${icon("gauge")}${L("Meten", "Measure")}</button></div>
      <p class="help">${L("Meet de snelheid tussen dit apparaat en Sonar, dus je wifi (of kabel) zelf, los van internet. Duurt ongeveer 15 seconden.", "Measures the speed between this device and Sonar, so your wifi (or cable) itself, independent of the internet. Takes about 15 seconds.")}</p>
      ${d.rows.length ? `<div class="table-wrap" style="border:0;margin-top:8px"><table><thead><tr><th>${L("Wanneer", "When")}</th><th>${L("Waar", "Where")}</th><th class="r">↓ Mbit/s</th><th class="r">↑ Mbit/s</th></tr></thead><tbody>
        ${d.rows.slice(0, 10).map((x) => `<tr style="cursor:default"><td class="num">${dateTxt(x.ts, true)}</td><td><div>${esc(x.room || x.name || "–")}</div><div class="cell-sub">${esc([x.room ? x.name : null, x.ap, x.band ? `${x.band} GHz` : null, x.signal != null ? `${x.signal} dBm` : null].filter(Boolean).join(" · "))}</div></td>
          <td class="r num">${mbTxt(x.down)}</td><td class="r num">${mbTxt(x.up)}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
    hydrateIcons(el);
  }
  async function runSelftest() {
    const el = $("#net-self-body"); if (!el || net.self.busy) return;
    const room = ($("#self-room")?.value || "").trim(); store.set("self.room", room);
    net.self.busy = true;
    const show = (phase, v) => { el.innerHTML = `<div class="self-run"><span class="live-dot"></span><b>${phase}</b>${v != null ? ` <span class="num">${mbTxt(v)} Mbit/s</span>` : ""}</div>`; };
    try {
      show("Ping");
      const pings = [];
      for (let i = 0; i < 8; i++) { const t = performance.now(); await fetch("/api/selftest/ping", { cache: "no-store" }); pings.push(performance.now() - t); }
      pings.sort((a, b) => a - b);
      const ping = pings[Math.floor(pings.length / 2)];
      // download: groter blok tot het ~4 seconden duurt
      let down = 0, mb = 8;
      for (let round = 0; round < 3; round++) {
        show("Download", down || null);
        const t = performance.now(), r = await fetch(`/api/selftest/down?mb=${mb}`, { cache: "no-store" });
        const reader = r.body.getReader(); let n = 0;
        for (;;) { const { done, value } = await reader.read(); if (done) break; n += value.length; const s = (performance.now() - t) / 1000; if (s > 0.3) show("Download", (n * 8) / s / 1e6); }
        const s = (performance.now() - t) / 1000;
        down = (n * 8) / s / 1e6;
        if (s > 3) break;
        mb = Math.min(400, Math.ceil(mb * Math.max(2, 4 / s)));
      }
      let up = 0, size = 4 << 20;
      for (let round = 0; round < 3; round++) {
        show("Upload", up || null);
        const blob = new Uint8Array(size); crypto.getRandomValues(blob.subarray(0, 65536));
        const t = performance.now();
        await fetch("/api/selftest/up", { method: "POST", body: blob, headers: { "Content-Type": "application/octet-stream" } });
        const s = (performance.now() - t) / 1000;
        up = (size * 8) / s / 1e6;
        if (s > 3) break;
        size = Math.min(300 << 20, Math.ceil(size * Math.max(2, 4 / s)));
      }
      const res = await post("/api/selftest/result", { down, up, ping, room });
      net.self.busy = false;
      loadSelftests(res.result);
    } catch (err) {
      net.self.busy = false;
      el.innerHTML = `<div class="banner err">${icon("octagon")}<span>${esc(err.message)}</span></div>`;
      setTimeout(loadSelftests, 4000);
    }
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
      return `${L("verwacht", "expected")} ~${gb((u.avg_day.rx + u.avg_day.tx) * days)}`;
    })() : "";
    $("#net-usage-kpis").innerHTML = tile(L("Vandaag", "Today"), u.today, L("tot nu", "so far")) + tile(L("Deze maand", "This month"), tm, pace) + tile(L("Vorige maand", "Last month"), lm) +
      tile(L("Gemiddeld per dag", "Average per day"), u.avg_day, L("laatste 30 dagen", "last 30 days"));
    const rows = net.usagePeriod === "month" ? u.months.slice(-24) : u.days.slice(-60);
    const running = rows.length && rows[rows.length - 1].ts === (net.usagePeriod === "month" ? u.month0 : u.day0) ? rows.length - 1 : -1;
    const toGb = (b) => b / 1e9;
    MEcharts.barChart($("#net-usage-chart"), {
      labels: rows.map((r) => r.ts), highlight: running, height: 210,
      series: [{ name: "Download", color: C.cyan, data: rows.map((r) => toGb(r.rx)) }, { name: "Upload", color: C.violet, data: rows.map((r) => toGb(r.tx)) }],
      fmt: (v) => `${nf(v, v < 10 && v > 0 ? 1 : 0)} GB`, label: `${L("Datagebruik", "Data usage")} ${net.usagePeriod === "month" ? L("per maand", "per month") : L("per dag", "per day")}`,
      xfmt: (t) => new Date(t * 1000).toLocaleDateString(LOC, net.usagePeriod === "month" ? { month: "short", year: "2-digit" } : { day: "numeric", month: "short" }),
      tfmt: (t) => new Date(t * 1000).toLocaleDateString(LOC, net.usagePeriod === "month" ? { month: "long", year: "numeric" } : { weekday: "long", day: "numeric", month: "long" }),
    });
    const since = u.since ? new Date(u.since * 1000).toLocaleDateString(LOC, { day: "numeric", month: "long", year: "numeric" }) : "";
    $("#net-usage-note").textContent = u.error ? `${L("Ophalen lukte niet", "Fetching failed")}: ${u.error}`
      : u.since ? L(`Gegevens van je gateway sinds ${since}. Sonar bewaart ze zelf, dus de historie groeit vanaf nu.`, `Data from your gateway since ${since}. Sonar keeps it itself, so the history grows from now on.`) : "";
  }
  const normal = (key) => {   // wat is normaal voor deze verbinding: mediaan van de tests
    const v = (net.data?.speedtests || []).map((r) => r[key]).filter(Boolean).sort((a, b) => a - b);
    return v.length ? v[Math.floor(v.length / 2)] : null;
  };
  function renderNetKpis() {
    const cur = net.last, d = net.data;
    if (!$("#net-kpis") || !d) return;
    const last = d.speedtests[d.speedtests.length - 1];
    const fresh = cur ? Math.max(0, Math.round(cur.now - cur.updated)) : null;
    const kpi = (ic, label, v, unit, ref, sub) => {
      const pct = ref && v != null ? Math.min(100, (100 * v) / ref) : null;
      return `<div class="card compact kpi"><div class="label">${icon(ic)}${label}</div><div class="value">${mbTxt(v)}<small>${unit}</small></div>
        ${pct != null ? `<div class="scorebar" title="${L(`${nf(pct)}% van wat de verbinding haalt`, `${nf(pct)}% of what the connection achieves`)}"><span style="width:${pct}%"></span></div>` : ""}<div class="sub">${sub}</div></div>`;
    };
    const live = cur ? `<span class="live-dot" aria-hidden="true"></span>${fresh < 5 ? L("zojuist", "just now") : L(`${dur(fresh)} geleden`, `${dur(fresh)} ago`)}` : L("laden…", "loading…");
    $("#net-kpis").innerHTML =
      kpi("activity", L("Download nu", "Download now"), mb(cur?.rx_bps), "Mbit/s", normal("down"), live) +
      kpi("activity", L("Upload nu", "Upload now"), mb(cur?.tx_bps), "Mbit/s", normal("up"), normal("up") ? `${L("van", "of")} ~${mbTxt(normal("up"))} Mbit/s` : "") +
      `<div class="card compact kpi"><div class="label">${icon("clock")}Latency</div><div class="value">${cur?.latency_ms == null ? "–" : nf(cur.latency_ms)}<small>ms</small></div><div class="sub">${L("naar internet", "to the internet")}</div></div>` +
      `<div class="card compact kpi"><div class="label">${icon("gauge")}${L("Laatste speedtest", "Last speed test")}</div><div class="value">${last ? mbTxt(last.down) : "–"}<small>/ ${last ? mbTxt(last.up) : "–"} Mbit/s</small></div>
        <div class="sub">${last ? `${dateTxt(last.ts, true)} · ping ${nf(last.latency)} ms` : L("nog niet gemeten", "not measured yet")}</div></div>`;
  }
  const PHASES = [["ping", "Ping"], ["download", "Download"], ["upload", "Upload"]];
  function bloatHTML(b) {
    if (!b) return "";
    const lv = { "A+": "ok", A: "ok", B: "info", C: "warning", D: "critical", F: "critical" }[b.grade];
    const text = { ok: L("Je verbinding blijft ook onder volle belasting snel reageren.", "Your connection keeps responding quickly even under full load."),
      info: L("Prima: als de lijn vol zit merk je er weinig van.", "Fine: you will barely notice when the line is full."),
      warning: L("Als de lijn vol zit, merk je dat bij videobellen en games.", "When the line is full, you will notice it in video calls and games."),
      critical: L("Als de lijn vol zit, wordt alles traag. Smart Queues in UniFi kunnen helpen.", "When the line is full, everything gets slow. Smart Queues in UniFi can help.") }[lv];
    const part = (l, v) => (v == null ? "" : ` · ${l} +${nf(v)} ms`);
    return `<div class="bloat"><span class="bloat-g ${lv}" title="${L("Cijfer", "Grade")} ${esc(b.grade)}">${esc(b.grade)}</span><div><div class="bloat-t">${L("Vertraging onder belasting", "Delay under load")}</div>
      <div class="num muted">${L("rustig", "idle")} ${nf(b.idle)} ms${part("download", b.added_down)}${part("upload", b.added_up)}</div><div class="help" style="margin-top:4px">${text}</div></div></div>`;
  }
  function renderTest() {
    const root = $("#net-test");
    if (!root || !net.data) return;
    const t = net.last?.test || net.data.speedtest || {};
    const g = net.last?.speedtest || {};
    const last = net.data.speedtests[net.data.speedtests.length - 1];
    const nd = normal("down");
    if (t.running) {
      const at = PHASES.findIndex(([k]) => k === g.phase);
      root.innerHTML = `<div class="card-head"><h2 style="margin:0">${L("Speedtest", "Speed test")}</h2><span class="badge info"><span class="live-dot"></span>${L("bezig", "running")}</span></div>
        <ol class="st-steps">${PHASES.map(([k, l], i) => {
          const val = i < at ? (k === "ping" ? (g.latency != null ? `${nf(g.latency)} ms` : "") : g[k === "download" ? "down" : "up"] != null ? `${mbTxt(g[k === "download" ? "down" : "up"])} Mbit/s` : "") : "";
          return `<li class="${at < 0 ? (i === 0 ? "active" : "") : i < at ? "done" : i === at ? "active" : ""}">${i < at ? icon("check") : `<span>${i + 1}</span>`}${l}${val ? `<b class="num st-val">${val}</b>` : ""}</li>`;
        }).join("")}</ol>
        <p class="muted">${L("Je gateway meet nu de snelheid van je internetverbinding. Dit duurt 15 tot 30 seconden.", "Your gateway is now measuring the speed of your internet connection. This takes 15 to 30 seconds.")}</p>`;
      return;
    }
    const res = last ? `<div class="st-result"><div><div class="k">Download</div><div class="v">${mbTxt(last.down)}<small>Mbit/s</small></div></div>
        <div><div class="k">Upload</div><div class="v">${mbTxt(last.up)}<small>Mbit/s</small></div></div>
        <div><div class="k">Ping</div><div class="v">${last.latency == null ? "–" : nf(last.latency)}<small>ms</small></div></div></div>
        <p class="muted" style="margin:6px 0 0">${dateTxt(last.ts, true)}${nd && last.down < 0.8 * nd ? ` · <span class="t-warning">${L("lager dan normaal", "lower than normal")} (~${mbTxt(nd)} Mbit/s)</span>` : nd ? ` · ${L("normaal", "normal")} ~${mbTxt(nd)} Mbit/s` : ""}</p>` : "";
    root.innerHTML = `<div class="card-head"><h2 style="margin:0">${L("Speedtest", "Speed test")}</h2></div>${res}${bloatHTML(net.data.bufferbloat)}
      ${t.error ? `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(t.error)}</span></div>` : ""}
      <div class="wiz-actions" style="margin-top:16px"><button class="btn primary" data-st="start" ${net.data.available ? "" : "disabled"}>${icon("gauge")}${L("Start speedtest", "Start speed test")}</button></div>
      <p class="help">${L("De test draait op je gateway zelf en meet dus je echte internetverbinding, los van wifi of dit apparaat. Duurt 15 tot 30 seconden en gebruikt even je volledige bandbreedte.", "The test runs on your gateway itself, so it measures your real internet connection, independent of wifi or this device. Takes 15 to 30 seconds and briefly uses your full bandwidth.")}</p>`;
  }
  async function startSpeedtest() {
    const b = $("[data-st=start]");
    if (b) { b.disabled = true; b.textContent = L("Starten…", "Starting…"); }
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
      unit: " Mbit/s", yMin: 0, bucket: 60, label: L("Live internetverkeer in Mbit/s", "Live internet traffic in Mbit/s"), tfmt: (t) => new Date(t * 1000).toLocaleTimeString(LOC) });
    $("#net-live-sub").textContent = L("laatste 15 minuten", "last 15 minutes");
  }
  async function liveLoop() {
    clearTimeout(net.timer);
    if (current !== "internet") return;
    try {
      const live = await api("/api/live/wan");
      const prev = net.last;
      net.last = live;
      if (!prev || prev.updated !== live.updated) { net.live.push({ t: live.updated, rx: mb(live.rx_bps), tx: mb(live.tx_bps) }); drawLive(); }
      renderNetKpis();
      if (net.wasRunning && !live.test.running) { net.wasRunning = false; loadInternet(); }
      else if (live.test.running) { net.wasRunning = true; renderTest(); }
    } catch (e) {
      $("#net-live-sub").textContent = e.message;
    }
    net.timer = setTimeout(liveLoop, net.last?.test?.running ? 1500 : 3000);
  }

  // ------------------------------------------------------------------ muurscherm
  const kio = { mode: "", clock: null, globe: null, worldAt: 0 };
  function stopKiosk() {
    clearInterval(kio.clock); kio.clock = null;
    kio.globe?.destroy(); kio.globe = null; kio.worldAt = 0;
  }
  function kioskClock() {
    const now = new Date();
    const t = $("#k-time"), d = $("#k-date");
    if (!t) return;
    t.textContent = now.toLocaleTimeString(LOC, { hour: "2-digit", minute: "2-digit" });
    d.textContent = now.toLocaleDateString(LOC, { weekday: "long", day: "numeric", month: "long" });
  }
  function mountKiosk() {
    stopKiosk();
    mount("kiosk", `<div class="ks ${kio.mode === "globe" ? "with-globe" : ""}">
      <header class="ks-head"><div class="brand"><span class="logo">${icon("radar")}</span>UniFi Sonar</div><div class="ks-clock"><time id="k-time"></time><span id="k-date"></span></div></header>
      <div class="ks-main">
        <div class="ks-col"><section class="card ks-score" id="k-score"></section><section class="ks-tiles" id="k-tiles"></section></div>
        <section class="card ks-issues"><h2>${L("Wat vraagt aandacht", "Needs attention")}</h2><div id="k-issues"></div></section>
        ${kio.mode === "globe" ? `<section class="card ks-globe"><div id="k-globe"></div></section>` : ""}
      </div>
      <footer class="ks-foot"><span id="k-status"></span><span class="ks-acts"><button class="linkbtn" id="k-full">${L("Volledig scherm", "Full screen")}</button><a class="linkbtn" href="#/overzicht">${L("Sluiten", "Close")}</a></span></footer>
    </div>`);
    kioskClock();
    kio.clock = setInterval(kioskClock, 15000);
    $("#k-full").onclick = () => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.());
    if (kio.mode === "globe") startKioskGlobe();
  }
  UPDATERS.kiosk = () => {
    const s = state.snap, st = state.status;
    if (!s || !$("#k-score")) return;
    const h = s.health || {}, score = h.score ?? 0, [label, lv] = scoreLabel(score);
    $("#k-score").innerHTML = `<div class="label">${L("Netwerkscore", "Network score")}</div><div class="ks-num">${nf(score)}<small>/100</small></div>${badge(lv, label)}<div class="scorebar"><span style="width:${score}%;background:var(--me-${lv === "ok" ? "success" : lv === "warning" ? "warning" : "danger"})"></span></div>`;
    const online = s.devices.filter((d) => d.state === "online").length;
    const clients = s.clients.filter((c) => c.connected !== false).length;
    const tile = (ic, l, v, sub) => `<div class="card ks-tile"><div class="label">${icon(ic)}${l}</div><div class="ks-val">${v}</div><div class="sub">${sub}</div></div>`;
    $("#k-tiles").innerHTML =
      tile("globe", "Internet", s.wan.up === false ? L("Offline", "Offline") : `${s.wan.latency_ms == null ? "–" : nf(s.wan.latency_ms)}<small>ms</small>`, s.wan.up === false ? L("geen verbinding", "no connection") : L("online", "online")) +
      tile("activity", L("Verkeer nu", "Traffic now"), `${mbTxt(mb(s.wan.rx_bps))}<small>Mbit/s</small>`, `${L("omhoog", "up")} ${mbTxt(mb(s.wan.tx_bps))} Mbit/s`) +
      tile("laptop", "Clients", nf(clients), `${nf(s.clients.filter((c) => c.connected !== false && !c.wired).length)} wifi`) +
      tile("router", L("Apparaten", "Devices"), `${nf(online)}<small>/ ${nf(s.devices.length)}</small>`, L("online", "online"));
    const top = state.issues.filter((i) => !i.group && !i.resolved_at && !i.muted), shown = kio.mode === "globe" ? 4 : 7;
    $("#k-issues").innerHTML = top.length ? top.slice(0, shown).map((i) => `<div class="ks-issue">${sevBadge(i.severity)}<span>${esc(i.title)}</span></div>`).join("") + (top.length > shown ? `<p class="muted">${L(`en nog ${top.length - shown}`, `and ${top.length - shown} more`)}</p>` : "")
      : `<div class="ks-ok">${icon("check")}<span>${L("Alles in orde", "All good")}</span></div>`;
    const stale = st.last_ok && Date.now() / 1000 - st.last_ok > st.poll_seconds * 3;
    $("#k-status").innerHTML = `<span class="dot ${st.last_error || stale ? "err" : ""}"></span>${L(`Bijgewerkt ${ago(st.last_ok)} geleden`, `Updated ${ago(st.last_ok)} ago`)}`;
    if (kio.globe) loadKioskWorld();
  };
  async function startKioskGlobe() {
    try { await ensureGlobe(); } catch (e) { return; }
    const host = $("#k-globe");
    if (!host || kio.globe || kio.mode !== "globe") return;
    kio.globe = window.SonarGlobe.mount(host, { onHover() {}, onLeave() {}, onClick() {}, onZoom() {} });
    loadKioskWorld();
  }
  async function loadKioskWorld() {
    if (Date.now() - kio.worldAt < 55000) return;
    kio.worldAt = Date.now();
    const d = await api("/api/world?hours=6").catch(() => null);
    if (!d || !kio.globe) return;
    const byCc = Object.fromEntries(d.countries.map((c) => [c.cc, c]));
    const max = Math.max(1, ...d.countries.map((c) => c.bytes));
    const lvl = (b) => (b > 0 ? Math.log10(1 + b) / Math.log10(1 + max) : 0);
    const maxN = Math.max(1, ...d.countries.map((c) => Math.max(c.out_n, c.in_n, c.blocked_n || 0)));
    const arcs = [];
    for (const c of d.countries) {
      if (c.cc === d.home) continue;
      for (const k of ["out", "in", "blocked"]) {
        const n = c[`${k}_n`] || 0;
        if (n) arcs.push({ cc: c.cc, kind: k, w: 0.8 + 2.6 * (k === "out" ? lvl(c.bytes) : Math.log10(1 + n) / Math.log10(1 + maxN)) });
      }
    }
    const G = window.WORLD_GEO, has = new Set(G.features.map((f) => f.id));
    kio.globe.setData({ home: d.home, byCc, show: { out: true, in: true, blocked: true }, lvl, name: ccName, arcs,
      dots: d.countries.filter((c) => c.cc !== d.home && G.labels[c.cc] && !has.has(c.cc)).map((c) => c.cc) });
  }

  // ------------------------------------------------------------------ beveiliging
  const secState = { hours: store.get("sec.hours", 24), scope: "all", ignored: false };
  const ignMenu = (opts) => `<details class="mute ign"><summary class="mutebtn">${L("Negeren", "Ignore")}</summary><div class="mute-menu" role="group" aria-label="${L("Negeren", "Ignore")}">${opts.map(([l, o]) => `<button data-ign="${esc(JSON.stringify(o))}">${l}</button>`).join("")}</div></details>`;
  const catLabel = (c) => (c || "").replace(/^emerging-/, "").replace(/-/g, " ");
  function mountSecurity() {
    mount("beveiliging", `
      <div class="page-head"><div><h1>${L("Beveiliging", "Security")}</h1><p class="subtitle">${L("Wat de IPS op je gateway tegenhield, wat er openstaat naar internet en hoe je netwerken van elkaar gescheiden zijn. Aanvallen van buiten zijn normaal; blokkades van <b>eigen apparaten</b> verdienen aandacht.", "What the IPS on your gateway stopped, what is open to the internet and how your networks are separated. Attacks from outside are normal; blocks of <b>your own devices</b> deserve attention.")}</p></div>
        <div class="seg" role="group" aria-label="${L("Periode", "Period")}" id="sec-range">${[[24, L("24 u", "24 h")], [168, "7 d"], [336, "14 d"]].map(([h, l]) => `<button data-h="${h}" aria-pressed="${secState.hours === h}">${l}</button>`).join("")}</div></div>
      ${jumpBar("beveiliging", [["#sec-kpis", L("Blokkades", "Blocks"), 1], ["#sec-seg-card", L("Netwerkscheiding", "Segmentation")], ["#sec-checks", L("Bevindingen", "Findings")],
        ["#h-dns", "DNS"], ["#h-vuln", L("Kwetsbaarheden", "Vulnerabilities")], ["#sec-adv", L("Adviezen", "Advisories")], ["#sec-expo", L("Open poorten", "Open ports")], ["#sec-table", L("Alle blokkades", "All blocks")]])}
      <div id="sec-banner"></div>
      <section class="grid kpis" id="sec-kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))"></section>
      <section class="grid cols-2" style="margin-bottom:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">${L("Meest geraakte regels", "Most hit rules")}</h2></div><div class="rank" id="sec-sigs"></div></div>
        <div class="card"><div class="card-head"><h2 style="margin:0">${L("Bronnen", "Sources")}</h2></div><div class="rank" id="sec-srcs"></div></div>
      </section>
      <section class="card" style="margin-bottom:16px" id="sec-seg-card"><div class="card-head"><h2 style="margin:0">${L("Netwerkscheiding", "Network segmentation")}</h2><span class="muted" id="sec-seg-sub"></span></div>
        <div class="seg-nets" id="sec-seg-nets"></div><div id="sec-seg-matrix"></div><div id="sec-seg-issues"></div></section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h2 style="margin:0">${L("Firewall, DNS en adviezen", "Firewall, DNS and advisories")}</h2><span class="muted" id="sec-checks-sub"></span></div><div class="issue-list" id="sec-checks"></div></section>
      <section class="card" style="margin-bottom:16px" id="h-dns"><div class="card-head"><h2 style="margin:0">${L("DNS via AdGuard", "DNS via AdGuard")}</h2><span class="muted" id="sec-dns-sub"></span></div><div id="sec-dns"></div></section>
      <section class="card" style="margin-bottom:16px" id="h-vuln"><div class="card-head"><h2 style="margin:0">${L("Kwetsbaarheden", "Vulnerabilities")}</h2><span class="muted" id="sec-vuln-sub"></span></div><div id="sec-vuln"></div></section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h2 style="margin:0">${L("Beveiligingsadviezen van Ubiquiti", "Ubiquiti security advisories")}</h2><span class="muted" id="sec-adv-sub"></span></div><div id="sec-adv"></div></section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h2 style="margin:0">${L("Open naar internet", "Open to the internet")}</h2><span class="muted" id="sec-expo-sub"></span></div><div id="sec-expo"></div></section>
      <section class="card" style="margin-bottom:16px"><div class="card-head"><h3>${L("Blokkades in de tijd", "Blocks over time")}</h3><span class="muted" id="sec-bucket"></span></div><div id="sec-chart"></div></section>
      <div class="toolbar"><div class="chips" role="group" aria-label="${L("Bron", "Source")}" id="sec-scope">${[["all", L("Alles", "All")], ["internal", L("Eigen apparaten", "Own devices")], ["external", L("Van buiten", "From outside")]].map(([v, l]) => `<button class="chip" data-s="${v}" aria-pressed="${secState.scope === v}">${l}</button>`).join("")}</div>
        <button class="chip" id="sec-ignored" aria-pressed="${secState.ignored}">${L("Genegeerde tonen", "Show ignored")} <span class="num" id="sec-ignored-n"></span></button></div>
      <div class="table-wrap" id="sec-table"></div>
      <section class="card" style="margin-top:16px" id="sec-ign-card" hidden><div class="card-head"><h3>${L("Negeerregels", "Ignore rules")}</h3><span class="muted">${L("tellen niet mee in de cijfers en geven geen meldingen", "not counted in the figures and raise no issues")}</span></div><div id="sec-ign"></div></section>`);
    $("#sec-kpis").addEventListener("click", (e) => {
      if (!e.target.closest("#sec-review")) return;
      $('#sec-scope .chip[data-s="internal"]').click();
      $("#sec-scope").scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });
    });
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
    bindIssueActions($("#sec-checks"), renderSecChecks);
    $("#sec-dns").addEventListener("click", (e) => { const o = e.target.closest("[data-open]"); if (o && cliByMac()[o.dataset.id]) openDrawer("client", o.dataset.id, o); });
    $("#sec-adv").addEventListener("change", async (e) => {
      if (e.target.id !== "adv-on") return;
      try { await post("/api/advisories/settings", { enabled: e.target.checked }); } catch (err) { alert(err.message); }
      loadAdvisories(); refresh();
    });
    bindFlow($("#sec-seg-matrix"));
  }
  // ---- firewall-audit, DNS om je DNS-server heen en beveiligingsadviezen
  const CHECK_KEYS = ["fw_", "dns_", "adguard:", "advisory:", "vuln:", "quarantine:"];
  function renderSecChecks() {
    const el = $("#sec-checks"); if (!el) return;
    const list = (state.issues || []).filter((i) => !i.resolved_at && CHECK_KEYS.some((k) => i.key.startsWith(k)))
      .sort((a, b) => (a.muted - b.muted) || ({ critical: 0, warning: 1, info: 2 }[a.severity] - { critical: 0, warning: 1, info: 2 }[b.severity]));
    const open = list.filter((i) => !i.muted);
    $("#sec-checks-sub").textContent = list.length ? L(`${open.length} bevinding${open.length === 1 ? "" : "en"}${list.length > open.length ? `, ${list.length - open.length} genegeerd` : ""}`,
      `${open.length} finding${open.length === 1 ? "" : "s"}${list.length > open.length ? `, ${list.length - open.length} ignored` : ""}`) : "";
    el.innerHTML = open.length ? open.map((i) => issueHTML(i, state.issues, false)).join("")
      : `<div class="empty">${icon("check")}<div>${L("Geen regels die niets doen of je netwerk openzetten, en geen apparaten die om je DNS-server heen gaan.", "No rules that do nothing or open your network, and no devices bypassing your DNS server.")}</div></div>`;
  }
  async function loadAdvisories() {
    let d;
    try { d = await api("/api/advisories"); } catch (e) { return; }
    const el = $("#sec-adv"); if (!el || current !== "beveiliging") return;
    const hits = d.items.filter((x) => x.affects).length;
    $("#sec-adv-sub").textContent = d.enabled && d.fetched ? L(`bijgewerkt ${stamp(d.fetched)}`, `updated ${stamp(d.fetched)}`) : "";
    el.innerHTML = `${d.enabled ? (d.items.length ? `<div class="adv-list">${d.items.map((x) => `<div class="adv-row ${x.affects ? "hit" : ""}">
        <div style="min-width:0"><a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" class="rank-name">${esc(x.title)}</a>
          <div class="cell-sub">${new Date(x.ts * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short", year: "numeric" })} · ${esc(x.products.slice(0, 3).join(", "))}${x.products.length > 3 ? "…" : ""}</div></div>
        <div class="adv-badges">${x.score != null ? `<span class="num muted">${nf(x.score, 1)}</span>` : ""}${x.exploited ? badge("warning", L("Wordt misbruikt", "Exploited"), "alert") : ""}${x.affects ? badge("critical", L("Geldt voor jou", "Affects you"), "alert") : badge("ok", L("Niet voor jou", "Not for you"), "check")}</div></div>`).join("")}</div>`
        : `<p class="muted">${d.error ? `${L("Ophalen lukte niet", "Fetching failed")}: ${esc(d.error)}` : L("Nog niet opgehaald.", "Not fetched yet.")}</p>`) : ""}
      <p class="help" style="margin:10px 0 0">${hits ? "" : d.enabled && d.items.length ? `${L("Geen van de recente adviezen geldt voor jouw firmware.", "None of the recent advisories apply to your firmware.")} ` : ""}${L("Sonar haalt elke 6 uur de openbare lijst van Ubiquiti op en vergelijkt die met de firmware van je apparaten. Er gaat niets van jouw netwerk mee.", "Every 6 hours Sonar fetches Ubiquiti's public list and compares it with your devices' firmware. Nothing from your network is sent.")}</p>
      <label class="check" style="margin-top:8px"><input type="checkbox" id="adv-on" ${d.enabled ? "checked" : ""}> ${L("Beveiligingsadviezen ophalen", "Fetch security advisories")}</label>`;
    hydrateIcons(el);
  }

  // ------------------------------------------------------------------ kwetsbaarheden
  let vulnTimer = null;
  const COVER = { ok: ["ok", L("Bekeken", "Checked"), "check"], partial: ["warning", L("Deels", "Partly"), "info"], manual: ["warning", L("Zelf controleren", "Check yourself"), "alert"],
    none: ["info", L("Niet beoordeeld", "Not assessed"), "info"], off: ["info", L("Niet gedaan", "Not done"), "info"] };
  function vulnPort(h, o) {
    const used = o.used_by.length ? ` ${L("Via de gateway gebruikt door", "Used through the gateway by")} ${esc(o.used_by.join(", "))}.` : "";
    return `<div class="vuln-port${o.accepted ? "" : " finding"}"><div style="min-width:0"><span class="num">${o.port}</span> ${esc(o.name)}${o.why || used ? `<div class="cell-sub">${esc(o.why)}${used}</div>` : ""}</div>
      <div class="adv-badges">${o.accepted ? `<span class="muted">${L("Hoort zo", "Expected")}</span>` : badge("warning", L("Nakijken", "Review"), "alert")}
      <button class="btn ghost" data-acc="${esc(h.mac)}" data-port="${o.port}" data-on="${o.accepted ? 0 : 1}">${o.accepted ? L("Terugzetten", "Undo") : L("Hoort zo", "Expected")}</button></div></div>`;
  }
  const OUT_STATE = { expected: ["ok", L("Hoort bij je instellingen", "Matches your settings"), "check"], stale: ["info", L("Waarschijnlijk oud", "Probably outdated"), "info"],
    lingering: ["warning", L("Nakijken", "Review"), "alert"], unexplained: ["warning", L("Nakijken", "Review"), "alert"], unknown: ["info", L("Niet te verklaren", "Can't explain"), "info"] };
  function outsideWhy(r, days) {
    const via = (v) => v.kind === "vpn" ? L(`VPN-server '${v.name}'`, `VPN server '${v.name}'`)
      : `${v.kind === "upnp" ? L("UPnP-koppeling", "UPnP mapping") : "Port forward"} '${v.name}'${v.to ? ` → ${v.to}` : ""}`;
    const names = r.via.map(via).join(", ");
    const since = new Date(r.since * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short" });
    if (r.state === "expected") {
      const also = r.via.flatMap((v) => v.also);
      return L(`Hoort bij ${names}.`, `Belongs to ${names}.`) + (also.length ? ` ${L("Dat apparaat heeft binnen je netwerk ook open", "Inside your network that device also has open")}: ${also.map((o) => `${o.port} ${o.name}`).join(", ")}.` : "");
    }
    if (r.state === "stale") return L(`Hoort bij ${names}, maar dat staat uit. Waarschijnlijk zijn de gegevens van Shodan ouder. Staat de poort er na ${days} dagen nog, dan wordt het een bevinding. In de lijst sinds ${since}.`,
      `Belongs to ${names}, but that is switched off. Shodan's data is probably older. If the port is still listed after ${days} days, it becomes a finding. Listed since ${since}.`);
    if (r.state === "lingering") return L(`Staat sinds ${since} bij Shodan, terwijl ${names} uitstaat. Ga na of de poort echt dicht is, bijvoorbeeld vanaf je telefoon via mobiel internet.`,
      `Listed by Shodan since ${since}, while ${names} is switched off. Check that the port is really closed, for example from your phone on mobile data.`);
    if (r.state === "unknown") return L("Sonar kan je port forwards niet lezen (dat kan alleen via de uitgebreide API), dus ook niet zeggen waar deze poort bij hoort.",
      "Sonar can't read your port forwards (that needs the extended API), so it can't tell what this port belongs to.");
    return L(`Je controller weet hier niets van: geen port forward, UPnP-koppeling of VPN-server op deze poort. Het kan een dienst op de gateway zelf zijn, of gegevens van Shodan die niet meer kloppen. In de lijst sinds ${since}.`,
      `Your controller knows nothing about this: no port forward, UPnP mapping or VPN server on this port. It may be a service on the gateway itself, or Shodan data that is no longer correct. Listed since ${since}.`);
  }
  function outsidePort(r, days) {
    const act = r.state !== "expected" && r.state !== "unknown";
    const cls = r.accepted ? "" : r.state === "stale" ? " stale" : r.state === "unexplained" || r.state === "lingering" ? " finding" : "";
    return `<div class="vuln-port${cls}"><div style="min-width:0"><span class="num">${r.port}</span>${r.name ? ` ${esc(r.name)}` : ""}<div class="cell-sub">${esc(outsideWhy(r, days))}</div></div>
      <div class="adv-badges">${r.accepted ? `<span class="muted">${L("Hoort zo", "Expected")}</span>` : badge(...OUT_STATE[r.state])}
      ${act ? `<button class="btn ghost" data-acc="wan" data-port="${r.port}" data-on="${r.accepted ? 0 : 1}">${r.accepted ? L("Terugzetten", "Undo") : L("Hoort zo", "Expected")}</button>` : ""}</div></div>`;
  }
  function vulnHost(h) {
    const risky = h.open.filter((o) => o.cls === "plain"), rest = h.open.filter((o) => o.cls !== "plain");
    return `<div class="vuln-host"><div class="rank-name">${esc(h.name)} <span class="muted num">${esc(h.ip)} · ${esc(h.network)}</span></div>
      ${risky.map((o) => vulnPort(h, o)).join("")}
      ${rest.length ? `<div class="cell-sub">${L("Beheer of delen", "Admin or sharing")}: ${rest.map((o) => `${o.port} ${esc(o.name)}`).join(", ")}</div>` : ""}</div>`;
  }
  async function loadVuln() {
    let d;
    try { d = await api("/api/vulnscan"); } catch (e) { return; }
    const el = $("#sec-vuln"); if (!el || current !== "beveiliging") return;
    clearTimeout(vulnTimer);
    if (d.running) vulnTimer = setTimeout(loadVuln, 3000);
    $("#sec-vuln-sub").textContent = d.kev.fetched ? L(`lijst van ${nf(d.kev.count)} misbruikte lekken bijgewerkt ${stamp(d.kev.fetched)}`, `list of ${nf(d.kev.count)} exploited flaws updated ${stamp(d.kev.fetched)}`) : "";
    const s = d.summary, sk = d.plan.skipped, out = d.outside, p = d.ports;
    const notSeen = sk.iot + sk.guest + sk.unknown + sk.limit;
    el.innerHTML = `
      ${d.kev.error ? `<div class="banner err">${L("De KEV-lijst ophalen lukte niet", "Fetching the KEV list failed")}: ${esc(d.kev.error)}</div>` : ""}
      <div class="kv" style="margin-bottom:12px">
        <div><div class="k">${L("Echt misbruikt en bij jou", "Exploited and present here")}</div><div class="v">${nf(s.exploited)}</div></div>
        <div><div class="k">${L("Bevindingen", "Findings")}</div><div class="v">${nf(s.findings)}</div></div>
        <div><div class="k">${L("Bekeken", "Looked at")}</div><div class="v">${L(`${nf(s.checked)} van ${nf(s.total)} apparaten`, `${nf(s.checked)} of ${nf(s.total)} devices`)}</div></div>
      </div>
      ${d.exploited.length ? `<h3>${L("Bij jou en echt misbruikt", "Present here and exploited")}</h3><div class="adv-list">${d.exploited.map((x) => `<div class="adv-row hit"><div style="min-width:0"><a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" class="rank-name">${esc(x.title)}</a>
        <div class="cell-sub">${esc(x.devices.map((v) => `${v.name} (${v.version})`).join(", "))}${x.fixed ? ` · ${L("opgelost in", "fixed in")} ${esc(x.fixed)}` : ""} · ${esc(x.cves.join(", "))}</div></div>
        <div class="adv-badges">${x.ransomware ? badge("critical", "Ransomware", "alert") : ""}${badge("critical", L("Bijwerken", "Update"), "alert")}</div></div>`).join("")}</div>` : ""}
      <h3>${L("Wat er bekeken is", "What was looked at")}</h3>
      <div class="adv-list">${d.coverage.map((c) => `<div class="adv-row"><div style="min-width:0"><div class="rank-name">${esc(c.title)}</div><div class="cell-sub">${esc(c.text)}${c.url ? ` <a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">${L("Advies", "Advisory")}</a>` : ""}</div></div>
        <div class="adv-badges">${badge(...COVER[c.state])}</div></div>`).join("")}</div>
      ${out && out.state === "ok" ? `<h3>${L("Zo zie je er van buiten uit", "How you look from outside")}</h3>
        <p class="help" style="margin:0">${esc(out.ip)} · ${L("bijgewerkt", "updated")} ${stamp(out.fetched)} · ${out.ports.length ? L("Shodan geeft geen protocol en geen datum. 'Sinds' is wanneer Sonar de poort voor het eerst in de lijst zag.", "Shodan gives no protocol and no date. 'Since' is when Sonar first saw the port listed.") : L("Shodan ziet geen open poorten.", "Shodan sees no open ports.")}</p>
        ${out.explained.length ? `<div>${out.explained.map((r) => outsidePort(r, out.stale_days)).join("")}</div>` : ""}
        ${out.vulns.length ? `<div class="adv-list">${out.vulns.slice(0, 30).map((v) => `<div class="adv-row"><div style="min-width:0"><div class="rank-name num">${esc(v.id)}</div>${v.name ? `<div class="cell-sub">${esc(v.name)}</div>` : ""}</div><div class="adv-badges">${v.exploited ? badge("critical", L("Wordt misbruikt", "Exploited"), "alert") : badge("info", L("Mogelijk", "Possible"), "info")}</div></div>`).join("")}</div>` : ""}` : ""}
      ${d.hosts.length ? `<h3>${L("Open diensten", "Open services")}</h3><div>${d.hosts.map(vulnHost).join("")}</div>
        <p class="help" style="margin:8px 0 0">${L("Open betekent dat de poort antwoord geeft. Of er een wachtwoord op zit, controleert Sonar bewust niet.", "Open means the port answers. Sonar deliberately does not check whether it has a password.")}</p>` : ""}
      ${p.error && !d.running ? `<div class="banner err" style="margin-top:12px">${L("De poortcheck ging mis", "The port check failed")}: ${esc(p.error)}</div>` : ""}
      <h3>${L("Poortcheck", "Port check")}</h3>
      ${d.running ? `<p class="help" style="margin:0" role="status">${L("Bezig", "Running")}${d.running.total ? `: ${nf(d.running.done)} / ${nf(d.running.total)}` : "…"}</p>`
        : `<p class="help" style="margin:0">${L(`Controleert ${d.plan.targets} apparaten op ${d.plan.ports} beheerpoorten, in ongeveer ${d.plan.minutes} min. Sonar maakt alleen verbinding en sluit meteen weer: geen wachtwoorden en geen exploits.${notSeen ? ` ${notSeen} apparaten slaan we over: ${sk.iot} slimme apparaten, ${sk.guest} gasten en ${sk.unknown + sk.limit} overig.` : ""} De controle komt vanaf het netwerk van Sonar, dus ze zegt niets over wat je slimme apparaten kunnen bereiken.`,
            `Checks ${d.plan.targets} devices on ${d.plan.ports} admin ports, in about ${d.plan.minutes} min. Sonar only connects and closes right away: no passwords and no exploits.${notSeen ? ` ${notSeen} devices are skipped: ${sk.iot} smart devices, ${sk.guest} guests and ${sk.unknown + sk.limit} other.` : ""} The check runs from Sonar's network, so it says nothing about what your smart devices can reach.`)}${p.ran ? ` ${L("Laatst", "Last run")}: ${stamp(p.ran)}.` : ""}</p>
           <div class="wiz-actions"><button type="button" class="btn" id="vuln-run" ${d.plan.targets ? "" : "disabled"}>${p.ran ? L("Opnieuw controleren", "Check again") : L("Poorten controleren", "Check ports")}</button></div>`}
      <label class="check"><input type="checkbox" id="vuln-nightly" ${d.options.nightly ? "checked" : ""}> ${L("Elke nacht tussen 3 en 5 uur herhalen", "Repeat every night between 3 and 5 am")}</label>
      <label class="check" style="margin-top:8px"><input type="checkbox" id="vuln-outside" ${d.options.outside ? "checked" : ""}> ${L("Mijn publieke adres dagelijks opzoeken bij Shodan InternetDB (je adres gaat dan naar Shodan)", "Look up my public address daily at Shodan InternetDB (your address is then sent to Shodan)")}</label>`;
    hydrateIcons(el);
  }
  function bindVuln() {
    const el = $("#sec-vuln");
    el.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-acc]");
      try {
        if (b) { b.disabled = true; await post("/api/vulnscan/accept", { mac: b.dataset.acc, port: +b.dataset.port, accepted: b.dataset.on === "1" }); }
        else if (e.target.closest("#vuln-run")) { e.target.closest("#vuln-run").disabled = true; await post("/api/vulnscan/run", {}); }
        else return;
      } catch (err) { alert(err.message); }
      loadVuln();
    });
    el.addEventListener("change", async (e) => {
      const key = { "vuln-nightly": "nightly", "vuln-outside": "outside" }[e.target.id]; if (!key) return;
      try { await post("/api/vulnscan/settings", { [key]: e.target.checked }); } catch (err) { alert(err.message); }
      loadVuln();
    });
  }

  // ------------------------------------------------------------------ DNS via AdGuard
  const agHost = (url) => { try { return new URL(url).hostname; } catch (e) { return url; } };
  const openCli = (mac, label) => mac ? `<button class="linkbtn plain rank-name" data-open="client" data-id="${esc(mac)}">${esc(label)}</button>` : `<span class="rank-name">${esc(label)}</span>`;
  async function loadAdGuard() {
    let d;
    try { d = await api("/api/adguard"); } catch (e) { return; }
    const el = $("#sec-dns"); if (!el || current !== "beveiliging") return;
    if (!d.active) {
      $("#sec-dns-sub").textContent = "";
      el.innerHTML = `<p class="help" style="margin:0">${L("Koppel AdGuard Home en Sonar laat zien welke namen achter je verbindingen zitten, wat je slimme apparaten opzoeken, of je DNS-servers het doen, wat AdGuard aan malware tegenhield en welke apparaten AdGuard overslaan.",
        "Connect AdGuard Home and Sonar shows the names behind your connections, what your smart devices look up, whether your DNS servers work, what malware AdGuard blocked and which devices skip AdGuard.")}</p>
        <div class="wiz-actions"><a class="btn" href="#/instellingen">${L("AdGuard koppelen", "Connect AdGuard")}</a></div>`;
      return;
    }
    const t = d.totals, pct = t.queries ? Math.round(100 * t.blocked / t.queries) : 0;
    $("#sec-dns-sub").textContent = d.since ? L(`gevolgd sinds ${new Date(d.since * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short" })}`, `followed since ${new Date(d.since * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short" })}`) : "";
    const probes = new Map(d.servers.map((s) => [s.host, s]));
    const rows = d.instances.map((i) => ({ i, p: probes.get(agHost(i.url)) }));
    d.servers.filter((s) => !rows.some((r) => r.p === s)).forEach((p) => rows.push({ i: null, p }));
    const srvRow = ({ i, p }) => {
      const b = [];
      if (p) b.push(p.down ? badge("critical", L("Antwoordt niet", "Not answering"), "octagon") : p.ok ? badge(p.median_ms > 150 ? "warning" : "ok", `${nf(p.median_ms ?? p.ms)} ms`, p.median_ms > 150 ? "alert" : "check") : badge("warning", L("Gemist", "Missed"), "alert"));
      if (i && i.ok === false) b.push(badge("warning", L("Niet uit te lezen", "Can't read"), "alert"));
      if (i && i.protection === false) b.push(badge("warning", L("Bescherming uit", "Protection off"), "alert"));
      const host = p ? p.host : agHost(i.url);
      const sub = [host !== (i?.name || p.name) ? host : "", !i ? L("alleen DNS-controle, niet gekoppeld", "DNS check only, not linked") : "", i?.version, i?.stats ? L(`${nf(i.stats.queries)} vragen in AdGuard`, `${nf(i.stats.queries)} queries in AdGuard`) : "", i && !p ? L("geen DNS-controle", "no DNS check") : "", i?.error || ""].filter(Boolean).join(" · ");
      return `<div class="adv-row"><div style="min-width:0"><div class="rank-name">${esc(i?.name || p.name)}</div><div class="cell-sub">${esc(sub)}</div></div><div class="adv-badges">${b.join("")}</div></div>`;
    };
    const what = { rewrites: ["rewrite", "rewrites"], lists: [L("filterlijst", "filter list"), L("filterlijsten", "filter lists")], upstreams: ["upstream", "upstreams"] };
    const missing = (x) => `${x.n} ${what[x.what][x.n === 1 ? 0 : 1]} ${L(x.n === 1 ? "ontbreekt op" : "ontbreken op", "missing on")} ${x.missing_on}`;
    const drift = (d.drift?.items || []).filter((x) => x.missing_on);
    const ago2 = (ts) => new Date(ts * 1000).toLocaleString(LOC, { weekday: "short", hour: "2-digit", minute: "2-digit" });
    const ownRow = (x) => {
      const parts = [];
      if (x.redirected) parts.push(L(`${nf(x.redirected)}× omgeleid naar AdGuard`, `${nf(x.redirected)}× redirected to AdGuard`));
      if (x.blocked) parts.push(L(`${nf(x.blocked)}× tegengehouden door je firewall`, `${nf(x.blocked)}× stopped by your firewall`));
      if (x.dot) parts.push(L(`${nf(x.dot)}× DNS-over-TLS doorgelaten`, `${nf(x.dot)}× DNS-over-TLS let through`));
      const b = x.dot ? badge("warning", L("Om AdGuard heen", "Around AdGuard"), "alert")
        : x.redirected ? badge("ok", L("Omgeleid", "Redirected"), "check") : badge("ok", L("Tegengehouden", "Stopped"), "shield");
      return `<div class="adv-row"><div style="min-width:0">${openCli(x.mac, x.name)}<div class="cell-sub">${esc(x.servers.join(", "))} · ${parts.join(" · ")}</div></div><div class="adv-badges">${b}</div></div>`;
    };
    el.innerHTML = `
      <div class="kv" style="margin-bottom:12px">
        <div><div class="k">${L("Vragen, 24 uur", "Queries, 24 hours")}</div><div class="v">${nf(t.queries)}</div></div>
        <div><div class="k">${L("Tegengehouden", "Blocked")}</div><div class="v">${nf(t.blocked)} <span class="muted">(${pct}%)</span></div></div>
        <div><div class="k">${L("Omgeleid via de gateway", "Redirected via the gateway")}</div><div class="v">${nf(t.redirected)}</div></div>
      </div>
      <h3>${L("DNS-servers", "DNS servers")}</h3><div class="adv-list">${rows.map(srvRow).join("")}</div>
      ${drift.length ? `<h3>${L("Verschillen tussen je AdGuard-servers", "Differences between your AdGuard servers")}</h3><div class="adv-list">${drift.map((x) => `<div class="adv-row"><div style="min-width:0"><div class="rank-name">${esc(missing(x))}</div><div class="cell-sub">${esc(x.items.join(", "))}</div></div><div class="adv-badges">${badge("info", L("Uiteen", "Drifted"), "info")}</div></div>`).join("")}</div>` : ""}
      ${d.threats.length ? `<h3>${L("Malware en phishing tegengehouden", "Malware and phishing blocked")}</h3><div class="adv-list">${d.threats.map((x) => `<div class="adv-row hit"><div style="min-width:0">${openCli(x.mac, x.name)}<div class="cell-sub">${x.mac && x.ip ? `${esc(x.ip)} · ` : ""}${esc(x.domains.slice(0, 4).join(", "))} · ${esc(x.lists.join(", "))} · ${L("laatst", "last")} ${ago2(x.last)}</div></div>
        <div class="adv-badges"><span class="num muted">${nf(x.n)}×</span>${x.ips ? badge("critical", L("Ook IPS", "IPS too"), "alert") : badge("warning", L("Tegengehouden", "Blocked"), "shield")}${x.mac ? quarantineMenu(x.mac, L(`Malware/phishing: ${x.domains.slice(0, 2).join(", ")}`, `Malware/phishing: ${x.domains.slice(0, 2).join(", ")}`), true, x.ip) : ""}</div></div>`).join("")}</div>` : ""}
      ${d.new_domains.length ? `<h3>${L("Nieuwe domeinen bij gevolgde apparaten", "New domains on followed devices")}</h3><div class="adv-list">${d.new_domains.map((x) => `<div class="adv-row"><div style="min-width:0">${openCli(x.mac, x.name)}<div class="cell-sub">${x.domains.slice(0, 5).map((v) => `${esc(v.domain)}${v.blocked ? ` (${L("geblokkeerd", "blocked")})` : ""}`).join(", ")}${x.domains.length > 5 ? "…" : ""} · ${L("sinds", "since")} ${ago2(x.domains[x.domains.length - 1].first)}</div></div><div class="adv-badges">${badge("info", L("Nieuw", "New"), "info")}</div></div>`).join("")}</div>` : ""}
      <h3>${L("Apparaten die AdGuard overslaan", "Devices that skip AdGuard")}</h3>
      ${d.bypass.length ? `<div class="adv-list">${d.bypass.map((x) => `<div class="adv-row"><div style="min-width:0">${openCli(x.mac, x.name)}<div class="cell-sub">${L(`${nf(x.flows)} verbindingen met internet in 24 uur, geen enkele vraag aan AdGuard`, `${nf(x.flows)} internet connections in 24 hours, not a single query to AdGuard`)}</div></div><div class="adv-badges">${badge("warning", L("Nakijken", "Review"), "alert")}</div></div>`).join("")}</div>`
        : `<p class="help" style="margin:0">${d.bypass_why ? esc(d.bypass_why) : L("Elk apparaat met internetverkeer vraagt ook iets aan AdGuard.", "Every device with internet traffic also asks AdGuard something.")}</p>`}
      ${(d.own_dns || []).length ? `<h3>${L("Apparaten met een eigen DNS-server", "Devices with their own DNS server")}</h3><div class="adv-list">${d.own_dns.map(ownRow).join("")}</div>` : ""}
      <p class="help" style="margin:12px 0 0">${L(`Omgeleide vragen zijn van apparaten met een eigen DNS-server: je NAT-regel stuurt ze naar AdGuard, maar dan ziet AdGuard alleen de gateway als afzender. ${d.not_watched ? `Domeinen bewaart Sonar alleen van de ${nf(d.watched)} apparaten die het volgt (slimme apparaten en servers${d.personal ? ", en telefoons en laptops" : ""}); van de andere ${nf(d.not_watched)} telt het alleen hoeveel ze opzoeken.` : `Sonar volgt alle ${nf(d.watched)} apparaten en bewaart van elk welke domeinen het opzoekt. Per apparaat zet je dat uit in de apparaatkaart.`}`,
        `Redirected queries come from devices with their own DNS server: your NAT rule sends them to AdGuard, but then AdGuard only sees the gateway as the sender. ${d.not_watched ? `Sonar keeps domains only for the ${nf(d.watched)} devices it follows (smart devices and servers${d.personal ? ", and phones and laptops" : ""}); for the other ${nf(d.not_watched)} it only counts how much they look up.` : `Sonar follows all ${nf(d.watched)} devices and keeps which domains each one looks up. Turn that off per device in the device panel.`}`)}</p>`;
    hydrateIcons(el);
  }

  // ------------------------------------------------------------------ netwerkscheiding
  let segData = null;
  const SEG_KIND = { main: [L("Hoofdnetwerk", "Main network"), "home"], iot: [L("Slimme apparaten", "Smart devices"), "plug"],
    other: [L("Apart netwerk", "Separate network"), "layers"], guest: [L("Gasten", "Guests"), "users"] };
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
    el.innerHTML = `<div class="seg-sub-head"><h3>${hasApart ? L("Slimme apparaten op je hoofdnetwerk", "Smart devices on your main network") : L("Advies", "Advice")}</h3>
        ${muted ? `<button class="chip" id="seg-muted" aria-pressed="${!!state.segShowMuted}">${L("Genegeerde tonen", "Show ignored")} <span class="num">(${muted})</span></button>` : ""}</div>
      ${shown.length ? segListHTML(shown, all)
        : `<div class="empty">${icon("check")}<div>${hasApart ? L("Alle herkende slimme apparaten staan op een apart netwerk", "All recognized smart devices are on a separate network") : L("Niets te melden", "Nothing to report")}</div></div>`}`;
    const b = $("#seg-muted");
    if (b) b.onclick = () => { state.segShowMuted = !state.segShowMuted; renderSegIssues(); };
  }
  // Per apparaat één regel; het (steeds gelijke) verhuisadvies staat er één keer boven.
  function segListHTML(shown, all) {
    const general = shown.filter((i) => !i.key.startsWith("segment:") || i.key === "segment:none");
    const devs = shown.filter((i) => !general.includes(i));
    const cli = cliByMac();
    const target = (segData.segments.find((s) => s.kind === "iot") || segData.segments.find((s) => s.kind === "other") || {}).name || L("het aparte netwerk", "the separate network");
    return `${general.length ? `<div class="issue-list" style="margin-bottom:12px">${general.map((i) => issueHTML(i, all)).join("")}</div>` : ""}
      ${devs.length ? `<div class="advice seg-advice">${icon("bulb")}<span>${L(`<b>Verhuizen naar ${esc(target)}:</b> wifi-apparaten in UniFi bij het apparaat → Settings → Virtual Network Override (kan op dezelfde SSID). Daarna stellen alle access points zich opnieuw in en valt de wifi ongeveer een minuut weg, dus verhuis ze in één keer. Bekabelde apparaten via de switchpoort (Port Manager → Native VLAN/Network). Pas daarna het nieuwe IP-adres aan in Home Assistant of de app die het aanstuurt. Hoort een apparaat bewust hier? Kies Negeren → Altijd.`, `<b>Moving to ${esc(target)}:</b> wifi devices in UniFi at the device → Settings → Virtual Network Override (works on the same SSID). Afterwards all access points re-provision and wifi drops for about a minute, so move them all at once. Wired devices via the switch port (Port Manager → Native VLAN/Network). Then update the new IP address in Home Assistant or the app that controls the device. Does a device belong here on purpose? Choose Ignore → Always.`)}</span></div>
      <div class="seg-devs">${devs.map((i) => {
        const c = cli[i.client_mac] || {};
        const why = (i.detail.match(/\(([^)]+)\)/) || [])[1] || "";
        const via = c.wired ? `${L("bekabeld", "wired")} · ${devName(c.sw_mac)}${c.sw_port ? ` ${L("poort", "port")} ${c.sw_port}` : ""}` : c.ap_mac ? `wifi · ${devName(c.ap_mac)}` : "";
        return `<div class="seg-dev ${i.muted ? "muted" : ""}"><span class="seg-dev-ico">${icon(c.wired ? "cable" : "wifi")}</span>
          <div style="min-width:0"><div class="seg-name">${esc(c.name || i.title.replace(L(" staat op je hoofdnetwerk", " is on your main network"), ""))}</div><div class="cell-sub">${esc([why, via, c.ip].filter(Boolean).join(" · "))}</div></div>
          <div class="seg-dev-act">${i.muted ? badge("", L("Genegeerd", "Ignored")) : ""}${i.client_mac ? `<button class="linkbtn" data-open="client" data-id="${esc(i.client_mac)}">${L("Bekijk", "View")}</button>` : ""}${muteCtlHTML(i)}</div></div>`;
      }).join("")}</div>` : ""}`;
  }
  function ruleText(r) {
    const what = r.targets.length ? r.targets.join(", ") : r.to === "any" ? L("alles", "everything") : r.to;
    const port = r.port ? ` · ${L("poort", "port")} ${r.port}${r.proto ? " " + r.proto : ""}` : r.proto ? ` · ${r.proto}` : "";
    if (r.forward) return `${r.upnp ? L("UPnP-mapping", "UPnP mapping") : "port forward"} ${L("naar", "to")} ${what}${port}`;
    const from = r.sources && r.sources.length ? ` · ${L("alleen vanaf", "only from")} ${r.sources.join(", ")}` : "";
    return `${r.action === "allow" ? L("toegestaan", "allowed") : L("geblokkeerd", "blocked")} ${L("naar", "to")} ${what}${port}${from}`;
  }
  function renderSegments() {
    const d = segData;
    if (!d || !d.available) {
      $("#sec-seg-sub").textContent = "";
      $("#sec-seg-nets").innerHTML = `<p class="muted">${L("Netwerken en firewallzones zijn alleen te zien via de uitgebreide UniFi-API (API-key of lokaal account).", "Networks and firewall zones are only visible via the extended UniFi API (API key or local account).")}</p>`;
      $("#sec-seg-issues").innerHTML = $("#sec-seg-matrix").innerHTML = "";
      return;
    }
    const nets = d.segments;
    $("#sec-seg-sub").textContent = `${plural(nets.length, L("netwerk", "network"), L("netwerken", "networks"))}${d.matrix ? ` · ${d.matrix.zones.length} ${L("firewallzones", "firewall zones")}` : ""}`;
    $("#sec-seg-nets").innerHTML = nets.map((n) => {
      const [label, ic] = SEG_KIND[n.kind] || SEG_KIND.other;
      const iso = n.isolated === true ? badge("ok", L("Afgeschermd", "Isolated"), "lock") : n.isolated === false ? badge("warning", L("Niet afgeschermd", "Not isolated"), "alert") : "";
      return `<div class="seg-net">
        <div class="seg-net-head"><span class="seg-ico">${icon(ic)}</span><div style="min-width:0"><div class="seg-name">${esc(n.name)}</div><div class="cell-sub">${esc(label)}</div></div></div>
        <div class="seg-facts"><span>VLAN <b class="num">${n.vlan ?? "1"}</b></span>${n.subnet ? `<span class="num">${esc(n.subnet)}</span>` : ""}${n.zone ? `<span>zone <b>${esc(n.zone)}</b></span>` : ""}</div>
        <div class="seg-count"><span class="num">${nf(n.clients)}</span> ${L("apparaten", "devices")}<span class="muted"> · ${nf(n.wifi)} wifi · ${nf(n.wired)} ${L("bekabeld", "wired")}</span></div>
        <div class="seg-badges">${iso}${n.smart ? `<span class="muted">${nf(n.smart)} ${L("herkend als slim apparaat", "recognized as smart device")}</span>` : ""}</div></div>`;
    }).join("");
    renderSegIssues();
    renderFlowBlock();
  }
  function matrixHTML(m) {
    const srcs = m.zones.filter((z) => z.networks && z.key !== "external");
    const cell = (a, b) => m.cells[`${a.id}>${b.id}`];
    const rows = srcs.map((a) => `<tr style="cursor:default"><th scope="row">${esc(a.name)}</th>${m.zones.map((b) => {
      const c = cell(a, b);
      if (a.id === b.id && a.networks < 2) return `<td class="mx-na" title="${L("Binnen één netwerk gaat verkeer niet via de firewall", "Within one network traffic does not pass the firewall")}">–</td>`;
      if (!c || !c.effective) return `<td class="mx-na">?</td>`;
      const n = c.rules.filter((r) => r.enabled).length;
      const lbl = c.effective === "allow" ? "Open" : L("Dicht", "Closed");
      const tip = `${a.name} → ${b.name}: ${c.effective === "allow" ? L("toegestaan", "allowed") : L("geblokkeerd", "blocked")}${n ? L(`, met ${n} eigen regel${n > 1 ? "s" : ""}`, `, with ${n} custom rule${n > 1 ? "s" : ""}`) : ""}`;
      return `<td class="mx ${c.effective}" title="${esc(tip)}"><span class="mx-pill">${c.effective === "block" ? icon("lock") : ""}${lbl}</span>${n ? `<span class="mx-n">+${n}</span>` : ""}</td>`;
    }).join("")}</tr>`).join("");
    const exc = [];
    srcs.forEach((a) => m.zones.forEach((b) => { const c = cell(a, b); if (c && c.rules.length) exc.push([a, b, c]); }));
    return `<p class="cell-sub" style="margin:0 0 8px">${L("Per firewallzone · rij = van, kolom = naar · standaard plus je eigen regels", "Per firewall zone · row = from, column = to · default plus your own rules")}</p>
      <div class="table-wrap mx-wrap"><table class="mx-table"><thead><tr><th scope="col"><span class="sr-only">${L("Van", "From")}</span></th>${m.zones.map((z) => `<th scope="col">${esc(z.key === "external" ? "Internet" : z.name)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>
      ${exc.length ? `<div class="mx-exc">${exc.map(([a, b, c]) => `<div class="mx-exc-row"><div class="mx-exc-pair">${esc(a.name)} → ${esc(b.key === "external" ? "Internet" : b.name)}<div class="cell-sub">${L("standaard", "default")} ${c.default === "allow" ? "open" : L("dicht", "closed")}</div></div>
        <ul>${c.rules.map((r) => `<li class="${r.enabled ? "" : "off"}"><b>${esc(r.name)}</b> <span class="muted">${esc(ruleText(r))}${r.enabled ? "" : ` · ${L("uitgeschakeld", "disabled")}`}</span></li>`).join("")}</ul></div>`).join("")}</div>` : ""}`;
  }

  // ------------------------------------------------------------------ toegang tussen netwerken (diagram)
  const FL = { sel: store.get("fl.sel", null), edge: null, view: store.get("fl.view", "diagram"), key: "", ro: null, w: 0 };
  const FL_ICON = { main: "home", iot: "plug", other: "layers", guest: "users", vpn: "key", gateway: "router", internet: "globe" };
  const FL_SUB = { main: L("hoofdnetwerk", "main network"), iot: L("slimme apparaten", "smart devices"), other: L("apart netwerk", "separate network"),
    guest: L("gasten", "guests"), vpn: "VPN", gateway: "router", internet: L("buitenwereld", "outside world") };
  const FL_ST = { allow: [L("mag", "allowed"), "check"], partial: [L("deels", "partly"), "alert"], block: [L("geblokkeerd", "blocked"), "x"] };
  const trunc = (t, n) => (t.length > n ? t.slice(0, n - 1) + "…" : t);

  function renderFlowBlock() {
    const el = $("#sec-seg-matrix"), d = segData;
    if (!el || !d || !d.available) return;
    if (!d.matrix || !d.flows) {
      FL.key = "";
      el.innerHTML = `<p class="muted" style="margin-top:16px">${L("Wat er tussen je netwerken mag, is alleen te zien met de zone-gebaseerde firewall (UniFi Network 9 of nieuwer).", "What is allowed between your networks can only be shown with the zone-based firewall (UniFi Network 9 or newer).")}</p>`;
      return;
    }
    const key = FL.view + JSON.stringify(d.flows) + (FL.view === "tabel" ? JSON.stringify(d.matrix) : "");
    if (key === FL.key && el.firstChild) return;   // niets veranderd: laat selectie en animatie staan
    FL.key = key;
    el.innerHTML = `
      <div class="seg-sub-head"><div><h3>${L("Toegang tussen netwerken", "Access between networks")}</h3>
          <div class="cell-sub">${L("Wat er mag bij een nieuwe verbinding, nagerekend uit je firewallregels op volgorde. Kies een netwerk voor zijn pijlen, of een pijl voor de regels die het bepalen.", "What a new connection is allowed to do, worked out from your firewall rules in order. Pick a network for its arrows, or an arrow for the rules behind it.")}</div></div>
        <div class="seg" role="group" aria-label="${L("Weergave", "View")}" id="fl-view">${[["diagram", "Diagram"], ["tabel", L("Tabel", "Table")]].map(([v, l]) => `<button data-flview="${v}" aria-pressed="${FL.view === v}">${l}</button>`).join("")}</div></div>
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
    const dx = b[0] - a[0], dy = b[1] - a[1], dist = Math.hypot(dx, dy) || 1, nx = -dy / dist, ny = dx / dist, half = both ? 13 : 5;
    const c = [(a[0] + b[0]) / 2 + nx * half * 2, (a[1] + b[1]) / 2 + ny * half * 2];
    const p0 = flClip(a, w, h, c), p1 = flClip(b, w, h, c), f = (v) => v.toFixed(1);
    return { d: `M${f(p0[0])},${f(p0[1])} Q${f(c[0])},${f(c[1])} ${f(p1[0])},${f(p1[1])}`, len: dist };
  }

  function flNodeHTML(n, x, y, nw, nh, on, compact) {
    const sub = n.kind !== "vpn" && n.kind !== "gateway" && n.kind !== "internet" && n.clients != null
      ? `${nf(n.clients)} ${L("apparaten", "devices")}` : FL_SUB[n.kind] || "";
    const tx = compact ? 13 : 51, maxc = Math.floor((nw - tx - (n.isolated ? 24 : 8)) / 7.4);
    return `<g class="fl-node ${n.kind}${on ? " sel" : ""}" data-node="${esc(n.id)}" tabindex="0" role="button" aria-pressed="${on}"
        aria-label="${esc(`${n.name}${n.isolated ? L(", afgeschermd", ", isolated") : ""}`)}" style="transform:translate(${(x - nw / 2).toFixed(1)}px,${(y - nh / 2).toFixed(1)}px)">
      <title>${esc(n.name)}${n.subnet ? ` · ${esc(n.subnet)}` : ""}</title>
      <rect width="${nw}" height="${nh}" rx="14"/>
      ${compact ? "" : `<rect class="fl-ico-bg" x="11" y="${nh / 2 - 15}" width="30" height="30" rx="9"/>
      <svg class="fl-ico" x="17" y="${nh / 2 - 9}" width="18" height="18" viewBox="0 0 24 24">${ICONS[FL_ICON[n.kind]] || ""}</svg>`}
      <text class="fl-name" x="${tx}" y="${nh / 2 - 2}">${esc(trunc(n.name, maxc))}</text>
      <text class="fl-sub" x="${tx}" y="${nh / 2 + 14}">${esc(trunc(sub, Math.floor((nw - tx - 6) / 6.3)))}</text>
      ${n.isolated ? `<svg class="fl-lock" x="${nw - 21}" y="8" width="13" height="13" viewBox="0 0 24 24"><title>${L("Afgeschermd", "Isolated")}</title>${ICONS.lock}</svg>` : ""}
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
      const lbl = `${byId[e.from].name} ${L("naar", "to")} ${byId[e.to].name}: ${FL_ST[e.status][0]}`;
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
      canvas.innerHTML = `<svg class="fl-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H.toFixed(0)}" data-w="${W}" data-nodes="${esc(fl.nodes.map((n) => n.id).join("|"))}" role="group" aria-label="${L("Toegang tussen netwerken", "Access between networks")}">
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
        <ul>${items.map((it) => `<li><span>${esc(it.what)}</span>${it.how ? `<span class="fl-how">${esc(it.how)}</span>` : ""}${it.name ? `<div class="cell-sub">${L("regel", "rule")}: ${esc(it.name)}</div>` : ""}</li>`).join("")}</ul></div>`;
      const nr = e.rules.length, s = nr > 1 ? "s" : "";
      el.innerHTML = `<div class="fl-det-head"><b>${esc(a.name)} → ${esc(b.name)}</b>${pill(e.status)}<button class="linkbtn" data-fl-close>${L("Sluiten", "Close")}</button></div>
        <div class="fl-wn-grid">${col("wel", L("Wel", "Allowed"), wn.wel)}${col("niet", L("Niet", "Not allowed"), wn.niet)}</div>
        <div class="cell-sub" style="margin-top:10px">${L("Standaard", "Default")} ${e.default === "allow" ? L("toegestaan", "allowed") : L("geblokkeerd", "blocked")}${a.zone && b.zone ? ` (zone ${esc(a.zone)} → ${esc(b.zone)})` : ""}${nr ? L(`, aangevuld met ${nr} eigen regel${s}.`, `, plus ${nr} custom rule${s}.`) : L(", zonder eigen regels.", ", without custom rules.")}
          ${wn.base === "block" ? L(` Antwoorden op verbindingen die ${esc(b.name)} zelf begint, komen wel terug.`, ` Replies to connections that ${esc(b.name)} starts itself do come back.`) : ""}</div>`;
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
        return `${esc(other)} <span class="muted">(${wn.base === "block" ? L("alleen", "only") : L("behalve", "except")} ${esc(short)})</span>`;
      });
      return `<div class="fl-sum-row">${pill(st)}<span>${names.join(", ")}</span></div>`;
    }).join("");
    const out = edges.filter((x) => x.from === n.id), inc = edges.filter((x) => x.to === n.id);
    el.innerHTML = `<div class="fl-sum">
      ${out.length ? `<div><div class="fl-sum-h">${L(`Vanaf ${esc(n.name)} naar`, `From ${esc(n.name)} to`)}</div>${group(out, true)}</div>` : ""}
      ${inc.length ? `<div><div class="fl-sum-h">${L(`Naar ${esc(n.name)} vanaf`, `To ${esc(n.name)} from`)}</div>${group(inc, false)}</div>` : ""}</div>`;
  }

  // Wat mag er wel en niet over deze pijl? Uit de standaard plus de regels op volgorde.
  function flWelNiet(e, b) {
    const isWhole = (r) => !r.forward && !r.ips.length && !(r.src_ips || []).length && !r.port && !r.proto;
    const whole = e.rules.find(isWhole);
    const base = whole ? whole.action : e.default;
    const item = (r) => ({
      what: r.targets && r.targets.length ? r.targets.join(", ") : r.to === "any" ? L(`alles in ${b.name}`, `everything in ${b.name}`) : r.to,
      how: [r.port ? `${L("poort", "port")} ${r.port}${r.proto ? " " + r.proto : ""}` : r.proto || "",
            r.sources && r.sources.length ? `${L("alleen vanaf", "only from")} ${r.sources.join(", ")}` : "",
            r.forward ? (r.upnp ? "UPnP" : "port forward") : ""].filter(Boolean).join(" · "),
      name: r.forward ? r.name : r.name });
    const exc = e.rules.filter((r) => r !== whole);
    const rest = { what: exc.length ? L("al het andere", "everything else") : L(`alles naar ${b.name}`, `everything to ${b.name}`), how: "", name: whole ? whole.name : "" };
    const wel = exc.filter((r) => r.action === "allow").map(item), niet = exc.filter((r) => r.action === "block").map(item);
    if (base === "allow") wel.push(rest); else niet.push(rest);
    const none = [{ what: L("niets", "nothing"), how: "", name: "" }];
    return { base, wel: wel.length ? wel : none, niet: niet.length ? niet : none };
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
  $("#view").addEventListener("click", async (e) => { if (await quarantineAction(e)) return; if (current === "clients") await pauseAction(e); });
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
    if (!x) return `<p class="muted">${L("Port forwards en UPnP zijn alleen te zien via de uitgebreide UniFi-API (API-key of lokaal account).", "Port forwards and UPnP are only visible via the extended UniFi API (API key or local account).")}</p>`;
    const f = x.forwards;
    if (!f.length) return `<div class="empty">${icon("check")}<div>${L("Geen port forwards en geen actieve UPnP-mappings", "No port forwards and no active UPnP mappings")}</div></div>`;
    return `<div class="table-wrap" style="border:0"><table><thead><tr><th>${L("Naam", "Name")}</th><th>${L("Poort op internet", "Internet port")}</th><th>${L("Naar", "To")}</th><th>${L("Soort", "Type")}</th><th class="r">${L("Aanvallen", "Attacks")}</th><th>Status</th></tr></thead><tbody>
      ${f.map((r) => `<tr style="cursor:default" class="${r.enabled ? "" : "off"}"><td class="cell-name">${esc(r.name)}</td>
        <td class="num">${esc(r.port)}<span class="muted"> ${esc(r.proto)}</span></td>
        <td>${esc(r.target_name || r.fwd_ip)}<div class="cell-sub">${esc(r.fwd_ip)}:${esc(r.fwd_port || r.port)}</div></td>
        <td>${r.upnp ? badge("info", "UPnP") : badge("", L("Vast", "Fixed"))}${r.src && r.src !== "any" ? `<div class="cell-sub">${L("alleen", "only")} ${esc(r.src)}</div>` : ""}</td>
        <td class="r num ${r.attacks >= 10 ? "t-warning" : ""}">${r.enabled ? nf(r.attacks) : "–"}</td>
        <td>${r.enabled ? badge("warning", "Open", "globe") : badge("", L("Uit", "Off"))}</td></tr>`).join("")}</tbody></table></div>`;
  }
  const srcLabel = (e) => `${esc(e.src_name && e.src_name !== e.src_ip ? e.src_name : e.src_ip)}${e.src_name && e.src_name !== e.src_ip ? `<div class="cell-sub">${esc(e.src_ip)}</div>` : ""}`;
  UPDATERS.beveiliging = async function () {
    loadSegments(); renderSecChecks(); loadAdvisories(); if (!$("#sec-vuln").dataset.bound) { $("#sec-vuln").dataset.bound = "1"; bindVuln(); } loadVuln(); loadAdGuard();
    const d = await api(`/api/ips?hours=${secState.hours}&scope=${secState.scope}&ignored=${secState.ignored}`);
    if (current !== "beveiliging") return;
    const s = d.summary;
    $("#sec-banner").innerHTML = d.available === false
      ? `<div class="banner err">${icon("info")}<span>${L("IPS-gegevens zijn alleen beschikbaar via de uitgebreide UniFi-API (API-key of lokaal account).", "IPS data is only available via the extended UniFi API (API key or local account).")}</span></div>` : "";
    const per = secState.hours <= 24 ? L("24 uur", "24 hours") : secState.hours <= 168 ? L("7 dagen", "7 days") : L("14 dagen", "14 days");
    $("#sec-kpis").innerHTML = `
      <div class="card compact kpi"><div class="label">${icon("shield")}${L("Blokkades", "Blocks")}</div><div class="value">${nf(s.total)}</div><div class="sub">${L("afgelopen", "past")} ${per}</div></div>
      <div class="card compact kpi"><div class="label">${icon("globe")}${L("Van buiten", "From outside")}</div><div class="value">${nf(s.external)}</div><div class="sub">${L("tegengehouden door de IPS", "stopped by the IPS")}</div></div>
      <div class="card compact kpi"><div class="label">${icon("home")}${L("Van eigen apparaten", "From own devices")}</div><div class="value">${nf(s.internal)}</div>
        <div class="sub">${s.internal ? `<button type="button" class="badge warning" id="sec-review" aria-controls="sec-table">${icon("alert")}${L("Bekijken", "Review")}</button>` : badge("ok", L("Geen", "None"), "check")}</div></div>
      <div class="card compact kpi"><div class="label">${icon("users")}${L("Unieke bronnen", "Unique sources")}</div><div class="value">${nf(s.sources)}</div><div class="sub">${L("IP-adressen", "IP addresses")}</div></div>`;
    const max1 = Math.max(1, ...d.by_signature.map((x) => x.count)), max2 = Math.max(1, ...d.by_source.map((x) => x.count));
    const srcName = (x) => (x.name && x.name !== x.ip ? `${x.name} (${x.ip})` : x.ip);
    $("#sec-sigs").innerHTML = d.by_signature.length ? d.by_signature.map((x) => `
      <div class="rank-row"><div class="rank-main"><div class="rank-name" title="${esc(x.signature)}">${esc(x.signature)}</div><div class="cell-sub">${esc(catLabel(x.category))}${x.sid ? ` · SID ${x.sid}` : ""}</div></div>
        <div class="rank-bar">${meter(100 * x.count / max1)}</div><span class="num rank-n">${x.count}</span>
        <span>${x.sid ? ignMenu([[L("Negeer deze regel", "Ignore this rule"), { sid: x.sid, label: x.signature }]]) : ""}</span></div>`).join("")
      : `<div class="empty">${icon("check")}<div>${L("Niets geblokkeerd in deze periode", "Nothing blocked in this period")}</div></div>`;
    $("#sec-srcs").innerHTML = d.by_source.length ? d.by_source.map((x) => `
      <div class="rank-row"><div class="rank-main"><div class="rank-name">${esc(srcName(x))}</div><div class="cell-sub">${x.internal ? badge("warning", L("eigen netwerk", "own network"), "home") : badge("", "internet", "globe")} ${esc(x.net || "")}</div></div>
        <div class="rank-bar">${meter(100 * x.count / max2, x.internal ? "warning" : "")}</div><span class="num rank-n">${x.count}</span>
        <span>${ignMenu([[L("Negeer dit adres", "Ignore this address"), { ip: x.ip, label: srcName(x) }]])}</span></div>`).join("")
      : `<div class="empty">${L("Geen bronnen", "No sources")}</div>`;
    $("#sec-expo-sub").textContent = d.exposure ? (d.exposure.upnp_enabled ? L("UPnP staat aan", "UPnP is on") : d.exposure.upnp_enabled === false ? L("UPnP staat uit", "UPnP is off") : "") + ` · ${L("aanvallen in de afgelopen", "attacks in the past")} ${per}` : "";
    $("#sec-expo").innerHTML = exposureHTML(d.exposure);
    $("#sec-ignored-n").textContent = s.ignored ? `(${s.ignored})` : "";
    $("#sec-ign-card").hidden = !d.ignores.length;
    $("#sec-ign").innerHTML = d.ignores.map((r) => `<div class="rank-row ign-row"><div class="rank-main"><div class="rank-name">${esc(r.label || (r.ip || "") + (r.sid ? " SID " + r.sid : ""))}</div>
      <div class="cell-sub">${r.ip && r.sid ? L(`regel ${r.sid} voor ${esc(r.ip)}`, `rule ${r.sid} for ${esc(r.ip)}`) : r.ip ? L(`alle regels voor ${esc(r.ip)}`, `all rules for ${esc(r.ip)}`) : L(`regel ${r.sid}, alle adressen`, `rule ${r.sid}, all addresses`)} · ${L("sinds", "since")} ${new Date(r.created * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short" })}</div></div>
      <button class="linkbtn" data-unign="${r.id}">${L("Niet meer negeren", "Stop ignoring")}</button></div>`).join("");
    $("#sec-bucket").textContent = d.bucket === 3600 ? L("per uur", "per hour") : L("per 6 uur", "per 6 hours");
    MEcharts.lineChart($("#sec-chart"), { series: [
      { name: L("Van buiten", "From outside"), color: C.cyan, data: d.series.map((p) => [p.t, p.external]) },
      { name: L("Eigen apparaten", "Own devices"), color: C.amber, data: d.series.map((p) => [p.t, p.internal]) }],
      yMin: 0, bucket: d.bucket, fmt: (v) => nf(v), label: L("Aantal IPS-blokkades", "Number of IPS blocks") });
    const ev = d.events;
    $("#sec-table").innerHTML = ev.length ? `<table><thead><tr><th>${L("Tijd", "Time")}</th><th>${L("Bron", "Source")}</th><th>${L("Doel", "Target")}</th><th>${L("Regel", "Rule")}</th><th>${L("Risico", "Risk")}</th><th><span class="sr-only">${L("Acties", "Actions")}</span></th></tr></thead><tbody>
      ${ev.map((e) => `<tr style="cursor:default"><td class="num"><div>${hhmm(e.ts)}</div><div class="cell-sub">${new Date(e.ts * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short" })}</div></td>
        <td>${e.internal ? `<span class="t-warning">${icon("home", "")}</span> ` : ""}${srcLabel(e)}<div class="cell-sub">${esc(e.src_net || "")}</div></td>
        <td>${esc(e.dst_name || e.dst_ip)}${e.dst_port ? `<span class="muted">:${e.dst_port}</span>` : ""}<div class="cell-sub">${esc([e.proto, e.service].filter(Boolean).join(" · "))}</div></td>
        <td style="white-space:normal;min-width:240px"><div>${esc(e.signature)}</div><div class="cell-sub">${esc(catLabel(e.category))}${e.sid ? ` · SID ${e.sid}` : ""}</div></td>
        <td>${badge(e.risk === "high" ? "critical" : e.risk === "medium" ? "warning" : "", e.risk || "–")}${e.ignored ? ` ${badge("", L("genegeerd", "ignored"))}` : ""}</td>
        <td>${e.ignored ? "" : ignMenu([...(e.sid ? [[L("Deze regel voor dit adres", "This rule for this address"), { ip: e.src_ip, sid: e.sid, label: `${e.signature} · ${e.src_name || e.src_ip}` }], [L("Deze regel overal", "This rule everywhere"), { sid: e.sid, label: e.signature }]] : []), [L("Dit adres", "This address"), { ip: e.src_ip, label: e.src_name || e.src_ip }]])}</td></tr>`).join("")}</tbody></table>`
      : `<div class="empty">${icon("check")}<div>${L("Geen blokkades voor deze filter", "No blocks for this filter")}</div></div>`;
  };

  // ------------------------------------------------------------------ setup-wizard
  const wiz = { step: 1, address: "", api_key: "", username: "", password: "", site: "default", verify_tls: false,
                current_api_key: "", result: null, error: null, busy: false, info: null };
  async function showWizard(step) {
    document.body.classList.add("setup");
    $("#status").innerHTML = `<span class="dot off"></span>${L("Nog niet gekoppeld", "Not connected yet")}`;
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
    const steps = [L("Welkom", "Welcome"), L("Koppelen", "Connect"), L("Controleren", "Check")];
    const reconf = wiz.info?.configured;
    const head = `<div class="wiz-brand"><span class="logo">${icon("radar")}</span><div><div class="wiz-title">UniFi Sonar</div><div class="muted">${reconf ? L("Koppeling wijzigen", "Change connection") : L("Eerste keer instellen", "First-time setup")}</div></div></div>
      <ol class="wiz-steps" aria-label="${L("Stappen", "Steps")}">${steps.map((s, i) => `<li ${i + 1 === wiz.step ? 'aria-current="step"' : ""} class="${i + 1 < wiz.step ? "done" : ""}"><span>${i + 1}</span>${s}</li>`).join("")}</ol>`;
    let body = "";
    if (wiz.step === 1) {
      body = `<h1>${L("Welkom", "Welcome")}</h1>
        <p class="lead">${L("UniFi Sonar houdt je UniFi-netwerk in de gaten en vertelt in gewone taal waar het misgaat: zwak wifi-signaal, veel retries, drukke kanalen, kabelproblemen, apparaten die op de verkeerde AP blijven hangen en wat de IPS tegenhoudt.", "UniFi Sonar keeps an eye on your UniFi network and tells you in plain language where things go wrong: weak wifi signal, many retries, busy channels, cable problems, devices stuck on the wrong AP and what the IPS stops.")}</p>
        <p class="muted">${L("Je hebt nodig: het IP-adres van je UniFi-console (UDM, UCG, Cloud Gateway of UniFi OS Server) en een API-key. Alles blijft op dit apparaat; er gaat niets naar internet.", "You need: the IP address of your UniFi console (UDM, UCG, Cloud Gateway or UniFi OS Server) and an API key. Everything stays on this device; nothing goes to the internet.")}</p>
        <div class="wiz-actions"><button class="btn primary" data-wiz="2">${L("Koppel mijn UniFi-controller", "Connect my UniFi controller")}</button><button class="btn" data-wiz="demo">${L("Eerst rondkijken met demodata", "Look around with demo data first")}</button></div>`;
    } else if (wiz.step === 2) {
      body = `<h1>${L("Koppel je controller", "Connect your controller")}</h1>
        <form id="wiz-form" novalidate>
        ${field("w-addr", L("Adres van je UniFi-console", "Address of your UniFi console"), `<input class="input" id="w-addr" name="address" required autocomplete="off" spellcheck="false" placeholder="192.168.1.1" value="${esc(wiz.address)}">`,
          L("Het IP-adres of de hostnaam. Poort 443 en 11443 (UniFi OS Server) worden allebei geprobeerd; een andere poort vul je zo in: <code>192.168.1.10:8443</code>.", "The IP address or host name. Ports 443 and 11443 (UniFi OS Server) are both tried; enter another port like this: <code>192.168.1.10:8443</code>."))}
        ${field("w-key", L("API-key", "API key"), `<div class="pw"><input class="input" id="w-key" name="api_key" type="password" autocomplete="off" spellcheck="false" placeholder="${L("Plak hier je API-key", "Paste your API key here")}" value="${esc(wiz.api_key)}"><button type="button" class="btn ghost" data-show="w-key" aria-label="${L("Toon API-key", "Show API key")}">${icon("eye")}</button></div>`,
          L(`<details><summary>Waar vind ik de API-key?</summary><ol><li>Open <b>UniFi Network</b> op je console.</li><li>Ga naar <b>Instellingen → Control Plane → Integrations</b>.</li><li>Kies <b>Create API Key</b>, geef hem een naam (bijv. "UniFi Sonar") en kopieer de sleutel. Je ziet hem maar één keer.</li></ol></details>`,
            `<details><summary>Where do I find the API key?</summary><ol><li>Open <b>UniFi Network</b> on your console.</li><li>Go to <b>Settings → Control Plane → Integrations</b>.</li><li>Choose <b>Create API Key</b>, give it a name (e.g. "UniFi Sonar") and copy the key. You only see it once.</li></ol></details>`))}
        ${reconf && wiz.info.needs_confirmation ? field("w-cur", L("Huidige API-key (ter bevestiging)", "Current API key (to confirm)"), `<input class="input" id="w-cur" name="current_api_key" type="password" autocomplete="off" value="${esc(wiz.current_api_key)}">`, L("Alleen nodig als je een andere API-key invult. Zo kan niet iedereen in je netwerk de koppeling omzetten.", "Only needed when you enter a different API key. This way not everyone on your network can change the connection.")) : ""}
        <details class="adv"><summary>${L("Geavanceerd", "Advanced")}</summary>
          ${field("w-site", "Site", `<input class="input" id="w-site" name="site" value="${esc(wiz.site)}" spellcheck="false">`, L("Meestal <code>default</code>.", "Usually <code>default</code>."))}
          <label class="check"><input type="checkbox" id="w-tls" name="verify_tls" ${wiz.verify_tls ? "checked" : ""}> ${L("Certificaat controleren", "Verify certificate")} <span class="muted">${L("(alleen met een officieel certificaat; staat dit uit, dan legt Sonar het certificaat van je controller vast bij de eerste verbinding)", "(only with an official certificate; if off, Sonar pins your controller's certificate on first connection)")}</span></label>
          <p class="help" style="margin-top:14px">${L("Geeft je API-key alleen beperkte gegevens (geen signaal en retries)? Vul dan een lokaal account met <b>View Only</b>-rechten in. Dat wordt alleen gebruikt als het nodig is.", "Does your API key only give limited data (no signal and retries)? Then enter a local account with <b>View Only</b> rights. It is only used when needed.")}</p>
          ${field("w-user", L("Gebruikersnaam (optioneel)", "Username (optional)"), `<input class="input" id="w-user" name="username" autocomplete="off" value="${esc(wiz.username)}">`)}
          ${field("w-pass", L("Wachtwoord (optioneel)", "Password (optional)"), `<input class="input" id="w-pass" name="password" type="password" autocomplete="off" value="${esc(wiz.password)}">`)}
        </details>
        ${wiz.error ? `<div class="banner err" role="alert">${icon("octagon")}<div><b>${esc(wiz.error.error)}</b>${wiz.error.hint ? `<div>${esc(wiz.error.hint)}</div>` : ""}</div></div>` : ""}
        <div class="wiz-actions"><button type="submit" class="btn primary" ${wiz.busy ? "disabled" : ""}>${wiz.busy ? L("Bezig met testen…", "Testing…") : L("Verbinding testen", "Test connection")}</button>
          <button type="button" class="btn ghost" data-wiz="${reconf ? "cancel" : "1"}">${reconf ? L("Annuleren", "Cancel") : L("Terug", "Back")}</button></div>
        </form>`;
    } else if (wiz.step === 3) {
      const r = wiz.result;
      const row = (ok, text) => `<li>${icon(ok ? "check" : "alert", ok ? "t-ok" : "t-warning")}<span>${text}</span></li>`;
      body = `<h1>${L("Gelukt", "Success")}</h1><p class="lead">${L("De verbinding werkt. Dit is wat ik zie:", "The connection works. This is what Sonar sees:")}</p>
        <ul class="checks">
          ${row(true, `${L("Bereikbaar op", "Reachable at")} <b>${esc(r.url)}</b>`)}
          ${row(r.source !== "integration", `${L("Ingelogd via de", "Logged in via the")} ${esc(SOURCE_LABEL[r.source] || r.source)}`)}
          ${r.gateway ? row(true, `Gateway: <b>${esc(r.gateway)}</b>`) : ""}
          ${row(r.devices > 0, L(`<b>${r.devices}</b> UniFi-apparaten en <b>${r.clients}</b> clients`, `<b>${r.devices}</b> UniFi devices and <b>${r.clients}</b> clients`))}
        </ul>
        ${r.warnings.map((w) => `<div class="banner">${icon("info")}<span>${esc(w)}</span></div>`).join("")}
        ${wiz.error ? `<div class="banner err" role="alert">${icon("octagon")}<span>${esc(wiz.error.error)}</span></div>` : ""}
        <div class="wiz-actions"><button class="btn primary" data-wiz="save" ${wiz.busy ? "disabled" : ""}>${wiz.busy ? L("Opslaan…", "Saving…") : L("Opslaan en starten", "Save and start")}</button><button class="btn ghost" data-wiz="2">${L("Terug", "Back")}</button></div>`;
    }
    $("#view").innerHTML = `<div class="wizard">${head}<div class="card wiz-card">${body}</div><p class="wiz-foot muted">${L("Je API-key wordt alleen op dit apparaat opgeslagen en nooit teruggestuurd naar de browser.", "Your API key is only stored on this device and never sent back to the browser.")}</p></div>`;
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
    if (r.status === 401) throw needLogin();
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || r.statusText);
    return j;
  }
  async function wizTest() {
    readForm();
    wiz.error = null;
    if (!wiz.address) { wiz.error = { error: L("Vul het adres van je UniFi-console in.", "Enter the address of your UniFi console.") }; return renderWizard(); }
    if (!wiz.api_key && !(wiz.username && wiz.password)) { wiz.error = { error: L("Vul een API-key in.", "Enter an API key.") }; return renderWizard(); }
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
    mount("instellingen", `<div class="page-head"><div><h1>${L("Instellingen", "Settings")}</h1><p class="subtitle">${L("Koppeling, taal, meldingen naar je telefoon, toegang en probleemoplossing.", "Connection, language, notifications to your phone, access and troubleshooting.")}</p></div></div>
      ${jumpBar("instellingen", [["#h-conn", L("Koppeling", "Connection"), 1], ["#h-lang", L("Taal", "Language")], ["#h-notify", L("Meldingen", "Notifications")], ["#h-mqtt", "Home Assistant"],
        ["#h-adguard", "AdGuard"], ["#h-access", L("Toegang", "Access")], ["#h-backups", "Backups"], ["#h-kiosk", L("Muurscherm", "Wall display")], ["#h-debug", L("Probleemoplossing", "Troubleshooting")]])}
      <div class="settings">
        <section class="card" aria-labelledby="h-conn"><h2 id="h-conn">${L("Koppeling", "Connection")}</h2><div id="set-conn"></div></section>
        <section class="card" aria-labelledby="h-lang"><h2 id="h-lang">${L("Taal", "Language")}</h2>
          <p class="help" style="margin:-4px 0 12px">${L("Geldt voor het dashboard, de meldingen die Sonar verstuurt en de namen in Home Assistant.", "Applies to the dashboard, the notifications Sonar sends and the names in Home Assistant.")}</p>${langSwitch(true)}</section>
        <section class="card" aria-labelledby="h-notify"><h2 id="h-notify">${L("Meldingen versturen", "Sending notifications")}</h2>
          <p class="help" style="margin:-4px 0 4px">${L("Krijg een bericht als er iets misgaat: via Home Assistant, ntfy, Discord, Slack of een eigen webhook.", "Get a message when something goes wrong: via Home Assistant, ntfy, Discord, Slack or your own webhook.")}</p><div id="set-notify"></div></section>
        <section class="card" aria-labelledby="h-mqtt"><h2 id="h-mqtt">Home Assistant (MQTT)</h2>
          <p class="help" style="margin:-4px 0 4px">${L("Zet de netwerkscore, meldingen, internetsnelheid, datagebruik en een speedtest-knop in Home Assistant. HA herkent alles vanzelf via MQTT-discovery.", "Put the network score, issues, internet speed, data usage and a speed test button in Home Assistant. HA picks everything up automatically via MQTT discovery.")}</p><div id="set-mqtt"></div></section>
        <section class="card" aria-labelledby="h-adguard"><h2 id="h-adguard">AdGuard Home</h2>
          <p class="help" style="margin:-4px 0 4px">${L("Namen bij je verbindingen, wat je slimme apparaten opzoeken, of je DNS-servers het doen en wat AdGuard aan malware tegenhield. Sonar leest alleen.", "Names for your connections, what your smart devices look up, whether your DNS servers work and what malware AdGuard blocked. Sonar only reads.")}</p><div id="set-adguard"></div></section>
        <section class="card" aria-labelledby="h-access"><h2 id="h-access">${L("Toegang", "Access")}</h2><div id="set-access"></div></section>
        <section class="card" aria-labelledby="h-backups"><h2 id="h-backups">${L("UniFi-backups", "UniFi backups")}</h2><div id="set-backups"></div></section>
        <section class="card" aria-labelledby="h-kiosk"><h2 id="h-kiosk">${L("Muurscherm", "Wall display")}</h2>
          <p class="help" style="margin:-4px 0 12px">${L("Een rustige weergave op volledig scherm voor een tablet aan de muur. Bewaar de link op het apparaat; staat de inlog aan, dan log je daar één keer in.", "A calm full-screen view for a tablet on the wall. Save the link on that device; if the login is on, you log in there once.")}</p>
          <div class="wiz-actions" style="margin-top:0"><a class="btn" href="#/kiosk">${L("Rustig", "Calm")}</a><a class="btn" href="#/kiosk/globe">${L("Met globe", "With globe")}</a><a class="btn" href="#/kiosk/paper">${L("E-paper (zwart-wit)", "E-paper (black and white)")}</a></div></section>
        <section class="card" aria-labelledby="h-debug"><h2 id="h-debug">${L("Probleemoplossing", "Troubleshooting")}</h2><div id="set-debug"></div></section>
      </div>
      <p class="muted" style="font-size:12px;margin-top:16px">${L("UniFi Sonar is een onofficieel hobbyproject en niet verbonden aan Ubiquiti.", "UniFi Sonar is an unofficial hobby project and not affiliated with Ubiquiti.")}</p>`);
    $("#set-conn").addEventListener("click", (e) => {
      const b = e.target.closest("[data-act]");
      if (!b) return;
      if (b.dataset.act === "change") { wiz.step = 2; wiz.address = ""; showWizard(2); }
      if (b.dataset.act === "demo") { wiz.step = 1; showWizard(1); }
    });
    loadNotify(); loadMqtt(); loadAgSettings(); loadAccess(); loadBackups(); loadDebug();
    $("#set-adguard").addEventListener("click", (e) => { const b = e.target.closest("[data-ag]"); if (b) agAction(b.dataset.ag, b); });
    $("#set-mqtt").addEventListener("click", (e) => { const b = e.target.closest("[data-mq]"); if (b) mqttAction(b.dataset.mq, b); });
  }
  UPDATERS.instellingen = async function () {   // alleen de koppeling ververst; formulieren blijven staan
    const info = await api("/api/setup").catch(() => ({}));
    const s = state.status || {};
    if (current !== "instellingen" || !$("#set-conn")) return;
    const live = info.mode === "live";
    $("#set-conn").innerHTML = `
      ${kv([[L("Modus", "Mode"), live ? badge("ok", "Live", "check") : badge("info", L("Demodata", "Demo data"))],
            ["Controller", live ? esc(info.controller_url) : "–"], ["Site", live ? esc(info.site) : "–"],
            [L("Bron", "Source"), esc(SOURCE_LABEL[s.source] || s.source || "–")], [L("Laatste meting", "Last reading"), s.last_ok ? L(`${ago(s.last_ok)} geleden`, `${ago(s.last_ok)} ago`) : "–"],
            [L("API-key", "API key"), info.has_api_key ? L("opgeslagen (verborgen)", "stored (hidden)") : "–"]])}
      ${s.last_error ? `<div class="banner err" style="margin-top:16px">${icon("octagon")}<span>${esc(s.last_error)}</span></div>` : ""}
      <div class="wiz-actions" style="margin-top:20px"><button class="btn primary" data-act="change">${live ? L("Koppeling wijzigen", "Change connection") : L("Koppel mijn UniFi-controller", "Connect my UniFi controller")}</button>
      ${live ? `<button class="btn" data-act="demo">${L("Overschakelen naar demodata", "Switch to demo data")}</button>` : ""}</div>`;
  };

  // ---- meldingen versturen
  const KIND = {
    homeassistant: ["Home Assistant", "http://homeassistant.local:8123/api/webhook/unifi-sonar",
      L("Maak in Home Assistant een automatisering met als trigger <b>Webhook</b> (bijv. ID <code>unifi-sonar</code>) en plak hier de webhook-URL. In de automatisering heb je <code>trigger.json.title</code>, <code>.message</code>, <code>.severity</code> en <code>.event</code>.",
        "Create an automation in Home Assistant with a <b>Webhook</b> trigger (e.g. ID <code>unifi-sonar</code>) and paste the webhook URL here. In the automation you have <code>trigger.json.title</code>, <code>.message</code>, <code>.severity</code> and <code>.event</code>.")],
    ntfy: ["ntfy", L("https://ntfy.sh/kies-een-lastig-te-raden-naam", "https://ntfy.sh/pick-a-hard-to-guess-name"),
      L("Installeer de ntfy-app, abonneer je op een topic met een lastig te raden naam en vul die URL hier in. Eigen ntfy-server met login? Vul dan ook een toegangstoken in.",
        "Install the ntfy app, subscribe to a topic with a hard-to-guess name and enter that URL here. Your own ntfy server with login? Then also enter an access token.")],
    discord: ["Discord", "https://discord.com/api/webhooks/…",
      L("In Discord: Serverinstellingen → Integraties → Webhooks → Nieuwe webhook → Webhook-URL kopiëren.", "In Discord: Server Settings → Integrations → Webhooks → New Webhook → Copy Webhook URL.")],
    slack: ["Slack", "https://hooks.slack.com/services/…", L("Maak een <b>Incoming Webhook</b> aan in Slack en plak de URL hier.", "Create an <b>Incoming Webhook</b> in Slack and paste the URL here.")],
    webhook: [L("Eigen webhook", "Custom webhook"), "https://…",
      L("Krijgt een POST met JSON: <code>event</code>, <code>severity</code>, <code>title</code>, <code>message</code>, <code>url</code> en <code>key</code>. Handig voor n8n of Node-RED.",
        "Receives a POST with JSON: <code>event</code>, <code>severity</code>, <code>title</code>, <code>message</code>, <code>url</code> and <code>key</code>. Handy for n8n or Node-RED.")],
  };
  const nfy = { cfg: null, msg: {}, saving: false, banner: null };
  // ---- Home Assistant via MQTT
  async function loadMqtt() {
    let m;
    try { m = await api("/api/mqtt"); } catch (e) { return; }
    const el = $("#set-mqtt");
    if (!el) return;
    const st = m.status || {};
    const stTxt = !m.enabled ? "" : st.connected ? `<span class="badge ok">${icon("check")}${L("Verbonden", "Connected")}${st.last_publish ? L(` · bijgewerkt ${ago(st.last_publish)} geleden`, ` · updated ${ago(st.last_publish)} ago`) : ""}</span>`
      : st.error ? `<span class="badge critical">${icon("octagon")}${esc(st.error)}</span>` : `<span class="badge info">${L("verbinden…", "connecting…")}</span>`;
    const keep = L("opgeslagen (leeg laten = behouden, zolang het adres gelijk blijft)", "stored (leave empty = keep, as long as the address stays the same)");
    const chosen = new Map((m.presence || []).map((d) => [d.mac, d.name]));
    const seen = (state.snap?.clients || []).map((c) => ({ mac: c.mac, name: c.name, sub: c.wired ? L("bedraad", "wired") : c.ssid || "" }));
    const prList = [...seen, ...[...chosen].filter(([mac]) => !seen.some((c) => c.mac === mac)).map(([mac, name]) => ({ mac, name, sub: L("nu niet verbonden", "not connected now") }))]
      .sort((a, b) => (chosen.has(b.mac) - chosen.has(a.mac)) || a.name.localeCompare(b.name));
    const presence = !m.enabled ? "" : `<hr class="sep"><h3 style="margin:0 0 6px">${L("Aanwezigheid", "Presence")}</h3>
      <p class="help" style="margin-top:0">${L("Kies telefoons of andere apparaten: ze verschijnen in Home Assistant als <code>device_tracker</code> (thuis of weg). Zet bij een telefoon het privé-wifiadres op <i>vast</i> voor dit netwerk, anders raakt Sonar hem kwijt.", "Choose phones or other devices: they appear in Home Assistant as a <code>device_tracker</code> (home or away). On a phone, set the private Wi-Fi address to <i>fixed</i> for this network, or Sonar will lose track of it.")}</p>
      <input class="input" id="pr-q" placeholder="${L("Zoek apparaat", "Search device")}" aria-label="${L("Zoek apparaat", "Search device")}">
      <div class="sched-devs" id="pr-list">${prList.map((c) => `<label class="check" data-q="${esc(c.name.toLowerCase())}"><input type="checkbox" data-mac="${esc(c.mac)}" data-name="${esc(c.name)}" ${chosen.has(c.mac) ? "checked" : ""}> ${esc(c.name)} <span class="muted">${esc(c.sub)}</span></label>`).join("")}</div>
      <div class="field" style="margin-top:12px"><label for="pr-grace">${L("Afwezig na", "Away after")}</label><select class="input" id="pr-grace">${[1, 3, 5, 10, 15, 30].map((n) => `<option value="${n * 60}" ${(m.presence_grace || 300) === n * 60 ? "selected" : ""}>${n} ${L(n === 1 ? "minuut" : "minuten", n === 1 ? "minute" : "minutes")}</option>`).join("")}</select>
        <div class="help">${L("Telefoons vallen in slaapstand soms even van de wifi; zo tellen ze dan niet meteen als weg.", "Phones sometimes drop off the Wi-Fi while asleep; this keeps them from counting as away straight away.")}</div></div>
      <div class="wiz-actions" style="margin-top:12px;align-items:center"><button class="btn" data-mq="presence">${L("Aanwezigheid opslaan", "Save presence")}</button><span id="pr-msg"></span></div>`;
    el.innerHTML = `<form class="form-grid" id="mq-form" onsubmit="return false">
        <div class="field" style="grid-column:1/-1"><label class="check"><input type="checkbox" name="enabled" ${m.enabled ? "checked" : ""}> ${L("Koppeling aan", "Integration on")}</label></div>
        <div class="field"><label for="mq-host">Broker</label><input class="input" id="mq-host" name="host" value="${esc(m.host)}" placeholder="${L("bijv. 192.168.1.20 of homeassistant.local", "e.g. 192.168.1.20 or homeassistant.local")}"></div>
        <div class="field"><label for="mq-port">${L("Poort", "Port")}</label><input class="input" id="mq-port" name="port" type="number" min="1" max="65535" value="${esc(m.port)}"></div>
        <div class="field"><label for="mq-user">${L("Gebruikersnaam", "Username")}</label><input class="input" id="mq-user" name="username" autocomplete="off" value="${esc(m.username)}"></div>
        <div class="field"><label for="mq-pw">${L("Wachtwoord", "Password")}</label><input class="input" id="mq-pw" name="password" type="password" autocomplete="new-password" placeholder="${m.has_password ? keep : ""}"></div>
      </form>
      <div class="wiz-actions" style="margin-top:14px;align-items:center"><button class="btn primary" data-mq="save">${L("Opslaan", "Save")}</button><button class="btn" data-mq="test">${L("Verbinding testen", "Test connection")}</button><span id="mq-msg">${stTxt}</span></div>
      <p class="help">${L("Gebruik je de Mosquitto-add-on, maak dan in Home Assistant een gewone gebruiker aan voor Sonar en vul die hier in. Na het opslaan verschijnt <b>UniFi Sonar</b> als apparaat onder Instellingen → Apparaten → MQTT.", "If you use the Mosquitto add-on, create a regular user for Sonar in Home Assistant and enter it here. After saving, <b>UniFi Sonar</b> appears as a device under Settings → Devices → MQTT.")}</p>${presence}`;
    $("#pr-q")?.addEventListener("input", (e) => { const q = e.target.value.trim().toLowerCase(); document.querySelectorAll("#pr-list .check").forEach((l) => { l.hidden = q && !l.dataset.q.includes(q); }); });
    hydrateIcons(el);
  }
  async function mqttAction(act, b) {
    if (act === "presence") {
      const out = $("#pr-msg");
      const devices = [...document.querySelectorAll("#pr-list input:checked")].map((i) => ({ mac: i.dataset.mac, name: i.dataset.name }));
      b.disabled = true;
      try { await post("/api/mqtt/presence", { devices, grace: +$("#pr-grace").value }); out.innerHTML = badge("ok", L("Opgeslagen", "Saved"), "check"); hydrateIcons(out); }
      catch (err) { out.innerHTML = badge("critical", err.message, "octagon"); }
      b.disabled = false;
      return;
    }
    const f = $("#mq-form"), msg = $("#mq-msg");
    const body = { enabled: f.enabled.checked, host: f.host.value, port: +f.port.value || 1883, username: f.username.value, password: f.password.value || null };
    b.disabled = true;
    try {
      if (act === "test") {
        const r = await post("/api/mqtt/test", body);
        msg.innerHTML = r.ok ? `<span class="badge ok">${icon("check")}${L("Broker bereikbaar en inloggen gelukt", "Broker reachable and login succeeded")}</span>` : `<span class="badge critical">${icon("octagon")}${esc(r.error)}</span>`;
      } else {
        await post("/api/mqtt/save", body);
        msg.innerHTML = `<span class="badge ok">${icon("check")}${L("Opgeslagen", "Saved")}</span>`;
        setTimeout(loadMqtt, 3000);
      }
    } catch (err) { msg.innerHTML = `<span class="badge critical">${icon("octagon")}${esc(err.message)}</span>`; }
    b.disabled = false;
  }
  // ---- AdGuard Home
  let agData = null;
  function agRows() {   // wat er nu in het formulier staat
    return [...document.querySelectorAll("#ag-list .ag-row")].map((r) => ({ name: r.querySelector("[name=name]").value, url: r.querySelector("[name=url]").value,
      username: r.querySelector("[name=username]").value, password: r.querySelector("[name=password]").value || null,
      verify_tls: r.querySelector("[name=verify_tls]").checked, has_password: r.dataset.pw === "1" }));
  }
  async function loadAgSettings(rows) {
    if (!rows) { try { agData = await api("/api/adguard"); } catch (e) { return; } rows = agData.settings.instances; }
    const el = $("#set-adguard"); if (!el) return;
    if (!rows.length) rows = [{ name: "", url: "", username: "", has_password: false, verify_tls: false }];
    const st = new Map((agData?.instances || []).map((i) => [i.url, i]));
    const keep = L("opgeslagen (leeg laten = behouden, zolang het adres gelijk blijft)", "stored (leave empty = keep, as long as the address stays the same)");
    el.innerHTML = `<div id="ag-list">${rows.map((r, n) => {
      const s = st.get(r.url && !r.url.includes("://") ? "http://" + r.url : r.url);
      const state = !s || agData?.mock ? "" : s.ok ? badge("ok", `${L("Verbonden", "Connected")}${s.version ? ` · ${s.version}` : ""}`, "check") : s.ok === false ? badge("critical", s.error || L("Fout", "Error"), "octagon") : "";
      return `<div class="ag-row" data-pw="${r.has_password ? 1 : 0}">${n ? `<hr class="sep">` : ""}
        <form class="form-grid" onsubmit="return false">
          <div class="field"><label for="ag-name-${n}">${L("Naam", "Name")}</label><input class="input" id="ag-name-${n}" name="name" value="${esc(r.name || "")}" placeholder="${L("bijv. AdGuard 1", "e.g. AdGuard 1")}"></div>
          <div class="field"><label for="ag-url-${n}">${L("Adres", "Address")}</label><input class="input" id="ag-url-${n}" name="url" value="${esc(r.url || "")}" placeholder="http://192.168.1.10"></div>
          <div class="field"><label for="ag-user-${n}">${L("Gebruikersnaam", "Username")}</label><input class="input" id="ag-user-${n}" name="username" autocomplete="off" value="${esc(r.username || "")}"></div>
          <div class="field"><label for="ag-pw-${n}">${L("Wachtwoord", "Password")}</label><input class="input" id="ag-pw-${n}" name="password" type="password" autocomplete="new-password" placeholder="${r.has_password ? keep : ""}"></div>
          <div class="field" style="grid-column:1/-1"><label class="check"><input type="checkbox" name="verify_tls" ${r.verify_tls ? "checked" : ""}> ${L("Certificaat controleren (alleen bij https met een geldig certificaat)", "Verify certificate (only for https with a valid certificate)")}</label></div>
        </form>
        <div class="wiz-actions" style="margin-top:4px;align-items:center"><button class="btn" data-ag="test" data-n="${n}">${L("Verbinding testen", "Test connection")}</button>${rows.length > 1 ? `<button class="btn ghost" data-ag="remove" data-n="${n}">${L("Verwijderen", "Remove")}</button>` : ""}<span class="ag-msg">${state}</span></div></div>`;
    }).join("")}</div>
      ${rows.length < 4 ? `<div class="wiz-actions" style="margin-top:12px"><button class="btn ghost" data-ag="add">${L("Nog een AdGuard toevoegen", "Add another AdGuard")}</button></div>` : ""}
      <hr class="sep"><label class="check"><input type="checkbox" id="ag-personal" ${agData?.settings.personal ? "checked" : ""}> ${L("Ook domeinen van telefoons, laptops en tablets bewaren", "Also keep domains of phones, laptops and tablets")}</label>
      <p class="help">${L("Standaard bewaart Sonar alleen welke domeinen slimme apparaten en servers opzoeken. Van de andere apparaten telt het alleen hoeveel ze opzoeken, want hun querylog is in feite de browsegeschiedenis van wie ze gebruikt. Per apparaat kun je dit aanpassen in de details van dat apparaat.",
        "By default Sonar only keeps which domains smart devices and servers look up. For other devices it only counts how much they look up, because their query log is in effect the browsing history of whoever uses them. You can change this per device in that device's details.")}</p>
      <div class="wiz-actions" style="margin-top:8px;align-items:center"><button class="btn primary" data-ag="save">${L("Opslaan", "Save")}</button><span id="ag-msg"></span></div>
      <p class="help">${L("AdGuard Home kent geen gebruikers die alleen mogen lezen. Sonar doet alleen leesverzoeken en het wachtwoord blijft op deze machine. Het adres is dat van de beheerpagina van AdGuard, met de poort als die niet 80 of 443 is.",
        "AdGuard Home has no read-only users. Sonar only makes read requests and the password stays on this machine. The address is that of AdGuard's admin page, with the port if it isn't 80 or 443.")}</p>`;
    hydrateIcons(el);
  }
  async function agAction(act, b) {
    const rows = agRows(), n = +b.dataset.n;
    if (act === "add") return loadAgSettings([...rows, { name: "", url: "", username: "", has_password: false, verify_tls: false }]);
    if (act === "remove") return loadAgSettings(rows.filter((_, i) => i !== n));
    b.disabled = true;
    try {
      if (act === "test") {
        const out = b.parentElement.querySelector(".ag-msg");
        const r = await post("/api/adguard/test", rows[n]);
        out.innerHTML = r.ok ? badge("ok", `${L("Inloggen gelukt", "Login succeeded")}${r.version ? ` · ${r.version}` : ""}${r.log ? "" : L(" · querylog is leeg of staat uit", " · query log is empty or off")}`, "check") : badge("critical", r.error, "octagon");
        hydrateIcons(out);
      } else if (act === "save") {
        await post("/api/adguard/settings", { instances: rows.filter((r) => r.url.trim()), personal: $("#ag-personal").checked });
        $("#ag-msg").innerHTML = badge("ok", L("Opgeslagen", "Saved"), "check"); hydrateIcons($("#ag-msg"));
        setTimeout(() => loadAgSettings(), 4000);
      }
    } catch (err) { const m = act === "save" ? $("#ag-msg") : b.parentElement.querySelector(".ag-msg"); m.innerHTML = badge("critical", err.message, "octagon"); hydrateIcons(m); }
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
      : st.error ? `<span class="t-critical">${L("Laatste poging mislukt", "Last attempt failed")}: ${esc(st.error)}</span>`
      : st.ok ? `<span class="muted">${L(`Laatst verstuurd ${ago(st.ok)} geleden`, `Last sent ${ago(st.ok)} ago`)}</span>` : "";
    const keep = L("leeg laten = behouden, zolang het adres gelijk blijft", "leave empty = keep, as long as the address stays the same");
    return `<div class="channel" data-ch="${i}">
      <div class="channel-head"><b>${esc(label)}</b>
        <label class="check" style="margin:0"><input type="checkbox" name="enabled" ${c.enabled !== false ? "checked" : ""}> ${L("Aan", "On")}</label>
        <button type="button" class="linkbtn" data-n="remove" data-i="${i}">${L("Verwijderen", "Remove")}</button></div>
      <div class="form-grid">
        <div class="field"><label for="n-kind-${i}">${L("Soort", "Type")}</label><select class="input" id="n-kind-${i}" name="kind">${Object.entries(KIND).map(([k, v]) => `<option value="${k}" ${k === c.kind ? "selected" : ""}>${v[0]}</option>`).join("")}</select></div>
        <div class="field"><label for="n-sev-${i}">${L("Vanaf", "From")}</label><select class="input" id="n-sev-${i}" name="sev">${[["critical", L("Alleen kritiek", "Critical only")], ["warning", L("Waarschuwing en kritiek", "Warning and critical")], ["info", L("Alles, ook info", "Everything, including info")]].map(([k, l]) => `<option value="${k}" ${k === (c.min_severity || "warning") ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      </div>
      <div class="field"><label for="n-url-${i}">${L("Webhook-adres", "Webhook address")}</label><input class="input" id="n-url-${i}" name="url" autocomplete="off" spellcheck="false" value="${esc(c.url || "")}" placeholder="${esc(c.url_masked ? `${c.url_masked}  (${keep})` : ph)}">
        <div class="help">${help}</div></div>
      ${c.kind === "ntfy" ? `<div class="field"><label for="n-tok-${i}">${L("Toegangstoken (optioneel)", "Access token (optional)")}</label><input class="input" id="n-tok-${i}" name="token" type="password" autocomplete="off" placeholder="${c.has_token ? `${L("opgeslagen", "stored")} (${keep})` : "tk_…"}"></div>` : ""}
      <label class="check"><input type="checkbox" name="resolved" ${c.resolved !== false ? "checked" : ""}> ${L("Ook een bericht als het weer is opgelost", "Also send a message when it is resolved")}</label>
      <div class="channel-foot"><button type="button" class="btn" data-n="test" data-i="${i}">${L("Testbericht sturen", "Send test message")}</button>${stat}</div>
    </div>`;
  }
  function renderNotify() {
    const root = $("#set-notify");
    if (!root) return;
    if (!nfy.cfg) { root.innerHTML = `<p class="muted">${L("Beschikbaar zodra UniFi Sonar is gekoppeld.", "Available once UniFi Sonar is connected.")}</p>`; return; }
    const c = nfy.cfg;
    root.innerHTML = `
      ${c.channels.length ? c.channels.map(channelHTML).join("") : `<p class="muted">${L("Nog geen kanalen. Voeg er een toe om meldingen te krijgen.", "No channels yet. Add one to get notifications.")}</p>`}
      <div class="wiz-actions" style="margin-top:12px"><button type="button" class="btn" data-n="add" ${c.channels.length >= 5 ? "disabled" : ""}>${L("Kanaal toevoegen", "Add channel")}</button></div>
      <div class="form-grid" style="margin-top:8px">
        <div class="field"><label for="n-delay">${L("Pas melden na", "Notify only after")}</label><select class="input" id="n-delay">${[0, 2, 5, 10, 15, 30].map((m) => `<option value="${m}" ${m === c.delay_min ? "selected" : ""}>${m ? `${m} ${L("minuten", "minutes")}` : L("direct", "immediately")}</option>`).join("")}</select>
          <div class="help">${L("Een probleem moet zo lang aanhouden; voorkomt berichten bij één uitschieter.", "A problem has to last this long; prevents messages for a single spike.")}</div></div>
        <div class="field"><label for="n-digest">${L("Dagoverzicht", "Daily summary")}</label><select class="input" id="n-digest"><option value="">${L("Uit", "Off")}</option>${[6, 7, 8, 9, 12, 17, 18, 19, 20, 21].map((h) => `<option value="${h}" ${h === c.digest_hour ? "selected" : ""}>${L("Elke dag om", "Every day at")} ${String(h).padStart(2, "0")}:00</option>`).join("")}</select>
          <div class="help">${L("Eén bericht met de netwerkscore en alle open meldingen.", "One message with the network score and all open issues.")}</div></div>
      </div>
      <div class="field"><label for="n-base">${L("Adres van dit dashboard", "Address of this dashboard")}</label><input class="input" id="n-base" value="${esc(c.base_url || "")}" spellcheck="false"><div class="help">${L("Voor de link in elk bericht.", "For the link in each message.")}</div></div>
      ${nfy.banner ? `<div class="banner ${nfy.banner.ok ? "" : "err"}" role="status" style="margin-top:16px">${icon(nfy.banner.ok ? "check" : "octagon")}<span>${esc(nfy.banner.text)}</span></div>` : ""}
      <div class="wiz-actions"><button type="button" class="btn primary" data-n="save" ${nfy.saving ? "disabled" : ""}>${nfy.saving ? L("Opslaan…", "Saving…") : L("Meldingen opslaan", "Save notifications")}</button></div>`;
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
      b.disabled = true; b.textContent = L("Versturen…", "Sending…");
      try { await post("/api/notify/test", { channel: chBody(nfy.cfg.channels[i]), base_url: nfy.cfg.base_url }); nfy.msg[i] = { ok: true, text: L("Verstuurd, kijk of het aankomt.", "Sent, check whether it arrives.") }; }
      catch (err) { nfy.msg[i] = { ok: false, text: err.message }; }
    }
    if (act === "save") {
      nfy.saving = true; renderNotify();
      try {
        await post("/api/notify/save", { channels: nfy.cfg.channels.map(chBody), delay_min: nfy.cfg.delay_min, digest_hour: nfy.cfg.digest_hour, base_url: nfy.cfg.base_url });
        nfy.cfg = await api("/api/notify"); nfy.msg = {};
        nfy.banner = { ok: true, text: L("Opgeslagen. Wat nu al openstaat wordt niet alsnog verstuurd; nieuwe problemen wel.", "Saved. What is already open now won't be sent afterwards; new problems will.") };
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
    const [a, au] = await Promise.all([api("/api/access").catch(() => null), api("/api/auth/state").catch(() => null)]);
    if (!a) { root.innerHTML = `<p class="muted">${L("Niet beschikbaar.", "Not available.")}</p>`; return; }
    const pw = (id, label, ac) => `<div class="field"><label for="${id}">${label}</label><input class="input" id="${id}" type="password" autocomplete="${ac}"></div>`;
    const [pks, ss, tls] = await Promise.all([au?.enabled ? api("/api/auth/passkeys").catch(() => null) : null,
      au?.enabled ? api("/api/auth/sessions").catch(() => null) : null, api("/api/tls").catch(() => null)]);
    const others = (ss?.rows || []).filter((r) => !r.current).length;
    const ssSection = !ss ? "" : `<hr class="sep"><h3 style="margin:0 0 6px">${L("Ingelogde apparaten", "Logged-in devices")}</h3>
      <p class="help" style="margin-top:0">${L("Herken je er een niet, of ben je een apparaat kwijt? Log het dan hier uit.", "Don't recognise one, or lost a device? Log it out here.")}</p>
      <div class="bk-list">${ss.rows.map((r) => `<div class="bk-row"><div class="bk-main"><div>${esc(r.agent || L("Onbekend apparaat", "Unknown device"))}</div><div class="cell-sub">${L("ingelogd", "logged in")} ${dateTxt(r.created, true)} · ${L("laatst vernieuwd", "last renewed")} ${dateTxt(r.last_seen, true)}</div></div>${r.current ? badge("ok", L("deze browser", "this browser")) : `<button type="button" class="btn" data-ss-rev="${esc(r.id)}">${L("Uitloggen", "Log out")}</button>`}</div>`).join("")}</div>
      ${others > 1 ? `<div class="wiz-actions"><button type="button" class="btn" id="ss-all">${L("Alle andere apparaten uitloggen", "Log out all other devices")}</button></div>` : ""}`;
    const tlsTrust = `<form class="form-grid" onsubmit="return false" style="margin-top:12px">${pw("tls-pw", L("Huidig wachtwoord", "Current password"), "current-password")}</form><div id="tls-msg" role="status"></div><div class="wiz-actions"><button type="button" class="btn" id="tls-trust">${L("Dit certificaat vertrouwen", "Trust this certificate")}</button></div>`;
    const fpRow = (label, fp) => `<div class="tls-fp"><div class="cell-sub">${label}</div><code>${esc(fp)}</code></div>`;
    const tlsSection = !tls || !["ca", "pinned", "expired", "unpinned"].includes(tls.mode) ? "" : `<hr class="sep"><h3 style="margin:0 0 6px">${L("Certificaat van de controller", "Controller certificate")}</h3>
      ${tls.mode === "ca" ? `<p class="help" style="margin-top:0">${L("Sonar controleert het certificaat van je controller via een officiële certificaatuitgever.", "Sonar verifies your controller's certificate through an official certificate authority.")}</p>`
      : tls.mode === "unpinned" ? `<p class="help" style="margin-top:0">${L("Sonar legt het certificaat vast bij de volgende verbinding met je controller.", "Sonar will pin the certificate on the next connection to your controller.")}</p>`
      : `${tls.changed ? `<div class="banner err">${icon("octagon")}<span>${L("Je controller laat een ander certificaat zien. Sonar stuurt zijn sleutel daar niet heen. Heb je zelf de controller vervangen of het certificaat vernieuwd? Dan kun je het nieuwe hieronder vertrouwen. Zo niet, kijk dan eerst wat er aan de hand is.", "Your controller presents a different certificate. Sonar will not send its key there. Did you replace the controller or renew the certificate yourself? Then you can trust the new one below. If not, find out what is going on first.")}</span></div>` : tls.mode === "expired" ? `<div class="banner err">${icon("octagon")}<span>${L("Het vastgelegde certificaat is verlopen, dus Sonar kan de controller nu niet controleren. Vernieuw het certificaat in UniFi en vertrouw daarna het nieuwe.", "The pinned certificate has expired, so Sonar cannot verify the controller right now. Renew the certificate in UniFi and then trust the new one.")}</span></div>` : `<p class="help" style="margin-top:0">${L("Sonar stuurt zijn sleutel alleen naar de controller als die precies dit certificaat laat zien.", "Sonar only sends its key to the controller if it presents exactly this certificate.")}</p>`}
        ${fpRow(L("Vastgelegd", "Pinned"), tls.fingerprint)}${tls.changed ? fpRow(L("Nu getoond door de controller", "Now presented by the controller"), tls.presented) : ""}
        ${tls.changed || tls.mode === "expired" ? tlsTrust : ""}`}`;
    const pkOk = passkeyPossible();
    const pkSection = !au?.enabled ? "" : `<hr class="sep"><h3 style="margin:0 0 6px">Passkeys</h3>
      <p class="help" style="margin-top:0">${L("Inloggen met je vingerafdruk, gezicht of beveiligingssleutel in plaats van je wachtwoord. Dit is een keuze: je wachtwoord blijft altijd werken.", "Log in with your fingerprint, face or security key instead of your password. This is optional: your password always keeps working.")}</p>
      ${(pks?.rows || []).length ? `<div class="bk-list" style="margin-bottom:12px">${pks.rows.map((p) => `<div class="bk-row"><div class="bk-main"><div>${esc(p.name)}</div><div class="cell-sub">${L("toegevoegd", "added")} ${dateTxt(p.created, true)}${p.last_used ? ` · ${L("laatst gebruikt", "last used")} ${dateTxt(p.last_used, true)}` : ""}${p.here ? "" : ` · ${L("hoort bij een andere hostnaam", "belongs to another host name")}`}</div></div><button type="button" class="btn" data-pk-del="${esc(p.id)}">${L("Verwijderen", "Remove")}</button></div>`).join("")}</div>` : ""}
      ${pkOk ? `<form class="form-grid" onsubmit="return false"><div class="field"><label for="pk-name">${L("Naam van dit apparaat", "Name of this device")}</label><input class="input" id="pk-name" maxlength="60" placeholder="${L("bijv. iPhone", "e.g. iPhone")}"></div>${pw("pk-pw", L("Huidig wachtwoord", "Current password"), "current-password")}</form>
        <div id="pk-msg" role="status"></div><div class="wiz-actions"><button type="button" class="btn" id="pk-add">${L("Passkey toevoegen", "Add a passkey")}</button></div>`
      : `<div class="banner">${icon("info")}<span>${L("Passkeys werken alleen via HTTPS met een hostnaam. Open Sonar via zo'n adres om er een toe te voegen.", "Passkeys only work over HTTPS with a host name. Open Sonar via such an address to add one.")}</span></div>`}`;
    root.innerHTML = `<h3 style="margin:0 0 6px">${L("Inlog", "Login")} ${au?.enabled ? badge("ok", L("aan", "on"), "check") : badge("warning", L("uit", "off"))}</h3>
      <p class="help" style="margin-top:0">${au?.enabled ? L("Je hebt het wachtwoord nodig om het dashboard te zien en te bedienen.", "You need the password to see and operate the dashboard.") : L("Zonder inlog kan iedereen op je netwerk die het adres kent meekijken en apparaten pauzeren. Stel een wachtwoord in om dat te voorkomen.", "Without a login, anyone on your network who knows the address can look around and pause devices. Set a password to prevent that.")}</p>
      <form class="form-grid" id="au-form" onsubmit="return false">
        ${au?.enabled ? pw("au-cur", L("Huidig wachtwoord", "Current password"), "current-password") : ""}
        ${pw("au-new", au?.enabled ? L("Nieuw wachtwoord", "New password") : L("Wachtwoord", "Password"), "new-password")}
        ${pw("au-rep", L("Herhaal wachtwoord", "Repeat password"), "new-password")}
      </form>
      <div id="au-msg" role="status"></div>
      <div class="wiz-actions"><button type="button" class="btn primary" id="au-save">${au?.enabled ? L("Wachtwoord wijzigen", "Change password") : L("Inlog aanzetten", "Turn on login")}</button>
        ${au?.enabled && au.optional ? `<button type="button" class="btn" id="au-off">${L("Inlog uitzetten", "Turn off login")}</button>` : ""}${au?.enabled ? `<button type="button" class="btn" id="au-out">${L("Uitloggen", "Log out")}</button>` : ""}</div>
      <p class="help">${L("Wachtwoord kwijt? Zie <i>Privacy en veiligheid</i> in de README.", "Forgot the password? See <i>Privacy and security</i> in the README.")}${au?.enabled && au.optional ? ` ${L("Zet je de inlog uit, dan vervallen ook je passkeys.", "If you turn off the login, your passkeys are removed too.")}` : ""}</p>
      ${pkSection}${ssSection}${tlsSection}
      <hr class="sep">
      <p class="help">${L("Het dashboard werkt via een IP-adres, <code>localhost</code> en lokale namen zoals <code>sonar.local</code> of <code>sonar.lan</code>. Andere hostnamen worden geweigerd, zodat een website in je browser het dashboard niet stiekem kan aansturen (DNS-rebinding). Gebruik je een eigen naam of een reverse proxy, zet die hieronder.", "The dashboard works via an IP address, <code>localhost</code> and local names such as <code>sonar.local</code> or <code>sonar.lan</code>. Other host names are refused, so a website in your browser cannot secretly control the dashboard (DNS rebinding). If you use your own name or a reverse proxy, add it below.")}</p>
      <div class="field"><label for="a-hosts">${L("Extra hostnamen", "Extra host names")}</label><input class="input" id="a-hosts" spellcheck="false" placeholder="${L("sonar.mijndomein.nl", "sonar.mydomain.com")}, sonar.tailnet.ts.net" value="${esc((a.allowed_hosts || []).join(", "))}">
        <div class="help">${L("Gescheiden door komma's, precies zoals in de adresbalk.", "Separated by commas, exactly as in the address bar.")}${a.env_hosts.length ? ` ${L("Al toegestaan via de service", "Already allowed via the service")}: <code>${esc(a.env_hosts.join(", "))}</code>.` : ""} ${L("Je bent nu verbonden via", "You are now connected via")} <code>${esc(a.current_host)}</code>.</div></div>
      ${msg ? `<div class="banner ${msg.ok ? "" : "err"}" role="status" style="margin-top:16px">${icon(msg.ok ? "check" : "octagon")}<span>${esc(msg.text)}</span></div>` : ""}
      <div class="wiz-actions"><button type="button" class="btn" id="a-save">${L("Opslaan", "Save")}</button></div>`;
    const auMsg = (ok, text) => { $("#au-msg").innerHTML = `<div class="banner ${ok ? "" : "err"}" style="margin-top:12px">${icon(ok ? "check" : "octagon")}<span>${esc(text)}</span></div>`; };
    $("#au-save").onclick = async () => {
      const nw = $("#au-new").value;
      if (nw !== $("#au-rep").value) return auMsg(false, L("De twee wachtwoorden zijn niet gelijk.", "The two passwords do not match."));
      try { await post("/api/auth/password", { current: $("#au-cur")?.value || "", new: nw }); loadAccess({ ok: true, text: L("Wachtwoord opgeslagen. Deze browser blijft ingelogd.", "Password saved. This browser stays logged in.") }); }
      catch (err) { auMsg(false, err.message); }
    };
    if ($("#au-off")) $("#au-off").onclick = async () => {
      try { await post("/api/auth/disable", { password: $("#au-cur").value }); loadAccess({ ok: true, text: L("Inlog uitgezet.", "Login turned off.") }); }
      catch (err) { auMsg(false, err.message); }
    };
    if ($("#pk-add")) $("#pk-add").onclick = async () => {
      const b = $("#pk-add"), out = (ok, text) => { $("#pk-msg").innerHTML = `<div class="banner ${ok ? "" : "err"}" style="margin-top:12px">${icon(ok ? "check" : "octagon")}<span>${esc(text)}</span></div>`; };
      b.disabled = true;
      try { await passkeyAdd($("#pk-name").value, $("#pk-pw").value); loadAccess({ ok: true, text: L("Passkey toegevoegd.", "Passkey added.") }); }
      catch (e) { out(false, passkeyError(e)); b.disabled = false; }
    };
    root.querySelectorAll("[data-pk-del]").forEach((b) => { b.onclick = async () => {
      try { await post("/api/auth/passkey/delete", { id: b.dataset.pkDel }); loadAccess({ ok: true, text: L("Passkey verwijderd.", "Passkey removed.") }); }
      catch (e) { auMsg(false, e.message); }
    }; });
    if ($("#au-out")) $("#au-out").onclick = async () => { await post("/api/auth/logout", {}).catch(() => {}); showLogin(); };
    const revoke = async (id, text) => {
      try { await post("/api/auth/sessions/revoke", { id }); loadAccess({ ok: true, text }); }
      catch (e) { auMsg(false, e.message); }
    };
    root.querySelectorAll("[data-ss-rev]").forEach((b) => { b.onclick = () => revoke(b.dataset.ssRev, L("Dat apparaat is uitgelogd.", "That device has been logged out.")); });
    if ($("#ss-all")) $("#ss-all").onclick = () => revoke(null, L("Alle andere apparaten zijn uitgelogd.", "All other devices have been logged out."));
    if ($("#tls-trust")) $("#tls-trust").onclick = async () => {
      try { await post("/api/tls/trust", { password: $("#tls-pw").value }); loadAccess({ ok: true, text: L("Nieuw certificaat vastgelegd.", "New certificate pinned.") }); }
      catch (e) { $("#tls-msg").innerHTML = `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(e.message)}</span></div>`; }
    };
    $("#a-save").onclick = async () => {
      const hosts = $("#a-hosts").value.split(/[,\s]+/).map((h) => h.trim()).filter(Boolean);
      try { await post("/api/access", { allowed_hosts: hosts }); loadAccess({ ok: true, text: L("Opgeslagen.", "Saved.") }); }
      catch (err) { loadAccess({ ok: false, text: err.message }); }
    };
  }

  // ---- UniFi-backups
  async function loadBackups(msg, recovery) {
    const root = $("#set-backups");
    if (!root) return;
    const b = await api("/api/backups").catch(() => null);
    if (!b) { root.innerHTML = `<p class="muted">${L("Niet beschikbaar.", "Not available.")}</p>`; return; }
    const row = (f) => `<div class="bk-row"><div class="bk-main"><div>${dateTxt(f.ts, true)}</div><div class="cell-sub">${f.source === "sonar" ? L("gemaakt door Sonar", "made by Sonar") : L("automatische backup van UniFi", "automatic UniFi backup")} · ${bytes(f.size)}</div></div>
      ${b.can_download ? `<button type="button" class="btn" data-bk-dl="${esc(f.name)}">${L("Download", "Download")}</button>` : ""}</div>`;
    root.innerHTML = `<p class="help" style="margin-top:-4px">${L("Sonar bewaart een kopie van de backups van je controller, zodat je er nog bij kunt als de controller crasht. Terugzetten doe je bij het opzetten van een nieuwe controller, of in UniFi onder Instellingen → Systeem → Backups.", "Sonar keeps a copy of your controller's backups, so you can still reach them if the controller crashes. You restore one while setting up a new controller, or in UniFi under Settings → System → Backups.")}</p>
      ${b.error ? `<div class="banner err" style="margin-bottom:12px">${icon("octagon")}<span>${esc(b.error)}</span></div>` : ""}
      ${msg ? `<div class="banner" role="status" style="margin-bottom:12px">${icon("check")}<span>${esc(msg)}</span></div>` : ""}
      ${recovery ? recoveryHTML(recovery) : ""}
      ${!b.encrypted && b.can_download ? `<div class="banner" style="margin-bottom:12px">${icon("alert")}<span>${L("Je backups staan nog onversleuteld op deze machine, met daarin je wifi-wachtwoorden. Vul je wachtwoord in om ze te versleutelen. Je krijgt dan één keer een herstelcode te zien.", "Your backups are still unencrypted on this machine, including your Wi-Fi passwords. Enter your password to encrypt them. You will be shown a recovery code once.")}</span></div>
        <form class="form-grid" onsubmit="return false"><div class="field"><label for="bk-enc-pw">${L("Huidig wachtwoord", "Current password")}</label><input class="input" id="bk-enc-pw" type="password" autocomplete="current-password"></div></form>
        <div id="bk-enc-msg" role="status"></div><div class="wiz-actions" style="margin-bottom:16px"><button type="button" class="btn primary" id="bk-enc">${L("Backups versleutelen", "Encrypt backups")}</button></div>` : ""}
      <label class="check"><input type="checkbox" id="bk-daily" ${b.daily ? "checked" : ""}> ${L("Elke dag een verse backup laten maken", "Have a fresh backup made every day")}</label>
      <div class="help">${L("UniFi maakt automatische backups soms maar eens per maand. Met deze optie vraagt Sonar de controller elke dag om een backup van de instellingen.", "UniFi sometimes makes automatic backups only once a month. With this option Sonar asks the controller every day for a backup of the settings.")}</div>
      ${b.files.length ? `<div class="bk-list">${b.files.slice(0, 6).map(row).join("")}</div>${b.files.length > 6 ? `<p class="muted" style="font-size:13px">${L(`en nog ${b.files.length - 6}; Sonar bewaart de nieuwste ${b.keep}`, `and ${b.files.length - 6} more; Sonar keeps the newest ${b.keep}`)}</p>` : ""}` : `<p class="muted">${L("Nog geen backups opgehaald.", "No backups fetched yet.")}</p>`}
      ${b.can_download && b.encrypted && b.files.length ? `<form class="form-grid" onsubmit="return false" style="margin-top:12px"><div class="field"><label for="bk-secret">${L("Wachtwoord of herstelcode", "Password or recovery code")}</label><input class="input" id="bk-secret" type="password" autocomplete="off"><div class="help">${L("Nodig om een backup te downloaden: Sonar kan ze zonder jou niet openen.", "Needed to download a backup: Sonar cannot open them without you.")}</div></div></form>` : ""}
      <div id="bk-dl-msg" role="alert"></div>
      ${b.can_download ? "" : `<div class="banner" style="margin-top:12px">${icon("info")}<span>${L("Een backup bevat ook je wifi-wachtwoorden. Downloaden kan daarom pas als de inlog aanstaat (zie Toegang).", "A backup also contains your Wi-Fi passwords. You can therefore only download one once the login is on (see Access).")}</span></div>`}
      <div class="wiz-actions"><button type="button" class="btn" id="bk-run">${L("Nu een backup maken", "Make a backup now")}</button></div>`;
    hydrateIcons(root);
    root.querySelectorAll("[data-bk-dl]").forEach((btn) => { btn.onclick = async () => {
      const out = $("#bk-dl-msg"), name = btn.dataset.bkDl;
      out.innerHTML = "";
      btn.disabled = true;
      try {
        const r = await fetch("/api/backups/download", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name, secret: $("#bk-secret")?.value || "" }) });
        if (r.status === 401) throw needLogin();
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
        const url = URL.createObjectURL(await r.blob()), a = document.createElement("a");
        a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 10000);
      } catch (e) { out.innerHTML = `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(e.message)}</span></div>`; }
      btn.disabled = false;
    }; });
    if ($("#bk-enc")) $("#bk-enc").onclick = async (e) => {
      e.target.disabled = true;
      try {
        const r = await post("/api/backups/encrypt", { password: $("#bk-enc-pw").value });
        loadBackups(L(`${r.encrypted} bestaande ${r.encrypted === 1 ? "backup" : "backups"} versleuteld.`, `${r.encrypted} existing ${r.encrypted === 1 ? "backup" : "backups"} encrypted.`), r.recovery_code);
      } catch (err) { $("#bk-enc-msg").innerHTML = `<div class="banner err" style="margin-top:12px">${icon("octagon")}<span>${esc(err.message)}</span></div>`; e.target.disabled = false; }
    };
    $("#bk-daily").onchange = async (e) => { await post("/api/backups/settings", { daily: e.target.checked }).catch(() => {}); };
    $("#bk-run").onclick = async (e) => {
      e.target.disabled = true; e.target.textContent = L("Bezig…", "Working…");
      try { await post("/api/backups/run", {}); loadBackups(L("Backup gemaakt en opgeslagen.", "Backup made and stored.")); }
      catch (err) { loadBackups(); }
    };
  }

  // ---- probleemoplossing
  async function loadDebug() {
    const root = $("#set-debug");
    if (!root) return;
    const d = await api("/api/debug").catch((e) => ({ text: L("Kon geen debug-info ophalen: ", "Could not fetch debug info: ") + e.message }));
    root.innerHTML = `<p class="help" style="margin-top:-4px">${L("Werkt er iets niet? Kopieer deze gegevens en plak ze in een issue op GitHub. IP-adressen, namen, MAC-adressen en sleutels zijn eruit gehaald.", "Something not working? Copy this info and paste it into an issue on GitHub. IP addresses, names, MAC addresses and keys have been removed.")}</p>
      <pre class="debug" id="dbg-text" tabindex="0">${esc(d.text)}</pre>
      <div class="wiz-actions" style="margin-top:12px"><button type="button" class="btn" id="dbg-copy">${L("Debug-info kopiëren", "Copy debug info")}</button><button type="button" class="btn ghost" id="dbg-reload">${L("Vernieuwen", "Refresh")}</button><span class="muted" id="dbg-msg" role="status"></span></div>`;
    $("#dbg-reload").onclick = loadDebug;
    $("#dbg-copy").onclick = async () => {
      const text = $("#dbg-text").textContent;
      try { await navigator.clipboard.writeText(text); $("#dbg-msg").textContent = L("Gekopieerd.", "Copied."); }
      catch {   // geen clipboard-API (http): selecteer de tekst zodat ⌘C/Ctrl+C werkt
        const r = document.createRange(); r.selectNodeContents($("#dbg-text"));
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
        $("#dbg-msg").textContent = L("Geselecteerd: druk op Ctrl+C of ⌘C.", "Selected: press Ctrl+C or ⌘C.");
      }
    };
  }

  // ------------------------------------------------------------------ tijdlijn
  const EV = {
    device_offline: ["octagon", "bad"], device_online: ["check", "good"], device_reboot: ["power", "bad"], device_upgrade: ["check", "good"],
    port_down: ["plug", "bad"], port_up: ["plug", "good"], roam: ["roam", "roam"], client_join: ["wifi", "good"], client_leave: ["wifi", ""],
    config: ["settings", "cfg"], wan_ip: ["globe", "cfg"],
  };
  const EKIND = { all: null, config: ["config"], device: ["device_offline", "device_online", "device_reboot", "device_upgrade"], port: ["port_down", "port_up"], roam: ["roam"], client: ["client_join", "client_leave"] };
  // Een apparaat dat steeds tussen dezelfde twee access points wisselt, vult anders de hele tijdlijn: vanaf drie keer
  // op één dag wordt het één regel, met de losse wissels erachter.
  const GROUP_MIN = 3;
  function roamGroups(evts) {
    const dayOf = (e) => new Date(e.ts * 1000).toDateString();
    const groups = new Map();
    evts.forEach((e) => {
      if (e.kind !== "roam") return;
      const m = /^(.*): (.+) → (.+)$/.exec(e.message || "");
      if (!m) return;
      const key = `tl:${dayOf(e)}|${e.entity_id || m[1]}|${[m[2], m[3]].sort().join("|")}`;
      const g = groups.get(key) || { key, who: m[1], aps: [m[2], m[3]].sort(), items: [] };
      g.items.push(e);
      groups.set(key, g);
      e._g = g;
    });
    groups.forEach((g) => { if (g.items.length < GROUP_MIN) g.items.forEach((e) => { delete e._g; }); });
  }
  function eventsHTML(evts, group) {
    let day = "", out = "";
    if (group) roamGroups(evts);
    const row = (e, sub) => {
      const [ic, cls] = EV[e.kind] || ["activity", ""];
      return `<div class="event${sub ? " sub" : ""}"><span class="time">${hhmm(e.ts)}</span><span class="eico ${cls}">${icon(ic)}</span><span>${esc(e.message)}</span></div>`;
    };
    evts.forEach((e) => {
      const d = new Date(e.ts * 1000).toLocaleDateString(LOC, { weekday: "long", day: "numeric", month: "long" });
      if (d !== day) { out += `<div class="day">${d}</div>`; day = d; }
      const g = e._g;
      if (!g) { out += row(e); return; }
      if (g.items[0] !== e) return;            // de groep staat bij zijn nieuwste wissel
      const open = state.expanded.has(g.key), n = g.items.length, first = g.items[n - 1].ts;
      out += `<div class="event grp"><span class="time">${hhmm(e.ts)}</span><span class="eico roam">${icon("roam")}</span>
        <span>${esc(L(`${g.who} wisselde ${n}× tussen ${g.aps[0]} en ${g.aps[1]}, sinds ${hhmm(first)}`, `${g.who} switched ${n}× between ${g.aps[0]} and ${g.aps[1]}, since ${hhmm(first)}`))}
        <button class="toggle" aria-expanded="${open}" data-expand="${esc(g.key)}">${icon("chevron")}${open ? L("Verberg", "Hide") : L("Toon alle", "Show all")}</button></span></div>`;
      if (open) out += g.items.map((x) => row(x, true)).join("");
    });
    return out || `<div class="empty">${L("Geen gebeurtenissen in deze periode", "No events in this period")}</div>`;
  }
  let tlEvents = [];
  function mountTimeline() {
    mount("tijdlijn", `
      <div class="page-head"><div><h1>${L("Tijdlijn", "Timeline")}</h1><p class="subtitle">${L("Wat er in je netwerk gebeurde: herstarts, links die wegvallen, roaming en clients die komen en gaan.", "What happened in your network: restarts, links dropping, roaming and clients coming and going.")}</p></div>${rangeSeg("tl-range")}</div>
      <div class="toolbar"><div class="chips" role="group" aria-label="${L("Soort", "Type")}" id="tl-kind">${[["all", L("Alles", "All")], ["config", L("Instellingen", "Settings")], ["device", L("Apparaten", "Devices")], ["port", L("Poorten", "Ports")], ["roam", "Roaming"], ["client", "Clients"]].map(([v, l]) => `<button class="chip" data-k="${v}" aria-pressed="${state.ekind === v}">${l}</button>`).join("")}</div></div>
      <div class="card"><div class="events" id="tl-list"></div></div>`);
    bindRange("tl-range", UPDATERS.tijdlijn);
    $("#tl-list").addEventListener("click", (e) => {
      const x = e.target.closest("[data-expand]"); if (!x) return;
      const k = x.dataset.expand; state.expanded.has(k) ? state.expanded.delete(k) : state.expanded.add(k);
      $("#tl-list").innerHTML = eventsHTML(tlEvents, true);
      hydrateIcons($("#tl-list"));
    });
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
    tlEvents = kinds ? evts.filter((e) => kinds.includes(e.kind)) : evts;
    $("#tl-list").innerHTML = eventsHTML(tlEvents, true);
    hydrateIcons($("#tl-list"));
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
    if (type !== "blocked") history.replaceState(null, "", `#/${current}/${encodeURIComponent(id)}`);   // deelbare link
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
    if (type === "blocked") return renderBlockedDrawer();
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
    const up = d.uplink_mac ? `${esc(dm[d.uplink_mac]?.name || d.uplink_mac)}${d.uplink_port ? ` · ${L("poort", "port")} ${d.uplink_port}` : ""}` : "–";
    let body = kv([
      ["Status", d.state === "online" ? badge("ok", "Online", "check") : badge("critical", d.state, "octagon")],
      ["Firmware", `${esc(d.version)}${d.upgradable ? ` ${badge("info", "update " + (d.upgrade_to || ""))}` : ""}`],
      ["Uptime", dur(d.uptime)], ["CPU", `${nf(d.cpu)}%`], [L("Geheugen", "Memory"), `${nf(d.mem)}%`], [L("Temperatuur", "Temperature"), d.temp == null ? "–" : `${nf(d.temp)} °C`],
      ["Clients", d.num_clients], ["Uplink", up], ["Score", `${d.score}/100`],
    ]);
    body = `<div class="card">${body}</div>` + relatedIssues((i) => i.device_mac === d.mac && !i.client_mac && !i.group);
    if (d.client_issue_count) body += `<div class="banner">${icon("users")}<span>${L(`${d.client_issue_count} meldingen bij clients op dit apparaat.`, `${d.client_issue_count} issues with clients on this device.`)} <button class="linkbtn" id="dr-goclients">${L("Bekijk deze clients", "View these clients")}</button></span></div>`;
    if (d.type === "gateway") {
      const w = state.snap.wan;
      body += `<div class="card"><h3 style="margin-bottom:12px">Internet</h3>${kv([["Provider", esc(w.isp || "–")], ["WAN-IP", esc(w.wan_ip || "–")], ["Latency", `${nf(w.latency_ms)} ms`], [L("Pakketverlies", "Packet loss"), `${nf(w.loss_pct, 1)}%`], ["Download (test)", `${nf(w.xput_down)} Mbit/s`], ["Upload (test)", `${nf(w.xput_up)} Mbit/s`]])}</div>`;
    }
    if (d.radios.length) {
      body += `<div class="card"><h3 style="margin-bottom:12px">${L("Radio's", "Radios")}</h3><div class="table-wrap" style="border:0"><table><thead><tr><th>Band</th><th class="r">${L("Kanaal", "Channel")}</th><th class="r">Clients</th><th>${L("Bezetting", "Utilization")}</th><th class="r">${L("Storing", "Interference")}</th><th class="r">Retries</th><th class="r">${L("Ervaring", "Experience")}</th></tr></thead><tbody>
        ${d.radios.map((r) => { const lv = level("cu", r.cu_total); return `<tr style="cursor:default"><td><b>${r.radio} GHz</b><div class="cell-sub">${r.width ? r.width + " MHz" : ""}${r.tx_power ? ` · ${r.tx_power} dBm` : ""}</div></td><td class="r num">${r.channel ?? "–"}</td><td class="r num">${r.num_clients}</td>
          <td><div style="display:flex;gap:8px;align-items:center">${meter(r.cu_total, lv)}<span class="num ${lv !== "ok" ? "t-" + lv : ""}">${nf(r.cu_total)}%</span></div></td>
          <td class="r num">${nf(r.interference)}%</td><td class="r num">${nf(r.retry_pct, 1)}%</td><td class="r num">${nf(r.satisfaction)}</td></tr>`; }).join("")}
        </tbody></table></div></div>
        <div class="card"><div class="card-head"><h3>${L("Kanaalbezetting per band", "Channel utilization per band")}</h3>${rangeSeg("dr-range")}</div><div id="dr-ch-cu"></div></div>
        <div class="card"><div class="card-head"><h3>${L("Retries per band", "Retries per band")}</h3></div><div id="dr-ch-rt"></div></div>
        <div class="card"><div class="card-head"><h3>${L("Drukte per uur van de week", "Busyness per hour of the week")}</h3><span class="muted">${L("afgelopen 7 dagen", "past 7 days")}</span></div>
          <div class="toolbar" style="margin-bottom:12px"><div class="seg" role="group" aria-label="Band" id="dr-hm-band">${d.radios.map((r) => `<button data-b="${r.radio}" aria-pressed="${r.radio === (hm.mac === d.mac ? hm.band : d.radios[0].radio)}">${r.radio} GHz</button>`).join("")}</div>
          <div class="seg" role="group" aria-label="${L("Meting", "Metric")}" id="dr-hm-metric">${[["cu", L("Bezetting", "Utilization")], ["interference", L("Storing", "Interference")], ["clients", "Clients"]].map(([k, l]) => `<button data-m="${k}" aria-pressed="${k === hm.metric}">${l}</button>`).join("")}</div></div>
          <div id="dr-heat"><div class="chart-empty">${L("Laden…", "Loading…")}</div></div></div>`;
      body += `<div class="card"><div class="card-head"><h3>${L("Wifi in de buurt", "Nearby wifi")}</h3><span class="muted" id="dr-nb-sub"></span></div><div id="dr-nb"><div class="chart-empty">${L("Laden…", "Loading…")}</div></div></div>`;
      const cl = state.snap.clients.filter((c) => c.ap_mac === d.mac).sort((a, b) => (a.satisfaction ?? 100) - (b.satisfaction ?? 100));
      body += `<div class="card"><h3 style="margin-bottom:8px">${L("Clients op dit access point", "Clients on this access point")}</h3><div class="table-wrap" style="border:0"><table><thead><tr><th>${L("Naam", "Name")}</th><th>Band</th><th>${L("Signaal", "Signal")}</th><th class="r">Retries</th><th class="r">${L("Ervaring", "Experience")}</th></tr></thead><tbody>
        ${cl.map((c) => `<tr data-id="${esc(c.mac)}" data-client tabindex="0"><td class="cell-name">${esc(c.name)}</td><td>${c.band} GHz</td><td>${signalBars(c.signal, c.band)}</td><td class="r num ${level("retry", c.retry_pct) !== "ok" ? "t-" + level("retry", c.retry_pct) : ""}">${nf(c.retry_pct, 1)}%</td><td class="r num">${nf(c.satisfaction)}</td></tr>`).join("")}
        </tbody></table></div></div>`;
    }
    if (d.ports.length && d.type === "switch") {
      const cm = Object.fromEntries(state.snap.clients.filter((c) => c.sw_mac === d.mac).map((c) => [c.sw_port, c]));
      const apm = Object.fromEntries(state.snap.devices.filter((x) => x.uplink_mac === d.mac).map((x) => [x.uplink_port, x]));
      const pi = portIssues(d);
      body += `<div class="card"><div class="card-head"><h3>${L("Poorten", "Ports")}</h3>${d.poe_budget_w ? `<span class="muted">PoE ${nf(d.poe_used_w)} / ${nf(d.poe_budget_w)} W</span>` : ""}</div>
        ${d.poe_budget_w ? `<div style="margin-bottom:14px">${meter(100 * d.poe_used_w / d.poe_budget_w, 100 * d.poe_used_w / d.poe_budget_w >= state.th.poe_budget_warn ? "warning" : "")}</div>` : ""}
        ${portGrid(d, false)}
        <div class="legend-row"><span><i class="sw" style="background:var(--me-success)"></i>${L("Actief", "Active")}</span><span><i class="sw" style="background:var(--me-warning)"></i>${L("Aandacht", "Attention")}</span><span><i class="sw" style="background:var(--me-danger)"></i>${L("Fouten / flapt", "Errors / flapping")}</span><span><i class="sw" style="background:var(--me-elevated);border:1px solid var(--me-border)"></i>${L("Geen link", "No link")}</span><span><i class="sw" style="background:var(--me-warning);border-radius:50%;width:6px;height:6px"></i>PoE</span></div>
        <div class="table-wrap" style="border:0;margin-top:12px"><table><thead><tr><th class="r">#</th><th>${L("Aangesloten", "Connected")}</th><th>${L("Snelheid", "Speed")}</th><th class="r">PoE</th><th>Status</th></tr></thead><tbody>
        ${d.ports.filter((p) => p.up || pi[p.idx]).map((p) => {
          const who = cm[p.idx]?.name || apm[p.idx]?.name || p.name;
          const iss = pi[p.idx] || [];
          return `<tr style="cursor:default"><td class="r num">${p.idx}</td><td>${esc(who)}${p.is_uplink ? ' <span class="badge">uplink</span>' : ""}</td><td class="num">${p.up ? speed(p.speed) : L("geen link", "no link")}</td><td class="r num">${p.poe_w ? nf(p.poe_w, 1) + " W" : "–"}</td><td>${iss.length ? iss.map((i) => badge(i.severity, i.title.split(": ").pop())).join(" ") : badge("ok", "OK")}</td></tr>`;
        }).join("")}</tbody></table></div></div>`;
    }
    body += `<div class="card"><div class="card-head"><h3>${L("CPU en geheugen", "CPU and memory")}</h3>${d.radios.length ? "" : rangeSeg("dr-range")}</div><div id="dr-ch-sys"></div></div>
      <div class="card"><h3 style="margin-bottom:8px">${L("Gebeurtenissen", "Events")}</h3><div class="events" id="dr-events"></div></div>`;
    $("#drawer-body").innerHTML = body;
    $("#dr-goclients")?.addEventListener("click", () => { state.cuplink = d.mac; state.ckind = "issues"; closeDrawer(); location.hash = "#/clients"; $("#view").dataset.mounted = ""; update(); });
    bindRange("dr-range", () => loadDeviceHistory(d));
    if (d.radios.length) { loadDevicePattern(d); loadNeighbors(d); }
    await loadDeviceHistory(d);
  }

  // ---- wifi in de buurt: per kanaal hoe druk het is voor deze AP
  async function loadNeighbors(ap) {
    let d;
    try { d = await api(`/api/neighbors/${encodeURIComponent(ap.mac)}`); } catch (e) { return; }
    const el = $("#dr-nb"); if (!el || state.drawer?.id !== ap.mac) return;
    if (!d.available) { el.innerHTML = `<p class="muted">${L("Alleen te zien via de uitgebreide UniFi-API.", "Only available via the extended UniFi API.")}</p>`; return; }
    $("#dr-nb-sub").textContent = L(`${d.total} netwerken gehoord`, `${d.total} networks heard`);
    const band = (b) => {
      const rows = d.channels[b] || [];
      if (!rows.length) return "";
      const max = Math.max(1, ...rows.map((r) => r.load)), best = Math.min(...rows.filter((r) => !r.own.length && (r.interference ?? 0) < 40).map((r) => r.load).concat([Infinity]));
      return `<h4 class="sub-h">${b} GHz</h4><div class="nb-rows">${rows.map((r) => {
        const lv = r.load >= 1000 ? "critical" : r.load >= 100 ? "warning" : "ok";
        return `<div class="nb-row ${r.current ? "cur" : ""}"><span class="num nb-ch">${r.channel}</span>${meter(Math.max(3, 100 * Math.log10(1 + r.load) / Math.log10(1 + max)), lv)}
          <span class="cell-sub">${r.neighbors ? L(`${r.neighbors} buren`, `${r.neighbors} neighbours`) : L("geen buren", "no neighbours")}${r.strongest != null ? ` · ${r.strongest} dBm` : ""}${r.own.length ? ` · ${L("eigen", "own")}: ${esc(r.own.join(", "))}` : ""}${r.interference != null ? ` · ${L("gemeten storing", "measured interference")} ${r.interference}%` : ""}</span>
          <span>${r.current ? badge("info", L("nu", "now")) : (r.interference ?? 0) >= 40 ? badge("warning", L("storing", "interference"), "alert") : !r.own.length && r.load === best && r.load * 4 < (rows.find((x) => x.current)?.load || 0) ? badge("ok", L("rustigst", "quietest"), "check") : ""}</span></div>`;
      }).join("")}</div>`;
    };
    el.innerHTML = `${band("2.4")}${band("5")}
      <details class="nb-list"><summary>${L("Sterkste netwerken in de buurt", "Strongest nearby networks")}</summary>
        <div class="table-wrap" style="border:0"><table><thead><tr><th>SSID</th><th>Band</th><th class="r">${L("Kanaal", "Channel")}</th><th class="r">${L("Signaal", "Signal")}</th></tr></thead><tbody>
        ${d.neighbors.slice(0, 15).map((n) => `<tr style="cursor:default"><td>${esc(n.ssid || L("(verborgen)", "(hidden)"))}</td><td>${n.band} GHz</td><td class="r num">${n.channel}</td><td class="r num">${n.signal ?? "–"} dBm</td></tr>`).join("")}</tbody></table></div></details>
      <p class="help" style="margin:8px 0 0">${L("Hoe voller de balk, hoe meer (en hoe sterker) buren op dat kanaal. Storing die niet van wifi komt (magnetrons, babyfoons) ziet Sonar alleen op kanalen waar deze AP eerder zelf op zat (zolang die historie bewaard is).", "The fuller the bar, the more (and stronger) neighbours on that channel. Non-wifi interference (microwaves, baby monitors) is only known for channels this AP used before (as long as that history is kept).")}</p>`;
  }

  // ------------------------------------------------------------------ patronen (heatmaps)
  const hm = { band: null, metric: "cu", data: null, mac: null };
  function heatmap(grid, { min, max, fmt, what }) {
    const vals = grid.flat().filter((v) => v != null);
    if (!vals.length) return `<div class="chart-empty">${L("Nog te weinig historie: na een dag meten verschijnt hier een patroon.", "Not enough history yet: after a day of measuring a pattern appears here.")}</div>`;
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
      const tip = `${at([d, h])} · ${v == null ? L("geen meting", "no reading") : fmt(v)}`;
      return `<span class="hm-c ${v == null ? "na" : ""}" data-tip="${esc(tip)}" style="${v == null ? "" : `background:rgba(57,216,244,${(0.07 + 0.78 * Math.max(0, Math.min(1, (v - bottom) / (top - bottom)))).toFixed(3)})`}"></span>`;
    }).join("")).join("");
    const hours = `<span></span>` + Array.from({ length: 24 }, (_, h) => `<span class="hm-h">${h % 6 === 0 ? h : ""}</span>`).join("");
    const flat = hi[2] - lo[2] < 0.05 * top;
    const summary = flat ? (what === "presence" ? (lo[2] >= 0.95 ? L("Altijd verbonden", "Always connected") : L(`Elk uur ongeveer even vaak verbonden (${fmt(hi[2])})`, `Connected about equally often every hour (${fmt(hi[2])})`)) : L(`Elk uur ongeveer gelijk (${fmt(hi[2])})`, `About the same every hour (${fmt(hi[2])})`))
      : `${what === "presence" ? L("Meest verbonden", "Most connected") : L("Drukst", "Busiest")}: ${at(hi)} (${fmt(hi[2])}) · ${what === "presence" ? L("minst", "least") : L("rustigst", "quietest")}: ${at(lo)} (${fmt(lo[2])})`;
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
      html += `<p style="margin:0 0 10px">${L(`Meestal op <b>${esc(fav.name)}</b> (${Math.round(fav.share * 100)}% van de tijd)`, `Mostly on <b>${esc(fav.name)}</b> (${Math.round(fav.share * 100)}% of the time)`)}${p.switches ? L(`, ${p.switches}× van AP gewisseld`, `, switched AP ${p.switches}×`) : L(", nooit van AP gewisseld", ", never switched AP")}.</p>
        <div class="ap-share">${p.aps.slice(0, 6).map((a) => `<div class="ap-row"><span class="cell-name">${esc(a.name)}</span>${meter(a.share * 100)}<span class="num">${Math.round(a.share * 100)}%</span><span class="muted num">${dur(a.seconds)}</span><span>${signalBars(a.signal, c.band)}</span></div>`).join("")}</div>
        <h4 class="sub-h">${L("Wanneer verbonden", "When connected")}</h4>`;
    }
    html += heatmap(p.presence, { min: 0, max: 1, fmt: (v) => `${Math.round(v * 100)}%`, what: "presence" });
    if (p.since && p.since > Date.now() / 1000 - p.days * 86400 + 6 * 3600) html += `<p class="help">${L("Historie sinds", "History since")} ${new Date(p.since * 1000).toLocaleDateString(LOC, { weekday: "long", day: "numeric", month: "long" })}.</p>`;
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
        : `<div class="chart-empty">${L("Geen historie voor deze band", "No history for this band")}</div>`;
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
        threshold: { value: state.th.radio_cu_warn, label: `${L("drempel", "threshold")} ${nf(state.th.radio_cu_warn)}%` } });
      MEcharts.lineChart($("#dr-ch-rt"), { series: bands.map((b) => ({ name: `${b} GHz`, color: BAND_COLOR[b], data: h.radios[b].map((p) => [p.t, p.retry_pct]) })), unit: "%", yMin: 0, bucket: h.bucket,
        threshold: { value: state.th.radio_retry_warn, label: `${L("drempel", "threshold")} ${nf(state.th.radio_retry_warn)}%` } });
    }
    MEcharts.lineChart($("#dr-ch-sys"), { series: [{ name: "CPU", color: C.cyan, data: h.device.map((p) => [p.t, p.cpu]) }, { name: L("Geheugen", "Memory"), color: C.violet, data: h.device.map((p) => [p.t, p.mem]) }], unit: "%", yMin: 0, yMax: 100, bucket: h.bucket });
    $("#dr-events").innerHTML = eventsHTML(h.events.slice(0, 60));
  }

  async function loadClientIdentity(c) {
    let r;
    try { r = await api(`/api/identify/${encodeURIComponent(c.mac)}`); } catch (e) { $("#dr-id-card")?.remove(); return; }
    const el = $("#dr-id");
    if (!el || state.drawer?.id !== c.mac) return;
    const g = r.guess;
    $("#dr-id-badge").innerHTML = confBadge(g);
    el.innerHTML = `${g ? `<div class="id-label">${esc(g.label)} <span class="muted">· ${esc(g.kind_label)}</span></div>
        <div class="cell-sub" style="margin-top:4px">${esc(g.evidence.join(" · "))}</div>
        ${g.hint ? `<div class="cell-sub id-hint">${icon("bulb")}${esc(g.hint)}</div>` : ""}`
      : `<p class="muted" style="margin:0">${L("Sonar herkent dit apparaat niet aan zijn verkeer, fabrikant of hostnaam.", "Sonar doesn't recognise this device from its traffic, vendor or hostname.")}</p>`}
      <div style="margin-top:12px">${nameForm(c.mac, r.unnamed ? g?.name || "" : c.name)}</div>
      <p class="help" style="margin:8px 0 0">${L("De naam komt in UniFi zelf, dus ook de UniFi-app ziet hem.", "The name goes into UniFi itself, so the UniFi app sees it too.")}</p>`;
    hydrateIcons(el);
  }
  async function renderClientDrawer(c) {
    if (!c) return closeDrawer();
    const dm = devByMac();
    $("#drawer-icon").innerHTML = icon(c.wired ? "cable" : "laptop");
    $("#drawer-title").textContent = c.name;
    $("#drawer-sub").textContent = `${c.vendor || ""} · ${c.ip} · ${c.mac}`;
    const conn = c.wired ? `${esc(dm[c.sw_mac]?.name || "–")} · ${L("poort", "port")} ${c.sw_port ?? "?"}` : esc(dm[c.ap_mac]?.name || "–");
    let body = `<div class="card">${kv(c.wired
      ? [[L("Verbonden met", "Connected to"), conn], ["Type", L("Bedraad", "Wired")], [L("Netwerk", "Network"), esc(c.network || "–")], [L("Verbonden sinds", "Connected for"), dur(c.uptime)], ["IP", esc(c.ip)], ["Score", `${c.score}/100`]]
      : [[L("Verbonden met", "Connected to"), conn], ["Band", `${c.band} GHz · ${L("kanaal", "channel")} ${c.channel}`], [L("Standaard", "Standard"), proto(c.proto)], [L("Signaal", "Signal"), signalBars(c.signal, c.band)], [L("Ruis", "Noise"), `${nf(c.noise)} dBm`],
        ["Retries", `${nf(c.retry_pct, 1)}%`], [L("Ervaring", "Experience"), nf(c.satisfaction)], [L("Snelheid", "Speed"), `${nf(c.tx_rate_mbps)} / ${nf(c.rx_rate_mbps)} Mbit/s`],
        [L("Met deze AP sinds", "On this AP since"), c.assoc_ts ? new Date(c.assoc_ts * 1000).toLocaleString(LOC, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : dur(c.uptime)]])}
      <div style="margin-top:14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        ${c.wired ? "" : reconnectBtn(c.mac).replace('class="linkbtn"', 'class="btn"')}${pauseMenu(c.mac)}${quarantineMenu(c.mac)}
        <span class="muted" style="font-size:12px">${c.wired ? "" : L("Opnieuw verbinden: kort los, daarna kiest het zelf de beste AP. ", "Reconnect: briefly disconnects, then it picks the best AP itself. ")}${L("Pauzeren: geen internet of netwerk tot de tijd om is.", "Pause: no internet or network until the time is up.")}</span></div></div>`;
    body += `<div class="card" id="dr-id-card"><div class="card-head"><h3>${L("Wat is dit?", "What is this?")}</h3><span id="dr-id-badge"></span></div><div id="dr-id"><div class="chart-empty">${L("Laden…", "Loading…")}</div></div></div>`;
    body += relatedIssues((i) => i.client_mac === c.mac);
    if (!c.wired) {
      body += `<div class="card"><div class="card-head"><h3>${L("Signaalsterkte", "Signal strength")}</h3>${rangeSeg("dr-range")}</div><div id="dr-ch-sig"></div></div>
        <div class="card"><div class="card-head"><h3>Retries</h3><span class="muted">${L("% opnieuw verstuurde pakketten", "% of packets resent")}</span></div><div id="dr-ch-rt"></div></div>
        <div class="card"><div class="card-head"><h3>${L("Wifi-ervaring", "Wifi experience")}</h3></div><div id="dr-ch-sat"></div></div>`;
    }
    body += `<div class="card"><div class="card-head"><h3>${L("Patroon", "Pattern")}</h3><span class="muted">${L("afgelopen 7 dagen", "past 7 days")}</span></div><div id="dr-pattern"><div class="chart-empty">${L("Laden…", "Loading…")}</div></div></div>`;
    body += `<div class="card"><div class="card-head"><h3>${L("Verbruik", "Usage")}</h3><span class="muted" id="dr-cu-sub"></span></div><div id="dr-cu"><div class="chart-empty">${L("Laden…", "Loading…")}</div></div></div>`;
    if (!c.wired) body += `<div class="card"><h3 style="margin-bottom:8px">${L("Roaming en verbindingen", "Roaming and connections")}</h3><div class="events" id="dr-events"></div></div>`;
    body += `<div class="card" id="dr-dns-card" hidden><div class="card-head"><h3>DNS (AdGuard)</h3><span class="muted">${L("afgelopen 24 uur", "past 24 hours")}</span></div><div id="dr-dns"></div></div>`;
    $("#drawer-body").innerHTML = body;
    loadClientPattern(c); loadClientUsageChart(c); loadClientDns(c); loadClientIdentity(c);
    if (!c.wired) { bindRange("dr-range", () => loadClientHistory(c)); await loadClientHistory(c); }
  }
  async function loadClientDns(c) {
    let d;
    try { d = await api(`/api/adguard/client/${encodeURIComponent(c.mac)}`); } catch (e) { return; }
    const el = $("#dr-dns"); if (!el || !d.active || state.drawer?.id !== c.mac) return;
    el.closest(".card").hidden = false;
    const auto = { smart: L("slim apparaat", "smart device"), server: "server", personal: L("persoonlijk apparaat", "personal device") }[d.auto];
    const sel = d.override === true ? "on" : d.override === false ? "off" : "auto";
    const day = (ts) => new Date(ts * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short" });
    el.innerHTML = `${kv([[L("Opgezocht", "Looked up"), nf(d.queries)], [L("Tegengehouden", "Blocked"), nf(d.blocked)], [L("Domeinen", "Domains"), d.watched ? nf(d.domains.length) : L("niet bewaard", "not kept")]])}
      <div class="field" style="margin-top:12px"><label for="dr-dns-watch">${L("Domeinen bewaren", "Keep domains")}</label>
        <select class="input" id="dr-dns-watch"><option value="auto" ${sel === "auto" ? "selected" : ""}>${L(`Automatisch (${auto}: ${d.auto === "personal" ? "nee" : "ja"})`, `Automatic (${auto}: ${d.auto === "personal" ? "no" : "yes"})`)}</option>
          <option value="on" ${sel === "on" ? "selected" : ""}>${L("Ja", "Yes")}</option><option value="off" ${sel === "off" ? "selected" : ""}>${L("Nee, en wis wat er is", "No, and erase what's there")}</option></select></div>
      ${d.watched ? (d.domains.length ? `<div class="adv-list" style="margin-top:8px">${d.domains.map((x) => `<div class="adv-row"><div style="min-width:0"><div class="rank-name">${esc(x.domain)}</div><div class="cell-sub">${L(`${nf(x.n)}× · eerst ${day(x.first)} · laatst ${day(x.last)}`, `${nf(x.n)}× · first ${day(x.first)} · last ${day(x.last)}`)}${x.blocked ? ` · ${nf(x.blocked)} ${L("tegengehouden", "blocked")}` : ""}</div></div><div class="adv-badges">${x.new ? badge("info", L("Nieuw", "New"), "info") : ""}</div></div>`).join("")}</div>`
        : `<p class="help">${L("Nog geen domeinen gezien.", "No domains seen yet.")}</p>`) + (d.learning_until ? `<p class="help">${L(`Sonar leert tot ${day(d.learning_until)} wat normaal is; daarna meldt het nieuwe domeinen.`, `Sonar learns what is normal until ${day(d.learning_until)}; after that it reports new domains.`)}</p>` : "")
        : `<p class="help">${L("Van dit apparaat bewaart Sonar alleen hoeveel het opzoekt, niet wat.", "For this device Sonar only keeps how much it looks up, not what.")}</p>`}`;
    hydrateIcons(el);
    $("#dr-dns-watch").addEventListener("change", async (e) => {
      const v = e.target.value;
      try { await post("/api/adguard/watch", { mac: c.mac, watch: v === "auto" ? null : v === "on" }); } catch (err) { alert(err.message); }
      loadClientDns(c);
    });
  }
  async function loadClientUsageChart(c) {
    let d;
    try { d = await api(`/api/usage/client/${encodeURIComponent(c.mac)}`); } catch (e) { return; }
    const el = $("#dr-cu"); if (!el || state.drawer?.id !== c.mac) return;
    if (!d.days.length) { el.innerHTML = `<div class="chart-empty">${L("Nog geen verbruik bekend", "No usage known yet")}</div>`; return; }
    const tot = d.days.reduce((a, r) => a + r.down + r.up, 0);
    $("#dr-cu-sub").textContent = L(`${gb(tot)} in ${d.days.length} dagen`, `${gb(tot)} in ${d.days.length} days`);
    el.innerHTML = `<div id="dr-cu-chart"></div>${d.cats.length ? `<div class="cu-cats">${d.cats.slice(0, 6).map((x) => `<span class="chip" style="cursor:default">${esc(x.cat)} <b class="num">${gb(x.down + x.up)}</b></span>`).join("")}</div>` : ""}`;
    MEcharts.barChart($("#dr-cu-chart"), {
      labels: d.days.map((r) => r.ts), height: 170, highlight: d.days.length - 1,
      series: [{ name: "Download", color: C.cyan, data: d.days.map((r) => r.down / 1e9) }, { name: "Upload", color: C.violet, data: d.days.map((r) => r.up / 1e9) }],
      fmt: (v) => `${nf(v, v < 10 && v > 0 ? 1 : 0)} GB`, label: L("Verbruik per dag", "Usage per day"),
      xfmt: (t) => new Date(t * 1000).toLocaleDateString(LOC, { day: "numeric", month: "short" }),
      tfmt: (t) => new Date(t * 1000).toLocaleDateString(LOC, { weekday: "long", day: "numeric", month: "long" }) });
  }
  async function loadClientHistory(c) {
    const h = await api(`/api/history/client/${encodeURIComponent(c.mac)}?hours=${state.hours}`);
    if (state.drawer?.id !== c.mac) return;
    const s = h.series;
    const th = L("drempel", "threshold");
    MEcharts.lineChart($("#dr-ch-sig"), { series: [{ name: L("Signaal", "Signal"), color: C.cyan, data: s.map((p) => [p.t, p.signal]) }], unit: " dBm", bucket: h.bucket,
      threshold: { value: sigLimits(c.band)[0], label: `${th} ${nf(sigLimits(c.band)[0])} dBm (${c.band} GHz)` } });
    MEcharts.lineChart($("#dr-ch-rt"), { series: [{ name: "Retries", color: C.violet, data: s.map((p) => [p.t, p.retry_pct]) }], unit: "%", yMin: 0, bucket: h.bucket,
      threshold: { value: state.th.client_retry_warn, label: `${th} ${nf(state.th.client_retry_warn)}%` } });
    MEcharts.lineChart($("#dr-ch-sat"), { series: [{ name: L("Ervaring", "Experience"), color: C.mint, data: s.map((p) => [p.t, p.satisfaction]) }], yMin: 0, yMax: 100, bucket: h.bucket,
      threshold: { value: state.th.client_satisfaction_warn, label: `${th} ${nf(state.th.client_satisfaction_warn)}` } });
    $("#dr-events").innerHTML = eventsHTML(h.events.slice(0, 60));
  }

  // ------------------------------------------------------------------ wereld
  const world = { hours: store.get("world.hours", 6), show: store.get("world.show", { out: true, in: true, blocked: true }),
                  mode: store.get("world.mode", "flat"), globe: null,
                  data: null, after: 0, timer: null, seen: new Set(), focus: null,
                  conn: { dir: "all", sort: "last", q: "", cc: null, limit: 50 } };
  const DIR = { out: [L("Uitgaand", "Outgoing"), C.cyan, "arrow-up-right"], in: [L("Inkomend", "Incoming"), C.violet, "arrow-down-left"], blocked: [L("Geblokkeerd", "Blocked"), C.rose, "octagon"] };
  const ccName = (() => {
    let dn = null;
    try { dn = new Intl.DisplayNames([LANG], { type: "region" }); } catch (e) { /* oude browser */ }
    return (cc) => { try { return (cc && dn?.of(cc)) || cc || L("Onbekend", "Unknown"); } catch (e) { return cc; } };
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
      <div class="page-head"><div><h1>${L("Wereld", "World")}</h1><p class="subtitle">${L("Met welke landen je netwerk praat, live uit het verkeerslogboek van je gateway.", "Which countries your network talks to, live from your gateway's traffic log.")}</p></div>
        <div class="seg" role="group" aria-label="${L("Periode", "Period")}" id="w-range">${[1, 6, 24, 48].map((h) => [h, `${h} ${L("u", "h")}`]).map(([h, l]) => `<button data-h="${h}" aria-pressed="${world.hours === h}">${l}</button>`).join("")}</div></div>
      <div id="w-banner"></div>
      <section class="grid kpis" id="w-kpis" aria-label="${L("Samenvatting", "Summary")}"></section>
      <section class="card world-card">
        <div class="card-head"><div class="chips" role="group" aria-label="${L("Soort verkeer", "Traffic type")}" id="w-show">${Object.entries(DIR).map(([k, [l, col]]) => `<button class="chip" data-k="${k}" aria-pressed="${!!world.show[k]}"><i class="sw" style="background:${col}"></i>${l}</button>`).join("")}</div>
          <div class="w-head-r"><div class="seg" role="group" aria-label="${L("Weergave", "View")}" id="w-mode">${[["flat", L("Plat", "Flat")], ["globe", "Globe"]].map(([k, l]) => `<button data-m="${k}" aria-pressed="${world.mode === k}">${l}</button>`).join("")}</div>
          <span class="muted" id="w-live-sub"><span class="live-dot" aria-hidden="true"></span>live</span></div></div>
        <div class="world-wrap" id="w-map">
          <div class="globe-host" id="w-globe" hidden></div>
          <svg viewBox="0 0 ${W.w} ${W.h}" role="img" aria-labelledby="w-map-title" preserveAspectRatio="xMidYMid meet">
            <title id="w-map-title">${L("Wereldkaart met verbindingen per land", "World map with connections per country")}</title>
            <g class="land">${Object.entries(W.countries).filter(([, c]) => c.d).map(([cc, c]) => `<path data-cc="${cc}" d="${c.d}"/>`).join("")}</g>
            <g class="arcs" id="w-arcs"></g><g class="pulses" id="w-pulses"></g><g id="w-home"></g><g class="marks" id="w-marks"></g><g class="labels" id="w-labels"></g>
          </svg>
          <div class="zoom-ctl" role="group" aria-label="${L("Zoomen", "Zoom")}">
            <button data-z="in" aria-label="${L("Inzoomen", "Zoom in")}" title="${L("Inzoomen", "Zoom in")}">+</button>
            <button data-z="out" aria-label="${L("Uitzoomen", "Zoom out")}" title="${L("Uitzoomen", "Zoom out")}">−</button>
            <button data-z="reset" aria-label="${L("Hele wereld", "Whole world")}" title="${L("Hele wereld", "Whole world")}">${icon("globe")}</button>
          </div>
          <div class="tooltip" id="w-tip"></div>
        </div>
        <div class="legend-row" id="w-legend"></div>
      </section>
      <section class="grid cols-2" style="margin-top:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">${L("Landen", "Countries")}</h2><span class="muted" id="w-cty-sub"></span></div><div class="rank w-rank" id="w-cty"></div></div>
        <div class="card"><div class="card-head"><h2 style="margin:0">Live</h2><span class="muted">${L("nieuwste eerst", "newest first")}</span></div><ol class="ticker" id="w-ticker" aria-live="off"></ol></div>
      </section>
      <section class="card" id="w-conn" style="margin-top:16px">
        <div class="card-head"><h2 style="margin:0">${L("Verbindingen", "Connections")}</h2><span class="muted" id="w-conn-sub"></span></div>
        <div class="toolbar">
          <div class="chips" role="group" aria-label="${L("Richting", "Direction")}" id="w-conn-dir">${[["all", L("Alles", "All"), null], ["out", DIR.out[0], C.cyan], ["in", DIR.in[0], C.violet], ["blocked", DIR.blocked[0], C.rose]].map(([k, l, col]) => `<button class="chip" data-d="${k}" aria-pressed="${world.conn.dir === k}">${col ? `<i class="sw" style="background:${col}"></i>` : ""}${l}</button>`).join("")}</div>
          <span id="w-conn-cc"></span>
          <div class="seg" role="group" aria-label="${L("Sorteren", "Sort")}" id="w-conn-sort">${[["last", L("Laatst", "Latest")], ["bytes", L("Meeste data", "Most data")], ["count", L("Vaakst", "Most often")]].map(([k, l]) => `<button data-s="${k}" aria-pressed="${world.conn.sort === k}">${l}</button>`).join("")}</div>
          <label class="search"><span class="sr-only">${L("Zoeken in verbindingen", "Search connections")}</span>${icon("search")}<input class="input" id="w-conn-q" type="search" placeholder="${L("Apparaat, domein, land of poort", "Device, domain, country or port")}" value="${esc(world.conn.q)}"></label>
        </div>
        <div class="table-wrap" id="w-conn-table"></div>
        <div class="wiz-actions" style="margin-top:12px;justify-content:center" id="w-conn-more"></div>
      </section>
      <section class="grid cols-2" style="margin-top:16px">
        <div class="card"><div class="card-head"><h2 style="margin:0">${L("Apparaten", "Devices")}</h2><span class="muted">${L("meeste internetverkeer", "most internet traffic")}</span></div><div class="rank w-rank" id="w-cli"></div></div>
        <div class="card"><div class="card-head"><h2 style="margin:0">${L("Bestemmingen", "Destinations")}</h2><span class="muted">${L("meeste data", "most data")}</span></div><div class="rank w-rank" id="w-dom"></div></div>
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
    const openBlocked = (tr) => { world.sel = world.blockedRows[tr.dataset.id]; if (world.sel) openDrawer("blocked", tr.dataset.id, tr); };
    $("#w-conn-table").addEventListener("click", (e) => {
      const n = e.target.closest("[data-open]");
      if (n) return openDrawer("client", n.dataset.id, n);
      const tr = e.target.closest("tr[data-blocked]");
      if (tr) openBlocked(tr);
    });
    $("#w-conn-table").addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("tr[data-blocked]")) openBlocked(e.target); });
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
  function globeButtons(z) {   // de knoppen volgen in globe-modus de globe, niet de platte kaart
    const q = (k) => $(`#w-map [data-z=${k}]`);
    if (!q("in")) return;
    q("out").disabled = z <= 1.01; q("in").disabled = z >= 4.99; q("reset").disabled = false;   // reset draait ook terug
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
    const svc = b.what && !/^(OTHER|Onbekend|Unknown)$/i.test(b.what) ? b.what.replace(/_/g, " ") : null;
    const port = L("poort", "port");
    return svc ? (b.port ? `${svc} (${port} ${b.port})` : svc) : b.port ? `${port} ${b.port}` : L("verbinding", "connection");
  };
  function countryTip(c) {
    const row = (k, l, v) => (v ? `<div class="tt-row"><span><i class="sw" style="background:${DIR[k][1]}"></i>${l}</span><b>${v}</b></div>` : "");
    return `<div class="tt-time">${esc(ccName(c.cc))}</div>
      ${row("out", DIR.out[0], c.out_n ? `${nf(c.out_n)} × · ${bytes(c.bytes_out ?? c.up + c.down)}` : "")}
      ${row("in", DIR.in[0], c.in_n ? `${nf(c.in_n)} ×` : "")}
      ${row("blocked", DIR.blocked[0], c.blocked_n ? `${nf(c.blocked_n)} ×` : "")}
      ${c.blocked?.length ? `<div class="tt-list tt-blocked">${c.blocked.slice(0, 4).map((b) => `<div>
        <div>${esc(blockWhat(b))} → ${esc(b.target)}</div>
        <div class="muted">${nf(b.n)}× · ${esc(b.by)}${b.sources > 1 ? ` · ${b.sources} ${L("adressen", "addresses")}` : ""} · ${L("laatst", "last")} ${stamp(b.last)}</div></div>`).join("")}</div>` : ""}
      ${c.domains?.length ? `<div class="tt-list">${c.domains.slice(0, 3).map((d) => `<div>${esc(d.name)} <span class="muted">${bytes(d.bytes)}</span></div>`).join("")}</div>` : ""}
      ${c.clients?.length ? `<div class="tt-list muted">${c.clients.slice(0, 3).map((x) => esc(x.name)).join(" · ")}</div>` : ""}
      <div class="tt-hint">${L("Klik voor alle verbindingen", "Click for all connections")}</div>`;
  }
  async function loadWorld() {
    let d;
    try { d = await api(`/api/world?hours=${world.hours}`); } catch (e) { return; }
    if (current !== "wereld") return;
    world.data = d;
    world.byCc = Object.fromEntries(d.countries.map((c) => [c.cc, c]));
    $("#w-banner").innerHTML = d.available === false ? `<div class="banner err">${icon("info")}<span>${L("Verbindingen zijn alleen beschikbaar via de uitgebreide UniFi-API (API-key of lokaal account).", "Connections are only available via the extended UniFi API (API key or local account).")}</span></div>`
      : d.error ? `<div class="banner err">${icon("info")}<span>${L("Verbindingen ophalen lukte niet", "Fetching connections failed")}: ${esc(d.error)}</span></div>` : "";
    const t = d.totals, per = world.hours === 1 ? L("het afgelopen uur", "the past hour") : L(`de afgelopen ${world.hours} uur`, `the past ${world.hours} hours`);
    const kpi = (k, ic, label, v, sub, hint) => `<button class="card compact kpi kpi-link" data-kpi="${k}" title="${hint}"><div class="label">${icon(ic)}${label}${icon("chevron", "kpi-go")}</div><div class="value">${v}</div><div class="sub">${sub}</div></button>`;
    $("#w-kpis").innerHTML =
      kpi("countries", "globe", L("Landen", "Countries"), nf(t.countries), per, L("Naar de landenlijst", "To the country list")) +
      kpi("out", "arrow-up-right", DIR.out[0], nf(t.out_n), L("verbindingen", "connections"), L("Toon de uitgaande verbindingen", "Show the outgoing connections")) +
      kpi("in", "arrow-down-left", DIR.in[0], nf(t.in_n), L("van internet naar binnen", "from the internet inwards"), L("Toon de inkomende verbindingen", "Show the incoming connections")) +
      kpi("bytes", "activity", "Data", bytes(t.bytes), L("op en neer", "up and down"), L("Toon de verbindingen met de meeste data", "Show the connections with the most data")) +
      kpi("blocked", "octagon", DIR.blocked[0], nf(t.blocked_n), L("door IPS en firewall", "by IPS and firewall"), L("Toon wat er geblokkeerd is", "Show what was blocked"));
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
    $("#w-legend").innerHTML = `<span><i class="sw" style="background:${C.cyan}"></i>${L("Uitgaand: eigen apparaat → internet", "Outgoing: own device → internet")}</span><span><i class="sw" style="background:${C.violet}"></i>${L("Inkomend: internet → eigen apparaat", "Incoming: internet → own device")}</span>
      <span><i class="sw" style="background:${C.rose}"></i>${L("Geblokkeerd: tegengehouden door IPS of firewall", "Blocked: stopped by IPS or firewall")}</span><span>${L("Kleur van een land: hoeveel data, dikte van de boog: hoeveel verkeer", "Colour of a country: how much data; thickness of the arc: how much traffic")}</span>`;
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
    try { await ensureGlobe(); } catch (e) { host.innerHTML = `<div class="empty">${L("De globe kon niet laden.", "The globe could not load.")}</div>`; return; }
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
      onZoom: globeButtons,
    });
    globeButtons(1);
    renderWorld();
  }
  function renderWorldLists() {
    const d = world.data;
    if (!d) return;
    const cs = d.countries.filter((c) => c.cc !== d.home || c.out_n).sort((a, b) => b.bytes - a.bytes || (b.blocked_n || 0) - (a.blocked_n || 0));
    const max = Math.max(1, ...cs.map((c) => c.bytes));
    const unk = d.totals.unknown_n || 0;
    $("#w-cty-sub").textContent = `${plural(cs.length, L("land", "country"), L("landen", "countries"))}${unk ? ` · ${nf(unk)} ${L("verbindingen zonder land", "connections without a country")}` : ""}`;
    $("#w-cty-sub").title = unk ? L("UniFi geeft niet bij elke verbinding een land mee, bijvoorbeeld bij DNS naar publieke resolvers.", "UniFi does not include a country with every connection, for example DNS to public resolvers.") : "";
    $("#w-cty").innerHTML = cs.length ? cs.slice(0, 25).map((c) => `
      <div class="rank-row w-row" data-cc="${c.cc}" tabindex="0" title="${L("Klik om in te zoomen op", "Click to zoom in on")} ${esc(ccName(c.cc))}"><div class="rank-main"><div class="rank-name"><span class="cc">${esc(c.cc)}</span>${esc(ccName(c.cc))}${c.cc === d.home ? ` <span class="muted">(${L("thuis", "home")})</span>` : ""}</div>
        <div class="cell-sub">${[c.out_n ? `${nf(c.out_n)} ${L("uit", "out")}` : "", c.in_n ? `${nf(c.in_n)} in` : "", c.blocked_n ? `<span class="t-critical">${nf(c.blocked_n)} ${L("geblokkeerd", "blocked")}</span>` : ""].filter(Boolean).join(" · ")}${c.domains?.[0] ? ` · ${esc(c.domains[0].name)}` : c.blocked?.[0] ? ` · ${esc(blockWhat(c.blocked[0]))} → ${esc(c.blocked[0].target)}` : ""}</div></div>
        <div class="rank-bar">${meter(100 * c.bytes / max)}</div><span class="num rank-n">${bytes(c.bytes)}</span></div>`).join("")
      : `<div class="empty">${L("Nog geen verbindingen in deze periode.", "No connections in this period yet.")}</div>`;
    const cmax = Math.max(1, ...d.clients.map((c) => c.bytes));
    $("#w-cli").innerHTML = d.clients.length ? d.clients.map((c) => `
      <div class="rank-row"><div class="rank-main"><div class="rank-name">${c.mac && cliByMac()[c.mac] ? `<button class="linkbtn plain" data-open="client" data-id="${esc(c.mac)}">${esc(c.name || c.mac)}</button>` : esc(c.name || "–")}</div>
        <div class="cell-sub">${nf(c.n)} ${L("verbindingen", "connections")} · ${plural(c.countries, L("land", "country"), L("landen", "countries"))}</div></div>
        <div class="rank-bar">${meter(100 * c.bytes / cmax)}</div><span class="num rank-n">${bytes(c.bytes)}</span></div>`).join("") : `<div class="empty">${L("Geen gegevens", "No data")}</div>`;
    const dmax = Math.max(1, ...d.domains.map((x) => x.bytes));
    $("#w-dom").innerHTML = d.domains.length ? d.domains.map((x) => `
      <div class="rank-row"><div class="rank-main"><div class="rank-name">${esc(x.name)}</div><div class="cell-sub">${x.cc ? `<span class="cc">${esc(x.cc)}</span>${esc(ccName(x.cc))} · ` : ""}${nf(x.n)} ${L("verbindingen", "connections")}</div></div>
        <div class="rank-bar">${meter(100 * x.bytes / dmax)}</div><span class="num rank-n">${bytes(x.bytes)}</span></div>`).join("") : `<div class="empty">${L("Geen gegevens", "No data")}</div>`;
  }
  function setConn(patch, scroll) {
    Object.assign(world.conn, patch, { limit: 50 });
    const c = world.conn;
    $("#w-conn-dir")?.querySelectorAll("[data-d]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.d === c.dir));
    $("#w-conn-sort")?.querySelectorAll("[data-s]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.s === c.sort));
    if (scroll) $("#w-conn").scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });
    loadConn();
  }
  function connSvc(r) {
    const s = r.service && !/^(OTHER)$/i.test(r.service) ? r.service.replace(/_/g, " ") : null;
    return s && r.port ? `${s} · ${r.port}` : s || (r.port ? `${L("poort", "port")} ${r.port}` : "–");
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
    $("#w-conn-cc").innerHTML = c.cc ? `<button class="chip" aria-pressed="true" data-clear-cc title="${L("Filter op land weghalen", "Remove country filter")}"><span class="cc">${esc(c.cc)}</span>${esc(ccName(c.cc))} ${icon("x")}</button>` : "";
    hydrateIcons($("#w-conn-cc"));
    const per = world.hours === 1 ? L("afgelopen uur", "past hour") : L(`afgelopen ${world.hours} uur`, `past ${world.hours} hours`);
    $("#w-conn-sub").textContent = `${nf(d.total)} ${d.total === 1 ? L("groep", "group") : L("groepen", "groups")} · ${per} · ${L("gelijke verbindingen samengevoegd", "identical connections merged")}`;
    const other = (r) => r.dir === "out"
      ? `<div class="rank-name">${esc(r.dest || "–")}</div><div class="cell-sub">${r.cc ? `<span class="cc">${esc(r.cc)}</span>${esc(ccName(r.cc))}` : L("land onbekend", "country unknown")}</div>`
      : `<div class="rank-name">${r.cc ? `<span class="cc">${esc(r.cc)}</span>${esc(ccName(r.cc))}` : L("onbekend", "unknown")}</div><div class="cell-sub">${plural(r.remotes || 0, L("adres", "address"), L("adressen", "addresses"))}</div>`;
    const dirTxt = (r) => r.dir === "blocked" ? `<span class="t-critical">${esc(r.by || DIR.blocked[0])}</span><span class="why-cue">${L("waarom?", "why?")}</span>` : DIR[r.dir][0];
    world.blockedRows = {};
    const rowAttrs = (r) => {
      if (r.dir !== "blocked") return 'style="cursor:default"';
      const id = ["blocked", r.by, r.cc, r.client, r.dest, r.port, r.service].join("|");
      world.blockedRows[id] = r;
      return `data-id="${esc(id)}" data-blocked tabindex="0" title="${L("Bekijk waarom dit geblokkeerd is", "See why this was blocked")}"`;
    };
    $("#w-conn-table").innerHTML = d.rows.length ? `<table class="conn-table"><thead><tr><th>${L("Laatst", "Last")}</th><th>${L("Richting", "Direction")}</th><th>${L("Eigen apparaat", "Own device")}</th><th>${L("Andere kant", "Other side")}</th><th>${L("Dienst", "Service")}</th><th class="r">${L("Aantal", "Count")}</th><th class="r">Data</th></tr></thead><tbody>
      ${d.rows.map((r) => `<tr ${rowAttrs(r)}><td class="num" title="${esc(fullStamp(r.last))}">${stamp(r.last)}</td>
        <td><span class="dir"><i class="sw" style="background:${DIR[r.dir][1]}"></i>${dirTxt(r)}</span></td>
        <td>${r.client_mac && cliByMac()[r.client_mac] ? `<button class="linkbtn plain" data-open="client" data-id="${esc(r.client_mac)}">${esc(r.client || "–")}</button>` : esc(r.client || "–")}</td>
        <td>${other(r)}</td><td class="muted">${esc(connSvc(r))}</td>
        <td class="r num">${nf(r.n)}</td><td class="r num">${r.bytes ? bytes(r.bytes) : "–"}</td></tr>`).join("")}</tbody></table>`
      : `<div class="empty">${L("Geen verbindingen gevonden", "No connections found")}${c.q || c.cc ? L(" met dit filter", " with this filter") : L(" in deze periode", " in this period")}.</div>`;
    markSelected();
    $("#w-conn-more").innerHTML = d.rows.length < d.total ? `<button class="btn">${L(`Toon meer (${nf(d.total - d.rows.length)} over)`, `Show more (${nf(d.total - d.rows.length)} left)`)}</button>` : "";
  }
  function blockedReason(r, land) {
    if (r.kind === "ips") return [r.service || L("IPS-regel", "IPS rule"), L("De inbraakpreventie (IPS) van je gateway herkende dit verkeer als een bekend aanvalspatroon en hield het tegen.", "The intrusion prevention (IPS) on your gateway recognised this traffic as a known attack pattern and stopped it.")];
    if (r.kind === "region") return [L("Regioblokkade", "Region block"), L(`${land || "Dit land"} staat in UniFi bij de geblokkeerde landen (Region Blocking). Verkeer met zo'n land wordt tegengehouden, welke dienst het ook is.`, `${land || "This country"} is on the blocked countries list in UniFi (Region Blocking). Traffic with such a country is stopped, whatever the service.`)];
    if (r.kind === "firewall" && r.rule) return [r.rule, L("Deze regel uit je UniFi-firewall hield de verbinding tegen.", "This rule in your UniFi firewall stopped the connection.")];
    if (r.kind === "conntrack") return [L("Ongeldige verbinding", "Invalid connection"), L("Dit verkeer hoorde volgens de firewall van je gateway niet bij een geldige verbinding. Dat is geen regel van jezelf en gebeurt af en toe vanzelf, bijvoorbeeld als een verbinding net verlopen is.", "According to your gateway's firewall this traffic did not belong to a valid connection. That is not one of your own rules and happens now and then, for example when a connection has just expired.")];
    if (r.kind === "firewall" && r.inbound == null) return [L("Firewallregel", "Firewall rule"), L("Een regel uit je UniFi-firewall hield dit tegen. Welke regel is hier niet bekend, omdat Sonar de naam pas sinds versie 1.6 bewaart. Bij nieuwe blokkades staat hij er wel bij.", "A rule in your UniFi firewall stopped this. Which rule is unknown here, because Sonar only keeps the name since version 1.6. New blocks do show it.")];
    if (r.kind === "firewall") return [L("Firewallregel", "Firewall rule"), L("Een regel uit je UniFi-firewall hield dit tegen. UniFi gaf de naam van de regel niet door.", "A rule in your UniFi firewall stopped this. UniFi did not report the name of the rule.")];
    return [r.rule || r.by, L(`UniFi hield deze verbinding tegen (${r.by}).`, `UniFi stopped this connection (${r.by}).`)];
  }
  function blockedAdvice(r) {
    if (r.inbound === 1) return L("Je hoeft niets te doen: dit is precies waar de blokkade voor is. Zulke pogingen komen op elke internetaansluiting voor.", "You don't need to do anything: this is exactly what the block is for. Attempts like this happen on every internet connection.");
    if (r.inbound !== 0) return "";
    if (r.kind === "region") return L("Moet dit apparaat wel bij dit land kunnen? Haal het land dan uit de regioblokkade in UniFi.", "Should this device be able to reach this country? Then remove the country from the region block in UniFi.");
    if (r.kind === "firewall") return L("Werkt er iets niet op dit apparaat? Maak dan in UniFi een uitzondering boven deze regel. Geen klachten, dan hoef je niets te doen.", "Is something not working on this device? Then add an exception above this rule in UniFi. No complaints means nothing to do.");
    return "";
  }
  function renderBlockedDrawer() {
    const r = world.sel;
    if (!r) return closeDrawer();
    const land = r.cc ? ccName(r.cc) : "", service = r.kind === "ips" ? (r.port ? `${L("poort", "port")} ${r.port}` : "–") : connSvc(r), [title, why] = blockedReason(r, land);
    const who = esc(r.client || L("Dit apparaat", "This device"));
    const attempt = r.inbound === 1 ? L(`Iemand op internet${land ? ` (${esc(land)})` : ""} probeerde <b>${who}</b> te bereiken via ${esc(service)}.`, `Someone on the internet${land ? ` (${esc(land)})` : ""} tried to reach <b>${who}</b> via ${esc(service)}.`)
      : r.inbound === 0 ? L(`<b>${who}</b> probeerde verbinding te maken met ${esc(r.dest || (land ? `een adres op internet (${land})` : "een adres op internet"))} via ${esc(service)}.`, `<b>${who}</b> tried to connect to ${esc(r.dest || (land ? `an address on the internet (${land})` : "an address on the internet"))} via ${esc(service)}.`) : "";
    const advice = blockedAdvice(r);
    const device = r.client_mac && cliByMac()[r.client_mac] ? `<button class="linkbtn plain" data-open="client" data-id="${esc(r.client_mac)}">${esc(r.client || "–")}</button>` : esc(r.client || "–");
    const pairs = [[L("Eigen apparaat", "Own device"), device], [L("Netwerk", "Network"), r.net && esc(r.net)],
      [L("Andere kant", "Other side"), esc([land, r.dest].filter(Boolean).join(" · ") || "–")], [L("Dienst", "Service"), esc(service)], [L("Protocol", "Protocol"), r.proto && esc(r.proto)],
      [L("Pogingen", "Attempts"), nf(r.n)], [L("Eerste keer", "First"), `<span title="${esc(fullStamp(r.first))}">${stamp(r.first)}</span>`], [L("Laatste keer", "Last"), `<span title="${esc(fullStamp(r.last))}">${stamp(r.last)}</span>`],
      [L("Categorie", "Category"), r.category && esc(r.category)], [L("Risico", "Risk"), r.kind === "ips" && r.risk && esc(r.risk)], [L("Regelnummer", "Rule number"), r.sid && esc(r.sid)]].filter(([, v]) => v);
    const ips = r.ips || [], more = (r.remotes || 0) - ips.length;
    $("#drawer-icon").innerHTML = icon("octagon");
    $("#drawer-title").textContent = L("Geblokkeerde verbinding", "Blocked connection");
    $("#drawer-sub").textContent = [r.client, land, service].filter(Boolean).join(" · ");
    $("#drawer-body").innerHTML = `<section class="card why-card">
        <div class="why-kind">${L("Waarom geblokkeerd", "Why blocked")}</div>
        <h3>${esc(title)}</h3>
        <p>${why}</p>
        ${r.note ? `<p class="why-note">${esc(r.note)}</p>` : ""}
        ${attempt ? `<p>${attempt}</p>` : ""}
        ${advice ? `<p class="muted">${advice}</p>` : ""}
      </section>
      <section class="card">${kv(pairs)}</section>
      ${ips.length ? `<section class="card"><h3 style="margin-bottom:10px">${L("Adressen aan de andere kant", "Addresses on the other side")}</h3>
        <div class="why-ips">${ips.map((ip) => `<code>${esc(ip)}</code>`).join("")}${more > 0 ? `<span class="muted">${L(`en nog ${nf(more)}`, `and ${nf(more)} more`)}</span>` : ""}</div></section>` : ""}`;
  }
  function renderTicker() {
    const el = $("#w-ticker");
    if (!el) return;
    const rows = (world.live || []).filter((f) => world.show[f.dir]).slice(0, 18);
    el.innerHTML = rows.length ? rows.map((f) => {
      const [l, col] = DIR[f.dir];
      const port = L("poort", "port");
      const what = f.dir === "blocked" ? `${esc(f.service || L("IPS-regel", "IPS rule"))}` : `${esc(f.domain || (f.port ? `${port} ${f.port}` : "–"))}`;
      const who = f.dir === "out" ? `${esc(f.client_name || "–")} → ${what}`
        : f.dir === "in" ? `${esc(ccName(f.cc))} → ${esc(f.client_name || "–")}${f.port ? ` <span class="muted">${port} ${f.port}</span>` : ""}`
        : `${what}${f.port ? ` <span class="muted">→ ${port} ${f.port}</span>` : ""}`;
      return `<li><span class="num muted">${hhmm(f.ts)}</span><i class="sw" style="background:${col}" title="${l}"></i>
        <span class="t-main">${who}</span><span class="t-cc" title="${esc(ccName(f.cc))}">${esc(f.cc || "–")}</span><span class="num muted t-b">${f.up + f.down ? bytes(f.up + f.down) : ""}</span></li>`;
    }).join("") : `<li class="empty">${L("Wachten op verbindingen…", "Waiting for connections…")}</li>`;
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
  if (LANG === "en") {   // vaste teksten in index.html
    document.querySelectorAll("[data-en]").forEach((n) => { n.textContent = n.dataset.en; });
    document.querySelectorAll("[data-en-label]").forEach((n) => { n.setAttribute("aria-label", n.dataset.enLabel); if (n.title) n.title = n.dataset.enLabel; });
  }
  $("#lang-top").outerHTML = langSwitch();
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-lang]");
    if (!b || b.dataset.lang === LANG) return;
    document.querySelectorAll("[data-lang]").forEach((x) => { x.disabled = true; });
    try { await post("/api/language", { language: b.dataset.lang }); location.reload(); }
    catch (err) { document.querySelectorAll("[data-lang]").forEach((x) => { x.disabled = false; }); alert(err.message); }
  });
  hydrateIcons(document);
  $("#drawer-close").onclick = closeDrawer;
  $("#scrim").onclick = closeDrawer;
  $("#drawer-body").addEventListener("click", async (e) => {
    if (await quarantineAction(e)) return;
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
  document.querySelectorAll(".nav a").forEach((a) => { a.title = a.querySelector(".lbl").textContent; });   // voor de icoonmodus op smalle vensters
  window.addEventListener("hashchange", route);
  $("#tab-more").addEventListener("click", (e) => {
    e.stopPropagation();
    const open = $("#more-sheet").hidden;
    $("#more-sheet").hidden = !open;
    $("#tab-more").setAttribute("aria-expanded", String(open));
    if (open) $("#more-sheet a").focus();
  });
  document.addEventListener("click", (e) => { if (!$("#more-sheet").hidden && !e.target.closest("#more-sheet")) closeMore(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#more-sheet").hidden) { closeMore(); $("#tab-more").focus(); } });
  // hoogte van de kopbalk als CSS-variabele: springknoppen plakken er net onder
  new ResizeObserver(() => document.documentElement.style.setProperty("--topbar-h", `${$(".topbar").offsetHeight}px`)).observe($(".topbar"));
  const start = () => { route(); refresh(); setInterval(refresh, 30000); };
  // Nog geen taal gekozen: de pagina volgde de browser; leg die keuze vast, zodat ook meldingen in die taal gaan.
  if (document.documentElement.dataset.langSet === "0") post("/api/language", { language: LANG }).catch(() => {}).finally(start);
  else start();
})();
