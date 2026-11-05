import XCTest
@testable import PhotoWorkflowCore

final class ViewportTests: XCTestCase {
    // Catch width-only fit and accidental enlargement of small previews.
    func testFitHandlesLandscapePortraitAndSmallRetinaPreview() {
        let landscape = ViewportTransform(image: CGSize(width: 4000, height: 2000), viewport: CGSize(width: 1000, height: 800), backingScale: 2)
        XCTAssertEqual(landscape.scale, 0.25)
        XCTAssertEqual(landscape.imageRect, CGRect(x: 0, y: 150, width: 1000, height: 500))
        let portrait = ViewportTransform(image: CGSize(width: 2000, height: 4000), viewport: CGSize(width: 1000, height: 800))
        XCTAssertEqual(portrait.scale, 0.2)
        let small = ViewportTransform(image: CGSize(width: 200, height: 100), viewport: CGSize(width: 1000, height: 800), backingScale: 2)
        XCTAssertEqual(small.imageRect, CGRect(x: 450, y: 375, width: 100, height: 50))
    }
    // Catch zooming around the center instead of the actual cursor.
    func testCursorAnchorRemainsWithinTwoDisplayPixels() {
        for backing: CGFloat in [1, 2] {
            var view = ViewportTransform(image: CGSize(width: 4000, height: 2000), viewport: CGSize(width: 1000, height: 800), backingScale: backing)
            view.zoom(factor: 2, anchor: CGPoint(x: 750, y: 300))
            // Cursor originally touches image pixel(3000,600).
            XCTAssertEqual(view.imageRect.minX + 3000 * view.scale, 750, accuracy: 2 / backing)
            XCTAssertEqual(view.imageRect.minY + 600 * view.scale, 300, accuracy: 2 / backing)
            XCTAssertEqual(view.offset, CGPoint(x: -250, y: 100))
        }
    }
    func testLetterboxClampsToImageEdgeWithoutRecentering() {
        var view = ViewportTransform(image: CGSize(width: 4000, height: 2000), viewport: CGSize(width: 1000, height: 800))
        view.zoom(factor: 0.5, anchor: CGPoint(x: 750, y: 0))
        XCTAssertEqual(view.imageRect.minY, 150, accuracy: 0.001)
        XCTAssertEqual(view.imageRect.minX + 3000 * view.scale, 750, accuracy: 0.001)
        XCTAssertNotEqual(view.offset, .zero)
    }
    func testScrollAccumulatesAndClampsDisplayScale() {
        var view = ViewportTransform(image: CGSize(width: 4000, height: 2000), viewport: CGSize(width: 1000, height: 800), backingScale: 2)
        view.scroll(pixels: -100, anchor: CGPoint(x: 500, y: 400))
        view.scroll(pixels: -100, anchor: CGPoint(x: 500, y: 400))
        XCTAssertEqual(view.scale, 0.25 * exp(0.36), accuracy: 0.000001)
        for _ in 0..<30 { view.scroll(pixels: -10000, anchor: .zero) }
        XCTAssertEqual(view.pixelScale, 16)
        view.zoom(factor: 0.000001, anchor: .zero)
        XCTAssertEqual(view.pixelScale, 0.02)
    }
    func testPanLimitsAndFitReset() {
        var view = ViewportTransform(image: CGSize(width: 4000, height: 2000), viewport: CGSize(width: 1000, height: 800))
        view.actualSize()
        view.pan(by: CGSize(width: 9000, height: -9000))
        XCTAssertEqual(view.offset, CGPoint(x: 1500, y: -600))
        view.fit()
        XCTAssertEqual(view.offset, .zero)
        XCTAssertEqual(view.scale, 0.25)
        XCTAssertTrue(view.isFitted)
    }
    func testActualSizeAndScreenChangeKeepOnePixelPerDisplayPixel() {
        var view = ViewportTransform(image: CGSize(width: 4000, height: 2000), viewport: CGSize(width: 1000, height: 800), backingScale: 2)
        view.actualSize()
        XCTAssertEqual(view.scale, 0.5)
        XCTAssertEqual(view.pixelScale, 1)
        view.resize(to: CGSize(width: 1200, height: 900), backingScale: 1)
        XCTAssertEqual(view.scale, 1)
        XCTAssertFalse(view.isFitted)
        view.fit()
        view.resize(to: CGSize(width: 800, height: 600), backingScale: 2)
        XCTAssertEqual(view.scale, 0.2)
        XCTAssertTrue(view.isFitted)
    }
    // Ratio alone misses half-pixel interpolation of odd-sized previews.
    func testActualSizeAlignsOddAndEvenPreviewsToDisplayPixels() {
        let cases: [(CGSize, CGFloat, CGPoint)] = [
            (CGSize(width: 4001, height: 2001), 1, CGPoint(x: -1600, y: -701)),
            (CGSize(width: 4001, height: 2001), 2, CGPoint(x: -1200, y: -401)),
            (CGSize(width: 4000, height: 2000), 1, CGPoint(x: -1600, y: -700)),
            (CGSize(width: 4000, height: 2000), 2, CGPoint(x: -1199, y: -400))
        ]
        for (image, backing, expectedOrigin) in cases {
            var view = ViewportTransform(image: image, viewport: CGSize(width: 801, height: 600), backingScale: backing)
            view.actualSize()
            XCTAssertEqual(view.imageRect.minX * backing, expectedOrigin.x)
            XCTAssertEqual(view.imageRect.minY * backing, expectedOrigin.y)
            XCTAssertEqual(view.imageRect.width * backing, image.width)
            XCTAssertEqual(view.imageRect.height * backing, image.height)
            XCTAssertEqual(view.pixelScale, 1)
        }
        let small = ViewportTransform(image: CGSize(width: 101, height: 51), viewport: CGSize(width: 801, height: 600), backingScale: 2)
        XCTAssertEqual(small.imageRect.minX * 2, 751)
        XCTAssertEqual(small.imageRect.minY * 2, 575)
    }
    func testActualSizeStaysPixelAlignedAfterFractionalDrag() {
        var view = ViewportTransform(image: CGSize(width: 4001, height: 2001), viewport: CGSize(width: 801, height: 600), backingScale: 2)
        view.actualSize()
        view.pan(by: CGSize(width: 0.3, height: 0.2))
        XCTAssertEqual(view.imageRect.minX * 2, -1199)
        XCTAssertEqual(view.imageRect.minY * 2, -401)
        XCTAssertEqual(view.imageRect.size, CGSize(width: 2000.5, height: 1000.5))
        view.resize(to: CGSize(width: 801, height: 600), backingScale: 1)
        XCTAssertEqual(view.imageRect.minX, -1600)
        XCTAssertEqual(view.imageRect.minY, -701)
        XCTAssertEqual(view.pixelScale, 1)
    }
    func testEmptyCanvasAndInvalidInputCannotProduceNaN() {
        var view = ViewportTransform(image: .zero, viewport: .zero, backingScale: 0)
        view.zoom(factor: .infinity, anchor: .zero)
        view.scroll(pixels: .nan, anchor: .zero)
        view.pan(by: CGSize(width: CGFloat.infinity, height: CGFloat.nan))
        XCTAssertEqual(view.imageRect, .zero)
        XCTAssertTrue(view.scale.isFinite)
        XCTAssertEqual(view.backingScale, 1)
    }
}
