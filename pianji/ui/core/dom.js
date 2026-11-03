import { decorateButton } from "../icons.js";
export const $ = (s) => document.querySelector(s);
export function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
export function button(text, fn, cls = "") {
  const b = el("button", cls, text);
  b.type = "button";
  b.addEventListener("click", fn);
  decorateButton(b);
  return b;
}
let timer;
export function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(timer);
  timer = setTimeout(() => ($("#toast").hidden = true), 4500);
}
export function error(e) {
  toast(e.message || String(e));
}
