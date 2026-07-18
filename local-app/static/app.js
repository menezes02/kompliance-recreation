const app = document.querySelector("#app");
const loading = document.querySelector("#loading");
const modalRoot = document.querySelector("#modal-root");
const toastRoot = document.querySelector("#toast-root");
const mainNav = document.querySelector("#main-nav");
const sidebar = document.querySelector("#sidebar");
const navOverlay = document.querySelector("#nav-overlay");

const LIST_ROUTES = {
  "/sites": {
    resource: "sites",
    title: "Sites",
    addLabel: "Add Site",
    columns: [
      ["name", "Name"],
      ["address", "Address"],
      ["created_at", "Created At", "date"],
    ],
    fields: [
      { name: "name", label: "Site Name", required: true },
      { name: "address", label: "Address", required: true },
      { name: "remarks", label: "Additional Remarks", type: "textarea", full: true },
    ],
  },
  "/workers-roles": {
    resource: "roles",
    title: "Roles",
    addLabel: "Add Role",
    columns: [
      ["name", "Name"],
      ["created_at", "Created At", "date"],
      ["updated_at", "Updated At", "date"],
    ],
    fields: [{ name: "name", label: "Role Name", required: true }],
  },
  "/workers": {
    resource: "workers",
    title: "Worker",
    addLabel: "Add Worker",
    columns: [
      ["worker_id", "Worker ID"],
      ["name", "Name"],
      ["email", "Email"],
      ["sites", "Assigned Sites"],
      ["roles", "Assigned Roles"],
      ["training_status", "Training Status", "status"],
      ["safe_pass_expiry", "Safe Pass Expiry Date"],
      ["induction_status", "Induction Status", "status"],
      ["phone", "Phone Number"],
    ],
    fields: [
      {
        name: "type",
        label: "Worker Type",
        type: "select",
        options: ["Permanent", "Temporary"],
        required: true,
      },
      { name: "name", label: "Worker Name", required: true },
      { name: "email", label: "Worker Email", type: "email", required: true },
      { name: "worker_id", label: "Worker ID" },
      { name: "phone", label: "Phone Number", required: true },
      { name: "emergency_phone", label: "Emergency Contact Number" },
      { name: "emergency_name", label: "Name of Person to Contact" },
      { name: "emergency_address", label: "Emergency Contact Address" },
      { name: "sites", label: "Assigned Sites" },
      { name: "roles", label: "Assigned Roles" },
      { name: "subcontractor", label: "Subcontractor" },
      {
        name: "status",
        label: "Approval Status",
        type: "select",
        options: ["Pending", "Approved"],
      },
      { name: "medical_details", label: "Relevant Medical History", type: "textarea", full: true },
    ],
  },
  "/subcontractor": {
    resource: "subcontractors",
    title: "Subcontractors",
    addLabel: "Add Subcontractor",
    columns: [
      ["company_name", "Subcontractor Company Name"],
      ["name", "Name"],
      ["email", "Email"],
      ["phone", "Phone Number"],
      ["expiry_date", "Expiry Date"],
    ],
    fields: [
      { name: "email", label: "Subcontractor Email", type: "email", required: true },
      { name: "expiry_date", label: "Expiry Date", type: "date", required: true },
      { name: "company_name", label: "Company Name" },
      { name: "name", label: "Contact Name" },
      { name: "phone", label: "Phone Number" },
    ],
  },
  "/training": {
    resource: "training",
    title: "Training Questions",
    addLabel: "Add Question",
    columns: [
      ["question", "Question"],
      ["created_at", "Created At", "date"],
      ["updated_at", "Updated At", "date"],
    ],
    fields: [{ name: "question", label: "Question", required: true, full: true }],
  },
  "/forms": {
    resource: "forms",
    title: "Forms",
    addLabel: "Add Form",
    columns: [
      ["name", "Name"],
      ["assigned_sites", "Assigned Sites"],
      ["assigned_roles", "Assigned Roles"],
      ["status", "Status", "status"],
      ["created_at", "Created At", "date"],
      ["updated_at", "Updated At", "date"],
    ],
    fields: [
      { name: "name", label: "Form Name", required: true, full: true },
      { name: "assigned_sites", label: "Assigned Sites" },
      { name: "assigned_roles", label: "Assigned Roles" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: ["Draft", "Active", "Archived"],
      },
      {
        name: "definition",
        label: "Sections and questions (JSON)",
        type: "textarea",
        full: true,
      },
    ],
  },
  "/form/distribution": {
    resource: "distributions",
    title: "Form Distributions",
    addLabel: "Assign Form",
    columns: [
      ["worker", "Worker Name"],
      ["sites", "Assigned Sites"],
      ["form", "Assigned Form"],
      ["assigned_date", "Assigned Date"],
      ["submitted_date", "Submitted Date"],
      ["score", "Score in %"],
      ["status", "Status", "status"],
    ],
    fields: [
      { name: "worker", label: "Worker", required: true },
      { name: "sites", label: "Sites", required: true },
      { name: "form", label: "Form", required: true },
      { name: "assigned_date", label: "Assigned Date", type: "date" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: ["Pending", "Submitted", "Completed"],
      },
    ],
  },
  "/appliances": {
    resource: "assets",
    title: "Assets",
    addLabel: "Add Assets",
    columns: [
      ["subcontractor", "Subcontractor Name"],
      ["name", "Asset Name"],
      ["asset_id", "Asset ID"],
      ["created_at", "Created At", "date"],
      ["updated_at", "Updated At", "date"],
    ],
    fields: [
      { name: "asset_id", label: "Appliance ID", required: true },
      { name: "name", label: "Appliance Name", required: true },
      { name: "subcontractor", label: "Subcontractor" },
    ],
  },
  "/document": {
    resource: "documents",
    title: "Documents",
    addLabel: "Add Document",
    columns: [
      ["subcontractor", "Subcontractor Name"],
      ["title", "Title"],
      ["file_name", "Document"],
      ["type", "Type"],
      ["created_at", "Created At", "date"],
    ],
    fields: [
      { name: "title", label: "Title", required: true },
      { name: "file_name", label: "Local file name", required: true },
      { name: "type", label: "Type" },
      { name: "subcontractor", label: "Subcontractor" },
    ],
  },
  "/ga1": documentSetConfig("ga1", "GA1 Forms", "Add GA1 Documents"),
  "/risk_assessment": documentSetConfig(
    "risk_assessment",
    "Risk Assessment / Safety Statement",
    "Add Risk Assessment / Safety Statement",
  ),
  "/ga2/form": hsaConfig("ga2", "GA2 Forms"),
  "/ga3/form": hsaConfig("ga3", "GA3 Forms"),
  "/ga3scaffold/form": hsaConfig("ga3_scaffold", "GA3 Scaffold Inspections"),
  "/af3/form": hsaConfig("af3", "AF3 Forms"),
  "/handover/form": hsaConfig("handover", "Handover Certificate"),
  "/ga2_manual/form": hsaConfig("ga2_manual", "GA2 Manual Forms"),
  "/ga3_manual/form": hsaConfig("ga3_manual", "GA3 Manual Forms"),
  "/inductions": {
    resource: "inductions",
    title: "Induction Forms",
    addLabel: "Create Induction Form",
    columns: [
      ["title", "Title"],
      ["site", "Site"],
      ["submissions", "Submissions"],
      ["status", "Status", "status"],
      ["created_at", "Created", "date"],
    ],
    fields: [
      { name: "title", label: "Induction Title", required: true },
      { name: "site", label: "Site", required: true },
      { name: "subcontractors", label: "Subcontractors", type: "textarea", full: true },
      {
        name: "pages",
        label: "Pages, media, and questions (JSON)",
        type: "textarea",
        full: true,
      },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: ["Draft", "Active", "Inactive"],
      },
    ],
  },
};

function hsaConfig(resource, title) {
  return {
    resource,
    title,
    addLabel: "Add Local Example",
    filterMode: "hsa",
    columns: [
      ["subcontractor", "Subcontractor Name"],
      ["site", "Site Name"],
      ["worker", "Worker Name"],
      ["worker_email", "Worker Email"],
      ["submitted_date", "Submitted Date"],
      ["archive_path", "Archived PDF", "archive"],
    ],
    fields: [
      { name: "subcontractor", label: "Subcontractor" },
      { name: "site", label: "Site", required: true },
      { name: "worker", label: "Worker", required: true },
      { name: "worker_email", label: "Worker Email", type: "email" },
      { name: "submitted_date", label: "Submitted Date", type: "date" },
      { name: "archive_path", label: "Archive path" },
    ],
  };
}

function documentSetConfig(resource, title, addLabel) {
  const columns = [
    ["title", "Title"],
    ["company", "Company Name"],
    ["subcontractor", "Subcontractor Name"],
    ["site", "Site Name"],
    ["expiry_date", "Expiry Date"],
    ["expiry_status", "Expiry Status", "status"],
  ];
  if (resource === "ga1") {
    columns.push(["archive_paths", "Documents", "archives"]);
  }
  return {
    resource,
    title,
    addLabel,
    columns,
    fields: [
      { name: "title", label: "Title", required: true },
      { name: "company", label: "Company" },
      { name: "subcontractor", label: "Company Subcontractor" },
      { name: "site", label: "Company Site", required: true },
      { name: "expiry_date", label: "Expiry Date", type: "date", required: true },
      { name: "document_paths", label: "Document paths", type: "textarea", full: true },
    ],
  };
}

const dashboardCards = [
  ["sites", "TOTAL SITES", "/sites", "blue", "🏗"],
  ["workers", "TOTAL WORKERS", "/workers", "slate", "👷"],
  ["subcontractors", "SUB-CONTRACTORS", "/subcontractor", "gold", "⛑"],
  ["forms", "TOTAL FORMS", "/forms", "olive", "▤"],
  ["ga2", "GA2 Forms", "/ga2/form", "purple", "🗎"],
  ["ga3", "GA3 Forms", "/ga3/form", "purple", "🗎"],
  ["ga3_scaffold", "GA3 Scaffold Inspections", "/ga3scaffold/form", "purple", "🗎"],
  ["af3", "AF3 Forms", "/af3/form", "purple", "🗎"],
  ["handover", "Handover Certificate", "/handover/form", "purple", "🗎"],
  ["ga2_manual", "GA2 Manual Form", "/ga2_manual/form", "purple", "🗎"],
  ["ga3_manual", "GA3 Manual Form", "/ga3_manual/form", "purple", "🗎"],
  ["ga1", "GA1 Forms", "/ga1", "purple", "🗎"],
  ["risk_assessment", "Risk Assessment / Safety Statement", "/risk_assessment", "purple", "🗎"],
  ["inductions", "INDUCTIONS", "/inductions", "purple", "🗎"],
];

const archivedDashboardIcons = [
  "/archive/static-assets/sites-icon.svg",
  "/archive/static-assets/workers-icon.svg",
  "/archive/static-assets/subcontractors-icon.svg",
  "/archive/static-assets/forms-icon.svg",
  ...Array(9).fill("/archive/static-assets/completed-forms-icon.svg"),
  "/archive/static-assets/forms-icon.svg",
];
dashboardCards.forEach((card, index) => {
  card[4] = archivedDashboardIcons[index];
});

const state = {
  search: "",
  pageSize: 10,
  page: 1,
  listFilters: {
    site: "",
    worker: "",
    dateStart: "",
    dateEnd: "",
    order: "newest",
  },
  calendarMonth: new Date().toISOString().slice(0, 7),
  calendarOpen: false,
  currentConfig: null,
  currentRows: [],
};

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return new Intl.DateTimeFormat("en-IE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

function archiveHref(value) {
  const safePath = String(value || "")
    .replaceAll("\\", "/")
    .split("/")
    .filter(Boolean)
    .map((part) => encodeURIComponent(part))
    .join("/");
  return safePath ? `/archive/${safePath}` : "";
}

function isPdfPath(value) {
  return /\.pdf$/i.test(String(value || ""));
}

function archiveDocumentLink(value) {
  const href = archiveHref(value);
  if (!href) return "";
  const fileName = String(value).replaceAll("\\", "/").split("/").pop();
  const previewAttributes = isPdfPath(value)
    ? `data-pdf-preview data-pdf-name="${escapeHtml(fileName)}"`
    : "";
  return `
    <a class="document-link" href="${escapeHtml(href)}" target="_blank" rel="noopener"
       ${previewAttributes} title="${isPdfPath(value) ? "Preview" : "Open"} ${escapeHtml(fileName)}">
      <span aria-hidden="true">↗</span>
      ${escapeHtml(fileName)}
    </a>
  `;
}

function dateValue(value) {
  const text = String(value || "").trim();
  const european = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (european) {
    return Date.UTC(Number(european[3]), Number(european[2]) - 1, Number(european[1]));
  }
  const parsed = Date.parse(text);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function isoDate(timestamp) {
  return new Date(timestamp).toISOString().slice(0, 10);
}

function displayDate(value) {
  const timestamp = dateValue(value);
  if (!timestamp) return "";
  return new Intl.DateTimeFormat("en-IE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(timestamp));
}

function selectedDateLabel() {
  const { dateStart, dateEnd } = state.listFilters;
  if (!dateStart) return "All submitted dates";
  if (!dateEnd || dateEnd === dateStart) return displayDate(dateStart);
  return `${displayDate(dateStart)} – ${displayDate(dateEnd)}`;
}

function calendarMarkup() {
  const [year, month] = state.calendarMonth.split("-").map(Number);
  const monthStart = Date.UTC(year, month - 1, 1);
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const leadingDays = (new Date(monthStart).getUTCDay() + 6) % 7;
  const today = new Date().toISOString().slice(0, 10);
  const { dateStart, dateEnd } = state.listFilters;
  const rangeStart = dateStart && dateEnd ? [dateStart, dateEnd].sort()[0] : "";
  const rangeEnd = dateStart && dateEnd ? [dateStart, dateEnd].sort()[1] : "";
  const monthLabel = new Intl.DateTimeFormat("en-IE", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(monthStart));
  const dayCells = Array.from({ length: 42 }, (_, index) => {
    const day = index - leadingDays + 1;
    if (day < 1 || day > daysInMonth) {
      return `<span class="calendar-day empty" aria-hidden="true"></span>`;
    }
    const iso = isoDate(Date.UTC(year, month - 1, day));
    const isEndpoint = iso === dateStart || iso === dateEnd;
    const isInRange = rangeStart && iso > rangeStart && iso < rangeEnd;
    const classes = [
      "calendar-day",
      isEndpoint ? "selected" : "",
      isInRange ? "in-range" : "",
      iso === today ? "today" : "",
    ]
      .filter(Boolean)
      .join(" ");
    return `
      <button class="${classes}" type="button" data-calendar-day="${iso}"
              aria-label="${escapeHtml(displayDate(iso))}" aria-pressed="${isEndpoint}">
        ${day}
      </button>
    `;
  }).join("");
  const guidance = dateStart && !dateEnd
    ? "Showing this day. Choose another date to extend the range."
    : "Choose one day, or choose two days for a range.";
  return `
    <div class="date-range-popover ${state.calendarOpen ? "" : "hidden"}" id="date-range-popover">
      <div class="calendar-header">
        <button type="button" data-calendar-nav="-1" aria-label="Previous month">‹</button>
        <strong>${escapeHtml(monthLabel)}</strong>
        <button type="button" data-calendar-nav="1" aria-label="Next month">›</button>
      </div>
      <div class="calendar-weekdays" aria-hidden="true">
        ${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => `<span>${day}</span>`).join("")}
      </div>
      <div class="calendar-grid">${dayCells}</div>
      <div class="calendar-footer">
        <small>${escapeHtml(guidance)}</small>
        <button type="button" id="clear-date-range">Clear date</button>
      </div>
    </div>
  `;
}

function uniqueValues(rows, key) {
  return [
    ...new Set(
      rows
        .map((row) => String(row[key] || "").trim())
        .filter((value) => value && value !== "-"),
    ),
  ].sort((left, right) => left.localeCompare(right, "en", { sensitivity: "base" }));
}

function applyListFilters(rows, config) {
  if (config.filterMode !== "hsa") return [...rows];
  const { site, worker, dateStart, dateEnd, order } = state.listFilters;
  const fromValue = dateValue(dateStart);
  const toValue = dateValue(dateEnd || dateStart);
  const filtered = rows.filter(
    (row) => {
      const submittedValue = dateValue(row.submitted_date);
      return (
        (!site || row.site === site) &&
        (!worker || row.worker === worker) &&
        (!fromValue || submittedValue >= fromValue) &&
        (!toValue || submittedValue <= toValue)
      );
    },
  );
  return filtered.sort((left, right) => {
    const difference = dateValue(left.created_at) - dateValue(right.created_at);
    const fallback = Number(left.source_id || left.id) - Number(right.source_id || right.id);
    const comparison = difference || fallback;
    return order === "oldest" ? comparison : -comparison;
  });
}

function renderCell(value, format) {
  if (format === "date") return formatDate(value);
  if (format === "status") {
    const status = String(value || "Pending");
    return `<span class="status ${escapeHtml(status.toLowerCase().replaceAll(" ", "-"))}">${escapeHtml(status)}</span>`;
  }
  if (format === "archive") {
    return archiveDocumentLink(value) || "—";
  }
  if (format === "archives") {
    const paths = Array.isArray(value) ? value : [];
    if (!paths.length) return "—";
    return `<div class="document-links">${paths.map(archiveDocumentLink).join("")}</div>`;
  }
  if (!value) return "—";
  if (String(value).includes("/") && String(value).includes(".")) {
    return escapeHtml(value);
  }
  return escapeHtml(value);
}

function openPdfPreview(href, fileName) {
  const safeHref = escapeHtml(href);
  const safeName = escapeHtml(fileName || "Archived document.pdf");
  modalRoot.innerHTML = `
    <div class="modal-backdrop pdf-preview-backdrop">
      <section class="pdf-preview-modal" role="dialog" aria-modal="true" aria-labelledby="pdf-preview-title">
        <header class="pdf-preview-header">
          <div class="pdf-preview-title">
            <span class="pdf-badge">PDF</span>
            <div>
              <small>Archived compliance document</small>
              <h2 id="pdf-preview-title">${safeName}</h2>
            </div>
          </div>
          <div class="pdf-preview-actions">
            <a class="button button-secondary" href="${safeHref}" target="_blank" rel="noopener">
              Open in new tab
            </a>
            <a class="button button-primary" href="${safeHref}" download="${safeName}">
              Download PDF
            </a>
            <button class="pdf-preview-close" type="button" aria-label="Close PDF preview">×</button>
          </div>
        </header>
        <div class="pdf-preview-body">
          <div class="pdf-preview-loading">
            <span></span>
            Loading document preview…
          </div>
          <iframe class="pdf-preview-frame" src="${safeHref}#view=FitH&toolbar=1"
                  title="PDF preview: ${safeName}"></iframe>
          <p class="pdf-preview-fallback">
            If the document does not appear,
            <a href="${safeHref}" target="_blank" rel="noopener">open it in a new tab</a>.
          </p>
        </div>
      </section>
    </div>
  `;
  document.body.classList.add("modal-open");
  const close = () => {
    modalRoot.innerHTML = "";
    document.body.classList.remove("modal-open");
  };
  modalRoot.querySelector(".pdf-preview-close").addEventListener("click", close);
  modalRoot.querySelector(".pdf-preview-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("pdf-preview-backdrop")) close();
  });
  modalRoot.querySelector(".pdf-preview-frame").addEventListener("load", () => {
    modalRoot.querySelector(".pdf-preview-body")?.classList.add("loaded");
  });
  modalRoot.querySelector(".pdf-preview-close").focus();
}

function setLoading(visible) {
  loading.classList.toggle("hidden", !visible);
}

function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastRoot.append(toast);
  setTimeout(() => toast.remove(), 3200);
}

function updateActiveNavigation(path) {
  document.querySelectorAll("[data-route]").forEach((link) => {
    const href = link.getAttribute("href");
    link.classList.toggle("active", href === path);
  });
  document.querySelectorAll(".nav-group").forEach((group) => {
    const hasActiveChild = Boolean(group.querySelector(".nav-menu a.active"));
    group.classList.toggle("active", hasActiveChild);
  });
}

function pageHeader(title, subtitle = "", action = "") {
  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">${escapeHtml(title)}</h1>
        ${subtitle ? `<p class="page-subtitle">${escapeHtml(subtitle)}</p>` : ""}
      </div>
      ${action}
    </div>
  `;
}

async function renderDashboard() {
  const counts = await api("/api/dashboard");
  const complianceTotal = [
    "ga2",
    "ga3",
    "ga3_scaffold",
    "af3",
    "handover",
    "ga2_manual",
    "ga3_manual",
    "ga1",
    "risk_assessment",
  ].reduce((total, key) => total + Number(counts[key] || 0), 0);
  const cards = dashboardCards
    .map(([key, label, href, color, icon]) => {
      const badge =
        key === "workers" && counts.unapproved_workers
          ? `<span class="metric-badge">Unapproved: ${counts.unapproved_workers}</span>`
          : "";
      return `
        <a class="metric-card ${color}" href="${href}" data-route>
          ${badge}
          <div class="metric-value">${counts[key] ?? 0}</div>
          <div class="metric-label">${escapeHtml(label)}</div>
          <span class="metric-icon" aria-hidden="true"><img src="${icon}" alt="" /></span>
        </a>
      `;
    })
    .join("");
  app.innerHTML = `
    ${pageHeader(
      "Operations overview",
      "A live view of the secured customer-data snapshot",
      `<a class="button button-secondary" href="/archive" data-route>Browse source archive</a>`,
    )}
    <section class="dashboard-hero">
      <div class="dashboard-hero-copy">
        <span class="hero-eyebrow">Compliance command centre</span>
        <h2>Your safety records, clearly organised.</h2>
        <p>Monitor workforce readiness, inspection activity, forms and documentation from one workspace.</p>
        <div class="hero-actions">
          <a class="button button-primary" href="/workers" data-route>Review workforce</a>
          <a class="button button-ghost" href="/forms" data-route>Manage forms</a>
        </div>
      </div>
      <div class="hero-stats">
        <div><span>${Number(counts.unapproved_workers || 0).toLocaleString()}</span><small>Workers awaiting approval</small></div>
        <div><span>${complianceTotal.toLocaleString()}</span><small>Compliance records</small></div>
        <div><span>${Number(counts.inductions || 0).toLocaleString()}</span><small>Active induction forms</small></div>
      </div>
    </section>
    <div class="section-heading">
      <div><span>Workspace modules</span><strong>Everything at a glance</strong></div>
      <small>Customer snapshot · read-only source</small>
    </div>
    <section class="dashboard-grid">${cards}</section>
  `;
  bindRouteLinks();
}

async function renderList(config) {
  state.currentConfig = config;
  const query = new URLSearchParams({
    q: state.search,
    limit: "5000",
  });
  const result = await api(`/api/resources/${config.resource}?${query}`);
  const filteredRows = applyListFilters(result.data, config);
  const filteredTotal = filteredRows.length;
  state.currentRows = filteredRows;
  const totalPages = Math.max(1, Math.ceil(filteredTotal / state.pageSize));
  state.page = Math.min(state.page, totalPages);
  const start = (state.page - 1) * state.pageSize;
  const rows = filteredRows.slice(start, start + state.pageSize);
  const siteOptions = uniqueValues(result.data, "site");
  const workerOptions = uniqueValues(result.data, "worker");

  const headers = [
    `<th>#</th>`,
    ...config.columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`),
    `<th>Actions</th>`,
  ].join("");

  const body = rows.length
    ? rows
        .map((row, index) => {
          const cells = config.columns
            .map(([key, , format]) => `<td>${renderCell(row[key], format)}</td>`)
            .join("");
          const documentPaths = [
            ...(Array.isArray(row.archive_paths) ? row.archive_paths : []),
            row.archive_path,
          ].filter(Boolean);
          const actionPath =
            documentPaths.find((path) => isPdfPath(path)) || documentPaths[0];
          const actionFileName = actionPath
            ? String(actionPath).replaceAll("\\", "/").split("/").pop()
            : "";
          const viewAction = actionPath
            ? `
              <a class="button-icon view-document" href="${escapeHtml(archiveHref(actionPath))}"
                 target="_blank" rel="noopener"
                 ${isPdfPath(actionPath) ? `data-pdf-preview data-pdf-name="${escapeHtml(actionFileName)}"` : ""}
                 title="${isPdfPath(actionPath) ? "Preview PDF" : "Open document"}"
                 aria-label="${isPdfPath(actionPath) ? "Preview archived PDF" : "Open archived document"}">
                ${isPdfPath(actionPath) ? "Preview" : "Open"}
              </a>
            `
            : "";
          return `
            <tr>
              <td>${start + index + 1}</td>
              ${cells}
              <td>
                <div class="actions">
                  ${viewAction}
                  <button class="button-icon" data-edit="${row.id}" title="Edit">✎</button>
                  <button class="button-icon danger" data-delete="${row.id}" title="Delete">⌫</button>
                </div>
              </td>
            </tr>
          `;
        })
        .join("")
    : `<tr><td class="table-empty" colspan="${config.columns.length + 2}">No records found.</td></tr>`;

  const pagination = Array.from({ length: totalPages }, (_, index) => index + 1)
    .slice(Math.max(0, state.page - 3), Math.min(totalPages, state.page + 2))
    .map(
      (page) =>
        `<button class="${page === state.page ? "active" : ""}" data-page="${page}">${page}</button>`,
    )
    .join("");

  const advancedFilters =
    config.filterMode === "hsa"
      ? `
        <div class="advanced-filters" aria-label="Record filters">
          <label>
            <span>Site</span>
            <select id="filter-site">
              <option value="">All sites</option>
              ${siteOptions
                .map(
                  (site) =>
                    `<option value="${escapeHtml(site)}" ${site === state.listFilters.site ? "selected" : ""}>${escapeHtml(site)}</option>`,
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>Worker name</span>
            <select id="filter-worker">
              <option value="">All workers</option>
              ${workerOptions
                .map(
                  (worker) =>
                    `<option value="${escapeHtml(worker)}" ${worker === state.listFilters.worker ? "selected" : ""}>${escapeHtml(worker)}</option>`,
                )
                .join("")}
            </select>
          </label>
          <div class="date-range-filter">
            <span class="filter-label">Submitted date</span>
            <button class="date-range-trigger ${state.listFilters.dateStart ? "active" : ""}"
                    id="date-range-trigger" type="button"
                    aria-haspopup="dialog" aria-expanded="${state.calendarOpen}">
              <span aria-hidden="true">▦</span>
              <strong>${escapeHtml(selectedDateLabel())}</strong>
              <span aria-hidden="true">⌄</span>
            </button>
            ${calendarMarkup()}
          </div>
          <label>
            <span>Creation order</span>
            <select id="filter-order">
              <option value="newest" ${state.listFilters.order === "newest" ? "selected" : ""}>Newest first</option>
              <option value="oldest" ${state.listFilters.order === "oldest" ? "selected" : ""}>Oldest first</option>
            </select>
          </label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `
      : "";

  app.innerHTML = `
    ${pageHeader(
      config.title,
      "",
      `<button class="button button-primary" id="add-record">＋ ${escapeHtml(config.addLabel)}</button>`,
    )}
    <section class="card table-card">
      <div class="table-toolbar">
        <label class="table-size">Show
          <select id="page-size">
            ${[10, 25, 50, 100]
              .map(
                (size) =>
                  `<option value="${size}" ${size === state.pageSize ? "selected" : ""}>${size}</option>`,
              )
              .join("")}
          </select>
          entries
        </label>
        <label class="search-field">Search:
          <input id="table-search" value="${escapeHtml(state.search)}" />
        </label>
      </div>
      ${advancedFilters}
      <div class="table-scroll">
        <table class="data-table">
          <thead><tr>${headers}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
      <div class="table-footer">
        <span>Showing ${filteredTotal ? start + 1 : 0} to ${Math.min(start + rows.length, filteredTotal)} of ${filteredTotal} entries</span>
        <div class="pagination">${pagination}</div>
      </div>
    </section>
  `;
  bindTableEvents(config);
}

function bindTableEvents(config) {
  document.querySelector("#add-record")?.addEventListener("click", () => openRecordModal(config));
  document.querySelectorAll("[data-pdf-preview]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      openPdfPreview(link.getAttribute("href"), link.dataset.pdfName);
    });
  });
  document.querySelector("#page-size")?.addEventListener("change", async (event) => {
    state.pageSize = Number(event.target.value);
    state.page = 1;
    await renderList(config);
  });
  let searchTimer;
  document.querySelector("#table-search")?.addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      state.search = event.target.value;
      state.page = 1;
      await renderList(config);
    }, 250);
  });
  ["site", "worker", "order"].forEach((filterName) => {
    document.querySelector(`#filter-${filterName}`)?.addEventListener("change", async (event) => {
      state.listFilters[filterName] = event.target.value;
      state.calendarOpen = false;
      state.page = 1;
      await renderList(config);
    });
  });
  document.querySelector("#date-range-trigger")?.addEventListener("click", async () => {
    state.calendarOpen = !state.calendarOpen;
    if (state.calendarOpen && state.listFilters.dateStart) {
      state.calendarMonth = state.listFilters.dateStart.slice(0, 7);
    }
    await renderList(config);
  });
  document.querySelectorAll("[data-calendar-nav]").forEach((button) => {
    button.addEventListener("click", async () => {
      const [year, month] = state.calendarMonth.split("-").map(Number);
      const target = new Date(Date.UTC(year, month - 1 + Number(button.dataset.calendarNav), 1));
      state.calendarMonth = target.toISOString().slice(0, 7);
      state.calendarOpen = true;
      await renderList(config);
    });
  });
  document.querySelectorAll("[data-calendar-day]").forEach((button) => {
    button.addEventListener("click", async () => {
      const selected = button.dataset.calendarDay;
      const { dateStart, dateEnd } = state.listFilters;
      if (!dateStart || dateEnd) {
        state.listFilters.dateStart = selected;
        state.listFilters.dateEnd = "";
        state.calendarOpen = true;
      } else if (selected === dateStart) {
        state.listFilters.dateEnd = "";
        state.calendarOpen = false;
      } else {
        const [start, end] = [dateStart, selected].sort();
        state.listFilters.dateStart = start;
        state.listFilters.dateEnd = end;
        state.calendarOpen = false;
      }
      state.page = 1;
      await renderList(config);
    });
  });
  document.querySelector("#clear-date-range")?.addEventListener("click", async () => {
    state.listFilters.dateStart = "";
    state.listFilters.dateEnd = "";
    state.calendarOpen = false;
    state.page = 1;
    await renderList(config);
  });
  document.querySelector("#clear-filters")?.addEventListener("click", async () => {
    state.listFilters = {
      site: "",
      worker: "",
      dateStart: "",
      dateEnd: "",
      order: "newest",
    };
    state.calendarOpen = false;
    state.page = 1;
    await renderList(config);
  });
  document.querySelectorAll("[data-page]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.page = Number(button.dataset.page);
      await renderList(config);
    });
  });
  document.querySelectorAll("[data-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => row.id === Number(button.dataset.edit));
      openRecordModal(config, record);
    });
  });
  document.querySelectorAll("[data-delete]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = Number(button.dataset.delete);
      if (!window.confirm("Delete this local record? Production data is never affected.")) return;
      try {
        await api(`/api/resources/${config.resource}/${id}`, { method: "DELETE" });
        showToast("Local record deleted.");
        await renderList(config);
      } catch (error) {
        showToast(error.message, "error");
      }
    });
  });
}

function fieldMarkup(field, record = {}) {
  const value = record[field.name] ?? field.value ?? "";
  const classes = `form-group ${field.full ? "full" : ""}`;
  const required = field.required ? "required" : "";
  let control;
  if (field.type === "textarea") {
    control = `<textarea class="form-control" name="${field.name}" ${field.required ? "required" : ""}>${escapeHtml(value)}</textarea>`;
  } else if (field.type === "select") {
    control = `
      <select class="form-control" name="${field.name}" ${field.required ? "required" : ""}>
        <option value="">Select</option>
        ${(field.options || [])
          .map(
            (option) =>
              `<option value="${escapeHtml(option)}" ${String(value) === String(option) ? "selected" : ""}>${escapeHtml(option)}</option>`,
          )
          .join("")}
      </select>
    `;
  } else {
    control = `<input class="form-control" type="${field.type || "text"}" name="${field.name}" value="${escapeHtml(value)}" ${field.required ? "required" : ""} />`;
  }
  return `
    <div class="${classes}">
      <label class="${required}">${escapeHtml(field.label)}</label>
      ${control}
    </div>
  `;
}

function parseStructuredValue(value, fallback) {
  if (!value) return structuredClone(fallback);
  if (typeof value === "object") return structuredClone(value);
  try {
    return JSON.parse(value);
  } catch {
    return structuredClone(fallback);
  }
}

function formSectionMarkup(section, sectionIndex) {
  return `
    <article class="builder-card" data-section="${sectionIndex}">
      <div class="builder-card-header">
        <span class="builder-index">Section ${sectionIndex + 1}</span>
        <button type="button" class="button-link danger" data-builder-action="remove-section" data-section="${sectionIndex}">Remove section</button>
      </div>
      <label class="builder-label">Section name
        <input class="form-control" data-section-name="${sectionIndex}" value="${escapeHtml(section.name || "")}" />
      </label>
      <div class="builder-items">
        ${(section.questions || [])
          .map(
            (question, questionIndex) => `
              <div class="builder-item">
                <span class="builder-item-number">${questionIndex + 1}</span>
                <input class="form-control" data-question-text="${sectionIndex}:${questionIndex}" value="${escapeHtml(question.text || "")}" placeholder="Question or instruction" />
                <select class="form-control compact" data-question-type="${sectionIndex}:${questionIndex}">
                  ${["Default", "Textbox", "Date Time", "Date", "Time", "Location", "Sign"]
                    .map(
                      (type) =>
                        `<option ${type === question.type ? "selected" : ""}>${type}</option>`,
                    )
                    .join("")}
                </select>
                <button type="button" class="button-icon danger" data-builder-action="remove-question" data-section="${sectionIndex}" data-question="${questionIndex}" aria-label="Remove question">×</button>
              </div>
            `,
          )
          .join("")}
      </div>
      <button type="button" class="button button-secondary button-small" data-builder-action="add-question" data-section="${sectionIndex}">+ Add question</button>
    </article>
  `;
}

function inductionPageMarkup(page, pageIndex) {
  const blocks = page.blocks?.length ? page.blocks : [{ type: "text", text: "" }];
  return `
    <article class="builder-card" data-page="${pageIndex}">
      <div class="builder-card-header">
        <span class="builder-index">Page ${pageIndex + 1}</span>
        <button type="button" class="button-link danger" data-builder-action="remove-page" data-page="${pageIndex}">Remove page</button>
      </div>
      <div class="builder-items builder-blocks">
        ${blocks
          .map((block, blockIndex) => {
            const isQuestion = block.type === "question";
            const options = (block.options || []).map((option) => option.text || option).join("\n");
            const correctIndex = Math.max(
              0,
              (block.options || []).findIndex((option) => option.correct),
            );
            return `
              <div class="builder-block">
                <div class="builder-block-toolbar">
                  <select class="form-control compact" data-block-type="${pageIndex}:${blockIndex}">
                    <option value="text" ${!isQuestion ? "selected" : ""}>Text / media</option>
                    <option value="question" ${isQuestion ? "selected" : ""}>Question</option>
                  </select>
                  <button type="button" class="button-link danger" data-builder-action="remove-block" data-page="${pageIndex}" data-block="${blockIndex}">Remove block</button>
                </div>
                <textarea class="form-control builder-textarea" data-block-text="${pageIndex}:${blockIndex}" placeholder="${isQuestion ? "Question" : "Page content"}">${escapeHtml(block.text || block.heading || "")}</textarea>
                ${
                  isQuestion
                    ? `
                      <div class="builder-question-options">
                        <label>Choices, one per line
                          <textarea class="form-control" data-block-options="${pageIndex}:${blockIndex}">${escapeHtml(options)}</textarea>
                        </label>
                        <label>Correct choice
                          <input class="form-control compact" type="number" min="1" value="${correctIndex + 1}" data-block-correct="${pageIndex}:${blockIndex}" />
                        </label>
                      </div>
                    `
                    : ""
                }
              </div>
            `;
          })
          .join("")}
      </div>
      <div class="builder-inline-actions">
        <button type="button" class="button button-secondary button-small" data-builder-action="add-text" data-page="${pageIndex}">+ Text block</button>
        <button type="button" class="button button-secondary button-small" data-builder-action="add-choice" data-page="${pageIndex}">+ Question</button>
      </div>
    </article>
  `;
}

async function openStructuredBuilder(config, record = null) {
  const isForm = config.resource === "forms";
  const fallback = isForm
    ? { sections: [{ name: "New section", questions: [{ text: "", type: "Textbox" }] }] }
    : { pages: [{ index: 0, blocks: [{ type: "text", text: "" }] }] };
  const definition = parseStructuredValue(
    record?.[isForm ? "definition" : "pages"],
    fallback,
  );
  const builderState = isForm
    ? { sections: definition.sections || definition || fallback.sections }
    : { pages: definition.pages || definition || fallback.pages };

  modalRoot.innerHTML = `
    <div class="modal-backdrop" role="presentation">
      <section class="modal modal-wide" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="modal-header">
          <div>
            <h2 id="modal-title">${record ? "Edit" : "Create"} ${isForm ? "Form" : "Induction"}</h2>
            <p class="modal-kicker">Local builder — no production data is changed</p>
          </div>
          <button class="modal-close" aria-label="Close">×</button>
        </div>
        <form class="modal-body builder-modal-body" id="structured-form">
          <div class="form-grid builder-metadata">
            ${
              isForm
                ? `
                  ${fieldMarkup({ name: "name", label: "Form Name", required: true }, record || {})}
                  ${fieldMarkup({ name: "assigned_sites", label: "Assigned Sites" }, record || {})}
                  ${fieldMarkup({ name: "assigned_roles", label: "Assigned Roles" }, record || {})}
                  ${fieldMarkup({ name: "status", label: "Status", type: "select", options: ["Draft", "Active", "Archived"] }, record || {})}
                `
                : `
                  ${fieldMarkup({ name: "title", label: "Induction Title", required: true }, record || {})}
                  ${fieldMarkup({ name: "site", label: "Site", required: true }, record || {})}
                  ${fieldMarkup({ name: "subcontractors", label: "Subcontractors" }, record || {})}
                  ${fieldMarkup({ name: "status", label: "Status", type: "select", options: ["Draft", "Active", "Inactive"] }, record || {})}
                `
            }
          </div>
          <div class="builder-template-bar">
            <label>Start from a mapped example
              <select class="form-control" id="builder-example">
                <option value="">Choose an example</option>
              </select>
            </label>
            <button type="button" class="button button-secondary" id="load-builder-example">Load example</button>
          </div>
          <section id="builder-workspace" class="builder-workspace"></section>
          <div class="builder-footer">
            <button type="button" class="button button-secondary" id="builder-add">${isForm ? "+ Add section" : "+ Add page"}</button>
            <div class="form-actions">
              <button type="button" class="button button-secondary modal-cancel">Cancel</button>
              <button type="submit" class="button button-primary">${record ? "Update" : "Save"} locally</button>
            </div>
          </div>
        </form>
      </section>
    </div>
  `;

  const workspace = modalRoot.querySelector("#builder-workspace");
  const renderWorkspace = () => {
    workspace.innerHTML = isForm
      ? builderState.sections.map(formSectionMarkup).join("")
      : builderState.pages.map(inductionPageMarkup).join("");
  };
  renderWorkspace();

  const exampleSelect = modalRoot.querySelector("#builder-example");
  let examples = [];
  let exampleCatalog = null;
  try {
    const response = await fetch(
      isForm ? "/examples/custom-forms.json" : "/examples/inductions.json",
    );
    const mapped = await response.json();
    exampleCatalog = mapped;
    examples = isForm ? mapped : mapped.inductions || [];
    exampleSelect.insertAdjacentHTML(
      "beforeend",
      examples
        .map((example, index) => `<option value="${index}">${escapeHtml(example.name || example.title)}</option>`)
        .join(""),
    );
  } catch {
    exampleSelect.insertAdjacentHTML("beforeend", `<option disabled>Examples unavailable</option>`);
  }

  const close = () => (modalRoot.innerHTML = "");
  modalRoot.querySelector(".modal-close").addEventListener("click", close);
  modalRoot.querySelector(".modal-cancel").addEventListener("click", close);
  modalRoot.querySelector(".modal-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("modal-backdrop")) close();
  });

  modalRoot.querySelector("#load-builder-example").addEventListener("click", () => {
    const example = examples[Number(exampleSelect.value)];
    if (!example) return;
    if (isForm) {
      builderState.sections = structuredClone(example.sections || []);
      modalRoot.querySelector('[name="name"]').value = example.name || "";
    } else {
      const common = [
        ...(exampleCatalog?.shared_content_pages || []).map((page) => ({
          index: page.index,
          blocks: (page.blocks || [page]).map((block) => ({
            type: "text",
            text: block.heading,
          })),
        })),
        ...(example.site_pages || []).map((page) => ({
          index: page.index,
          blocks: [{ type: "text", text: page.heading }],
        })),
        ...((exampleCatalog?.shared_questions || []).map((question, index) => ({
          index: 13 + index,
          blocks: [
            {
              ...question,
              type: "question",
              question_type: question.type || "single_choice",
            },
          ],
        }))),
      ];
      builderState.pages = common.sort((a, b) => a.index - b.index);
      modalRoot.querySelector('[name="title"]').value = example.title || "";
      modalRoot.querySelector('[name="site"]').value = example.site || "";
    }
    renderWorkspace();
  });

  workspace.addEventListener("input", (event) => {
    const target = event.target;
    if (target.dataset.sectionName !== undefined) {
      builderState.sections[Number(target.dataset.sectionName)].name = target.value;
    }
    if (target.dataset.questionText) {
      const [section, question] = target.dataset.questionText.split(":").map(Number);
      builderState.sections[section].questions[question].text = target.value;
    }
    if (target.dataset.questionType) {
      const [section, question] = target.dataset.questionType.split(":").map(Number);
      builderState.sections[section].questions[question].type = target.value;
    }
    if (target.dataset.blockType) {
      const [page, block] = target.dataset.blockType.split(":").map(Number);
      builderState.pages[page].blocks[block].type = target.value;
      renderWorkspace();
    }
    if (target.dataset.blockText) {
      const [page, block] = target.dataset.blockText.split(":").map(Number);
      builderState.pages[page].blocks[block].text = target.value;
    }
    if (target.dataset.blockOptions) {
      const [page, block] = target.dataset.blockOptions.split(":").map(Number);
      const correct = Number(
        workspace.querySelector(`[data-block-correct="${page}:${block}"]`)?.value || 1,
      );
      builderState.pages[page].blocks[block].options = target.value
        .split("\n")
        .filter(Boolean)
        .map((text, index) => ({ text, correct: index + 1 === correct }));
    }
    if (target.dataset.blockCorrect) {
      const [page, block] = target.dataset.blockCorrect.split(":").map(Number);
      const correct = Number(target.value || 1);
      const options = builderState.pages[page].blocks[block].options || [];
      options.forEach((option, index) => (option.correct = index + 1 === correct));
    }
  });

  workspace.addEventListener("click", (event) => {
    const button = event.target.closest("[data-builder-action]");
    if (!button) return;
    const action = button.dataset.builderAction;
    const section = Number(button.dataset.section);
    const question = Number(button.dataset.question);
    const page = Number(button.dataset.page);
    const block = Number(button.dataset.block);
    if (action === "remove-section") builderState.sections.splice(section, 1);
    if (action === "add-question") {
      builderState.sections[section].questions ||= [];
      builderState.sections[section].questions.push({ text: "", type: "Textbox" });
    }
    if (action === "remove-question") builderState.sections[section].questions.splice(question, 1);
    if (action === "remove-page") builderState.pages.splice(page, 1);
    if (action === "remove-block") builderState.pages[page].blocks.splice(block, 1);
    if (action === "add-text") builderState.pages[page].blocks.push({ type: "text", text: "" });
    if (action === "add-choice") {
      builderState.pages[page].blocks.push({
        type: "question",
        text: "",
        question_type: "single_choice",
        options: [
          { text: "Choice 1", correct: true },
          { text: "Choice 2", correct: false },
        ],
      });
    }
    renderWorkspace();
  });

  modalRoot.querySelector("#builder-add").addEventListener("click", () => {
    if (isForm) {
      builderState.sections.push({
        name: `Section ${builderState.sections.length + 1}`,
        questions: [{ text: "", type: "Textbox" }],
      });
    } else {
      builderState.pages.push({
        index: builderState.pages.length,
        blocks: [{ type: "text", text: "" }],
      });
    }
    renderWorkspace();
  });

  modalRoot.querySelector("#structured-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    data[isForm ? "definition" : "pages"] = JSON.stringify(builderState);
    const url = record
      ? `/api/resources/${config.resource}/${record.id}`
      : `/api/resources/${config.resource}`;
    try {
      await api(url, {
        method: record ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      close();
      showToast(record ? "Local record updated." : "Local record created.");
      await renderList(config);
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}

function openRecordModal(config, record = null) {
  if (["forms", "inductions"].includes(config.resource)) {
    openStructuredBuilder(config, record);
    return;
  }
  modalRoot.innerHTML = `
    <div class="modal-backdrop" role="presentation">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="modal-header">
          <h2 id="modal-title">${record ? "Edit" : "Add New"} ${escapeHtml(config.title)}</h2>
          <button class="modal-close" aria-label="Close">×</button>
        </div>
        <form class="modal-body" id="record-form">
          <div class="form-grid">
            ${config.fields.map((field) => fieldMarkup(field, record || {})).join("")}
          </div>
          <div class="form-actions">
            <button type="button" class="button button-secondary modal-cancel">Cancel</button>
            <button type="submit" class="button button-primary">${record ? "Update" : "Submit"}</button>
          </div>
        </form>
      </section>
    </div>
  `;
  const close = () => (modalRoot.innerHTML = "");
  modalRoot.querySelector(".modal-close").addEventListener("click", close);
  modalRoot.querySelector(".modal-cancel").addEventListener("click", close);
  modalRoot.querySelector(".modal-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("modal-backdrop")) close();
  });
  modalRoot.querySelector("#record-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const url = record
        ? `/api/resources/${config.resource}/${record.id}`
        : `/api/resources/${config.resource}`;
      await api(url, {
        method: record ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      close();
      showToast(record ? "Local record updated." : "Local record created.");
      await renderList(config);
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}

async function renderArchive() {
  const result = await api("/api/archive?limit=5000");
  const totalBytes = result.data.reduce((sum, file) => sum + file.size, 0);
  const categories = [
    ...new Set(
      result.data.map((file) => file.path.split("/").slice(0, -1).join("/")),
    ),
  ].sort();
  app.innerHTML = `
    ${pageHeader("Source Archive", "Authorized production examples stored locally")}
    <div class="archive-summary">
      <div class="card summary-box"><span class="summary-value">${result.total}</span>Local files indexed</div>
      <div class="card summary-box"><span class="summary-value">${formatBytes(totalBytes)}</span>Total archive size</div>
      <div class="card summary-box"><span class="summary-value">${result.ready ? "Ready" : "Waiting"}</span>Archive state</div>
    </div>
    <section class="card table-card">
      <div class="table-toolbar archive-toolbar">
        <label>Category
          <select id="archive-category">
            <option value="">All categories</option>
            ${categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join("")}
          </select>
        </label>
        <label class="search-field">Search:
          <input id="archive-search" placeholder="File name or path" />
        </label>
      </div>
      <p class="archive-result-note" id="archive-result-note"></p>
      <div class="table-scroll">
        <table class="data-table">
          <thead><tr><th>#</th><th>Path</th><th>Type</th><th>Size</th><th>Action</th></tr></thead>
          <tbody id="archive-rows"></tbody>
        </table>
      </div>
    </section>
  `;

  const renderArchiveRows = () => {
    const category = document.querySelector("#archive-category").value;
    const search = document.querySelector("#archive-search").value.trim().toLowerCase();
    const filtered = result.data.filter(
      (file) =>
        (!category || file.path.startsWith(`${category}/`)) &&
        (!search || file.path.toLowerCase().includes(search)),
    );
    const visible = filtered.slice(0, 300);
    document.querySelector("#archive-result-note").textContent =
      `Showing ${visible.length.toLocaleString()} of ${filtered.length.toLocaleString()} matching files.`;
    document.querySelector("#archive-rows").innerHTML = visible.length
      ? visible
          .map(
            (file, index) => `
              <tr>
                <td>${index + 1}</td>
                <td>${escapeHtml(file.path)}</td>
                <td>${escapeHtml(file.type.toUpperCase() || "FILE")}</td>
                <td>${formatBytes(file.size)}</td>
                <td><a class="archive-link" href="/archive/${encodeURI(file.path)}" target="_blank" rel="noopener">Open local copy</a></td>
              </tr>
            `,
          )
          .join("")
      : `<tr><td class="table-empty" colspan="5">No matching archive files.</td></tr>`;
  };
  document.querySelector("#archive-category").addEventListener("change", renderArchiveRows);
  document.querySelector("#archive-search").addEventListener("input", renderArchiveRows);
  renderArchiveRows();
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function renderProfile() {
  app.innerHTML = `
    ${pageHeader("My Profile")}
    <section class="card form-card">
      <form id="profile-form">
        <div class="form-grid">
          ${[
            { name: "company_name", label: "Company Name", required: true, value: "Local Company" },
            { name: "email", label: "Email", type: "email", required: true, value: "admin@example.test" },
            { name: "admin_name", label: "Company Admin Name", required: true, value: "Local Administrator" },
            { name: "admin_email", label: "Company Admin Email", type: "email", value: "admin@example.test" },
            { name: "phone", label: "Phone Number", value: "+353" },
            { name: "address", label: "Address", full: true, value: "Local development address" },
          ]
            .map((field) => fieldMarkup(field, field))
            .join("")}
        </div>
        <div class="form-actions"><button class="button button-primary">Update</button></div>
      </form>
    </section>
  `;
  document.querySelector("#profile-form").addEventListener("submit", (event) => {
    event.preventDefault();
    showToast("Profile saved locally.");
  });
}

function renderChangePassword() {
  app.innerHTML = `
    ${pageHeader("Change password")}
    <section class="card form-card">
      <form id="password-form">
        <div class="form-grid">
          ${[
            { name: "current", label: "Current password", type: "password", required: true },
            { name: "new", label: "New password", type: "password", required: true },
            { name: "confirm", label: "Confirm password", type: "password", required: true },
          ]
            .map((field) => fieldMarkup(field))
            .join("")}
        </div>
        <div class="form-actions"><button class="button button-primary">Update password</button></div>
      </form>
    </section>
  `;
  document.querySelector("#password-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (form.get("new") !== form.get("confirm")) {
      showToast("New passwords do not match.", "error");
      return;
    }
    event.currentTarget.reset();
    showToast("Password changed in the local prototype only.");
  });
}

function renderContact() {
  app.innerHTML = `
    ${pageHeader("Contact us", "We are happy to provide info and assist you")}
    <section class="card form-card">
      <form id="contact-form">
        <div class="form-grid">
          ${[
            { name: "name", label: "Name", required: true },
            { name: "email", label: "Email", type: "email", required: true, value: "admin@example.test" },
            { name: "subject", label: "Subject", required: true, full: true },
            { name: "message", label: "Message", type: "textarea", required: true, full: true },
          ]
            .map((field) => fieldMarkup(field, field))
            .join("")}
        </div>
        <div class="form-actions"><button class="button button-primary">Submit Now</button></div>
      </form>
    </section>
  `;
  document.querySelector("#contact-form").addEventListener("submit", (event) => {
    event.preventDefault();
    showToast("Message stored locally; no external email was sent.");
    event.currentTarget.reset();
  });
}

async function route() {
  setLoading(true);
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  updateActiveNavigation(path);
  try {
    if (path === "/") {
      await renderDashboard();
    } else if (LIST_ROUTES[path]) {
      state.search = "";
      state.page = 1;
      state.listFilters = {
        site: "",
        worker: "",
        dateStart: "",
        dateEnd: "",
        order: "newest",
      };
      state.calendarOpen = false;
      await renderList(LIST_ROUTES[path]);
    } else if (path === "/archive") {
      await renderArchive();
    } else if (path === "/company-profile") {
      renderProfile();
    } else if (path === "/change-password") {
      renderChangePassword();
    } else if (path === "/contact-us") {
      renderContact();
    } else {
      app.innerHTML = `
        ${pageHeader("Page not mapped")}
        <section class="card error-card">
          <h2>Local route not implemented yet</h2>
          <p>${escapeHtml(path)}</p>
          <a class="button button-primary" href="/" data-route>Return to Dashboard</a>
        </section>
      `;
      bindRouteLinks();
    }
    app.focus({ preventScroll: true });
  } catch (error) {
    app.innerHTML = `
      ${pageHeader("Local application error")}
      <section class="card error-card">
        <h2>Unable to load this screen</h2>
        <p>${escapeHtml(error.message)}</p>
      </section>
    `;
  } finally {
    setTimeout(() => setLoading(false), 120);
  }
}

function navigate(href) {
  history.pushState({}, "", href);
  closeSidebar();
  route();
}

function closeSidebar() {
  sidebar?.classList.remove("open");
  navOverlay?.classList.remove("open");
  document.body.classList.remove("nav-open");
}

function bindRouteLinks() {
  document.querySelectorAll("[data-route]").forEach((link) => {
    if (link.dataset.bound) return;
    link.dataset.bound = "true";
    link.addEventListener("click", (event) => {
      const href = link.getAttribute("href");
      if (!href || href.startsWith("http")) return;
      event.preventDefault();
      navigate(href);
    });
  });
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-route]");
  if (link && !link.dataset.bound) {
    event.preventDefault();
    navigate(link.getAttribute("href"));
  }
});

document.querySelector("#menu-toggle").addEventListener("click", () => {
  sidebar?.classList.add("open");
  navOverlay?.classList.add("open");
  document.body.classList.add("nav-open");
});

document.querySelector("#sidebar-close")?.addEventListener("click", closeSidebar);
navOverlay?.addEventListener("click", closeSidebar);

document.querySelectorAll(".nav-trigger").forEach((trigger) => {
  trigger.addEventListener("click", () => trigger.closest(".nav-group").classList.toggle("open"));
});

document.querySelector("#account-trigger").addEventListener("click", () => {
  document.querySelector("#account-dropdown").classList.toggle("open");
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeSidebar();
    document.querySelector("#account-dropdown")?.classList.remove("open");
    if (modalRoot.innerHTML) {
      modalRoot.innerHTML = "";
      document.body.classList.remove("modal-open");
    }
  }
});

window.addEventListener("popstate", route);
document.querySelector("#year").textContent = new Date().getFullYear();
bindRouteLinks();
route();
