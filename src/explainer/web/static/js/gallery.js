// src/explainer/web/static/js/gallery.js
// Renders the module grid (home). Each card shows a real PDF first-page thumbnail
// with a graceful lamp-motif fallback if the image fails to load.
"use strict";

import { el } from "./views.js";
import { t, formatDate } from "./i18n.js";
import { getModules } from "./api.js";
import { openModule } from "./result.js";

let lastModules = [];

const LAMP_SVG =
  '<svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M8 3h7l3 8H5z"></path><path d="M11.5 11v7"></path><path d="M8 21h7"></path></svg>';

function card(m) {
  const li = document.createElement("li");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "card";
  btn.innerHTML =
    '<span class="card__thumb">' +
      '<img class="card__img" loading="lazy" alt="">' +
      '<span class="card__fallback" aria-hidden="true">' + LAMP_SVG + "</span>" +
    "</span>" +
    '<span class="card__meta">' +
      '<span class="card__name"></span>' +
      '<span class="card__date"></span>' +
    "</span>";
  btn.querySelector(".card__name").textContent = m.name;
  btn.querySelector(".card__date").textContent = formatDate(m.created_at);
  const thumb = btn.querySelector(".card__thumb");
  const img = btn.querySelector(".card__img");
  // decorative: the card__name span already labels the button for AT
  img.addEventListener("error", () => { thumb.dataset.fallback = "true"; });
  img.src = m.thumb_url;
  btn.addEventListener("click", () => openModule(m));
  li.appendChild(btn);
  return li;
}

// Dashed "+" tile: alternate entry to compose at the end of the shelf.
function addTile() {
  const li = document.createElement("li");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "card card--add";
  btn.setAttribute("aria-label", t("newModule"));
  btn.innerHTML = '<span aria-hidden="true">+</span>';
  btn.addEventListener("click", () => el.newBtn.click());
  li.appendChild(btn);
  return li;
}

export function renderGallery(modules) {
  lastModules = modules || [];
  el.galleryGrid.innerHTML = "";
  el.galleryEmpty.hidden = lastModules.length > 0;
  for (const m of lastModules) el.galleryGrid.appendChild(card(m));
  if (lastModules.length > 0) el.galleryGrid.appendChild(addTile());
}

export async function loadGallery() {
  try {
    renderGallery(await getModules());
  } catch { /* offline: keep what we have */ }
}

// Re-render relative dates when the language changes.
document.addEventListener("i18n:changed", () => renderGallery(lastModules));

// Test/demo hook: render the gallery from fixture data without a backend.
window.__demoGallery = (modules) => renderGallery(modules || [
  { id: "demo-1", name: "Gradient Descent, Week 2", created_at: "2026-06-11T14:20:00", thumb_url: "" },
  { id: "demo-2", name: "Arabic Poetry", created_at: "2026-06-10T09:00:00", thumb_url: "" },
]);
