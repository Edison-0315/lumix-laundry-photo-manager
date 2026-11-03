import {
  state,
  $,
  visible,
  current,
  assets,
  el,
  button,
  toast,
  error,
} from "../store.js";
import { api } from "../api.js";
import { preview, invalidateLibraryPreviews } from "../previews.js";
import { openViewer, updatePhotoThumbnail } from "../gallery.js";
import { setSidebarScene } from "../sidebar-motion.js";
import { confirmAction } from "../core/modal.js";

export function createInspector({ refresh, start }) {
  let inspectorRevision = 0;
  const safe =
    (fn) =>
    (...args) =>
      Promise.resolve()
        .then(() => fn(...args))
        .catch(error);
  async function renderInspector() {
    const box = $("#inspector"),
      p = current(),
      rev = ++inspectorRevision;
    box.replaceChildren();
    if (!p) $("#ambient-photo").style.backgroundImage = "none";
    if (!p) {
      const first = visible()[0];
      if (first)
        preview(
          first,
          state.view === "library" && state.stage === "exports"
            ? "export-thumb"
            : "thumb",
          state.view === "sd" ? state.scanId : null,
        )
          .then((result) => {
            if (rev === inspectorRevision)
              setSidebarScene(
                result.url?.startsWith("data:image/") ? result.url : null,
              );
          })
          .catch(() => {
            if (rev === inspectorRevision) setSidebarScene(null);
          });
      else setSidebarScene(null);
      const empty = el("div", "empty");
      empty.append(
        el("span", "", "选择一张照片"),
        el("small", "", "单击选择 · 双击查看大图\n拖动可批量选择"),
      );
      box.append(empty);
      return;
    }
    const thumb = el("div", "large-thumb"),
      badge = el(
        "span",
        "format-chip",
        [
          ...new Set(
            assets(p)
              .filter((a) => a.kind === "jpeg" || a.kind === "raw")
              .map((a) => (a.kind === "raw" ? "RAW" : "JPG")),
          ),
        ].join(" + "),
      );
    badge.setAttribute("aria-label", "文件格式 " + badge.textContent);
    const showThumb = (im) => thumb.replaceChildren(im, badge);
    showThumb(el("span", "muted small", "正在读取…"));
    thumb.onclick = () => openViewer(p.id, thumb);
    box.append(thumb, el("div", "file-title", p.stem));
    const dl = el("dl");
    const add = (k, v) => dl.append(el("dt", "", k), el("dd", "", v));
    const fields = new Map();
    for (const label of [
      "文件大小",
      "拍摄日期",
      "相机型号",
      "镜头焦段",
      "镜头型号",
      "相机参数",
    ]) {
      add(label, "读取中…");
      fields.set(label, dl.lastElementChild);
    }
    const fillDetails = (details) => {
      const size = (value) =>
        value == null
          ? "不可用"
          : value < 1024
            ? value + " B"
            : value < 1048576
              ? (value / 1024).toFixed(1) + " KB"
              : (value / 1048576).toFixed(1).replace(/\.0$/, "") + " MB";
      const files = (details.files || []).map(
        (f) =>
          (({ jpeg: "JPG", raw: "RAW", export: "成片", xmp: "XMP" })[f.kind] ||
            f.name) +
          " " +
          size(f.bytes),
      );
      fields.get("文件大小").textContent =
        (details.total_bytes != null
          ? size(details.total_bytes) + (files.length > 1 ? "（合计）" : "")
          : "未完整读取") + (files.length > 1 ? "\n" + files.join("\n") : "");
      fields.get("拍摄日期").textContent =
        details.captured_at || p.captured_at?.replace("T", " ") || "未记录";
      fields.get("相机型号").textContent = details.camera || "未记录";
      fields.get("镜头焦段").textContent = details.focal_length || "未记录";
      fields.get("镜头型号").textContent = details.lens || "未记录";
      fields.get("相机参数").textContent =
        [
          details.aperture,
          details.shutter,
          details.iso ? "ISO " + details.iso : null,
          details.exposure_bias,
        ]
          .filter(Boolean)
          .join(" · ") || "未记录";
    };
    api("get_photo_details", p.id, state.view === "sd" ? state.scanId : null)
      .then((details) => {
        if (rev === inspectorRevision) fillDetails(details);
      })
      .catch(() => {
        if (rev === inspectorRevision) fillDetails({});
      });
    if (state.view === "library") {
      add(
        "人物",
        state.people.find((person) => person.id === p.person_id)?.name ||
          "待分类",
      );
      add("修图阶段", p.edited ? "已修原片" : "选出原片");
      if (p.opened_at)
        add("PS请求", p.opened_at.slice(0, 16).replace("T", " "));
    }
    box.append(dl);
    if (p.error || p.missing)
      box.append(
        el(
          "p",
          "warning small",
          p.missing ? "部分文件缺失，请定位原文件后恢复。" : p.error,
        ),
      );
    if (state.view === "library") {
      if (state.stage !== "exports") {
        box.append(el("h3", "", "Photoshop"));
        const options = el("div", "format-options");
        const available = new Set(assets(p).map((a) => a.kind));
        if (!available.has(state.psFormat))
          state.psFormat = available.has("raw") ? "raw" : "jpeg";
        for (const format of ["jpeg", "raw"]) {
          const b = button(
            format === "jpeg" ? "JPEG" : "RAW",
            () => {
              state.psFormat = format;
              renderInspector();
            },
            state.psFormat === format ? "active" : "",
          );
          b.disabled = !available.has(format);
          options.append(b);
        }
        box.append(options);
        const ps = button(
          "用 Photoshop 打开",
          safe(async () => {
            await api("open_photoshop", p.id, state.psFormat);
            invalidateLibraryPreviews();
            toast("已请求Photoshop打开；修完后请手动标记");
            await refresh();
          }),
          "primary wide",
        );
        ps.disabled = state.busy;
        box.append(ps, el("p", "small muted", "打开不会自动标记已修。"));
      }
      box.append(el("div", "divider"), el("h3", "", "关联成片"));
      box.append(
        button(
          "选择导出图片并关联",
          safe(() => start("choose_and_link_export", p.id)),
          "outline wide",
        ),
      );
      const exports = assets(p).filter((a) => a.kind === "export");
      if (exports.length) {
        box.append(
          button(
            "打开成片文件夹",
            safe(() => api("open_export_folder", p.id)),
            "wide",
          ),
        );
        for (const a of exports) {
          const row = el("div", "export-version");
          row.append(
            el("div", "", a.path.split(/[\\/]/).pop()),
            el(
              "div",
              "small muted",
              a.id === p.primary_export_id ? "当前封面" : "导出版本",
            ),
          );
          if (a.id !== p.primary_export_id)
            row.append(
              button(
                "设为封面",
                safe(async () => {
                  await api("set_export_cover", p.id, a.id);
                  invalidateLibraryPreviews();
                  await refresh();
                }),
              ),
            );
          row.append(
            button("解除此版本关联", () =>
              confirmAction(
                "解除成片关联",
                "此版本不再显示为成片，复制文件移入照片库内的“取消关联保留”目录；原片和修图阶段保留。",
                () => start("unlink_export", p.id, a.id),
              ),
            ),
          );
          box.append(row);
        }
      } else
        box.append(
          el("p", "small muted", "选一张修好后导出的图片，保留原片关联。"),
        );
      if (p.missing)
        box.append(
          button(
            "定位缺失文件",
            safe(() => start("relink_missing", p.id)),
            "outline wide",
          ),
        );
      if (state.lastOperation?.photoId === p.id)
        box.append(
          button(
            "撤销最近一次归档",
            safe(() => start("undo_operation", state.lastOperation.id)),
            "wide",
          ),
        );
      box.querySelectorAll("button").forEach((b) => {
        b.dataset.mutation = "true";
        if (state.busy) b.disabled = true;
      });
    }
    const details = el("details");
    details.append(el("summary", "muted small", "文件位置"));
    for (const a of assets(p)) details.append(el("p", "path", a.path));
    box.append(el("div", "divider"), details);
    try {
      const result = await preview(
        p,
        state.view === "library" && state.stage === "exports"
          ? "export-thumb"
          : "thumb",
        state.view === "sd" ? state.scanId : null,
      );
      if (rev !== inspectorRevision) return;
      if (result.url) {
        const im = el("img");
        im.src = result.url;
        im.alt = p.stem;
        showThumb(im);
        if (result.url.startsWith("data:image/")) {
          $("#ambient-photo").style.backgroundImage =
            'url("' + result.url.replaceAll('"', "%22") + '")';
          setSidebarScene(result.url);
        }
        updatePhotoThumbnail(p.id, result.url);
      } else {
        showThumb(el("span", "muted small", "无法预览"));
        setSidebarScene(null);
      }
    } catch {
      if (rev === inspectorRevision) {
        showThumb(el("span", "muted small", "无法预览"));
        setSidebarScene(null);
      }
    }
  }
  return renderInspector;
}
