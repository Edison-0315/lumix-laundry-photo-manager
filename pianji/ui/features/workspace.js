import {
  state,
  $,
  selected,
  basePhotos,
  visible,
  el,
  resetLibrarySelection,
  libraryFolderMode,
  toast,
  error,
} from "../store.js";
import {
  renderGallery,
  syncSelection,
  setThumbnailSize,
  onInspector,
  onFolder,
  setupViewer,
} from "../gallery.js";
import { setupSelection } from "../selection.js";
import { settingsDialog } from "./settings-dialog.js";
import { importDialog } from "./import-dialogs.js";
import {
  assignDialog,
  newPersonDialog,
  managePeopleDialog,
} from "./people-dialogs.js";
import { deleteDialog, trashDialog } from "./trash-dialogs.js";
import { confirmAction } from "../core/modal.js";
import { libraryDialog } from "../library-manager.js";
import { setupContextMenu } from "../context-menu.js";
import {
  choices,
  syncChoices,
  folderScope,
  selectableFolderKeys,
} from "../choice-list.js";
import { remember, goBack } from "../navigation.js";
import { decorateControls } from "../icons.js";
import { syncChrome } from "../chrome-motion.js";
import {
  enterWorkspaceFolder,
  stopWorkspaceTransition,
  folderIdentity,
} from "../workspace-motion.js";

export function setupWorkspace({
  refresh,
  renderInspector,
  start,
  scanSource,
  cancel,
  sidebar,
}) {
  const safe =
    (fn) =>
    (...args) =>
      Promise.resolve()
        .then(() => fn(...args))
        .catch(error);
  function render() {
    stopWorkspaceTransition();
    const isSD = state.view === "sd";
    document
      .querySelectorAll("[data-view]")
      .forEach((b) =>
        b.classList.toggle("active", b.dataset.view === state.view),
      );
    $("#title").textContent = isSD
      ? "选片"
      : state.activities.find((a) => a.id === state.activity)?.name || "照片库";
    $("#subtitle").textContent = isSD
      ? state.source?.path || "选择SD卡或照片文件夹，在这里查看和选片"
      : "原片与成片关联管理 · 人物和修图阶段分别整理";
    $("#context").textContent = isSD
      ? "浏览来源 · 选择后导入"
      : "照片库 · " +
        (state.people.find((p) => p.id === state.person)?.name || "全部人物");
    $("#choose-source").hidden = !isSD;
    $("#classify").hidden = isSD;
    $("#classify").disabled = !state.activity || state.busy;
    $("#source-read-label").hidden = !isSD;
    $("#toggle-browse").hidden = isSD || state.person !== "all";
    $("#toggle-browse").textContent =
      state.browse === "folders" ? "平铺照片" : "人物文件夹";
    $("#stage-tabs").hidden = isSD;
    $("#people-section").hidden = isSD;
    $("#import").hidden = !isSD;
    $("#library-actions").hidden = isSD;
    $("#library-path").textContent =
      state.settings.library?.split(/[\\/]/).filter(Boolean).pop() ||
      "尚未选择照片库";
    $("#choose-library").textContent = "管理照片库";
    $("#format-filter").value = state.format;
    sidebar.renderNavigation();
    document
      .querySelectorAll("[data-stage]")
      .forEach((b) =>
        b.classList.toggle("active", b.dataset.stage === state.stage),
      );
    const dates = [
      ...new Set(
        basePhotos().map((p) => p.captured_at?.slice(0, 10) || "unknown"),
      ),
    ].sort();
    const date = $("#date-filter");
    date.replaceChildren();
    for (const value of ["all", ...dates]) {
      const o = el(
        "option",
        "",
        value === "all"
          ? "所有日期"
          : value === "unknown"
            ? "拍摄日期未知"
            : value,
      );
      o.value = value;
      date.append(o);
    }
    if (!dates.includes(state.date)) state.date = "all";
    date.value = state.date;
    $("#only-selected").checked = state.onlySelected;
    if (!visible().some((p) => p.id === state.current))
      state.current = visible().find((p) => selected().has(p.id))?.id || null;
    renderGallery();
    renderInspector();
    decorateControls();
    syncChrome();
    $("#library-path").title = state.settings.library || "";
  }
  document.querySelectorAll("[data-view]").forEach(
    (b) =>
      (b.onclick = () => {
        if (state.view !== b.dataset.view) remember();
        state.view = b.dataset.view;
        state.current = null;
        state.date = "all";
        state.onlySelected = false;
        render();
      }),
  );
  document.querySelectorAll("[data-stage]").forEach(
    (b) =>
      (b.onclick = () => {
        if (state.stage !== b.dataset.stage || state.browse !== "photos")
          remember();
        resetLibrarySelection();
        state.stage = b.dataset.stage;
        state.browse = "photos";
        state.date = "all";
        state.onlySelected = false;
        render();
      }),
  );
  $("#choose-source").onclick = safe(scanSource);
  $("#choose-library").onclick = safe(() => libraryDialog(refresh));
  $("#trash").onclick = safe(() => trashDialog(start));
  $("#settings").onclick = safe(() => settingsDialog(start));
  $("#import").onclick = safe(() => importDialog(start, refresh));
  $("#toggle-browse").onclick = () => {
    remember();
    resetLibrarySelection();
    state.browse = state.browse === "folders" ? "photos" : "folders";
    render();
  };
  $("#back").onclick = safe(() => goBack(refresh));
  document.addEventListener("keydown", (e) => {
    if (
      e.altKey &&
      e.key === "ArrowLeft" &&
      !e.target.closest("input,select,textarea") &&
      !$("#modal").open &&
      !$("#viewer").open
    ) {
      e.preventDefault();
      safe(() => goBack(refresh))();
    }
  });
  $("#classify").onclick = safe(() =>
    confirmAction(
      "识别人脸",
      "在本机按当前活动分人物。多人照片进入合照，不确定的保留待分类；手动确认过的照片将跳过。",
      () => start("classify_activity", state.activity),
    ),
  );
  const actionIds = () =>
    libraryFolderMode()
      ? []
      : visible()
          .filter((p) => selected().has(p.id))
          .map((p) => p.id);
  $("#assign").onclick = () => assignDialog(actionIds(), start, refresh);
  $("#new-person").onclick = () =>
    newPersonDialog(async () => {
      await refresh();
      toast("人物已创建");
    });
  $("#manage-people").onclick = () => managePeopleDialog(start);
  $("#mark-edited").onclick = safe(() =>
    start("set_edited", actionIds(), true),
  );
  $("#mark-pending").onclick = safe(() => {
    const ids = actionIds();
    if (state.photos.some((p) => ids.includes(p.id) && p.primary_export_id))
      confirmAction(
        "恢复待修",
        "这些照片已有成片，恢复待修会移动原片并保留全部成片关联。",
        () => start("set_edited", ids, false),
      );
    else return start("set_edited", ids, false);
  });
  $("#mark-finished").onclick = safe(() =>
    start("set_finished", actionIds(), true),
  );
  $("#unmark-finished").onclick = () => {
    const ids = actionIds();
    confirmAction(
      "取消成片",
      "取消所选照片的全部成片关联，复制文件移入库内“取消关联保留”目录；原片与修图阶段保留。",
      () => start("set_finished", ids, false),
    );
  };
  $("#date-filter").onchange = (e) => {
    if (state.view === "library") resetLibrarySelection();
    state.date = e.target.value;
    renderGallery();
    renderInspector();
  };
  $("#only-selected").onchange = (e) => {
    state.onlySelected = e.target.checked;
    renderGallery();
  };
  $("#format-filter").onchange = (e) => {
    if (state.view === "library") resetLibrarySelection();
    state.format = e.target.value;
    renderGallery();
    renderInspector();
  };
  $("#select-all").onclick = () => {
    const folders = selectableFolderKeys(),
      rows = libraryFolderMode() ? [] : visible(),
      set = choices(folderScope());
    const all =
      folders.length + rows.length > 0 &&
      folders.every((key) => set.has(key)) &&
      rows.every((p) => selected().has(p.id));
    folders.forEach((key) => (all ? set.delete(key) : set.add(key)));
    rows.forEach((p) => (all ? selected().delete(p.id) : selected().add(p.id)));
    syncChoices(folderScope());
    if (state.onlySelected) renderGallery();
    else syncSelection();
  };
  $("#thumb-size").oninput = (e) => setThumbnailSize(e.target.value);
  $("#thumb-smaller").onclick = () => setThumbnailSize(state.thumbSize - 40);
  $("#thumb-larger").onclick = () => setThumbnailSize(state.thumbSize + 40);
  $("#gallery").addEventListener(
    "wheel",
    (e) => {
      if (e.ctrlKey) {
        e.preventDefault();
        setThumbnailSize(state.thumbSize + (e.deltaY < 0 ? 40 : -40));
      }
    },
    { passive: false },
  );
  $("#cancel-task").onclick = safe(cancel);
  setupSelection(renderInspector);
  setupViewer();
  onInspector(renderInspector);
  onFolder((folder, source) => {
    const identity = folderIdentity(source);
    return enterWorkspaceFolder(source, () =>
      folder.kind === "source"
        ? sidebar.chooseFolder(folder.path, identity)
        : sidebar.openLibraryFolder(folder, identity),
    ).catch(error);
  });
  setupContextMenu(
    { trash: () => deleteDialog(actionIds(), start) },
    renderInspector,
  );
  return render;
}
