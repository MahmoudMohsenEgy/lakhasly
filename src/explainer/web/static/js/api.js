// src/explainer/web/static/js/api.js
// Thin fetch wrappers over the JSON API. No DOM access.
"use strict";

// Central fetch: on an auth failure, send the user to the login page.
async function _fetch(url, opts) {
  const res = await fetch(url, opts);
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("unauthorized");
  }
  return res;
}

export async function getModules() {
  const res = await _fetch("/api/modules");
  if (!res.ok) throw new Error("modules");
  return res.json();
}

export async function generate(name, text) {
  const res = await _fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, text }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export async function getJob(jobId) {
  const res = await _fetch(`/api/jobs/${jobId}`);
  if (!res.ok) throw new Error("job");
  return res.json();
}

export async function getDriveStatus() {
  const res = await _fetch("/api/drive/status");
  if (!res.ok) throw new Error("drive");
  return res.json();
}

export async function uploadModule(moduleId) {
  const res = await _fetch(`/api/modules/${moduleId}/upload`, { method: "POST" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "failed");
  return data;
}
