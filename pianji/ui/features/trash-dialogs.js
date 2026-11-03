import { state, assets, el, button, error, toast } from "../store.js";
import { api } from "../api.js";
import { modal, field, confirmAction } from "../core/modal.js";

export function deleteActivityDialog(id, start) {
  const activity = state.activities.find((a) => a.id === id);
  if (!activity) return;
  const count = state.photos.filter((p) => p.activity_id === id).length;
  confirmAction(
    "删除活动",
    `将“${activity.name}”的 ${count} 张照片及关联原片、成片和保留版本移入回收站，并从活动列表移除。恢复其中任意照片时，活动会重新出现。SD 来源和活动文件夹中的其他文件保留。`,
    () => start("delete_activity", id),
  );
}
export function deleteDialog(ids, start) {
  if (!ids.length) return;
  const rows = state.photos.filter((p) => ids.includes(p.id)),
    count = rows.flatMap(assets).length;
  confirmAction(
    "删除照片",
    `将所选 ${ids.length} 张照片（${count} 个已关联文件，以及同组保留版本）移到当前照片库的回收站。JPEG、RAW、XMP 和成片一起移入，可从左侧“回收站”恢复；仍占用磁盘空间。SD 卡上的来源照片保留。`,
    () => start("trash_photos", ids),
  );
}
export async function trashDialog(start, selectedIds = []) {
  const rows = await api("list_photos", { trashed: true }),
    m = modal("回收站");
  const chosen = new Set(
    selectedIds.filter((id) => rows.some((p) => p.id === id)),
  );
  m.content.append(
    el(
      "p",
      "",
      `${rows.length} 张照片 · 仅当前照片库。单击选择或取消，支持多选；永久删除后不可恢复。`,
    ),
  );
  const toolbar = el("div", "trash-toolbar"),
    count = el("span", "small muted"),
    all = button("全选", () => {
      if (rows.every((p) => chosen.has(p.id))) chosen.clear();
      else rows.forEach((p) => chosen.add(p.id));
      sync();
    });
  toolbar.append(all, count);
  m.content.append(toolbar);
  const list = el("div", "trash-list");
  const checks = new Map();
  const run = async (name, ids) => {
    const snap = await start(name, ids);
    if (snap?.status === "succeeded") await trashDialog(start);
  };
  for (const p of rows) {
    const row = el("div", "library-row"),
      info = button(
        "",
        (e) => {
          if (e.detail > 1) return;
          chosen.has(p.id) ? chosen.delete(p.id) : chosen.add(p.id);
          sync();
        },
        "trash-choice",
      );
    info.setAttribute("aria-label", "选择 " + p.stem);
    info.append(
      el("strong", "", p.stem),
      el(
        "span",
        "small muted",
        (p.activity_name ||
          state.activities.find((a) => a.id === p.activity_id)?.name ||
          "活动") +
          " · " +
          (p.file_count ?? assets(p).length) +
          " 个关联文件" +
          (p.purge_pending
            ? " · 永久删除未完成，请重试"
            : p.missing
              ? " · 部分文件缺失"
              : ""),
      ),
    );
    checks.set(p.id, info);
    const restore = button(
      "恢复",
      async () => {
        try {
          await run("restore_photos", [p.id]);
        } catch (e) {
          m.err.textContent = e.message;
        }
      },
      "outline",
    );
    restore.disabled = Boolean(p.purge_pending);
    row.append(info, restore);
    list.append(row);
  }
  m.content.append(list);
  m.buttons.replaceChildren(button("关闭", () => m.dialog.close()));
  function confirmDelete(ids) {
    if (!ids.length) return;
    const selectedRows = rows.filter((p) => ids.includes(p.id)),
      files = selectedRows.reduce(
        (sum, p) => sum + (p.file_count ?? assets(p).length),
        0,
      ),
      confirm = modal("永久删除照片");
    confirm.content.append(
      el(
        "p",
        "",
        `将永久删除 ${ids.length} 张照片（${files} 个关联文件及保留版本）。此操作不可恢复，仅删除当前照片库回收站文件；SD 来源和正常照片保留。`,
      ),
    );
    confirm.buttons.replaceChildren(
      button("取消", () => trashDialog(start, [...chosen]).catch(error)),
    );
    const execute = confirm.submit("确认永久删除", () =>
      run("purge_trash", ids),
    );
    execute.classList.add("destructive");
  }
  const erase = button(
      "永久删除所选",
      () => confirmDelete([...chosen]),
      "danger outline",
    ),
    restoreSelected = button(
      "恢复所选",
      async () => {
        try {
          await run("restore_photos", [...chosen]);
        } catch (e) {
          m.err.textContent = e.message;
        }
      },
      "outline",
    );
  m.buttons.append(
    restoreSelected,
    erase,
    button(
      "清空回收站",
      () => confirmDelete(rows.map((p) => p.id)),
      "danger outline",
    ),
  );
  function sync() {
    count.textContent = `已选 ${chosen.size} 张`;
    all.textContent =
      rows.length && rows.every((p) => chosen.has(p.id)) ? "取消全选" : "全选";
    all.disabled = !rows.length;
    erase.disabled = !chosen.size;
    restoreSelected.disabled =
      !chosen.size || rows.some((p) => chosen.has(p.id) && p.purge_pending);
    for (const [id, node] of checks) {
      node.classList.toggle("checked", chosen.has(id));
      node.setAttribute("aria-pressed", String(chosen.has(id)));
    }
  }
  if (!rows.length) m.buttons.lastElementChild.disabled = true;
  sync();
}
