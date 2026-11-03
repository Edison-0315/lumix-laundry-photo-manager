import {
  state,
  $,
  el,
  button,
  toast,
  error,
  folderPaths,
  sourceDirs,
  resetLibrarySelection,
} from "../store.js";
import { remember } from "../navigation.js";
import { icon } from "../icons.js";
import { choices, syncChoices } from "../choice-list.js";
import { commandMenu } from "../context-menu.js";
import { newActivityDialog } from "./import-dialogs.js";
import { managePeopleDialog, deletePeopleDialog } from "./people-dialogs.js";
import { deleteActivityDialog } from "./trash-dialogs.js";

export function createSidebar({ refresh, render, start }) {
  const safe =
    (fn) =>
    (...args) =>
      Promise.resolve()
        .then(() => fn(...args))
        .catch(error);
  function sideButton(label, active, fn, count) {
    const b = button("", safe(fn), "side-item" + (active ? " active" : ""));
    b.append(icon("folder"), el("span", "side-label", label));
    if (count !== undefined) b.append(el("span", "count", String(count)));
    b.title = label;
    return b;
  }
  async function openActivity(id) {
    if (
      state.activity !== id ||
      state.view !== "library" ||
      state.person !== "all" ||
      state.stage !== "all" ||
      state.browse !== "folders"
    )
      remember();
    resetLibrarySelection();
    state.activity = id;
    state.person = "all";
    state.stage = "all";
    state.browse = "folders";
    state.view = "library";
    await refresh();
  }
  function openPerson(id, returnFolder = null) {
    const layout = id === "all" ? "folders" : "photos";
    if (
      state.person !== id ||
      state.view !== "library" ||
      state.browse !== layout ||
      state.stage !== "all"
    )
      remember(returnFolder);
    resetLibrarySelection();
    state.person = id;
    state.stage = "all";
    state.browse = layout;
    state.date = "all";
    state.view = "library";
    render();
  }
  function openLibraryFolder(folder, returnFolder = null) {
    if (folder.kind === "person") openPerson(folder.person, returnFolder);
  }
  function createActivity() {
    if (!state.settings.library_available) {
      toast("请先创建或打开照片库");
      return;
    }
    newActivityDialog(async (activity) => openActivity(activity.id));
  }
  function chooseFolder(path, returnFolder = null) {
    if (state.sourceFolder !== path) remember(returnFolder);
    state.sourceFolder = path;
    state.date = "all";
    state.onlySelected = false;
    state.current = null;
    render();
  }
  function renderFolders() {
    const show = state.view === "sd" && Boolean(state.scanId);
    $("#source-section").hidden = !show;
    $("#source-breadcrumbs").hidden = !show;
    if (!show) return;
    const rows = folderPaths(),
      container = $("#source-folders");
    container.replaceChildren();
    for (const path of rows) {
      const b = sideButton(
        path || "来源根目录",
        state.sourceFolder === path,
        () => chooseFolder(path),
        state.sourcePhotos.filter((p) => sourceDirs(p).includes(path)).length,
      );
      b.setAttribute("aria-label", "文件夹 " + (path || "来源根目录"));
      b.title = path || state.source?.path || "";
      container.append(b);
    }
    if (rows.length > 1)
      container.append(
        sideButton(
          "全部子文件夹",
          state.sourceFolder === "*",
          () => chooseFolder("*"),
          state.sourcePhotos.length,
        ),
      );
    const crumb = $("#source-breadcrumbs");
    crumb.replaceChildren(button("来源根目录", () => chooseFolder("")));
    if (state.sourceFolder === "*")
      crumb.append(el("span", "", "/ 全部子文件夹"));
    else {
      let path = "";
      for (const part of state.sourceFolder.split("/").filter(Boolean)) {
        path = path ? path + "/" + part : part;
        const target = path;
        crumb.append(
          el("span", "muted", "/"),
          button(part, () => chooseFolder(target)),
        );
      }
    }
  }
  function sidebarMenu(e) {
    const node = e.target.closest("[data-person],[data-activity]"),
      personArea = e.target.closest("#people-section");
    if (!node && !personArea && !e.target.closest("#activities-section"))
      return;
    e.preventDefault();
    const scope = node?.dataset.selectScope,
      key = node?.dataset.selectKey;
    if (scope && !choices(scope).has(key)) {
      choices(scope).clear();
      choices(scope).add(key);
      syncChoices(scope);
    }
    if (node?.dataset.person || personArea) {
      const ids = scope
          ? [...choices(scope)].filter((id) =>
              state.people.some((p) => p.id === id),
            )
          : node?.dataset.person
            ? [node.dataset.person]
            : [],
        people = state.people.filter((p) => ids.includes(p.id));
      commandMenu(e.clientX, e.clientY, "人物分类", [
        {
          name: "添加人物",
          fn: () => $("#new-person").click(),
          disabled: state.busy || !state.activity,
        },
        {
          name: "查看人物照片",
          fn: () => openPerson(ids[0]),
          disabled: ids.length !== 1,
        },
        {
          name: "重命名人物",
          fn: () => managePeopleDialog(start, ids[0]),
          disabled:
            state.busy || people.length !== 1 || Boolean(people[0]?.role),
        },
        {
          name: "删除人物分类…",
          fn: () => deletePeopleDialog(ids, start),
          disabled: state.busy || !people.length || people.some((p) => p.role),
          danger: true,
        },
      ]);
    } else
      commandMenu(e.clientX, e.clientY, "活动", [
        {
          name: "新建活动",
          fn: createActivity,
          disabled: state.busy || !state.settings.library_available,
        },
        {
          name: "打开活动",
          fn: () => openActivity(node.dataset.activity),
          disabled: !node,
        },
        {
          name: "删除活动…",
          fn: () => deleteActivityDialog(node.dataset.activity, start),
          disabled: state.busy || !node,
          danger: true,
        },
      ]);
  }
  document.addEventListener("contextmenu", sidebarMenu);
  document.addEventListener("keydown", (e) => {
    if (
      (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) &&
      e.target.closest("#people-section,#activities-section")
    ) {
      const r = e.target.getBoundingClientRect();
      sidebarMenu({
        target: e.target,
        clientX: r.left,
        clientY: r.bottom,
        preventDefault: () => e.preventDefault(),
      });
    }
  });
  function renderNavigation() {
    const isSD = state.view === "sd";
    $("#activities").replaceChildren(
      ...state.activities.map((a) => {
        const b = sideButton(a.name, a.id === state.activity, () =>
          openActivity(a.id),
        );
        b.firstElementChild.replaceWith(icon("calendar"));
        b.dataset.activity = a.id;
        return b;
      }),
    );
    $("#people-all").classList.toggle("active", state.person === "all");
    $("#people-body").hidden = state.peopleCollapsed;
    $("#people-body").inert = state.peopleCollapsed;
    $("#people-collapse").setAttribute(
      "aria-expanded",
      String(!state.peopleCollapsed),
    );
    $("#people").replaceChildren(
      ...state.people.map((p) => {
        const b = sideButton(
          p.name,
          state.person === p.id,
          () => openPerson(p.id),
          state.photos.filter(
            (row) =>
              row.activity_id === state.activity && row.person_id === p.id,
          ).length,
        );
        b.firstElementChild.replaceWith(
          icon(
            p.role === "group"
              ? "users"
              : p.role === "unclassified"
                ? "inbox"
                : "person",
          ),
        );
        b.dataset.person = p.id;
        return b;
      }),
    );
    const crumbs = $("#library-breadcrumbs");
    crumbs.hidden = isSD;
    crumbs.replaceChildren(button("全部人物", () => openPerson("all")));
    if (state.person !== "all") {
      crumbs.append(
        el("span", "muted", "/"),
        button(
          state.people.find((p) => p.id === state.person)?.name || "人物",
          () => openPerson(state.person),
        ),
      );
      if (state.stage !== "all")
        crumbs.append(
          el("span", "muted", "/"),
          el(
            "span",
            "",
            { pending: "选出原片", edited: "已修原片", exports: "成片" }[
              state.stage
            ],
          ),
        );
    } else if (state.browse === "photos")
      crumbs.append(el("span", "small muted", "/ 平铺照片"));
    renderFolders();
  }
  $("#new-activity").onclick = safe(createActivity);
  $("#people-all").onclick = () => openPerson("all");
  $("#people-collapse").onclick = () => {
    state.peopleCollapsed = !state.peopleCollapsed;
    render();
  };
  return { renderNavigation, chooseFolder, openLibraryFolder };
}
