const root = document.getElementById("dashboard-root");
const tabStrip = document.getElementById("tab-strip");
const heroTitle = document.getElementById("hero-title");
const heroCopy = document.getElementById("hero-copy");
const heroMeta = document.getElementById("hero-meta");
const heroSteps = document.getElementById("hero-steps");
const briefingRoot = document.getElementById("briefing-root");
const kpiRoot = document.getElementById("kpi-root");
const readinessRoot = document.getElementById("readiness-root");
const sourcesRoot = document.getElementById("sources");
const liveLogRoot = document.getElementById("live-log-root");
const refreshDashboardButton = document.getElementById("refresh-dashboard-button");

const LIVE_LOG_LIMIT = 12;
const DEFAULT_LIVE_LOG_POLL_MS = 5000;
let liveLogTimer = 0;

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

function isInternalHref(href) {
  return String(href || "").startsWith("#");
}

function linkAttributes(href) {
  if (!href) {
    return "";
  }
  if (isInternalHref(href)) {
    return ` href="${escapeHtml(href)}"`;
  }
  return ` href="${escapeHtml(href)}" target="_blank" rel="noreferrer"`;
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
  if (heroTitle) {
    heroTitle.textContent = payload.title || "AI Trust & Security Stack Control Plane";
  }

  if (heroCopy) {
    const subtitle = payload.subtitle ? `${payload.subtitle} ` : "";
    heroCopy.textContent = `${subtitle}${payload.hero_copy || ""}`.trim();
  }

  const mode = payload.data_mode || {};
  heroMeta.innerHTML = `
    <span class="chip">${escapeHtml(payload.runtime_module || "Governed runtime")}</span>
    <span class="${statusClass(mode.status || "neutral")}">${escapeHtml(mode.label || "Dashboard mode")}</span>
    <span class="chip">Generated ${escapeHtml(formatTimestamp(payload.generated_at))}</span>
  `;

  const landingSteps = Array.isArray(payload.landing_steps) ? payload.landing_steps : [];
  heroSteps.innerHTML = landingSteps
    .map(
      (label, index) => `
        <article class="step-card">
          <span class="step-index">${index + 1}</span>
          <span class="step-label">${escapeHtml(label)}</span>
        </article>
      `,
    )
    .join("");
}

function renderBriefing(items) {
  if (!briefingRoot) {
    return;
  }

  briefingRoot.innerHTML = (Array.isArray(items) ? items : [])
    .map(
      (item) => `
        <${item.href ? "a" : "article"} class="briefing-card"${linkAttributes(item.href)}>
          <p class="briefing-question">${escapeHtml(item.question || "")}</p>
          <h3>${escapeHtml(item.answer || "")}</h3>
          <p class="briefing-detail">${escapeHtml(item.detail || "")}</p>
          <div class="${statusClass(item.status || "neutral")}">${escapeHtml(item.status || "neutral")}</div>
        </${item.href ? "a" : "article"}>
      `,
    )
    .join("");
}

function renderCards(items) {
  return `
    <div class="cards-grid">
      ${(Array.isArray(items) ? items : [])
        .map(
          (item) => `
            <${item.href ? "a" : "article"} class="metric-card"${linkAttributes(item.href)}>
              <div class="metric-label">${escapeHtml(item.label || "")}</div>
              <div class="metric-value">${escapeHtml(item.value || "")}</div>
              <div class="metric-detail">${escapeHtml(item.detail || "")}</div>
              <div class="${statusClass(item.status || "neutral")}">${escapeHtml(item.status || "neutral")}</div>
            </${item.href ? "a" : "article"}>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderKpis(items) {
  if (!kpiRoot) {
    return;
  }
  kpiRoot.innerHTML = renderCards(items);
}

function renderRecords(items) {
  return `
    <div class="records-grid">
      ${(Array.isArray(items) ? items : [])
        .map(
          (item) => `
            <${item.href ? "a" : "article"} class="record-card"${linkAttributes(item.href)}>
              <h3>${escapeHtml(item.title || "")}</h3>
              <p class="record-meta">${escapeHtml(item.meta || "")}</p>
              <p class="record-detail">${escapeHtml(item.detail || "")}</p>
              <div class="${statusClass(item.status || "neutral")}">${escapeHtml(item.status || "neutral")}</div>
            </${item.href ? "a" : "article"}>
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
            ${(block.columns || []).map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${(block.rows || [])
            .map(
              (row) => `
                <tr>
                  ${(block.columns || []).map((column) => `<td>${escapeHtml(row[column.key] ?? "")}</td>`).join("")}
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
      ${(Array.isArray(items) ? items : [])
        .map(
          (item) => `
            <a class="link-card"${linkAttributes(item.href)}>
              <div class="${statusClass(item.status || "neutral")}">${escapeHtml(item.status || "neutral")}</div>
              <h3>${escapeHtml(item.label || "")}</h3>
              <p class="link-description">${escapeHtml(item.description || "")}</p>
            </a>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderBlocks(blocks) {
  return (Array.isArray(blocks) ? blocks : [])
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
          <div class="block-head">
            <h3 class="block-title">${escapeHtml(block.title || "")}</h3>
          </div>
          ${content}
        </section>
      `;
    })
    .join("");
}

function renderReadiness(panel) {
  if (!readinessRoot) {
    return;
  }

  const controlFamilies = Array.isArray(panel.control_families) ? panel.control_families : [];
  const failingControls = Array.isArray(panel.top_failing_controls) ? panel.top_failing_controls : [];
  const residualRisks = Array.isArray(panel.residual_risks) ? panel.residual_risks : [];
  const evidenceLinks = Array.isArray(panel.evidence_links) ? panel.evidence_links : [];

  readinessRoot.innerHTML = `
    <div class="readiness-shell">
      <div class="readiness-main">
        <div class="section-head">
          <p class="eyebrow">Security readiness / launch gate</p>
          <h2 id="readiness-title">Current Readiness State: ${escapeHtml(panel.status_label || "UNKNOWN")}</h2>
          <p class="section-description">${escapeHtml(panel.summary || "")}</p>
        </div>
        <div class="readiness-score-band">
          <div class="readiness-score ${statusClass(panel.status || "neutral")}">
            <span class="readiness-score-label">Readiness score</span>
            <strong>${escapeHtml(panel.score || "0")}</strong>
            <span class="readiness-score-detail">${escapeHtml(panel.coverage || "")} controls passing</span>
          </div>
          <div class="hero-meta">
            <span class="${statusClass(panel.status || "neutral")}">${escapeHtml(panel.status_label || "unknown")}</span>
            <span class="chip">Generated ${escapeHtml(formatTimestamp(panel.generated_at))}</span>
          </div>
        </div>
        <div class="readiness-family-grid">
          ${controlFamilies
            .map(
              (family) => `
                <article class="readiness-family-card">
                  <div class="${statusClass(family.status || "neutral")}">${escapeHtml(family.status || "neutral")}</div>
                  <h3>${escapeHtml(family.family || "")}</h3>
                  <p class="readiness-family-score">${escapeHtml(family.score || "0")}%</p>
                  <p class="record-detail">${escapeHtml(family.detail || "")}</p>
                </article>
              `,
            )
            .join("")}
        </div>
      </div>
      <div class="readiness-side">
        <section class="readiness-side-panel">
          <p class="eyebrow">Top failing controls</p>
          ${failingControls.length ? renderRecords(failingControls) : "<p class=\"record-detail\">No failing controls listed.</p>"}
        </section>
        <section class="readiness-side-panel">
          <p class="eyebrow">Residual risks</p>
          ${residualRisks.length ? renderRecords(residualRisks) : "<p class=\"record-detail\">No residual risks listed.</p>"}
        </section>
        <section class="readiness-side-panel">
          <p class="eyebrow">Underlying evidence</p>
          ${renderLinks(evidenceLinks, "readiness-link-grid")}
        </section>
      </div>
    </div>
  `;
}

function renderSections(sections) {
  root.innerHTML = (Array.isArray(sections) ? sections : [])
    .map(
      (section) => `
        <section class="dashboard-section section-${escapeHtml(section.id || "")}" data-section="${escapeHtml(section.id || "")}" id="${escapeHtml(section.id || "")}">
          <div class="section-head">
            <p class="eyebrow">${escapeHtml(section.id || "")}</p>
            <h2>${escapeHtml(section.title || "")}</h2>
            <p class="section-description">${escapeHtml(section.description || "")}</p>
          </div>
          ${renderBlocks(section.blocks)}
        </section>
      `,
    )
    .join("");
}

function renderTabs(tabs) {
  tabStrip.innerHTML = (Array.isArray(tabs) ? tabs : [])
    .map(
      (tab) => `
        <button class="tab-button" type="button" data-target="${escapeHtml(tab.id || "")}">
          ${escapeHtml(tab.label || "")}
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

function renderSources(sources) {
  sourcesRoot.innerHTML = (Array.isArray(sources) ? sources : [])
    .map(
      (source) => `
        <a class="source-card"${linkAttributes(source.href)}>
          <div class="${statusClass(source.status || "neutral")}">${escapeHtml(source.status || "neutral")}</div>
          <h3>${escapeHtml(source.label || "")}</h3>
          <p class="source-description">${escapeHtml(source.description || "")}</p>
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
      <a class="live-log-source"${linkAttributes(payload.source_href || "/api/control-plane/live-log?limit=50")}>
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
                        <span class="${statusClass(entry.status || "neutral")}">${escapeHtml(entry.severity || "info")}</span>
                        <h3>${escapeHtml(entry.event_type || "event")}</h3>
                      </div>
                      <time class="live-log-time">${escapeHtml(formatTimestamp(entry.timestamp))}</time>
                    </div>
                    <p class="live-log-summary">${escapeHtml(entry.summary || "No event summary available.")}</p>
                    <div class="live-log-meta-row">
                      ${entry.request_id ? `<span class="live-log-meta-chip">request ${escapeHtml(entry.request_id)}</span>` : ""}
                      ${entry.trace_id ? `<span class="live-log-meta-chip">trace ${escapeHtml(entry.trace_id)}</span>` : ""}
                      ${entry.tenant_id ? `<span class="live-log-meta-chip">tenant ${escapeHtml(entry.tenant_id)}</span>` : ""}
                    </div>
                  </article>
                `,
              )
              .join("")
          : `
            <article class="live-log-entry live-log-empty">
              <h3>No recent activity yet</h3>
              <p class="live-log-summary">New runtime and observability events will appear here.</p>
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
    renderHero(payload);
    renderBriefing(payload.operator_briefing);
    renderKpis(payload.kpis);
    renderReadiness(payload.readiness_panel || {});
    renderTabs(payload.tabs);
    renderSections(payload.sections);
    renderSources(payload.sources);
  } catch (error) {
    const message = escapeHtml(error.message || "Unknown error");
    root.innerHTML = `
      <section class="loading-panel">
        <p class="eyebrow">Unavailable</p>
        <h2>Dashboard could not load</h2>
        <p>${message}</p>
      </section>
    `;
    if (briefingRoot) {
      briefingRoot.innerHTML = "";
    }
    if (kpiRoot) {
      kpiRoot.innerHTML = "";
    }
    if (readinessRoot) {
      readinessRoot.innerHTML = "";
    }
  }
}

async function refreshDashboard() {
  if (refreshDashboardButton) {
    refreshDashboardButton.disabled = true;
    refreshDashboardButton.textContent = "Refreshing...";
  }

  await Promise.all([boot(), loadLiveLog()]);

  if (refreshDashboardButton) {
    refreshDashboardButton.disabled = false;
    refreshDashboardButton.textContent = "Refresh evidence";
  }
}

if (refreshDashboardButton) {
  refreshDashboardButton.addEventListener("click", () => {
    refreshDashboard();
  });
}

boot();
loadLiveLog();
