import SwiftUI
import AppKit
import PhotoWorkflowCore

/// SwiftUI owns the transform. AppKit handles precise events and draws CGImage.
struct ViewerCanvas: NSViewRepresentable {
    let image: CGImage?
    @Binding var viewport: ViewportTransform
    let previous: () -> Void
    let next: () -> Void
    let toggleSelection: () -> Void
    let close: () -> Void
    func makeNSView(context: Context) -> CanvasView { CanvasView() }
    func updateNSView(_ view: CanvasView, context: Context) {
        view.image = image
        view.readViewport = { viewport }
        view.writeViewport = { viewport = $0 }
        view.previous = previous; view.next = next; view.toggleSelection = toggleSelection; view.close = close
        view.needsDisplay = true
        view.updateDensity()
    }
    static func dismantleNSView(_ view: CanvasView, coordinator: ()) {
        view.readViewport = nil; view.writeViewport = nil
        view.previous = nil; view.next = nil; view.toggleSelection = nil; view.close = nil
    }
    final class CanvasView: NSView {
        var image: CGImage?
        var readViewport: (() -> ViewportTransform)?
        var writeViewport: ((ViewportTransform) -> Void)?
        var previous: (() -> Void)?
        var next: (() -> Void)?
        var toggleSelection: (() -> Void)?
        var close: (() -> Void)?
        private var lastDragPoint: CGPoint?
        private var densityUpdatePending = false
        override var isFlipped: Bool { true }
        override var acceptsFirstResponder: Bool { true }
        override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
        override init(frame frameRect: NSRect) {
            super.init(frame: frameRect)
            setAccessibilityElement(true); setAccessibilityRole(.image)
            setAccessibilityLabel("照片预览画布"); setAccessibilityIdentifier("viewerCanvas")
            setAccessibilityHelp("滚轮或捏合缩放，拖动平移；方向键切图，空格切换选中")
        }
        required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow(); updateDensity()
            // A photo change recreates the canvas. Keep an existing toolbar
            // responder so its next Space still activates that same control.
            if let window, window.firstResponder == nil || window.firstResponder === window || window.firstResponder is CanvasView {
                window.makeFirstResponder(self)
            }
        }
        override func viewDidChangeBackingProperties() { super.viewDidChangeBackingProperties(); updateDensity() }
        func updateDensity() {
            guard let window, let current = readViewport?(), current.backingScale != window.backingScaleFactor,
                  !densityUpdatePending else { return }
            densityUpdatePending = true
            // Never publish SwiftUI state from inside updateNSView/layout.
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.densityUpdatePending = false
                guard let density = self.window?.backingScaleFactor else { return }
                self.modify { $0.resize(to: self.bounds.size, backingScale: density) }
            }
        }
        var imageDrawingRect: CGRect? {
            guard let viewport = readViewport?() else { return nil }
            var rect = viewport.imageRect
            if abs(viewport.pixelScale - 1) < 0.0000001 {
                // SwiftUI can place the view itself between backing pixels.
                // Align its actual backing-store origin without rounding size.
                rect.origin = backingAlignedRect(rect, options: [.alignMinXNearest, .alignMaxXNearest, .alignMinYNearest, .alignMaxYNearest]).origin
            }
            return rect
        }
        override func draw(_ dirtyRect: NSRect) {
            NSColor.black.setFill(); bounds.fill()
            guard let image, let rect = imageDrawingRect, let context = NSGraphicsContext.current?.cgContext else { return }
            context.saveGState(); context.interpolationQuality = .high
            context.translateBy(x: rect.minX, y: rect.maxY); context.scaleBy(x: 1, y: -1)
            context.draw(image, in: CGRect(origin: .zero, size: rect.size))
            context.restoreGState()
        }
        override func scrollWheel(with event: NSEvent) {
            // AppKit precise deltas are points; conventional wheel deltas are lines.
            let pixels = -event.scrollingDeltaY * (event.hasPreciseScrollingDeltas ? 1 : 16)
            let point = convert(event.locationInWindow, from: nil)
            modify { $0.scroll(pixels: pixels, anchor: point) }
        }
        override func magnify(with event: NSEvent) {
            let point = convert(event.locationInWindow, from: nil)
            modify { $0.zoom(factor: max(0.01, 1 + event.magnification), anchor: point) }
        }
        override func mouseDown(with event: NSEvent) {
            window?.makeFirstResponder(self)
            lastDragPoint = convert(event.locationInWindow, from: nil)
            NSCursor.closedHand.push()
        }
        override func mouseDragged(with event: NSEvent) {
            let point = convert(event.locationInWindow, from: nil)
            guard let lastDragPoint else { return }
            modify { $0.pan(by: CGSize(width: point.x - lastDragPoint.x, height: point.y - lastDragPoint.y)) }
            self.lastDragPoint = point
        }
        override func mouseUp(with event: NSEvent) {
            if lastDragPoint != nil { NSCursor.pop() }
            lastDragPoint = nil
        }
        override func resignFirstResponder() -> Bool {
            if lastDragPoint != nil { NSCursor.pop(); lastDragPoint = nil }
            return super.resignFirstResponder()
        }
        override func keyDown(with event: NSEvent) {
            guard event.modifierFlags.intersection([.command, .control, .option]).isEmpty else { super.keyDown(with: event); return }
            switch event.keyCode {
            case 49: if !event.isARepeat { toggleSelection?() }
            case 123: previous?()
            case 124: next?()
            case 53: close?()
            default: super.keyDown(with: event)
            }
        }
        private func modify(_ change: (inout ViewportTransform) -> Void) {
            guard var value = readViewport?() else { return }
            change(&value); writeViewport?(value); needsDisplay = true
        }
    }
}
