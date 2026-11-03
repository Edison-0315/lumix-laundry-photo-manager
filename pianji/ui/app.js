/** Composition root: module wiring and initial application load only. */
import { ready, api } from "./api.js";
import { state, $, visible, error } from "./store.js";
import { setupChrome } from "./chrome-motion.js";
import { leaveWorkspaceFolder } from "./workspace-motion.js";
import { createTaskController } from "./features/tasks.js";
import { createInspector } from "./features/inspector.js";
import { createSidebar } from "./features/sidebar.js";
import { setupWorkspace } from "./features/workspace.js";

setupChrome();
const tasks = createTaskController({
  refresh,
  renderInspector: () => renderInspector(),
});
const renderInspector = createInspector({ refresh, start: tasks.start });
const sidebar = createSidebar({
  refresh,
  render: () => render(),
  start: tasks.start,
});
const render = setupWorkspace({ refresh, renderInspector, ...tasks, sidebar });

async function refresh(options = null) {
  state.settings = await api("get_settings");
  if (state.settings.library_available) {
    state.activities = await api("list_activities");
    if (!state.activities.some((a) => a.id === state.activity))
      state.activity = state.activities[0]?.id || null;
    state.people = state.activity
      ? await api("list_people", state.activity)
      : [];
    state.photos = await api("list_photos", {});
    if (
      state.person !== "all" &&
      !state.people.some((p) => p.id === state.person)
    ) {
      state.person = "all";
      state.stage = "all";
      state.browse = "folders";
    }
    const context =
      state.view === "library"
        ? visible()
        : state.photos.filter((p) => p.activity_id === state.activity);
    const valid = new Set(context.map((p) => p.id));
    for (const id of state.selected.library)
      if (!valid.has(id)) state.selected.library.delete(id);
  } else {
    state.activities = [];
    state.people = [];
    state.photos = [];
  }
  const draw = () => {
    render();
    if (options?.scroll !== undefined) $("#gallery").scrollTop = options.scroll;
  };
  if (options?.folderReturn)
    return leaveWorkspaceFolder(options.folderReturn, draw);
  draw();
}
ready()
  .then(async () => {
    state.settings = await api("get_settings");
    state.thumbSize = state.settings.thumbnail_size || 240;
    $("#thumb-size").value = state.thumbSize;
    await refresh();
  })
  .catch(error);
