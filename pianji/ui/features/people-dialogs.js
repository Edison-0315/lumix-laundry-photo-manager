import { state, assets, el, button, error, toast } from "../store.js";
import { api } from "../api.js";
import { modal, field, confirmAction } from "../core/modal.js";

export function deletePeopleDialog(ids, start) {
  if (!ids.length) return;
  confirmAction(
    "删除人物分类",
    `删除 ${ids.length} 个人物分类，并将其全部原片和成片移回同活动的“待分类”。保留照片、修图阶段和成片关联；回收站中该人物照片恢复后也归入待分类。`,
    () => start("delete_people", ids),
  );
}
export function assignDialog(ids, start, refresh) {
  const m = modal("调整人物");
  m.content.append(
    el("p", "", `将 ${ids.length} 张照片及关联文件整理到所选人物文件夹。`),
  );
  const select = el("select");
  for (const p of state.people) {
    const o = el("option", "", p.name);
    o.value = p.id;
    select.append(o);
  }
  m.content.append(select);
  m.content.append(
    button(
      "新建人物",
      () =>
        newPersonDialog(async (person) => {
          await refresh();
          await start("set_person", ids, person.id);
        }),
      "outline",
    ),
  );
  m.submit("移动到此人物", () => start("set_person", ids, select.value));
}
export function newPersonDialog(done) {
  if (!state.activity) {
    toast("请先选择活动");
    return;
  }
  const m = modal("新建人物"),
    name = field(m.content, "人物名称");
  m.submit("创建", async () => {
    const person = await api("create_person", state.activity, name.value);
    await done(person);
  });
  name.focus();
}
export function managePeopleDialog(start, initialId = null) {
  const normal = state.people.filter((p) => !p.role);
  if (!normal.length) {
    toast("还没有普通人物，可以先识别人脸或新建人物");
    return;
  }
  const m = modal("管理人物"),
    select = el("select");
  normal.forEach((p) => {
    const o = el("option", "", p.name);
    o.value = p.id;
    select.append(o);
  });
  m.content.append(select);
  if (initialId && normal.some((p) => p.id === initialId))
    select.value = initialId;
  const name = field(
    m.content,
    "新名称",
    normal.find((p) => p.id === select.value).name,
  );
  select.onchange = () =>
    (name.value = normal.find((p) => p.id === select.value).name);
  m.submit("重命名", () => start("rename_person", select.value, name.value));
  const target = el("select");
  state.people.forEach((p) => {
    const o = el("option", "", p.name);
    o.value = p.id;
    target.append(o);
  });
  const label = el("label", "", "或合并到");
  label.append(target);
  m.content.append(
    label,
    el("p", "", "合并会移动全部原片和成片，人工归属将保留。"),
  );
  m.buttons.prepend(
    button(
      "合并人物",
      async () => {
        try {
          if (select.value === target.value)
            throw new Error("请选择另一个人物");
          m.dialog.close();
          confirmAction(
            "合并人物",
            "确认将所选人物的全部照片移到目标人物？",
            () => start("merge_people", select.value, target.value),
          );
        } catch (e) {
          m.err.textContent = e.message;
        }
      },
      "outline",
    ),
  );
}
