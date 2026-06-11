// src/explainer/web/static/js/progress.js
// Renders the four-stage progress list and polls the job until done/error.
"use strict";

import { el, showView } from "./views.js";
import { getJob } from "./api.js";
import { openModule, renderDrive } from "./result.js";
import { loadGallery } from "./gallery.js";

const STAGE_ORDER = ["loading", "outlining", "writing", "rendering"];
let pollTimer = null;

export function renderStage(job) {
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

export function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

export function startJob(jobId, name) {
  el.progressModule.textContent = name;
  el.steps.querySelectorAll(".step").forEach((s) => (s.dataset.state = "pending"));
  el.writeCount.textContent = "";
  el.progressDetail.textContent = "";
  showView("progress");
  stopPolling();
  pollTimer = setInterval(async () => {
    let job;
    try { job = await getJob(jobId); } catch { return; }
    renderStage(job);
    if (job.status === "done") {
      stopPolling();
      await loadGallery();
      openModule({ id: jobId, name, pdf_url: job.pdf_url, drive_link: job.drive_link || "" });
      if (job.drive_status === "uploading") renderDrive("uploading", "", jobId);
    } else if (job.status === "error") {
      stopPolling();
      el.errorMessage.textContent = job.error || "";
      showView("error");
    }
  }, 1200);
}

// Test/demo hook: render a fake progress state without a real run.
window.__demoStage = (stage, done, total, detail) => {
  showView("progress");
  el.progressModule.textContent = "Gradient Descent, Week 2";
  renderStage({ stage, done: done || 0, total: total || 0, detail: detail || "", status: "running" });
};
