/** Compatibility facade. All UI modules share this single application session. */
import { createState } from "./core/state.js";
import { createQueries } from "./core/queries.js";
export { $, el, button, toast, error } from "./core/dom.js";
export const state = createState();
export const {
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
} = createQueries(state);
