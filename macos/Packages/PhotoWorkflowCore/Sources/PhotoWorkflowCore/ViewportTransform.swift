import Foundation

/// Image pixels → top-left-origin canvas points. No file or UI dependencies.
public struct ViewportTransform: Sendable {
    public let imageSize: CGSize
    public private(set) var viewportSize: CGSize
    public private(set) var backingScale: CGFloat
    public private(set) var scale: CGFloat = 1
    public private(set) var offset: CGPoint = .zero
    public private(set) var isFitted = true
    /// Display pixels per decoded preview pixel, independent of Retina density.
    public var pixelScale: CGFloat { scale * backingScale }
    public var imageRect: CGRect {
        guard usable else { return .zero }
        let width = imageSize.width * scale, height = imageSize.height * scale
        return CGRect(x: (viewportSize.width - width) / 2 + offset.x,
                      y: (viewportSize.height - height) / 2 + offset.y,
                      width: width, height: height)
    }
    private var usable: Bool {
        imageSize.width > 0 && imageSize.height > 0 && viewportSize.width > 0 && viewportSize.height > 0
    }
    public init(image: CGSize, viewport: CGSize, backingScale: CGFloat = 1) {
        imageSize = Self.clean(image); viewportSize = Self.clean(viewport)
        self.backingScale = Self.density(backingScale)
        fit()
    }
    public mutating func fit() {
        offset = .zero; isFitted = true
        guard usable else { scale = 1 / backingScale; return }
        scale = min(viewportSize.width / imageSize.width, viewportSize.height / imageSize.height, 1 / backingScale)
        alignActualPixels()
    }
    public mutating func actualSize() {
        scale = 1 / backingScale; offset = .zero; isFitted = false
        alignActualPixels()
    }
    public mutating func zoom(factor: CGFloat, anchor: CGPoint) {
        guard usable, factor.isFinite, factor > 0, anchor.x.isFinite, anchor.y.isFinite else { return }
        let next = min(16 / backingScale, max(0.02 / backingScale, scale * factor))
        let rect = imageRect
        let x = min(rect.maxX, max(rect.minX, anchor.x)) - viewportSize.width / 2
        let y = min(rect.maxY, max(rect.minY, anchor.y)) - viewportSize.height / 2
        let ratio = next / scale
        offset = CGPoint(x: x - (x - offset.x) * ratio, y: y - (y - offset.y) * ratio)
        scale = next; isFitted = false
        // Zoom may leave empty space to preserve the cursor's image pixel.
        // Keep at least a small visible strip; don't apply ordinary pan bounds.
        offset.x = Self.clamp(offset.x, limit: Self.zoomLimit(imageSize.width * scale, viewportSize.width))
        offset.y = Self.clamp(offset.y, limit: Self.zoomLimit(imageSize.height * scale, viewportSize.height))
        alignActualPixels()
    }
    public mutating func scroll(pixels: CGFloat, anchor: CGPoint) {
        guard pixels.isFinite else { return }
        zoom(factor: exp(min(0.4, max(-0.4, -pixels * 0.0018))), anchor: anchor)
    }
    public mutating func pan(by delta: CGSize) {
        guard usable, delta.width.isFinite, delta.height.isFinite else { return }
        offset.x = Self.clamp(offset.x + delta.width, limit: max(0, (imageSize.width * scale - viewportSize.width) / 2))
        offset.y = Self.clamp(offset.y + delta.height, limit: max(0, (imageSize.height * scale - viewportSize.height) / 2))
        isFitted = false
        alignActualPixels()
    }
    public mutating func resize(to size: CGSize, backingScale: CGFloat) {
        let oldPixelScale = pixelScale
        viewportSize = Self.clean(size); self.backingScale = Self.density(backingScale)
        if isFitted { fit() }
        else {
            scale = oldPixelScale / self.backingScale
            pan(by: .zero)
        }
    }
    /// At 100%, preserve size and align only the origin to backing pixels.
    /// Store the aligned offset so future cursor anchors use the actual geometry.
    private mutating func alignActualPixels() {
        guard usable, abs(pixelScale - 1) < 0.0000001 else { return }
        let origin = imageRect.origin
        offset.x += (origin.x * backingScale).rounded() / backingScale - origin.x
        offset.y += (origin.y * backingScale).rounded() / backingScale - origin.y
    }
    private static func density(_ value: CGFloat) -> CGFloat { value.isFinite && value > 0 ? value : 1 }
    private static func clean(_ size: CGSize) -> CGSize {
        CGSize(width: size.width.isFinite ? max(0, size.width) : 0,
               height: size.height.isFinite ? max(0, size.height) : 0)
    }
    private static func clamp(_ value: CGFloat, limit: CGFloat) -> CGFloat { min(limit, max(-limit, value)) }
    private static func zoomLimit(_ image: CGFloat, _ canvas: CGFloat) -> CGFloat {
        (image + canvas) / 2 - min(48, image / 2, canvas / 2)
    }
}
