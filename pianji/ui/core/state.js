/** Creates one application session. No DOM, API or persistent settings access. */
export function createState() {
  const state = {
    view: "sd",
    source: null,
    sourceFolder: "",
    format: "all",
    scanId: null,
    sourcePhotos: [],
    photos: [],
    activities: [],
    people: [],
    activity: null,
    person: "all",
    stage: "all",
    date: "all",
    onlySelected: false,
    selected: { sd: new Set(), library: new Set() },
    anchor: { sd: null, library: null },
    current: null,
    thumbSize: 240,
    settings: {},
    busy: false,
    psFormat: "raw",
    lastOperation: null,
  };
  state.browse = "folders";
  state.peopleCollapsed = false;
  state.readFormat = "both";
  return state;
}
