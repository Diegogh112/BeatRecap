/* Beat Recap — lógica del frontend */
"use strict";

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

// ---------------------------------------------------------------------------
// API base
// ---------------------------------------------------------------------------
const API_BASE =
  (location.hostname === "127.0.0.1" || location.hostname === "localhost")
    ? ""
    : "http://127.0.0.1:8000";
function api(path) { return API_BASE + path; }

// ---------------------------------------------------------------------------
// Estado global
// ---------------------------------------------------------------------------
const state = {
  jobId:        null,
  bpm:          0,
  baseBeats:    [],
  beats:        [],
  duration:     0,
  drop:         0,
  n:            1,
  multiplier:   1,
  offsetMs:     0,
  // images: [{dataUrl, name, file, isVideo, videoSeek}]
  // isVideo: true si es mp4/mov; videoSeek: segundo elegido
  images:       [],
  order:        [],
  // cropOffsets: {str(imgIndex): [cx, cy]}  — por índice en state.images
  cropOffsets:  {},
  // monthLabels: {str(imgIndex): "Enero"}  — etiqueta de mes por imagen
  monthLabels:  {},
  // tiltAngle: grados de inclinación alternada (0 = sin tilt)
  tiltAngle:    0,
  audioDataUrl: null,
  audioName:    null,
};

let ws               = null;
let sortableInstance = null;
let _dragging        = false;

// ---------------------------------------------------------------------------
// Persistencia en localStorage
// ---------------------------------------------------------------------------
const SESSION_KEY = "beatrecap_session";

function saveSession() {
  if (!state.jobId) return;

  const cfg = {
    jobId:        state.jobId,
    bpm:          state.bpm,
    baseBeats:    state.baseBeats,
    beats:        state.beats,
    duration:     state.duration,
    drop:         state.drop,
    n:            state.n,
    multiplier:   state.multiplier,
    offsetMs:     state.offsetMs,
    order:        state.order,
    audioName:    state.audioName,
    cropOffsets:  state.cropOffsets,
    monthLabels:  state.monthLabels,
    tiltAngle:    state.tiltAngle,
    images:       state.images.map(({ dataUrl, name, isVideo, videoSeek }) =>
                    ({ dataUrl, name: name || "img.jpg", isVideo: !!isVideo, videoSeek: videoSeek || 0, hasVideoFile: false })),
    introStyle:   $("intro-style").value,
    tiltAngle:    state.tiltAngle,
    title:        $("title-input").value,
    subtitle:     $("subtitle-input").value,
    textColor:    $("color-input").value,
    font:         $("font-select").value,
    transition:   $("transition-select").value,
    resolution:   $("resolution-select").value,
  };

  try {
    if (state.audioDataUrl) localStorage.setItem(SESSION_KEY + "_audio", state.audioDataUrl);
  } catch (_) {}

  try { localStorage.setItem(SESSION_KEY, JSON.stringify(cfg)); return; } catch (_) {}
  try { cfg.images = []; localStorage.setItem(SESSION_KEY, JSON.stringify(cfg)); return; } catch (_) {}
  try {
    cfg.images = []; cfg.baseBeats = []; cfg.beats = [];
    localStorage.setItem(SESSION_KEY, JSON.stringify(cfg));
  } catch (e) { console.error("[BeatRecap] No se pudo guardar:", e.message); }
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(SESSION_KEY + "_audio");
}

function dataUrlToFile(dataUrl, name) {
  const arr  = dataUrl.split(",");
  const mime = arr[0].match(/:(.*?);/)[1];
  const b    = atob(arr[1]);
  const buf  = new Uint8Array(b.length);
  for (let i = 0; i < b.length; i++) buf[i] = b.charCodeAt(i);
  return new File([buf], name || "image.jpg", { type: mime });
}

async function restoreSession() {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return false;
  let saved;
  try { saved = JSON.parse(raw); } catch (_) { clearSession(); return false; }
  if (!saved.jobId) { clearSession(); return false; }

  let jobAlive = false;
  try { const r = await fetch(api(`/audio/${saved.jobId}`), { method: "HEAD" }); jobAlive = r.ok; } catch (_) {}

  const audioDataUrl = localStorage.getItem(SESSION_KEY + "_audio") || null;
  if (!jobAlive && audioDataUrl) {
    saved.audioDataUrl = audioDataUrl;
    const ok = await _reuploadAudio(saved);
    if (ok) saved.jobId = state.jobId;
  } else if (jobAlive) {
    state.jobId = saved.jobId;
  }

  Object.assign(state, {
    jobId:        saved.jobId,
    bpm:          saved.bpm        ?? 0,
    baseBeats:    saved.baseBeats  ?? [],
    beats:        saved.beats      ?? [],
    duration:     saved.duration   ?? 0,
    drop:         saved.drop       ?? 0,
    n:            saved.n          ?? 1,
    multiplier:   saved.multiplier ?? 1,
    offsetMs:     saved.offsetMs   ?? 0,
    order:        saved.order      ?? [],
    cropOffsets:  saved.cropOffsets ?? {},
    monthLabels:  saved.monthLabels ?? {},
    tiltAngle:    saved.tiltAngle   ?? 0,
    audioDataUrl: audioDataUrl,
    audioName:    saved.audioName  ?? null,
  });

  state.images = (saved.images ?? []).map(({ dataUrl, name, isVideo, videoSeek }) => ({
    dataUrl,
    name,
    isVideo:      !!isVideo,
    videoSeek:    videoSeek || 0,
    hasVideoFile: false,   // el archivo de video original no sobrevive a localStorage
    file:         dataUrlToFile(dataUrl, name),
  }));

  $("offset-ms").value          = state.offsetMs;
  $("drop-val").value           = state.drop.toFixed(3);
  $("n-select").value           = String(state.n);
  $("intro-style").value        = saved.introStyle  ?? "text";
  $("title-input").value        = saved.title       ?? "2025 RECAP";
  $("subtitle-input").value     = saved.subtitle    ?? "";
  $("color-input").value        = saved.textColor   ?? "#FFFFFF";
  $("font-select").value        = saved.font        ?? "Impact";
  $("transition-select").value  = saved.transition  ?? "cut";
  $("resolution-select").value  = saved.resolution  ?? "vertical";
  // Tilt
  const savedTilt = saved.tiltAngle ?? 0;
  state.tiltAngle = savedTilt;
  const tiltChk = $("tilt-enable");
  if (tiltChk) tiltChk.checked = savedTilt > 0;
  refreshMonthsSummary();

  const beatsInfo = `${state.beats.length} beats · ${state.duration.toFixed(1)} s`;
  $("audio-status").className   = "status ok";
  $("audio-status").textContent = jobAlive
    ? `Sesión restaurada ✓  (${beatsInfo})`
    : `Sesión restaurada ✓  (${beatsInfo}) — sube el audio de nuevo para la forma de onda`;

  show($("step-beats")); show($("step-images"));
  show($("step-intro")); show($("step-render"));

  if (state.jobId && jobAlive) initWaveform();
  refreshBeatUi();
  renderImageGrid();
  renderImageWarnings();
  refreshMonthsSummary();
  return true;
}

async function _reuploadAudio(saved) {
  if (!saved.audioDataUrl) return false;
  const s = $("audio-status");
  s.className = "status"; s.textContent = "Re-subiendo audio al servidor…";
  try {
    const fd = new FormData();
    fd.append("file", dataUrlToFile(saved.audioDataUrl, saved.audioName || "audio.mp3"));
    const res = await fetch(api("/audio"), { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) return false;
    state.jobId = data.job_id; state.bpm = data.bpm; state.baseBeats = data.beats;
    return true;
  } catch (_) { return false; }
}

// ---------------------------------------------------------------------------
// Arranque: comprobación de conexión + restauración
// ---------------------------------------------------------------------------
(async () => {
  const s = $("audio-status");
  if (location.protocol === "file:") {
    s.className = "status error";
    s.innerHTML = "Abre la app desde el servidor. Ejecuta: <code>uvicorn backend.main:app --port 8000</code> y ve a <b>http://127.0.0.1:8000</b>.";
    $("analyze-btn").disabled = true; $("audio-input").disabled = true;
    return;
  }
  try {
    const r = await fetch(api("/openapi.json"));
    if (!r.ok) throw new Error("HTTP " + r.status);
  } catch (e) {
    s.className = "status error";
    s.textContent = "No se detecta el backend (" + e.message + "). Ejecuta: uvicorn backend.main:app --host 127.0.0.1 --port 8000";
    return;
  }
  const restored = await restoreSession();
  if (!restored) { s.className = "status ok"; s.textContent = "Servidor conectado ✓"; }
})();

// ---------------------------------------------------------------------------
// Transformaciones de rejilla
// ---------------------------------------------------------------------------
function doubleBeats(b) {
  const o = [];
  for (let i = 0; i < b.length; i++) {
    o.push(b[i]);
    if (i + 1 < b.length) o.push((b[i] + b[i + 1]) / 2);
  }
  return o;
}
function halveBeats(b) { return b.filter((_, i) => i % 2 === 0); }

function transformBeats(beats, multiplier, offsetMs, duration) {
  let bs = beats.map((b) => b + offsetMs / 1000);
  if (multiplier === 2) { bs = doubleBeats(bs); }
  else if (multiplier === 0.5) { bs = halveBeats(bs); }
  else if (multiplier !== 1) {
    const steps = Math.round(Math.abs(Math.log2(multiplier)));
    for (let i = 0; i < steps; i++) bs = multiplier > 1 ? doubleBeats(bs) : halveBeats(bs);
  }
  bs.sort((a, b) => a - b);
  return bs.filter((b) => b > -1e-6 && b <= duration + 1e-6);
}

function snapToNearestBeat(drop, beats) {
  if (!beats.length) return drop;
  return beats.reduce((best, b) => Math.abs(b - drop) < Math.abs(best - drop) ? b : best, beats[0]);
}
function beatsAfterDropCount() { return state.beats.filter((b) => state.drop < b && b <= state.duration).length; }
function imagesNeeded() { return Math.ceil(beatsAfterDropCount() / state.n); }

// ---------------------------------------------------------------------------
// Paso 1 — Audio
// ---------------------------------------------------------------------------
$("analyze-btn").addEventListener("click", async () => {
  const file = $("audio-input").files[0];
  if (!file) return;
  const status = $("audio-status");
  status.className = "status"; status.textContent = "Analizando…";
  $("analyze-btn").disabled = true;
  const fd = new FormData(); fd.append("file", file);
  try {
    const res  = await fetch(api("/audio"), { method: "POST", body: fd });
    const text = await res.text();
    let data = null;
    try { data = JSON.parse(text); } catch (_) {}
    if (!res.ok) {
      status.className = "status error";
      status.textContent = (data && data.detail) || text || "Error HTTP " + res.status;
      return;
    }
    clearSession();
    state.images = []; state.order = []; state.cropOffsets = {};
    state.monthLabels = {}; state.tiltAngle = 0;
    state.jobId = data.job_id; state.bpm = data.bpm;
    state.baseBeats = data.beats; state.beats = [...data.beats];
    state.duration = data.duration;
    state.drop = data.beats.length ? data.beats[0] : 0;
    state.multiplier = 1; state.offsetMs = 0;
    $("offset-ms").value = 0; $("image-grid").innerHTML = "";
    state.audioDataUrl = await fileToDataUrl(file); state.audioName = file.name;
    status.className = "status ok";
    status.textContent = `Audio analizado ✓  (${data.beats.length} beats, ${data.duration.toFixed(1)} s)`;
    initWaveform(); refreshBeatUi();
    show($("step-beats")); show($("step-images")); show($("step-intro")); show($("step-render"));
    saveSession();
  } catch (e) {
    status.className = "status error"; status.textContent = "Error al analizar: " + e.message;
  } finally { $("analyze-btn").disabled = false; }
});
$("audio-input").addEventListener("change", () => { $("analyze-btn").disabled = !$("audio-input").files.length; });

// ---------------------------------------------------------------------------
// Paso 2 — WaveSurfer + overlay
// ---------------------------------------------------------------------------
function initWaveform() {
  if (ws) { try { ws.destroy(); } catch (_) {} ws = null; }
  ws = WaveSurfer.create({
    container: "#waveform", waveColor: "#5a6678", progressColor: "#4f8cff",
    cursorColor: "#ffffff", height: 110, barWidth: 2, responsive: true,
  });
  ws.load(api(`/audio/${state.jobId}`));
  ws.on("ready", () => { drawBeatsOverlay(); setDrop(state.drop, false); });
  window.addEventListener("resize", drawBeatsOverlay);
  initOverlayInteraction();
}

function initOverlayInteraction() {
  const old = $("beats-overlay"); const fresh = old.cloneNode(true);
  old.parentNode.replaceChild(fresh, old);
  const c = $("beats-overlay");
  const move = (e) => {
    if (!state.duration) return;
    const rect = c.getBoundingClientRect();
    setDrop(Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)) * state.duration, false);
  };
  c.addEventListener("mousedown",  (e) => { _dragging = true;  move(e); });
  c.addEventListener("mousemove",  (e) => { if (_dragging) move(e); });
  c.addEventListener("mouseup",    ()  => { _dragging = false; });
  c.addEventListener("mouseleave", ()  => { _dragging = false; });
  c.addEventListener("touchstart", (e) => { _dragging = true;  move(e.touches[0]); e.preventDefault(); }, { passive: false });
  c.addEventListener("touchmove",  (e) => { if (_dragging) move(e.touches[0]); e.preventDefault(); }, { passive: false });
  c.addEventListener("touchend",   ()  => { _dragging = false; });
}

function positionOverlay() {
  const canvas = $("beats-overlay"); const waveDiv = $("waveform");
  const w = waveDiv.clientWidth || 600; const h = 110;
  canvas.style.position = "absolute"; canvas.style.left = waveDiv.offsetLeft + "px";
  canvas.style.top = waveDiv.offsetTop + "px"; canvas.style.width = w + "px";
  canvas.style.height = h + "px"; canvas.style.cursor = "col-resize";
  canvas.width = w; canvas.height = h;
}

function drawBeatsOverlay() {
  positionOverlay();
  const canvas = $("beats-overlay"); const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!state.duration) return;
  for (const b of state.beats) {
    const x = (b / state.duration) * canvas.width;
    ctx.strokeStyle = "rgba(124,92,255,0.75)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
  }
  const dx = (state.drop / state.duration) * canvas.width;
  ctx.strokeStyle = "#ff6b6b"; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(dx, 0); ctx.lineTo(dx, canvas.height); ctx.stroke();
  ctx.fillStyle = "#ff6b6b"; ctx.beginPath();
  ctx.moveTo(dx - 7, 0); ctx.lineTo(dx + 7, 0); ctx.lineTo(dx, 12); ctx.closePath(); ctx.fill();
  ctx.font = "bold 10px sans-serif"; ctx.fillStyle = "#ff6b6b"; ctx.fillText("DROP", dx + 4, 22);
}

function setDrop(t, snap) {
  t = Math.max(0, Math.min(t, state.duration));
  if (snap) t = snapToNearestBeat(t, state.beats);
  state.drop = t; $("drop-val").value = t.toFixed(3);
  drawBeatsOverlay(); refreshBeatUi(); saveSession();
}

$("snap-btn").addEventListener("click",  () => setDrop(state.drop, true));
$("drop-val").addEventListener("change", () => setDrop(parseFloat($("drop-val").value) || 0, false));
$("play-drop").addEventListener("click", () => { if (ws) ws.play(state.drop); });
$("stop-btn").addEventListener("click",  () => { if (ws) ws.stop(); });
$("bpm-double").addEventListener("click", () => { state.multiplier *= 2; recomputeBeats(); });
$("bpm-half").addEventListener("click",   () => { state.multiplier *= 0.5; recomputeBeats(); });
$("offset-ms").addEventListener("change", () => { state.offsetMs = parseFloat($("offset-ms").value) || 0; recomputeBeats(); });
$("n-select").addEventListener("change",  () => { state.n = parseInt($("n-select").value, 10); refreshBeatUi(); saveSession(); });

function recomputeBeats() {
  state.beats = transformBeats(state.baseBeats, state.multiplier, state.offsetMs, state.duration);
  drawBeatsOverlay(); refreshBeatUi(); saveSession();
}

function refreshBeatUi() {
  $("bpm-val").textContent     = state.bpm ? (state.bpm * state.multiplier).toFixed(1) : "—";
  $("beats-count").textContent = state.beats.length;
  $("dur-val").textContent     = state.duration ? state.duration.toFixed(1) : "—";
  const needed = imagesNeeded();
  $("needed-count").textContent = (needed > 0 && state.duration) ? needed : "—";
  const w = $("beat-warnings"); w.innerHTML = "";
  const after = beatsAfterDropCount();
  if (state.duration && after < 4) addWarn(w, `Quedan ${after} beat(s) tras el drop.`, after < 2 ? "danger" : "");
  renderImageWarnings();
}

function addWarn(container, text, cls = "") {
  const d = document.createElement("div");
  // Mapear clases legacy a nuevas
  const map = { "": "warning", "ok": "ok", "danger": "danger", "info": "info" };
  d.className = "warn " + (map[cls] || cls);
  d.textContent = text;
  container.appendChild(d);
}

// Botón "Eliminar todo" en el paso 3
$("clear-images-btn").addEventListener("click", () => {
  if (!state.images.length) return;
  if (!confirm(`¿Eliminar los ${state.images.length} elemento(s) subidos?`)) return;
  state.images = [];
  state.order  = [];
  state.cropOffsets  = {};
  state.monthLabels  = {};
  renderImageGrid();
  renderImageWarnings();
  refreshMonthsSummary();
  saveSession();
});

// ---------------------------------------------------------------------------
// Paso 3 — Imágenes y clips de video
// ---------------------------------------------------------------------------
const VIDEO_EXTS = new Set(["mp4", "mov", "webm"]);
function isVideoFile(name) { return VIDEO_EXTS.has((name || "").split(".").pop().toLowerCase()); }

["intro-style","title-input","subtitle-input","color-input","font-select","transition-select","resolution-select"]
  .forEach((id) => { $(id).addEventListener("change", saveSession); $(id).addEventListener("input", saveSession); });

// ── Tilt checkbox ───────────────────────────────────────────────────────────
$("tilt-enable").addEventListener("change", () => {
  // 0 = desactivado, 18 = amplitud máxima aleatoria
  state.tiltAngle = $("tilt-enable").checked ? 18 : 0;
  saveSession();
});

// ── Panel de meses inline en paso 3 ─────────────────────────────────────────
const MONTHS = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio",
                "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

function refreshMonthsSummary() {
  const count = Object.values(state.monthLabels).filter(Boolean).length;
  // Mostrar resumen en el botón
  const btn = $("open-months-btn");
  if (btn) btn.textContent = count > 0 ? `📅 Meses (${count})` : "📅 Asignar meses";
}

function buildMonthsList() {
  const list = $("months-list");
  list.innerHTML = "";
  if (!state.images.length) {
    list.innerHTML = '<p class="hint" style="margin:0;padding:8px">Sube imágenes primero.</p>';
    return;
  }
  state.order.forEach((imgIdx, carouselPos) => {
    const it    = state.images[imgIdx];
    const saved = state.monthLabels[String(imgIdx)] || "";
    const row   = document.createElement("div");
    row.className = "month-row";

    const img       = document.createElement("img");
    img.src         = it.dataUrl;
    img.className   = "month-thumb";

    const name      = document.createElement("span");
    name.className  = "month-name";
    name.textContent = `#${carouselPos + 1} ${it.name}`;

    const sel       = document.createElement("select");
    sel.className   = "month-select";
    sel.dataset.imgIdx = String(imgIdx);
    MONTHS.forEach(m => {
      const opt       = document.createElement("option");
      opt.value       = m;
      opt.textContent = m || "— sin mes —";
      if (m === saved) opt.selected = true;
      sel.appendChild(opt);
    });
    // Guardar al instante al cambiar
    sel.addEventListener("change", () => {
      if (sel.value) state.monthLabels[String(imgIdx)] = sel.value;
      else delete state.monthLabels[String(imgIdx)];
      refreshMonthsSummary();
      saveSession();
    });

    row.appendChild(img);
    row.appendChild(name);
    row.appendChild(sel);
    list.appendChild(row);
  });
}

$("open-months-btn").addEventListener("click", () => {
  const panel = $("months-panel");
  if (panel.classList.contains("hidden")) {
    buildMonthsList();
    show(panel);
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } else {
    hide(panel);
  }
});

$("months-panel-close").addEventListener("click", () => hide($("months-panel")));

$("months-clear").addEventListener("click", () => {
  state.monthLabels = {};
  buildMonthsList();   // reconstruir con selects en blanco
  refreshMonthsSummary();
  saveSession();
});

$("image-input").addEventListener("change", async () => {
  for (const f of Array.from($("image-input").files)) {
    const isVideo = isVideoFile(f.name);
    let dataUrl;
    if (isVideo) {
      dataUrl = await extractFrameAsDataUrl(f, 0);
    } else {
      dataUrl = await fileToDataUrl(f);
    }
    // hasVideoFile: true SOLO cuando el archivo de video original está en memoria
    state.images.push({ dataUrl, name: f.name, file: f, isVideo, videoSeek: 0, hasVideoFile: isVideo });
    state.order.push(state.images.length - 1);
  }
  $("image-input").value = "";
  renderImageGrid(); renderImageWarnings(); saveSession();
});

function fileToDataUrl(f) {
  return new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(f); });
}

/** Envía el clip al backend y devuelve el frame como dataUrl. */
async function extractFrameAsDataUrl(fileOrDataUrl, seek) {
  let fileObj;
  if (fileOrDataUrl instanceof File) {
    fileObj = fileOrDataUrl;
  } else {
    // viene de sesión guardada: reconstruir File desde dataUrl
    const name = typeof fileOrDataUrl === "string" ? "clip.mp4" : "clip.mp4";
    fileObj = dataUrlToFile(fileOrDataUrl, name);
  }
  const fd = new FormData();
  fd.append("file", fileObj);
  fd.append("seek", String(seek || 0));
  try {
    const res = await fetch(api("/extract-frame"), { method: "POST", body: fd });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const blob = await res.blob();
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(blob);
    });
  } catch (e) {
    console.warn("No se pudo extraer el frame:", e.message);
    // Fallback: canvas negro con icono
    const canvas = document.createElement("canvas");
    canvas.width = 90; canvas.height = 160;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#111"; ctx.fillRect(0, 0, 90, 160);
    ctx.font = "30px sans-serif"; ctx.textAlign = "center";
    ctx.fillText("🎬", 45, 90);
    return canvas.toDataURL("image/jpeg");
  }
}

function renderImageGrid() {
  const grid     = $("image-grid");
  const snapshot = [...state.order];
  grid.innerHTML = "";

  snapshot.forEach((imgIdx, pos) => {
    const it  = state.images[imgIdx];
    const cx  = (state.cropOffsets[String(imgIdx)] || [0.5, 0.5])[0];
    const cy  = (state.cropOffsets[String(imgIdx)] || [0.5, 0.5])[1];
    const hasCustomCrop = (cx !== 0.5 || cy !== 0.5);

    const div = document.createElement("div");
    div.className   = "thumb";
    div.dataset.pos = String(pos);
    div.dataset.imgIdx = String(imgIdx);
    div.innerHTML = `
      <span class="num">${pos + 1}</span>
      <img src="${it.dataUrl}" alt="" loading="lazy" />
      ${it.isVideo ? '<span class="badge-video">VIDEO</span>' : ""}
      ${hasCustomCrop ? '<span class="badge-crop">✂</span>' : ""}
      <div class="acts">
        <button class="dup act-dup" title="Duplicar">⧉</button>
        <button class="del act-del" title="Eliminar">✕</button>
      </div>`;

    // Click en el thumb completo → abrir editor de encuadre
    div.addEventListener("click", () => openCropModal(imgIdx));

    div.querySelector(".del").addEventListener("click", (e) => {
      e.stopPropagation();
      state.order.splice(pos, 1);
      renderImageGrid(); renderImageWarnings(); saveSession();
    });
    div.querySelector(".dup").addEventListener("click", (e) => {
      e.stopPropagation();
      state.order.splice(pos + 1, 0, imgIdx);
      renderImageGrid(); renderImageWarnings(); saveSession();
    });
    grid.appendChild(div);
  });

  $("img-count").textContent = `${state.images.length} elemento(s) · ${state.order.length} en el carrusel`;

  if (sortableInstance) { try { sortableInstance.destroy(); } catch (_) {} }
  sortableInstance = Sortable.create(grid, {
    animation: 150, ghostClass: "sortable-ghost", chosenClass: "sortable-chosen",
    onEnd: () => {
      const positions = Array.from(grid.children).map((el) => parseInt(el.dataset.pos, 10));
      const oldOrder  = [...state.order];
      state.order     = positions.map((p) => oldOrder[p]);
      renderImageGrid(); renderImageWarnings(); saveSession();
      // Si el panel de meses está abierto, reconstruirlo con el nuevo orden
      if (!$("months-panel").classList.contains("hidden")) buildMonthsList();
    },
  });
}

function renderImageWarnings() {
  const w = $("image-warnings"); if (!w || !state.duration) return;
  w.innerHTML = "";
  const needed = imagesNeeded();
  if (needed === 0) { addWarn(w, "No hay beats tras el drop.", "danger"); return; }
  const uploaded = state.images.length;
  if (uploaded === 0)          addWarn(w, `Sube ${needed} elemento(s). Si subes menos se repetirán en bucle.`);
  else if (uploaded < needed)  addWarn(w, `Tienes ${uploaded}, se necesitan ${needed}. Se repetirán en bucle.`, "ok");
  else if (uploaded > needed)  addWarn(w, `Tienes ${uploaded}, solo se usan ${needed}. Sobran ${uploaded - needed}.`);
  else                         addWarn(w, `Número correcto: ${needed}. ✓`, "ok");
}

// ---------------------------------------------------------------------------
// Editor de encuadre (modal)
// ---------------------------------------------------------------------------
let _cropImgIdx     = null;
let _cropCx         = 0.5;
let _cropCy         = 0.5;
let _rectDragging   = false;
let _rectDragStartX = 0;
let _rectDragStartY = 0;
let _rectStartCx    = 0.5;
let _rectStartCy    = 0.5;
let _modalVideoURL  = null;   // objectURL activo del video en el modal

function _revokeModalVideo() {
  const v = $("modal-video");
  if (v) { v.pause(); v.src = ""; }
  if (_modalVideoURL) { URL.revokeObjectURL(_modalVideoURL); _modalVideoURL = null; }
}

function openCropModal(imgIdx) {
  _revokeModalVideo();
  _cropImgIdx = imgIdx;
  const it    = state.images[imgIdx];
  const saved = state.cropOffsets[String(imgIdx)] || [0.5, 0.5];
  _cropCx = saved[0];
  _cropCy = saved[1];

  $("crop-modal-title").textContent = it.isVideo
    ? `Clip — ${it.name}`
    : `Encuadre — ${it.name}`;

  $("crop-canvas-label").textContent = it.isVideo
    ? "Encuadre del frame elegido (arrastra el recuadro)"
    : "Arrastra el recuadro rojo para elegir qué parte se verá en el video.";

  // Mostrar/ocultar columna de video sin mover nada del DOM
  const videoCol  = $("crop-video-col");
  const modalBody = $("crop-modal").querySelector(".modal-body");

  if (it.isVideo) {
    videoCol.style.display = "";
    modalBody.classList.add("two-col");

    const v    = $("modal-video");
    const warn = $("video-seek-warn");
    const btn  = $("video-use-point");

    if (it.hasVideoFile && it.file) {
      warn.style.display = "none";
      btn.style.display  = "";
      _modalVideoURL = URL.createObjectURL(it.file);
      v.src = _modalVideoURL;
      v.load();
      v.onloadedmetadata = () => {
        $("video-dur-val").textContent = `/ ${v.duration.toFixed(1)} s`;
        v.currentTime = it.videoSeek || 0;
      };
      v.ontimeupdate = () => {
        $("video-seek-val").textContent = v.currentTime.toFixed(1) + " s";
      };
    } else {
      v.src = "";
      warn.style.display = "";
      warn.textContent   = "El archivo de video no está disponible en memoria. Re-sube el clip para cambiar el punto de inicio.";
      btn.style.display  = "none";
      $("video-seek-val").textContent = (it.videoSeek || 0).toFixed(1) + " s";
      $("video-dur-val").textContent  = "";
    }
  } else {
    videoCol.style.display = "none";
    modalBody.classList.remove("two-col");
  }

  show($("crop-modal"));
  _renderCropCanvas(it.dataUrl);
}

function _renderCropCanvas(dataUrl) {
  const img = new window.Image();
  img.onload = () => {
    const wrap   = $("crop-canvas-wrap");
    const canvas = $("crop-canvas");
    // Ancho máximo: el del contenedor actual, máx 400px para no ocupar demasiado
    const maxW   = Math.min(wrap.clientWidth || 360, 400);
    const scale  = maxW / img.width;
    canvas.width  = Math.round(img.width  * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.style.width  = canvas.width  + "px";
    canvas.style.height = canvas.height + "px";
    wrap.style.height   = canvas.height + "px";
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    _updateCropRect();
  };
  img.src = dataUrl;
}

function _updateCropRect() {
  const canvas = $("crop-canvas");
  const rect   = $("crop-rect");
  if (!canvas.width) return;

  // Calcular el tamaño del recuadro (proporción del canvas destino sobre la imagen escalada)
  const res      = $("resolution-select").value;
  const [dw, dh] = res === "horizontal" ? [1920, 1080] : [1080, 1920];

  // Escala del recuadro en la vista previa del canvas
  const imgW     = canvas.width;
  const imgH     = canvas.height;
  // Tamaño del "frame destino" proyectado sobre la imagen escalada (como cover_fit)
  const scaleC   = Math.max(dw / imgW, dh / imgH);
  const fitW     = dw / scaleC;
  const fitH     = dh / scaleC;

  // Margen disponible (en píxeles del canvas de preview)
  const marginX  = Math.max(0, imgW - fitW);
  const marginY  = Math.max(0, imgH - fitH);

  const left     = _cropCx * marginX;
  const top      = _cropCy * marginY;

  rect.style.left   = left + "px";
  rect.style.top    = top  + "px";
  rect.style.width  = fitW + "px";
  rect.style.height = fitH + "px";
}

// Drag del recuadro
$("crop-rect").addEventListener("mousedown", (e) => {
  _rectDragging  = true;
  _rectDragStartX = e.clientX; _rectDragStartY = e.clientY;
  _rectStartCx   = _cropCx;    _rectStartCy    = _cropCy;
  e.preventDefault();
});
window.addEventListener("mousemove", (e) => {
  if (!_rectDragging) return;
  _moveCropRect(e.clientX - _rectDragStartX, e.clientY - _rectDragStartY);
});
window.addEventListener("mouseup", () => { _rectDragging = false; });

$("crop-rect").addEventListener("touchstart", (e) => {
  _rectDragging = true;
  _rectDragStartX = e.touches[0].clientX; _rectDragStartY = e.touches[0].clientY;
  _rectStartCx = _cropCx; _rectStartCy = _cropCy;
  e.preventDefault();
}, { passive: false });
window.addEventListener("touchmove", (e) => {
  if (!_rectDragging) return;
  _moveCropRect(e.touches[0].clientX - _rectDragStartX, e.touches[0].clientY - _rectDragStartY);
}, { passive: true });
window.addEventListener("touchend", () => { _rectDragging = false; });

function _moveCropRect(dx, dy) {
  const canvas  = $("crop-canvas");
  const res     = $("resolution-select").value;
  const [dw, dh]= res === "horizontal" ? [1920, 1080] : [1080, 1920];
  const scaleC  = Math.max(dw / canvas.width, dh / canvas.height);
  const fitW    = dw / scaleC;
  const fitH    = dh / scaleC;
  const marginX = Math.max(1, canvas.width  - fitW);
  const marginY = Math.max(1, canvas.height - fitH);
  _cropCx = Math.max(0, Math.min(1, _rectStartCx + dx / marginX));
  _cropCy = Math.max(0, Math.min(1, _rectStartCy + dy / marginY));
  _updateCropRect();
}

$("crop-reset").addEventListener("click", () => {
  _cropCx = 0.5; _cropCy = 0.5; _updateCropRect();
});

$("crop-save").addEventListener("click", () => {
  if (_cropImgIdx === null) return;
  state.cropOffsets[String(_cropImgIdx)] = [_cropCx, _cropCy];
  hide($("crop-modal"));
  renderImageGrid(); saveSession();
});

$("crop-close").addEventListener("click", () => {
  _revokeModalVideo();
  hide($("crop-modal"));
});
$("crop-modal").addEventListener("click", (e) => {
  if (e.target === $("crop-modal")) { _revokeModalVideo(); hide($("crop-modal")); }
});

// "Usar este punto": congela el currentTime del video como seekPoint,
// extrae el frame en ese segundo y actualiza la miniatura.
$("video-use-point").addEventListener("click", async () => {
  if (_cropImgIdx === null) return;
  const it  = state.images[_cropImgIdx];
  if (!it.isVideo || !it.hasVideoFile) return;

  const v    = $("modal-video");
  const seek = v.currentTime;
  v.pause();

  const btn = $("video-use-point");
  btn.disabled     = true;
  btn.textContent  = "Extrayendo frame…";

  // Extraer el frame del segundo elegido para la miniatura y el encuadre
  const newDataUrl = await extractFrameAsDataUrl(it.file, seek);

  it.videoSeek = seek;
  it.dataUrl   = newDataUrl;

  btn.disabled    = false;
  btn.textContent = "✓ Usar este punto";

  // Actualizar el canvas de encuadre con el nuevo frame
  _renderCropCanvas(newDataUrl);
  renderImageGrid();
  saveSession();
});

// ---------------------------------------------------------------------------
// Paso 5 — Vista previa y render
// ---------------------------------------------------------------------------

/**
 * Para clips de video, antes de enviar al render necesitamos tener el frame
 * extraído guardado como imagen JPEG. buildFormData llama extractFrameAsDataUrl
 * para cada video con su seek y lo envía como imagen estática.
 */
async function buildFormData() {
  const fd = new FormData();
  fd.append("job_id",      state.jobId);

  // Construir la lista de Files a enviar: imágenes normales tal cual,
  // videos como JPEG del frame elegido
  const filesForRender = [];
  const cropOffsetsByRenderIdx = {};

  for (let i = 0; i < state.images.length; i++) {
    const it = state.images[i];
    let fileToSend;
    if (it.isVideo && it.hasVideoFile && it.file) {
      // Video con archivo original en memoria → enviar el mp4 con seek en el nombre
      const seek    = it.videoSeek || 0;
      const ext     = it.name.split(".").pop();
      const newName = it.name.replace(/\.\w+$/, "") + `_seek${seek.toFixed(2)}.${ext}`;
      fileToSend    = new File([it.file], newName, { type: it.file.type });
    } else {
      // Imagen estática (o video sin archivo original → usar el frame guardado)
      fileToSend = it.file instanceof File && !it.hasVideoFile
        ? it.file
        : dataUrlToFile(it.dataUrl, it.isVideo ? it.name.replace(/\.\w+$/, ".jpg") : it.name);
    }
    filesForRender.push(fileToSend);
    const off = state.cropOffsets[String(i)];
    if (off) cropOffsetsByRenderIdx[String(i)] = off;
  }

  for (const f of filesForRender) fd.append("images", f);
  fd.append("order",        JSON.stringify(state.order));
  fd.append("beats",        JSON.stringify(state.beats));
  fd.append("drop",         String(state.drop));
  fd.append("n",            String(state.n));
  fd.append("intro_style",  $("intro-style").value);
  fd.append("title",        $("title-input").value    || "2025 RECAP");
  fd.append("subtitle",     $("subtitle-input").value || "");
  fd.append("text_color",   $("color-input").value    || "#FFFFFF");
  fd.append("font",         $("font-select").value);
  fd.append("transition",   $("transition-select").value);
  fd.append("resolution",   $("resolution-select").value);
  fd.append("crop_offsets",  JSON.stringify(cropOffsetsByRenderIdx));
  fd.append("month_labels",  JSON.stringify(state.monthLabels || {}));
  fd.append("tilt_angle",    String(state.tiltAngle || 0));
  return fd;
}

async function startRender(preview) {
  if (!state.jobId)         return alert("Sube y analiza el audio primero.");
  if (!state.images.length) return alert("Sube al menos una imagen o clip.");
  const wrap = $("progress-wrap");
  show(wrap);
  $("progress-label").textContent = preview ? "Generando vista previa…" : "Renderizando…";
  $("progress-bar").value = 0; $("progress-pct").textContent = "0%";
  $("result-area").innerHTML = ""; hide($("result-area"));
  try {
    const fd   = await buildFormData();
    const res  = await fetch(api(preview ? "/preview" : "/render"), { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) { hide(wrap); alert((data && data.detail) || "Error HTTP " + res.status); return; }
    pollRender(data.render_id, preview);
  } catch (e) { hide(wrap); alert("No se pudo conectar con el servidor: " + e.message); }
}

function pollRender(renderId, preview) {
  const timer = setInterval(async () => {
    let data;
    try { const res = await fetch(api(`/render/${renderId}`)); data = await res.json(); }
    catch (e) { clearInterval(timer); hide($("progress-wrap")); alert("Se perdió la conexión: " + e.message); return; }
    const pct = Math.round((data.progress || 0) * 100);
    $("progress-bar").value = pct; $("progress-pct").textContent = pct + "%";
    if (data.status === "completed") { clearInterval(timer); hide($("progress-wrap")); showResult(renderId, preview); }
    else if (data.status === "failed") { clearInterval(timer); hide($("progress-wrap")); alert("El render falló: " + (data.error || "?")); }
  }, 800);
}

function showResult(renderId, preview) {
  const streamUrl   = api(`/render/${renderId}/stream`);
  const downloadUrl = api(`/render/${renderId}/download`);
  const area = $("result-area");
  area.innerHTML = `
    <div id="player-wrap"><video id="result-video" controls playsinline preload="auto"></video></div>
    <div class="row result-actions">
      <a id="download-btn" class="btn primary dl">⬇ Descargar</a>
      <button id="close-result-btn" class="btn small">✕ Cerrar</button>
    </div>`;
  const video = area.querySelector("#result-video");
  const dlBtn = area.querySelector("#download-btn");
  const closeBtn = area.querySelector("#close-result-btn");
  video.src = streamUrl; video.load(); video.play().catch(() => {});
  dlBtn.href = downloadUrl;
  dlBtn.download    = preview ? "beat_recap_preview.mp4" : "beat_recap.mp4";
  dlBtn.textContent = preview ? "⬇ Descargar vista previa" : "⬇ Descargar MP4";
  closeBtn.addEventListener("click", () => { video.pause(); video.src = ""; area.innerHTML = ""; hide(area); });
  show(area); area.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

$("preview-btn").addEventListener("click", () => startRender(true));
$("render-btn").addEventListener("click",  () => startRender(false));

// --- Nueva sesión -----------------------------------------------------------
$("new-session-btn").addEventListener("click", () => {
  if (!confirm("¿Borrar todo y empezar de cero?")) return;
  clearSession(); location.reload();
});
