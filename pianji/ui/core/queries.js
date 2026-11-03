/** Derived views over a supplied session; never loads files or renders UI. */
export function createQueries(state) {
  function selected() {
    return state.selected[state.view];
  }
  function basePhotos() {
    return state.view === "sd"
      ? state.sourcePhotos
      : state.photos.filter((p) => p.activity_id === state.activity);
  }
  function sourceDirs(p) {
    return p.relative_dirs || [p.relative_dir || ""];
  }
  function visible(ignoreSelection = false) {
    return basePhotos().filter(
      (p) =>
        (state.view !== "sd" ||
          state.sourceFolder === "*" ||
          sourceDirs(p).includes(state.sourceFolder)) &&
        (state.format === "all" ||
          assets(p).some((a) => a.kind === state.format)) &&
        (state.view === "sd" ||
          state.person === "all" ||
          p.person_id === state.person) &&
        (state.view === "sd" ||
          state.stage === "all" ||
          (state.stage === "pending" && !p.edited) ||
          (state.stage === "edited" && p.edited) ||
          (state.stage === "exports" && p.primary_export_id)) &&
        (state.date === "all" ||
          (p.captured_at?.slice(0, 10) || "unknown") === state.date) &&
        (ignoreSelection || !state.onlySelected || selected().has(p.id)),
    );
  }
  function libraryFolderMode() {
    return (
      state.view === "library" &&
      state.browse === "folders" &&
      state.person === "all"
    );
  }
  function libraryFolders() {
    if (!libraryFolderMode()) return [];
    const rows = visible(true);
    if (state.person === "all")
      return state.people.map((p) => {
        const items = rows.filter((row) => row.person_id === p.id);
        return {
          key: p.id,
          label: p.name,
          kind: "person",
          person: p.id,
          count: items.length,
          examples: items.slice(0, 3),
        };
      });
    return [
      ["pending", "选出原片"],
      ["edited", "已修原片"],
      ["exports", "成片"],
    ].map(([stage, label]) => ({
      key: stage,
      label,
      kind: "stage",
      stage,
      count: rows.filter((p) =>
        stage === "pending"
          ? !p.edited
          : stage === "edited"
            ? p.edited
            : p.primary_export_id,
      ).length,
    }));
  }
  function folderPaths() {
    const paths = new Set([""]);
    for (const p of state.sourcePhotos)
      for (const dir of sourceDirs(p)) {
        let parent = "";
        for (const part of dir.split("/").filter(Boolean)) {
          parent = parent ? parent + "/" + part : part;
          paths.add(parent);
        }
      }
    return [...paths].sort();
  }
  function childFolders() {
    if (state.view !== "sd" || state.sourceFolder === "*") return [];
    const prefix = state.sourceFolder ? state.sourceFolder + "/" : "";
    return folderPaths().filter(
      (p) =>
        p.startsWith(prefix) &&
        p !== state.sourceFolder &&
        !p.slice(prefix.length).includes("/"),
    );
  }
  function resetLibrarySelection() {
    state.selected.library.clear();
    state.anchor.library = null;
    state.current = null;
    state.lastOperation = null;
    state.onlySelected = false;
  }
  function current() {
    return visible().find((p) => p.id === state.current);
  }
  function assets(p) {
    return p.assets || p.files || [];
  }
  return {
    selected,
    basePhotos,
    sourceDirs,
    visible,
    libraryFolderMode,
    libraryFolders,
    folderPaths,
    childFolders,
    resetLibrarySelection,
    current,
    assets,
  };
}
