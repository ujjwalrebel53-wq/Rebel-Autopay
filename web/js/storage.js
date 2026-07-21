const STORAGE_KEY = "tower_intel_moments";
const SETTINGS_KEY = "tower_intel_settings";

export function loadSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
  } catch {
    return {};
  }
}

export function saveSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export function loadMoments() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

export function saveMoments(moments) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(moments.slice(0, 200)));
}

export function addMoment(moment) {
  const moments = loadMoments();
  moments.unshift(moment);
  saveMoments(moments);
  return moments;
}

export function clearMoments() {
  localStorage.removeItem(STORAGE_KEY);
}

export function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { hour12: true });
}

export function congestionBadge(level) {
  const map = {
    Low: "badge-low",
    Medium: "badge-med",
    "Very High": "badge-high",
    High: "badge-high",
  };
  return map[level] || "badge-med";
}
