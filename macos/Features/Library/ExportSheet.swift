import SwiftUI
import PhotoWorkflowCore

struct ExportSheet: View {
    @Bindable var model: LibraryModel
    let id: PhotoID
    @Environment(\.dismiss) private var dismiss
    private var photo: CatalogPhoto? { model.catalog?.photos.first { $0.id == id } }
    private var versions: [CatalogAsset] { photo?.assets.filter { $0.kind == .export } ?? [] }
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("成片版本").font(.title2).accessibilityIdentifier("exportSheet")
            Text(photo?.photo.stem ?? "照片").foregroundStyle(.secondary)
            if versions.isEmpty { Text("尚未关联成片，可选择导出的 JPEG、PNG、TIFF 或 WebP。").foregroundStyle(.secondary) }
            List(versions) { asset in
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(URL(fileURLWithPath: asset.path).lastPathComponent).lineLimit(1)
                        if let problem = asset.problem { Text(problem).font(.caption).foregroundStyle(.orange) }
                        if photo?.photo.primaryExportID == asset.id { Label("封面", systemImage: "checkmark.seal").font(.caption) }
                    }
                    Spacer()
                    Button("设为封面") { model.setCover(id, asset: asset.id) }
                        .disabled(!model.canWrite || model.busy || photo?.photo.primaryExportID == asset.id)
                        .accessibilityIdentifier("exportCover:\(asset.id)")
                    Button("Finder") { model.revealAsset(asset) }.disabled(asset.url == nil)
                    Button("解除关联") { model.unlinkExport(id, asset: asset.id) }.disabled(!model.canWrite || model.busy)
                        .accessibilityIdentifier("unlinkExport:\(asset.id)")
                }.padding(.vertical, 4)
            }
            Text("解除关联后文件保留在照片库内；关联成片会将原片归入已修。").font(.caption).foregroundStyle(.secondary)
            if model.busy { ProgressView(model.progress).controlSize(.small) }
            if let error = model.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
            HStack {
                Button("关闭") { dismiss() }.keyboardShortcut(.cancelAction).disabled(model.busy)
                Spacer()
                Button("关联导出图片…") { model.chooseExport(id) }.disabled(!model.canWrite || model.busy).accessibilityIdentifier("linkExport")
            }
        }.padding(24).frame(width: 650, height: 390).interactiveDismissDisabled(model.busy)
    }
}

struct EditorSettings: View {
    @AppStorage("photoshopPath") private var path = ""
    var body: some View {
        LabeledContent("Photoshop") {
            Text(path.isEmpty ? "自动查找已安装的 Photoshop" : URL(fileURLWithPath: path).lastPathComponent).lineLimit(1)
            Button("选择…") { if let url = ExternalEditor.choose() { path = url.path } }
        }
    }
}
