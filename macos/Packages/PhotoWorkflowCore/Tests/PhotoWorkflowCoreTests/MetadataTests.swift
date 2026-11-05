import XCTest
import ImageIO
@testable import PhotoWorkflowCore
final class MetadataTests: XCTestCase {
    func testExposureFieldsAndLocalDateFallback() {
        let info = ImageReader.metadata([
            kCGImagePropertyTIFFDictionary: [kCGImagePropertyTIFFMake: " Panasonic ", kCGImagePropertyTIFFModel: "DC-S5M2"],
            kCGImagePropertyExifDictionary: [kCGImagePropertyExifDateTimeDigitized: "2026:11:03 00:15:00", kCGImagePropertyExifExposureTime: 0.008, kCGImagePropertyExifFNumber: 4.0, kCGImagePropertyExifISOSpeedRatings: [640], kCGImagePropertyExifFocalLength: 50.0, kCGImagePropertyExifExposureBiasValue: -0.7],
            kCGImagePropertyPixelWidth: 6000, kCGImagePropertyPixelHeight: 4000, kCGImagePropertyOrientation: 6
        ])
        XCTAssertEqual(info.camera, "Panasonic DC-S5M2")
        XCTAssertEqual(info.capturedAt, "2026-11-03T00:15:00")
        XCTAssertEqual(info.shutter, "1/125 s"); XCTAssertEqual(info.aperture, "f/4")
        XCTAssertEqual(info.iso, "640"); XCTAssertEqual(info.focalLength, "50 mm")
        XCTAssertEqual(info.exposureBias, "-0.7 EV"); XCTAssertEqual(info.dimensions, "4000 × 6000")
    }
    func testInvalidNumbersAndDatesStayUnknown() {
        let info = ImageReader.metadata([kCGImagePropertyExifDictionary: [kCGImagePropertyExifExposureTime: Double.nan, kCGImagePropertyExifFNumber: -1, kCGImagePropertyExifISOSpeedRatings: [0], kCGImagePropertyExifFocalLength: Double.infinity, kCGImagePropertyExifDateTimeOriginal: "2026:02:30 12:00:00"]])
        XCTAssertNil(info.shutter); XCTAssertNil(info.aperture); XCTAssertNil(info.iso)
        XCTAssertNil(info.focalLength); XCTAssertNil(info.capturedAt)
    }
    func testDetailsUseOriginalMetadataAndReportEachFileIndependently() throws {
        var root = FileManager.default.temporaryDirectory.appendingPathComponent("Lumix-meta-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let resolved = try XCTUnwrap(realpath(root.path, nil)); defer { free(resolved) }
        root = URL(fileURLWithPath: String(cString: resolved))
        defer { try? FileManager.default.removeItem(at: root) }
        let jpg = root.appendingPathComponent("A.JPG")
        let context = CGContext(data: nil, width: 100, height: 50, bitsPerComponent: 8, bytesPerRow: 400, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
        let destination = CGImageDestinationCreateWithURL(jpg as CFURL, "public.jpeg" as CFString, 1, nil)!
        CGImageDestinationAddImage(destination, context.makeImage()!, [kCGImagePropertyExifDictionary: [kCGImagePropertyExifFNumber: 4.0]] as CFDictionary)
        XCTAssertTrue(CGImageDestinationFinalize(destination))
        let xmp = root.appendingPathComponent("A.xmp"); try Data("<xmp/>".utf8).write(to: xmp)
        let photo = PhotoGroup(id: "meta", stem: "A", files: [.init(url: xmp, kind: .xmp), .init(url: jpg, kind: .jpeg), .init(url: root.appendingPathComponent("missing.RW2"), kind: .raw)], capturedAt: "2026-11-03T01:00:00")
        let details = PhotoDetails.read(photo)
        XCTAssertEqual(details.info.aperture, "f/4")
        XCTAssertEqual(details.info.capturedAt, photo.capturedAt)
        XCTAssertEqual(details.files[0].bytes, 6); XCTAssertNil(details.files[0].error)
        XCTAssertNotNil(details.files[1].bytes)
        XCTAssertNotNil(details.files[2].error); XCTAssertNil(details.totalBytes)
    }
}
