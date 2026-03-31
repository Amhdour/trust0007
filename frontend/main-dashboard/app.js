const root = document.getElementById("dashboard-root");
const tabStrip = document.getElementById("tab-strip");
const heroTitle = document.getElementById("hero-title");
const heroCopy = document.getElementById("hero-copy");
const heroMeta = document.getElementById("hero-meta");
const heroSteps = document.getElementById("hero-steps");
const modeBannerRoot = document.getElementById("mode-banner-root");
const incidentBannerRoot = document.getElementById("incident-banner-root");
const riskStripRoot = document.getElementById("risk-strip-root");
const briefingRoot = document.getElementById("briefing-root");
const proofPipelineRoot = document.getElementById("proof-pipeline-root");
const readingGuideRoot = document.getElementById("reading-guide-root");
const kpiRoot = document.getElementById("kpi-root");
const sourcesRoot = document.getElementById("sources");
const liveLogRoot = document.getElementById("live-log-root");
const refreshDashboardButton = document.getElementById("refresh-dashboard-button");

const LIVE_LOG_LIMIT = 6;
const DEFAULT_LIVE_LOG_POLL_MS = 5000;
const SECTION_SCROLL_OFFSET_PX = 152;
let liveLogTimer = 0;
let activeTabTarget = "";
let activeTabSyncFrame = 0;
let tabStripScrollBound = false;

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

function statusLabel(status) {
  return {
    healthy: "Good",
    warning: "Needs attention",
    critical: "Serious issue",
    neutral: "For context",
  }[status || "neutral"] || String(status || "neutral");
}

function renderStatusPill(status, options = {}) {
  const normalized = status || "neutral";
  if ((options.hideHealthy && normalized === "healthy") || (options.hideNeutral && normalized === "neutral")) {
    return "";
  }

  return `<div class="${statusClass(normalized)}" title="${escapeHtml(normalized)}">${escapeHtml(options.label || statusLabel(normalized))}</div>`;
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

function formatBadgeValue(badge) {
  if (!badge) {
    return "";
  }

  if (badge.kind === "timestamp") {
    return formatTimestamp(badge.value);
  }

  return String(badge.value || "");
}

function renderMetaBadges(items, className = "evidence-meta-row") {
  const badges = Array.isArray(items) ? items.filter((item) => item && item.value) : [];
  if (!badges.length) {
    return "";
  }

  return `
    <div class="${className}">
      ${badges
        .map((badge) => {
          const classes = ["evidence-meta-chip"];
          if (badge.status) {
            classes.push(`evidence-meta-chip-${badge.status}`);
          }

          return `
            <span class="${classes.join(" ")}">
              ${badge.label ? `<span class="evidence-meta-chip-label">${escapeHtml(badge.label)}</span>` : ""}
              <strong>${escapeHtml(formatBadgeValue(badge))}</strong>
            </span>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderTrendSummary(trend) {
  if (!trend?.label) {
    return "";
  }

  const status = trend.status || "neutral";
  return `
    <div class="trend-summary trend-summary-${escapeHtml(status)}">
      <span class="trend-summary-label">Trend</span>
      <strong>${escapeHtml(trend.label)}</strong>
      ${trend.detail ? `<p>${escapeHtml(trend.detail)}</p>` : ""}
    </div>
  `;
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
    <span class="${statusClass(mode.status || "neutral")}" title="${escapeHtml(mode.label || "Dashboard mode")}">${escapeHtml(mode.display_label || mode.label || "Dashboard mode")}</span>
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
          <h2>${escapeHtml(modeBanner.display_label || modeBanner.label || "Governance mode unavailable")}</h2>
          <p class="section-description">${escapeHtml(modeBanner.display_summary || modeBanner.summary || "")}</p>
        </div>
        <div class="${statusClass(modeBanner.status || "neutral")}" title="${escapeHtml(modeBanner.status || "neutral")}">${escapeHtml(statusLabel(modeBanner.status || "neutral"))}</div>
      </div>
      <p class="mode-banner-detail">${escapeHtml(modeBanner.display_detail || modeBanner.detail || "")}</p>
      <div class="mode-banner-chips">
        ${chips
          .map(
            (chip) => `
              <article class="mode-chip">
                <span class="mode-chip-label">${escapeHtml(chip.display_label || chip.label || "")}</span>
                <strong>${escapeHtml(chip.display_value || chip.value || "")}</strong>
              </article>
            `,
              )
              .join("")}
      </div>
      ${
        consequences.length
          ? `
            <details class="mode-banner-disclosure">
              <summary>How to interpret this mode</summary>
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
            </details>
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
        <p class="eyebrow">${escapeHtml(item.display_eyebrow || item.eyebrow || "")}</p>
        <div class="${statusClass(item.status || "neutral")}" title="${escapeHtml(item.status || "neutral")}">${escapeHtml(statusLabel(item.status || "neutral"))}</div>
      </div>
      <h3>${escapeHtml(item.display_title || item.title || "")}</h3>
      <p class="record-detail">${escapeHtml(item.display_detail || item.detail || "")}</p>
      ${renderMetaBadges(item.display_meta_badges || item.meta_badges, "evidence-meta-row spotlight-meta-row")}
      ${renderFieldGrid(item.display_fields || item.fields)}
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
          <p class="eyebrow">Safety summary</p>
          <p class="record-detail">Read this first for the current decision and the few proof links you need.</p>
        </div>
        ${renderCards(cards, "cards-grid command-cards-grid")}
        <div class="command-primary-footer">
          <p class="eyebrow">Primary proof links</p>
          ${renderActionPills(actions)}
        </div>
      </section>
      <div class="command-focus-grid">
        ${renderSpotlight(latestRequest, "command-focus-panel spotlight-card")}
        ${renderSpotlight(flagshipProof, "command-focus-panel spotlight-card")}
      </div>
    </div>
  `;
}

function renderRiskStrip(strip) {
  if (!riskStripRoot) {
    return;
  }

  const items = Array.isArray(strip.items) ? strip.items : [];
  if (!items.length) {
    riskStripRoot.innerHTML = "";
    return;
  }

  riskStripRoot.innerHTML = `
    <section class="risk-strip-card">
      <div class="support-card-head">
        <div>
          <p class="eyebrow">${escapeHtml(strip.eyebrow || "Current risk strip")}</p>
          <h3>${escapeHtml(strip.title || "Four signals to watch")}</h3>
        </div>
      </div>
      <p class="record-detail">${escapeHtml(strip.detail || "")}</p>
      <div class="risk-strip-grid">
        ${items
          .map(
            (item) => `
              <${item.href ? "a" : "article"} class="risk-stat-card risk-stat-${escapeHtml(item.status || "neutral")}"${linkAttributes(item.href)}>
                <div class="card-topline">
                  <div class="metric-label">${escapeHtml(item.display_label || item.label || "")}</div>
                  ${renderStatusPill(item.status || "neutral", { hideNeutral: true })}
                </div>
                <strong class="risk-stat-value">${escapeHtml(item.display_value || item.value || "")}</strong>
                ${renderTrendSummary(item.trend)}
                <p class="risk-stat-detail">${escapeHtml(item.display_detail || item.detail || "")}</p>
                ${renderMetaBadges(item.meta_badges, "evidence-meta-row risk-meta-row")}
              </${item.href ? "a" : "article"}>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderIncidentBanner(banner) {
  if (!incidentBannerRoot) {
    return;
  }

  if (!banner?.visible) {
    incidentBannerRoot.innerHTML = "";
    return;
  }

  const facts = Array.isArray(banner.facts) ? banner.facts : [];
  const actions = Array.isArray(banner.actions) ? banner.actions : [];
  incidentBannerRoot.innerHTML = `
    <section class="incident-banner incident-banner-${escapeHtml(banner.status || "warning")}">
      <div class="incident-banner-head">
        <div>
          <p class="eyebrow">${escapeHtml(banner.eyebrow || "Current blocker")}</p>
          <h3>${escapeHtml(banner.title || "Attention needed")}</h3>
        </div>
        ${renderStatusPill(banner.status || "warning")}
      </div>
      <p class="incident-banner-summary">${escapeHtml(banner.summary || "")}</p>
      <p class="incident-banner-detail">${escapeHtml(banner.detail || "")}</p>
      <div class="incident-banner-facts">
        ${facts
          .map(
            (fact) => `
              <article class="incident-fact-card">
                <span class="incident-fact-label">${escapeHtml(fact.label || "")}</span>
                <strong>${escapeHtml(fact.value || "")}</strong>
              </article>
            `,
          )
          .join("")}
      </div>
      ${actions.length ? renderActionPills(actions) : ""}
    </section>
  `;
}

function pipelineStatusLabel(step) {
  return (
    step.badge_label
    || {
      healthy: "Passed",
      warning: "Needs review",
      critical: "Failed",
      neutral: "Not needed",
    }[step.status || "neutral"]
    || statusLabel(step.status || "neutral")
  );
}

function renderProofPipeline(pipeline) {
  if (!proofPipelineRoot) {
    return;
  }

  const steps = Array.isArray(pipeline.steps) ? pipeline.steps : [];
  proofPipelineRoot.innerHTML = `
    <section class="command-secondary-card pipeline-panel">
      <div class="support-card-head">
        <div>
          <p class="eyebrow">Latest governed path</p>
          <h3>${escapeHtml(pipeline.title || "Latest governed path")}</h3>
        </div>
        ${renderStatusPill(pipeline.status || "neutral")}
      </div>
      <p class="record-detail">${escapeHtml(pipeline.detail || "")}</p>
      ${renderMetaBadges(pipeline.meta_badges, "evidence-meta-row pipeline-summary-meta")}
      <div class="pipeline-step-grid">
        ${steps
          .map(
            (step, index) => `
              <${step.href ? "a" : "article"} class="pipeline-step-card pipeline-step-${escapeHtml(step.status || "neutral")}"${linkAttributes(step.href)}>
                <div class="pipeline-step-head">
                  <span class="pipeline-step-index">${index + 1}</span>
                  ${renderStatusPill(step.status || "neutral", { label: pipelineStatusLabel(step) })}
                </div>
                <p class="pipeline-step-label">${escapeHtml(step.label || "")}</p>
                <strong class="pipeline-step-value">${escapeHtml(step.value || "")}</strong>
                ${renderMetaBadges(step.meta_badges, "evidence-meta-row pipeline-step-meta")}
                <p class="pipeline-step-detail">${escapeHtml(step.detail || "")}</p>
              </${step.href ? "a" : "article"}>
            `,
          )
          .join("")}
      </div>
      <div class="pipeline-summary">
        <div class="hero-meta">
          ${pipeline.mode_label ? `<span class="chip">${escapeHtml(pipeline.mode_label)}</span>` : ""}
          ${pipeline.trace_id ? `<span class="chip">Trace ${escapeHtml(pipeline.trace_id)}</span>` : ""}
        </div>
        <p class="record-detail">${escapeHtml(pipeline.summary || "")}</p>
        ${
          pipeline.summary_href
            ? `<a class="audience-link-pill"${linkAttributes(pipeline.summary_href)}>Open latest technical summary</a>`
            : ""
        }
      </div>
    </section>
  `;
}

function renderActionPills(items) {
  return `
    <div class="command-action-row">
      ${(Array.isArray(items) ? items : [])
        .map(
          (item) => `
            <a class="action-pill action-pill-${escapeHtml(item.status || "neutral")}"${linkAttributes(item.href)}>
              ${escapeHtml(item.display_label || item.label || "")}
            </a>
          `,
        )
        .join("")}
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
                <div class="metric-label">${escapeHtml(item.display_label || item.label || "")}</div>
                <div class="${statusClass(item.status || "neutral")}" title="${escapeHtml(item.status || "neutral")}">${escapeHtml(statusLabel(item.status || "neutral"))}</div>
              </div>
              <div class="metric-value">${escapeHtml(item.display_value || item.value || "")}</div>
              ${renderMetaBadges(item.meta_badges)}
              <div class="metric-detail">${escapeHtml(item.display_detail || item.detail || "")}</div>
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

  kpiRoot.innerHTML = `
    <section class="command-secondary-card support-panel">
      <div class="support-card-head">
        <div>
          <p class="eyebrow">Reading lanes</p>
          <h3 id="kpi-title">Reviewer View And Operator Drilldown</h3>
        </div>
      </div>
      <p class="record-detail">Start with the plain-language lane. Use the technical lane when you need traces and raw reasons.</p>
      <div class="audience-path-grid">
        ${(Array.isArray(paths) ? paths : [])
          .map(
            (path) => `
              <section class="audience-path-card">
                <div class="audience-lane-head">
                  <div>
                    <p class="eyebrow">${escapeHtml(String(path.title || "").toLowerCase().includes("technical") ? "Then drill deeper" : "Start here")}</p>
                    <h3>${escapeHtml(path.title || "")}</h3>
                  </div>
                  ${renderStatusPill(path.status || "neutral", { hideHealthy: true, hideNeutral: true })}
                </div>
                <p class="record-detail">${escapeHtml(path.detail || "")}</p>
                <div class="audience-link-pill-row">
                  ${(Array.isArray(path.links) ? path.links : [])
                    .map(
                      (item) => `
                        <a class="audience-link-pill"${linkAttributes(item.href)}>
                          ${escapeHtml(item.display_label || item.label || "")}
                        </a>
                      `,
                    )
                    .join("")}
                </div>
              </section>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderRecords(items) {
  return `
    <div class="records-grid">
      ${(Array.isArray(items) ? items : [])
        .map(
          (item) => `
            <${item.href ? "a" : "article"} class="record-card"${linkAttributes(item.href)}>
              <div class="card-topline">
                <div class="record-meta-label">${escapeHtml(item.display_meta || item.meta || "")}</div>
                ${renderStatusPill(item.status || "neutral", { hideNeutral: true })}
              </div>
              <h3>${escapeHtml(item.display_title || item.title || "")}</h3>
              <p class="record-detail">${escapeHtml(item.display_detail || item.detail || "")}</p>
              ${renderMetaBadges(item.meta_badges)}
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
                  ${(block.columns || [])
                    .map(
                      (column) => `
                        <td data-label="${escapeHtml(column.label)}">${escapeHtml(row[column.key] ?? "")}</td>
                      `,
                    )
                    .join("")}
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
                ${renderStatusPill(item.status || "neutral", { hideHealthy: true, hideNeutral: true })}
              </div>
              <h3>${escapeHtml(item.display_label || item.label || "")}</h3>
              <p class="link-description">${escapeHtml(item.display_description || item.description || "")}</p>
              ${renderMetaBadges(item.meta_badges)}
            </a>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderReadingGuide(guide) {
  if (!readingGuideRoot) {
    return;
  }

  const statuses = Array.isArray(guide.statuses) ? guide.statuses : [];
  const questions = Array.isArray(guide.questions) ? guide.questions : [];

  readingGuideRoot.innerHTML = `
    <section class="command-secondary-card support-panel">
      <div class="support-card-head">
        <div>
          <p class="eyebrow">Quick help</p>
          <h3 id="guide-title">${escapeHtml(guide.title || "How to read this dashboard")}</h3>
        </div>
      </div>
      <p class="record-detail">${escapeHtml(guide.intro || "")}</p>
      <div class="guide-status-summary">
        ${statuses
          .map(
            (item) => `
              <article class="guide-status-chip-card">
                <div class="${statusClass(item.status || "neutral")}" title="${escapeHtml(item.status || "neutral")}">${escapeHtml(item.label || statusLabel(item.status || "neutral"))}</div>
                <p>${escapeHtml(item.detail || "")}</p>
              </article>
            `,
          )
          .join("")}
      </div>
      <details class="guide-disclosure">
        <summary>Show the main questions and technical note</summary>
        <div class="reading-guide-grid">
          <section class="guide-card">
            <h3>Main questions this page answers</h3>
            <div class="guide-question-grid">
              ${questions
                .map(
                  (item) => `
                    <a class="guide-question-card"${linkAttributes(item.href)}>
                      <div class="card-topline">
                        <span class="metric-label">${escapeHtml(item.question || "")}</span>
                        ${renderStatusPill(item.status || "neutral", { hideHealthy: true, hideNeutral: true })}
                      </div>
                      <strong>${escapeHtml(item.answer || "")}</strong>
                      <p>${escapeHtml(item.detail || "")}</p>
                    </a>
                  `,
                )
                .join("")}
            </div>
            <p class="guide-note">${escapeHtml(guide.technical_note || "")}</p>
          </section>
        </div>
      </details>
    </section>
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
                  ? "Start here for the plain-language story: current state, blocked actions, proof, and readiness."
                  : "Continue here for traces, raw reasons, evidence links, and control detail."
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

function setActiveTab(targetId) {
  if (!tabStrip) {
    return;
  }

  activeTabTarget = targetId || "";
  for (const button of tabStrip.querySelectorAll("button[data-target]")) {
    const isActive = button.dataset.target === activeTabTarget;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  }
}

function syncActiveTabFromScroll() {
  const sections = Array.from(root.querySelectorAll(".dashboard-section[id]"));
  if (!sections.length) {
    return;
  }

  let nextActive = sections[0].id;
  for (const section of sections) {
    const top = section.getBoundingClientRect().top;
    if (top - SECTION_SCROLL_OFFSET_PX <= 0) {
      nextActive = section.id;
      continue;
    }
    break;
  }

  setActiveTab(nextActive);
}

function scheduleActiveTabSync() {
  window.cancelAnimationFrame(activeTabSyncFrame);
  activeTabSyncFrame = window.requestAnimationFrame(syncActiveTabFromScroll);
}

function bindTabStripScrollListeners() {
  if (tabStripScrollBound) {
    return;
  }

  window.addEventListener("scroll", scheduleActiveTabSync, { passive: true });
  window.addEventListener("resize", scheduleActiveTabSync);
  tabStripScrollBound = true;
}

function scrollToSection(targetId) {
  const target = document.getElementById(targetId);
  if (!target) {
    return;
  }

  const absoluteTop = window.scrollY + target.getBoundingClientRect().top - SECTION_SCROLL_OFFSET_PX;
  window.scrollTo({ top: Math.max(0, absoluteTop), behavior: "smooth" });
  setActiveTab(targetId);
}

function renderTabs(tabs) {
  const groups = new Map();
  const allTabs = Array.isArray(tabs) ? tabs : [];
  for (const tab of allTabs) {
    const groupLabel = tab.group_label || "Sections";
    if (!groups.has(groupLabel)) {
      groups.set(groupLabel, []);
    }
    groups.get(groupLabel).push(tab);
  }

  const primaryTabs = allTabs.filter((tab) => tab.group === "reviewer").slice(0, 5);

  tabStrip.innerHTML = `
    <section class="tab-strip-shell">
      <div class="tab-strip-head">
        <div>
          <p class="eyebrow">Quick jump</p>
          <p class="section-description">Use the short row for the main story. Open the full list only for deeper drill-down.</p>
        </div>
      </div>
      <div class="tab-group-row tab-primary-row">
        ${primaryTabs
          .map(
            (tab) => `
              <button class="tab-button" type="button" data-target="${escapeHtml(tab.id || "")}" aria-pressed="false">
                ${escapeHtml(tab.label || "")}
              </button>
            `,
          )
          .join("")}
      </div>
      <details class="tab-disclosure">
        <summary>Show all sections</summary>
        <div class="tab-disclosure-body">
          ${Array.from(groups.entries())
            .map(
              ([groupLabel, groupTabs]) => `
                <section class="tab-group">
                  <p class="eyebrow">${escapeHtml(groupLabel)}</p>
                  <div class="tab-group-row">
                    ${groupTabs
                      .map(
                        (tab) => `
                          <button class="tab-button" type="button" data-target="${escapeHtml(tab.id || "")}" aria-pressed="false">
                            ${escapeHtml(tab.label || "")}
                          </button>
                        `,
                      )
                      .join("")}
                  </div>
                </section>
              `,
            )
            .join("")}
        </div>
      </details>
    </section>
  `;

  for (const button of tabStrip.querySelectorAll("button")) {
    button.addEventListener("click", () => {
      scrollToSection(button.dataset.target);

      const disclosure = button.closest(".tab-strip-shell")?.querySelector(".tab-disclosure");
      if (disclosure?.open) {
        disclosure.open = false;
      }
    });
  }

  bindTabStripScrollListeners();
  setActiveTab(activeTabTarget || primaryTabs[0]?.id || allTabs[0]?.id || "");
  scheduleActiveTabSync();
}

function renderSources(sources) {
  sourcesRoot.innerHTML = (Array.isArray(sources) ? sources : [])
    .map(
      (source) => `
        <a class="source-card"${linkAttributes(source.href)}>
          <div class="card-topline">
            <span class="metric-label">Source</span>
            ${renderStatusPill(source.status || "neutral", { hideHealthy: true, hideNeutral: true })}
          </div>
          <h3>${escapeHtml(source.label || "")}</h3>
          <p class="source-description">${escapeHtml(source.description || "")}</p>
          ${renderMetaBadges(source.meta_badges)}
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
    renderIncidentBanner(payload.command_center?.incident_banner || {});
    renderRiskStrip(payload.command_center?.risk_strip || {});
    renderBriefing(payload.command_center || {});
    renderProofPipeline(payload.command_center?.proof_pipeline || {});
    renderReadingGuide(payload.reading_guide || {});
    renderKpis(payload.audience_paths || []);
    renderSections(payload.sections);
    renderTabs(payload.tabs);
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
    if (incidentBannerRoot) {
      incidentBannerRoot.innerHTML = "";
    }
    if (riskStripRoot) {
      riskStripRoot.innerHTML = "";
    }
    if (proofPipelineRoot) {
      proofPipelineRoot.innerHTML = "";
    }
    if (kpiRoot) {
      kpiRoot.innerHTML = "";
    }
    if (readingGuideRoot) {
      readingGuideRoot.innerHTML = "";
    }
    if (modeBannerRoot) {
      modeBannerRoot.innerHTML = "";
    }
    if (tabStrip) {
      tabStrip.innerHTML = "";
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
