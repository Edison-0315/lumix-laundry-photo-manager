import AppKit
import XCTest
import PhotoWorkflowCore

final class ViewerCanvasTests: XCTestCase {
    /// Represents a native button reachable with keyboard navigation enabled.
    private final class KeyboardButton: NSButton {
        override var acceptsFirstResponder: Bool { true }
    }
    @MainActor func testSwitchingPhotoPreservesToolbarKeyboardFocus() {
        _ = NSApplication.shared
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 800, height: 600), styleMask: [.titled], backing: .buffered, defer: false)
        let root = NSView(frame: window.contentLayoutRect); window.contentView = root
        let first = ViewerCanvas.CanvasView(frame: root.bounds); root.addSubview(first)
        let nextButton = KeyboardButton(title: "下一张", target: nil, action: nil); root.addSubview(nextButton)
        XCTAssertTrue(window.makeFirstResponder(nextButton))
        first.removeFromSuperview()
        let next = ViewerCanvas.CanvasView(frame: root.bounds); root.addSubview(next)
        // Recreating a photo must not change where a second Space is delivered.
        XCTAssertTrue(window.firstResponder === nextButton)
        window.contentView = nil
    }
    @MainActor func testActualSizeDrawingAlignsFractionalCanvasPlacement() throws {
        _ = NSApplication.shared
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 900, height: 700), styleMask: [.titled], backing: .buffered, defer: false)
        let root = NSView(frame: window.contentLayoutRect); window.contentView = root
        let canvas = ViewerCanvas.CanvasView(frame: CGRect(x: 0.25, y: 0.25, width: 801, height: 600)); root.addSubview(canvas)
        var transform = ViewportTransform(image: CGSize(width: 4001, height: 2001), viewport: canvas.bounds.size, backingScale: window.backingScaleFactor)
        transform.actualSize()
        canvas.readViewport = { transform }
        let rect = try XCTUnwrap(canvas.imageDrawingRect)
        let backing = canvas.convertToBacking(rect.origin)
        XCTAssertEqual(backing.x.truncatingRemainder(dividingBy: 1), 0, accuracy: 0.000001)
        XCTAssertEqual(backing.y.truncatingRemainder(dividingBy: 1), 0, accuracy: 0.000001)
        XCTAssertEqual(rect.size, transform.imageRect.size)
        window.contentView = nil
    }
    @MainActor func testSwitchingPhotoKeepsCanvasKeyboardNavigation() {
        _ = NSApplication.shared
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 800, height: 600), styleMask: [.titled], backing: .buffered, defer: false)
        let root = NSView(frame: window.contentLayoutRect); window.contentView = root
        let first = ViewerCanvas.CanvasView(frame: root.bounds); root.addSubview(first)
        XCTAssertTrue(window.firstResponder === first)
        first.removeFromSuperview()
        let next = ViewerCanvas.CanvasView(frame: root.bounds); root.addSubview(next)
        XCTAssertTrue(window.firstResponder === next)
        window.contentView = nil
    }
}
