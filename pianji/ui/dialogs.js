/** Compatibility exports; implementations are grouped by feature. */
export { modal, confirmAction } from "./core/modal.js";
export { settingsDialog } from "./features/settings-dialog.js";
export { importDialog, newActivityDialog } from "./features/import-dialogs.js";
export {
  deletePeopleDialog,
  assignDialog,
  newPersonDialog,
  managePeopleDialog,
} from "./features/people-dialogs.js";
export {
  deleteActivityDialog,
  deleteDialog,
  trashDialog,
} from "./features/trash-dialogs.js";
export { resultDialog } from "./features/result-dialog.js";
