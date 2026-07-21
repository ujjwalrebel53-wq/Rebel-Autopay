import { CameraTracker } from "./camera.js";
import { fetchTowers, renderTowerList, summarizeTowers } from "./towers.js";
import {
  clearMoments,
  formatTime,
  loadMoments,
  loadSettings,
  saveSettings,
} from "./storage.js";

const state = {
  geo: { lat: null, lon: null, accuracy: null },
  towers: [],
  settings: loadSettings(),
};

const els = {
  sections: document.querySelectorAll(".section"),
  navButtons: document.querySelectorAll("[data-section]"),
  statTowers: document.getElementById("statTowers"),
  statDevices: document.getElementById("statDevices"),
  statMoments: document.getElementById("statMoments"),
  collectorUrl: document.getElementById("collectorUrl"),
  btnRefreshTowers: document.getElementById("btnRefreshTowers"),
  towerStatus: document.getElementById("towerStatus"),
  towerList: document.getElementById("towerList"),
  geoStatus: document.getElementById("geoStatus"),
  geoLat: document.getElementById("geoLat"),
  geoLon: document.getElementById("geoLon"),
  geoAcc: document.getElementById("geoAcc"),
  mapLink: document.getElementById("mapLink"),
  cameraVideo: document.getElementById("cameraVideo"),
  motionCanvas: document.getElementById("motionCanvas"),
  captureCanvas: document.getElementById("captureCanvas"),
  cameraOverlay: document.getElementById("cameraOverlay"),
  cameraBadge: document.getElementById("cameraBadge"),
  cameraBadgeText: document.getElementById("cameraBadgeText"),
  cameraStatus: document.getElementById("cameraStatus"),
  btnStartCamera: document.getElementById("btnStartCamera"),
  btnStopCamera: document.getElementById("btnStopCamera"),
  btnCapture: document.getElementById("btnCapture"),
  btnSwitchCam: document.getElementById("btnSwitchCam"),
  motionDetect: document.getElementById("motionDetect"),
  linkTower: document.getElementById("linkTower"),
  sensitivity: document.getElementById("sensitivity"),
  sensitivityVal: document.getElementById("sensitivityVal"),
  cooldown: document.getElementById("cooldown"),
  cooldownVal: document.getElementById("cooldownVal"),
  liveMoments: document.getElementById("liveMoments"),
  allMoments: document.getElementById("allMoments"),
  btnClearMoments: document.getElementById("btnClearMoments"),
  settingsCollector: document.getElementById("settingsCollector"),
  deviceId: document.getElementById("deviceId"),
  btnSaveSettings: document.getElementById("btnSaveSettings"),
  settingsStatus: document.getElementById("settingsStatus"),
  imageModal: document.getElementById("imageModal"),
  modalImage: document.getElementById("modalImage"),
  modalClose: document.getElementById("modalClose"),
};

const camera = new CameraTracker({
  video: els.cameraVideo,
  motionCanvas: els.motionCanvas,
  captureCanvas: els.captureCanvas,
  overlay: els.cameraOverlay,
  badge: els.cameraBadge,
  badgeText: els.cameraBadgeText,
  onStatus: (msg, isError) => setCameraStatus(msg, isError),
  onMoment: (moment) => {
    renderMomentCard(els.liveMoments, moment, true);
    renderAllMoments();
    updateMomentStat();
  },
  getMetadata: () => buildMomentMetadata(),
});

function init() {
  applySettings();
  setupNav();
  setupGeo();
  setupTowers();
  setupCamera();
  setupMoments();
  setupSettings();
  updateMomentStat();
  renderAllMoments();
}

function applySettings() {
  const defaultCollector =
    window.location.port === "8080"
      ? `${window.location.origin}/api`
      : "http://localhost:8787";
  const url = state.settings.collectorUrl || defaultCollector;
  els.collectorUrl.value = url;
  els.settingsCollector.value = url;
  els.deviceId.value = state.settings.deviceId || `web-${navigator.userAgent.includes("Mobile") ? "mobile" : "desktop"}`;
}

function setupNav() {
  els.navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.section;
      els.sections.forEach((s) => s.classList.toggle("active", s.id === id));
      els.navButtons.forEach((b) => b.classList.toggle("active", b === btn));
    });
  });
}

function setupGeo() {
  if (!navigator.geolocation) {
    els.geoStatus.textContent = "Geolocation not supported.";
    return;
  }

  navigator.geolocation.watchPosition(
    (pos) => {
      state.geo.lat = pos.coords.latitude;
      state.geo.lon = pos.coords.longitude;
      state.geo.accuracy = pos.coords.accuracy;
      els.geoLat.textContent = state.geo.lat.toFixed(6);
      els.geoLon.textContent = state.geo.lon.toFixed(6);
      els.geoAcc.textContent = `${Math.round(state.geo.accuracy)} m`;
      els.geoStatus.textContent = "GPS active — moments will include location.";
      els.mapLink.href = `https://www.openstreetmap.org/?mlat=${state.geo.lat}&mlon=${state.geo.lon}#map=16/${state.geo.lat}/${state.geo.lon}`;
    },
    (err) => {
      els.geoStatus.textContent = `GPS error: ${err.message}`;
      els.geoStatus.classList.add("error");
    },
    { enableHighAccuracy: true, maximumAge: 10000 }
  );
}

function setupTowers() {
  els.btnRefreshTowers.addEventListener("click", refreshTowers);
  setInterval(refreshTowers, 15000);
}

async function refreshTowers() {
  const url = els.collectorUrl.value.trim();
  if (!url) {
    setTowerStatus("Collector URL enter karo.", true);
    return;
  }

  try {
    setTowerStatus("Fetching tower data...");
    const data = await fetchTowers(url);
    state.towers = renderTowerList(els.towerList, data);
    const summary = summarizeTowers(state.towers);
    els.statTowers.textContent = summary.towerCount;
    els.statDevices.textContent = summary.deviceCount;
    setTowerStatus(`Updated — ${summary.towerCount} tower(s), ${summary.deviceCount} device(s).`);
  } catch (err) {
    setTowerStatus(`Collector error: ${err.message}`, true);
  }
}

function setupCamera() {
  els.btnStartCamera.addEventListener("click", async () => {
    try {
      await camera.start();
      els.btnStartCamera.disabled = true;
      els.btnStopCamera.disabled = false;
      els.btnCapture.disabled = false;
      els.btnSwitchCam.disabled = false;
    } catch {
      /* status already set */
    }
  });

  els.btnStopCamera.addEventListener("click", () => {
    camera.stop();
    els.btnStartCamera.disabled = false;
    els.btnStopCamera.disabled = true;
    els.btnCapture.disabled = true;
    els.btnSwitchCam.disabled = true;
  });

  els.btnCapture.addEventListener("click", () => camera.captureMoment("manual"));
  els.btnSwitchCam.addEventListener("click", () => camera.switchCamera());

  els.motionDetect.addEventListener("change", (e) => camera.setMotionEnabled(e.target.checked));
  els.sensitivity.addEventListener("input", (e) => {
    camera.setSensitivity(e.target.value);
    els.sensitivityVal.textContent = e.target.value;
  });
  els.cooldown.addEventListener("input", (e) => {
    camera.setCooldown(e.target.value);
    els.cooldownVal.textContent = e.target.value;
  });
}

function setupMoments() {
  els.btnClearMoments.addEventListener("click", () => {
    if (!confirm("Saare moments delete karne hain?")) return;
    clearMoments();
    els.allMoments.innerHTML = "";
    els.liveMoments.innerHTML = "";
    updateMomentStat();
  });

  els.modalClose.addEventListener("click", () => els.imageModal.classList.remove("open"));
  els.imageModal.addEventListener("click", (e) => {
    if (e.target === els.imageModal) els.imageModal.classList.remove("open");
  });
}

function setupSettings() {
  els.btnSaveSettings.addEventListener("click", () => {
    state.settings = {
      collectorUrl: els.settingsCollector.value.trim(),
      deviceId: els.deviceId.value.trim(),
    };
    saveSettings(state.settings);
    applySettings();
    els.settingsStatus.textContent = "Settings saved.";
    refreshTowers();
  });
}

function buildMomentMetadata() {
  const meta = {
    lat: state.geo.lat,
    lon: state.geo.lon,
    accuracy_m: state.geo.accuracy,
    deviceId: els.deviceId.value.trim(),
  };

  if (els.linkTower.checked && state.towers.length) {
    const top = state.towers[0];
    const t = top.tower || {};
    meta.tower = {
      mcc: t.mcc,
      mnc: t.mnc,
      lac: t.lac,
      cid: t.cid,
      operator: t.operator,
      observed_devices: top.observed_devices,
      load_percent: top.estimate?.load_percent,
    };
  }

  return meta;
}

function renderMomentCard(container, moment, prepend = false) {
  const card = document.createElement("div");
  card.className = "moment-card";
  const towerLine = moment.tower
    ? `${moment.tower.operator || "Tower"} · ${moment.tower.observed_devices ?? "?"} devices`
    : moment.trigger;

  card.innerHTML = `
    <img src="${moment.image}" alt="Moment ${moment.id}" loading="lazy" />
    <div class="moment-meta">
      <div>${formatTime(moment.capturedAt)}</div>
      <div>${towerLine}</div>
    </div>
  `;

  card.addEventListener("click", () => {
    els.modalImage.src = moment.image;
    els.imageModal.classList.add("open");
  });

  if (prepend && container.firstChild) {
    container.insertBefore(card, container.firstChild);
  } else {
    container.appendChild(card);
  }

  while (container.children.length > 12) {
    container.removeChild(container.lastChild);
  }
}

function renderAllMoments() {
  const moments = loadMoments();
  els.allMoments.innerHTML = "";
  moments.forEach((m) => renderMomentCard(els.allMoments, m));
  els.liveMoments.innerHTML = "";
  moments.slice(0, 6).forEach((m) => renderMomentCard(els.liveMoments, m));
}

function updateMomentStat() {
  els.statMoments.textContent = loadMoments().length;
}

function setTowerStatus(msg, isError = false) {
  els.towerStatus.textContent = msg;
  els.towerStatus.classList.toggle("error", isError);
}

function setCameraStatus(msg, isError = false) {
  els.cameraStatus.textContent = msg;
  els.cameraStatus.classList.toggle("error", isError);
}

init();
