"use strict";

/* ---- i18n: English (default) + Egyptian Arabic ---- */
const STRINGS = {
  en: {
    appName: "Study Lamp",
    skip: "Skip to content",
    langToggle: "العربية",
    newModule: "New module",
    yourModules: "Your modules",
    libraryEmpty: "Modules you make will show up here.",
    composeTitle: "Turn a lesson into Egyptian-Arabic study notes",
    composeSub: "Paste a course transcript or an article. You get a clear Egyptian-Arabic PDF with diagrams and a review quiz.",
    moduleNameLabel: "Module name",
    moduleNamePh: "e.g. Gradient Descent, Week 2",
    contentLabel: "Paste your content",
    contentPh: "Paste the full transcript or article text here.",
    generate: "Generate study PDF",
    generateHint: "This takes a minute or two. The PDF is always in Egyptian Arabic.",
    progressTitle: "Building your study PDF",
    stepLoading: "Reading the content",
    stepOutlining: "Planning the sections",
    stepWriting: "Writing in Egyptian Arabic",
    stepRendering: "Rendering the PDF",
    download: "Download",
    errorTitle: "That didn't work",
    tryAgain: "Try again",
    untitled: "Untitled module",
    errNoContent: "Paste some content to explain first.",
    errNetwork: "Could not reach the server. Is it still running?",
    connectDrive: "Connect Google Drive",
    driveConnected: "Saved to Drive",
    uploadingDrive: "Uploading to Drive…",
    savedToDrive: "Saved to Drive",
    openInDrive: "Open in Drive",
    uploadToDrive: "Upload to Drive",
    uploadFailedDrive: "Drive upload failed",
    htmlLang: "en", dir: "ltr", locale: "en-GB",
  },
  ar: {
    appName: "مصباح المذاكرة",
    skip: "تخطّي للمحتوى",
    langToggle: "English",
    newModule: "موديول جديد",
    yourModules: "الموديولز بتاعتك",
    libraryEmpty: "الموديولز اللي هتعملها هتظهر هنا.",
    composeTitle: "حوّل أي درس لمذكرة مذاكرة بالعامية المصرية",
    composeSub: "الصق ترانسكريبت كورس أو مقال، وهتطلعلك مذكرة PDF واضحة بالعامية المصرية فيها رسومات وأسئلة مراجعة.",
    moduleNameLabel: "اسم الموديول",
    moduleNamePh: "مثال: Gradient Descent، الأسبوع ٢",
    contentLabel: "الصق المحتوى",
    contentPh: "الصق نص الترانسكريبت أو المقال كامل هنا.",
    generate: "اعمل مذكرة PDF",
    generateHint: "بياخد دقيقة أو اتنين. المذكرة دايمًا بالعامية المصرية.",
    progressTitle: "بنجهّز مذكرة المذاكرة بتاعتك",
    stepLoading: "بنقرا المحتوى",
    stepOutlining: "بنرتّب الأقسام",
    stepWriting: "بنكتب بالعامية المصرية",
    stepRendering: "بنطلّع الـ PDF",
    download: "تحميل",
    errorTitle: "للأسف مظبطش",
    tryAgain: "جرّب تاني",
    untitled: "موديول من غير اسم",
    errNoContent: "الصق شوية محتوى الأول.",
    errNetwork: "مش قادر أوصل للسيرفر. لسه شغّال؟",
    connectDrive: "اربط جوجل درايف",
    driveConnected: "متصل بدرايف",
    uploadingDrive: "بنرفع على درايف…",
    savedToDrive: "اتحفظت على درايف",
    openInDrive: "افتح في درايف",
    uploadToDrive: "ارفع على درايف",
    uploadFailedDrive: "الرفع على درايف فشل",
    htmlLang: "ar", dir: "rtl", locale: "ar-EG",
  },
};
const STAGE_ORDER = ["loading", "outlining", "writing", "rendering"];

const $ = (sel) => document.querySelector(sel);
const el = {
  html: document.documentElement,
  langToggle: $("#langToggle"),
  themeToggle: $("#themeToggle"),
  newBtn: $("#newBtn"),
  libraryList: $("#libraryList"),
  libraryEmpty: $("#libraryEmpty"),
  form: $("#composeForm"),
  name: $("#nameInput"),
  text: $("#textInput"),
  generateBtn: $("#generateBtn"),
  composeError: $("#composeError"),
  progressModule: $("#progressModule"),
  steps: $("#steps"),
  writeCount: $("#writeCount"),
  progressDetail: $("#progressDetail"),
  resultName: $("#resultName"),
  resultPdf: $("#resultPdf"),
  downloadLink: $("#downloadLink"),
  resultNewBtn: $("#resultNewBtn"),
  errorMessage: $("#errorMessage"),
  errorRetry: $("#errorRetry"),
  driveBtn: $("#driveBtn"),
  driveBtnLabel: $("#driveBtnLabel"),
};

let lang = localStorage.getItem("sl-lang") || "en";
let theme = localStorage.getItem("sl-theme") || "dark";
let pollTimer = null;
let driveConnected = false;

/* ---- i18n + theme application ---- */
function t(key) { return STRINGS[lang][key]; }

function applyLang(next) {
  lang = next;
  localStorage.setItem("sl-lang", lang);
  const s = STRINGS[lang];
  el.html.lang = s.htmlLang;
  el.html.dir = s.dir;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const v = s[node.getAttribute("data-i18n")];
    if (v != null) node.textContent = v;
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((node) => {
    const v = s[node.getAttribute("data-i18n-ph")];
    if (v != null) node.setAttribute("placeholder", v);
  });
  renderLibrary(lastModules); // re-render dates in the new locale
  if (el.driveBtn && !el.driveBtn.hidden)
    el.driveBtnLabel.textContent = driveConnected ? t("driveConnected") : t("connectDrive");
}

function applyTheme(next) {
  theme = next;
  localStorage.setItem("sl-theme", theme);
  el.html.setAttribute("data-theme", theme);
}

/* ---- View switching ---- */
function showView(name) {
  for (const v of ["Compose", "Progress", "Result", "Error"]) {
    $("#view" + v).hidden = (v.toLowerCase() !== name);
  }
}

/* ---- Library ---- */
let lastModules = [];
let currentId = null;

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  try {
    return new Intl.DateTimeFormat(t("locale"), { dateStyle: "medium", timeStyle: "short" }).format(d);
  } catch { return d.toLocaleString(); }
}

function renderLibrary(modules) {
  lastModules = modules || [];
  el.libraryList.innerHTML = "";
  el.libraryEmpty.hidden = lastModules.length > 0;
  for (const m of lastModules) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "library__item";
    if (m.id === currentId) btn.setAttribute("aria-current", "true");
    btn.innerHTML =
      `<span class="library__item-name"></span><span class="library__item-date"></span>`;
    btn.querySelector(".library__item-name").textContent = m.name;
    btn.querySelector(".library__item-date").textContent = formatDate(m.created_at);
    btn.addEventListener("click", () => openModule(m));
    li.appendChild(btn);
    el.libraryList.appendChild(li);
  }
}

async function loadLibrary() {
  try {
    const res = await fetch("/api/modules");
    if (res.ok) renderLibrary(await res.json());
  } catch { /* offline: keep what we have */ }
}

async function loadDriveStatus() {
  try {
    const res = await fetch("/api/drive/status");
    if (!res.ok) return;
    const s = await res.json();
    el.driveBtn.hidden = !s.configured;
    driveConnected = s.connected;
    el.driveBtn.dataset.connected = s.connected ? "true" : "false";
    el.driveBtnLabel.textContent = s.connected ? t("driveConnected") : t("connectDrive");
  } catch { /* ignore */ }
}

/* ---- Result ---- */
function openModule(m) {
  stopPolling();
  currentId = m.id;
  el.resultName.textContent = m.name;
  el.resultPdf.src = m.pdf_url;
  el.downloadLink.href = m.pdf_url;
  el.downloadLink.setAttribute("download", m.name + ".pdf");
  showView("result");
  renderLibrary(lastModules); // update aria-current highlight
}

/* ---- Progress ---- */
function renderStage(job) {
  const idx = STAGE_ORDER.indexOf(job.stage);
  el.steps.querySelectorAll(".step").forEach((step) => {
    const sIdx = STAGE_ORDER.indexOf(step.dataset.stage);
    let state = "pending";
    if (job.stage === "done") state = "done";
    else if (sIdx < idx) state = "done";
    else if (sIdx === idx) state = "active";
    step.dataset.state = state;
  });
  el.writeCount.textContent = (job.total > 0 && (job.stage === "writing" || STAGE_ORDER.indexOf(job.stage) > 2))
    ? `${job.done} / ${job.total}` : "";
  el.progressDetail.textContent = job.detail || "";
}

function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

function pollJob(jobId, name) {
  stopPolling();
  pollTimer = setInterval(async () => {
    let job;
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) return;
      job = await res.json();
    } catch { return; }
    renderStage(job);
    if (job.status === "done") {
      stopPolling();
      await loadLibrary();
      openModule({ id: jobId, name, pdf_url: job.pdf_url });
    } else if (job.status === "error") {
      stopPolling();
      el.errorMessage.textContent = job.error || "";
      showView("error");
    }
  }, 1200);
}

/* ---- Generate ---- */
async function generate(ev) {
  ev.preventDefault();
  const text = el.text.value.trim();
  el.composeError.hidden = true;
  if (!text) {
    el.composeError.textContent = t("errNoContent");
    el.composeError.hidden = false;
    el.text.focus();
    return;
  }
  const name = el.name.value.trim() || t("untitled");
  el.generateBtn.disabled = true;
  let data;
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, text }),
    });
    data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");
  } catch (e) {
    el.composeError.textContent = (e && e.message) || t("errNetwork");
    el.composeError.hidden = false;
    el.generateBtn.disabled = false;
    return;
  }
  el.generateBtn.disabled = false;
  currentId = data.job_id;
  el.progressModule.textContent = data.name;
  el.steps.querySelectorAll(".step").forEach((s) => (s.dataset.state = "pending"));
  el.writeCount.textContent = "";
  el.progressDetail.textContent = "";
  showView("progress");
  pollJob(data.job_id, data.name);
}

function newModule() {
  stopPolling();
  currentId = null;
  el.form.reset();
  el.composeError.hidden = true;
  showView("compose");
  renderLibrary(lastModules);
  el.name.focus();
}

/* ---- Wire up ---- */
el.langToggle.addEventListener("click", () => applyLang(lang === "en" ? "ar" : "en"));
el.themeToggle.addEventListener("click", () => applyTheme(theme === "dark" ? "light" : "dark"));
el.newBtn.addEventListener("click", newModule);
el.resultNewBtn.addEventListener("click", newModule);
el.errorRetry.addEventListener("click", newModule);
el.form.addEventListener("submit", generate);

applyTheme(theme);
applyLang(lang);
showView("compose");
loadLibrary();
loadDriveStatus();

/* test/demo hook: render a fake progress state without a real run */
window.__demoStage = (stage, done, total, detail) => {
  showView("progress");
  el.progressModule.textContent = "Gradient Descent, Week 2";
  renderStage({ stage, done: done || 0, total: total || 0, detail: detail || "", status: "running" });
};
