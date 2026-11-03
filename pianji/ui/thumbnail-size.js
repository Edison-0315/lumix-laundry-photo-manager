/** Slider state updates immediately; gallery layout commits at most once per frame. */
import { state, $, error } from './store.js';
import { api } from './api.js';
import { syncThumbnailControl } from './sidebar-motion.js';

let frame = 0, saveTimer = 0;

export function setThumbnailSize(value) {
  state.thumbSize = Math.max(80, Math.min(720, Number(value) || 240));
  $('#thumb-size').value = state.thumbSize;
  syncThumbnailControl(state.thumbSize);

  if (!frame) frame = requestAnimationFrame(() => {
    frame = 0;
    const grid = $('#gallery');
    grid.dispatchEvent(new Event('layoutchange'));
    grid.style.setProperty('--thumb-size', state.thumbSize + 'px');
  });

  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api('save_settings', {
    thumbnail_size: state.thumbSize,
  }).catch(error), 500);
}
