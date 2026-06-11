// src/explainer/web/static/js/result.js
// The result view: PDF iframe, download link, and Google Drive state/upload.
"use strict";

import { el, showView } from "./views.js";
import { t } from "./i18n.js";
import { uploadModule } from "./api.js";
import { loadGallery } from "./gallery.js";
import { driveConnected } from "./app.js";

export function openModule(m) {
  el.resultName.textContent = m.name;
  el.resultPdf.src = m.pdf_url;
  el.downloadLink.href = m.pdf_url;
  el.downloadLink.setAttribute("download", m.name + ".pdf");
  renderDrive(m.drive_link ? "uploaded" : "", m.drive_link || "", m.id);
  showView("result");
}

export function renderDrive(state, link, moduleId) {
  const box = el.resultDrive;
  box.hidden = false;
  box.innerHTML = "";
  if (state === "uploading") {
    box.textContent = t("uploadingDrive");
  } else if (link) {
    const label = document.createElement("span");
    label.textContent = t("savedToDrive") + " · ";
    const a = document.createElement("a");
    a.href = link; a.target = "_blank"; a.rel = "noopener";
    a.textContent = t("openInDrive");
    box.append(label, a);
  } else if (driveConnected()) {
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "btn btn--ghost";
    btn.textContent = (state === "error")
      ? t("uploadFailedDrive") + " · " + t("uploadToDrive") : t("uploadToDrive");
    btn.addEventListener("click", () => manualUpload(moduleId, btn));
    box.appendChild(btn);
  } else {
    box.hidden = true;
  }
}

async function manualUpload(moduleId, btn) {
  btn.disabled = true;
  try {
    const data = await uploadModule(moduleId);
    renderDrive("uploaded", data.link, moduleId);
    await loadGallery();
  } catch {
    btn.disabled = false;
    renderDrive("error", "", moduleId);
  }
}
