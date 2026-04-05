// ============================================================================
// TWITTER/X VIDEO DOWNLOADER — FRONTEND
// ============================================================================

const API_BASE = "/api/v1";

let currentVideoInfo = null;
let selectedFormat = null;
let statusCheckInterval = null;
let activeTasksInterval = null;
let isDownloading = false;
let currentTaskId = null;

const videoUrlInput = document.getElementById("videoUrl");
const extractBtn = document.getElementById("extractBtn");
const extractLabel = extractBtn?.querySelector(".extract-label");
const pasteBtn = document.getElementById("pasteBtn");
const urlError = document.getElementById("urlError");
const videoInfoSection = document.getElementById("videoInfoSection");
const formatSection = document.getElementById("formatSection");
const progressSection = document.getElementById("progressSection");
const tasksSection = document.getElementById("tasksSection");
const tabSwitcher = document.querySelector(".tab-switcher");
const mobileDownloadDock = document.getElementById("mobileDownloadDock");

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadActiveTasks();
  activeTasksInterval = setInterval(loadActiveTasks, 5000);
  window.addEventListener("resize", () => {
    if (currentVideoInfo) syncMobileDownloadDock();
  });
});

function setupEventListeners() {
  extractBtn.addEventListener("click", handleExtractInfo);

  videoUrlInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleExtractInfo();
  });

  pasteBtn?.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text?.trim()) {
        videoUrlInput.value = text.trim();
        videoUrlInput.focus();
      }
    } catch {
      showError("Could not read clipboard. Paste manually (Ctrl+V).");
    }
  });

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const tab = e.currentTarget.dataset.tab;
      switchTab(tab, e.currentTarget);
    });
  });

  formatSection?.addEventListener("click", (e) => {
    const btn = e.target.closest(".format-download-btn");
    if (!btn || btn.disabled) return;
    const formatId = btn.dataset.formatId;
    const quality = btn.dataset.quality || "";
    const type = btn.dataset.formatType || "video";
    if (!formatId) return;
    startDownload(formatId, quality, type, btn);
  });

  videoInfoSection?.addEventListener(
    "error",
    (e) => {
      const img = e.target;
      if (img?.matches?.("img.media-thumb")) {
        const wrap = document.createElement("div");
        wrap.className = "media-thumb-placeholder";
        wrap.innerHTML = '<i data-lucide="image-off"></i>';
        img.replaceWith(wrap);
        if (window.lucide) lucide.createIcons();
      }
    },
    true,
  );

  videoInfoSection?.addEventListener("click", (e) => {
    if (e.target.closest(".btn-copy-link")) {
      const url = videoUrlInput.value.trim();
      if (!url) return;
      navigator.clipboard.writeText(url).then(
        () => {
          const el = e.target.closest(".btn-copy-link");
          if (el) {
            const t = el.querySelector(".copy-label");
            if (t) {
              const prev = t.textContent;
              t.textContent = "Copied!";
              setTimeout(() => {
                t.textContent = prev;
              }, 1600);
            }
          }
        },
        () => showError("Could not copy to clipboard."),
      );
    }
    if (e.target.closest(".btn-share-link")) {
      const url = videoUrlInput.value.trim();
      if (!url) return;
      if (navigator.share) {
        navigator.share({ title: "X post", url }).catch(() => {});
      } else {
        navigator.clipboard.writeText(url).catch(() => {});
      }
    }
  });
}

function isValidTwitterUrl(url) {
  const patterns = [
    /twitter\.com\/\w+\/status\/\d+/,
    /x\.com\/\w+\/status\/\d+/,
    /twitter\.com\/i\/web\/status\/\d+/,
    /x\.com\/i\/web\/status\/\d+/,
  ];
  return patterns.some((p) => p.test(url));
}

function showError(message) {
  urlError.textContent = message;
  urlError.classList.add("show");
}

function clearError() {
  urlError.textContent = "";
  urlError.classList.remove("show");
}

async function handleExtractInfo() {
  const url = videoUrlInput.value.trim();

  if (!url || !isValidTwitterUrl(url)) {
    showError(
      "Invalid X/Twitter URL. Use: https://x.com/user/status/123… or twitter.com/…",
    );
    return;
  }

  clearError();
  extractBtn.disabled = true;
  extractBtn.classList.add("is-loading");
  if (extractLabel) extractLabel.textContent = "Loading…";

  const commandCenter = document.getElementById("commandCenter");
  commandCenter?.classList.add("is-fetching");
  if (formatSection.style.display === "block") showFormatsSkeleton();

  try {
    const res = await fetch(`${API_BASE}/info?url=${encodeURIComponent(url)}`, {
      method: "POST",
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Failed to extract video info");
    }

    currentVideoInfo = await res.json();
    displayVideoInfo(currentVideoInfo);
    displayFormats(currentVideoInfo);

    videoInfoSection.style.display = "block";
    formatSection.style.display = "block";
  } catch (e) {
    showError(`Error: ${e.message}`);
  } finally {
    extractBtn.disabled = false;
    extractBtn.classList.remove("is-loading");
    if (extractLabel) extractLabel.textContent = "Download";
    document.getElementById("commandCenter")?.classList.remove("is-fetching");
    if (window.lucide) lucide.createIcons();
  }
}

function showFormatsSkeleton() {
  const sk =
    '<div class="skeleton-grid"><div class="skeleton-card"></div><div class="skeleton-card"></div><div class="skeleton-card"></div></div>';
  const vf = document.getElementById("videoFormats");
  const af = document.getElementById("audioFormats");
  if (vf) vf.innerHTML = sk;
  if (af) af.innerHTML = sk;
}

function safeHttpUrl(href) {
  if (!href || typeof href !== "string") return "";
  try {
    const u = new URL(href.trim());
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : "";
  } catch {
    return "";
  }
}

function pickThumbnailUrl(info) {
  const primary = safeHttpUrl(info.thumbnail);
  if (primary) return primary;
  const list = info.thumbnails;
  if (!Array.isArray(list)) return "";
  let best = "";
  let bestArea = 0;
  for (const t of list) {
    if (!t || typeof t !== "object") continue;
    const u = safeHttpUrl(t.url);
    if (!u) continue;
    const w = Number(t.width) || 0;
    const h = Number(t.height) || 0;
    const area = w && h ? w * h : Math.max(w, h, 1);
    if (area > bestArea) {
      bestArea = area;
      best = u;
    }
  }
  return best;
}

function isBareUrlText(s) {
  const t = (s || "").trim();
  return t.length > 0 && /^https?:\/\/\S+$/i.test(t);
}

function displayVideoInfo(info) {
  const thumbSrc = pickThumbnailUrl(info);
  const thumb = thumbSrc
    ? `<img class="media-thumb" src="${escapeAttr(thumbSrc)}" alt="" loading="lazy" decoding="async" width="640" height="360" referrerpolicy="no-referrer">`
    : `<div class="media-thumb-placeholder"><i data-lucide="image-off"></i></div>`;

  const descRaw = (info.description || "").trim();
  const skipDesc = !descRaw || isBareUrlText(descRaw);
  const desc = skipDesc
    ? ""
    : descRaw.length > 220
      ? `${escapeHtml(descRaw.slice(0, 220))}…`
      : escapeHtml(descRaw);
  const descBlock = desc
    ? `<div class="media-desc">${desc}</div>`
    : "";

  const videoDetails = `
    <div class="media-card media-card--details animate-in">
      <div class="media-thumb-wrap">
        ${thumb}
        <div class="media-play-overlay">
          <div class="media-play-btn" aria-hidden="true">
            <i data-lucide="play"></i>
          </div>
        </div>
      </div>
      <div class="media-meta">
        <h3 class="media-title media-title--single">${escapeHtml(info.title || "Tweet media")}</h3>
        <dl class="media-facts">
          <div class="media-fact"><dt>Uploader</dt><dd>${escapeHtml(info.uploader || "—")}</dd></div>
          <div class="media-fact"><dt>Duration</dt><dd>${escapeHtml(info.duration_string || "—")}</dd></div>
          <div class="media-fact"><dt>Upload date</dt><dd>${info.upload_date ? escapeHtml(formatDate(info.upload_date)) : "—"}</dd></div>
        </dl>
        <div class="media-actions">
          <button type="button" class="btn-media-action btn-copy-link">
            <i data-lucide="copy"></i>
            <span class="copy-label">Copy link</span>
          </button>
          <button type="button" class="btn-media-action btn-share-link">
            <i data-lucide="share-2"></i>
            Share
          </button>
        </div>
        ${descBlock}
      </div>
    </div>
  `;
  document.getElementById("videoInfo").innerHTML = videoDetails;
  if (window.lucide) lucide.createIcons();
}

function formatDate(dateStr) {
  if (!dateStr || dateStr.length < 8) return dateStr;
  const year = dateStr.substring(0, 4);
  const month = dateStr.substring(4, 6);
  const day = dateStr.substring(6, 8);
  return `${month}/${day}/${year}`;
}

const MAX_FORMAT_CARDS = 4;

function pickDisplayVideoFormats(list) {
  if (!list?.length) return [];
  const ranked = [...list].sort(
    (a, b) => (b.height || 0) - (a.height || 0) || (b.filesize || 0) - (a.filesize || 0),
  );
  const seen = new Set();
  const out = [];
  for (const f of ranked) {
    const h = f.height || 0;
    const key = h > 0 ? `h:${h}` : `id:${f.format_id || out.length}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(f);
    if (out.length >= MAX_FORMAT_CARDS) break;
  }
  return out;
}

function pickDisplayAudioFormats(list) {
  if (!list?.length) return [];
  const ranked = [...list].sort(
    (a, b) => (Number(b.abr) || 0) - (Number(a.abr) || 0) || (b.filesize || 0) - (a.filesize || 0),
  );
  const seen = new Set();
  const out = [];
  for (const f of ranked) {
    const fid = f.format_id || "";
    if (!fid || seen.has(fid)) continue;
    seen.add(fid);
    out.push(f);
    if (out.length >= MAX_FORMAT_CARDS) break;
  }
  return out;
}

function friendlyVideoTitle(format) {
  const h = format.height || 0;
  if (h >= 1080) return `${h}p · Full HD`;
  if (h >= 720) return `${h}p · HD`;
  if (h >= 480) return `${h}p`;
  if (h > 0) return `${h}p · Data saver`;
  return "Best available";
}

function friendlyAudioTitle(format) {
  const abr = Number(format.abr) || 0;
  if (abr >= 256) return "High quality audio";
  if (abr >= 128) return "Balanced audio";
  if (abr > 0) return `${Math.round(abr)} kbps audio`;
  return "Audio track";
}

function displayFormats(info) {
  const vids = pickDisplayVideoFormats(info.video_formats || []);
  const videoFormatsHtml = vids
    .map((f, i) => createFormatCard(f, "video", i, vids, i === 0))
    .join("");
  const vf = document.getElementById("videoFormats");
  if (vf) {
    vf.innerHTML =
      videoFormatsHtml ||
      '<p class="empty-formats">No video formats available.</p>';
  }

  const auds = pickDisplayAudioFormats(info.audio_formats || []);
  const audioFormatsHtml = auds
    .map((f, i) => createFormatCard(f, "audio", i, auds, i === 0))
    .join("");
  const af = document.getElementById("audioFormats");
  if (af) {
    af.innerHTML =
      audioFormatsHtml ||
      '<p class="empty-formats">No audio formats available.</p>';
  }

  syncMobileDownloadDock();
  if (window.lucide) lucide.createIcons();
}

function syncMobileDownloadDock() {
  if (!mobileDownloadDock) return;
  if (window.innerWidth >= 768) {
    mobileDownloadDock.style.display = "none";
    mobileDownloadDock.innerHTML = "";
    return;
  }
  const recBtn = document.querySelector(
    "#videoFormats .quality-card.recommended .format-download-btn",
  );
  mobileDownloadDock.innerHTML = "";
  if (!recBtn || formatSection.style.display === "none") {
    mobileDownloadDock.style.display = "none";
    return;
  }
  const clone = recBtn.cloneNode(true);
  clone.addEventListener("click", () => recBtn.click());
  mobileDownloadDock.appendChild(clone);
  mobileDownloadDock.style.display = "block";
  if (window.lucide) lucide.createIcons();
}

function qualityBarPercent(format, type) {
  if (type !== "video" || !format.height) return 45;
  return Math.min(100, Math.round((format.height / 1080) * 100));
}

function audioTierClass(formats, format, index) {
  if (format.recommended) return "audio-tier-high";
  const n = formats.length;
  if (n <= 1) return "audio-tier-high";
  if (index === 0) return "audio-tier-low";
  if (index === n - 1) return "audio-tier-high";
  return "audio-tier-mid";
}

function createFormatCard(format, type, index, allOfType, isRecommendedFlag) {
  const isRecommended =
    typeof isRecommendedFlag === "boolean" ? isRecommendedFlag : !!format.recommended;
  const filesize = format.estimated_size || "—";
  const ext = (format.ext || "mp4").toUpperCase();
  const formatId = format.format_id || "";
  const disabled = !formatId;
  const barPct = qualityBarPercent(format, type);
  const tierClass =
    type === "audio" ? audioTierClass(allOfType, format, index) : "";

  const mainTitle =
    type === "video"
      ? friendlyVideoTitle(format)
      : friendlyAudioTitle(format);
  const sizeKnown = filesize && filesize !== "Unknown" && filesize !== "—";
  const subLine = sizeKnown
    ? `${ext} · ${filesize}`
    : `${ext} · Size after download`;

  const wave =
    type === "audio"
      ? `<div class="audio-wave-icon audio-wave-icon--compact" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></div>`
      : "";

  const pickBadge = isRecommended
    ? `<div class="quality-pick-strip"><i data-lucide="star"></i><span>Recommended</span></div>`
    : "";

  const iconName = type === "video" ? "download" : "headphones";
  let btnInner = "";
  if (disabled) {
    btnInner = `<span>Unavailable</span>`;
  } else if (isDownloading) {
    btnInner = `<i data-lucide="loader-2" class="animate-spin"></i><span>Please wait…</span>`;
  } else {
    btnInner = `<i data-lucide="${iconName}"></i><span>Download</span>`;
  }

  const btn = `
    <button type="button"
      class="format-download-btn"
      data-format-id="${escapeAttr(formatId)}"
      data-quality="${escapeAttr(format.quality || "")}"
      data-format-type="${type}"
      ${disabled || isDownloading ? "disabled" : ""}>
      ${btnInner}
    </button>`;

  return `
    <div class="quality-card quality-card--simple animate-in ${isRecommended ? "recommended" : ""} ${tierClass}">
      ${pickBadge}
      ${wave}
      <div class="quality-card-simple-inner">
        <div class="quality-simple-label">${type === "video" ? "Resolution" : "Audio"}</div>
        <div class="quality-simple-title">${escapeHtml(mainTitle)}</div>
        <p class="quality-simple-sub">${escapeHtml(subLine)}</p>
        <div class="quality-meter quality-meter--compact" aria-hidden="true">
          <div class="quality-meter-fill" style="width: ${barPct}%"></div>
        </div>
      </div>
      ${btn}
    </div>
  `;
}

function escapeAttr(text) {
  if (text == null) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;");
}

async function startDownload(formatId, quality, type, targetBtn) {
  if (isDownloading) {
    showError("A download is already in progress. Please wait.");
    return;
  }

  const originalHtml = targetBtn.innerHTML;

  try {
    isDownloading = true;
    currentTaskId = null;

    targetBtn.disabled = true;
    targetBtn.innerHTML =
      '<i data-lucide="loader-2" class="animate-spin"></i><span>Downloading…</span>';
    if (window.lucide) lucide.createIcons();

    const res = await fetch(`${API_BASE}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: videoUrlInput.value.trim(),
        format_id: formatId,
        quality: quality,
      }),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Request failed");
    }

    const response = await res.json();
    currentTaskId = response.task_id;

    progressSection.style.display = "block";
    progressSection.scrollIntoView({ behavior: "smooth", block: "start" });
    startStatusCheck(currentTaskId);
  } catch (e) {
    showError(`Error: ${e.message}`);
    isDownloading = false;
    targetBtn.disabled = false;
    targetBtn.innerHTML = originalHtml;
    if (window.lucide) lucide.createIcons();
  }
}

function startStatusCheck(taskId) {
  if (statusCheckInterval) clearInterval(statusCheckInterval);

  const check = async () => {
    try {
      const res = await fetch(`${API_BASE}/status/${taskId}`);
      if (!res.ok) throw new Error("Failed to fetch status");
      const task = await res.json();
      displayTaskProgress(task);

      if (["completed", "failed", "cancelled"].includes(task.status)) {
        clearInterval(statusCheckInterval);
        isDownloading = false;
        if (currentVideoInfo) displayFormats(currentVideoInfo);
      }
    } catch (e) {
      console.error("Status check error:", e);
    }
  };

  check();
  statusCheckInterval = setInterval(check, 3000);
}

function displayTaskProgress(task) {
  const statusBadge = `<span class="status-badge status-${task.status}">${task.status.toUpperCase()}</span>`;

  const progressPercent = Math.min(task.progress || 0, 100);
  const progressBar = `
    <div class="progress-container">
      <div class="progress-label-row">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-weight:600;font-size:0.875rem;">Status</span>
        </div>
        <span style="font-weight:700;font-size:0.875rem;color:var(--tw-blue);">${progressPercent}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width:${progressPercent}%;background:linear-gradient(90deg,var(--tw-blue),#60a5fa);box-shadow:0 0 10px rgba(29,161,242,0.25)"></div>
      </div>
    </div>
  `;

  let actionButtons = "";
  if (task.status === "completed") {
    actionButtons = `
      <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;">
        <button type="button" class="command-btn" onclick="downloadFile('${escapeAttr(task.task_id)}')" style="flex:1;min-width:140px;">
          <i data-lucide="check-circle"></i>
          <span>Save to device</span>
        </button>
        <button type="button" class="command-btn command-btn-secondary" onclick="newDownload()" style="flex:1;min-width:140px;">
          <i data-lucide="refresh-cw"></i>
          <span>New extraction</span>
        </button>
      </div>`;
  } else if (["processing", "pending"].includes(task.status)) {
    actionButtons = `
      <div style="margin-top:8px;">
        <button type="button" class="command-btn command-btn-danger-outline" onclick="cancelTask('${escapeAttr(task.task_id)}')"
          style="width:100%;">
          <i data-lucide="x-circle"></i>
          <span>Cancel download</span>
        </button>
      </div>`;
  }

  document.getElementById("taskInfo").innerHTML = `
    <div class="task-info">
      <div class="task-card-header">
        <div class="task-card-title">${escapeHtml(task.filename || "Downloading…")}</div>
        ${statusBadge}
      </div>
      ${progressBar}
      <div class="task-status-row">
        <span class="status-label">Message</span>
        <span class="status-value">${escapeHtml(task.message || "Processing…")}</span>
      </div>
      ${
        task.download_speed
          ? `<div class="task-status-row"><span class="status-label">Speed</span><span class="status-value">${escapeHtml(task.download_speed)}</span></div>`
          : ""
      }
      ${
        task.eta && task.eta !== "Unknown"
          ? `<div class="task-status-row"><span class="status-label">ETA</span><span class="status-value">${escapeHtml(task.eta)}</span></div>`
          : ""
      }
      ${
        task.file_size && task.file_size !== "Unknown"
          ? `<div class="task-status-row"><span class="status-label">Size</span><span class="status-value">${escapeHtml(task.file_size)}</span></div>`
          : ""
      }
      ${
        task.error
          ? `<div class="task-status-row" style="color:var(--danger)"><span class="status-label">Error</span><span class="status-value">${escapeHtml(task.error)}</span></div>`
          : ""
      }
      ${actionButtons}
    </div>
  `;
  if (window.lucide) lucide.createIcons();
}

async function loadActiveTasks() {
  try {
    const res = await fetch(`${API_BASE}/tasks`);
    if (!res.ok) return;
    const data = await res.json();
    const tasks = (data.tasks || []).filter(
      (t) => !["completed", "failed", "cancelled"].includes(t.status),
    );

    if (!tasks.length) {
      tasksSection.style.display = "none";
      return;
    }

    tasksSection.style.display = "block";
    document.getElementById("activeTasksList").innerHTML = tasks
      .map((task) => createTaskCard(task))
      .join("");
  } catch (e) {
    console.error("Failed to load active tasks:", e);
  }
}

function createTaskCard(task) {
  const statusBadge = `<span class="status-badge status-${task.status}">${task.status.toUpperCase()}</span>`;
  const progressPercent = Math.min(task.progress || 0, 100);

  return `
    <div class="task-card">
      <div class="task-card-header">
        <div class="task-card-title">${escapeHtml(task.filename || "Download")}</div>
        ${statusBadge}
      </div>
      <div class="progress-bar">
        <div class="progress-fill" style="width:${progressPercent}%"></div>
      </div>
      <div style="font-size:0.85rem;color:var(--text-muted);">${escapeHtml(task.message || "")}</div>
    </div>
  `;
}

async function cancelTask(taskId) {
  if (!confirm("Cancel this download?")) return;

  try {
    const res = await fetch(`${API_BASE}/cancel/${taskId}`, { method: "POST" });
    if (res.ok) {
      clearInterval(statusCheckInterval);
      isDownloading = false;
      if (currentVideoInfo) displayFormats(currentVideoInfo);
      showError("Download cancelled.");
    }
  } catch (e) {
    showError(`Failed to cancel: ${e.message}`);
  }
}

function downloadFile(taskId) {
  window.location.href = `${API_BASE}/download/${taskId}`;
}

function newDownload() {
  videoUrlInput.value = "";
  videoInfoSection.style.display = "none";
  formatSection.style.display = "none";
  progressSection.style.display = "none";
  if (mobileDownloadDock) {
    mobileDownloadDock.style.display = "none";
    mobileDownloadDock.innerHTML = "";
  }
  currentVideoInfo = null;
  selectedFormat = null;
  isDownloading = false;
  currentTaskId = null;
  if (statusCheckInterval) clearInterval(statusCheckInterval);
  clearError();
}

function switchTab(tabName, btn) {
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.remove("active");
  });
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.remove("active");
    b.setAttribute("aria-selected", "false");
  });

  const tabEl = document.getElementById(tabName);
  if (tabEl) tabEl.classList.add("active");

  if (btn) {
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
  }

  if (tabSwitcher) {
    tabSwitcher.dataset.active = tabName === "audio-formats" ? "audio" : "video";
  }
  if (window.lucide) lucide.createIcons();
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

window.addEventListener("beforeunload", () => {
  if (statusCheckInterval) clearInterval(statusCheckInterval);
  if (activeTasksInterval) clearInterval(activeTasksInterval);
});
