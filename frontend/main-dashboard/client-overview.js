const heroTitle = document.getElementById("client-hero-title");
const heroCopy = document.getElementById("client-hero-copy");
const heroMeta = document.getElementById("client-hero-meta");
const trafficSummaryRoot = document.getElementById("traffic-summary-root");
const processRoot = document.getElementById("process-root");
const comparisonRoot = document.getElementById("comparison-root");
const examplesRoot = document.getElementById("examples-root");
const readinessRoot = document.getElementById("readiness-root");
const linksRoot = document.getElementById("links-root");

function escapeHtml(value) {
  return String(value ?? "")
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
    healthy: "Working well",
    warning: "Needs attention",
    critical: "Serious issue",
    neutral: "For context",
  }[status || "neutral"] || "For context";
}

function clientReadinessLabel(value) {
  return {
    GO: "Ready",
    CONDITIONAL: "Partly ready",
    "NO-GO": "Not ready",
  }[String(value || "").toUpperCase()] || "Unknown";
}

function formatTimestamp(value) {
  if (!value) {
    return "Time unavailable";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleString();
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Request failed for ${url}: ${response.status}`);
  }
  return response.json();
}

function findCommandCard(payload, label) {
  const cards = payload.command_center?.cards || [];
  return cards.find((item) => item.display_label === label || item.label === label) || null;
}

function findSource(payload, label) {
  return (payload.sources || []).find((item) => item.label === label) || null;
}

function familyStatus(payload, keyword) {
  const families = payload.readiness_panel?.control_families || [];
  return families.find((item) => String(item.family || "").toLowerCase().includes(keyword)) || null;
}

function renderHero(payload) {
  const readiness = payload.readiness_panel || {};
  const mode = payload.mode_banner || {};
  const latestRequest = payload.command_center?.latest_request || {};

  if (heroTitle) {
    heroTitle.textContent = "What this AI safety layer does";
  }

  if (heroCopy) {
    heroCopy.textContent =
      "It checks who is using the AI, what rules apply, what information and actions are allowed, and whether enough proof exists to safely allow access.";
  }

  if (heroMeta) {
    heroMeta.innerHTML = `
      <span class="meta-chip">${escapeHtml(mode.display_label || mode.label || "Mode unavailable")}</span>
      <span class="${statusClass(readiness.status || "neutral")}">${escapeHtml(clientReadinessLabel(readiness.status_label || ""))}</span>
      <span class="meta-chip">Latest checked request: ${escapeHtml(formatTimestamp(latestRequest.display_fields?.find((field) => field.label === "Time")?.value || latestRequest.fields?.find((field) => field.label === "Timestamp")?.value || payload.generated_at))}</span>
    `;
  }
}

function renderTrafficSummary(payload) {
  const readiness = payload.readiness_panel || {};
  const evidenceCard = findCommandCard(payload, "How up to date the proof is");
  const latestDecision = findCommandCard(payload, "Latest access decision");
  const families = readiness.control_families || [];
  const healthyCount = families.filter((item) => item.status === "healthy").length;
  const failingCount = families.filter((item) => item.status === "critical").length;
  const riskCount = (readiness.residual_risks || []).length;

  const items = [
    {
      title: "System protections",
      value: `${healthyCount}/${families.length || 0} main checks working`,
      detail: "Shows whether the main identity, rules, information, key, and process checks are behaving as expected.",
      status: failingCount > 1 ? "critical" : failingCount === 1 ? "warning" : "healthy",
    },
    {
      title: "Risks still open",
      value: `${riskCount} risk${riskCount === 1 ? "" : "s"} still visible`,
      detail: "Shows whether important issues still need work before the system should be presented as ready.",
      status: readiness.status || "neutral",
    },
    {
      title: "Proof available",
      value: evidenceCard?.display_value || evidenceCard?.value || "Proof status unavailable",
      detail: "Shows whether current review proof exists and how fresh it is.",
      status: evidenceCard?.status || "neutral",
    },
    {
      title: "Safe to use now?",
      value: clientReadinessLabel(readiness.status_label || ""),
      detail: latestDecision?.display_detail || "Shows the current decision about whether the system should be used now.",
      status: readiness.status || "neutral",
    },
  ];

  trafficSummaryRoot.innerHTML = items
    .map(
      (item) => `
        <article class="traffic-card traffic-${escapeHtml(item.status || "neutral")}">
          <div class="traffic-light" aria-hidden="true"></div>
          <div class="card-topline">
            <h3>${escapeHtml(item.title)}</h3>
            <span class="${statusClass(item.status || "neutral")}">${escapeHtml(statusLabel(item.status || "neutral"))}</span>
          </div>
          <strong class="traffic-value">${escapeHtml(item.value)}</strong>
          <p>${escapeHtml(item.detail)}</p>
        </article>
      `,
    )
    .join("");
}

function renderProcess(payload) {
  const latestDecision = findCommandCard(payload, "Latest access decision");
  const steps = [
    {
      title: "User asks a question",
      detail: "A person tries to reach the AI system.",
      status: "neutral",
    },
    {
      title: "Check who they are",
      detail: "Confirms identity and tenant access before moving forward.",
      status: familyStatus(payload, "identity")?.status || "neutral",
    },
    {
      title: "Check the rules",
      detail: "Applies the current policy rules to the request.",
      status: familyStatus(payload, "policy")?.status || "neutral",
    },
    {
      title: "Check allowed information",
      detail: "Confirms whether the AI can read the requested information source.",
      status: familyStatus(payload, "retrieval")?.status || "neutral",
    },
    {
      title: "Check allowed actions and keys",
      detail: "Confirms protected actions and secrets are handled safely.",
      status: familyStatus(payload, "secret")?.status || "neutral",
    },
    {
      title: "Save proof",
      detail: "Records trace and evidence so the decision can be reviewed later.",
      status: familyStatus(payload, "trace")?.status || "neutral",
    },
    {
      title: "Allow or block",
      detail: latestDecision?.display_value
        ? `Current latest decision: ${latestDecision.display_value}.`
        : "The system either allows access or blocks it.",
      status: latestDecision?.status || payload.readiness_panel?.status || "neutral",
    },
  ];

  processRoot.innerHTML = `
    <div class="process-grid">
      ${steps
        .map(
          (step, index) => `
            <article class="process-step">
              <div class="process-index">${index + 1}</div>
              <div class="${statusClass(step.status || "neutral")}">${escapeHtml(statusLabel(step.status || "neutral"))}</div>
              <h3>${escapeHtml(step.title)}</h3>
              <p>${escapeHtml(step.detail)}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderComparison(payload) {
  const mode = payload.mode_banner || {};
  comparisonRoot.innerHTML = `
    <div class="comparison-grid">
      <article class="comparison-card warning-card">
        <p class="eyebrow">Without the control plane</p>
        <h3>The AI is reached more directly</h3>
        <ul class="comparison-list">
          <li>Fewer visible checks happen before the AI responds.</li>
          <li>It is harder to explain why access should have been allowed.</li>
          <li>There is less review proof if something goes wrong.</li>
        </ul>
      </article>
      <article class="comparison-card healthy-card">
        <p class="eyebrow">With the control plane</p>
        <h3>The AI must pass safety checks first</h3>
        <ul class="comparison-list">
          <li>Identity, rules, data access, actions, and proof checks happen before access is allowed.</li>
          <li>Unsafe or unsupported requests can be blocked instead of passed through.</li>
          <li>The decision is backed by saved proof, not just an assertion.</li>
        </ul>
        <p class="comparison-note">${escapeHtml(mode.display_summary || mode.summary || "")}</p>
      </article>
    </div>
  `;
}

function proofList(items) {
  if (!Array.isArray(items) || !items.length) {
    return "<li>Proof links unavailable.</li>";
  }
  return items
    .slice(0, 3)
    .map((item) => `<li>${escapeHtml(String(item).split("/").slice(-1)[0])}</li>`)
    .join("");
}

function renderExamples(payload, allowedFlow, deniedFlow) {
  const flagship = payload.command_center?.flagship_proof || {};
  const allowedChecks = [
    allowedFlow?.artifact_snapshots?.identity_evidence?.authenticated ? "Identity was confirmed." : "",
    allowedFlow?.artifact_snapshots?.policy_evidence?.allow ? "Rules allowed the request." : "",
    allowedFlow?.artifact_snapshots?.retrieval_evidence?.allow ? "Information access stayed within the allowed boundary." : "",
    allowedFlow?.artifact_snapshots?.trace_correlation?.complete ? "The full process was recorded under one trace." : "",
    allowedFlow?.artifact_snapshots?.launch_gate_result?.decision === "pass" ? "The final safety check passed." : "",
  ].filter(Boolean);

  const blockedReason = deniedFlow?.summary
    || flagship.display_detail
    || "The blocked example shows the system refusing access when the rules or proof do not support the handoff.";

  examplesRoot.innerHTML = `
    <div class="example-grid">
      <article class="example-card">
        <div class="card-topline">
          <p class="eyebrow">Allowed example</p>
          <span class="${statusClass("healthy")}">Allowed</span>
        </div>
        <h3>Request passed the checks</h3>
        <p>${escapeHtml(allowedFlow?.summary || "A governed request passed identity, rules, information, and proof checks, so access was allowed.")}</p>
        <div class="example-detail">
          <strong>Why it was allowed</strong>
          <ul class="example-list">
            ${allowedChecks.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>Technical allow summary available in the proof artifact.</li>"}
          </ul>
        </div>
        <div class="example-detail">
          <strong>Proof saved</strong>
          <ul class="example-list">
            ${proofList(allowedFlow?.artifacts)}
          </ul>
        </div>
        <a class="link-button" href="/raw/evidence/reviewer/inspectable-live-runtime/allowed-flow.json">Open technical allow proof</a>
      </article>
      <article class="example-card blocked-card">
        <div class="card-topline">
          <p class="eyebrow">Blocked example</p>
          <span class="${statusClass("critical")}">Blocked</span>
        </div>
        <h3>Request was stopped before AI access</h3>
        <p>${escapeHtml(blockedReason)}</p>
        <div class="example-detail">
          <strong>Why it was blocked</strong>
          <ul class="example-list">
            <li>The system saw a request that should not continue as-is.</li>
            <li>It refused the handoff instead of passing the problem downstream.</li>
            <li>The exact technical reason remains available in the deeper proof layer.</li>
          </ul>
        </div>
        <div class="example-detail">
          <strong>Proof saved</strong>
          <ul class="example-list">
            ${proofList(deniedFlow?.artifacts)}
          </ul>
        </div>
        <a class="link-button" href="/raw/evidence/reviewer/inspectable-live-runtime/denied-flow.json">Open technical blocked proof</a>
      </article>
    </div>
  `;
}

function renderReadiness(payload) {
  const readiness = payload.readiness_panel || {};
  const score = Number.parseInt(readiness.score || "0", 10) || 0;
  const topIssue = readiness.top_failing_controls?.[0]?.title || "No major issue recorded";
  const label = clientReadinessLabel(readiness.status_label || "");
  const gaugeColor = readiness.status === "healthy" ? "#0f6c5e" : readiness.status === "warning" ? "#ad5d16" : "#9d2d2d";

  readinessRoot.innerHTML = `
    <div class="readiness-grid">
      <article class="gauge-card">
        <div class="gauge" style="--gauge-value: ${Math.max(0, Math.min(score, 100))}; --gauge-color: ${escapeHtml(gaugeColor)};">
          <div class="gauge-center">
            <strong>${escapeHtml(String(score))}</strong>
            <span>/100</span>
          </div>
        </div>
        <div class="gauge-copy">
          <p class="eyebrow">Current readiness</p>
          <h3>${escapeHtml(label)}</h3>
          <p>${escapeHtml(readiness.coverage || "Coverage unavailable")} important checks currently pass.</p>
        </div>
      </article>
      <article class="readiness-card">
        <div class="card-topline">
          <h3>What this means right now</h3>
          <span class="${statusClass(readiness.status || "neutral")}">${escapeHtml(statusLabel(readiness.status || "neutral"))}</span>
        </div>
        <p>${escapeHtml(readiness.summary || "Readiness summary unavailable.")}</p>
        <div class="readiness-points">
          <article>
            <strong>Top issue</strong>
            <p>${escapeHtml(topIssue)}</p>
          </article>
          <article>
            <strong>Latest report</strong>
            <p>${escapeHtml(formatTimestamp(readiness.generated_at))}</p>
          </article>
        </div>
        <a class="link-button" href="/#launch-gate">Open technical safety section</a>
      </article>
    </div>
  `;
}

function renderLinks(payload) {
  const reviewerBundle = findSource(payload, "Reviewer evidence bundle");
  const launchReport = findSource(payload, "Launch report");
  const eventFeed = findSource(payload, "Governed event feed");

  const links = [
    {
      label: "Technical dashboard",
      description: "Open the full trust and security dashboard with reviewer and operator detail.",
      href: "/",
      status: "healthy",
    },
    {
      label: "Reviewer fast path",
      description: "Open the shortest proof path through pass, deny, and launch readiness.",
      href: "/raw/docs/reviewer-fast-path.md",
      status: "neutral",
    },
    {
      label: "Proof bundle",
      description: "Open the bundled reviewer evidence pack behind this project.",
      href: reviewerBundle?.href || "/raw/evidence/reviewer_evidence_bundle.json",
      status: reviewerBundle?.status || "healthy",
    },
    {
      label: "Launch report",
      description: "Open the technical readiness report used for the current decision.",
      href: launchReport?.href || "/raw/launch-gate/starter_launch_readiness_report.json",
      status: launchReport?.status || "warning",
    },
    {
      label: "Event feed",
      description: "Open the raw technical event feed used to build the dashboard state.",
      href: eventFeed?.href || "/raw/overlays/myStarterKit/artifacts/events.jsonl",
      status: eventFeed?.status || "healthy",
    },
  ];

  linksRoot.innerHTML = links
    .map(
      (item) => `
        <a class="deep-link-card" href="${escapeHtml(item.href)}">
          <div class="card-topline">
            <h3>${escapeHtml(item.label)}</h3>
            <span class="${statusClass(item.status || "neutral")}">${escapeHtml(statusLabel(item.status || "neutral"))}</span>
          </div>
          <p>${escapeHtml(item.description)}</p>
        </a>
      `,
    )
    .join("");
}

function renderError(error) {
  const message = `Unable to load the client overview. ${error.message || error}`;
  for (const root of [trafficSummaryRoot, processRoot, comparisonRoot, examplesRoot, readinessRoot, linksRoot]) {
    root.innerHTML = `<section class="loading-card error-card">${escapeHtml(message)}</section>`;
  }
}

async function boot() {
  try {
    const payload = await fetchJson("/api/control-plane/overview");
    const [allowedResult, deniedResult] = await Promise.allSettled([
      fetchJson("/raw/evidence/reviewer/inspectable-live-runtime/allowed-flow.json"),
      fetchJson("/raw/evidence/reviewer/inspectable-live-runtime/denied-flow.json"),
    ]);
    const allowedFlow = allowedResult.status === "fulfilled" ? allowedResult.value : null;
    const deniedFlow = deniedResult.status === "fulfilled" ? deniedResult.value : null;

    renderHero(payload);
    renderTrafficSummary(payload);
    renderProcess(payload);
    renderComparison(payload);
    renderExamples(payload, allowedFlow, deniedFlow);
    renderReadiness(payload);
    renderLinks(payload);
  } catch (error) {
    renderError(error);
  }
}

boot();
