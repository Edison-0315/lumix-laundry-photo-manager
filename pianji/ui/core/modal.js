import { $, el, button } from "./dom.js";

export function modal(title) {
  const trigger = document.activeElement?.getBoundingClientRect();
  const dialog = $("#modal"),
    body = $("#modal-content"),
    heading = el("h2", "", title);
  heading.id = "modal-title";
  dialog.setAttribute("aria-labelledby", heading.id);
  body.replaceChildren(heading);
  const content = el("div"),
    err = el("div", "field-error"),
    buttons = el("div", "buttons");
  err.setAttribute("role", "alert");
  body.append(content, err, buttons);
  buttons.append(button("取消", () => dialog.close()));
  if (!dialog.open) dialog.showModal();
  const bounds = dialog.getBoundingClientRect(),
    clamp = (n) => Math.max(0, Math.min(100, n));
  dialog.style.transformOrigin = trigger?.width
    ? `${clamp(((trigger.x + trigger.width / 2 - bounds.x) / bounds.width) * 100)}% ${clamp(((trigger.y + trigger.height / 2 - bounds.y) / bounds.height) * 100)}%`
    : "50% 50%";
  const submit = (text, fn) => {
    const b = button(
      text,
      async () => {
        b.disabled = true;
        err.textContent = "";
        try {
          await fn();
          if (content.isConnected && dialog.open) dialog.close();
        } catch (e) {
          if (!dialog.open && content.isConnected) dialog.showModal();
          err.textContent = e.message;
        } finally {
          b.disabled = false;
        }
      },
      "primary",
    );
    buttons.append(b);
    return b;
  };
  return { dialog, content, err, buttons, submit };
}
export function field(parent, label, value = "", type = "text") {
  const row = el("label", "", label),
    input = el("input");
  input.type = type;
  input.value = value;
  row.append(input);
  parent.append(row);
  return input;
}
export function confirmAction(title, message, fn) {
  const m = modal(title);
  m.content.append(el("p", "", message));
  m.submit("确认", fn);
}
