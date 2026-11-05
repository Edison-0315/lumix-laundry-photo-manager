import SwiftUI
import PhotoWorkflowCore
struct PhotoInspector: View {
    let photo: PhotoGroup?
    var body: some View {
        ScrollView {
            if let photo { InspectorDetails(photo: photo).id(photo) }
            else { ContentUnavailableView("选择一张照片", systemImage: "photo", description: Text("单击选择，双击查看大图。")) }
        }
    }
}
private struct InspectorDetails: View {
    let photo: PhotoGroup
    @State private var details: PhotoDetails?
    @State private var revision = 0
    private var info: ImageInfo { details?.info ?? ImageInfo() }
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            PhotoImage(photo: photo, maxPixel: 640).aspectRatio(4/3, contentMode: .fit)
            Text(photo.stem).font(.headline).textSelection(.enabled)
            LabeledContent("拍摄日期", value: info.capturedAt?.replacingOccurrences(of: "T", with: " ") ?? "未记录")
            LabeledContent("相机", value: info.camera ?? "未记录")
            LabeledContent("镜头", value: info.lens ?? "未记录")
            LabeledContent("快门", value: info.shutter ?? "未记录").accessibilityIdentifier("detailShutter")
            LabeledContent("光圈", value: info.aperture ?? "未记录").accessibilityIdentifier("detailAperture")
            LabeledContent("ISO", value: info.iso ?? "未记录").accessibilityIdentifier("detailISO")
            LabeledContent("焦距", value: info.focalLength ?? "未记录")
            LabeledContent("曝光补偿", value: info.exposureBias ?? "未记录")
            LabeledContent("像素尺寸", value: info.dimensions ?? "未记录")
            if let warning = photo.warning { Text(warning).font(.caption).foregroundStyle(.orange) }
            Divider()
            HStack {
                Text("文件信息").font(.subheadline)
                Spacer()
                Button("刷新") { revision += 1 }.disabled(details == nil)
            }
            if let details {
                LabeledContent("合计", value: details.totalBytes.map(size) ?? "部分文件不可读，无法合计")
                ForEach(Array(details.files.enumerated()), id: \.offset) { _, file in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(file.asset.kind.rawValue.uppercased()).font(.caption.bold())
                            Spacer()
                            Text(file.bytes.map(size) ?? "大小未知").font(.caption)
                        }
                        Text(file.asset.url.path).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                        if let error = file.error { Text(error).font(.caption).foregroundStyle(.orange) }
                    }
                }
            } else { ProgressView("读取详情…").controlSize(.small) }
        }
        .padding()
        .task(id: revision) {
            details = nil
            let value = await Task.detached(priority: .userInitiated) { PhotoDetails.read(photo) }.value
            guard !Task.isCancelled else { return }
            details = value
        }
    }
    private func size(_ bytes: Int64) -> String {
        ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
    }
}
