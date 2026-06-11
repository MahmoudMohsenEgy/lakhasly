// src/explainer/web/static/js/views.js
// DOM references, view switching, and theme application.
"use strict";

const $ = (sel) => document.querySelector(sel);

export const el = {
  html: document.documentElement,
  langToggle: $("#langToggle"),
  themeToggle: $("#themeToggle"),
  brandHome: $("#brandHome"),
  newBtn: $("#newBtn"),
  galleryGrid: $("#galleryGrid"),
  galleryEmpty: $("#galleryEmpty"),
  composeBack: $("#composeBack"),
  form: $("#composeForm"),
  name: $("#nameInput"),
  text: $("#textInput"),
  generateBtn: $("#generateBtn"),
  composeError: $("#composeError"),
  progressModule: $("#progressModule"),
  steps: $("#steps"),
  writeCount: $("#writeCount"),
  progressDetail: $("#progressDetail"),
  resultBack: $("#resultBack"),
  resultName: $("#resultName"),
  resultDrive: $("#resultDrive"),
  resultPdf: $("#resultPdf"),
  downloadLink: $("#downloadLink"),
  resultNewBtn: $("#resultNewBtn"),
  errorMessage: $("#errorMessage"),
  errorRetry: $("#errorRetry"),
  driveBtn: $("#driveBtn"),
  driveBtnLabel: $("#driveBtnLabel"),
};

const VIEWS = ["Gallery", "Compose", "Progress", "Result", "Error"];

export function showView(name) {
  for (const v of VIEWS) {
    document.querySelector("#view" + v).hidden = (v.toLowerCase() !== name);
  }
}

let theme = localStorage.getItem("sl-theme") || "light";

export function getTheme() { return theme; }

export function applyTheme(next) {
  theme = next;
  localStorage.setItem("sl-theme", theme);
  el.html.setAttribute("data-theme", theme);
}
