// src/explainer/web/static/js/compose.js
// The full-screen compose view: form reset, validation, and generate submission.
"use strict";

import { el, showView } from "./views.js";
import { t } from "./i18n.js";
import { generate } from "./api.js";
import { startJob, stopPolling } from "./progress.js";

export function showCompose() {
  stopPolling();
  el.form.reset();
  el.composeError.hidden = true;
  showView("compose");
  el.name.focus();
}

async function onSubmit(ev) {
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
    data = await generate(name, text);
  } catch (e) {
    el.composeError.textContent = (e && e.message) || t("errNetwork");
    el.composeError.hidden = false;
    el.generateBtn.disabled = false;
    return;
  }
  el.generateBtn.disabled = false;
  startJob(data.job_id, data.name);
}

export function initCompose() {
  el.form.addEventListener("submit", onSubmit);
}
