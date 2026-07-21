export async function fetchTowers(collectorUrl) {
  const base = collectorUrl.replace(/\/$/, "");
  const res = await fetch(`${base}/towers`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Collector returned ${res.status}`);
  return res.json();
}

export async function reportDevice(collectorUrl, payload) {
  const base = collectorUrl.replace(/\/$/, "");
  const res = await fetch(`${base}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Report failed: ${res.status}`);
  return res.json();
}

export function renderTowerList(container, data) {
  container.innerHTML = "";
  const towers = data.towers || [];

  if (!towers.length) {
    container.innerHTML = '<div class="status-bar">Abhi koi tower data nahi. Collector + phone report chalao.</div>';
    return towers;
  }

  towers.forEach((item) => {
    const t = item.tower || {};
    const est = item.estimate || {};
    const div = document.createElement("div");
    div.className = "tower-item";
    const congestion = est.congestion || "Unknown";
    const badgeClass =
      congestion === "Low" ? "badge-low" : congestion.includes("High") ? "badge-high" : "badge-med";

    div.innerHTML = `
      <strong>${t.operator || "Unknown"} · ${t.radio || "LTE"}</strong>
      <div class="meta">MCC/MNC: ${t.mcc}/${t.mnc} · LAC: ${t.lac} · CID: ${t.cid}</div>
      <div class="meta">
        Observed devices: <strong>${item.observed_devices ?? 0}</strong>
        &nbsp;·&nbsp;
        Est. load: <span class="badge ${badgeClass}">${est.load_percent ?? "?"}% ${congestion}</span>
      </div>
      <div class="meta">Est. total devices: ~${est.device_range || "—"}</div>
      <div class="meta">IDs: ${(item.device_ids || []).join(", ") || "—"}</div>
    `;
    container.appendChild(div);
  });

  return towers;
}

export function summarizeTowers(towers) {
  let devices = 0;
  towers.forEach((t) => {
    devices += t.observed_devices || 0;
  });
  return { towerCount: towers.length, deviceCount: devices };
}
