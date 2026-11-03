import { state, $, toast } from "../store.js";
import { api } from "../api.js";
import { syncSelection } from "../gallery.js";
import { invalidateLibraryPreviews } from "../previews.js";
import { clearChoices } from "../choice-list.js";
import { remember, clearHistory } from "../navigation.js";
import { resultDialog } from "./result-dialog.js";

export function createTaskController({ refresh, renderInspector }) {
  let taskId = null,
    proposedSource = null;
  async function start(name, ...args) {
    if (state.busy) throw new Error("请等待当前任务完成");
    state.busy = true;
    syncSelection();
    $("#inspector")
      .querySelectorAll("[data-mutation]")
      .forEach((b) => (b.disabled = true));
    try {
      const result = await api(name, ...args);
      if (!result) return;
      if (!result.task_id) return result;
      if ($("#modal").open) $("#modal").close();
      taskId = result.task_id;
      $("#taskbar").hidden = false;
      $("#cancel-task").disabled = false;
      $("#classify").disabled = true;
      while (taskId) {
        const snap = await api("get_task", taskId);
        $("#task-message").textContent = snap.message || "处理中";
        $("#task-progress").textContent = snap.total
          ? `${snap.done} / ${snap.total}`
          : "请稍候";
        const meter = $("#task-meter");
        if (snap.total) {
          meter.max = snap.total;
          meter.value = snap.done;
        } else meter.removeAttribute("value");
        if (
          ["succeeded", "partial", "failed", "cancelled"].includes(snap.status)
        ) {
          if (
            name === "scan" &&
            ["succeeded", "partial"].includes(snap.status) &&
            snap.result?.scan_id
          ) {
            clearHistory();
            state.source = proposedSource;
            state.sourceFolder = "";
            state.format = "all";
            state.scanId = snap.result.scan_id;
            state.sourcePhotos = snap.result.photos;
            state.selected.sd.clear();
            state.current = null;
            clearChoices();
          }
          if (name === "import_selected" && snap.result?.activity_id) {
            remember();
            state.activity = snap.result.activity_id;
            state.view = "library";
            state.person = "all";
            state.stage = "all";
            state.selected.sd.clear();
          }
          if (
            ["set_person", "set_edited"].includes(name) &&
            snap.result?.operations?.length
          )
            state.lastOperation = {
              id: snap.result.operations.at(-1),
              photoId: snap.result.photo_ids?.at(-1),
            };
          else if (name !== "scan") state.lastOperation = null;
          if (name !== "scan") invalidateLibraryPreviews();
          taskId = null;
          await refresh();
          if (snap.status !== "succeeded") resultDialog(snap, name);
          else
            toast(
              name === "scan"
                ? `已读取 ${snap.result.photos.length} 张照片`
                : name === "import_selected"
                  ? `导入 ${snap.result.imported.length} 张，补充 ${snap.result.updated?.length || 0} 张，跳过 ${snap.result.skipped} 张`
                  : "操作已完成",
            );
          return snap;
        }
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
    } finally {
      taskId = null;
      state.busy = false;
      $("#taskbar").hidden = true;
      syncSelection();
      renderInspector();
      $("#classify").disabled = !state.activity;
    }
  }
  async function scanSource() {
    if (state.busy) return;
    const result = await api("choose_source");
    if (!result) return;
    proposedSource = result;
    await start("scan", result.token, $("#source-read-format").value);
  }
  async function cancel() {
    if (taskId) {
      await api("cancel_task", taskId);
      $("#cancel-task").disabled = true;
      $("#task-message").textContent = "正在等待当前照片安全结束…";
    }
  }
  return { start, scanSource, cancel };
}
