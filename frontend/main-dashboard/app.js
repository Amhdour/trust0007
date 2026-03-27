const root = document.getElementById("dashboard-root");
const tabStrip = document.getElementById("tab-strip");
const heroMeta = document.getElementById("hero-meta");
const heroSteps = document.getElementById("hero-steps");
const sourcesRoot = document.getElementById("sources");
const liveLogRoot = document.getElementById("live-log-root");
const resetDashboardButton = document.getElementById("reset-dashboard-button");

const LIVE_LOG_LIMIT = 12;
const DEFAULT_LIVE_LOG_POLL_MS = 5000;
let liveLogTimer = 0;
let lastDashboardPayload = null;

const LANDING_STEPS = [
  "Business overview",
  "User access",
  "AI operations",
  "Evidence and reports",
];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function statusClass(status) {
  return `status-pill status-${status || "neutral"}`;
}

function formatTimestamp(value) {
  if (!value) {
    return "Timestamp unavailable";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }

  return parsed.toLocaleString();
}

function renderHero(payload) {
  heroMeta.innerHTML = `
    <span class="chip">${escapeHtml(payload.runtime_module)}</span>
    <span class="chip">Generated ${escapeHtml(new Date(payload.generated_at).toLocaleString())}</span>
  `;

  heroSteps.innerHTML = LANDING_STEPS.map(
    (label, index) => `
      <article class="step-card">
        <span class="step-index">${index + 1}</span>
        <span class="step-label">${escapeHtml(label)}</span>
      </article>
    `,
  ).join("");
}

function renderResetState() {
  heroMeta.innerHTML = "";
  heroSteps.innerHTML = "";

  const linkSections = Array.isArray(lastDashboardPayload?.sections)
    ? lastDashboardPayload.sections
        .map((section) => {
          const linkBlocks = Array.isArray(section.blocks)
            ? section.blocks.filter((block) => block.type === "links")
            : [];
          return linkBlocks.length ? { ...section, blocks: linkBlocks } : null;
        })
        .filter(Boolean)
    : [];

  const resetTabs = linkSections.map((section) => ({
    id: section.id,
    label: section.title,
  }));

  if (resetTabs.length) {
    renderTabs(resetTabs);
  } else {
    tabStrip.innerHTML = "";
  }

  if (Array.isArray(lastDashboardPayload?.sources)) {
    renderSources(lastDashboardPayload.sources);
  } else {
    sourcesRoot.innerHTML = "";
  }

  if (liveLogRoot) {
    liveLogRoot.innerHTML = `
      <section class="loading-panel">
        <p class="eyebrow">Reset</p>
        <h3>Live log cleared</h3>
        <p>No recent activity is currently shown.</p>
      </section>
    `;
  }

  if (linkSections.length) {
    root.innerHTML = `
      <section class="loading-panel">
        <p class="eyebrow">Reset</p>
        <h2>Dashboard data cleared</h2>
        <p>Business metrics were removed, but useful links and source URLs remain available below.</p>
      </section>
      ${linkSections
        .map(
          (section) => `
            <section class="dashboard-section" id="${escapeHtml(section.id)}">
              <div class="section-head">
                <p class="eyebrow">${escapeHtml(section.id)}</p>
                <h2>${escapeHtml(section.title)}</h2>
                <p class="section-description">${escapeHtml(section.description)}</p>
              </div>
              ${renderBlocks(section.blocks)}
            </section>
          `,
        )
        .join("")}
    `;
    return;
  }

  root.innerHTML = `
    <section class="loading-panel">
      <p class="eyebrow">Reset</p>
      <h2>Dashboard cleared</h2>
      <p>All rendered control-plane data has been removed from the page.</p>
    </section>
  `;
}

function renderTabs(tabs) {
  tabStrip.innerHTML = tabs
    .map(
      (tab) => `
        <button class="tab-button" type="button" data-target="${escapeHtml(tab.id)}">
          ${escapeHtml(tab.label)}
        </button>
      `,
    )
    .join("");

  for (const button of tabStrip.querySelectorAll("button")) {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.target);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }
}

function renderCards(items) {
  return `
    <div class="cards-grid">
      ${items
        .map(
          (item) => `
            <article class="metric-card">
              <div class="metric-label">${escapeHtml(item.label)}</div>
              <div class="metric-value">${escapeHtml(item.value)}</div>
              <div class="metric-detail">${escapeHtml(item.detail)}</div>
              <div class="${statusClass(item.status)}">${escapeHtml(item.status || "neutral")}</div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderRecords(items) {
  return `
    <div class="records-grid">
      ${items
        .map(
          (item) => `
            <article class="record-card">
              <h3>${escapeHtml(item.title)}</h3>
              <p class="record-meta">${escapeHtml(item.meta)}</p>
              <p class="record-detail">${escapeHtml(item.detail)}</p>
              <div class="${statusClass(item.status)}">${escapeHtml(item.status || "neutral")}</div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderTable(block) {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            ${block.columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${block.rows
            .map(
              (row) => `
                <tr>
                  ${block.columns.map((column) => `<td>${escapeHtml(row[column.key] ?? "")}</td>`).join("")}
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderLinks(items, className = "link-grid") {
  return `
    <div class="${className}">
      ${items
        .map(
          (item) => `
            <a class="link-card" href="${escapeHtml(item.href)}" target="_blank" rel="noreferrer">
              <div class="${statusClass(item.status)}">${escapeHtml(item.status || "neutral")}</div>
              <h3>${escapeHtml(item.label)}</h3>
              <p class="link-description">${escapeHtml(item.description)}</p>
            </a>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderBlocks(blocks) {
  return blocks
    .map((block) => {
      let content = "";
      if (block.type === "cards") {
        content = renderCards(block.items);
      } else if (block.type === "records") {
        content = renderRecords(block.items);
      } else if (block.type === "table") {
        content = renderTable(block);
      } else if (block.type === "links") {
        content = renderLinks(block.items);
      }

      return `
        <section class="block">
          <h3 class="block-title">${escapeHtml(block.title)}</h3>
          ${content}
        </section>
      `;
    })
    .join("");
}

function renderSections(sections) {
  root.innerHTML = sections
    .map(
      (section) => `
        <section class="dashboard-section" id="${escapeHtml(section.id)}">
          <div class="section-head">
            <p class="eyebrow">${escapeHtml(section.id)}</p>
            <h2>${escapeHtml(section.title)}</h2>
            <p class="section-description">${escapeHtml(section.description)}</p>
          </div>
          ${renderBlocks(section.blocks)}
        </section>
      `,
    )
    .join("");
}

function renderSources(sources) {
  sourcesRoot.innerHTML = sources
    .map(
      (source) => `
        <a class="source-card" href="${escapeHtml(source.href)}" target="_blank" rel="noreferrer">
          <h3>${escapeHtml(source.label)}</h3>
          <p class="source-description">${escapeHtml(source.description)}</p>
        </a>
      `,
    )
    .join("");
}

function renderLiveLog(payload) {
  if (!liveLogRoot) {
    return;
  }

  const entries = Array.isArray(payload.entries) ? payload.entries : [];
  const refreshedAt = formatTimestamp(payload.generated_at);
  const intervalSeconds = Math.max(1, Math.round((payload.poll_interval_ms || DEFAULT_LIVE_LOG_POLL_MS) / 1000));

  liveLogRoot.innerHTML = `
    <div class="live-log-toolbar">
      <div class="hero-meta">
        <span class="chip">Auto-refresh ${intervalSeconds}s</span>
        <span class="chip">Last updated ${escapeHtml(refreshedAt)}</span>
        <span class="chip">${escapeHtml(String(entries.length))} recent items</span>
      </div>
      <a class="live-log-source" href="${escapeHtml(payload.source_href || "/raw/telemetry/exports/sample_events.jsonl")}" target="_blank" rel="noreferrer">
        Open activity feed
      </a>
    </div>
    <div class="live-log-list">
      ${
        entries.length
          ? entries
              .map(
                (entry) => `
                  <article class="live-log-entry">
                    <div class="live-log-entry-head">
                      <div class="live-log-title-row">
                        ${
                          entry.source_label
                            ? `<span class="live-log-meta-chip">${escapeHtml(entry.source_label)}</span>`
                            : ""
                        }
                        <span class="${statusClass(entry.status)}">${escapeHtml(entry.severity || "info")}</span>
                        <h3>${escapeHtml(entry.event_type || "event")}</h3>
                      </div>
                      <time class="live-log-time">${escapeHtml(formatTimestamp(entry.timestamp))}</time>
                    </div>
                    <p class="live-log-summary">${escapeHtml(entry.summary || "No event summary available.")}</p>
                    <div class="live-log-meta-row">
                      ${
                        entry.request_id
                          ? `<span class="live-log-meta-chip">request ${escapeHtml(entry.request_id)}</span>`
                          : ""
                      }
                      ${
                        entry.trace_id
                          ? `<span class="live-log-meta-chip">trace ${escapeHtml(entry.trace_id)}</span>`
                          : ""
                      }
                      ${
                        entry.tenant_id
                          ? `<span class="live-log-meta-chip">tenant ${escapeHtml(entry.tenant_id)}</span>`
                          : ""
                      }
                    </div>
                  </article>
                `,
              )
              .join("")
          : `
            <article class="live-log-entry live-log-empty">
              <h3>No recent activity yet</h3>
              <p class="live-log-summary">New requests, alerts, and operating events will appear here.</p>
            </article>
          `
      }
    </div>
  `;
}

function renderLiveLogError(error) {
  if (!liveLogRoot) {
    return;
  }

  liveLogRoot.innerHTML = `
    <section class="loading-panel">
      <p class="eyebrow">Unavailable</p>
      <h3>Recent activity could not load</h3>
      <p>${escapeHtml(error.message || "Unknown error")}</p>
    </section>
  `;
}

function scheduleLiveLogRefresh(intervalMs) {
  window.clearTimeout(liveLogTimer);
  liveLogTimer = window.setTimeout(loadLiveLog, intervalMs);
}

async function loadLiveLog() {
  try {
    const response = await fetch(`/api/control-plane/live-log?limit=${LIVE_LOG_LIMIT}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Live log API returned ${response.status}`);
    }

    const payload = await response.json();
    renderLiveLog(payload);
    scheduleLiveLogRefresh(payload.poll_interval_ms || DEFAULT_LIVE_LOG_POLL_MS);
  } catch (error) {
    renderLiveLogError(error);
    scheduleLiveLogRefresh(DEFAULT_LIVE_LOG_POLL_MS);
  }
}

async function boot() {
  try {
    const response = await fetch("/api/control-plane/overview", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Dashboard API returned ${response.status}`);
    }

    const payload = await response.json();
    lastDashboardPayload = payload;
    renderHero(payload);
    renderTabs(payload.tabs);
    renderSections(payload.sections);
    renderSources(payload.sources);
  } catch (error) {
    root.innerHTML = `
      <section class="loading-panel">
        <p class="eyebrow">Unavailable</p>
        <h2>Dashboard could not load</h2>
        <p>${escapeHtml(error.message || "Unknown error")}</p>
      </section>
    `;
  }
}

async function resetDashboard() {
  if (resetDashboardButton) {
    resetDashboardButton.disabled = true;
    resetDashboardButton.textContent = "Resetting...";
  }

  window.clearTimeout(liveLogTimer);
  renderResetState();
  window.scrollTo({ top: 0, behavior: "smooth" });

  if (resetDashboardButton) {
    resetDashboardButton.disabled = false;
    resetDashboardButton.textContent = "Reset dashboard";
  }
}

if (resetDashboardButton) {
  resetDashboardButton.addEventListener("click", () => {
    resetDashboard();
  });
}

boot();
loadLiveLog();
