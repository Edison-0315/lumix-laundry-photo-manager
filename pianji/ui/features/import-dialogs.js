import { state, assets, el, button, error, toast } from "../store.js";
import { api } from "../api.js";
import { modal, field, confirmAction } from "../core/modal.js";

export async function importDialog(start, refresh, activityName = null) {
  if (!state.settings.library_available) {
    const { libraryDialog } = await import("../library-manager.js");
    if (!(await libraryDialog(refresh))) return;
  }
  const ids = [...state.selected.sd];
  if (!ids.length) return;
  const m = modal("导入所选照片"),
    labelActivity = el("label", "", "活动名称"),
    name = el("select");
  name.setAttribute("aria-label", "活动名称");
  const placeholder = el("option", "", "请选择活动");
  placeholder.value = "";
  placeholder.disabled = true;
  name.append(placeholder);
  state.activities.forEach((a) => {
    const o = el("option", "", a.name);
    o.value = a.name;
    name.append(o);
  });
  labelActivity.append(name);
  m.content.append(labelActivity);
  name.value =
    activityName ||
    state.activities.find((a) => a.id === state.activity)?.name ||
    state.activities[0]?.name ||
    "";
  m.content.append(
    button(
      "新建活动",
      () =>
        newActivityDialog(async (activity) => {
          await refresh();
          await importDialog(start, refresh, activity.name);
        }),
      "outline",
    ),
    el(
      "p",
      "small muted",
      state.activities.length
        ? "选择要导入的活动，或新建一个活动。"
        : "还没有活动，请先点“新建活动”。",
    ),
  );
  const label = el("label", "", "导入格式"),
    select = el("select");
  for (const [value, text] of [
    ["both", "JPEG 和 RAW"],
    ["jpeg", "仅 JPEG"],
    ["raw", "仅 RAW"],
  ]) {
    const o = el("option", "", text);
    o.value = value;
    select.append(o);
  }
  label.append(select);
  m.content.append(label);
  select.value = state.format === "all" ? "both" : state.format;
  const summary = el("div", "notice");
  const submit = m.submit("开始导入", () => {
    if (!name.value) throw new Error("请先选择或新建活动");
    return start(
      "import_selected",
      state.scanId,
      ids,
      name.value,
      select.value,
    );
  });
  const update = () => {
    const groups = state.sourcePhotos.filter((p) => ids.includes(p.id)),
      files = groups
        .flatMap(assets)
        .filter(
          (a) =>
            select.value === "both" ||
            a.kind === select.value ||
            (select.value === "raw" && a.kind === "xmp"),
        );
    summary.textContent = `已选 ${ids.length} 张照片，预计 ${files.length} 个文件。\n目标：${name.value ? state.settings.library + "\\" + name.value + "\\待分类\\选出原片" : "请先选择或新建活动"}\n从来源复制，源文件保留；导入后可识别人脸。`;
    submit.disabled = !name.value;
  };
  name.onchange = update;
  select.onchange = update;
  update();
  m.content.append(summary);
}
export function newActivityDialog(done, initial = "") {
  const m = modal("新建活动"),
    name = field(m.content, "活动名称", initial);
  m.submit("创建活动", async () => {
    const activity = await api("create_activity", name.value.trim());
    await done(activity);
  });
  name.focus();
  name.select();
}
