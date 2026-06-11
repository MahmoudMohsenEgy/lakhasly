// src/explainer/web/static/js/i18n.js
// Bilingual strings (English default + Egyptian Arabic) and language application.
// applyLang() dispatches a document-level "i18n:changed" event so locale-dependent
// views (e.g. the gallery's relative dates) can re-render without a circular import.
"use strict";

export const STRINGS = {
  en: {
    appName: "Study Lamp",
    skip: "Skip to content",
    langToggle: "العربية",
    newModule: "New module",
    yourModules: "Your modules",
    galleryEmpty: "No modules yet. Make your first one.",
    backToModules: "Modules",
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
    driveConnected: "Drive connected",
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
    galleryEmpty: "لسه مفيش موديولز. اعمل أول واحد.",
    backToModules: "الموديولز",
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

let lang = localStorage.getItem("sl-lang") || "en";

export function getLang() { return lang; }
export function t(key) { return STRINGS[lang][key]; }

export function applyLang(next) {
  lang = next;
  localStorage.setItem("sl-lang", lang);
  const s = STRINGS[lang];
  const html = document.documentElement;
  html.lang = s.htmlLang;
  html.dir = s.dir;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const v = s[node.getAttribute("data-i18n")];
    if (v != null) node.textContent = v;
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((node) => {
    const v = s[node.getAttribute("data-i18n-ph")];
    if (v != null) node.setAttribute("placeholder", v);
  });
  document.dispatchEvent(new CustomEvent("i18n:changed"));
}

export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  try {
    return new Intl.DateTimeFormat(t("locale"), { dateStyle: "medium", timeStyle: "short" }).format(d);
  } catch { return d.toLocaleString(); }
}
