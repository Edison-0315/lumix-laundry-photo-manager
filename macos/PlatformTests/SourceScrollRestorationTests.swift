import AppKit
import XCTest

final class SourceScrollRestorationTests: XCTestCase {
    @MainActor func testRestoresOnceClampsToDocumentAndReportsLaterScrolling() {
        let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 300, height: 200))
        let document = FlippedDocument(frame: NSRect(x: 0, y: 0, width: 300, height: 2000))
        scroll.documentView = document
        let probe = SourceScrollProbe(frame: document.bounds); document.addSubview(probe)
        probe.initialOffset = 650
        probe.restoreIfReady()
        XCTAssertEqual(scroll.contentView.bounds.minY, 650, accuracy: 0.1)
        scroll.contentView.scroll(to: CGPoint(x: 0, y: 900))
        probe.restoreIfReady()
        XCTAssertEqual(scroll.contentView.bounds.minY, 900, accuracy: 0.1)
        var recorded: Double?
        probe.onOffset = { recorded = $0 }; probe.recordOffset()
        XCTAssertEqual(recorded, 900)
        probe.detach(); probe.removeFromSuperview()
        document.addSubview(probe); probe.initialOffset = 550; probe.restoreIfReady()
        XCTAssertEqual(scroll.contentView.bounds.minY, 550, accuracy: 0.1)
        probe.detach(); probe.removeFromSuperview()
        let shorter = SourceScrollProbe(frame: document.bounds); document.addSubview(shorter)
        shorter.initialOffset = 5000; shorter.restoreIfReady()
        XCTAssertEqual(scroll.contentView.bounds.minY, 1800, accuracy: 0.1)
        shorter.detach()
    }
    private final class FlippedDocument: NSView { override var isFlipped: Bool { true } }
}
