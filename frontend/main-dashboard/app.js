const root = document.getElementById("dashboard-root");
const tabStrip = document.getElementById("tab-strip");
const heroTitle = document.getElementById("hero-title");
const heroCopy = document.getElementById("hero-copy");
const heroMeta = document.getElementById("hero-meta");
const heroSteps = document.getElementById("hero-steps");
const modeBannerRoot = document.getElementById("mode-banner-root");
const briefingRoot = document.getElementById("briefing-root");
const kpiRoot = document.getElementById("kpi-root");
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

function renderModeBanner(modeBanner) {
  if (!modeBannerRoot) {
    return;
  }

  const chips = Array.isArray(modeBanner.chips) ? modeBanner.chips : [];
  const consequences = Array.isArray(modeBanner.consequences) ? modeBanner.consequences : [];
  modeBannerRoot.innerHTML = `
    <section class="mode-banner mode-${escapeHtml(modeBanner.status || "neutral")}">
      <div class="mode-banner-head">
        <div>
          <p class="eyebrow">Governance mode</p>
          <h2>${escapeHtml(modeBanner.label || "Governance mode unavailable")}</h2>
          <p class="section-description">${escapeHtml(modeBanner.summary || "")}</p>
        </div>
        <div class="${statusClass(modeBanner.status || "neutral")}">${escapeHtml(modeBanner.status || "neutral")}</div>
      </div>
      <p class="mode-banner-detail">${escapeHtml(modeBanner.detail || "")}</p>
      <div class="mode-banner-chips">
        ${chips
          .map(
            (chip) => `
              <article class="mode-chip">
                <span class="mode-chip-label">${escapeHtml(chip.label || "")}</span>
                <strong>${escapeHtml(chip.value || "")}</strong>
              </article>
            `,
          )
          .join("")}
      </div>
      ${
        consequences.length
          ? `
            <div class="mode-banner-consequences">
              ${consequences
                .map(
                  (item) => `
                    <article class="mode-consequence-card">
                      <p>${escapeHtml(item)}</p>
                    </article>
                  `,
                )
                .join("")}
            </div>
          `
          : ""
      }
    </section>
  `;
}

function renderFieldGrid(fields) {
  const items = Array.isArray(fields) ? fields.filter((field) => field && (field.label || field.value)) : [];
  if (!items.length) {
    return "";
  }

  return `
    <div class="spotlight-field-grid">
      ${items
        .map(
          (field) => `
            <article class="spotlight-field">
              <span class="spotlight-field-label">${escapeHtml(field.label || "")}</span>
              <strong class="spotlight-field-value">${escapeHtml(field.value || "")}</strong>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderSpotlight(item, className = "spotlight-card") {
  if (!item) {
    return "";
  }

  return `
    <${item.href ? "a" : "article"} class="${className}"${linkAttributes(item.href)}>
      <div class="card-topline">
        <p class="eyebrow">${escapeHtml(item.eyebrow || "")}</p>
        <div class="${statusClass(item.status || "neutral")}">${escapeHtml(item.status || "neutral")}</div>
      </div>
      <h3>${escapeHtml(item.title || "")}</h3>
      <p class="record-detail">${escapeHtml(item.detail || "")}</p>
      ${renderFieldGrid(item.fields)}
    </${item.href ? "a" : "article"}>
  `;
}

function renderBriefing(commandCenter) {
  if (!briefingRoot) {
    return;
  }

  const cards = Array.isArray(commandCenter.cards) ? commandCenter.cards : [];
  const latestRequest = commandCenter.latest_request || {};
  const flagshipProof = commandCenter.flagship_proof || {};
  const actions = Array.isArray(commandCenter.actions) ? commandCenter.actions : [];

  briefingRoot.innerHTML = `
    <div class="command-summary-grid">
      <section class="command-primary-panel">
        <div class="command-primary-head">
          <p class="eyebrow">Executive state</p>
          <p class="record-detail">Read this first for readiness, latest handoff, top blocker, and evidence freshness.</p>
        </div>
        ${renderCards(cards, "cards-grid command-cards-grid")}
      </section>
      <div class="command-focus-grid">
        ${renderSpotlight(latestRequest, "command-focus-panel spotlight-card")}
        ${renderSpotlight(flagshipProof, "command-focus-panel spotlight-card")}
        <section class="command-focus-panel action-panel">
          <div class="card-topline">
            <p class="eyebrow">Primary actions</p>
          </div>
          <h3>Review or refresh governed proof</h3>
          <p class="record-detail">Open the strongest pass and deny artifacts, or generate a fresh governed flow without hunting through deeper sections.</p>
          ${renderLinks(actions, "command-link-grid")}
        </section>
      </div>
    </div>
  `;
}

function renderCards(items, className = "cards-grid") {
  return `
    <div class="${className}">
      ${(Array.isArray(items) ? items : [])
        .map(
          (item) => `
            <${item.href ? "a" : "article"} class="metric-card"${linkAttributes(item.href)}>
              <div class="card-topline">
                <div class="metric-label">${escapeHtml(item.label || "")}</div>
                <div class="${statusClass(item.status || "neutral")}">${escapeHtml(item.status || "neutral")}</div>
              </div>
              <div class="metric-value">${escapeHtml(item.value || "")}</div>
              <div class="metric-detail">${escapeHtml(item.detail || "")}</div>
            </${item.href ? "a" : "article"}>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderKpis(paths) {
  if (!kpiRoot) {
    return;
  }

  kpiRoot.innerHTML = (Array.isArray(paths) ? paths : [])
    .map(
      (path) => `
        <section class="audience-lane">
          <div class="audience-lane-head">
            <div>
              <p class="eyebrow">${escapeHtml(path.title === "Reviewer View" ? "Start here" : "Then drill deeper")}</p>
              <h3>${escapeHtml(path.title || "")}</h3>
            </div>
            <div class="${statusClass(path.status || "neutral")}">${escapeHtml(path.status || "neutral")}</div>
          </div>
          <p class="record-detail">${escapeHtml(path.detail || "")}</p>
          ${renderLinks(path.links || [], "audience-link-grid")}
        </section>
      `,
    )
    .join("");
}

function renderRecords(items) {
  return `
    <div class="records-grid">
      ${(Array.isArray(items) ? items : [])
        .map(
          (item) => `
            <${item.href ? "a" : "article"} class="record-card"${linkAttributes(item.href)}>
              <div class="card-topline">
                <div class="record-meta-label">${escapeHtml(item.meta || "")}</div>
                <div class="${statusClass(item.status || "neutral")}">${escapeHtml(item.status || "neutral")}</div>
              </div>
              <h3>${escapeHtml(item.title || "")}</h3>
              <p class="record-detail">${escapeHtml(item.detail || "")}</p>
            </${item.href ? "a" : "article"}>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderTable(block) {
  const tableMarkup = `
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

  if (!block.collapsed) {
    return tableMarkup;
  }

  return `
    <details class="table-disclosure">
      <summary>${escapeHtml(block.summary || "Open table sample")}</summary>
      ${tableMarkup}
    </details>
  `;
}

function renderLinks(items, className = "link-grid") {
  return `
    <div class="${className}">
      ${(Array.isArray(items) ? items : [])
        .map(
          (item) => `
            <a class="link-card"${linkAttributes(item.href)}>
              <div class="card-topline">
                <span class="metric-label">Drill through</span>
                <div class="${statusClass(item.status || "neutral")}">${escapeHtml(item.status || "neutral")}</div>
              </div>
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

function renderSections(sections) {
  let activeGroup = "";
  root.innerHTML = (Array.isArray(sections) ? sections : [])
    .map((section) => {
      const nextGroup = section.group || "";
      const groupBanner =
        nextGroup && nextGroup !== activeGroup
          ? `
            <section class="section-group-banner section-group-${escapeHtml(nextGroup)}">
              <p class="eyebrow">${escapeHtml(section.group_label || nextGroup)}</p>
              <h2>${escapeHtml(section.group_label || nextGroup)}</h2>
              <p class="section-description">${
                nextGroup === "reviewer"
                  ? "Start with reviewer-safe proof, launch posture, request visibility, and flagship pass or deny evidence."
                  : "Continue into operator diagnostics, control-domain detail, and deeper evidence or inventory slices."
              }</p>
            </section>
          `
          : "";
      activeGroup = nextGroup;

      return `
        ${groupBanner}
        <section class="dashboard-section section-${escapeHtml(section.id || "")}" data-section="${escapeHtml(section.id || "")}" id="${escapeHtml(section.id || "")}">
          <div class="section-head">
            <p class="eyebrow">${escapeHtml(section.id || "")}</p>
            <h2>${escapeHtml(section.title || "")}</h2>
            <p class="section-description">${escapeHtml(section.description || "")}</p>
          </div>
          ${renderBlocks(section.blocks)}
        </section>
      `;
    })
    .join("");
}

function renderTabs(tabs) {
  const groups = new Map();
  for (const tab of Array.isArray(tabs) ? tabs : []) {
    const groupLabel = tab.group_label || "Sections";
    if (!groups.has(groupLabel)) {
      groups.set(groupLabel, []);
    }
    groups.get(groupLabel).push(tab);
  }

  tabStrip.innerHTML = Array.from(groups.entries())
    .map(
      ([groupLabel, groupTabs]) => `
        <section class="tab-group">
          <p class="eyebrow">${escapeHtml(groupLabel)}</p>
          <div class="tab-group-row">
            ${groupTabs
              .map(
                (tab) => `
                  <button class="tab-button" type="button" data-target="${escapeHtml(tab.id || "")}">
                    ${escapeHtml(tab.label || "")}
                  </button>
                `,
              )
              .join("")}
          </div>
        </section>
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
          <div class="card-topline">
            <span class="metric-label">Source</span>
            <div class="${statusClass(source.status || "neutral")}">${escapeHtml(source.status || "neutral")}</div>
          </div>
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
    renderModeBanner(payload.mode_banner || {});
    renderBriefing(payload.command_center || {});
    renderKpis(payload.audience_paths || []);
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
    if (modeBannerRoot) {
      modeBannerRoot.innerHTML = "";
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
