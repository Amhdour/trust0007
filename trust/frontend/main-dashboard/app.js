const root = document.getElementById("dashboard-root");
const tabStrip = document.getElementById("tab-strip");
const heroEyebrow = document.getElementById("hero-eyebrow");
const heroTitle = document.getElementById("hero-title");
const heroCopy = document.getElementById("hero-copy");
const heroMeta = document.getElementById("hero-meta");
const runtimeLanesMeta = document.getElementById("runtime-lanes-meta");
// Legacy roots retained as no-op placeholders while cleanup converges.
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
const trustScorecardRoot = document.getElementById("trust-scorecard-root");
const secondaryContextRoot = document.getElementById("secondary-context-root");
const runtimePortfolioRoot = document.getElementById("runtime-portfolio-root");
const launchDecisionRoot = document.getElementById("launch-decision-root");
const audienceModesRoot = document.getElementById("audience-modes-root");
const liveOnyxProjectRoot = document.getElementById("live-onyx-project-root");
const ragProofChainRoot = document.getElementById("rag-proof-chain-root");
const whyNotGoRoot = document.getElementById("why-not-go-root");
const launchGatePacketRoot = document.getElementById("launch-gate-packet-root");
const liveRuntimeLink = document.getElementById("live-runtime-link");
const liveOnyxAgentLink = document.getElementById("live-onyx-link");
const viewEvidenceLink = document.getElementById("view-evidence-link");
const refreshDashboardButton = document.getElementById("refresh-dashboard-button");

const LIVE_LOG_LIMIT = 6;
const DEFAULT_LIVE_LOG_POLL_MS = 5000;
const SECTION_SCROLL_OFFSET_PX = 152;
const LIVE_LOG_STATUS_FILTERS = [
  ["all", "All activity"],
  ["critical", "Critical"],
  ["warning", "Warnings"],
  ["neutral", "Info"],
];
const DASHBOARD_VIEW_MODES = { operator: { label: "Operator" } };
const AUDIENCE_MODES = [
  { id: "executive", label: "Executive View" },
  { id: "security", label: "Security Reviewer View" },
  { id: "operator", label: "Operator View" },
  { id: "evidence", label: "Evidence/API View" },
];
const decisionModel = window.DashboardDecisionModel || {};
// Keep a single source of truth for visible drill-down sections in the
// shared control plane. New dual-runtime IDs are primary, while legacy IDs
// remain supported for backwards compatibility with older payloads.
const SECTION_ID_ALIASES = {
  "launch-gate": "runtime-portfolio",
  "entry-points": "rag-runtime-access",
  "onyx-agent-access": "agent-runtime-access",
};
const LEGACY_SECTION_ID_BY_CANONICAL = {
  "runtime-portfolio": "launch-gate",
  "rag-runtime-access": "entry-points",
  "agent-runtime-access": "onyx-agent-access",
};
const ACTIVE_DRILLDOWN_SECTION_IDS = new Set([
  "runtime-portfolio",
  "rag-runtime-access",
  "launch-gate",
  "entry-points",
  "policy-enforcement",
  "retrieval-boundaries",
  "audit-replay",
]);
let liveLogTimer = 0;
let activeTabTarget = "";
let activeTabSyncFrame = 0;
let tabStripScrollBound = false;
let presentationModeEnabled = false;
let dashboardViewMode = "operator";
let activeAudienceMode = "executive";
let dashboardSectionQuery = "";
let lastOverviewPayload = null;
let lastLiveLogPayload = null;
let liveLogStatusFilter = "all";
let liveLogSourceFilter = "all";
let dashboardFingerprints = new Map();
let changedDashboardKeys = new Set();
let changeHighlightTimer = 0;
let sectionDisclosureState = new Map();
let lastDerivedDashboardState = null;

function canonicalSectionId(value) {
  return SECTION_ID_ALIASES[value] || value;
}

function resolvedSectionId(value) {
  if (!value) {
    return "";
  }
  if (document.getElementById(value)) {
    return value;
  }
  return LEGACY_SECTION_ID_BY_CANONICAL[value] || value;
}

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

function trustControlStatusPresentation(status) {
  const normalized = String(status || "NEEDS_ATTENTION").toUpperCase();
  return {
    PASS: { uiStatus: "healthy", label: "PASS" },
    FAIL: { uiStatus: "critical", label: "FAIL" },
    MISSING_PROOF: { uiStatus: "critical", label: "MISSING_PROOF" },
    STALE: { uiStatus: "warning", label: "STALE" },
    DEMO_ONLY: { uiStatus: "warning", label: "DEMO_ONLY" },
    NEEDS_ATTENTION: { uiStatus: "warning", label: "NEEDS_ATTENTION" },
  }[normalized] || { uiStatus: "warning", label: normalized };
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

function humanizeLabel(value) {
  const normalized = String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!normalized) {
    return "";
  }

  return normalized.replace(/\b[a-z]/g, (match) => match.toUpperCase());
}

function normalizeSearchText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function searchTokens(value) {
  return normalizeSearchText(value).split(" ").filter(Boolean);
}

function collectSearchableText(value, bucket = []) {
  if (value === null || value === undefined) {
    return bucket;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    bucket.push(String(value));
    return bucket;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      collectSearchableText(item, bucket);
    }
    return bucket;
  }

  if (typeof value === "object") {
    for (const item of Object.values(value)) {
      collectSearchableText(item, bucket);
    }
  }

  return bucket;
}

function matchesSearchQuery(value, query) {
  const tokens = searchTokens(query);
  if (!tokens.length) {
    return true;
  }

  const haystack = normalizeSearchText(Array.isArray(value) ? value.join(" ") : value);
  return tokens.every((token) => haystack.includes(token));
}

function pluralize(count, singular, pluralForm = `${singular}s`) {
  return count === 1 ? singular : pluralForm;
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

function isExecutiveView() {
  return false;
}

function isRuntimeView() {
  return false;
}

function visibleSectionsForView(sections) {
  const items = Array.isArray(sections) ? sections : [];
  return items.filter((section) => ACTIVE_DRILLDOWN_SECTION_IDS.has(canonicalSectionId(section?.id)));
}

function sectionSearchText(section) {
  return collectSearchableText({
    id: section?.id,
    title: section?.title,
    description: section?.description,
    blocks: section?.blocks,
  }).join(" ");
}

function sectionMatchesDashboardQuery(section) {
  return matchesSearchQuery(sectionSearchText(section), dashboardSectionQuery);
}

function filteredSectionsForView(sections) {
  return visibleSectionsForView(sections).filter(sectionMatchesDashboardQuery);
}

function visibleTabsForView(tabs) {
  const items = Array.isArray(tabs) ? tabs : [];
  return items.filter((tab) => ACTIVE_DRILLDOWN_SECTION_IDS.has(canonicalSectionId(tab?.id)));
}

function filteredTabsForView(tabs, sections = []) {
  const items = visibleTabsForView(tabs);
  const query = dashboardSectionQuery.trim();
  if (!query) {
    return items;
  }

  const visibleSectionIds = new Set(filteredSectionsForView(sections).map((section) => section.id));
  return items.filter((tab) => {
    if (visibleSectionIds.has(tab.id)) {
      return true;
    }

    return matchesSearchQuery([tab.id, tab.label, tab.group, tab.group_label], query);
  });
}

function buildSectionSummaryPills(section) {
  const blocks = Array.isArray(section?.blocks) ? section.blocks : [];
  const counts = blocks.reduce((map, block) => {
    const type = block?.type || "other";
    map[type] = (map[type] || 0) + 1;
    return map;
  }, {});

  let drilldownLinks = 0;
  for (const block of blocks) {
    if (Array.isArray(block?.items)) {
      drilldownLinks += block.items.filter((item) => item?.href).length;
    }
  }

  const pills = [
    section?.group === "reviewer" ? "Plain-language lane" : "Technical lane",
    `${blocks.length} ${pluralize(blocks.length, "panel")}`,
  ];

  if (counts.cards) {
    pills.push(`${counts.cards} ${pluralize(counts.cards, "snapshot")}`);
  }
  if (counts.records) {
    pills.push(`${counts.records} ${pluralize(counts.records, "evidence log", "evidence logs")}`);
  }
  if (counts.table) {
    pills.push(`${counts.table} ${pluralize(counts.table, "reference table")}`);
  }
  if (drilldownLinks) {
    pills.push(`${drilldownLinks} ${pluralize(drilldownLinks, "drilldown link")}`);
  }

  return pills.slice(0, 4);
}

function renderSectionSummaryPills(section) {
  const pills = buildSectionSummaryPills(section);
  if (!pills.length) {
    return "";
  }

  return `
    <div class="section-summary-pills">
      ${pills.map((pill) => `<span class="section-summary-pill">${escapeHtml(pill)}</span>`).join("")}
    </div>
  `;
}

function defaultSectionOpen(section) {
  if (dashboardSectionQuery.trim()) {
    return true;
  }

  if (isExecutiveView() || isRuntimeView()) {
    return true;
  }

  return section?.group !== "operator";
}

function isSectionOpen(section) {
  if (dashboardSectionQuery.trim()) {
    return true;
  }

  if (section?.id && sectionDisclosureState.has(section.id)) {
    return sectionDisclosureState.get(section.id);
  }

  return defaultSectionOpen(section);
}

function updateSectionToggleLabel(details) {
  const label = details?.querySelector("[data-section-toggle-label]");
  if (!label) {
    return;
  }

  label.textContent = details.open ? "Hide detail" : "Show detail";
}

function bindSectionDisclosureListeners() {
  for (const details of root.querySelectorAll("[data-section-shell]")) {
    updateSectionToggleLabel(details);
    details.addEventListener("toggle", () => {
      const sectionId = details.dataset.sectionShell || "";
      if (sectionId) {
        sectionDisclosureState.set(sectionId, details.open);
      }
      updateSectionToggleLabel(details);
      scheduleActiveTabSync();
    });
  }
}

function setDashboardSectionQuery(query) {
  const nextQuery = String(query || "");
  if (dashboardSectionQuery === nextQuery) {
    return;
  }

  dashboardSectionQuery = nextQuery;
  if (lastOverviewPayload) {
    renderDashboardPayload(lastOverviewPayload);
  }
}

function bindDashboardFilterControls(container = document) {
  const searchInput = container.querySelector("#dashboard-section-filter");
  if (searchInput) {
    searchInput.addEventListener("input", (event) => {
      setDashboardSectionQuery(event.target.value || "");
    });
  }

  for (const button of container.querySelectorAll("[data-dashboard-filter-clear]")) {
    button.addEventListener("click", () => {
      setDashboardSectionQuery("");
    });
  }
}

function ensureSectionOpen(targetId) {
  const section = document.getElementById(targetId);
  const details = section?.querySelector("[data-section-shell]");
  if (details && !details.open) {
    details.open = true;
  }
}

function renderSectionsEmptyState() {
  root.innerHTML = `
    <section class="dashboard-empty-state">
      <p class="eyebrow">No matches</p>
      <h2>No sections match this filter</h2>
      <p>Try a broader term like runtime, evidence, policy, launch, or trace.</p>
      ${
        dashboardSectionQuery.trim()
          ? '<button class="summary-sheet-button dashboard-filter-reset" type="button" data-dashboard-filter-clear>Clear filter</button>'
          : ""
      }
    </section>
  `;
  bindDashboardFilterControls(root);
}

const HERO_VIEW_CONTENT = {
  default: {
    eyebrow: "AI Trust & Security Control Plane",
    title: (payload) => payload.title || "AI Trust & Security Control Plane",
    copy: (payload) => `${payload.subtitle ? `${payload.subtitle} ` : ""}${payload.hero_copy || ""}`.trim(),
    landingSteps: (payload) => (Array.isArray(payload.landing_steps) ? payload.landing_steps : []),
  },
  executive: {
    eyebrow: "Executive review mode",
    title: () => "AI Trust & Security Review Brief",
    copy: () =>
      "Use this audience-facing view to explain the current posture, main blocker, and strongest governed proof without the operator-only drill-down.",
    landingSteps: () => [
      "Start with the posture banner.",
      "Use the guided walkthrough to tell the story.",
      "Open blocked or approved proof as needed.",
      "Return to full view for operator detail.",
    ],
  },
  runtime: {
    eyebrow: "Live runtime focus",
    title: () => "Governed Live Runtime Workspace",
    copy: () =>
      "Focus on governed runtime paths, runtime proof, authentication requirements, and the activity that confirms governed handoff behavior.",
    landingSteps: () => [
      "Confirm the live session and stack state.",
      "Open the governed runtime workspace.",
      "Watch runtime activity and trace continuity.",
      "Drop into technical sections only when runtime proof looks off.",
    ],
  },
};

function currentHeroView() {
  if (isExecutiveView()) {
    return HERO_VIEW_CONTENT.executive;
  }

  if (isRuntimeView()) {
    return HERO_VIEW_CONTENT.runtime;
  }

  return HERO_VIEW_CONTENT.default;
}

function renderLandingSteps(steps) {
  return steps
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

function renderHero(payload) {
  const heroView = currentHeroView();

  if (heroEyebrow) {
    heroEyebrow.textContent = heroView.eyebrow;
  }

  if (heroTitle) {
    heroTitle.textContent = heroView.title(payload);
  }

  if (heroCopy) {
    heroCopy.textContent = heroView.copy(payload);
  }

  const mode = payload.data_mode || {};
  heroMeta.innerHTML = `
    ${isExecutiveView() ? '<span class="chip">Executive view</span>' : ""}
    ${isRuntimeView() ? '<span class="chip">Live runtime view</span>' : ""}
    <span class="chip">${escapeHtml(payload.runtime_module || "Governed runtime")}</span>
    <span class="${statusClass(mode.status || "neutral")}" title="${escapeHtml(mode.label || "Dashboard mode")}">${escapeHtml(mode.display_label || mode.label || "Dashboard mode")}</span>
    <span class="chip">Generated ${escapeHtml(formatTimestamp(payload.generated_at))}</span>
  `;

  heroSteps.innerHTML = renderLandingSteps(heroView.landingSteps(payload));
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

function updateLiveRuntimeLink() {
  if (!liveRuntimeLink) {
    return;
  }

  liveRuntimeLink.classList.remove("is-disabled");
  liveRuntimeLink.removeAttribute("aria-disabled");
  liveRuntimeLink.textContent = "Open Onyx workspace";
  liveRuntimeLink.href = "/launch/onyx?path=/app&mode=live&view=embedded";
  liveRuntimeLink.title = "Open the governed live workspace; authentication must already be in place";
}

function buildAccessRequirementsMeta(payload) {
  if (!payload) {
    return [];
  }

  const items = [
    { label: "Auth", value: "External OIDC", status: "neutral" },
    payload.data_mode?.label ? { label: "Evidence", value: payload.data_mode.label, status: "neutral" } : null,
    payload.mode_banner?.label ? { label: "Mode", value: payload.mode_banner.label, status: "neutral" } : null,
    { label: "RAG lane", value: "/launch/onyx?path=/app&mode=live", status: "neutral" },
    { label: "Agent lane", value: "/launch/onyx/agent&mode=live", status: "neutral" },
  ];

  return items.filter(Boolean);
}

function renderLiveSessionActions() {
  return `
    <div class="live-session-actions">
      <a class="hero-action-button hero-action-button-secondary" href="/raw/docs/onyx-integration.md">Onyx runtime note</a>
      <a class="hero-action-button hero-action-button-secondary" href="/raw/docs/onyx-integration.md">Onyx Agent runtime note</a>
    </div>
  `;
}

function renderAccessRequirements(payload) {
  if (!liveSessionRoot) {
    return;
  }

  updateLiveRuntimeLink();

  liveSessionRoot.innerHTML = `
    <section class="live-session-banner live-session-banner-neutral">
      <div class="live-session-head">
        <div>
          <p class="eyebrow">Live access</p>
          <h2 class="live-session-title">External identity required</h2>
          <p class="live-session-copy">The dashboard no longer mints dev cookies or browser bootstrap tokens. Use the deployment's OIDC sign-in flow or present a valid Keycloak-backed bearer token before opening the live workspace.</p>
        </div>
        ${renderStatusPill("neutral", { label: "Bring your own auth" })}
      </div>
      ${renderMetaBadges(buildAccessRequirementsMeta(payload), "live-session-meta")}
      <p class="live-session-detail">Live handoffs still fail closed when identity, policy, retrieval, secret, trace, or launch-gate evidence is missing on the same request trace.</p>
      ${renderLiveSessionActions()}
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

const BLOCK_RENDERERS = {
  cards: (block) => renderCards(block.items),
  records: (block) => renderRecords(block.items),
  table: (block) => renderTable(block),
  links: (block) => renderLinks(block.items),
};

function renderBlocks(blocks) {
  return (Array.isArray(blocks) ? blocks : [])
    .map((block) => {
      const renderBlock = BLOCK_RENDERERS[block.type];
      const content = renderBlock ? renderBlock(block) : "";

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

function renderSectionGroupBanner(section, nextGroup) {
  if (!nextGroup) {
    return "";
  }

  return `
    <section class="section-group-banner section-group-${escapeHtml(nextGroup)}" data-group="${escapeHtml(nextGroup)}">
      <p class="eyebrow">${escapeHtml(section.group_label || nextGroup)}</p>
      <h2>${escapeHtml(section.group_label || nextGroup)}</h2>
      <p class="section-description">${
        nextGroup === "reviewer"
          ? "Start here for the plain-language story: current state, blocked actions, proof, and readiness."
          : "Continue here for traces, raw reasons, evidence links, and control detail."
      }</p>
    </section>
  `;
}

function renderSectionShell(section, sectionOpen) {
  return `
    <section class="dashboard-section section-${escapeHtml(section.id || "")}" data-section="${escapeHtml(section.id || "")}" data-group="${escapeHtml(section.group || "")}" id="${escapeHtml(section.id || "")}">
      <details class="dashboard-section-shell" data-section-shell="${escapeHtml(section.id || "")}"${sectionOpen ? " open" : ""}>
        <summary class="dashboard-section-summary">
          <div class="section-summary-copy">
            <div class="section-head">
              <p class="eyebrow">${escapeHtml(humanizeLabel(section.id || section.title || "Section"))}</p>
              <h2>${escapeHtml(section.title || "")}</h2>
              <p class="section-description">${escapeHtml(compactSectionDescription(section))}</p>
            </div>
            ${renderSectionSummaryPills(section)}
          </div>
          <div class="section-summary-aside">
            <span class="section-toggle-hint" data-section-toggle-label>${sectionOpen ? "Hide detail" : "Show detail"}</span>
          </div>
        </summary>
        <div class="section-body">
          ${renderBlocks(section.blocks)}
        </div>
      </details>
    </section>
  `;
}

function renderSections(sections) {
  let activeGroup = "";
  const filteredSections = filteredSectionsForView(sections);
  if (!filteredSections.length) {
    renderSectionsEmptyState();
    return;
  }

  root.innerHTML = filteredSections
    .map((section) => {
      const nextGroup = section.group || "";
      const sectionOpen = isSectionOpen(section);
      const groupBanner = nextGroup !== activeGroup ? renderSectionGroupBanner(section, nextGroup) : "";
      activeGroup = nextGroup;

      return `
        ${groupBanner}
        ${renderSectionShell(section, sectionOpen)}
      `;
    })
    .join("");

  bindSectionDisclosureListeners();
}

function setActiveTab(targetId) {
  if (!tabStrip) {
    return;
  }

  activeTabTarget = targetId || "";
  for (const button of tabStrip.querySelectorAll("button[data-target]")) {
    const isActive = canonicalSectionId(button.dataset.target || "") === canonicalSectionId(activeTabTarget);
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  }
}

function syncActiveTabFromScroll() {
  const sections = Array.from(root.querySelectorAll(".dashboard-section[id]")).filter((section) => section.offsetParent !== null);
  if (!sections.length) {
    return;
  }

  let nextActive = canonicalSectionId(sections[0].id);
  for (const section of sections) {
    const top = section.getBoundingClientRect().top;
    if (top - SECTION_SCROLL_OFFSET_PX <= 0) {
      nextActive = canonicalSectionId(section.id);
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
  const resolvedTargetId = resolvedSectionId(targetId);
  const target = document.getElementById(resolvedTargetId);
  if (!target) {
    return;
  }

  ensureSectionOpen(resolvedTargetId);
  window.requestAnimationFrame(() => {
    const absoluteTop = window.scrollY + target.getBoundingClientRect().top - SECTION_SCROLL_OFFSET_PX;
    window.scrollTo({ top: Math.max(0, absoluteTop), behavior: "smooth" });
  });
  setActiveTab(canonicalSectionId(targetId));
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

function renderTabButton(tab) {
  return `
    <button class="tab-button" type="button" data-target="${escapeHtml(tab.id || "")}" data-tab-group="${escapeHtml(tab.group || "")}" aria-pressed="false">
      ${escapeHtml(tab.label || "")}
    </button>
  `;
}

function renderTabGroup(groupLabel, groupTabs) {
  return `
    <section class="tab-group" data-tab-group="${escapeHtml(groupTabs[0]?.group || "")}">
      <p class="eyebrow">${escapeHtml(groupLabel)}</p>
      <div class="tab-group-row">
        ${groupTabs.map((tab) => renderTabButton(tab)).join("")}
      </div>
    </section>
  `;
}

function renderPrimaryTabRow(primaryTabs) {
  return `
    <div class="tab-group-row tab-primary-row">
      ${primaryTabs.map((tab) => renderTabButton(tab)).join("")}
    </div>
  `;
}

function renderTabDisclosure(groups) {
  return `
    <details class="tab-disclosure">
      <summary>Show all sections</summary>
      <div class="tab-disclosure-body">
        ${Array.from(groups.entries())
          .map(([groupLabel, groupTabs]) => renderTabGroup(groupLabel, groupTabs))
          .join("")}
      </div>
    </details>
  `;
}

function renderTabContent(allTabs, primaryTabs, groups) {
  if (!allTabs.length) {
    return `
      <div class="tab-empty-state">
        <p>No quick-jump sections match the current filter.</p>
      </div>
    `;
  }

  return `
    ${renderPrimaryTabRow(primaryTabs)}
    ${renderTabDisclosure(groups)}
  `;
}

function renderTabs(tabs, freshnessBar = {}) {
  const groups = new Map();
  const allSections = Array.isArray(lastOverviewPayload?.sections) ? lastOverviewPayload.sections : [];
  const allVisibleSections = visibleSectionsForView(allSections);
  const matchingSections = filteredSectionsForView(allSections);
  const allTabs = filteredTabsForView(tabs, allSections);
  for (const tab of allTabs) {
    const groupLabel = tab.group_label || "Sections";
    if (!groups.has(groupLabel)) {
      groups.set(groupLabel, []);
    }
    groups.get(groupLabel).push(tab);
  }

  const preferredPrimaryTabs = (
    isRuntimeView()
      ? allTabs
      : isExecutiveView()
        ? allTabs.filter((tab) => tab.group === "reviewer")
        : allTabs.filter((tab) => tab.group === "reviewer")
  ).slice(0, 6);
  const primaryTabs = preferredPrimaryTabs.length ? preferredPrimaryTabs : allTabs.slice(0, 6);
  const quickJumpTitle = isRuntimeView() ? "Live runtime jump" : "Quick jump";
  const quickJumpDescription = isRuntimeView()
    ? "Use the short row for the current workspace path, handoff proof, and technical runtime checks."
    : "Use the short row for the main story. Open the full list only for deeper drill-down.";
  const viewLabel = DASHBOARD_VIEW_MODES[dashboardViewMode]?.label || "Operator";
  const sectionCountLabel = `${matchingSections.length} of ${allVisibleSections.length || 0} sections`;

  tabStrip.innerHTML = `
    <section class="tab-strip-shell">
      <div class="tab-strip-topline">
        <div class="tab-strip-head">
          <div>
            <p class="eyebrow">${escapeHtml(quickJumpTitle)}</p>
            <p class="section-description">${escapeHtml(quickJumpDescription)}</p>
          </div>
          <div class="tab-strip-meta">
            <span class="chip">View ${escapeHtml(viewLabel)}</span>
            <span class="chip">${escapeHtml(sectionCountLabel)}</span>
          </div>
        </div>
        <div class="tab-strip-utility">
          <label class="section-filter-field" for="dashboard-section-filter">
            <span>Find a section</span>
            <input
              id="dashboard-section-filter"
              class="section-filter-input"
              type="search"
              placeholder="Search sections, proof, trace, launch..."
              value="${escapeHtml(dashboardSectionQuery)}"
            />
          </label>
          ${
            dashboardSectionQuery.trim()
              ? `
                <button class="tab-strip-clear-button" type="button" data-dashboard-filter-clear>
                  Clear filter
                </button>
              `
              : ""
          }
        </div>
      </div>
      ${renderFreshnessStrip(freshnessBar)}
      ${renderTabContent(allTabs, primaryTabs, groups)}
    </section>
  `;

  for (const button of tabStrip.querySelectorAll("button[data-target]")) {
    button.addEventListener("click", () => {
      scrollToSection(button.dataset.target);

      const disclosure = button.closest(".tab-strip-shell")?.querySelector(".tab-disclosure");
      if (disclosure?.open) {
        disclosure.open = false;
      }
    });
  }

  bindDashboardFilterControls(tabStrip);

  bindTabStripScrollListeners();
  const nextActiveTab = allTabs.some((tab) => tab.id === activeTabTarget)
    ? activeTabTarget
    : primaryTabs[0]?.id || allTabs[0]?.id || "";
  setActiveTab(nextActiveTab);
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

function renderLiveLogStatusFilterButtons() {
  return LIVE_LOG_STATUS_FILTERS.map(
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
  ).join("");
}

function renderLiveLogSourceOptions(sources) {
  return sources
    .map(
      (source) => `
        <option value="${escapeHtml(source)}"${liveLogSourceFilter === source ? " selected" : ""}>${escapeHtml(source)}</option>
      `,
    )
    .join("");
}

function renderLiveLogMetaChips(entry) {
  return `
    ${entry.request_id ? `<span class="live-log-meta-chip">request ${escapeHtml(entry.request_id)}</span>` : ""}
    ${entry.trace_id ? `<span class="live-log-meta-chip">trace ${escapeHtml(entry.trace_id)}</span>` : ""}
    ${entry.tenant_id ? `<span class="live-log-meta-chip">tenant ${escapeHtml(entry.tenant_id)}</span>` : ""}
  `;
}

function renderLiveLogEntry(entry) {
  return `
    <article class="live-log-entry">
      <div class="live-log-entry-head">
        <div class="live-log-title-row">
          ${entry.source_label ? `<span class="live-log-meta-chip">${escapeHtml(entry.source_label)}</span>` : ""}
          <span class="${statusClass(entry.status || "neutral")}">${escapeHtml(entry.severity || "info")}</span>
          <h3>${escapeHtml(entry.event_type || "event")}</h3>
        </div>
        <time class="live-log-time">${escapeHtml(formatTimestamp(entry.timestamp))}</time>
      </div>
      <p class="live-log-summary">${escapeHtml(entry.summary || "No event summary available.")}</p>
      <div class="live-log-meta-row">
        ${renderLiveLogMetaChips(entry)}
      </div>
    </article>
  `;
}

function renderLiveLogList(filteredEntries) {
  if (!filteredEntries.length) {
    return `
      <article class="live-log-entry live-log-empty">
        <h3>No matching activity right now</h3>
        <p class="live-log-summary">Adjust the filters to widen the activity view, or wait for the next refresh.</p>
      </article>
    `;
  }

  return filteredEntries.map((entry) => renderLiveLogEntry(entry)).join("");
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
        <span class="${evidenceModeClass(lastDerivedDashboardState?.launchHeader?.evidenceMode || "UNKNOWN")}">Evidence ${escapeHtml(lastDerivedDashboardState?.launchHeader?.evidenceMode || "UNKNOWN")}</span>
      </div>
      <a class="live-log-source"${linkAttributes(payload.source_href || "/api/control-plane/live-log?limit=50")}>
        Open activity feed
      </a>
    </div>
    <div class="live-log-controls">
      <div class="live-log-filter-group" role="toolbar" aria-label="Activity severity filters">
        ${renderLiveLogStatusFilterButtons()}
      </div>
      <label class="live-log-filter-select">
        <span>Source</span>
        <select id="live-log-source-filter">
          <option value="all">All sources</option>
          ${renderLiveLogSourceOptions(sources)}
        </select>
      </label>
    </div>
    <div class="live-log-list">
      ${renderLiveLogList(filteredEntries)}
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

function evidenceModeClass(mode) {
  return `evidence-badge evidence-mode-${String(mode || "UNKNOWN").toLowerCase()}`;
}

function setAudienceMode(mode) {
  activeAudienceMode = AUDIENCE_MODES.some((item) => item.id === mode) ? mode : "executive";
  document.body.setAttribute("data-audience-mode", activeAudienceMode);
  if (audienceModesRoot && lastDerivedDashboardState) {
    renderAudienceModes(lastDerivedDashboardState);
  }
}

function renderAudienceModes(derivedState) {
  if (!audienceModesRoot) {
    return;
  }

  audienceModesRoot.innerHTML = `
    <div class="audience-mode-switch" role="tablist" aria-label="Dashboard audience mode">
      ${AUDIENCE_MODES.map(
        (mode) => `
          <button
            class="audience-mode-button${mode.id === activeAudienceMode ? " is-active" : ""}"
            type="button"
            role="tab"
            aria-selected="${mode.id === activeAudienceMode ? "true" : "false"}"
            data-audience-mode="${escapeHtml(mode.id)}"
          >
            ${escapeHtml(mode.label)}
          </button>
        `,
      ).join("")}
    </div>
    <p class="section-description">Current mode: ${escapeHtml(AUDIENCE_MODES.find((mode) => mode.id === activeAudienceMode)?.label || "Executive View")}.</p>
  `;

  for (const button of audienceModesRoot.querySelectorAll("[data-audience-mode]")) {
    button.addEventListener("click", () => setAudienceMode(button.dataset.audienceMode));
  }
}

function deriveDashboardState(payload) {
  const launchHeader = (decisionModel.deriveLaunchDecisionHeader || (() => ({})))(payload);
  const proofChain = (decisionModel.deriveRagProofChain || (() => []))(payload);
  const liveOnyxProject = (decisionModel.deriveLiveOnyxProject || (() => ({})))(payload, launchHeader);
  const packet = (decisionModel.buildLaunchGatePacket || (() => ({})))(payload);
  const failedRequired = proofChain.filter((item) => item.required && item.status === "FAIL");
  const unknownRequired = proofChain.filter((item) => item.required && item.status === "UNKNOWN");
  return { launchHeader, proofChain, liveOnyxProject, packet, failedRequired, unknownRequired };
}

function renderLaunchDecisionHeader(derivedState) {
  if (!launchDecisionRoot) {
    return;
  }
  const header = derivedState.launchHeader || {};
  const isNoGo = String(header.decision || "").toUpperCase() === "NO-GO";
  launchDecisionRoot.innerHTML = `
    <article class="launch-decision-header ${isNoGo ? "launch-decision-nogo" : ""}">
      <div class="launch-decision-topline">
        <span class="${statusClass(isNoGo ? "critical" : "neutral")}">${escapeHtml(header.decision || "UNKNOWN")}</span>
        <span class="${evidenceModeClass(header.evidenceMode)}">${escapeHtml(header.evidenceMode || "UNKNOWN")}</span>
      </div>
      <ul class="decision-list">
        <li><span>Runtime</span><strong>${escapeHtml(header.runtime || "Unknown")}</strong></li>
        <li><span>Proof backing decision</span><strong>Launch gate + RAG proof chain</strong></li>
        <li><span>Top blocker</span><strong>${escapeHtml(header.topBlocker || "No blocking control currently detected.")}</strong></li>
        <li><span>Required action</span><strong>${escapeHtml(header.requiredAction || "Maintain monitoring and evidence retention.")}</strong></li>
        <li><span>Last proven</span><strong>${escapeHtml(header.lastProvenAt ? formatTimestamp(header.lastProvenAt) : "Not proven yet.")}</strong></li>
      </ul>
      ${
        header.evidenceMode && header.evidenceMode !== "LIVE"
          ? `<p class="section-description">This decision is not based on fully proven live production evidence.</p>`
          : ""
      }
    </article>
  `;
}

function renderRagProofChain(derivedState) {
  if (!ragProofChainRoot) {
    return;
  }
  const items = Array.isArray(derivedState.proofChain) ? derivedState.proofChain : [];
  ragProofChainRoot.innerHTML = `
    <div class="proof-chain-list">
      ${items
        .map(
          (item) => `
            <article class="proof-chain-item status-${escapeHtml((item.status || "UNKNOWN").toLowerCase())}">
              <div class="card-topline">
                <strong>${escapeHtml(item.label || "Control")}</strong>
                <span class="${statusClass(trustControlStatusPresentation(item.status).uiStatus)}">${escapeHtml(item.status || "UNKNOWN")}</span>
              </div>
              <p>${escapeHtml(item.reason || "No reason supplied.")}</p>
              <div class="hero-meta">
                <span class="${evidenceModeClass(item.evidenceMode)}">${escapeHtml(item.evidenceMode || "UNKNOWN")}</span>
                <span class="chip">${item.required ? "Required" : "Optional"}</span>
                ${item.proofHref ? `<a class="chip" href="${escapeHtml(item.proofHref)}">Open proof</a>` : '<span class="chip">No proof link</span>'}
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderLiveOnyxProject(derivedState) {
  if (!liveOnyxProjectRoot) {
    return;
  }
  const project = derivedState.liveOnyxProject || {};
  const runtimeStatusUi = {
    CONNECTED: "healthy",
    PARTIAL: "warning",
    BLOCKED: "critical",
    UNKNOWN: "neutral",
    DEMO: "warning",
    SAMPLE: "warning",
  }[String(project.status || "").toUpperCase()] || "neutral";
  const folderMap = Array.isArray(project.folderMap) && project.folderMap.length
    ? project.folderMap
    : [
        { path: "/onyx", description: "Onyx runtime source" },
        { path: "/trust", description: "Trust control-plane root" },
        { path: "/trust/frontend/main-dashboard", description: "Reviewer dashboard" },
        { path: "/trust/backend/api_gateway", description: "Dashboard/API gateway" },
        { path: "/trust/launch-gate", description: "Launch readiness gate" },
        { path: "/trust/evidence", description: "Readiness evidence artifacts" },
        { path: "/trust/policies", description: "Policy-as-code controls" },
        { path: "/trust/telemetry", description: "Telemetry and audit readiness" },
      ];
  liveOnyxProjectRoot.innerHTML = `
    <article class="decision-panel">
      <div class="card-topline">
        <span class="${statusClass(runtimeStatusUi)}">Runtime status: ${escapeHtml(project.status || "UNKNOWN")}</span>
        <span class="chip">Runtime: ${escapeHtml(project.runtimeName || "Onyx RAG")}</span>
        <span class="${evidenceModeClass(project.evidenceMode)}">${escapeHtml(project.evidenceMode || "UNKNOWN")}</span>
      </div>
      <p>${escapeHtml(project.explanation || "Onyx is the governed RAG runtime. Trust is the control plane around it.")}</p>
      <div class="live-onyx-folder-grid">
        ${folderMap
          .map(
            (entry) => `
              <article class="live-onyx-folder-card">
                <strong><code>${escapeHtml(entry.path || "")}</code></strong>
                <p>${escapeHtml(entry.description || "")}</p>
              </article>
            `,
          )
          .join("")}
      </div>
      <ul class="decision-list">
        <li><span>Root folder relationship</span><strong><code>/onyx</code> and <code>/trust</code> are sibling root-level folders.</strong></li>
        <li><span>API gateway path</span><strong>${escapeHtml(project.apiGatewayPath || "/trust/backend/api_gateway")}</strong></li>
        <li><span>Live runtime proof available</span><strong>${escapeHtml(project.evidenceMode === "LIVE" && project.status === "CONNECTED" ? "Yes" : "No / not proven")}</strong></li>
        <li><span>Last checked</span><strong>${escapeHtml(project.lastCheckedAt ? formatTimestamp(project.lastCheckedAt) : "Not proven yet.")}</strong></li>
      </ul>
      <div class="decision-links">
        <a href="${escapeHtml(project.governedLaunchPath || "/launch/onyx?path=/app&mode=live&view=embedded")}">Open Onyx</a>
        <a href="#launch-gate">View evidence</a>
        <a href="#live-log-title">View live log</a>
        <span class="chip">View dashboard source: <code>${escapeHtml(project.dashboardPath || "/trust/frontend/main-dashboard")}</code></span>
      </div>
      <p class="section-description">Runtime wiring (safe names only): <code>${escapeHtml(project.onyxBaseUrlEnv || "CONTROL_PLANE_ONYX_BASE_URL")}</code>, <code>${escapeHtml(project.onyxApiBaseUrlEnv || "CONTROL_PLANE_ONYX_API_BASE_URL")}</code>, <code>${escapeHtml(project.readinessEndpoint || "/api/security/readiness")}</code>, <code>${escapeHtml(project.overviewEndpoint || "/api/control-plane/overview")}</code>, <code>${escapeHtml(project.liveLogEndpoint || "/api/control-plane/live-log")}</code>, <code>${escapeHtml(project.governedLaunchPath || "/launch/onyx?path=/app&mode=live&view=embedded")}</code></p>
    </article>
  `;
}

function renderWhyNotGoPanel(derivedState) {
  if (!whyNotGoRoot) {
    return;
  }
  const failed = derivedState.failedRequired || [];
  const unknown = derivedState.unknownRequired || [];
  const launchHeader = derivedState.launchHeader || {};
  whyNotGoRoot.innerHTML = `
    <article class="decision-panel">
      <h3>RAG launch remains blocked when required proof is missing.</h3>
      <p>${escapeHtml(launchHeader.topBlocker || "No blocking control currently detected.")}</p>
      <ul class="decision-list">
        <li><span>Failed required controls</span><strong>${escapeHtml(failed.map((item) => item.label).join(", ") || "None")}</strong></li>
        <li><span>Unknown required controls</span><strong>${escapeHtml(unknown.map((item) => item.label).join(", ") || "None")}</strong></li>
        <li><span>Required evidence to clear gate</span><strong>Current identity, policy, retrieval/source-boundary, secrets, telemetry, and launch-gate proof.</strong></li>
      </ul>
      <div class="decision-links">
        <a href="#launch-gate">Open launch-gate evidence</a>
        <a href="/raw/docs/strict-live-proof-matrix.md">Proof matrix</a>
      </div>
      <p class="section-description">Fail-closed behavior: if evidence is missing, stale, ambiguous, or non-live, production approval is withheld.</p>
    </article>
  `;
}

function downloadLaunchGatePacket(packet) {
  const timestamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "").replace("T", "-");
  const filename = `onyx-rag-launch-gate-packet-${timestamp}.json`;
  const blob = new Blob([JSON.stringify(packet, null, 2)], { type: "application/json" });
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(href);
}

function renderLaunchGatePacketPanel(derivedState) {
  if (!launchGatePacketRoot) {
    return;
  }
  const packet = derivedState.packet || {};
  launchGatePacketRoot.innerHTML = `
    <article class="decision-panel">
      <p>Export an evidence-backed bundle for review, audit, and launch-governance sign-off.</p>
      <div class="hero-meta">
        <span class="${statusClass(packet.decision === "NO-GO" ? "critical" : "neutral")}">${escapeHtml(packet.decision || "UNKNOWN")}</span>
        <span class="${evidenceModeClass(packet.evidenceMode)}">${escapeHtml(packet.evidenceMode || "UNKNOWN")}</span>
      </div>
      <button class="hero-action-button" id="download-launch-gate-packet" type="button">Download Launch Gate Packet</button>
    </article>
  `;
  const button = launchGatePacketRoot.querySelector("#download-launch-gate-packet");
  if (button) {
    button.addEventListener("click", () => downloadLaunchGatePacket(packet));
  }
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

function renderDashboardPayload(payload) {
  const derivedState = deriveDashboardState(payload);
  lastDerivedDashboardState = derivedState;
  renderDecisionHero(payload);
  renderLaunchDecisionHeader(derivedState);
  renderAudienceModes(derivedState);
  renderLiveOnyxProject(derivedState);
  renderRagProofChain(derivedState);
  renderWhyNotGoPanel(derivedState);
  renderLaunchGatePacketPanel(derivedState);
  renderRuntimePortfolio(payload);
  renderHomepagePanels(payload);
  renderTrustScorecard(payload);
  renderSecondaryContext(payload);
  renderSections((Array.isArray(payload.sections) ? payload.sections : []).filter((section) => ACTIVE_DRILLDOWN_SECTION_IDS.has(canonicalSectionId(section?.id))));
  renderDrilldownTabs(payload.tabs);
  renderSources(payload.sources);
  applyChangeHighlights();
}

function normalizeRuntimeCard(item = {}, fallback = {}) {
  const launchHref = item.launch_href || item.launch_route || item.workspace_href || fallback.launch_href || "";
  const evidenceHref = item.evidence_href || fallback.evidence_href || "#audit-replay";
  const controls = Array.isArray(item.primary_controls) ? item.primary_controls : (fallback.primary_controls || []);
  return {
    name: item.name || item.label || fallback.name || "Runtime",
    runtimeKey: item.runtime_key || item.id || fallback.runtime_key || "runtime",
    runtimeClass: item.runtime_class || item.type || fallback.runtime_class || "Governed runtime",
    description: item.description || item.summary || fallback.description || "Governed runtime lane.",
    status: item.status || fallback.status || "neutral",
    launchHref,
    evidenceHref,
    primaryControls: controls,
  };
}

function defaultRuntimePortfolio() {
  return [
    {
      name: "Onyx",
      runtime_key: "onyx",
      runtime_class: "RAG",
      description: "Retrieval-grounded runtime lane with data boundary governance.",
      status: "neutral",
      launch_href: "/launch/onyx?path=/app&mode=live&view=embedded",
      evidence_href: "#retrieval-boundaries",
      primary_controls: ["Retrieval boundaries", "Tenant/source policy", "Data-path governance"],
    },
  ];
}

function renderRuntimePortfolio(payload) {
  if (!runtimePortfolioRoot) {
    return;
  }

  const portfolio = payload.runtime_portfolio || {};
  const runtimeItems = Array.isArray(portfolio.runtimes) && portfolio.runtimes.length
    ? portfolio.runtimes
    : defaultRuntimePortfolio();

  const cards = runtimeItems
    .filter((item) => String(item?.runtime_key || item?.id || "").toLowerCase() === "onyx")
    .map((item) => normalizeRuntimeCard(item));
  runtimePortfolioRoot.innerHTML = `
    <div class="decision-panels-root">
      ${cards
        .map(
          (card) => `
            <article class="decision-panel runtime-lane-card">
              <p class="eyebrow">${escapeHtml(card.runtimeClass)} · Current RAG launch scope</p>
              <h3>${escapeHtml(card.name)}</h3>
              <p>${escapeHtml(card.description)}</p>
              ${renderStatusPill(card.status, { label: statusLabel(card.status) })}
              <ul class="decision-list">
                <li><span>Runtime key</span><strong>${escapeHtml(card.runtimeKey)}</strong></li>
                <li><span>Primary controls</span><strong>${escapeHtml(card.primaryControls.join(", ") || "Not listed")}</strong></li>
              </ul>
              <div class="decision-links">
                ${card.launchHref ? `<a href="${escapeHtml(card.launchHref)}">Open ${escapeHtml(card.name)}</a>` : "<span>Launch route unavailable</span>"}
                ${card.evidenceHref ? `<a href="${escapeHtml(card.evidenceHref)}">View evidence</a>` : "<span>Evidence unavailable</span>"}
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
    <p class="section-description">Deferred scope: autonomous-agent governance, MCP hardening, tool authorization, and agent identity controls are future expansion and not part of current RAG launch approval.</p>
  `;
}

function renderSecondaryContext(payload) {
  if (!secondaryContextRoot) {
    return;
  }

  const sources = Array.isArray(payload.sources) ? payload.sources : [];
  const sourceById = (id) => sources.find((item) => item?.id === id);

  const contextLinks = [
    { label: "Client Overview", href: "/client-overview", detail: "Non-technical explanation layer." },
    { label: "Connected systems inventory", href: "/api/control-plane/upstream-usage", detail: "Machine-readable upstream posture inventory." },
    {
      label: sourceById("dashboard_ingestion_feed")?.label || "Dashboard ingestion feed",
      href: sourceById("dashboard_ingestion_feed")?.href || "",
      detail: sourceById("dashboard_ingestion_feed")?.description || "Supporting export feed.",
    },
    {
      label: sourceById("governed_event_feed")?.label || "Governed event feed",
      href: sourceById("governed_event_feed")?.href || "",
      detail: sourceById("governed_event_feed")?.description || "Underlying event stream.",
    },
  ];

  secondaryContextRoot.innerHTML = `
    <div class="decision-links secondary-context-links">
      ${contextLinks
        .map((item) => {
          if (!item.href) {
            return `<span>${escapeHtml(item.label)} — ${escapeHtml(item.detail)}</span>`;
          }
          return `<a href="${escapeHtml(item.href)}">${escapeHtml(item.label)}</a><span class="secondary-context-note">${escapeHtml(item.detail)}</span>`;
        })
        .join("")}
    </div>
  `;
}

function latestCheckedLabelFromBadges(metaBadges = []) {
  const checkedBadge = (Array.isArray(metaBadges) ? metaBadges : []).find((badge) => badge?.kind === "timestamp");
  return checkedBadge?.value ? formatTimestamp(checkedBadge.value) : "Unavailable";
}

function renderTrustScorecard(payload) {
  if (!trustScorecardRoot) {
    return;
  }

  const trustProof = payload.trust_proof || {};
  const legacyIdentity = Boolean(trustProof.identity_proven);
  const readiness = payload.readiness || {};
  const commandCenter = payload.command_center || {};
  const proofPipeline = commandCenter.proof_pipeline || {};
  const pipelineSteps = Array.isArray(proofPipeline.steps) ? proofPipeline.steps : [];
  const evidenceLinks = Array.isArray(payload.sources) ? payload.sources : [];

  const findStep = (label) => pipelineSteps.find((step) => String(step?.label || "").toLowerCase().includes(label));
  const findSource = (id) => evidenceLinks.find((item) => item?.id === id);

  const launchReport = findSource("launch_report");
  const governedFlow = findSource("governed_flow_summary");
  const trustControlRows = Array.isArray(trustProof.controls) ? trustProof.controls : [];
  const rows = trustControlRows.length
    ? trustControlRows.map((row) => ({
        control: row.control || "Control",
        status: String(row.status || "NEEDS_ATTENTION").toUpperCase(),
        evidenceMode: String(row.evidence_mode || readiness.evidence_mode || "unknown").toUpperCase(),
        lastChecked: formatTimestamp(row.last_checked || ""),
        proofLabel: row.control || "Evidence",
        proofHref: row.proof_href || "",
        blocker: row.reason || "",
      }))
    : [
        {
          control: "Identity",
          status: legacyIdentity ? "PASS" : "MISSING_PROOF",
          evidenceMode: String(readiness.evidence_mode || "unknown").toUpperCase(),
          lastChecked: latestCheckedLabelFromBadges(findStep("identity")?.meta_badges || []),
          proofLabel: findStep("identity")?.label || "Identity step",
          proofHref: findStep("identity")?.href || "",
          blocker: legacyIdentity ? "" : "Identity proof is missing or incomplete.",
        },
      ];
  rows.push({
    control: "Launch Gate",
    status: String(readiness.decision || "").toUpperCase() === "GO" ? "PASS" : "FAIL",
    evidenceMode: String(readiness.evidence_mode || "unknown").toUpperCase(),
    lastChecked: formatTimestamp(readiness.last_updated),
    proofLabel: launchReport?.label || governedFlow?.label || "Launch evidence",
    proofHref: launchReport?.href || governedFlow?.href || "#launch-gate",
    blocker: String(readiness.decision || "").toUpperCase() === "GO" ? "" : (readiness.top_blocker || "Launch gate has unresolved blockers."),
  });
  const normalizedRows = rows.map((row) => ({ ...row, statusPresentation: trustControlStatusPresentation(row.status) }));

  trustScorecardRoot.innerHTML = `
    <div class="trust-scorecard-wrap">
      <table class="trust-scorecard-table">
        <thead>
          <tr>
            <th>Control</th>
            <th>Status</th>
            <th>Evidence mode</th>
            <th>Last checked</th>
            <th>Proof</th>
            <th>Blocker / reason</th>
          </tr>
        </thead>
        <tbody>
          ${normalizedRows
            .map(
              (row) => `
                <tr>
                  <td>${escapeHtml(row.control)}</td>
                  <td><span class="${statusClass(row.statusPresentation.uiStatus)}">${escapeHtml(row.statusPresentation.label)}</span></td>
                  <td><span class="${evidenceModeClass(row.evidenceMode)}">${escapeHtml(row.evidenceMode || "UNKNOWN")}</span></td>
                  <td>${escapeHtml(row.lastChecked || "Unavailable")}</td>
                  <td>${
                    row.proofHref
                      ? `<a href="${escapeHtml(row.proofHref)}">${escapeHtml(row.proofLabel || "Evidence")}</a>`
                      : `<span>${escapeHtml(row.proofLabel || "Unavailable")}</span>`
                  }</td>
                  <td>${escapeHtml(row.blocker || "None")}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderDecisionHero(payload) {
  if (heroEyebrow) {
    heroEyebrow.textContent = "Start here";
  }
  if (heroTitle) {
    heroTitle.textContent = "Trust Readiness Dashboard for the Onyx RAG Project";
  }
  if (heroCopy) {
    heroCopy.textContent = "Onyx is the governed RAG runtime. Trust is the security, policy, evidence, telemetry, and launch-readiness layer around it.";
  }

  const readiness = payload.readiness || {};
  const topBlocker = readiness.top_blocker || "No blocker listed.";
  const evidenceMode = readiness.evidence_mode || "unavailable";
  const score = readiness.readiness_score ?? "n/a";
  const decision = readiness.decision || "UNKNOWN";
  const topBlockers = Array.isArray(readiness.top_blockers) ? readiness.top_blockers.slice(0, 5) : [];
  const freshnessSla = payload.trust_proof?.freshness_sla || {};

  if (heroMeta) {
    heroMeta.innerHTML = `
      <span class="${statusClass(payload.data_mode?.status || "neutral")}">${escapeHtml(decision)}</span>
      <span class="chip">Score ${escapeHtml(String(score))}</span>
      <span class="chip">Main issue: ${escapeHtml(topBlocker)}</span>
      <span class="chip">Proof source: ${escapeHtml(String(evidenceMode).toUpperCase())}</span>
      ${
        Number.isFinite(Number(freshnessSla.fresh_hours))
          ? `<span class="chip">Freshness SLA: fresh ≤${escapeHtml(String(freshnessSla.fresh_hours))}h · stale >${escapeHtml(
              String(freshnessSla.stale_after_hours ?? freshnessSla.fresh_hours),
            )}h · expired >${escapeHtml(String(freshnessSla.expired_after_hours ?? "n/a"))}h</span>`
          : ""
      }
      ${
        topBlockers.length
          ? `<div class="hero-blocker-panel">
              <strong>What's blocking launch?</strong>
              <ul>
                ${topBlockers
                  .slice(0, 5)
                  .map(
                    (item) =>
                      `<li><a href="${escapeHtml(item.href || "#launch-gate")}">${escapeHtml(item.label || "Unresolved blocker")}</a></li>`,
                  )
                  .join("")}
              </ul>
            </div>`
          : ""
      }
    `;
  }

  const runtimeItems = Array.isArray(payload.runtime_portfolio?.runtimes) ? payload.runtime_portfolio.runtimes : [];
  const runtimeByKey = new Map(runtimeItems.map((item) => [String(item?.runtime_key || item?.id || "").toLowerCase(), item]));
  const onyxChatLaunchHref = String(
    runtimeByKey.get("onyx")?.launch_href || runtimeByKey.get("onyx")?.launch_route || "/launch/onyx?path=/app&mode=live&view=embedded",
  );
  const onyxAgentLaunchHref = String(
    runtimeByKey.get("onyx")?.agent_launch_href || "/launch/onyx/agent?mode=live&view=embedded",
  );

  if (liveRuntimeLink) {
    liveRuntimeLink.textContent = "Open Onyx";
    liveRuntimeLink.setAttribute("href", onyxChatLaunchHref);
  }
  if (liveOnyxAgentLink) {
    liveOnyxAgentLink.textContent = "Onyx Agent (future scope)";
    liveOnyxAgentLink.setAttribute("href", onyxAgentLaunchHref);
  }
  if (viewEvidenceLink) {
    viewEvidenceLink.setAttribute("href", "#dashboard-root");
  }
  if (runtimeLanesMeta) {
    runtimeLanesMeta.innerHTML = runtimeItems
      .filter((item) => String(item?.runtime_key || "").toLowerCase() === "onyx")
      .map(
        (item) =>
          `<span class="chip">${escapeHtml(item.label || "Runtime")} = ${escapeHtml(item.type || "Lane")} · ${escapeHtml(
            item.governance_focus || "",
          )}</span>`,
      )
      .join("");
    const onyxRuntime = runtimeByKey.get("onyx");
    if (onyxRuntime) {
      runtimeLanesMeta.innerHTML += `<span class="chip">Onyx service health: ${escapeHtml(String(onyxRuntime.status || "unknown").toUpperCase())}</span>`;
    }
    runtimeLanesMeta.innerHTML += '<span class="chip">Deferred: autonomous-agent, MCP, and tool-authorization controls are not in current RAG launch scope.</span>';
  }
}

function renderHomepagePanels(payload) {
  const panelRoot = document.getElementById("homepage-panels-root");
  if (!panelRoot) {
    return;
  }

  const readiness = payload.readiness || {};
  const trust = payload.trust_proof || {};
  const security = payload.security_posture || {};
  const scoreBasis = readiness.score_basis || {};
  const launchGateScore = scoreBasis.launch_gate_score ?? "n/a";
  const hardenedScore = readiness.readiness_score ?? "n/a";
  const runtimeByKey = new Map((payload.runtime_portfolio?.runtimes || []).map((item) => [String(item?.runtime_key || "").toLowerCase(), item]));
  const onyxRuntime = runtimeByKey.get("onyx") || {};
  const fallbackFailingControls = Array.isArray(security.failing_controls) && security.failing_controls.length
    ? security.failing_controls
    : [{ control: "none", summary: "No failing controls listed." }];

  const trustRow = (label, value) => `
    <li><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></li>
  `;

  panelRoot.innerHTML = `
    <article class="decision-panel">
      <p class="eyebrow">Panel A</p>
      <h3>Can we launch now?</h3>
      <ul class="decision-list">
        <li><span>Decision</span><strong>${escapeHtml(readiness.decision || "UNKNOWN")}</strong></li>
        <li><span>Launch-gate score (hard gate)</span><strong>${escapeHtml(String(launchGateScore))}</strong></li>
        <li><span>Advisory readiness score</span><strong>${escapeHtml(String(hardenedScore))}</strong></li>
        <li><span>Latest handoff</span><strong>${escapeHtml(readiness.latest_handoff_decision || "UNKNOWN")}</strong></li>
        <li><span>Proof source</span><strong>${escapeHtml(String(readiness.evidence_mode || "unavailable").toUpperCase())}</strong></li>
        <li><span>Main issue</span><strong>${escapeHtml(readiness.top_blocker || "No blocker listed.")}</strong></li>
        <li><span>Onyx continuity</span><strong>${escapeHtml(String(onyxRuntime.status || "unknown").toUpperCase())}</strong></li>
        <li><span>Last updated</span><strong>${escapeHtml(formatTimestamp(readiness.last_updated))}</strong></li>
      </ul>
      ${
        Array.isArray(readiness.top_blockers) && readiness.top_blockers.length
          ? `<div class="decision-failing-controls"><p class="metric-label">What's blocking launch?</p><ul>${readiness.top_blockers
              .slice(0, 5)
              .map((item) => `<li><strong>${escapeHtml(item.label || "Blocker")}</strong>: ${escapeHtml(item.detail || "")}</li>`)
              .join("")}</ul></div>`
          : ""
      }
    </article>
    <article class="decision-panel">
      <p class="eyebrow">Panel B</p>
      <h3>Safety checks</h3>
      <ul class="decision-list">
        ${trustRow("Identity", trust.identity_proven ? "Proven" : "Missing")}
        ${trustRow("Policy", trust.policy_proven ? "Proven" : "Missing")}
        ${trustRow("Retrieval", trust.retrieval_proven ? "Proven" : "Missing")}
        ${trustRow("Source boundary", trust.retrieval_proven ? "Proven" : "Missing")}
        ${trustRow("Audit", trust.audit_proven ? "Proven" : "Missing")}
        ${trustRow("Evidence freshness", trust.evidence_freshness || "Unavailable")}
      </ul>
      <div class="decision-links">
        ${trust.governed_flow_summary_available ? '<a href="#entry-points">Runtime handoff summary</a>' : '<span>Runtime handoff summary unavailable</span>'}
        ${trust.launch_report_available ? '<a href="#launch-gate">Launch report</a>' : '<span>Launch report unavailable</span>'}
        ${trust.reviewer_bundle_available ? '<a href="#audit-replay">Reviewer bundle</a>' : '<span>Reviewer bundle unavailable</span>'}
      </div>
    </article>
    <article class="decision-panel">
      <p class="eyebrow">Panel C</p>
      <h3>Security snapshot</h3>
      <ul class="decision-list">
        <li><span>Blocked actions</span><strong>${escapeHtml(String(security.blocked_actions_count ?? 0))}</strong></li>
        <li><span>Denied events</span><strong>${escapeHtml(String(security.denied_events_count ?? 0))}</strong></li>
        <li><span>Confirmation required</span><strong>${escapeHtml(String(security.confirmation_required_count ?? 0))}</strong></li>
        <li><span>Retrieval denials</span><strong>${escapeHtml(String(security.retrieval_denials_count ?? 0))}</strong></li>
        <li><span>Tool denials</span><strong>${escapeHtml(String(security.tool_denials_count ?? 0))}</strong></li>
        <li><span>Residual risks</span><strong>${escapeHtml(String(security.residual_risk_count ?? 0))}</strong></li>
      </ul>
      <div class="decision-failing-controls">
        <p class="metric-label">Top failing controls</p>
        <ul>
          ${fallbackFailingControls
            .map((item) => `<li><strong>${escapeHtml(item.control || "control")}</strong>: ${escapeHtml(item.summary || "No summary.")}</li>`)
            .join("")}
        </ul>
      </div>
    </article>
  `;
}

function renderDrilldownTabs(tabs) {
  if (!tabStrip) {
    return;
  }
  const filteredTabs = (Array.isArray(tabs) ? tabs : []).filter((tab) => ACTIVE_DRILLDOWN_SECTION_IDS.has(SECTION_ID_ALIASES[tab?.id] || tab?.id));
  tabStrip.innerHTML = `
    <section class="tab-strip-shell compact-drilldown-nav">
      <div class="tab-strip-head">
        <p class="eyebrow">Drill-down evidence</p>
        <p class="section-description">Technical detail for audit and control verification.</p>
      </div>
      <div class="tab-group-row tab-primary-row">
        ${filteredTabs
          .map(
            (tab) => `
              <button class="tab-button" type="button" data-target="${escapeHtml(tab.id || "")}" aria-pressed="false">
                ${escapeHtml(tab.label || tab.id || "")}
              </button>
            `,
          )
          .join("")}
      </div>
    </section>
  `;

  for (const button of tabStrip.querySelectorAll("button[data-target]")) {
    button.addEventListener("click", () => scrollToSection(button.dataset.target));
  }
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
    if (heroMeta) {
      heroMeta.innerHTML = "";
    }
    if (trustScorecardRoot) {
      trustScorecardRoot.innerHTML = "";
    }
    if (secondaryContextRoot) {
      secondaryContextRoot.innerHTML = "";
    }
    if (sourcesRoot) {
      sourcesRoot.innerHTML = "";
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

setAudienceMode("executive");
boot();
loadLiveLog();
