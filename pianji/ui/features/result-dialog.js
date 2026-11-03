import { state, assets, el, button, error, toast } from "../store.js";
import { api } from "../api.js";
import { modal, field, confirmAction } from "../core/modal.js";

export function resultDialog(snapshot, kind = "") {
  const scanCancelled = kind === "scan" && snapshot.status === "cancelled";
  const m = modal(
    scanCancelled
      ? "读取已取消"
      : kind === "scan"
        ? "读取结果"
        : snapshot.status === "failed"
          ? "任务未完成"
          : snapshot.status === "cancelled"
            ? "任务已取消"
            : "部分文件需要处理",
  );
  const result = snapshot.result || {};
  m.content.append(
    el(
      "p",
      "",
      scanCancelled
        ? "已停止读取，保留此前的选片结果。"
        : kind === "scan"
          ? result.scan_id
            ? `已读取 ${result.photos.length} 张可用照片，下面的文件或文件夹未能读取；其他照片可继续选片。`
            : "未读取到可用照片，保留此前的选片结果。请查看具体错误路径。"
          : snapshot.status === "cancelled"
            ? "已经完整完成的照片保留，未完成的文件已尝试恢复；可重新执行。"
            : "已完成的照片保留，请检查下面的文件后重试。",
    ),
  );
  const list = el("div", "notice");
  list.style.maxHeight = "300px";
  list.style.overflow = "auto";
  for (const e of snapshot.errors || [])
    list.append(
      el(
        "p",
        "",
        (e.operation || "") +
          " " +
          (e.path || e.name || e.id || "") +
          (e.winerror ? ` · WinError ${e.winerror}` : "") +
          " " +
          (e.message || JSON.stringify(e)),
      ),
    );
  if (!list.children.length)
    list.textContent = `完成 ${result.imported?.length ?? result.classified ?? snapshot.done ?? 0} 项。`;
  m.content.append(list);
  m.buttons.replaceChildren(
    button("知道了", () => m.dialog.close(), "primary"),
  );
}
