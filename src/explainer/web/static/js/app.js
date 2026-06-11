// src/explainer/web/static/js/app.js
// Entry point: wires the top bar and view navigation, then loads initial data.
"use strict";

import { el, showView, applyTheme, getTheme } from "./views.js";
import { applyLang, getLang, t } from "./i18n.js";
import { getDriveStatus } from "./api.js";
import { loadGallery } from "./gallery.js";
import { showCompose, initCompose } from "./compose.js";
import { stopPolling } from "./progress.js";

let _driveConnected = false;
export function driveConnected() { return _driveConnected; }

function goHome() {
  stopPolling();
  showView("gallery");
  loadGallery();
}

async function loadDriveStatus() {
  try {
    const s = await getDriveStatus();
    el.driveBtn.hidden = !s.configured;
    _driveConnected = s.connected;
    el.driveBtn.dataset.connected = s.connected ? "true" : "false";
    el.driveBtnLabel.textContent = s.connected ? t("driveConnected") : t("connectDrive");
  } catch { /* ignore */ }
}

// Keep the Drive button label in the active language.
document.addEventListener("i18n:changed", () => {
  if (el.driveBtn && !el.driveBtn.hidden)
    el.driveBtnLabel.textContent = _driveConnected ? t("driveConnected") : t("connectDrive");
});

el.langToggle.addEventListener("click", () => applyLang(getLang() === "en" ? "ar" : "en"));
el.themeToggle.addEventListener("click", () => applyTheme(getTheme() === "dark" ? "light" : "dark"));
el.brandHome.addEventListener("click", goHome);
el.newBtn.addEventListener("click", showCompose);
el.composeBack.addEventListener("click", goHome);
el.resultBack.addEventListener("click", goHome);
el.resultNewBtn.addEventListener("click", showCompose);
el.errorRetry.addEventListener("click", showCompose);

initCompose();
applyTheme(getTheme());
applyLang(getLang());
showView("gallery");
loadGallery();
loadDriveStatus();
