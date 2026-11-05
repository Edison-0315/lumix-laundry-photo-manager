import AppKit
import XCTest

final class MarqueeAutoscrollTests: XCTestCase {
    @MainActor func testEdgeScrollingMovesWhilePointerStaysAtEdgeAndStopsAtLimits() {
        let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 300, height: 200))
        let document = FlippedDocument(frame: NSRect(x: 0, y: 0, width: 300, height: 1000))
        scroll.documentView = document
        let driver = MarqueeAutoscroll(); driver.view = document
        XCTAssertFalse(driver.scroll(at: CGPoint(x: 100, y: 100)))
        for _ in 0..<20 {
            XCTAssertTrue(driver.scroll(at: CGPoint(x: 100, y: scroll.contentView.bounds.maxY - 2)))
        }
        XCTAssertGreaterThan(scroll.contentView.bounds.minY, 200)
        let before = scroll.contentView.bounds.minY
        XCTAssertTrue(driver.scroll(at: CGPoint(x: 100, y: before + 2)))
        XCTAssertLessThan(scroll.contentView.bounds.minY, before)
        scroll.contentView.scroll(to: CGPoint(x: 0, y: 800))
        XCTAssertFalse(driver.scroll(at: CGPoint(x: 100, y: 998)))
        XCTAssertEqual(scroll.contentView.bounds.minY, 800, accuracy: 0.1)
        scroll.contentView.scroll(to: .zero)
        XCTAssertFalse(driver.scroll(at: CGPoint(x: 100, y: 2)))
        XCTAssertFalse(driver.scroll(at: CGPoint(x: -100, y: 198)))
        XCTAssertEqual(scroll.contentView.bounds.minY, 0, accuracy: 0.1)
        driver.view = nil
        XCTAssertFalse(driver.scroll(at: CGPoint(x: 100, y: 198)))
    }
    private final class FlippedDocument: NSView { override var isFlipped: Bool { true } }
}
