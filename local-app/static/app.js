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
    viewMode: "worker",
    filterMode: "workers",
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
    allowCreate: false,
    viewMode: "training",
    filterMode: "training",
    columns: [
      ["question", "Question"],
      ["expiry_date", "Snapshot Expiry Indicator", "status"],
    ],
    fields: [{ name: "question", label: "Question", required: true, full: true }],
  },
  "/forms": {
    resource: "forms",
    title: "Forms",
    addLabel: "Add Form",
    allowCreate: false,
    viewMode: "form_definition",
    filterMode: "forms",
    columns: [
      ["name", "Name"],
      ["assigned_sites", "Assigned Sites"],
      ["assigned_roles", "Assigned Roles"],
      ["status", "Status", "status"],
      ["definition", "Structure", "formstructure"],
      ["qr_archive_path", "QR", "qrstate"],
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
    allowCreate: false,
    viewMode: "distribution",
    filterMode: "distributions",
    filterDateKey: "assigned_date",
    filterDateLabel: "Assigned date",
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
    allowCreate: false,
    viewMode: "asset",
    filterMode: "assets",
    columns: [
      ["company", "Company"],
      ["subcontractor", "Subcontractor Name"],
      ["name", "Asset Name"],
      ["asset_id", "Asset ID"],
      ["qr_archive_path", "QR", "qrstate"],
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
    allowCreate: false,
    filterMode: "documents",
    viewMode: "document",
    columns: [
      ["title", "Title"],
      ["company", "Company"],
      ["subcontractor", "Subcontractor"],
      ["file_name", "Original Filename"],
      ["archive_path", "File Type", "filetype"],
      ["archive_path", "Archived File", "archive"],
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
    allowCreate: false,
    viewMode: "induction",
    filterMode: "inductions",
    columns: [
      ["title", "Title"],
      ["site", "Site"],
      ["submissions", "Submissions"],
      ["status", "Status", "status"],
      ["pages", "Pages", "pagecount"],
      ["pages", "Questions", "questioncount"],
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
    allowCreate: false,
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
  const isGa1 = resource === "ga1";
  const isRiskAssessment = resource === "risk_assessment";
  const columns = [
    ["title", "Title"],
    ["company", "Company Name"],
    ["subcontractor", "Subcontractor Name"],
    ["site", "Site Name"],
    ["expiry_date", "Expiry Date"],
    ["expiry_status", "Expiry Status", "status"],
  ];
  if (isGa1) {
    columns.push(["archive_paths", "Documents", "archives"]);
  }
  return {
    resource,
    title,
    addLabel,
    allowCreate: false,
    filterMode: isGa1 ? "ga1" : isRiskAssessment ? "risk_assessment" : "",
    viewMode: isRiskAssessment ? "risk_assessment" : "",
    filterDateKey: isGa1 || isRiskAssessment ? "expiry_date" : "",
    filterDateLabel: isGa1 || isRiskAssessment ? "Expiry date" : "",
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
  auth: {
    enabled: false,
    authenticated: true,
    setupRequired: false,
    user: { name: "Local Administrator", email: "local@kompliance.test", role: "admin" },
    csrfToken: "",
  },
  search: "",
  pageSize: 10,
  page: 1,
  listFilters: {
    site: "",
    worker: "",
    expiryState: "",
    role: "",
    accountStatus: "",
    safePass: "",
    company: "",
    subcontractor: "",
    fileType: "",
    formName: "",
    workflowStatus: "",
    recordStatus: "",
    dateStart: "",
    dateEnd: "",
    order: "newest",
  },
  calendarMonth: new Date().toISOString().slice(0, 7),
  calendarOpen: false,
  currentConfig: null,
  currentRows: [],
};

function defaultListFilters(config = {}) {
  return {
    site: "",
    worker: "",
    expiryState: "",
    role: "",
    accountStatus: "",
    safePass: "",
    company: "",
    subcontractor: "",
    fileType: "",
    formName: "",
    workflowStatus: "",
    recordStatus: "",
    dateStart: "",
    dateEnd: "",
    order: ["ga1", "risk_assessment"].includes(config.filterMode)
      ? "expiry_soonest"
      : config.filterMode === "workers"
        ? "name_asc"
      : config.filterMode === "documents"
          ? "title_asc"
        : ["inductions", "assets", "training", "forms"].includes(config.filterMode)
          ? "title_asc"
        : "newest",
  };
}

async function api(url, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(method !== "GET" && state.auth.csrfToken ? { "X-CSRF-Token": state.auth.csrfToken } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const responseText = await response.text();
    let message = responseText;
    try {
      message = JSON.parse(responseText).error || responseText;
    } catch {}
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json();
}

function canEditLocalRecords() {
  return ["editor", "admin"].includes(state.auth.user?.role || "");
}

function canDeleteLocalRecords() {
  return state.auth.user?.role === "admin";
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

function isImagePath(value) {
  return /\.(?:jpe?g|png|webp)$/i.test(String(value || ""));
}

function fileTypeForPath(value) {
  const match = String(value || "").match(/\.([a-z0-9]+)$/i);
  return match ? match[1].toUpperCase() : "Unknown";
}

function archiveDocumentLink(value) {
  const href = archiveHref(value);
  if (!href) return "";
  const fileName = String(value).replaceAll("\\", "/").split("/").pop();
  const previewAttributes = isPdfPath(value)
    ? `data-pdf-preview data-pdf-name="${escapeHtml(fileName)}"`
    : isImagePath(value)
      ? `data-image-preview data-image-name="${escapeHtml(fileName)}"`
      : "";
  return `
    <a class="document-link" href="${escapeHtml(href)}" target="_blank" rel="noopener"
       ${previewAttributes} title="${isPdfPath(value) || isImagePath(value) ? "Preview" : "Open"} ${escapeHtml(fileName)}">
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

function selectedDateLabel(config = {}) {
  const { dateStart, dateEnd } = state.listFilters;
  const label = config.filterDateLabel || "Submitted date";
  if (!dateStart) return `All ${label.toLowerCase()}s`;
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

function splitWorkerValues(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item && item !== "-");
}

function uniqueWorkerValues(rows, key) {
  return [...new Set(rows.flatMap((row) => splitWorkerValues(row[key])))]
    .filter((value) => !value.endsWith("..."))
    .sort((left, right) => left.localeCompare(right, "en", { sensitivity: "base" }));
}

function expiryStateForRow(row) {
  const expiry = dateValue(row.expiry_date);
  if (!expiry) return "not_applicable";
  const todayText = new Date().toISOString().slice(0, 10);
  const today = dateValue(todayText);
  if (expiry < today) return "expired";
  if (expiry <= today + 30 * 24 * 60 * 60 * 1000) return "due_soon";
  return "active";
}

function expiryStateLabel(value) {
  return {
    active: "Valid",
    due_soon: "Due within 30 days",
    expired: "Expired",
    not_applicable: "No expiry date",
  }[value] || "Unknown";
}

function expiryTimingLabel(value) {
  const expiry = dateValue(value);
  if (!expiry) return "No expiry date";
  const today = dateValue(new Date().toISOString().slice(0, 10));
  const days = Math.round((expiry - today) / (24 * 60 * 60 * 1000));
  if (days < 0) return `Expired ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} ago`;
  if (days === 0) return "Expires today";
  return `Expires in ${days} day${days === 1 ? "" : "s"}`;
}

function applyListFilters(rows, config) {
  if (!config.filterMode) return [...rows];
  const {
    site,
    worker,
    expiryState,
    role,
    accountStatus,
    safePass,
    company,
    subcontractor,
    fileType,
    formName,
    workflowStatus,
    recordStatus,
    dateStart,
    dateEnd,
    order,
  } = state.listFilters;
  const fromValue = dateValue(dateStart);
  const toValue = dateValue(dateEnd || dateStart);
  const dateKey = config.filterDateKey || "submitted_date";
  const filtered = rows.filter(
    (row) => {
      const rowDateValue = dateValue(row[dateKey]);
      if (config.filterMode === "workers") {
        return (
          (!site || splitWorkerValues(row.sites).includes(site)) &&
          (!role || splitWorkerValues(row.roles).includes(role)) &&
          (!accountStatus || row.status === accountStatus) &&
          (!safePass || row.safe_pass_expiry === safePass)
        );
      }
      if (config.filterMode === "documents") {
        const rowFileType = fileTypeForPath(row.archive_path || row.file_name);
        return (
          (!company || row.company === company) &&
          (!subcontractor || row.subcontractor === subcontractor) &&
          (!fileType || rowFileType === fileType)
        );
      }
      if (config.filterMode === "distributions") {
        return (
          (!site || row.sites === site) &&
          (!worker || row.worker === worker) &&
          (!formName || row.form === formName) &&
          (!workflowStatus || row.status === workflowStatus) &&
          (!fromValue || rowDateValue >= fromValue) &&
          (!toValue || rowDateValue <= toValue)
        );
      }
      if (config.filterMode === "inductions") {
        return (
          (!site || row.site === site) &&
          (!recordStatus || row.status === recordStatus)
        );
      }
      if (config.filterMode === "assets") {
        return (
          (!company || row.company === company) &&
          (!subcontractor || row.subcontractor === subcontractor)
        );
      }
      if (config.filterMode === "training") {
        return !recordStatus || row.expiry_date === recordStatus;
      }
      if (config.filterMode === "forms") {
        return !recordStatus || row.status === recordStatus;
      }
      return (
        (!site || row.site === site) &&
        (config.filterMode !== "hsa" || !worker || row.worker === worker) &&
        (!["ga1", "risk_assessment"].includes(config.filterMode) || !expiryState || expiryStateForRow(row) === expiryState) &&
        (config.filterMode !== "risk_assessment" || !company || row.company === company) &&
        (config.filterMode !== "risk_assessment" || !subcontractor || row.subcontractor === subcontractor) &&
        (!fromValue || rowDateValue >= fromValue) &&
        (!toValue || rowDateValue <= toValue)
      );
    },
  );
  return filtered.sort((left, right) => {
    if (config.filterMode === "documents") {
      const comparison = String(left.title || "").localeCompare(String(right.title || ""), "en", {
        sensitivity: "base",
      });
      return order === "title_desc" ? -comparison : comparison;
    }
    if (config.filterMode === "workers") {
      const comparison = String(left.name || "").localeCompare(String(right.name || ""), "en", {
        sensitivity: "base",
      });
      return order === "name_desc" ? -comparison : comparison;
    }
    if (["ga1", "risk_assessment"].includes(config.filterMode)) {
      const leftExpiry = dateValue(left.expiry_date) || Number.MAX_SAFE_INTEGER;
      const rightExpiry = dateValue(right.expiry_date) || Number.MAX_SAFE_INTEGER;
      const difference = leftExpiry - rightExpiry;
      const fallback = Number(left.source_id || left.id) - Number(right.source_id || right.id);
      const comparison = difference || fallback;
      return order === "expiry_latest" ? -comparison : comparison;
    }
    if (config.filterMode === "distributions") {
      const leftAssigned = dateValue(left.assigned_date);
      const rightAssigned = dateValue(right.assigned_date);
      const difference = leftAssigned - rightAssigned;
      const fallback = Number(left.source_id || left.id) - Number(right.source_id || right.id);
      const comparison = difference || fallback;
      return order === "oldest" ? comparison : -comparison;
    }
    if (["inductions", "assets", "training", "forms"].includes(config.filterMode)) {
      const key = config.filterMode === "inductions"
        ? "title"
        : config.filterMode === "training"
          ? "question"
          : "name";
      const comparison = String(left[key] || "").localeCompare(String(right[key] || ""), "en", {
        sensitivity: "base",
      });
      return order === "title_desc" ? -comparison : comparison;
    }
    const difference = dateValue(left.created_at) - dateValue(right.created_at);
    const fallback = Number(left.source_id || left.id) - Number(right.source_id || right.id);
    const comparison = difference || fallback;
    return order === "oldest" ? comparison : -comparison;
  });
}

function renderCell(value, format) {
  if (format === "date") return formatDate(value);
  if (format === "filetype") return `<span class="file-type-badge">${escapeHtml(fileTypeForPath(value))}</span>`;
  if (format === "status") {
    const status = String(value || "Pending");
    return `<span class="status ${escapeHtml(status.toLowerCase().replaceAll(" ", "-"))}">${escapeHtml(status)}</span>`;
  }
  if (format === "pagecount") {
    return String(value?.pages?.length || 0);
  }
  if (format === "questioncount") {
    const pages = Array.isArray(value?.pages) ? value.pages : [];
    return String(pages.reduce((total, page) => total + (page.blocks || []).filter((block) => block.type === "question").length, 0));
  }
  if (format === "formstructure") {
    const sections = Array.isArray(value?.sections) ? value.sections : [];
    const questions = sections.reduce((total, section) => total + (section.questions || []).length, 0);
    return `${sections.length} section${sections.length === 1 ? "" : "s"} · ${questions} question${questions === 1 ? "" : "s"}`;
  }
  if (format === "qrstate") {
    return value
      ? `<span class="qr-state available">Available</span>`
      : `<span class="qr-state unavailable">Not archived</span>`;
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

function openImagePreview(href, fileName) {
  const safeHref = escapeHtml(href);
  const safeName = escapeHtml(fileName || "Archived image");
  modalRoot.innerHTML = `
    <div class="modal-backdrop pdf-preview-backdrop image-preview-backdrop">
      <section class="pdf-preview-modal image-preview-modal" role="dialog" aria-modal="true" aria-labelledby="image-preview-title">
        <header class="pdf-preview-header">
          <div class="pdf-preview-title">
            <span class="pdf-badge image-badge">IMG</span>
            <div>
              <small>Archived compliance image</small>
              <h2 id="image-preview-title">${safeName}</h2>
            </div>
          </div>
          <div class="pdf-preview-actions">
            <a class="button button-secondary" href="${safeHref}" target="_blank" rel="noopener">Open in new tab</a>
            <a class="button button-primary" href="${safeHref}" download="${safeName}">Download image</a>
            <button class="pdf-preview-close" type="button" aria-label="Close image preview">×</button>
          </div>
        </header>
        <div class="image-preview-body">
          <img src="${safeHref}" alt="Preview of ${safeName}" />
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
  modalRoot.querySelector(".image-preview-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("image-preview-backdrop")) close();
  });
  modalRoot.querySelector(".pdf-preview-close").focus();
}

function recordDocumentPaths(record) {
  return [
    ...(Array.isArray(record.archive_paths) ? record.archive_paths : []),
    record.archive_path,
  ].filter((path, index, paths) => path && paths.indexOf(path) === index);
}

function openDocumentSetViewer(record) {
  const paths = recordDocumentPaths(record);
  const files = paths.length
    ? paths
        .map((path, index) => {
          const href = archiveHref(path);
          const fileName = String(path).replaceAll("\\", "/").split("/").pop();
          const kind = isPdfPath(path) ? "PDF" : isImagePath(path) ? "Image" : "File";
          const preview = isPdfPath(path) || isImagePath(path)
            ? `<button class="button button-secondary" type="button" data-set-preview="${escapeHtml(href)}"
                       data-set-file="${escapeHtml(fileName)}" data-set-kind="${kind.toLowerCase()}">Preview</button>`
            : "";
          return `
            <article class="document-set-file">
              <span class="document-set-file-number">${index + 1}</span>
              <div class="document-set-file-copy">
                <small>${kind}</small>
                <strong>${escapeHtml(fileName)}</strong>
              </div>
              <div class="document-set-file-actions">
                ${preview}
                <a class="button button-quiet" href="${escapeHtml(href)}" target="_blank" rel="noopener">Open</a>
                <a class="button button-primary" href="${escapeHtml(href)}" download="${escapeHtml(fileName)}">Download</a>
              </div>
            </article>
          `;
        })
        .join("")
    : `<p class="document-set-empty">No archived files are linked to this record.</p>`;
  modalRoot.innerHTML = `
    <div class="modal-backdrop document-set-backdrop">
      <section class="document-set-modal" role="dialog" aria-modal="true" aria-labelledby="document-set-title">
        <header class="document-set-header">
          <div>
            <small>GA1 document set · read only</small>
            <h2 id="document-set-title">${escapeHtml(record.title || "Untitled document set")}</h2>
          </div>
          <button class="pdf-preview-close" type="button" aria-label="Close document set">×</button>
        </header>
        <div class="document-set-content">
          <dl class="document-set-summary">
            <div><dt>Company</dt><dd>${escapeHtml(record.company || "—")}</dd></div>
            <div><dt>Site</dt><dd>${escapeHtml(record.site || "—")}</dd></div>
            <div><dt>Subcontractor</dt><dd>${escapeHtml(record.subcontractor || "—")}</dd></div>
            <div><dt>Expiry date</dt><dd>${escapeHtml(formatDate(record.expiry_date) || "—")}</dd></div>
            <div><dt>Snapshot status</dt><dd>${escapeHtml(record.expiry_status || "—")}</dd></div>
            <div><dt>Documents</dt><dd>${paths.length}</dd></div>
          </dl>
          <div class="document-set-files">${files}</div>
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
  modalRoot.querySelector(".document-set-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("document-set-backdrop")) close();
  });
  modalRoot.querySelectorAll("[data-set-preview]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.setKind === "pdf") {
        openPdfPreview(button.dataset.setPreview, button.dataset.setFile);
      } else {
        openImagePreview(button.dataset.setPreview, button.dataset.setFile);
      }
    });
  });
  modalRoot.querySelector(".pdf-preview-close").focus();
}

function openSharedDocumentViewer(record) {
  const path = record.archive_path || "";
  const href = archiveHref(path);
  const archivedName = path ? String(path).replaceAll("\\", "/").split("/").pop() : "";
  const displayName = record.file_name || archivedName || "Archived document";
  const fileType = fileTypeForPath(path || displayName);
  const canPreview = isPdfPath(path) || isImagePath(path);
  modalRoot.innerHTML = `
    <div class="modal-backdrop shared-document-backdrop">
      <section class="shared-document-modal" role="dialog" aria-modal="true" aria-labelledby="shared-document-title">
        <header class="shared-document-header">
          <div class="shared-document-heading">
            <span class="shared-document-type">${escapeHtml(fileType)}</span>
            <div>
              <small>Shared document record · read only</small>
              <h2 id="shared-document-title">${escapeHtml(record.title || displayName)}</h2>
            </div>
          </div>
          <button class="pdf-preview-close" type="button" aria-label="Close document details">×</button>
        </header>
        <div class="shared-document-content">
          <div class="shared-document-notice">
            This is an existing migrated document. The source file and record remain unchanged.
          </div>
          <dl class="shared-document-summary">
            <div><dt>Company</dt><dd>${escapeHtml(workerProfileValue(record.company))}</dd></div>
            <div><dt>Subcontractor</dt><dd>${escapeHtml(workerProfileValue(record.subcontractor))}</dd></div>
            <div><dt>Original filename</dt><dd>${escapeHtml(displayName)}</dd></div>
            <div><dt>Archive filename</dt><dd>${escapeHtml(archivedName || "Not available")}</dd></div>
            <div><dt>File type</dt><dd>${escapeHtml(fileType)}</dd></div>
            <div><dt>Source</dt><dd>${escapeHtml(workerProfileValue(record.source))}</dd></div>
          </dl>
          <div class="shared-document-actions">
            ${canPreview && href
              ? `<button class="button button-primary" id="shared-document-preview" type="button">Preview ${escapeHtml(fileType)}</button>`
              : ""}
            ${href
              ? `<a class="button button-secondary" href="${escapeHtml(href)}" target="_blank" rel="noopener">Open in new tab</a>
                 <a class="button button-secondary" href="${escapeHtml(href)}" download="${escapeHtml(displayName)}">Download</a>`
              : ""}
          </div>
          <section class="shared-document-history" aria-labelledby="shared-document-history-title">
            <div class="shared-document-section-heading">
              <span>Version history</span>
              <h3 id="shared-document-history-title">Available source evidence</h3>
            </div>
            <article>
              <span class="version-marker">1</span>
              <div>
                <strong>Migrated source version</strong>
                <small>${escapeHtml(displayName)} · preserved in the authorised local archive</small>
              </div>
              <span class="version-state">Current archived copy</span>
            </article>
            <p>No replacement or earlier-version history was included in the current snapshot.</p>
          </section>
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
  modalRoot.querySelector(".shared-document-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("shared-document-backdrop")) close();
  });
  modalRoot.querySelector("#shared-document-preview")?.addEventListener("click", () => {
    if (isPdfPath(path)) openPdfPreview(href, displayName);
    else openImagePreview(href, displayName);
  });
  modalRoot.querySelector(".pdf-preview-close").focus();
}

function openRiskAssessmentViewer(record) {
  const calculatedState = expiryStateForRow(record);
  modalRoot.innerHTML = `
    <div class="modal-backdrop risk-detail-backdrop">
      <section class="risk-detail-modal" role="dialog" aria-modal="true" aria-labelledby="risk-detail-title">
        <header class="risk-detail-header">
          <div>
            <small>RAMS / Risk Assessment · read only</small>
            <h2 id="risk-detail-title">${escapeHtml(record.title || "Untitled record")}</h2>
            <p>${escapeHtml(record.site || "No site recorded")}</p>
          </div>
          <button class="pdf-preview-close" type="button" aria-label="Close RAMS details">×</button>
        </header>
        <div class="risk-detail-content">
          <div class="risk-status-banner ${calculatedState}">
            <span>${escapeHtml(expiryStateLabel(calculatedState))}</span>
            <strong>${escapeHtml(expiryTimingLabel(record.expiry_date))}</strong>
            <small>Calculated from the stored expiry date as of today.</small>
          </div>
          <dl class="risk-detail-summary">
            <div><dt>Company</dt><dd>${escapeHtml(workerProfileValue(record.company))}</dd></div>
            <div><dt>Subcontractor</dt><dd>${escapeHtml(workerProfileValue(record.subcontractor))}</dd></div>
            <div><dt>Site</dt><dd>${escapeHtml(workerProfileValue(record.site))}</dd></div>
            <div><dt>Expiry date</dt><dd>${escapeHtml(formatDate(record.expiry_date))}</dd></div>
            <div><dt>Calculated status</dt><dd>${escapeHtml(expiryStateLabel(calculatedState))}</dd></div>
            <div><dt>Source status</dt><dd>${escapeHtml(workerProfileValue(record.expiry_status))}</dd></div>
            <div><dt>Source</dt><dd>${escapeHtml(workerProfileValue(record.source))}</dd></div>
            <div><dt>Record ID</dt><dd>${escapeHtml(record.source_id || record.id || "Not available")}</dd></div>
          </dl>
          <section class="risk-attachment-state" aria-labelledby="risk-attachment-title">
            <span class="risk-attachment-icon" aria-hidden="true">!</span>
            <div>
              <h3 id="risk-attachment-title">Archived attachment not included</h3>
              <p>The authorised snapshot contains this RAMS metadata, but no corresponding PDF or image exists in the local archive. No replacement document has been generated.</p>
            </div>
          </section>
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
  modalRoot.querySelector(".risk-detail-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("risk-detail-backdrop")) close();
  });
  modalRoot.querySelector(".pdf-preview-close").focus();
}

function openDistributionViewer(record) {
  const status = String(record.status || "Pending");
  const statusClass = status.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const hasSubmission = Boolean(dateValue(record.submitted_date)) || ["Submitted", "Completed"].includes(status);
  const isCompleted = status === "Completed";
  const detailValue = (value) => {
    const text = String(value || "").trim();
    return text && text !== "-" ? text : "Not recorded in current snapshot";
  };
  const timelineStep = (label, detail, stateClass) => `
    <li class="${stateClass}">
      <span class="distribution-timeline-marker" aria-hidden="true"></span>
      <div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(detail)}</small></div>
    </li>
  `;
  modalRoot.innerHTML = `
    <div class="modal-backdrop distribution-detail-backdrop">
      <section class="distribution-detail-modal" role="dialog" aria-modal="true" aria-labelledby="distribution-detail-title">
        <header class="distribution-detail-header">
          <div>
            <small>Form distribution · read only</small>
            <h2 id="distribution-detail-title">${escapeHtml(record.form || "Unnamed form")}</h2>
            <p>${escapeHtml(record.worker || "No worker recorded")}</p>
          </div>
          <button class="pdf-preview-close" type="button" aria-label="Close distribution details">×</button>
        </header>
        <div class="distribution-detail-content">
          <div class="distribution-status-banner ${escapeHtml(statusClass)}">
            <span>${escapeHtml(status)}</span>
            <div>
              <strong>${hasSubmission ? "A submission is recorded" : "Awaiting worker submission"}</strong>
              <small>This state comes directly from the imported customer snapshot.</small>
            </div>
          </div>
          <dl class="distribution-detail-summary">
            <div><dt>Worker</dt><dd>${escapeHtml(detailValue(record.worker))}</dd></div>
            <div><dt>Assigned form</dt><dd>${escapeHtml(detailValue(record.form))}</dd></div>
            <div><dt>Assigned sites</dt><dd>${escapeHtml(detailValue(record.sites))}</dd></div>
            <div><dt>Current status</dt><dd>${escapeHtml(status)}</dd></div>
            <div><dt>Assigned date</dt><dd>${escapeHtml(displayDate(record.assigned_date) || detailValue(record.assigned_date))}</dd></div>
            <div><dt>Submitted date</dt><dd>${escapeHtml(displayDate(record.submitted_date) || detailValue(record.submitted_date))}</dd></div>
            <div><dt>Score</dt><dd>${escapeHtml(detailValue(record.score))}</dd></div>
            <div><dt>Source record ID</dt><dd>${escapeHtml(record.source_id || record.id || "Not available")}</dd></div>
          </dl>
          <section class="distribution-lifecycle" aria-labelledby="distribution-lifecycle-title">
            <div class="distribution-section-heading">
              <span>Workflow</span>
              <h3 id="distribution-lifecycle-title">Assignment lifecycle</h3>
            </div>
            <ol>
              ${timelineStep("Assigned", displayDate(record.assigned_date) || detailValue(record.assigned_date), "complete")}
              ${timelineStep("Submitted", hasSubmission ? (displayDate(record.submitted_date) || "Recorded without a date") : "Not yet recorded", hasSubmission ? "complete" : "current")}
              ${timelineStep("Completed", isCompleted ? "Marked completed" : "Not yet recorded", isCompleted ? "complete" : "upcoming")}
            </ol>
          </section>
          <section class="distribution-evidence-state" aria-labelledby="distribution-evidence-title">
            <span aria-hidden="true">i</span>
            <div>
              <h3 id="distribution-evidence-title">Submission answers are not included</h3>
              <p>The authorised snapshot contains assignment, date, status and score metadata only. Individual answers, signatures and attachments have not been inferred or generated.</p>
            </div>
          </section>
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
  modalRoot.querySelector(".distribution-detail-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("distribution-detail-backdrop")) close();
  });
  modalRoot.querySelector(".pdf-preview-close").focus();
}

function mountRecordInspector(markup, backdropClass, afterMount) {
  modalRoot.innerHTML = markup;
  document.body.classList.add("modal-open");
  const close = () => {
    modalRoot.innerHTML = "";
    document.body.classList.remove("modal-open");
  };
  modalRoot.querySelector(".pdf-preview-close").addEventListener("click", close);
  modalRoot.querySelector(`.${backdropClass}`).addEventListener("click", (event) => {
    if (event.target.classList.contains(backdropClass)) close();
  });
  afterMount?.(close);
  modalRoot.querySelector(".pdf-preview-close").focus();
}

function inductionStats(record) {
  const pages = Array.isArray(record?.pages?.pages) ? record.pages.pages : [];
  const blocks = pages.flatMap((page) => Array.isArray(page.blocks) ? page.blocks : []);
  return {
    pages,
    questionCount: blocks.filter((block) => block.type === "question").length,
    textCount: blocks.filter((block) => block.type === "text").length,
    imageCount: blocks.reduce((total, block) => total + Number(block.embedded_image_count || 0), 0),
  };
}

function inductionBlockMarkup(block, blockIndex) {
  if (block.type === "question") {
    const options = Array.isArray(block.options) ? block.options : [];
    return `
      <article class="induction-preview-block question-block">
        <div class="preview-block-label"><span>Question ${blockIndex + 1}</span><small>${escapeHtml(String(block.question_type || "Choice").replaceAll("_", " "))}</small></div>
        <h4>${escapeHtml(block.text || "Untitled question")}</h4>
        <ul class="induction-answer-options">
          ${options.map((option) => `
            <li class="${option.correct ? "correct" : ""}">
              <span aria-hidden="true">${option.correct ? "✓" : "○"}</span>
              <strong>${escapeHtml(option.text || "Unnamed option")}</strong>
              ${option.correct ? "<small>Configured correct answer</small>" : ""}
            </li>
          `).join("") || "<li>No answer options were included.</li>"}
        </ul>
      </article>
    `;
  }
  const imageCount = Number(block.embedded_image_count || 0);
  return `
    <article class="induction-preview-block text-block">
      <div class="preview-block-label"><span>Content block ${blockIndex + 1}</span><small>${Number(block.mapped_character_count || String(block.text || "").length).toLocaleString()} mapped characters</small></div>
      <p>${escapeHtml(block.text || "No text was included in this mapped block.")}</p>
      ${imageCount ? `<div class="mapped-media-note"><strong>${imageCount} embedded image${imageCount === 1 ? "" : "s"} referenced</strong><small>The image binaries were not included in the authorised induction snapshot.</small></div>` : ""}
    </article>
  `;
}

function openInductionViewer(record) {
  const stats = inductionStats(record);
  const pageButtons = stats.pages.map((page, index) => `
    <button type="button" class="induction-page-button ${index === 0 ? "active" : ""}" data-induction-page="${index}" aria-pressed="${index === 0}">
      <span>${String(index + 1).padStart(2, "0")}</span>
      <strong>Page ${index + 1}</strong>
      <small>${(page.blocks || []).length} block${(page.blocks || []).length === 1 ? "" : "s"}</small>
    </button>
  `).join("");
  const pagePanels = stats.pages.map((page, index) => `
    <section class="induction-page-panel ${index === 0 ? "active" : ""}" data-induction-panel="${index}" aria-label="Induction page ${index + 1}">
      <header><span>Page ${index + 1} of ${stats.pages.length}</span><strong>${(page.blocks || []).length} mapped content block${(page.blocks || []).length === 1 ? "" : "s"}</strong></header>
      <div class="induction-page-blocks">
        ${(page.blocks || []).map(inductionBlockMarkup).join("") || `<p class="inspector-empty">No mapped content was included for this page.</p>`}
      </div>
    </section>
  `).join("");
  mountRecordInspector(`
    <div class="modal-backdrop record-inspector-backdrop induction-inspector-backdrop">
      <section class="record-inspector-modal induction-inspector-modal" role="dialog" aria-modal="true" aria-labelledby="induction-inspector-title">
        <header class="record-inspector-header">
          <div>
            <small>Site induction · read only</small>
            <h2 id="induction-inspector-title">${escapeHtml(record.title || "Untitled induction")}</h2>
            <p>${escapeHtml(record.site || "No site recorded")} · ${escapeHtml(record.status || "Unknown status")}</p>
          </div>
          <button class="pdf-preview-close" type="button" aria-label="Close induction preview">×</button>
        </header>
        <div class="record-inspector-content induction-inspector-content">
          <section class="inspector-summary-grid induction-summary-grid" aria-label="Induction summary">
            <div><span>Pages</span><strong>${stats.pages.length}</strong></div>
            <div><span>Questions</span><strong>${stats.questionCount}</strong></div>
            <div><span>Text blocks</span><strong>${stats.textCount}</strong></div>
            <div><span>Recorded submissions</span><strong>${Number(record.submissions || 0).toLocaleString()}</strong></div>
          </section>
          <div class="induction-preview-layout">
            <nav class="induction-page-navigation" aria-label="Induction pages">${pageButtons}</nav>
            <div class="induction-page-stage">${pagePanels}</div>
          </div>
          <div class="inspector-disclosure"><strong>Media boundary</strong><span>${stats.imageCount} embedded image references were mapped, but their image files were not included. No replacement media has been generated.</span></div>
        </div>
      </section>
    </div>
  `, "induction-inspector-backdrop", () => {
    modalRoot.querySelectorAll("[data-induction-page]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.dataset.inductionPage;
        modalRoot.querySelectorAll("[data-induction-page]").forEach((candidate) => {
          const active = candidate.dataset.inductionPage === target;
          candidate.classList.toggle("active", active);
          candidate.setAttribute("aria-pressed", String(active));
        });
        modalRoot.querySelectorAll("[data-induction-panel]").forEach((panel) => {
          panel.classList.toggle("active", panel.dataset.inductionPanel === target);
        });
      });
    });
  });
}

function openAssetViewer(record) {
  const qrPath = record.qr_archive_path || "";
  const qrHref = archiveHref(qrPath);
  const qrName = qrPath ? qrPath.replaceAll("\\", "/").split("/").pop() : "";
  mountRecordInspector(`
    <div class="modal-backdrop record-inspector-backdrop asset-inspector-backdrop">
      <section class="record-inspector-modal asset-inspector-modal" role="dialog" aria-modal="true" aria-labelledby="asset-inspector-title">
        <header class="record-inspector-header asset-inspector-header">
          <div><small>Asset register · read only</small><h2 id="asset-inspector-title">${escapeHtml(record.name || "Unnamed asset")}</h2><p>${escapeHtml(record.asset_id || "No asset ID")}</p></div>
          <button class="pdf-preview-close" type="button" aria-label="Close asset details">×</button>
        </header>
        <div class="record-inspector-content asset-inspector-content">
          <dl class="record-inspector-fields">
            <div><dt>Asset ID</dt><dd>${escapeHtml(workerProfileValue(record.asset_id))}</dd></div>
            <div><dt>Asset name</dt><dd>${escapeHtml(workerProfileValue(record.name))}</dd></div>
            <div><dt>Company</dt><dd>${escapeHtml(workerProfileValue(record.company))}</dd></div>
            <div><dt>Subcontractor</dt><dd>${escapeHtml(workerProfileValue(record.subcontractor))}</dd></div>
            <div><dt>Source record ID</dt><dd>${escapeHtml(record.source_id || record.id || "Not available")}</dd></div>
            <div><dt>Source</dt><dd>${escapeHtml(workerProfileValue(record.source))}</dd></div>
          </dl>
          <section class="asset-qr-panel" aria-labelledby="asset-qr-title">
            ${qrHref ? `<img src="${escapeHtml(qrHref)}" alt="Archived QR code for ${escapeHtml(record.name || "asset")}" />` : `<div class="asset-qr-missing">QR unavailable</div>`}
            <div>
              <span>Preserved source QR</span>
              <h3 id="asset-qr-title">${qrHref ? "Archived QR code available" : "No QR was included"}</h3>
              <p>${qrHref ? "This is the original QR image preserved in the authorised source archive." : "No QR image path exists for this record."}</p>
              ${qrHref ? `<div class="inspector-actions"><a class="button button-secondary" href="${escapeHtml(qrHref)}" target="_blank" rel="noopener">Open QR</a><a class="button button-primary" href="${escapeHtml(qrHref)}" download="${escapeHtml(qrName)}">Download QR</a></div>` : ""}
            </div>
          </section>
        </div>
      </section>
    </div>
  `, "asset-inspector-backdrop");
}

function openTrainingViewer(record) {
  const indicator = String(record.expiry_date || "-");
  const indicatorClass = indicator === "Expired" ? "expired" : "not-recorded";
  mountRecordInspector(`
    <div class="modal-backdrop record-inspector-backdrop training-inspector-backdrop">
      <section class="record-inspector-modal training-inspector-modal" role="dialog" aria-modal="true" aria-labelledby="training-inspector-title">
        <header class="record-inspector-header training-inspector-header">
          <div><small>Training catalogue · read only</small><h2 id="training-inspector-title">${escapeHtml(record.question || "Untitled training question")}</h2><p>Customer-configured worker compliance question</p></div>
          <button class="pdf-preview-close" type="button" aria-label="Close training details">×</button>
        </header>
        <div class="record-inspector-content">
          <div class="training-indicator ${indicatorClass}"><span>${escapeHtml(indicator === "-" ? "Not recorded" : indicator)}</span><div><strong>Snapshot expiry indicator</strong><small>This value is stored on the training-question record and is not a worker certificate expiry date.</small></div></div>
          <dl class="record-inspector-fields">
            <div><dt>Question</dt><dd>${escapeHtml(workerProfileValue(record.question))}</dd></div>
            <div><dt>Source indicator</dt><dd>${escapeHtml(indicator === "-" ? "Not recorded" : indicator)}</dd></div>
            <div><dt>Source record ID</dt><dd>${escapeHtml(record.source_id || record.id || "Not available")}</dd></div>
            <div><dt>Source</dt><dd>${escapeHtml(workerProfileValue(record.source))}</dd></div>
          </dl>
          <div class="inspector-disclosure"><strong>Worker evidence not included</strong><span>The snapshot does not contain per-worker answers, certificate expiry dates, or evidence files for this question. These have not been inferred.</span></div>
        </div>
      </section>
    </div>
  `, "training-inspector-backdrop");
}

async function openFormDefinitionViewer(record) {
  const sections = Array.isArray(record?.definition?.sections) ? record.definition.sections : [];
  const questionCount = sections.reduce((total, section) => total + (section.questions || []).length, 0);
  const distributionResult = await api("/api/resources/distributions?limit=5000");
  const linked = (distributionResult.data || []).filter((distribution) => distribution.form === record.name);
  const linkedByStatus = linked.reduce((summary, distribution) => {
    const key = String(distribution.status || "Pending").toLowerCase();
    summary[key] = (summary[key] || 0) + 1;
    return summary;
  }, {});
  const qrHref = archiveHref(record.qr_archive_path || "");
  mountRecordInspector(`
    <div class="modal-backdrop record-inspector-backdrop form-inspector-backdrop">
      <section class="record-inspector-modal form-inspector-modal" role="dialog" aria-modal="true" aria-labelledby="form-inspector-title">
        <header class="record-inspector-header form-inspector-header">
          <div><small>Custom form definition · read only</small><h2 id="form-inspector-title">${escapeHtml(record.name || "Unnamed form")}</h2><p>${escapeHtml(record.status || "Unknown status")} · ${linked.length} linked distribution${linked.length === 1 ? "" : "s"}</p></div>
          <button class="pdf-preview-close" type="button" aria-label="Close form definition">×</button>
        </header>
        <div class="record-inspector-content">
          <section class="inspector-summary-grid form-summary-grid" aria-label="Form definition summary">
            <div><span>Sections</span><strong>${sections.length}</strong></div>
            <div><span>Questions</span><strong>${questionCount}</strong></div>
            <div><span>Pending assignments</span><strong>${Number(linkedByStatus.pending || 0)}</strong></div>
            <div><span>Submitted</span><strong>${Number(linkedByStatus.submitted || 0)}</strong></div>
          </section>
          <dl class="record-inspector-fields">
            <div><dt>Assigned sites</dt><dd>${escapeHtml(workerProfileValue(record.assigned_sites))}</dd></div>
            <div><dt>Assigned roles</dt><dd>${escapeHtml(workerProfileValue(record.assigned_roles))}</dd></div>
            <div><dt>Status</dt><dd>${escapeHtml(workerProfileValue(record.status))}</dd></div>
            <div><dt>Archived QR</dt><dd>${qrHref ? `<a href="${escapeHtml(qrHref)}" target="_blank" rel="noopener">Open preserved QR</a>` : "Not included"}</dd></div>
          </dl>
          <section class="form-definition-sections" aria-label="Form sections">
            ${sections.map((section, sectionIndex) => `
              <article>
                <header><span>${String(sectionIndex + 1).padStart(2, "0")}</span><div><small>Section</small><h3>${escapeHtml(section.name || `Section ${sectionIndex + 1}`)}</h3></div><strong>${(section.questions || []).length} questions</strong></header>
                <ol>${(section.questions || []).map((question) => `<li><span>${escapeHtml(question.type || "Default")}</span><strong>${escapeHtml(question.text || "Untitled question")}</strong></li>`).join("") || "<li>No questions included.</li>"}</ol>
              </article>
            `).join("") || `<p class="inspector-empty">No form sections were included.</p>`}
          </section>
          <div class="inspector-disclosure"><strong>Definition only</strong><span>This preview shows the imported form structure and linked assignment metadata. It does not create assignments or submit responses.</span></div>
        </div>
      </section>
    </div>
  `, "form-inspector-backdrop");
}

function workerInitials(name) {
  return String(name || "Worker")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function workerProfileValue(value) {
  const text = String(value || "").trim();
  return text && text !== "-" ? text : "Not available in current snapshot";
}

async function openWorkerProfile(record) {
  const inductionResult = await api("/api/resources/inductions?limit=5000");
  const assignedSites = splitWorkerValues(record.sites).map((site) => site.toLocaleLowerCase());
  const availableInductions = (inductionResult.data || []).filter((induction) =>
    assignedSites.includes(String(induction.site || "").trim().toLocaleLowerCase()),
  );
  const progressMatch = String(record.induction_status || "").match(/^(\d+)\s*\/\s*(\d+)$/);
  const inductionProgress = progressMatch
    ? `${progressMatch[1]} of ${progressMatch[2]} recorded as complete`
    : workerProfileValue(record.induction_status);
  const profileField = (label, value) => `
    <div class="worker-profile-field">
      <dt>${escapeHtml(label)}</dt>
      <dd>${escapeHtml(workerProfileValue(value))}</dd>
    </div>
  `;
  const complianceCard = (label, value) => {
    const display = workerProfileValue(value);
    const statusClass = String(value || "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-");
    return `
      <div class="worker-compliance-card">
        <span>${escapeHtml(label)}</span>
        <strong class="worker-compliance-value ${escapeHtml(statusClass)}">${escapeHtml(display)}</strong>
      </div>
    `;
  };
  modalRoot.innerHTML = `
    <div class="modal-backdrop worker-profile-backdrop">
      <section class="worker-profile-modal" role="dialog" aria-modal="true" aria-labelledby="worker-profile-title">
        <header class="worker-profile-header">
          <div class="worker-profile-identity">
            <span class="worker-profile-avatar" aria-hidden="true">${escapeHtml(workerInitials(record.name))}</span>
            <div>
              <small>Universal worker profile foundation · read only</small>
              <h2 id="worker-profile-title">${escapeHtml(record.name || "Unnamed worker")}</h2>
              <p>${escapeHtml(workerProfileValue(record.roles))} · ${escapeHtml(workerProfileValue(record.sites))}</p>
            </div>
          </div>
          <button class="pdf-preview-close" type="button" aria-label="Close worker profile">×</button>
        </header>
        <div class="worker-profile-content">
          <div class="worker-profile-notice">
            This profile shows only fields present in the authorised local snapshot. No details have been inferred or generated.
          </div>
          <section class="worker-profile-section" aria-labelledby="worker-contact-heading">
            <div class="worker-profile-section-heading">
              <span>01</span>
              <div><small>Current record</small><h3 id="worker-contact-heading">Identity and contact</h3></div>
            </div>
            <dl class="worker-profile-grid">
              ${profileField("Worker ID", record.worker_id)}
              ${profileField("Email", record.email)}
              ${profileField("Phone", record.phone)}
              ${profileField("Account status", record.status)}
            </dl>
          </section>
          <section class="worker-profile-section" aria-labelledby="worker-placement-heading">
            <div class="worker-profile-section-heading">
              <span>02</span>
              <div><small>Company relationship</small><h3 id="worker-placement-heading">Work placement</h3></div>
            </div>
            <dl class="worker-profile-grid">
              ${profileField("Worker type", record.type)}
              ${profileField("Assigned site", record.sites)}
              ${profileField("Role / trade", record.roles)}
              ${profileField("Subcontractor", record.subcontractor)}
            </dl>
          </section>
          <section class="worker-profile-section" aria-labelledby="worker-compliance-heading">
            <div class="worker-profile-section-heading">
              <span>03</span>
              <div><small>Snapshot indicators</small><h3 id="worker-compliance-heading">Compliance overview</h3></div>
            </div>
            <div class="worker-compliance-grid">
              ${complianceCard("Safe Pass", record.safe_pass_expiry)}
              ${complianceCard("Induction", record.induction_status)}
              ${complianceCard("Training", record.training_status)}
              ${complianceCard("Temporary validity", record.temporary_expiry)}
            </div>
            <dl class="worker-profile-grid worker-profile-grid-compact">
              ${profileField("Temporary valid from", record.temporary_valid_from)}
              ${profileField("Imported source", record.source)}
            </dl>
          </section>
          <section class="worker-profile-section" aria-labelledby="worker-induction-heading">
            <div class="worker-profile-section-heading">
              <span>04</span>
              <div><small>Available site relationships</small><h3 id="worker-induction-heading">Induction readiness</h3></div>
            </div>
            <div class="worker-induction-progress"><span>Snapshot progress</span><strong>${escapeHtml(inductionProgress)}</strong></div>
            <div class="worker-induction-links">
              ${availableInductions.length
                ? availableInductions.map((induction) => `<article><div><strong>${escapeHtml(induction.title || "Untitled induction")}</strong><small>${escapeHtml(induction.site || "No site")} · ${Number(induction.submissions || 0)} recorded submissions</small></div><span>${escapeHtml(induction.status || "Unknown")}</span></article>`).join("")
                : `<p>No induction definition exactly matches the worker's assigned-site text in the current snapshot.</p>`}
            </div>
            <div class="worker-profile-relationship-note">These are exact site-name matches only. The snapshot does not identify which specific induction each worker completed, so no completion has been inferred.</div>
          </section>
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
  modalRoot.querySelector(".worker-profile-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("worker-profile-backdrop")) close();
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
  const [counts, ga1Result, workerResult, riskResult, distributionResult, inductionResult, assetResult, trainingResult, formResult, reminderResult] = await Promise.all([
    api("/api/dashboard"),
    api("/api/resources/ga1?limit=5000"),
    api("/api/resources/workers?limit=5000"),
    api("/api/resources/risk_assessment?limit=5000"),
    api("/api/resources/distributions?limit=5000"),
    api("/api/resources/inductions?limit=5000"),
    api("/api/resources/assets?limit=5000"),
    api("/api/resources/training?limit=5000"),
    api("/api/resources/forms?limit=5000"),
    api("/api/compliance/reminders?days=30"),
  ]);
  const ga1Rows = ga1Result.data || [];
  const workerRows = workerResult.data || [];
  const riskRows = riskResult.data || [];
  const distributionRows = distributionResult.data || [];
  const inductionRows = inductionResult.data || [];
  const assetRows = assetResult.data || [];
  const trainingRows = trainingResult.data || [];
  const formRows = formResult.data || [];
  const expiryCounts = reminderResult.counts || {};
  const inductionSubmissionTotal = inductionRows.reduce((total, row) => total + Number(row.submissions || 0), 0);
  const inductionPageTotal = inductionRows.reduce((total, row) => total + inductionStats(row).pages.length, 0);
  const preservedAssetQrTotal = assetRows.filter((row) => row.qr_archive_path).length;
  const expiredTrainingIndicators = trainingRows.filter((row) => row.expiry_date === "Expired").length;
  const formQuestionTotal = formRows.reduce((total, row) => {
    const sections = Array.isArray(row?.definition?.sections) ? row.definition.sections : [];
    return total + sections.reduce((sectionTotal, section) => sectionTotal + (section.questions || []).length, 0);
  }, 0);
  const ga1ByState = ga1Rows.reduce((summary, row) => {
    const key = expiryStateForRow(row);
    summary[key] = (summary[key] || 0) + 1;
    return summary;
  }, {});
  const safePassExpired = workerRows.filter((row) => row.safe_pass_expiry === "Expired");
  const safePassDueSoon = workerRows.filter((row) => row.safe_pass_expiry === "Expiring Soon");
  const safePassMissing = workerRows.filter((row) => !row.safe_pass_expiry || row.safe_pass_expiry === "-");
  const riskByState = riskRows.reduce((summary, row) => {
    const key = expiryStateForRow(row);
    summary[key] = (summary[key] || 0) + 1;
    return summary;
  }, {});
  const distributionsByStatus = distributionRows.reduce((summary, row) => {
    const key = String(row.status || "Pending").toLowerCase();
    summary[key] = (summary[key] || 0) + 1;
    return summary;
  }, {});
  const ga1AttentionRows = ga1Rows
    .filter((row) => ["due_soon", "expired"].includes(expiryStateForRow(row)))
    .sort((left, right) => {
      const leftState = expiryStateForRow(left);
      const rightState = expiryStateForRow(right);
      if (leftState !== rightState) return leftState === "due_soon" ? -1 : 1;
      const difference = dateValue(left.expiry_date) - dateValue(right.expiry_date);
      return leftState === "expired" ? -difference : difference;
    })
    .slice(0, 6);
  const safePassAttentionRows = [...safePassExpired, ...safePassDueSoon, ...safePassMissing]
    .slice(0, 6);
  const riskAttentionRows = riskRows
    .filter((row) => ["due_soon", "expired"].includes(expiryStateForRow(row)))
    .sort((left, right) => {
      const leftState = expiryStateForRow(left);
      const rightState = expiryStateForRow(right);
      if (leftState !== rightState) return leftState === "due_soon" ? -1 : 1;
      const difference = dateValue(left.expiry_date) - dateValue(right.expiry_date);
      return leftState === "expired" ? -difference : difference;
    })
    .slice(0, 6);
  const ga1AttentionMarkup = ga1AttentionRows.length
    ? ga1AttentionRows
        .map((row) => {
          const stateKey = expiryStateForRow(row);
          return `
            <li>
              <span class="alert-status-dot ${stateKey}" aria-hidden="true"></span>
              <div>
                <strong>${escapeHtml(row.title || "Untitled GA1 set")}</strong>
                <small>${escapeHtml(row.site || "No site")} · ${escapeHtml(expiryTimingLabel(row.expiry_date))}</small>
              </div>
              <span class="alert-state ${stateKey}">${escapeHtml(expiryStateLabel(stateKey))}</span>
            </li>
          `;
        })
        .join("")
    : `<li class="alert-empty">No GA1 expiry issues in the current snapshot.</li>`;
  const safePassAttentionMarkup = safePassAttentionRows.length
    ? safePassAttentionRows
        .map((row) => {
          const rawStatus = row.safe_pass_expiry && row.safe_pass_expiry !== "-"
            ? row.safe_pass_expiry
            : "Not recorded";
          const stateKey = rawStatus === "Expired"
            ? "expired"
            : rawStatus === "Expiring Soon"
              ? "due_soon"
              : "not_applicable";
          return `
            <li>
              <span class="alert-status-dot ${stateKey}" aria-hidden="true"></span>
              <div>
                <strong>${escapeHtml(row.name || "Unnamed worker")}</strong>
                <small>${escapeHtml(row.roles || "No role")} · ${escapeHtml(row.sites || "No site")}</small>
              </div>
              <span class="alert-state ${stateKey}">${escapeHtml(rawStatus)}</span>
            </li>
          `;
        })
        .join("")
    : `<li class="alert-empty">No Safe Pass issues in the current snapshot.</li>`;
  const riskAttentionMarkup = riskAttentionRows.length
    ? riskAttentionRows
        .map((row) => {
          const stateKey = expiryStateForRow(row);
          return `
            <li>
              <span class="alert-status-dot ${stateKey}" aria-hidden="true"></span>
              <div>
                <strong>${escapeHtml(row.title || "Untitled RAMS record")}</strong>
                <small>${escapeHtml(row.site || "No site")} · ${escapeHtml(expiryTimingLabel(row.expiry_date))}</small>
              </div>
              <span class="alert-state ${stateKey}">${escapeHtml(expiryStateLabel(stateKey))}</span>
            </li>
          `;
        })
        .join("")
    : `<li class="alert-empty">No RAMS expiry issues in the current snapshot.</li>`;
  const pendingDistributionRows = distributionRows
    .filter((row) => String(row.status || "Pending") === "Pending")
    .sort((left, right) => dateValue(left.assigned_date) - dateValue(right.assigned_date))
    .slice(0, 6);
  const pendingDistributionMarkup = pendingDistributionRows.length
    ? pendingDistributionRows.map((row) => `
        <li>
          <span class="alert-status-dot due_soon" aria-hidden="true"></span>
          <div>
            <strong>${escapeHtml(row.worker || "Unnamed worker")}</strong>
            <small>${escapeHtml(row.form || "Unnamed form")} · assigned ${escapeHtml(displayDate(row.assigned_date) || "date unavailable")}</small>
          </div>
          <span class="alert-state due_soon">Pending</span>
        </li>
      `).join("")
    : `<li class="alert-empty">No pending form assignments in the current snapshot.</li>`;
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
    <div class="section-heading compliance-section-heading">
      <div><span>Compliance attention</span><strong>Calculated from the current snapshot</strong></div>
      <small>As of ${escapeHtml(displayDate(new Date().toISOString().slice(0, 10)))}</small>
    </div>
    <section class="compliance-summary-grid" aria-label="Compliance summary">
      <a class="compliance-summary-card expired" href="/ga1" data-route>
        <span>GA1 expired</span><strong>${Number(ga1ByState.expired || 0).toLocaleString()}</strong><small>Requires review</small>
      </a>
      <a class="compliance-summary-card due-soon" href="/ga1" data-route>
        <span>GA1 due within 30 days</span><strong>${Number(ga1ByState.due_soon || 0).toLocaleString()}</strong><small>Upcoming expiry</small>
      </a>
      <a class="compliance-summary-card valid" href="/ga1" data-route>
        <span>GA1 valid</span><strong>${Number(ga1ByState.active || 0).toLocaleString()}</strong><small>More than 30 days</small>
      </a>
      <a class="compliance-summary-card expired" href="/workers" data-route>
        <span>Safe Pass expired</span><strong>${safePassExpired.length.toLocaleString()}</strong><small>${safePassDueSoon.length} expiring soon</small>
      </a>
      <a class="compliance-summary-card expired" href="/risk_assessment" data-route>
        <span>RAMS expired</span><strong>${Number(riskByState.expired || 0).toLocaleString()}</strong><small>Requires review</small>
      </a>
      <a class="compliance-summary-card due-soon" href="/risk_assessment" data-route>
        <span>RAMS due within 30 days</span><strong>${Number(riskByState.due_soon || 0).toLocaleString()}</strong><small>${Number(riskByState.active || 0).toLocaleString()} currently valid</small>
      </a>
      <a class="compliance-summary-card due-soon" href="/form/distribution" data-route>
        <span>Form assignments pending</span><strong>${Number(distributionsByStatus.pending || 0).toLocaleString()}</strong><small>Awaiting submission</small>
      </a>
      <a class="compliance-summary-card valid" href="/form/distribution" data-route>
        <span>Forms submitted</span><strong>${Number(distributionsByStatus.submitted || 0).toLocaleString()}</strong><small>Response recorded</small>
      </a>
      <a class="compliance-summary-card valid" href="/form/distribution" data-route>
        <span>Forms completed</span><strong>${Number(distributionsByStatus.completed || 0).toLocaleString()}</strong><small>Workflow completed</small>
      </a>
    </section>
    <section class="compliance-alert-panels">
      <article class="compliance-alert-panel">
        <header>
          <div><span>GA1</span><h3>Priority document expiries</h3></div>
          <a href="/ga1" data-route>View all</a>
        </header>
        <ul>${ga1AttentionMarkup}</ul>
      </article>
      <article class="compliance-alert-panel">
        <header>
          <div><span>Workforce</span><h3>Safe Pass attention</h3></div>
          <a href="/workers" data-route>View all</a>
        </header>
        <ul>${safePassAttentionMarkup}</ul>
      </article>
      <article class="compliance-alert-panel compliance-alert-panel-wide">
        <header>
          <div><span>RAMS / Risk Assessment</span><h3>Priority RAMS expiries</h3></div>
          <a href="/risk_assessment" data-route>View all</a>
        </header>
        <ul>${riskAttentionMarkup}</ul>
      </article>
      <article class="compliance-alert-panel compliance-alert-panel-wide">
        <header>
          <div><span>Custom forms</span><h3>Oldest pending assignments</h3></div>
          <a href="/form/distribution" data-route>View all</a>
        </header>
        <ul>${pendingDistributionMarkup}</ul>
      </article>
    </section>
    <div class="section-heading operations-section-heading">
      <div><span>Operational coverage</span><strong>Real imported structures and evidence</strong></div>
      <small>No generated customer records</small>
    </div>
    <section class="operations-summary-grid" aria-label="Operational data coverage">
      <a class="operations-summary-card" href="/inductions" data-route><span>Induction definitions</span><strong>${inductionRows.length}</strong><small>${inductionPageTotal} mapped pages · ${inductionSubmissionTotal} recorded submissions</small></a>
      <a class="operations-summary-card" href="/appliances" data-route><span>Asset register</span><strong>${assetRows.length}</strong><small>${preservedAssetQrTotal} preserved QR images</small></a>
      <a class="operations-summary-card attention" href="/training" data-route><span>Training catalogue</span><strong>${trainingRows.length}</strong><small>${expiredTrainingIndicators} source expiry indicators</small></a>
      <a class="operations-summary-card" href="/forms" data-route><span>Custom form definitions</span><strong>${formRows.length}</strong><small>${formQuestionTotal} mapped questions</small></a>
      <a class="operations-summary-card attention" href="/compliance" data-route><span>Expiry actions</span><strong>${Number(expiryCounts.overdue || 0) + Number(expiryCounts.due_soon || 0)}</strong><small>${Number(expiryCounts.overdue || 0)} overdue · ${Number(expiryCounts.due_soon || 0)} due within 30 days</small></a>
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
  const siteOptions = config.filterMode === "workers"
    ? uniqueWorkerValues(result.data, "sites")
    : config.filterMode === "distributions"
      ? uniqueValues(result.data, "sites")
      : uniqueValues(result.data, "site");
  const workerOptions = uniqueValues(result.data, "worker");
  const formOptions = config.filterMode === "distributions" ? uniqueValues(result.data, "form") : [];
  const workflowStatusOptions = config.filterMode === "distributions" ? uniqueValues(result.data, "status") : [];
  const roleOptions = config.filterMode === "workers" ? uniqueWorkerValues(result.data, "roles") : [];
  const accountStatusOptions = config.filterMode === "workers" ? uniqueValues(result.data, "status") : [];
  const safePassOptions = config.filterMode === "workers" ? uniqueValues(result.data, "safe_pass_expiry") : [];
  const companyOptions = ["documents", "risk_assessment", "assets"].includes(config.filterMode)
    ? uniqueValues(result.data, "company")
    : [];
  const subcontractorOptions = ["documents", "risk_assessment", "assets"].includes(config.filterMode)
    ? uniqueValues(result.data, "subcontractor")
    : [];
  const recordStatusOptions = ["inductions", "forms"].includes(config.filterMode)
    ? uniqueValues(result.data, "status")
    : config.filterMode === "training"
      ? [...new Set(result.data.map((row) => String(row.expiry_date || "-").trim()))].sort()
      : [];
  const fileTypeOptions = config.filterMode === "documents"
    ? [...new Set(result.data.map((row) => fileTypeForPath(row.archive_path || row.file_name)))].sort()
    : [];

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
          const documentPaths = recordDocumentPaths(row);
          const actionPath =
            documentPaths.find((path) => isPdfPath(path)) || documentPaths[0];
          const actionFileName = actionPath
            ? String(actionPath).replaceAll("\\", "/").split("/").pop()
            : "";
          const viewAction = config.viewMode === "induction"
            ? `
              <button class="button-icon view-document" type="button" data-induction-preview="${row.id}"
                      title="Preview induction" aria-label="Preview induction ${escapeHtml(row.title || "record")}">Preview</button>
            `
            : config.viewMode === "asset"
            ? `
              <button class="button-icon view-document" type="button" data-asset-details="${row.id}"
                      title="View asset and QR" aria-label="View asset ${escapeHtml(row.name || row.asset_id || "record")}">View asset</button>
            `
            : config.viewMode === "training"
            ? `
              <button class="button-icon view-document" type="button" data-training-details="${row.id}"
                      title="View training question" aria-label="View training question ${escapeHtml(row.question || "record")}">View details</button>
            `
            : config.viewMode === "form_definition"
            ? `
              <button class="button-icon view-document" type="button" data-form-definition="${row.id}"
                      title="Preview form definition" aria-label="Preview form ${escapeHtml(row.name || "record")}">Preview form</button>
            `
            : config.viewMode === "distribution"
            ? `
              <button class="button-icon view-document" type="button"
                      data-distribution="${row.id}" title="View assignment details"
                      aria-label="View assignment details for ${escapeHtml(row.worker || "worker")}">
                View details
              </button>
            `
            : config.viewMode === "risk_assessment"
            ? `
              <button class="button-icon view-document" type="button"
                      data-risk-assessment="${row.id}" title="View RAMS details"
                      aria-label="View RAMS details for ${escapeHtml(row.title || "record")}">
                View details
              </button>
            `
            : config.viewMode === "document"
            ? `
              <button class="button-icon view-document" type="button"
                      data-shared-document="${row.id}" title="View document details"
                      aria-label="View document details for ${escapeHtml(row.title || actionFileName || "document")}">
                View details
              </button>
            `
            : config.viewMode === "worker"
            ? `
              <button class="button-icon view-document" type="button"
                      data-worker-profile="${row.id}" title="View worker profile"
                      aria-label="View profile for ${escapeHtml(row.name || "worker")}">
                View profile
              </button>
            `
            : config.resource === "ga1" && documentPaths.length
            ? `
              <button class="button-icon view-document view-document-set" type="button"
                      data-document-set="${row.id}" title="View all archived documents"
                      aria-label="View ${documentPaths.length} archived documents">
                View set (${documentPaths.length})
              </button>
            `
            : actionPath
            ? `
              <a class="button-icon view-document" href="${escapeHtml(archiveHref(actionPath))}"
                 target="_blank" rel="noopener"
                 ${isPdfPath(actionPath) ? `data-pdf-preview data-pdf-name="${escapeHtml(actionFileName)}"` : ""}
                 ${isImagePath(actionPath) ? `data-image-preview data-image-name="${escapeHtml(actionFileName)}"` : ""}
                 title="${isPdfPath(actionPath) || isImagePath(actionPath) ? "Preview document" : "Open document"}"
                 aria-label="${isPdfPath(actionPath) || isImagePath(actionPath) ? "Preview archived document" : "Open archived document"}">
                ${isPdfPath(actionPath) || isImagePath(actionPath) ? "Preview" : "Open"}
              </a>
            `
            : "";
          const mutationActions = row._read_only
            ? `<span class="read-only-badge" title="Imported snapshot records are immutable">Read only</span>`
            : !canEditLocalRecords()
            ? `<span class="read-only-badge" title="Viewer role cannot change local records">Viewer access</span>`
            : `
              <button class="button-icon" data-edit="${row.id}" title="Edit local record">✎</button>
              ${canDeleteLocalRecords() ? `<button class="button-icon danger" data-delete="${row.id}" title="Delete local record">⌫</button>` : ""}
            `;
          return `
            <tr>
              <td>${start + index + 1}</td>
              ${cells}
              <td>
                <div class="actions">
                  ${viewAction}
                  ${mutationActions}
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

  const hsaFilters = `
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
              <strong>${escapeHtml(selectedDateLabel(config))}</strong>
              <span aria-hidden="true">⌄</span>
            </button>
            ${calendarMarkup(config)}
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
      `;
  const ga1Filters = `
        <div class="advanced-filters ga1-filters" aria-label="GA1 document filters">
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
            <span>Expiry status</span>
            <select id="filter-expiry-state">
              <option value="">All statuses</option>
              <option value="active" ${state.listFilters.expiryState === "active" ? "selected" : ""}>Active</option>
              <option value="due_soon" ${state.listFilters.expiryState === "due_soon" ? "selected" : ""}>Due within 30 days</option>
              <option value="expired" ${state.listFilters.expiryState === "expired" ? "selected" : ""}>Expired</option>
              <option value="not_applicable" ${state.listFilters.expiryState === "not_applicable" ? "selected" : ""}>No expiry date</option>
            </select>
          </label>
          <div class="date-range-filter">
            <span class="filter-label">Expiry date</span>
            <button class="date-range-trigger ${state.listFilters.dateStart ? "active" : ""}"
                    id="date-range-trigger" type="button"
                    aria-haspopup="dialog" aria-expanded="${state.calendarOpen}">
              <span aria-hidden="true">▦</span>
              <strong>${escapeHtml(selectedDateLabel(config))}</strong>
              <span aria-hidden="true">⌄</span>
            </button>
            ${calendarMarkup(config)}
          </div>
          <label>
            <span>Expiry order</span>
            <select id="filter-order">
              <option value="expiry_soonest" ${state.listFilters.order === "expiry_soonest" ? "selected" : ""}>Soonest first</option>
              <option value="expiry_latest" ${state.listFilters.order === "expiry_latest" ? "selected" : ""}>Latest first</option>
            </select>
          </label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const riskAssessmentFilters = `
        <div class="advanced-filters risk-assessment-filters" aria-label="RAMS and Risk Assessment filters">
          <label>
            <span>Site</span>
            <select id="filter-site">
              <option value="">All sites</option>
              ${siteOptions.map((site) => `<option value="${escapeHtml(site)}" ${site === state.listFilters.site ? "selected" : ""}>${escapeHtml(site)}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Company</span>
            <select id="filter-company">
              <option value="">All companies</option>
              ${companyOptions.map((company) => `<option value="${escapeHtml(company)}" ${company === state.listFilters.company ? "selected" : ""}>${escapeHtml(company)}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Subcontractor</span>
            <select id="filter-subcontractor">
              <option value="">All subcontractors</option>
              ${subcontractorOptions.map((subcontractor) => `<option value="${escapeHtml(subcontractor)}" ${subcontractor === state.listFilters.subcontractor ? "selected" : ""}>${escapeHtml(subcontractor)}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Expiry status</span>
            <select id="filter-expiry-state">
              <option value="">All statuses</option>
              <option value="active" ${state.listFilters.expiryState === "active" ? "selected" : ""}>Valid</option>
              <option value="due_soon" ${state.listFilters.expiryState === "due_soon" ? "selected" : ""}>Due within 30 days</option>
              <option value="expired" ${state.listFilters.expiryState === "expired" ? "selected" : ""}>Expired</option>
              <option value="not_applicable" ${state.listFilters.expiryState === "not_applicable" ? "selected" : ""}>No expiry date</option>
            </select>
          </label>
          <div class="date-range-filter">
            <span class="filter-label">Expiry date</span>
            <button class="date-range-trigger ${state.listFilters.dateStart ? "active" : ""}"
                    id="date-range-trigger" type="button"
                    aria-haspopup="dialog" aria-expanded="${state.calendarOpen}">
              <span aria-hidden="true">▦</span>
              <strong>${escapeHtml(selectedDateLabel(config))}</strong>
              <span aria-hidden="true">⌄</span>
            </button>
            ${calendarMarkup(config)}
          </div>
          <label>
            <span>Expiry order</span>
            <select id="filter-order">
              <option value="expiry_soonest" ${state.listFilters.order === "expiry_soonest" ? "selected" : ""}>Soonest first</option>
              <option value="expiry_latest" ${state.listFilters.order === "expiry_latest" ? "selected" : ""}>Latest first</option>
            </select>
          </label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const distributionFilters = `
        <div class="advanced-filters distribution-filters" aria-label="Form distribution filters">
          <label>
            <span>Assigned sites</span>
            <select id="filter-site">
              <option value="">All site groups</option>
              ${siteOptions.map((site) => `<option value="${escapeHtml(site)}" ${site === state.listFilters.site ? "selected" : ""}>${escapeHtml(site)}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Worker</span>
            <select id="filter-worker">
              <option value="">All workers</option>
              ${workerOptions.map((worker) => `<option value="${escapeHtml(worker)}" ${worker === state.listFilters.worker ? "selected" : ""}>${escapeHtml(worker)}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Form</span>
            <select id="filter-form-name">
              <option value="">All forms</option>
              ${formOptions.map((formName) => `<option value="${escapeHtml(formName)}" ${formName === state.listFilters.formName ? "selected" : ""}>${escapeHtml(formName)}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Status</span>
            <select id="filter-workflow-status">
              <option value="">All statuses</option>
              ${workflowStatusOptions.map((status) => `<option value="${escapeHtml(status)}" ${status === state.listFilters.workflowStatus ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}
            </select>
          </label>
          <div class="date-range-filter">
            <span class="filter-label">Assigned date</span>
            <button class="date-range-trigger ${state.listFilters.dateStart ? "active" : ""}"
                    id="date-range-trigger" type="button"
                    aria-haspopup="dialog" aria-expanded="${state.calendarOpen}">
              <span aria-hidden="true">◦</span>
              <strong>${escapeHtml(selectedDateLabel(config))}</strong>
              <span aria-hidden="true">⌄</span>
            </button>
            ${calendarMarkup(config)}
          </div>
          <label>
            <span>Assignment order</span>
            <select id="filter-order">
              <option value="newest" ${state.listFilters.order === "newest" ? "selected" : ""}>Newest first</option>
              <option value="oldest" ${state.listFilters.order === "oldest" ? "selected" : ""}>Oldest first</option>
            </select>
          </label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const inductionFilters = `
        <div class="advanced-filters catalog-filters" aria-label="Induction filters">
          <label><span>Site</span><select id="filter-site"><option value="">All sites</option>${siteOptions.map((site) => `<option value="${escapeHtml(site)}" ${site === state.listFilters.site ? "selected" : ""}>${escapeHtml(site)}</option>`).join("")}</select></label>
          <label><span>Status</span><select id="filter-record-status"><option value="">All statuses</option>${recordStatusOptions.map((status) => `<option value="${escapeHtml(status)}" ${status === state.listFilters.recordStatus ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}</select></label>
          <label><span>Title order</span><select id="filter-order"><option value="title_asc" ${state.listFilters.order === "title_asc" ? "selected" : ""}>A to Z</option><option value="title_desc" ${state.listFilters.order === "title_desc" ? "selected" : ""}>Z to A</option></select></label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const assetFilters = `
        <div class="advanced-filters catalog-filters" aria-label="Asset filters">
          <label><span>Company</span><select id="filter-company"><option value="">All companies</option>${companyOptions.map((company) => `<option value="${escapeHtml(company)}" ${company === state.listFilters.company ? "selected" : ""}>${escapeHtml(company)}</option>`).join("")}</select></label>
          <label><span>Subcontractor</span><select id="filter-subcontractor"><option value="">All subcontractors</option>${subcontractorOptions.map((subcontractor) => `<option value="${escapeHtml(subcontractor)}" ${subcontractor === state.listFilters.subcontractor ? "selected" : ""}>${escapeHtml(subcontractor)}</option>`).join("")}</select></label>
          <label><span>Name order</span><select id="filter-order"><option value="title_asc" ${state.listFilters.order === "title_asc" ? "selected" : ""}>A to Z</option><option value="title_desc" ${state.listFilters.order === "title_desc" ? "selected" : ""}>Z to A</option></select></label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const trainingFilters = `
        <div class="advanced-filters catalog-filters" aria-label="Training catalogue filters">
          <label><span>Snapshot indicator</span><select id="filter-record-status"><option value="">All indicators</option>${recordStatusOptions.map((status) => `<option value="${escapeHtml(status)}" ${status === state.listFilters.recordStatus ? "selected" : ""}>${escapeHtml(status === "-" ? "Not recorded" : status)}</option>`).join("")}</select></label>
          <label><span>Question order</span><select id="filter-order"><option value="title_asc" ${state.listFilters.order === "title_asc" ? "selected" : ""}>A to Z</option><option value="title_desc" ${state.listFilters.order === "title_desc" ? "selected" : ""}>Z to A</option></select></label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const formDefinitionFilters = `
        <div class="advanced-filters catalog-filters" aria-label="Custom form filters">
          <label><span>Status</span><select id="filter-record-status"><option value="">All statuses</option>${recordStatusOptions.map((status) => `<option value="${escapeHtml(status)}" ${status === state.listFilters.recordStatus ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}</select></label>
          <label><span>Form order</span><select id="filter-order"><option value="title_asc" ${state.listFilters.order === "title_asc" ? "selected" : ""}>A to Z</option><option value="title_desc" ${state.listFilters.order === "title_desc" ? "selected" : ""}>Z to A</option></select></label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const workerFilters = `
        <div class="advanced-filters worker-list-filters" aria-label="Worker filters">
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
            <span>Role / trade</span>
            <select id="filter-role">
              <option value="">All roles</option>
              ${roleOptions
                .map(
                  (role) =>
                    `<option value="${escapeHtml(role)}" ${role === state.listFilters.role ? "selected" : ""}>${escapeHtml(role)}</option>`,
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>Account status</span>
            <select id="filter-account-status">
              <option value="">All account states</option>
              ${accountStatusOptions
                .map(
                  (status) =>
                    `<option value="${escapeHtml(status)}" ${status === state.listFilters.accountStatus ? "selected" : ""}>${escapeHtml(status)}</option>`,
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>Safe Pass</span>
            <select id="filter-safe-pass">
              <option value="">All Safe Pass states</option>
              ${safePassOptions
                .map(
                  (status) =>
                    `<option value="${escapeHtml(status)}" ${status === state.listFilters.safePass ? "selected" : ""}>${escapeHtml(status)}</option>`,
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>Name order</span>
            <select id="filter-order">
              <option value="name_asc" ${state.listFilters.order === "name_asc" ? "selected" : ""}>A to Z</option>
              <option value="name_desc" ${state.listFilters.order === "name_desc" ? "selected" : ""}>Z to A</option>
            </select>
          </label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const documentFilters = `
        <div class="advanced-filters document-list-filters" aria-label="Document filters">
          <label>
            <span>Company</span>
            <select id="filter-company">
              <option value="">All companies</option>
              ${companyOptions
                .map(
                  (company) =>
                    `<option value="${escapeHtml(company)}" ${company === state.listFilters.company ? "selected" : ""}>${escapeHtml(company)}</option>`,
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>Subcontractor</span>
            <select id="filter-subcontractor">
              <option value="">All subcontractors</option>
              ${subcontractorOptions
                .map(
                  (subcontractor) =>
                    `<option value="${escapeHtml(subcontractor)}" ${subcontractor === state.listFilters.subcontractor ? "selected" : ""}>${escapeHtml(subcontractor)}</option>`,
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>File type</span>
            <select id="filter-file-type">
              <option value="">All file types</option>
              ${fileTypeOptions
                .map(
                  (fileType) =>
                    `<option value="${escapeHtml(fileType)}" ${fileType === state.listFilters.fileType ? "selected" : ""}>${escapeHtml(fileType)}</option>`,
                )
                .join("")}
            </select>
          </label>
          <label>
            <span>Title order</span>
            <select id="filter-order">
              <option value="title_asc" ${state.listFilters.order === "title_asc" ? "selected" : ""}>A to Z</option>
              <option value="title_desc" ${state.listFilters.order === "title_desc" ? "selected" : ""}>Z to A</option>
            </select>
          </label>
          <button class="clear-filters" id="clear-filters" type="button">Clear filters</button>
        </div>
      `;
  const advancedFilters = config.filterMode === "hsa"
    ? hsaFilters
    : config.filterMode === "ga1"
      ? ga1Filters
      : config.filterMode === "risk_assessment"
        ? riskAssessmentFilters
      : config.filterMode === "distributions"
        ? distributionFilters
      : config.filterMode === "inductions"
        ? inductionFilters
      : config.filterMode === "assets"
        ? assetFilters
      : config.filterMode === "training"
        ? trainingFilters
      : config.filterMode === "forms"
        ? formDefinitionFilters
      : config.filterMode === "workers"
        ? workerFilters
        : config.filterMode === "documents"
          ? documentFilters
          : "";

  app.innerHTML = `
    ${pageHeader(
      config.title,
      "",
      config.allowCreate === false || !canEditLocalRecords()
        ? ""
        : `<button class="button button-primary" id="add-record">＋ ${escapeHtml(config.addLabel)}</button>`,
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
  document.querySelectorAll("[data-image-preview]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      openImagePreview(link.getAttribute("href"), link.dataset.imageName);
    });
  });
  document.querySelectorAll("[data-document-set]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.documentSet);
      if (record) openDocumentSetViewer(record);
    });
  });
  document.querySelectorAll("[data-worker-profile]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.workerProfile);
      if (record) openWorkerProfile(record);
    });
  });
  document.querySelectorAll("[data-shared-document]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.sharedDocument);
      if (record) openSharedDocumentViewer(record);
    });
  });
  document.querySelectorAll("[data-risk-assessment]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.riskAssessment);
      if (record) openRiskAssessmentViewer(record);
    });
  });
  document.querySelectorAll("[data-distribution]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.distribution);
      if (record) openDistributionViewer(record);
    });
  });
  document.querySelectorAll("[data-induction-preview]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.inductionPreview);
      if (record) openInductionViewer(record);
    });
  });
  document.querySelectorAll("[data-asset-details]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.assetDetails);
      if (record) openAssetViewer(record);
    });
  });
  document.querySelectorAll("[data-training-details]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.trainingDetails);
      if (record) openTrainingViewer(record);
    });
  });
  document.querySelectorAll("[data-form-definition]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = state.currentRows.find((row) => String(row.id) === button.dataset.formDefinition);
      if (record) openFormDefinitionViewer(record);
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
  [
    "site",
    "worker",
    "expiry-state",
    "role",
    "account-status",
    "safe-pass",
    "company",
    "subcontractor",
    "file-type",
    "form-name",
    "workflow-status",
    "record-status",
    "order",
  ].forEach((filterName) => {
    document.querySelector(`#filter-${filterName}`)?.addEventListener("change", async (event) => {
      const stateKey = {
        "expiry-state": "expiryState",
        "account-status": "accountStatus",
        "safe-pass": "safePass",
        "file-type": "fileType",
        "form-name": "formName",
        "workflow-status": "workflowStatus",
        "record-status": "recordStatus",
      }[filterName] || filterName;
      state.listFilters[stateKey] = event.target.value;
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
    state.listFilters = defaultListFilters(config);
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
  const user = state.auth.user || {};
  app.innerHTML = `
    ${pageHeader("My Profile")}
    <section class="card form-card">
      <form id="profile-form">
        <div class="form-grid">
          ${[
            { name: "company_name", label: "Company Name", required: true, value: "Local Company" },
            { name: "email", label: "Email", type: "email", required: true, value: user.email || "local@kompliance.test" },
            { name: "admin_name", label: "Company Admin Name", required: true, value: user.name || "Local Administrator" },
            { name: "admin_email", label: "Company Admin Email", type: "email", value: user.email || "local@kompliance.test" },
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
  document.querySelector("#password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (form.get("new") !== form.get("confirm")) {
      showToast("New passwords do not match.", "error");
      return;
    }
    if (!state.auth.enabled) {
      event.currentTarget.reset();
      showToast("Application authentication is disabled in this local process.");
      return;
    }
    try {
      const result = await api("/api/auth/password", {
        method: "POST",
        body: JSON.stringify({ current: form.get("current"), new: form.get("new") }),
      });
      state.auth.csrfToken = result.csrf_token || state.auth.csrfToken;
      event.currentTarget.reset();
      showToast("Password changed securely.");
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}

async function renderAuditLog() {
  const result = await api("/api/audit?limit=250");
  const rows = result.data || [];
  app.innerHTML = `
    ${pageHeader("Audit log", "Local security and data-change events")}
    <section class="card table-card">
      <div class="audit-summary"><strong>${rows.length.toLocaleString()}</strong><span>Most recent recorded events</span></div>
      <div class="table-scroll">
        <table class="data-table">
          <thead><tr><th>#</th><th>Date</th><th>Actor</th><th>Action</th><th>Resource</th><th>Record</th><th>Summary</th></tr></thead>
          <tbody>${rows.length ? rows.map((row, index) => `<tr><td>${index + 1}</td><td>${escapeHtml(displayDate(row.created_at) || row.created_at)}</td><td>${escapeHtml(row.actor)}</td><td><span class="status">${escapeHtml(row.action)}</span></td><td>${escapeHtml(row.resource)}</td><td>${escapeHtml(row.record_id || "—")}</td><td>${escapeHtml(row.summary)}</td></tr>`).join("") : `<tr><td class="table-empty" colspan="7">No audit events recorded yet.</td></tr>`}</tbody>
        </table>
      </div>
    </section>
  `;
}

async function renderUserManagement() {
  const result = await api("/api/users");
  const users = result.data || [];
  app.innerHTML = `
    ${pageHeader("Access management", "Application accounts and role permissions")}
    <div class="security-role-grid">
      <article><span>Viewer</span><strong>Read-only access</strong><small>Can view protected and local records.</small></article>
      <article><span>Editor</span><strong>Local workflow access</strong><small>Can create and update local-only records.</small></article>
      <article><span>Administrator</span><strong>Security ownership</strong><small>Can manage users, delete local records and review audit events.</small></article>
    </div>
    <section class="card table-card">
      <div class="table-scroll"><table class="data-table"><thead><tr><th>#</th><th>Name</th><th>Email</th><th>Role</th><th>State</th><th>Sessions</th><th>Security</th><th>Actions</th></tr></thead><tbody>${users.map((user, index) => `<tr><td>${index + 1}</td><td><input class="user-inline-name" data-user-name="${user.id}" value="${escapeHtml(user.name)}" /></td><td>${escapeHtml(user.email)}</td><td><select data-user-role="${user.id}">${["viewer", "editor", "admin"].map((role) => `<option ${user.role === role ? "selected" : ""}>${role}</option>`).join("")}</select></td><td><label class="toggle-label"><input type="checkbox" data-user-active="${user.id}" ${user.active ? "checked" : ""} /> Active</label></td><td>${Number(user.session_count || 0)}</td><td>${user.locked_until ? `Locked until ${escapeHtml(displayDate(user.locked_until) || user.locked_until)}` : `${Number(user.failed_attempts || 0)} failed`}</td><td><div class="user-actions"><button type="button" data-save-user="${user.id}">Save</button><button type="button" data-revoke-user="${user.id}">Sign out all</button><button type="button" data-reset-user="${user.id}">Reset link</button></div></td></tr>`).join("")}</tbody></table></div>
    </section>
    <section class="card form-card compact-form-card">
      <div class="local-section-heading"><span>Administrator action</span><h2>Create an application account</h2><p>The password is stored only as a PBKDF2 hash.</p></div>
      <form id="create-user-form"><div class="form-grid">
        ${fieldMarkup({ name: "name", label: "Name", required: true })}
        ${fieldMarkup({ name: "email", label: "Email", type: "email", required: true })}
        ${fieldMarkup({ name: "role", label: "Role", type: "select", options: ["viewer", "editor", "admin"], required: true })}
        ${fieldMarkup({ name: "password", label: "Temporary password (12+ characters)", type: "password", required: true })}
      </div><div class="form-actions"><button class="button button-primary" type="submit">Create account</button></div></form>
    </section>
  `;
  document.querySelector("#create-user-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      await api("/api/users", { method: "POST", body: JSON.stringify(values) });
      showToast("Application account created.");
      await renderUserManagement();
    } catch (error) {
      showToast(error.message, "error");
    }
  });
  document.querySelectorAll("[data-save-user]").forEach((button) => button.addEventListener("click", async () => {
    const id = button.dataset.saveUser;
    try {
      await api(`/api/users/${id}`, { method: "PUT", body: JSON.stringify({ name: document.querySelector(`[data-user-name='${id}']`).value, role: document.querySelector(`[data-user-role='${id}']`).value, active: document.querySelector(`[data-user-active='${id}']`).checked }) });
      showToast("Account security settings updated.");
      await renderUserManagement();
    } catch (error) { showToast(error.message, "error"); }
  }));
  document.querySelectorAll("[data-revoke-user]").forEach((button) => button.addEventListener("click", async () => {
    try { await api(`/api/users/${button.dataset.revokeUser}/revoke-sessions`, { method: "POST", body: "{}" }); showToast("All sessions revoked for this account."); await renderUserManagement(); } catch (error) { showToast(error.message, "error"); }
  }));
  document.querySelectorAll("[data-reset-user]").forEach((button) => button.addEventListener("click", async () => {
    try {
      const result = await api(`/api/users/${button.dataset.resetUser}/reset-link`, { method: "POST", body: "{}" });
      try {
        await navigator.clipboard.writeText(result.reset_url);
        showToast("Secure reset link copied. It expires in 30 minutes.");
      } catch {
        window.prompt("Copy this secure reset link. It expires in 30 minutes:", result.reset_url);
      }
    } catch (error) { showToast(error.message, "error"); }
  }));
}

function localSnapshotDate() {
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date());
}

async function renderLocalWorkflows() {
  const [workerResult, formResult, inductionResult, distributionResult, uploadResult, completionResult, submissionResult] = await Promise.all([
    api("/api/resources/workers?limit=5000"),
    api("/api/resources/forms?limit=5000"),
    api("/api/resources/inductions?limit=5000"),
    api("/api/resources/distributions?limit=5000"),
    api("/api/resources/local_uploads?limit=5000"),
    api("/api/resources/local_induction_completions?limit=5000"),
    api("/api/resources/local_submissions?limit=5000"),
  ]);
  const workers = workerResult.data || [];
  const forms = formResult.data || [];
  const inductions = inductionResult.data || [];
  const localDistributions = (distributionResult.data || []).filter((row) => !row._read_only && row.local_only);
  const uploads = uploadResult.data || [];
  const completions = completionResult.data || [];
  const submissions = submissionResult.data || [];
  const editable = canEditLocalRecords();
  const workerOptions = workers.map((worker) => `<option value="${escapeHtml(worker.name)}">${escapeHtml(worker.name)} · ${escapeHtml(worker.sites || "No site")}</option>`).join("");
  app.innerHTML = `
    ${pageHeader("Controlled local workflows", "New activity stays inside this clone and never writes to the imported source")}
    <div class="local-workflow-boundary"><strong>Isolation boundary</strong><span>Imported customer records remain immutable. Every action below creates separately marked local-only data and is written to the audit log.</span></div>
    ${editable ? "" : `<div class="worker-profile-notice">Your Viewer role can inspect local workflow history but cannot create or change records.</div>`}
    <section class="local-workflow-grid">
      <article class="card workflow-card">
        <div class="local-section-heading"><span>Documents</span><h2>Upload a local version</h2><p>PDF, office, CSV and image files up to 10 MB.</p></div>
        <form id="local-upload-form"><label><span>Document title</span><input name="title" required ${editable ? "" : "disabled"} /></label><label><span>File</span><input name="file" type="file" accept=".pdf,.csv,.xls,.xlsx,.doc,.docx,.png,.jpg,.jpeg" required ${editable ? "" : "disabled"} /></label><button class="button button-primary" ${editable ? "" : "disabled"}>Upload locally</button></form>
        <div class="workflow-history"><strong>${uploads.length} local version${uploads.length === 1 ? "" : "s"}</strong>${uploads.slice(0, 5).map((row) => `<a href="/local-files/uploads/${encodeURIComponent(row.stored_name)}" target="_blank" rel="noopener"><span>v${row.version}</span><div><strong>${escapeHtml(row.title)}</strong><small>${escapeHtml(row.original_name)} · ${formatBytes(row.size)}</small></div></a>`).join("") || `<p>No local uploads yet.</p>`}</div>
      </article>
      <article class="card workflow-card">
        <div class="local-section-heading"><span>Forms</span><h2>Create a local assignment</h2><p>Links a real definition to a worker without contacting production.</p></div>
        <form id="local-assignment-form"><label><span>Worker</span><select name="worker" required ${editable ? "" : "disabled"}>${workerOptions}</select></label><label><span>Form</span><select name="form" required ${editable ? "" : "disabled"}>${forms.map((form) => `<option value="${escapeHtml(form.name)}">${escapeHtml(form.name)}</option>`).join("")}</select></label><label><span>Site reference</span><input name="sites" required ${editable ? "" : "disabled"} /></label><button class="button button-primary" ${editable ? "" : "disabled"}>Create local assignment</button></form>
        <div class="workflow-history"><strong>${localDistributions.length} local assignment${localDistributions.length === 1 ? "" : "s"}</strong>${localDistributions.slice(0, 5).map((row) => `<div class="workflow-history-row"><span>${escapeHtml(row.status)}</span><div><strong>${escapeHtml(row.worker)}</strong><small>${escapeHtml(row.form)}</small></div></div>`).join("") || `<p>No local assignments yet.</p>`}</div>
      </article>
      <article class="card workflow-card">
        <div class="local-section-heading"><span>Submissions</span><h2>Record a local response</h2><p>Available only for assignments created in this local workspace.</p></div>
        <form id="local-submission-form"><label><span>Local assignment</span><select name="distribution_id" required ${editable && localDistributions.length ? "" : "disabled"}>${localDistributions.map((row) => `<option value="${row.id}">${escapeHtml(row.worker)} · ${escapeHtml(row.form)}</option>`).join("")}</select></label><label><span>Response notes / JSON</span><textarea name="answers" required ${editable && localDistributions.length ? "" : "disabled"}></textarea></label><label><span>Score (optional)</span><input name="score" placeholder="e.g. 100 %" ${editable && localDistributions.length ? "" : "disabled"} /></label><button class="button button-primary" ${editable && localDistributions.length ? "" : "disabled"}>Record submission</button></form>
        <div class="workflow-history"><strong>${submissions.length} local submission${submissions.length === 1 ? "" : "s"}</strong>${submissions.slice(0, 5).map((row) => `<div class="workflow-history-row"><span>${escapeHtml(row.score || "—")}</span><div><strong>${escapeHtml(row.worker)}</strong><small>${escapeHtml(row.form)} · ${escapeHtml(row.submitted_date)}</small></div></div>`).join("") || `<p>No local submissions yet.</p>`}</div>
      </article>
      <article class="card workflow-card">
        <div class="local-section-heading"><span>Inductions</span><h2>Record completion and certificate</h2><p>Creates a local PDF certificate with an audit event.</p></div>
        <form id="local-certificate-form"><label><span>Worker</span><select name="worker" required ${editable ? "" : "disabled"}>${workerOptions}</select></label><label><span>Induction</span><select name="induction" required ${editable ? "" : "disabled"}>${inductions.map((induction) => `<option value="${escapeHtml(induction.title)}" data-site="${escapeHtml(induction.site)}">${escapeHtml(induction.title)}</option>`).join("")}</select></label><button class="button button-primary" ${editable ? "" : "disabled"}>Generate local certificate</button></form>
        <div class="workflow-history"><strong>${completions.length} local certificate${completions.length === 1 ? "" : "s"}</strong>${completions.slice(0, 5).map((row) => `<a href="/local-files/certificates/${encodeURIComponent(row.certificate_file)}" target="_blank" rel="noopener"><span>PDF</span><div><strong>${escapeHtml(row.worker)}</strong><small>${escapeHtml(row.induction)}</small></div></a>`).join("") || `<p>No local certificates yet.</p>`}</div>
      </article>
    </section>
  `;
  if (!editable) return;
  document.querySelector("#local-upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    try {
      const response = await fetch("/api/local/upload", { method: "POST", headers: { "Content-Type": file.type || "application/octet-stream", "X-CSRF-Token": state.auth.csrfToken, "X-Upload-Title": encodeURIComponent(form.get("title")), "X-File-Name": encodeURIComponent(file.name) }, body: file });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Upload failed");
      showToast("Local document version uploaded.");
      await renderLocalWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelector("#local-assignment-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      await api("/api/resources/distributions", { method: "POST", body: JSON.stringify({ ...values, assigned_date: localSnapshotDate(), submitted_date: "-", score: "-", status: "Pending", source: "local controlled workspace", local_only: true }) });
      showToast("Local form assignment created.");
      await renderLocalWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelector("#local-submission-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    const distribution = localDistributions.find((row) => String(row.id) === String(values.distribution_id));
    if (!distribution) return;
    const submittedDate = localSnapshotDate();
    try {
      await api("/api/resources/local_submissions", { method: "POST", body: JSON.stringify({ distribution_id: distribution.id, worker: distribution.worker, form: distribution.form, answers: values.answers, score: values.score || "-", submitted_date: submittedDate, source: "local controlled workspace", local_only: true }) });
      await api(`/api/resources/distributions/${distribution.id}`, { method: "PUT", body: JSON.stringify({ ...distribution, status: "Submitted", submitted_date: submittedDate, score: values.score || "-" }) });
      showToast("Local submission recorded.");
      await renderLocalWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelector("#local-certificate-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const inductionSelect = event.currentTarget.elements.induction;
    try {
      await api("/api/local/certificate", { method: "POST", body: JSON.stringify({ worker: form.get("worker"), induction: form.get("induction"), site: inductionSelect.selectedOptions[0]?.dataset.site || "" }) });
      showToast("Local induction certificate generated.");
      await renderLocalWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  });
}

let selectedPilotAssignmentId = null;

function flattenFormQuestions(formRecord) {
  return (formRecord?.definition?.sections || []).flatMap((section, sectionIndex) =>
    (section.questions || []).map((question, questionIndex) => ({
      ...question,
      section: section.name || `Section ${sectionIndex + 1}`,
      key: `s${sectionIndex}q${questionIndex}`,
    })),
  );
}

function pilotQuestionMarkup(question, existingValue = "", disabled = false) {
  const name = `answer_${question.key}`;
  const safeValue = escapeHtml(existingValue || "");
  const disabledAttribute = disabled ? "disabled" : "";
  let control;
  if (question.type === "Date") {
    control = `<input type="date" name="${name}" value="${safeValue}" ${disabledAttribute} />`;
  } else if (question.type === "Time") {
    control = `<input type="time" name="${name}" value="${safeValue}" ${disabledAttribute} />`;
  } else if (question.type === "Date Time") {
    control = `<input type="datetime-local" name="${name}" value="${safeValue}" ${disabledAttribute} />`;
  } else if (question.type === "Default") {
    control = `<select name="${name}" ${disabledAttribute}><option value="">Select</option>${["Yes", "No", "N/A"].map((option) => `<option ${existingValue === option ? "selected" : ""}>${option}</option>`).join("")}</select>`;
  } else if (question.type === "Sign") {
    control = disabled
      ? `<div class="signature-readout">${existingValue ? "Captured signature" : "No signature"}</div>`
      : `<div class="signature-pad" data-signature-pad><canvas width="720" height="180" aria-label="Signature pad"></canvas><input type="hidden" name="${name}" value="${safeValue}" /><button class="button button-secondary signature-clear" type="button">Clear</button></div>`;
  } else if (question.type === "Textbox") {
    control = `<textarea name="${name}" rows="3" ${disabledAttribute}>${safeValue}</textarea>`;
  } else {
    control = `<input name="${name}" value="${safeValue}" ${disabledAttribute} />`;
  }
  return `<label class="pilot-question"><span>${escapeHtml(question.text || "Question")} <b>Required</b></span><small>${escapeHtml(question.type || "Text")} · ${escapeHtml(question.section)}</small>${control}</label>`;
}

function bindSignaturePads() {
  document.querySelectorAll("[data-signature-pad]").forEach((pad) => {
    const canvas = pad.querySelector("canvas");
    const input = pad.querySelector("input[type='hidden']");
    const context = canvas.getContext("2d");
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = 3;
    context.strokeStyle = "#12395a";
    if (input.value) {
      const image = new Image();
      image.onload = () => context.drawImage(image, 0, 0, canvas.width, canvas.height);
      image.src = input.value;
    }
    let drawing = false;
    const point = (event) => {
      const rectangle = canvas.getBoundingClientRect();
      return {
        x: (event.clientX - rectangle.left) * (canvas.width / rectangle.width),
        y: (event.clientY - rectangle.top) * (canvas.height / rectangle.height),
      };
    };
    canvas.addEventListener("pointerdown", (event) => {
      drawing = true;
      canvas.setPointerCapture(event.pointerId);
      const current = point(event);
      context.beginPath();
      context.moveTo(current.x, current.y);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!drawing) return;
      const current = point(event);
      context.lineTo(current.x, current.y);
      context.stroke();
    });
    const finish = () => {
      if (!drawing) return;
      drawing = false;
      input.value = canvas.toDataURL("image/png");
    };
    canvas.addEventListener("pointerup", finish);
    canvas.addEventListener("pointercancel", finish);
    pad.querySelector(".signature-clear").addEventListener("click", () => {
      context.clearRect(0, 0, canvas.width, canvas.height);
      input.value = "";
    });
  });
}

async function renderPilotWorkflows() {
  const [workerResult, formResult, inductionResult, distributionResult, uploadResult, completionResult, submissionResult, evidenceResult] = await Promise.all([
    api("/api/resources/workers?limit=5000"),
    api("/api/resources/forms?limit=5000"),
    api("/api/resources/inductions?limit=5000"),
    api("/api/resources/distributions?limit=5000"),
    api("/api/resources/local_uploads?limit=5000"),
    api("/api/resources/local_induction_completions?limit=5000"),
    api("/api/resources/local_submissions?limit=5000"),
    api("/api/resources/local_evidence?limit=5000"),
  ]);
  const workers = workerResult.data || [];
  const forms = formResult.data || [];
  const inductions = inductionResult.data || [];
  const localDistributions = (distributionResult.data || []).filter((row) => !row._read_only && row.local_only);
  const uploads = uploadResult.data || [];
  const completions = completionResult.data || [];
  const submissions = submissionResult.data || [];
  const evidence = evidenceResult.data || [];
  const editable = canEditLocalRecords();
  if (!selectedPilotAssignmentId && localDistributions.length) selectedPilotAssignmentId = String(localDistributions[0].id);
  const selectedDistribution = localDistributions.find((row) => String(row.id) === String(selectedPilotAssignmentId));
  const selectedForm = forms.find((row) => String(row.name || "").toLowerCase() === String(selectedDistribution?.form || "").toLowerCase());
  const selectedSubmission = submissions.find((row) => String(row.distribution_id) === String(selectedDistribution?.id));
  const selectedEvidence = evidence.filter((row) => String(row.distribution_id) === String(selectedDistribution?.id));
  const existingAnswers = Object.fromEntries((selectedSubmission?.answers || []).map((answer) => [answer.key, answer.value]));
  const formQuestions = flattenFormQuestions(selectedForm);
  const submitted = selectedSubmission?.status === "Submitted";
  const workerOptions = workers.map((worker) => `<option value="${escapeHtml(worker.name)}">${escapeHtml(worker.name)} · ${escapeHtml(worker.sites || "No site")}</option>`).join("");
  const assignmentOptions = localDistributions.map((row) => `<option value="${row.id}" ${String(row.id) === String(selectedPilotAssignmentId) ? "selected" : ""}>${escapeHtml(row.worker)} · ${escapeHtml(row.form)} · ${escapeHtml(row.status)}</option>`).join("");
  app.innerHTML = `
    ${pageHeader("Controlled local workflows", "Complete forms, evidence and verified certificates without changing imported records")}
    <div class="local-workflow-boundary"><strong>Isolation boundary</strong><span>Every action on this page creates separately marked local-only data and an audit event. Imported customer records remain immutable.</span></div>
    ${editable ? "" : `<div class="worker-profile-notice">Your Viewer role can inspect history but cannot create or change records.</div>`}
    <section class="local-workflow-grid pilot-workflow-grid">
      <article class="card workflow-card">
        <div class="local-section-heading"><span>Assignments</span><h2>Create a local form assignment</h2><p>Uses an imported form definition without editing it.</p></div>
        <form id="pilot-assignment-form"><label><span>Worker</span><select name="worker" required ${editable ? "" : "disabled"}>${workerOptions}</select></label><label><span>Form</span><select name="form" required ${editable ? "" : "disabled"}>${forms.map((form) => `<option>${escapeHtml(form.name)}</option>`).join("")}</select></label><label><span>Site reference</span><input name="sites" required ${editable ? "" : "disabled"} /></label><button class="button button-primary" ${editable ? "" : "disabled"}>Create assignment</button></form>
        <div class="workflow-history"><strong>${localDistributions.length} local assignment${localDistributions.length === 1 ? "" : "s"}</strong>${localDistributions.slice(0, 6).map((row) => `<div class="workflow-history-row"><span>${escapeHtml(row.status)}</span><div><strong>${escapeHtml(row.worker)}</strong><small>${escapeHtml(row.form)}</small></div></div>`).join("") || `<p>No local assignments yet.</p>`}</div>
      </article>
      <article class="card workflow-card">
        <div class="local-section-heading"><span>Documents</span><h2>Versioned document upload</h2><p>PDF, office, CSV and image files up to 10 MB.</p></div>
        <form id="pilot-upload-form"><label><span>Document title</span><input name="title" required ${editable ? "" : "disabled"} /></label><label><span>File</span><input name="file" type="file" accept=".pdf,.csv,.xls,.xlsx,.doc,.docx,.png,.jpg,.jpeg" required ${editable ? "" : "disabled"} /></label><button class="button button-primary" ${editable ? "" : "disabled"}>Upload version</button></form>
        <div class="workflow-history"><strong>${uploads.length} local version${uploads.length === 1 ? "" : "s"}</strong>${uploads.slice(0, 6).map((row) => `<a href="/local-files/uploads/${encodeURIComponent(row.stored_name)}" target="_blank" rel="noopener"><span>v${row.version}</span><div><strong>${escapeHtml(row.title)}</strong><small>${escapeHtml(row.original_name)} · ${formatBytes(row.size)}</small></div></a>`).join("") || `<p>No uploads yet.</p>`}</div>
      </article>
    </section>
    <section class="card pilot-submission-card">
      <div class="local-section-heading"><span>Rich submission</span><h2>Complete, save and submit a real form</h2><p>Drafts may be incomplete. Final submission validates every field and creates a PDF report.</p></div>
      <label class="assignment-picker"><span>Local assignment</span><select id="pilot-assignment-picker" ${localDistributions.length ? "" : "disabled"}>${assignmentOptions}</select></label>
      ${selectedDistribution && selectedForm ? `
        <div class="submission-context"><div><span>Worker</span><strong>${escapeHtml(selectedDistribution.worker)}</strong></div><div><span>Form</span><strong>${escapeHtml(selectedDistribution.form)}</strong></div><div><span>Status</span><strong>${escapeHtml(selectedSubmission?.status || selectedDistribution.status)}</strong></div><div><span>Questions</span><strong>${formQuestions.length}</strong></div></div>
        <form id="pilot-submission-form" data-submission-id="${selectedSubmission?.id || ""}"><div class="pilot-question-grid">${formQuestions.map((question) => pilotQuestionMarkup(question, existingAnswers[question.key], submitted || !editable)).join("")}</div>
        <div class="evidence-panel"><div><strong>Supporting evidence</strong><small>${selectedEvidence.length} attached file${selectedEvidence.length === 1 ? "" : "s"}</small></div>${selectedEvidence.map((row) => `<a href="/local-files/evidence/${encodeURIComponent(row.stored_name)}" target="_blank" rel="noopener">${escapeHtml(row.original_name)}</a>`).join("") || `<span>No evidence attached.</span>`}${!submitted && editable ? `<label class="evidence-upload"><span>Add evidence</span><input id="pilot-evidence-file" type="file" accept=".pdf,.csv,.xls,.xlsx,.doc,.docx,.png,.jpg,.jpeg" /></label>` : ""}</div>
        <div class="form-actions">${submitted ? `<a class="button button-primary" href="/local-files/reports/${encodeURIComponent(selectedSubmission.report_file)}" target="_blank" rel="noopener">Open submission PDF</a>` : `<button class="button button-secondary" type="button" data-submit-mode="draft" ${editable ? "" : "disabled"}>Save draft</button><button class="button button-primary" type="button" data-submit-mode="submitted" ${editable ? "" : "disabled"}>Submit final</button>`}</div></form>
      ` : `<div class="empty-state"><strong>Create or select a local assignment</strong><span>The corresponding imported form definition will appear here.</span></div>`}
    </section>
    <section class="card pilot-certificate-card">
      <div class="local-section-heading"><span>Certificates</span><h2>Issue and verify induction certificates</h2><p>Each PDF includes branding, an expiry date, unique number and scannable verification QR.</p></div>
      <form id="pilot-certificate-form" class="certificate-form"><label><span>Company</span><input name="company" value="Kingscroft Developments" required ${editable ? "" : "disabled"} /></label><label><span>Worker</span><select name="worker" ${editable ? "" : "disabled"}>${workerOptions}</select></label><label><span>Induction</span><select name="induction" ${editable ? "" : "disabled"}>${inductions.map((induction) => `<option value="${escapeHtml(induction.title)}" data-site="${escapeHtml(induction.site)}">${escapeHtml(induction.title)}</option>`).join("")}</select></label><label><span>Validity</span><select name="validity_days" ${editable ? "" : "disabled"}><option value="365">1 year</option><option value="730">2 years</option><option value="1095">3 years</option></select></label><button class="button button-primary" ${editable ? "" : "disabled"}>Issue certificate</button></form>
      <div class="certificate-register">${completions.map((row) => `<article><span class="status">${escapeHtml(row.status || "Active")}</span><div><strong>${escapeHtml(row.worker)}</strong><small>${escapeHtml(row.certificate_number || "Legacy local certificate")} · valid to ${escapeHtml(row.expires_at || "not recorded")}</small></div><div class="certificate-actions"><a href="/local-files/certificates/${encodeURIComponent(row.certificate_file)}" target="_blank" rel="noopener">PDF</a>${row.verification_url ? `<a href="${escapeHtml(row.verification_url)}" target="_blank" rel="noopener">Verify</a>` : ""}${row.status === "Active" && editable ? `<button type="button" data-replace-certificate="${row.id}">Replace</button>${canDeleteLocalRecords() ? `<button type="button" data-revoke-certificate="${row.id}">Revoke</button>` : ""}` : ""}</div></article>`).join("") || `<p>No local certificates yet.</p>`}</div>
    </section>
  `;
  bindSignaturePads();
  document.querySelector("#pilot-assignment-picker")?.addEventListener("change", async (event) => { selectedPilotAssignmentId = event.target.value; await renderPilotWorkflows(); });
  if (!editable) return;
  document.querySelector("#pilot-assignment-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const created = await api("/api/resources/distributions", { method: "POST", body: JSON.stringify({ ...values, assigned_date: localSnapshotDate(), submitted_date: "-", score: "-", status: "Pending", source: "local controlled workspace", local_only: true }) });
      selectedPilotAssignmentId = String(created.id);
      showToast("Local assignment created.");
      await renderPilotWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelector("#pilot-upload-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    try {
      const response = await fetch("/api/local/upload", { method: "POST", headers: { "Content-Type": file.type || "application/octet-stream", "X-CSRF-Token": state.auth.csrfToken, "X-Upload-Title": encodeURIComponent(form.get("title")), "X-File-Name": encodeURIComponent(file.name) }, body: file });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Upload failed");
      showToast("Document version uploaded.");
      await renderPilotWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelector("#pilot-evidence-file")?.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file || !selectedDistribution) return;
    try {
      const response = await fetch("/api/local/evidence", { method: "POST", headers: { "Content-Type": file.type || "application/octet-stream", "X-CSRF-Token": state.auth.csrfToken, "X-File-Name": encodeURIComponent(file.name), "X-Distribution-Id": String(selectedDistribution.id) }, body: file });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Evidence upload failed");
      showToast("Evidence attached locally.");
      await renderPilotWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelectorAll("[data-submit-mode]").forEach((button) => button.addEventListener("click", async () => {
    const submissionForm = document.querySelector("#pilot-submission-form");
    const values = new FormData(submissionForm);
    const answers = formQuestions.map((question) => ({ key: question.key, value: values.get(`answer_${question.key}`) || "" }));
    try {
      const result = await api("/api/local/submission", { method: "POST", body: JSON.stringify({ distribution_id: selectedDistribution.id, submission_id: submissionForm.dataset.submissionId || null, status: button.dataset.submitMode, answers, attachment_ids: selectedEvidence.map((row) => row.id) }) });
      showToast(result.status === "Submitted" ? "Form submitted and PDF created." : "Draft saved.");
      await renderPilotWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  }));
  document.querySelector("#pilot-certificate-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const inductionSelect = event.currentTarget.elements.induction;
    try {
      await api("/api/local/certificate", { method: "POST", body: JSON.stringify({ company: form.get("company"), worker: form.get("worker"), induction: form.get("induction"), validity_days: form.get("validity_days"), site: inductionSelect.selectedOptions[0]?.dataset.site || "" }) });
      showToast("Verified certificate issued.");
      await renderPilotWorkflows();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelectorAll("[data-revoke-certificate]").forEach((button) => button.addEventListener("click", async () => {
    const reason = window.prompt("Reason for revocation:");
    if (!reason) return;
    try { await api(`/api/local/certificate/${button.dataset.revokeCertificate}/revoke`, { method: "POST", body: JSON.stringify({ reason }) }); showToast("Certificate revoked."); await renderPilotWorkflows(); } catch (error) { showToast(error.message, "error"); }
  }));
  document.querySelectorAll("[data-replace-certificate]").forEach((button) => button.addEventListener("click", async () => {
    const prior = completions.find((row) => String(row.id) === button.dataset.replaceCertificate);
    if (!prior) return;
    try { await api("/api/local/certificate", { method: "POST", body: JSON.stringify({ company: prior.company, worker: prior.worker, induction: prior.induction, site: prior.site, validity_days: 365, replaces_id: prior.id }) }); showToast("Replacement issued; previous certificate marked replaced."); await renderPilotWorkflows(); } catch (error) { showToast(error.message, "error"); }
  }));
}

function applyAuthContext() {
  const user = state.auth.user || {};
  const name = user.name || "Local user";
  const firstName = name.split(/\s+/)[0] || "User";
  document.querySelector(".account-copy strong").textContent = firstName;
  document.querySelector(".account-copy small").textContent = user.role
    ? `${user.role[0].toUpperCase()}${user.role.slice(1)}`
    : "Viewer";
  document.querySelector(".avatar").textContent = firstName[0]?.toUpperCase() || "U";
  document.querySelector("#audit-link")?.classList.toggle("hidden", user.role !== "admin");
  document.querySelector("#users-link")?.classList.toggle("hidden", user.role !== "admin");
  document.querySelector("#system-link")?.classList.toggle("hidden", user.role !== "admin");
  document.querySelector("#logout-action")?.classList.toggle("hidden", !state.auth.enabled);
}

function renderAuthScreen(setupRequired) {
  document.body.classList.add("auth-screen");
  const mode = setupRequired ? "setup" : "login";
  app.innerHTML = `
    <section class="auth-panel" aria-labelledby="auth-title">
      <div class="auth-brand"><img src="/static/favicon.svg" alt="" /><span>Kompliance</span></div>
      <span class="auth-eyebrow">${setupRequired ? "Secure first-time setup" : "Application sign in"}</span>
      <h1 id="auth-title">${setupRequired ? "Create the initial administrator" : "Welcome back"}</h1>
      <p>${setupRequired ? "This creates the first local application account. Imported customer records will remain read-only." : "Sign in to the secured local Kompliance workspace."}</p>
      <form id="auth-form">
        ${setupRequired ? `<label><span>Name</span><input name="name" autocomplete="name" required /></label>` : ""}
        <label><span>Email</span><input name="email" type="email" autocomplete="username" required /></label>
        <label><span>Password</span><input name="password" type="password" autocomplete="${setupRequired ? "new-password" : "current-password"}" minlength="12" required /></label>
        ${setupRequired ? `<label><span>Confirm password</span><input name="confirm" type="password" autocomplete="new-password" minlength="12" required /></label>` : ""}
        <div class="auth-error" id="auth-error" role="alert"></div>
        <button class="button button-primary" type="submit">${setupRequired ? "Create administrator" : "Sign in"}</button>
        ${setupRequired ? "" : `<button class="auth-text-button" id="forgot-password" type="button">Forgot your password?</button>`}
        <a class="auth-privacy-link" href="/privacy">Privacy and data handling</a>
      </form>
      <small>Protected by the outer gateway and application-level session security.</small>
    </section>
  `;
  setLoading(false);
  document.querySelector("#auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const error = document.querySelector("#auth-error");
    if (setupRequired && form.get("password") !== form.get("confirm")) {
      error.textContent = "Passwords do not match.";
      return;
    }
    try {
      const result = await api(`/api/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify({ name: form.get("name"), email: form.get("email"), password: form.get("password") }),
      });
      state.auth.authenticated = true;
      state.auth.setupRequired = false;
      state.auth.user = result.user;
      state.auth.csrfToken = result.csrf_token || "";
      document.body.classList.remove("auth-screen");
      applyAuthContext();
      await route();
    } catch (authError) {
      error.textContent = authError.message;
    }
  });
  document.querySelector("#forgot-password")?.addEventListener("click", renderRecoveryRequest);
}

function renderRecoveryRequest() {
  document.body.classList.add("auth-screen");
  app.innerHTML = `
    <section class="auth-panel" aria-labelledby="recovery-title">
      <div class="auth-brand"><img src="/static/favicon.svg" alt="" /><span>Kompliance</span></div>
      <span class="auth-eyebrow">Account recovery</span><h1 id="recovery-title">Request a password reset</h1>
      <p>The request is recorded locally. An administrator must securely deliver the prepared reset link; no external email is sent automatically.</p>
      <form id="recovery-form"><label><span>Email</span><input name="email" type="email" autocomplete="email" required /></label><div class="auth-error" id="auth-error"></div><button class="button button-primary">Prepare reset request</button><button class="auth-text-button" id="back-to-login" type="button">Back to sign in</button></form>
    </section>`;
  setLoading(false);
  document.querySelector("#back-to-login").addEventListener("click", () => renderAuthScreen(false));
  document.querySelector("#recovery-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const result = await api("/api/auth/recovery/request", { method: "POST", body: JSON.stringify({ email: form.get("email") }) });
      document.querySelector("#auth-error").textContent = result.message;
      event.currentTarget.reset();
    } catch (error) { document.querySelector("#auth-error").textContent = error.message; }
  });
}

function renderPasswordReset() {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  document.body.classList.add("auth-screen");
  app.innerHTML = `
    <section class="auth-panel" aria-labelledby="reset-title">
      <div class="auth-brand"><img src="/static/favicon.svg" alt="" /><span>Kompliance</span></div>
      <span class="auth-eyebrow">Secure reset</span><h1 id="reset-title">Choose a new password</h1><p>This one-time link expires after 30 minutes and signs out every existing session.</p>
      <form id="reset-form"><label><span>New password</span><input name="password" type="password" minlength="12" autocomplete="new-password" required /></label><label><span>Confirm password</span><input name="confirm" type="password" minlength="12" autocomplete="new-password" required /></label><div class="auth-error" id="auth-error"></div><button class="button button-primary">Reset password</button></form>
    </section>`;
  setLoading(false);
  document.querySelector("#reset-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (form.get("password") !== form.get("confirm")) { document.querySelector("#auth-error").textContent = "Passwords do not match."; return; }
    try {
      await api("/api/auth/recovery/reset", { method: "POST", body: JSON.stringify({ token, password: form.get("password") }) });
      history.replaceState({}, "", "/");
      renderAuthScreen(false);
      showToast("Password reset. Sign in with the new password.");
    } catch (error) { document.querySelector("#auth-error").textContent = error.message; }
  });
}

async function initializeAuth() {
  setLoading(true);
  try {
    const status = await api("/api/auth/status");
    state.auth = {
      enabled: Boolean(status.enabled),
      authenticated: Boolean(status.authenticated),
      setupRequired: Boolean(status.setup_required),
      user: status.user,
      csrfToken: status.csrf_token || "",
    };
    if (state.auth.enabled && (!state.auth.authenticated || state.auth.setupRequired)) {
      if (window.location.pathname === "/reset-password" && !state.auth.setupRequired) renderPasswordReset();
      else renderAuthScreen(state.auth.setupRequired);
      return;
    }
    document.body.classList.remove("auth-screen");
    applyAuthContext();
    await route();
  } catch (error) {
    app.innerHTML = `<section class="card error-card"><h2>Unable to initialise security</h2><p>${escapeHtml(error.message)}</p></section>`;
    setLoading(false);
  }
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

async function renderSystemCentre() {
  const [configuration, status, notificationResult] = await Promise.all([
    api("/api/settings"),
    api("/api/system/status"),
    api("/api/resources/local_notifications?limit=250"),
  ]);
  const settings = configuration.settings || {};
  const email = configuration.email || {};
  const scheduler = configuration.scheduler || {};
  const retention = status.retention_preview || {};
  const notifications = notificationResult.data || [];
  app.innerHTML = `
    ${pageHeader("System & privacy", "Release readiness, branding, delivery and retention controls")}
    <section class="system-status-grid">
      <article><span>Database</span><strong>${escapeHtml(status.database?.integrity || "unknown")}</strong><small>${Number(status.records?.total || 0).toLocaleString()} records</small></article>
      <article><span>Protected snapshot</span><strong>${Number(status.records?.protected || 0).toLocaleString()}</strong><small>Immutable imported records</small></article>
      <article><span>Local records</span><strong>${Number(status.records?.local || 0).toLocaleString()}</strong><small>Controlled writable records</small></article>
      <article><span>Free storage</span><strong>${formatBytes(Number(status.disk?.free_bytes || 0))}</strong><small>Application data filesystem</small></article>
      <article class="${email.enabled && email.configured ? "system-ready" : "system-hold"}"><span>Email delivery</span><strong>${email.enabled && email.configured ? "Ready" : "Hold"}</strong><small>${email.enabled ? (email.configured ? escapeHtml(email.sender) : "SMTP incomplete") : "Explicitly disabled"}</small></article>
      <article class="${scheduler.enabled ? "system-ready" : "system-hold"}"><span>Scheduler</span><strong>${scheduler.enabled ? (scheduler.running ? "Running" : "Starting") : "Disabled"}</strong><small>${scheduler.last_run_at ? `Last ${escapeHtml(displayDate(scheduler.last_run_at) || scheduler.last_run_at)}` : "No scheduled run yet"}</small></article>
    </section>
    <section class="system-layout">
      <article class="card system-settings-card">
        <div class="local-section-heading"><span>Organisation</span><h2>Branding and governance</h2><p>Non-secret settings are stored locally. Environment variables can override them during deployment.</p></div>
        <form id="system-settings-form" class="system-settings-form">
          <label><span>Product name</span><input name="brand_name" value="${escapeHtml(settings.brand_name || "")}" required /></label>
          <label><span>Organisation</span><input name="brand_company" value="${escapeHtml(settings.brand_company || "")}" required /></label>
          <label><span>Brand tagline</span><input name="brand_tagline" value="${escapeHtml(settings.brand_tagline || "")}" required /></label>
          <label><span>Privacy contact</span><input name="privacy_contact" type="email" value="${escapeHtml(settings.privacy_contact || "")}" placeholder="privacy@example.ie" /></label>
          <label><span>Default compliance recipient</span><input name="compliance_recipient" type="email" value="${escapeHtml(settings.compliance_recipient || "")}" placeholder="safety@example.ie" /></label>
          <label><span>Reminder window (days)</span><input name="reminder_days" type="number" min="1" max="365" value="${escapeHtml(settings.reminder_days || "30")}" /></label>
          <label><span>Notification retention (days)</span><input name="retention_days" type="number" min="30" max="3650" value="${escapeHtml(settings.retention_days || "365")}" /></label>
          <div class="system-form-actions"><button class="button button-primary">Save settings</button><a class="button button-secondary" href="/privacy" target="_blank" rel="noopener">View privacy notice</a></div>
        </form>
      </article>
      <article class="card system-operations-card">
        <div class="local-section-heading"><span>Operations</span><h2>Delivery and retention</h2><p>External email remains fail-closed until explicitly enabled in the deployment environment.</p></div>
        <dl class="system-detail-list"><div><dt>SMTP host</dt><dd>${email.host_configured ? "Configured" : "Not configured"}</dd></div><div><dt>Canonical HTTPS URL</dt><dd>${email.base_url_configured ? "Configured" : "Not configured"}</dd></div><div><dt>Sender</dt><dd>${escapeHtml(email.sender || "Not configured")}</dd></div><div><dt>Security</dt><dd>${escapeHtml(email.mode || "starttls")}</dd></div><div><dt>Queued history</dt><dd>${notifications.length.toLocaleString()}</dd></div></dl>
        <button class="button button-primary" id="deliver-queue" ${email.enabled && email.configured ? "" : "disabled"}>Deliver prepared queue</button>
        <div class="retention-preview"><strong>Retention preview</strong><span>${Number(retention.local_notifications || 0)} old local notifications</span><span>${Number(retention.expired_sessions || 0)} expired sessions</span><span>${Number(retention.expired_reset_tokens || 0)} expired reset tokens</span><span>0 protected records</span></div>
        <button class="button button-danger" id="run-retention" ${Number(retention.local_notifications || 0) + Number(retention.expired_sessions || 0) + Number(retention.expired_reset_tokens || 0) ? "" : "disabled"}>Remove expired local data</button>
      </article>
    </section>
    <section class="card table-card"><div class="table-toolbar"><div><span>Delivery history</span><h2>Prepared and sent notifications</h2></div></div><div class="table-scroll"><table class="data-table"><thead><tr><th>Date</th><th>Kind</th><th>Recipient</th><th>Subject</th><th>Status</th><th>Attempts</th><th>Action</th></tr></thead><tbody>${notifications.slice(0, 100).map((row) => `<tr><td>${escapeHtml(displayDate(row.created_at) || row.created_at)}</td><td>${escapeHtml(row.kind || "Notification")}</td><td>${escapeHtml(row.recipient || "Not assigned")}</td><td>${escapeHtml(row.subject || "—")}</td><td><span class="status">${escapeHtml(row.status || row.delivery_status || "Prepared")}</span>${row.last_error ? `<small class="delivery-error">${escapeHtml(row.last_error)}</small>` : ""}</td><td>${Number(row.attempts || 0)}</td><td>${row.delivery_status === "failed" ? `<button type="button" data-retry-notification="${row.id}" ${email.enabled && email.configured ? "" : "disabled"}>Retry</button>` : "—"}</td></tr>`).join("") || `<tr><td colspan="7" class="table-empty">No local notification history yet.</td></tr>`}</tbody></table></div></section>
  `;
  document.querySelector("#system-settings-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const values = Object.fromEntries(new FormData(event.currentTarget).entries());
      await api("/api/settings", { method: "PUT", body: JSON.stringify(values) });
      showToast("System settings saved and audited.");
      await renderSystemCentre();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelector("#deliver-queue")?.addEventListener("click", async () => {
    try {
      const result = await api("/api/compliance/notifications/send", { method: "POST", body: JSON.stringify({ limit: 500 }) });
      showToast(`Delivery run complete: ${result.sent} sent, ${result.failed} failed, ${result.skipped} skipped.`);
      await renderSystemCentre();
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelectorAll("[data-retry-notification]").forEach((button) => button.addEventListener("click", async () => {
    try {
      const result = await api("/api/compliance/notifications/send", { method: "POST", body: JSON.stringify({ ids: [Number(button.dataset.retryNotification)], limit: 1 }) });
      showToast(result.sent ? "Notification delivered." : `Retry completed: ${result.failed} failed, ${result.skipped} skipped.`);
      await renderSystemCentre();
    } catch (error) { showToast(error.message, "error"); }
  }));
  document.querySelector("#run-retention")?.addEventListener("click", async () => {
    if (!window.confirm("Remove only expired local notifications, sessions and reset tokens? Imported customer records will not be touched.")) return;
    try {
      const result = await api("/api/system/retention-cleanup", { method: "POST", body: JSON.stringify({ confirmation: "PURGE_LOCAL_EXPIRED_DATA" }) });
      showToast(`Retention complete. ${result.local_notifications} local notification records removed; 0 protected records removed.`);
      await renderSystemCentre();
    } catch (error) { showToast(error.message, "error"); }
  });
}

async function renderComplianceCentre(days = 30) {
  const [result, notificationResult, configuration] = await Promise.all([
    api(`/api/compliance/reminders?days=${days}`),
    api("/api/resources/local_notifications?limit=5000"),
    api("/api/settings"),
  ]);
  const counts = result.counts || {};
  const rows = result.data || [];
  const notifications = (notificationResult.data || []).filter((row) => row.kind === "compliance_reminder");
  const email = configuration.email || {};
  const canDeliver = state.auth.user?.role === "admin" && email.enabled && email.configured;
  app.innerHTML = `
    ${pageHeader("Expiry centre", "Upcoming and overdue compliance records")}
    <section class="expiry-summary-grid">
      <article class="expiry-overdue"><span>Overdue</span><strong>${Number(counts.overdue || 0).toLocaleString()}</strong><small>Requires review</small></article>
      <article class="expiry-due"><span>Due within ${days} days</span><strong>${Number(counts.due_soon || 0).toLocaleString()}</strong><small>Reminder window</small></article>
      <article><span>Current</span><strong>${Number(counts.current || 0).toLocaleString()}</strong><small>Beyond the window</small></article>
      <article><span>Date missing</span><strong>${Number(counts.missing_date || 0).toLocaleString()}</strong><small>Source has no parseable date</small></article>
    </section>
    <section class="card expiry-controls"><label><span>Reminder window</span><select id="expiry-days">${[7, 14, 30, 60, 90].map((value) => `<option value="${value}" ${value === days ? "selected" : ""}>${value} days</option>`).join("")}</select></label><button class="button button-primary" id="prepare-reminders" ${canEditLocalRecords() ? "" : "disabled"}>Prepare due reminders</button><button class="button button-secondary" id="deliver-reminders" ${canDeliver ? "" : "disabled"}>Deliver prepared email</button><span>${notifications.length} reminder notification${notifications.length === 1 ? "" : "s"} · email ${email.enabled && email.configured ? "ready" : "on hold"}</span></section>
    <section class="card table-card"><div class="table-scroll"><table class="data-table"><thead><tr><th>State</th><th>Category</th><th>Subject</th><th>Recipient</th><th>Site</th><th>Due date</th><th>Days</th></tr></thead><tbody>${rows.map((row) => `<tr><td><span class="status expiry-${row.state.toLowerCase().replace(/\s/g, "-")}">${escapeHtml(row.state)}</span></td><td>${escapeHtml(row.category)}</td><td>${escapeHtml(row.subject)}</td><td>${escapeHtml(row.recipient || "Not assigned")}</td><td>${escapeHtml(row.site || "—")}</td><td>${escapeHtml(row.due_date)}</td><td>${Number(row.days_remaining)}</td></tr>`).join("") || `<tr><td colspan="7" class="table-empty">No dated compliance records found.</td></tr>`}</tbody></table></div></section>
  `;
  document.querySelector("#expiry-days").addEventListener("change", (event) => renderComplianceCentre(Number(event.target.value)));
  document.querySelector("#prepare-reminders").addEventListener("click", async () => {
    try {
      const prepared = await api("/api/compliance/notifications/prepare", { method: "POST", body: JSON.stringify({ days }) });
      showToast(`${prepared.created} reminder${prepared.created === 1 ? "" : "s"} prepared; ${prepared.duplicates || 0} duplicate${prepared.duplicates === 1 ? "" : "s"} skipped.`);
      await renderComplianceCentre(days);
    } catch (error) { showToast(error.message, "error"); }
  });
  document.querySelector("#deliver-reminders")?.addEventListener("click", async () => {
    try {
      const delivery = await api("/api/compliance/notifications/send", { method: "POST", body: JSON.stringify({ limit: 500 }) });
      showToast(`${delivery.sent} sent, ${delivery.failed} failed, ${delivery.skipped} skipped.`);
      await renderComplianceCentre(days);
    } catch (error) { showToast(error.message, "error"); }
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
      state.listFilters = defaultListFilters(LIST_ROUTES[path]);
      state.calendarOpen = false;
      await renderList(LIST_ROUTES[path]);
    } else if (path === "/archive") {
      await renderArchive();
    } else if (path === "/company-profile") {
      renderProfile();
    } else if (path === "/change-password") {
      renderChangePassword();
    } else if (path === "/audit") {
      await renderAuditLog();
    } else if (path === "/users") {
      await renderUserManagement();
    } else if (path === "/system") {
      await renderSystemCentre();
    } else if (path === "/local-workflows") {
      await renderPilotWorkflows();
    } else if (path === "/compliance") {
      await renderComplianceCentre();
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

document.querySelector("#logout-action")?.addEventListener("click", async (event) => {
  event.preventDefault();
  try {
    await api("/api/auth/logout", { method: "POST", body: "{}" });
  } finally {
    state.auth.authenticated = false;
    state.auth.user = null;
    state.auth.csrfToken = "";
    history.replaceState({}, "", "/");
    renderAuthScreen(false);
  }
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
initializeAuth();
