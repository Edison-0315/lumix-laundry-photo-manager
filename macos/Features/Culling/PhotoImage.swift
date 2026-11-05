import SwiftUI
import PhotoWorkflowCore
actor ImagePipeline {
    static let shared = ImagePipeline()
    private var cache: [String: Data] = [:]
    func load(_ photo: PhotoGroup, maxPixel: Int) throws -> Data {
        let fingerprint = photo.files.map { file in
            let v = try? file.url.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
            return file.url.path + "\(v?.contentModificationDate?.timeIntervalSince1970 ?? 0):\(v?.fileSize ?? 0)"
        }.joined(separator: "|") + ":\(maxPixel)"
        if let data = cache[fingerprint] { return data }
        let data = try ImageReader.preview(photo, maxPixel: maxPixel)
        if cache.count >= 64 { cache.removeAll(keepingCapacity: true) }
        cache[fingerprint] = data
        return data
    }
}
struct PhotoImage: View {
    let photo: PhotoGroup
    let maxPixel: Int
    @State private var image: NSImage?
    @State private var error: String?
    var body: some View {
        ZStack {
            Rectangle().fill(.black.opacity(0.25))
            if let image {
                Image(nsImage: image).resizable().scaledToFit()
                    .accessibilityLabel("照片预览，\(photo.stem)")
                    .accessibilityIdentifier("photoPreviewImage:\(photo.id.rawValue)")
            }
            else if let error { Text(error).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center).padding(8) }
            else { ProgressView().controlSize(.small) }
        }
        .task(id: photo) {
            image = nil; error = nil
            do {
                let data = try await ImagePipeline.shared.load(photo, maxPixel: maxPixel)
                try Task.checkCancellation()
                guard let decoded = NSImage(data: data) else { throw CocoaError(.fileReadCorruptFile) }
                image = decoded
            } catch is CancellationError {} catch { self.error = "无法预览" }
        }
    }
}
