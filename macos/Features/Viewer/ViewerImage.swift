import SwiftUI
import ImageIO
import PhotoWorkflowCore

/// CGImage is immutable; no mutable decoder or AppKit object crosses actors.
struct PreviewBitmap: @unchecked Sendable {
    let image: CGImage
}
private actor ViewerDecoder {
    static let shared = ViewerDecoder()
    func load(_ photo: PhotoGroup) async throws -> PreviewBitmap {
        let data = try await ImagePipeline.shared.load(photo, maxPixel: 4096)
        try Task.checkCancellation()
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, [kCGImageSourceShouldCacheImmediately: true] as CFDictionary)
        else { throw CocoaError(.fileReadCorruptFile) }
        return PreviewBitmap(image: image)
    }
}

/// One instance per photo: switching photos cancels loading and starts in fit mode.
struct ViewerImage: View {
    let photo: PhotoGroup
    let previous: () -> Void
    let next: () -> Void
    let toggleSelection: () -> Void
    let close: () -> Void
    @State private var bitmap: PreviewBitmap?
    @State private var error: String?
    @State private var retry = 0
    @State private var viewport = ViewportTransform(image: .zero, viewport: .zero)

    var body: some View {
        VStack(spacing: 10) {
            HStack {
                Button("适应窗口") { viewport.fit() }.accessibilityIdentifier("viewerFit")
                Button("100%") { viewport.actualSize() }
                    .help("一个解码预览像素对应一个显示像素；预览最长边为 4096 像素")
                    .accessibilityIdentifier("viewerActualSize")
                Button { zoom(0.8) } label: { Image(systemName: "minus.magnifyingglass") }
                    .accessibilityLabel("缩小").accessibilityIdentifier("viewerZoomOut")
                Button { zoom(1.25) } label: { Image(systemName: "plus.magnifyingglass") }
                    .accessibilityLabel("放大").accessibilityIdentifier("viewerZoomIn")
                Text("\(Int((viewport.pixelScale * 100).rounded()))%")
                    .monospacedDigit().frame(minWidth: 48).accessibilityIdentifier("viewerScale")
                Spacer()
                Text(viewport.isFitted ? "适应窗口" : "自由缩放")
                    .foregroundStyle(.secondary).accessibilityIdentifier("viewerMode")
            }
            .controlSize(.small)
            .padding(10)
            .modifier(ViewerControlSurface())
            .disabled(bitmap == nil)
            GeometryReader { geometry in
                ZStack {
                    Color.black.opacity(0.35)
                    // Keep the keyboard responder alive while loading or showing errors.
                    ViewerCanvas(image: bitmap?.image, viewport: $viewport, previous: previous, next: next,
                                 toggleSelection: toggleSelection, close: close)
                    if let error {
                        VStack(spacing: 12) {
                            Text(error).multilineTextAlignment(.center)
                            Button("重试预览") { self.error = nil; retry += 1 }.accessibilityIdentifier("viewerRetry")
                        }.padding()
                    } else if bitmap == nil { ProgressView("正在载入预览…") }
                }
                .clipped()
                .onChange(of: geometry.size, initial: true) { _, size in
                    viewport.resize(to: size, backingScale: viewport.backingScale)
                }
                .task(id: retry) {
                    bitmap = nil; error = nil
                    do {
                        let loaded = try await ViewerDecoder.shared.load(photo)
                        try Task.checkCancellation()
                        viewport = ViewportTransform(image: CGSize(width: loaded.image.width, height: loaded.image.height),
                                                     viewport: viewport.viewportSize, backingScale: viewport.backingScale)
                        bitmap = loaded
                    } catch {
                        guard !Task.isCancelled else { return }
                        self.error = "无法预览此照片。原文件保持不变；RAW 支持取决于当前系统。"
                    }
                }
            }
            HStack {
                Text(photo.stem).lineLimit(1)
                Spacer()
                if let bitmap { Text("预览 \(bitmap.image.width) × \(bitmap.image.height) 像素") }
            }.font(.caption).foregroundStyle(.secondary)
            Text("滚轮或捏合缩放 · 拖动平移 · 画布聚焦时方向键切图、空格选片")
                .font(.caption2).foregroundStyle(.secondary)
        }
    }
    private func zoom(_ factor: CGFloat) {
        viewport.zoom(factor: factor, anchor: CGPoint(x: viewport.viewportSize.width / 2, y: viewport.viewportSize.height / 2))
    }
}

/// Keep the image unobstructed; use glass only for the preview's control strip.
private struct ViewerControlSurface: ViewModifier {
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.colorSchemeContrast) private var contrast

    @ViewBuilder func body(content: Content) -> some View {
        if reduceTransparency || contrast == .increased {
            content.background(.background, in: .rect(cornerRadius: 14))
                .overlay { RoundedRectangle(cornerRadius: 14).strokeBorder(.primary.opacity(0.6), lineWidth: 1).allowsHitTesting(false) }
        } else if #available(macOS 26.0, *) {
            content.glassEffect(.regular.interactive(), in: .rect(cornerRadius: 14))
        } else {
            content.background(.regularMaterial, in: .rect(cornerRadius: 14))
        }
    }
}
