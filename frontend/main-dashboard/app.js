const root = document.getElementById("dashboard-root");
const tabStrip = document.getElementById("tab-strip");
const heroEyebrow = document.getElementById("hero-eyebrow");
const heroTitle = document.getElementById("hero-title");
const heroCopy = document.getElementById("hero-copy");
const heroMeta = document.getElementById("hero-meta");
const dashboardViewRoot = document.getElementById("dashboard-view-root");
const liveSessionRoot = document.getElementById("live-session-root");
const runtimeSummaryRoot = document.getElementById("runtime-summary-root");
const stackHealthRoot = document.getElementById("stack-health-root");
const heroSteps = document.getElementById("hero-steps");
const summarySheetRoot = document.getElementById("summary-sheet-root");
const modeBannerRoot = document.getElementById("mode-banner-root");
const incidentBannerRoot = document.getElementById("incident-banner-root");
const riskStripRoot = document.getElementById("risk-strip-root");
const nextActionRoot = document.getElementById("next-action-root");
const walkthroughRoot = document.getElementById("walkthrough-root");
const compareRoot = document.getElementById("compare-root");
const briefingRoot = document.getElementById("briefing-root");
const proofPipelineRoot = document.getElementById("proof-pipeline-root");
const readingGuideRoot = document.getElementById("reading-guide-root");
const kpiRoot = document.getElementById("kpi-root");
const sourcesRoot = document.getElementById("sources");
const liveLogRoot = document.getElementById("live-log-root");
const liveRuntimeLink = document.getElementById("live-runtime-link");
const clientOverviewLink = document.getElementById("client-overview-link");
const refreshDashboardButton = document.getElementById("refresh-dashboard-button");

const LIVE_LOG_LIMIT = 6;
const DEFAULT_LIVE_LOG_POLL_MS = 5000;
const SECTION_SCROLL_OFFSET_PX = 152;
const DASHBOARD_VIEW_STORAGE_KEY = "controlPlaneDashboardView";
const DASHBOARD_VIEW_MODES = {
  executive: {
    label: "Executive",
    description: "Posture, blocker, next step, and reviewer-friendly proof only.",
  },
  operator: {
    label: "Operator",
    description: "Full control-plane briefing with reviewer and technical lanes.",
  },
  runtime: {
    label: "Live Runtime",
    description: "Focus on the live workspace path, runtime proof, and current activity.",
  },
};
const RUNTIME_SECTION_IDS = new Set([
  "entry-points",
  "governed-requests",
  "identity-session",
  "audit-replay",
  "trace-correlation",
  "policy-enforcement",
]);
let liveLogTimer = 0;
let activeTabTarget = "";
let activeTabSyncFrame = 0;
let tabStripScrollBound = false;
let presentationModeEnabled = false;
let dashboardViewMode = "operator";
let lastOverviewPayload = null;
let lastLiveLogPayload = null;
let lastLiveSessionPayload = null;
let liveLogStatusFilter = "all";
let liveLogSourceFilter = "all";
let dashboardFingerprints = new Map();
let changedDashboardKeys = new Set();
let changeHighlightTimer = 0;

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

function formatRemainingDuration(totalSeconds) {
  if (!Number.isFinite(totalSeconds)) {
    return "";
  }

  if (totalSeconds <= 0) {
    return "Expired";
  }

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (hours > 0 && minutes > 0) {
    return `${hours}h ${minutes}m left`;
  }
  if (hours > 0) {
    return `${hours}h left`;
  }
  if (minutes > 0) {
    return `${minutes}m left`;
  }
  return `${Math.max(1, Math.floor(totalSeconds))}s left`;
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

function renderTrendSummary(trend, label = "Changed since last refresh") {
  if (!trend?.label) {
    return "";
  }

  const status = trend.status || "neutral";
  return `
    <div class="trend-summary trend-summary-${escapeHtml(status)}">
      <span class="trend-summary-label">${escapeHtml(label)}</span>
      <strong>${escapeHtml(trend.label)}</strong>
      ${trend.detail ? `<p>${escapeHtml(trend.detail)}</p>` : ""}
    </div>
  `;
}

function normalizeKeyFragment(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function fingerprintValue(value) {
  try {
    return JSON.stringify(value ?? null);
  } catch {
    return String(value ?? "");
  }
}

function buildDashboardFingerprints(payload) {
  const commandCenter = payload.command_center || {};
  const nextFingerprints = new Map();

  nextFingerprints.set("incident-banner", fingerprintValue(commandCenter.incident_banner || {}));
  nextFingerprints.set("next-action", fingerprintValue(commandCenter.next_action || {}));
  nextFingerprints.set("walkthrough", fingerprintValue(commandCenter.walkthrough || []));
  nextFingerprints.set("example-compare", fingerprintValue(commandCenter.example_compare || {}));
  nextFingerprints.set("proof-pipeline", fingerprintValue(commandCenter.proof_pipeline || {}));
  nextFingerprints.set("freshness-strip", fingerprintValue(commandCenter.freshness_bar || {}));
  nextFingerprints.set("presentation-summary", fingerprintValue(commandCenter.presentation_summary || {}));

  for (const card of Array.isArray(commandCenter.cards) ? commandCenter.cards : []) {
    const key = card.id ? `card:${card.id}` : `card:${normalizeKeyFragment(card.label || card.display_label)}`;
    nextFingerprints.set(
      key,
      fingerprintValue({
        value: card.value,
        display_value: card.display_value,
        status: card.status,
        detail: card.detail,
        display_detail: card.display_detail,
        meta_badges: card.meta_badges,
      }),
    );
  }

  const riskItems = Array.isArray(commandCenter.risk_strip?.items) ? commandCenter.risk_strip.items : [];
  for (const item of riskItems) {
    const key = `risk:${normalizeKeyFragment(item.label || item.display_label)}`;
    nextFingerprints.set(
      key,
      fingerprintValue({
        value: item.value,
        display_value: item.display_value,
        status: item.status,
        detail: item.detail,
        display_detail: item.display_detail,
        trend: item.trend,
      }),
    );
  }

  const comparison = commandCenter.example_compare || {};
  if (comparison.approved) {
    nextFingerprints.set("compare:approved", fingerprintValue(comparison.approved));
  }
  if (comparison.blocked) {
    nextFingerprints.set("compare:blocked", fingerprintValue(comparison.blocked));
  }

  return nextFingerprints;
}

function updateDashboardChangeTracking(payload) {
  const nextFingerprints = buildDashboardFingerprints(payload);
  const changed = new Set();

  if (dashboardFingerprints.size) {
    for (const [key, value] of nextFingerprints.entries()) {
      if (dashboardFingerprints.has(key) && dashboardFingerprints.get(key) !== value) {
        changed.add(key);
      }
    }
  }

  dashboardFingerprints = nextFingerprints;
  changedDashboardKeys = changed;
}

function changeAttributes(key) {
  if (!key) {
    return "";
  }

  return ` data-change-key="${escapeHtml(key)}"`;
}

function applyChangeHighlights() {
  window.clearTimeout(changeHighlightTimer);
  for (const node of document.querySelectorAll(".recent-change")) {
    node.classList.remove("recent-change");
  }

  if (!changedDashboardKeys.size) {
    return;
  }

  for (const node of document.querySelectorAll("[data-change-key]")) {
    if (changedDashboardKeys.has(node.dataset.changeKey || "")) {
      node.classList.add("recent-change");
    }
  }

  changeHighlightTimer = window.setTimeout(() => {
    for (const node of document.querySelectorAll(".recent-change")) {
      node.classList.remove("recent-change");
    }
    changedDashboardKeys = new Set();
  }, 4200);
}

function resolveInitialDashboardViewMode() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  if (view === "presentation") {
    return "executive";
  }
  if (view === "full") {
    return "operator";
  }
  if (view && DASHBOARD_VIEW_MODES[view]) {
    return view;
  }

  try {
    const stored = window.localStorage.getItem(DASHBOARD_VIEW_STORAGE_KEY);
    if (stored && DASHBOARD_VIEW_MODES[stored]) {
      return stored;
    }
  } catch {
    return "operator";
  }
  return "operator";
}

function renderDashboardViewModes() {
  if (!dashboardViewRoot) {
    return;
  }

  dashboardViewRoot.innerHTML = `
    <section class="dashboard-view-card">
      <div class="dashboard-view-head">
        <div>
          <p class="eyebrow">View mode</p>
          <h2>Choose the lens</h2>
        </div>
      </div>
      <div class="dashboard-view-switch" role="tablist" aria-label="Dashboard view modes">
        ${Object.entries(DASHBOARD_VIEW_MODES)
          .map(
            ([mode, config]) => `
              <button
                class="dashboard-view-button${dashboardViewMode === mode ? " is-active" : ""}"
                type="button"
                role="tab"
                aria-selected="${dashboardViewMode === mode ? "true" : "false"}"
                data-dashboard-view="${escapeHtml(mode)}"
              >
                <strong>${escapeHtml(config.label)}</strong>
                <span>${escapeHtml(config.description)}</span>
              </button>
            `,
          )
          .join("")}
      </div>
    </section>
  `;

  for (const button of dashboardViewRoot.querySelectorAll("[data-dashboard-view]")) {
    button.addEventListener("click", () => {
      setDashboardViewMode(button.dataset.dashboardView || "operator");
    });
  }
}

function setDashboardViewMode(mode) {
  dashboardViewMode = DASHBOARD_VIEW_MODES[mode] ? mode : "operator";
  presentationModeEnabled = dashboardViewMode === "executive";
  document.body.classList.toggle("presentation-mode", presentationModeEnabled);
  document.body.dataset.dashboardView = dashboardViewMode;
  renderDashboardViewModes();

  try {
    window.localStorage.setItem(DASHBOARD_VIEW_STORAGE_KEY, dashboardViewMode);
  } catch {
    // Ignore storage failures and keep the in-memory toggle working.
  }

  if (lastOverviewPayload) {
    renderDashboardPayload(lastOverviewPayload);
  }
  scheduleActiveTabSync();
}

function isExecutiveView() {
  return dashboardViewMode === "executive";
}

function isRuntimeView() {
  return dashboardViewMode === "runtime";
}

function visibleSectionsForView(sections) {
  const items = Array.isArray(sections) ? sections : [];
  if (isExecutiveView()) {
    return items.filter((section) => section.group === "reviewer" && section.id !== "upstream-posture");
  }
  if (isRuntimeView()) {
    return items.filter((section) => RUNTIME_SECTION_IDS.has(section.id));
  }
  return items;
}

function visibleTabsForView(tabs) {
  const items = Array.isArray(tabs) ? tabs : [];
  if (isExecutiveView()) {
    return items.filter((tab) => tab.group === "reviewer" && tab.id !== "upstream-posture");
  }
  if (isRuntimeView()) {
    return items.filter((tab) => RUNTIME_SECTION_IDS.has(tab.id));
  }
  return items;
}

function renderHero(payload) {
  const defaultTitle = payload.title || "AI Trust & Security Stack Control Plane";
  const defaultCopy = `${payload.subtitle ? `${payload.subtitle} ` : ""}${payload.hero_copy || ""}`.trim();
  const presenterTitle = "AI Trust & Security Review Brief";
  const presenterCopy =
    "Use this audience-facing view to explain the current posture, main blocker, and strongest governed proof without the operator-only drill-down.";
  const runtimeTitle = "Governed Live Runtime Workspace";
  const runtimeCopy =
    "Focus on the current Onyx path, runtime proof, live session state, and the activity that confirms the governed handoff is doing real work.";

  if (heroEyebrow) {
    heroEyebrow.textContent = isExecutiveView()
      ? "Executive review mode"
      : isRuntimeView()
        ? "Live runtime focus"
        : "Trust & Security Operations Dashboard";
  }

  if (heroTitle) {
    heroTitle.textContent = isExecutiveView() ? presenterTitle : isRuntimeView() ? runtimeTitle : defaultTitle;
  }

  if (heroCopy) {
    heroCopy.textContent = isExecutiveView() ? presenterCopy : isRuntimeView() ? runtimeCopy : defaultCopy;
  }

  const mode = payload.data_mode || {};
  heroMeta.innerHTML = `
    ${isExecutiveView() ? '<span class="chip">Executive view</span>' : ""}
    ${isRuntimeView() ? '<span class="chip">Live runtime view</span>' : ""}
    <span class="chip">${escapeHtml(payload.runtime_module || "Governed runtime")}</span>
    <span class="${statusClass(mode.status || "neutral")}" title="${escapeHtml(mode.label || "Dashboard mode")}">${escapeHtml(mode.display_label || mode.label || "Dashboard mode")}</span>
    <span class="chip">Generated ${escapeHtml(formatTimestamp(payload.generated_at))}</span>
  `;

  const landingSteps = isExecutiveView()
    ? [
        "Start with the posture banner.",
        "Use the guided walkthrough to tell the story.",
        "Open blocked or approved proof as needed.",
        "Return to full view for operator detail.",
      ]
    : isRuntimeView()
      ? [
          "Confirm the live session and stack state.",
          "Open the embedded runtime workspace.",
          "Watch current Onyx activity and trace continuity.",
          "Drop into technical sections only when runtime proof looks off.",
        ]
    : Array.isArray(payload.landing_steps)
      ? payload.landing_steps
      : [];
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

function compactSectionDescription(section) {
  const description = String(section.description || "");
  if (section.group !== "operator" || description.length <= 120) {
    return description;
  }

  const firstSentence = description.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim();
  if (firstSentence && firstSentence.length >= 50) {
    return firstSentence;
  }

  return `${description.slice(0, 117).trimEnd()}...`;
}

function updateLiveRuntimeLink(payload) {
  if (!liveRuntimeLink) {
    return;
  }

  const sessionReady = Boolean(payload?.authenticated);
  const helperEnabled = payload?.enabled !== false;
  const needsRestart = Boolean(payload?.cookie_present) && !sessionReady && helperEnabled;

  liveRuntimeLink.classList.remove("is-disabled");
  liveRuntimeLink.removeAttribute("aria-disabled");

  if (sessionReady) {
    liveRuntimeLink.textContent = "Open live workspace";
    liveRuntimeLink.href = payload.workspace_href || "/launch/onyx?path=/app&mode=live&view=embedded";
    liveRuntimeLink.title = "Open the governed live workspace using the active dev session";
    return;
  }

  if (helperEnabled) {
    liveRuntimeLink.textContent = needsRestart ? "Restart dev live workspace" : "Start dev live workspace";
    liveRuntimeLink.href = payload?.start_href || "/auth/live-session/start?next=%2Flaunch%2Fonyx%3Fpath%3D%2Fapp%26mode%3Dlive%26view%3Dembedded";
    liveRuntimeLink.title = "Mint a dev-only live session cookie and open the governed live workspace";
    return;
  }

  liveRuntimeLink.textContent = "Live workspace helper unavailable";
  liveRuntimeLink.href = payload?.start_href || "/auth/live-session/start?next=%2Flaunch%2Fonyx%3Fpath%3D%2Fapp%26mode%3Dlive%26view%3Dembedded";
  liveRuntimeLink.title = "This dev-only helper is unavailable in the current environment";
  liveRuntimeLink.classList.add("is-disabled");
  liveRuntimeLink.setAttribute("aria-disabled", "true");
}

function buildLiveSessionMeta(payload) {
  if (!payload) {
    return [];
  }

  const items = [
    payload.dev_only ? { label: "Scope", value: "dev-only", status: "warning" } : null,
    payload.environment_mode
      ? { label: "Mode", value: String(payload.environment_mode).toUpperCase(), status: "neutral" }
      : null,
    payload.username ? { label: "User", value: payload.username, status: payload.authenticated ? "healthy" : "neutral" } : null,
    payload.tenant_id ? { label: "Tenant", value: payload.tenant_id, status: payload.authenticated ? "healthy" : "neutral" } : null,
    payload.session_id ? { label: "Session", value: payload.session_id, status: "neutral" } : null,
    payload.expires_at ? { label: "Expires", value: payload.expires_at, kind: "timestamp", status: "neutral" } : null,
    Number.isFinite(payload.expires_in_seconds)
      ? { label: "TTL", value: formatRemainingDuration(payload.expires_in_seconds), status: payload.expires_in_seconds > 0 ? "neutral" : "critical" }
      : null,
  ];

  return items.filter(Boolean);
}

function renderLiveSession(payload) {
  if (!liveSessionRoot) {
    return;
  }

  lastLiveSessionPayload = payload;
  updateLiveRuntimeLink(payload);

  const status = payload?.status || "neutral";
  const actions = [];
  if (payload?.cookie_present) {
    actions.push(`<a class="hero-action-button hero-action-button-secondary" href="${escapeHtml(payload.end_href || "/auth/live-session/end?next=%2F")}">${escapeHtml(payload.authenticated ? "End dev session" : "Clear live-session cookie")}</a>`);
  }
  if (payload?.authenticated && payload?.workspace_href) {
    actions.push(`<a class="hero-action-button hero-action-button-secondary" href="${escapeHtml(payload.workspace_href)}">Re-open workspace</a>`);
  }

  liveSessionRoot.innerHTML = `
    <section class="live-session-banner live-session-banner-${escapeHtml(status)}">
      <div class="live-session-head">
        <div>
          <p class="eyebrow">Dev live session</p>
          <h2 class="live-session-title">${escapeHtml(payload?.status_label || "Live session")}</h2>
          <p class="live-session-copy">${escapeHtml(payload?.summary || "Session state unavailable.")}</p>
        </div>
        ${renderStatusPill(status, { label: payload?.status_label || statusLabel(status) })}
      </div>
      ${renderMetaBadges(buildLiveSessionMeta(payload), "live-session-meta")}
      ${payload?.detail ? `<p class="live-session-detail">${escapeHtml(payload.detail)}</p>` : ""}
      ${actions.length ? `<div class="live-session-actions">${actions.join("")}</div>` : ""}
    </section>
  `;
}

function renderLiveSessionError(error) {
  if (!liveSessionRoot) {
    return;
  }

  updateLiveRuntimeLink({
    enabled: true,
    authenticated: false,
    cookie_present: false,
    start_href: "/auth/live-session/start?next=%2Flaunch%2Fonyx%3Fpath%3D%2Fapp%26mode%3Dlive%26view%3Dembedded",
  });
  liveSessionRoot.innerHTML = `
    <section class="live-session-banner live-session-banner-warning">
      <div class="live-session-head">
        <div>
          <p class="eyebrow">Dev live session</p>
          <h2 class="live-session-title">Session state unavailable</h2>
          <p class="live-session-copy">The dashboard could not check the current dev live-session cookie right now.</p>
        </div>
        ${renderStatusPill("warning", { label: "Needs attention" })}
      </div>
      <p class="live-session-detail">${escapeHtml(error.message || "Unknown error")}</p>
    </section>
  `;
}

function renderRuntimeSummary(summary) {
  if (!runtimeSummaryRoot) {
    return;
  }

  if (!summary?.title) {
    runtimeSummaryRoot.innerHTML = "";
    return;
  }

  const items = Array.isArray(summary.items) ? summary.items : [];
  const actions = Array.isArray(summary.actions) ? summary.actions : [];
  runtimeSummaryRoot.innerHTML = `
    <section class="hero-runtime-card hero-runtime-${escapeHtml(summary.status || "neutral")}">
      <div class="hero-runtime-head">
        <div>
          <p class="eyebrow">${escapeHtml(summary.eyebrow || "Live runtime")}</p>
          <h2 class="hero-runtime-title">${escapeHtml(summary.title || "Runtime status")}</h2>
          <p class="hero-runtime-summary">${escapeHtml(summary.summary || "")}</p>
        </div>
        ${renderStatusPill(summary.status || "neutral")}
      </div>
      ${renderMetaBadges(summary.meta_badges || [], "hero-runtime-meta")}
      <p class="hero-runtime-detail">${escapeHtml(summary.detail || "")}</p>
      <div class="hero-runtime-grid">
        ${items
          .map(
            (item) => `
              <article class="hero-runtime-stat hero-runtime-stat-${escapeHtml(item.status || "neutral")}">
                <span class="hero-runtime-stat-label">${escapeHtml(item.display_label || item.label || "")}</span>
                <strong>${escapeHtml(item.display_value || item.value || "")}</strong>
                <p>${escapeHtml(item.display_detail || item.detail || "")}</p>
              </article>
            `,
          )
          .join("")}
      </div>
      ${
        actions.length
          ? `
            <div class="hero-runtime-actions">
              ${actions
                .map(
                  (action) => `
                    <a class="audience-link-pill"${linkAttributes(action.href)}>
                      ${escapeHtml(action.display_label || action.label || "")}
                    </a>
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

function renderStackHealth(payload) {
  if (!stackHealthRoot) {
    return;
  }

  if (!payload?.label) {
    stackHealthRoot.innerHTML = "";
    return;
  }

  const groups = Array.isArray(payload.groups) ? payload.groups : [];
  stackHealthRoot.innerHTML = `
    <section class="stack-health-card stack-health-${escapeHtml(payload.status || "neutral")}">
      <div class="stack-health-head">
        <div>
          <p class="eyebrow">Stack health</p>
          <h2>${escapeHtml(payload.label || "Stack status")}</h2>
          <p class="stack-health-summary">${escapeHtml(payload.summary || "")}</p>
        </div>
        ${renderStatusPill(payload.status || "neutral")}
      </div>
      ${renderMetaBadges(payload.badges || [], "stack-health-meta")}
      <p class="stack-health-detail">${escapeHtml(payload.detail || "")}</p>
      <details class="stack-health-disclosure"${isRuntimeView() ? " open" : ""}>
        <summary>Show service breakdown</summary>
        <div class="stack-health-groups">
          ${groups
            .map(
              (group) => `
                <section class="stack-health-group">
                  <p class="eyebrow">${escapeHtml(group.title || "Services")}</p>
                  <div class="stack-health-service-grid">
                    ${(Array.isArray(group.items) ? group.items : [])
                      .map(
                        (item) => `
                          <article class="stack-health-service stack-health-service-${escapeHtml(item.status || "neutral")}">
                            <div class="card-topline">
                              <span class="metric-label">${escapeHtml(item.label || item.service || "")}</span>
                              ${renderStatusPill(item.status || "neutral", { hideNeutral: true })}
                            </div>
                            <strong>${escapeHtml(item.state || "unknown")}</strong>
                            <p>${escapeHtml(item.detail || "")}</p>
                          </article>
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
      ${
        payload.action?.href
          ? `<a class="audience-link-pill stack-health-link"${linkAttributes(payload.action.href)}>${escapeHtml(payload.action.label || "Open runbook")}</a>`
          : ""
      }
    </section>
  `;
}

function renderModeBanner(modeBanner) {
  if (!modeBannerRoot) {
    return;
  }

  const chips = Array.isArray(modeBanner.chips) ? modeBanner.chips : [];
  const consequences = Array.isArray(modeBanner.consequences) ? modeBanner.consequences : [];
  const detail = modeBanner.display_detail || modeBanner.detail || "";
  const disclosureLabel = modeBanner.disclosure_label || "What this mode means";
  modeBannerRoot.innerHTML = `
    <section class="mode-banner mode-${escapeHtml(modeBanner.status || "neutral")}">
      <div class="mode-banner-head">
        <div>
          <p class="eyebrow">Governance mode</p>
          <h2>${escapeHtml(modeBanner.display_label || modeBanner.label || "Governance mode unavailable")}</h2>
          <p class="section-description">${escapeHtml(modeBanner.display_summary || modeBanner.summary || "")}</p>
        </div>
        ${renderStatusPill(modeBanner.status || "neutral", { label: modeBanner.status_label })}
      </div>
      ${detail ? `<p class="mode-banner-detail">${escapeHtml(detail)}</p>` : ""}
      ${
        chips.length
          ? `
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
          `
          : ""
      }
      ${
        consequences.length
          ? `
            <details class="mode-banner-disclosure">
              <summary>${escapeHtml(disclosureLabel)}</summary>
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

  if (isRuntimeView()) {
    riskStripRoot.innerHTML = "";
    return;
  }

  const items = Array.isArray(strip.items) ? strip.items : [];
  if (!items.length) {
    riskStripRoot.innerHTML = "";
    return;
  }

  riskStripRoot.innerHTML = `
    <section class="risk-strip-card"${changeAttributes("risk-strip")}>
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
              <${item.href ? "a" : "article"} class="risk-stat-card risk-stat-${escapeHtml(item.status || "neutral")}"${linkAttributes(item.href)}${changeAttributes(`risk:${normalizeKeyFragment(item.label || item.display_label)}`)}>
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
    <section class="incident-banner incident-banner-${escapeHtml(banner.status || "warning")}"${changeAttributes("incident-banner")}>
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

function renderNextAction(nextAction) {
  if (!nextActionRoot) {
    return;
  }

  if (!nextAction?.title) {
    nextActionRoot.innerHTML = "";
    return;
  }

  const status = nextAction.status || "neutral";
  const primaryAction = nextAction.primary_action || null;
  const secondaryActions = Array.isArray(nextAction.secondary_actions) ? nextAction.secondary_actions : [];
  const steps = Array.isArray(nextAction.steps) ? nextAction.steps : [];

  nextActionRoot.innerHTML = `
    <section class="next-action-card next-action-${escapeHtml(status)}"${changeAttributes("next-action")}>
      <div class="next-action-layout">
        <div class="next-action-copy">
          <div class="card-topline">
            <div>
              <p class="eyebrow">${escapeHtml(nextAction.eyebrow || "Recommended next action")}</p>
              <h3>${escapeHtml(nextAction.title || "Take the next review step")}</h3>
            </div>
            ${renderStatusPill(status)}
          </div>
          <p class="next-action-summary">${escapeHtml(nextAction.summary || "")}</p>
          ${renderTrendSummary(nextAction.change, "What changed since last refresh")}
          <div class="next-action-actions">
            ${
              primaryAction
                ? `
                  <a class="action-pill action-pill-${escapeHtml(primaryAction.status || status)} next-action-primary"${linkAttributes(primaryAction.href)}>
                    ${escapeHtml(primaryAction.display_label || primaryAction.label || "Open action")}
                  </a>
                `
                : ""
            }
            ${secondaryActions
              .map(
                (action) => `
                  <a class="audience-link-pill"${linkAttributes(action.href)}>
                    ${escapeHtml(action.display_label || action.label || "")}
                  </a>
                `,
              )
              .join("")}
          </div>
        </div>
        ${
          steps.length
            ? `
              <aside class="next-action-steps-panel">
                <p class="eyebrow">Suggested path</p>
                <ol class="next-action-steps">
                  ${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}
                </ol>
              </aside>
            `
            : ""
        }
      </div>
    </section>
  `;
}

function renderSummarySheet(summary) {
  if (!summarySheetRoot) {
    return;
  }

  if (!presentationModeEnabled || !summary?.title) {
    summarySheetRoot.innerHTML = "";
    return;
  }

  const bullets = Array.isArray(summary.bullets) ? summary.bullets : [];
  summarySheetRoot.innerHTML = `
    <section class="summary-sheet-card"${changeAttributes("presentation-summary")}>
      <div class="summary-sheet-head">
        <div>
          <p class="eyebrow">${escapeHtml(summary.eyebrow || "Share summary")}</p>
          <h2>${escapeHtml(summary.title || "External summary")}</h2>
        </div>
        ${renderStatusPill(summary.status || "neutral")}
      </div>
      <p class="summary-sheet-summary">${escapeHtml(summary.summary || "")}</p>
      <div class="summary-sheet-grid">
        <div class="summary-sheet-panel">
          <p class="eyebrow">Talking points</p>
          <div class="summary-sheet-bullet-list">
            ${bullets.map((bullet) => `<p>${escapeHtml(bullet)}</p>`).join("")}
          </div>
        </div>
        <div class="summary-sheet-panel">
          <p class="eyebrow">Export options</p>
          <div class="summary-sheet-actions">
            <button class="summary-sheet-button" type="button" data-summary-action="copy">Copy summary</button>
            <button class="summary-sheet-button" type="button" data-summary-action="print">Print brief</button>
          </div>
        </div>
      </div>
    </section>
  `;

  for (const button of summarySheetRoot.querySelectorAll("[data-summary-action]")) {
    button.addEventListener("click", async () => {
      const action = button.dataset.summaryAction;
      if (action === "copy") {
        try {
          if (!navigator.clipboard?.writeText) {
            throw new Error("Clipboard unavailable");
          }
          await navigator.clipboard.writeText(summary.export_text || summary.summary || "");
          button.textContent = "Copied";
          window.setTimeout(() => {
            button.textContent = "Copy summary";
          }, 1500);
        } catch {
          button.textContent = "Copy failed";
          window.setTimeout(() => {
            button.textContent = "Copy summary";
          }, 1500);
        }
      }

      if (action === "print") {
        window.print();
      }
    });
  }
}

function renderWalkthrough(walkthrough) {
  if (!walkthroughRoot) {
    return;
  }

  if (isRuntimeView()) {
    walkthroughRoot.innerHTML = "";
    return;
  }

  const steps = Array.isArray(walkthrough) ? walkthrough.filter((item) => item && item.href) : [];
  if (!steps.length) {
    walkthroughRoot.innerHTML = "";
    return;
  }

  walkthroughRoot.innerHTML = `
    <section class="walkthrough-card"${changeAttributes("walkthrough")}>
      <details class="walkthrough-disclosure"${isExecutiveView() ? " open" : ""}>
        <summary>
          <span>
            <span class="eyebrow">Guided walkthrough</span>
            <strong>Tell the story in four steps</strong>
          </span>
          <span class="walkthrough-summary-note">${isExecutiveView() ? "Open in executive view" : "Open when you need a clean review flow"}</span>
        </summary>
        <div class="walkthrough-disclosure-body">
          <p class="record-detail">Use these shortcuts when you need a clean review flow instead of a full free-form scan.</p>
          <div class="walkthrough-grid">
            ${steps
              .map(
                (step, index) => `
                  <a class="walkthrough-step-card walkthrough-step-${escapeHtml(step.status || "neutral")}"${linkAttributes(step.href)}>
                    <span class="walkthrough-step-index">${index + 1}</span>
                    <div class="walkthrough-step-copy">
                      <p class="walkthrough-step-title">${escapeHtml(step.display_label || step.label || "")}</p>
                      <p class="walkthrough-step-description">${escapeHtml(step.display_description || step.description || "")}</p>
                    </div>
                  </a>
                `,
              )
              .join("")}
          </div>
        </div>
      </details>
    </section>
  `;
}

function renderCompareFieldGrid(fields) {
  const items = Array.isArray(fields) ? fields.filter((item) => item && item.value) : [];
  if (!items.length) {
    return "";
  }

  return `
    <div class="compare-field-grid">
      ${items
        .map(
          (field) => `
            <article class="compare-field-card">
              <span class="compare-field-label">${escapeHtml(field.label || "")}</span>
              <strong>${escapeHtml(field.value || "")}</strong>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderCompareExample(item, key) {
  if (!item) {
    return "";
  }

  return `
    <${item.href ? "a" : "article"} class="compare-example-card compare-example-${escapeHtml(item.status || "neutral")}"${linkAttributes(item.href)}${changeAttributes(key)}>
      <div class="card-topline">
        <div>
          <p class="eyebrow">${escapeHtml(item.eyebrow || "")}</p>
          <h3>${escapeHtml(item.title || "")}</h3>
        </div>
        ${renderStatusPill(item.status || "neutral")}
      </div>
      <p class="record-detail">${escapeHtml(item.detail || "")}</p>
      ${renderMetaBadges(item.meta_badges, "evidence-meta-row")}
      ${renderCompareFieldGrid(item.fields)}
    </${item.href ? "a" : "article"}>
  `;
}

function renderCompareView(compare) {
  if (!compareRoot) {
    return;
  }

  if (isRuntimeView()) {
    compareRoot.innerHTML = "";
    return;
  }

  if (!compare?.title) {
    compareRoot.innerHTML = "";
    return;
  }

  const contrasts = Array.isArray(compare.contrasts) ? compare.contrasts : [];
  compareRoot.innerHTML = `
    <section class="compare-card"${changeAttributes("example-compare")}>
      <div class="support-card-head">
        <div>
          <p class="eyebrow">${escapeHtml(compare.eyebrow || "Compare outcomes")}</p>
          <h3>${escapeHtml(compare.title || "Approved and blocked examples")}</h3>
        </div>
      </div>
      <p class="record-detail">${escapeHtml(compare.detail || "")}</p>
      <div class="compare-grid">
        ${renderCompareExample(compare.approved, "compare:approved")}
        ${renderCompareExample(compare.blocked, "compare:blocked")}
      </div>
      ${
        contrasts.length
          ? `
            <div class="compare-contrast-grid">
              ${contrasts
                .map(
                  (row) => `
                    <article class="compare-contrast-row">
                      <span class="compare-contrast-label">${escapeHtml(row.label || "")}</span>
                      <div class="compare-contrast-values">
                        <p><strong>Approved:</strong> ${escapeHtml(row.approved || "")}</p>
                        <p><strong>Blocked:</strong> ${escapeHtml(row.blocked || "")}</p>
                      </div>
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
            <${item.href ? "a" : "article"} class="metric-card"${linkAttributes(item.href)}${changeAttributes(item.id ? `card:${item.id}` : "")}>
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

  if (isRuntimeView()) {
    kpiRoot.innerHTML = "";
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
            (path) => {
              const audienceType = String(path.title || "").toLowerCase().includes("technical") ? "technical" : "reviewer";
              return `
              <section class="audience-path-card audience-path-${escapeHtml(audienceType)}" data-audience="${escapeHtml(audienceType)}">
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
            `;
            },
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

  if (isRuntimeView()) {
    readingGuideRoot.innerHTML = "";
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

function blockTypeLabel(type) {
  return {
    cards: "Snapshot",
    records: "Evidence log",
    table: "Reference table",
    links: "Source links",
  }[type] || "Section";
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
        <section class="block block-type-${escapeHtml(block.type || "default")}" data-block-type="${escapeHtml(block.type || "default")}">
          <div class="block-head">
            <p class="block-kicker">${escapeHtml(blockTypeLabel(block.type))}</p>
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
  const filteredSections = visibleSectionsForView(sections);
  root.innerHTML = filteredSections
    .map((section) => {
      const nextGroup = section.group || "";
      const groupBanner =
        nextGroup && nextGroup !== activeGroup
          ? `
            <section class="section-group-banner section-group-${escapeHtml(nextGroup)}" data-group="${escapeHtml(nextGroup)}">
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
        <section class="dashboard-section section-${escapeHtml(section.id || "")}" data-section="${escapeHtml(section.id || "")}" data-group="${escapeHtml(section.group || "")}" id="${escapeHtml(section.id || "")}">
          <div class="section-head">
            <p class="eyebrow">${escapeHtml(section.id || "")}</p>
            <h2>${escapeHtml(section.title || "")}</h2>
            <p class="section-description">${escapeHtml(compactSectionDescription(section))}</p>
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
  const sections = Array.from(root.querySelectorAll(".dashboard-section[id]")).filter((section) => section.offsetParent !== null);
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

function renderFreshnessStrip(bar) {
  const items = Array.isArray(bar.items) ? bar.items : [];
  if (!items.length) {
    return "";
  }

  return `
    <div class="freshness-strip"${changeAttributes("freshness-strip")}>
      <span class="freshness-strip-title">${escapeHtml(bar.title || "Current proof")}</span>
      <div class="freshness-strip-row">
        ${items
          .map(
            (item) => `
              <span class="freshness-strip-chip freshness-strip-chip-${escapeHtml(item.status || "neutral")}">
                <span class="freshness-strip-chip-label">${escapeHtml(item.label || "")}</span>
                <strong>${escapeHtml(item.value || "")}</strong>
              </span>
            `,
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderTabs(tabs, freshnessBar = {}) {
  const groups = new Map();
  const allTabs = visibleTabsForView(tabs);
  for (const tab of allTabs) {
    const groupLabel = tab.group_label || "Sections";
    if (!groups.has(groupLabel)) {
      groups.set(groupLabel, []);
    }
    groups.get(groupLabel).push(tab);
  }

  const primaryTabs = (
    isRuntimeView()
      ? allTabs
      : isExecutiveView()
        ? allTabs.filter((tab) => tab.group === "reviewer")
        : allTabs.filter((tab) => tab.group === "reviewer")
  ).slice(0, 6);
  const quickJumpTitle = isRuntimeView() ? "Live runtime jump" : "Quick jump";
  const quickJumpDescription = isRuntimeView()
    ? "Use the short row for the current workspace path, handoff proof, and technical runtime checks."
    : "Use the short row for the main story. Open the full list only for deeper drill-down.";

  tabStrip.innerHTML = `
    <section class="tab-strip-shell">
      <div class="tab-strip-head">
        <div>
          <p class="eyebrow">${escapeHtml(quickJumpTitle)}</p>
          <p class="section-description">${escapeHtml(quickJumpDescription)}</p>
        </div>
      </div>
      ${renderFreshnessStrip(freshnessBar)}
      <div class="tab-group-row tab-primary-row">
        ${primaryTabs
          .map(
            (tab) => `
              <button class="tab-button" type="button" data-target="${escapeHtml(tab.id || "")}" data-tab-group="${escapeHtml(tab.group || "")}" aria-pressed="false">
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
                <section class="tab-group" data-tab-group="${escapeHtml(groupTabs[0]?.group || "")}">
                  <p class="eyebrow">${escapeHtml(groupLabel)}</p>
                  <div class="tab-group-row">
                    ${groupTabs
                      .map(
                        (tab) => `
                          <button class="tab-button" type="button" data-target="${escapeHtml(tab.id || "")}" data-tab-group="${escapeHtml(tab.group || "")}" aria-pressed="false">
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

function liveLogNormalizedStatus(entry) {
  const status = String(entry?.status || "").toLowerCase();
  if (status) {
    return status;
  }

  const severity = String(entry?.severity || "").toLowerCase();
  if (severity === "critical" || severity === "error") {
    return "critical";
  }
  if (severity === "warning" || severity === "warn") {
    return "warning";
  }
  return "neutral";
}

function liveLogMatchesFilters(entry) {
  const matchesStatus = liveLogStatusFilter === "all" || liveLogNormalizedStatus(entry) === liveLogStatusFilter;
  const matchesSource = liveLogSourceFilter === "all" || String(entry?.source_label || "") === liveLogSourceFilter;
  return matchesStatus && matchesSource;
}

function renderLiveLog(payload) {
  if (!liveLogRoot) {
    return;
  }

  lastLiveLogPayload = payload;
  const entries = Array.isArray(payload.entries) ? payload.entries : [];
  const sources = [...new Set(entries.map((entry) => String(entry.source_label || "")).filter(Boolean))].sort();
  if (liveLogSourceFilter !== "all" && !sources.includes(liveLogSourceFilter)) {
    liveLogSourceFilter = "all";
  }
  const filteredEntries = entries.filter(liveLogMatchesFilters);
  const refreshedAt = formatTimestamp(payload.generated_at);
  const intervalSeconds = Math.max(1, Math.round((payload.poll_interval_ms || DEFAULT_LIVE_LOG_POLL_MS) / 1000));

  liveLogRoot.innerHTML = `
    <div class="live-log-toolbar">
      <div class="hero-meta">
        <span class="chip">Auto-refresh ${intervalSeconds}s</span>
        <span class="chip">Last updated ${escapeHtml(refreshedAt)}</span>
        <span class="chip">Showing ${escapeHtml(String(filteredEntries.length))} of ${escapeHtml(String(entries.length))} recent items</span>
      </div>
      <a class="live-log-source"${linkAttributes(payload.source_href || "/api/control-plane/live-log?limit=50")}>
        Open activity feed
      </a>
    </div>
    <div class="live-log-controls">
      <div class="live-log-filter-group" role="toolbar" aria-label="Activity severity filters">
        ${[
          ["all", "All activity"],
          ["critical", "Critical"],
          ["warning", "Warnings"],
          ["neutral", "Info"],
        ]
          .map(
            ([value, label]) => `
              <button
                class="live-log-filter-button${liveLogStatusFilter === value ? " is-active" : ""}"
                type="button"
                data-live-log-status="${escapeHtml(value)}"
                aria-pressed="${liveLogStatusFilter === value ? "true" : "false"}"
              >
                ${escapeHtml(label)}
              </button>
            `,
          )
          .join("")}
      </div>
      <label class="live-log-filter-select">
        <span>Source</span>
        <select id="live-log-source-filter">
          <option value="all">All sources</option>
          ${sources
            .map(
              (source) => `
                <option value="${escapeHtml(source)}"${liveLogSourceFilter === source ? " selected" : ""}>${escapeHtml(source)}</option>
              `,
            )
            .join("")}
        </select>
      </label>
    </div>
    <div class="live-log-list">
      ${
        filteredEntries.length
          ? filteredEntries
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
              <h3>No matching activity right now</h3>
              <p class="live-log-summary">Adjust the filters to widen the activity view, or wait for the next refresh.</p>
            </article>
          `
      }
    </div>
  `;

  for (const button of liveLogRoot.querySelectorAll("[data-live-log-status]")) {
    button.addEventListener("click", () => {
      liveLogStatusFilter = button.dataset.liveLogStatus || "all";
      renderLiveLog(lastLiveLogPayload || payload);
    });
  }

  const sourceSelect = liveLogRoot.querySelector("#live-log-source-filter");
  if (sourceSelect) {
    sourceSelect.addEventListener("change", (event) => {
      liveLogSourceFilter = event.target.value || "all";
      renderLiveLog(lastLiveLogPayload || payload);
    });
  }
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

async function loadLiveSession() {
  try {
    const response = await fetch("/api/control-plane/live-session", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Live session API returned ${response.status}`);
    }

    renderLiveSession(await response.json());
  } catch (error) {
    renderLiveSessionError(error);
  }
}

function renderDashboardPayload(payload) {
  renderDashboardViewModes();
  renderHero(payload);
  renderSummarySheet(payload.command_center?.presentation_summary || {});
  renderRuntimeSummary(payload.command_center?.runtime_summary || {});
  renderStackHealth(payload.stack_health || {});
  renderModeBanner(payload.mode_banner || {});
  renderIncidentBanner(payload.command_center?.incident_banner || {});
  renderRiskStrip(payload.command_center?.risk_strip || {});
  renderNextAction(payload.command_center?.next_action || {});
  renderWalkthrough(payload.command_center?.walkthrough || []);
  renderCompareView(payload.command_center?.example_compare || {});
  renderBriefing(payload.command_center || {});
  renderProofPipeline(payload.command_center?.proof_pipeline || {});
  renderReadingGuide(payload.reading_guide || {});
  renderKpis(payload.audience_paths || []);
  renderSections(payload.sections);
  renderTabs(payload.tabs, payload.command_center?.freshness_bar || {});
  renderSources(payload.sources);
  applyChangeHighlights();
}

async function boot() {
  try {
    const response = await fetch("/api/control-plane/overview", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Dashboard API returned ${response.status}`);
    }

    const payload = await response.json();
    updateDashboardChangeTracking(payload);
    lastOverviewPayload = payload;
    renderDashboardPayload(payload);
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
    if (nextActionRoot) {
      nextActionRoot.innerHTML = "";
    }
    if (summarySheetRoot) {
      summarySheetRoot.innerHTML = "";
    }
    if (walkthroughRoot) {
      walkthroughRoot.innerHTML = "";
    }
    if (compareRoot) {
      compareRoot.innerHTML = "";
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
    if (dashboardViewRoot) {
      dashboardViewRoot.innerHTML = "";
    }
    if (runtimeSummaryRoot) {
      runtimeSummaryRoot.innerHTML = "";
    }
    if (stackHealthRoot) {
      stackHealthRoot.innerHTML = "";
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
  await loadLiveSession();

  if (refreshDashboardButton) {
    refreshDashboardButton.disabled = false;
    refreshDashboardButton.textContent = "Refresh evidence";
  }
}

dashboardViewMode = resolveInitialDashboardViewMode();
presentationModeEnabled = dashboardViewMode === "executive";
document.body.classList.toggle("presentation-mode", presentationModeEnabled);
document.body.dataset.dashboardView = dashboardViewMode;
renderDashboardViewModes();

if (refreshDashboardButton) {
  refreshDashboardButton.addEventListener("click", () => {
    refreshDashboard();
  });
}

boot();
loadLiveLog();
loadLiveSession();
