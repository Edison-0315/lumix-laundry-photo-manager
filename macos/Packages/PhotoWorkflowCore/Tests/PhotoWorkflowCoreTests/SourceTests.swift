import XCTest
import ImageIO
import CoreGraphics
import UniformTypeIdentifiers
import CryptoKit
@testable import PhotoWorkflowCore
final class SourceTests: XCTestCase {
    func fixture() throws -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("Lumix-test-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        addTeardownBlock { try FileManager.default.removeItem(at: root) }
        return root
    }
    func jpeg(_ url: URL, oriented: Bool = false) throws {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let context = CGContext(data: nil, width: 100, height: 50, bitsPerComponent: 8, bytesPerRow: 400, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
        context.setFillColor(CGColor(red: 0.8, green: 0.2, blue: 0.1, alpha: 1)); context.fill(CGRect(x: 0, y: 0, width: 100, height: 50))
        let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.jpeg.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(destination, context.makeImage()!, [kCGImagePropertyOrientation: oriented ? 6 : 1, kCGImagePropertyExifDictionary: [kCGImagePropertyExifDateTimeOriginal: "2026:11:03 00:15:00"]] as CFDictionary)
        XCTAssertTrue(CGImageDestinationFinalize(destination))
    }
    func hashes(_ root: URL) throws -> [String: String] {
        let e = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.isRegularFileKey])!
        var files: [String: String] = [:]
        for case let u as URL in e where try u.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true {
            files[u.path] = SHA256.hash(data: try Data(contentsOf: u)).map { String(format: "%02x", $0) }.joined()
        }
        return files
    }
    // A known readable image must not require listing every ancestor directory.
    // O_RDONLY on search-only parents breaks this otherwise valid read.
    func testPreviewReadsThroughSearchOnlyAncestor() throws {
        let root = try fixture()
        let restricted = root.appendingPathComponent("search-only")
        let candidate = restricted.appendingPathComponent("photos/A.jpg")
        try jpeg(candidate)
        // Foundation rewrites /private/var to /var even when resolving URLs.
        // Use the actual existing path; the production scanner supplies it too.
        let resolved = try XCTUnwrap(realpath(candidate.path, nil))
        defer { free(resolved) }
        let file = URL(fileURLWithPath: String(cString: resolved))
        try FileManager.default.setAttributes([.posixPermissions: 0o111], ofItemAtPath: restricted.path)
        defer { try? FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: restricted.path) }
        let photo = PhotoGroup(id: "search-only", stem: "A", files: [.init(url: file, kind: .jpeg)])
        do {
            let fd = try SafeImageSource.fileDescriptor(file)
            close(fd)
        } catch { XCTFail("Known image open failed at " + file.path + ": " + error.localizedDescription) }
        XCTAssertTrue(ImageReader.info(file).recognized)
        XCTAssertNoThrow(try ImageReader.preview(photo, maxPixel: 80))
    }
    func testReadOnlyScanAndOrientedPreview() throws {
        let root = try fixture(); let jpg = root.appendingPathComponent("A.JPG")
        try jpeg(jpg, oriented: true)
        try Data("raw".utf8).write(to: root.appendingPathComponent("A.RW2"))
        try Data("xmp".utf8).write(to: root.appendingPathComponent("A.RW2.xmp"))
        let before = try hashes(root)
        let scan = try SourceScanner.scan(root: root)
        XCTAssertEqual(scan.photos.count, 1); XCTAssertEqual(scan.photos.first?.files.count, 3)
        XCTAssertEqual(scan.photos.first?.dateKey, "2026-11-03")
        if let photo = scan.photos.first {
            let bytes = try ImageReader.preview(photo, maxPixel: 80)
            let source = try XCTUnwrap(CGImageSourceCreateWithData(bytes as CFData, nil))
            let props = try XCTUnwrap(CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any])
            XCTAssertEqual(props[kCGImagePropertyPixelWidth] as? Int, 40)
            XCTAssertEqual(props[kCGImagePropertyPixelHeight] as? Int, 80)
        }
        XCTAssertEqual(try hashes(root), before)
    }
    func testSymlinkExcludedAndCorruptJPEGKept() throws {
        let root = try fixture(); let outside = try fixture()
        try jpeg(outside.appendingPathComponent("secret.jpg"))
        try FileManager.default.createSymbolicLink(at: root.appendingPathComponent("link"), withDestinationURL: outside)
        try Data("broken".utf8).write(to: root.appendingPathComponent("bad.jpg"))
        let scan = try SourceScanner.scan(root: root)
        XCTAssertEqual(scan.photos.map(\.stem), ["bad"])
        XCTAssertNotNil(scan.photos.first?.warning)
    }
    func testOneReadFailureIsIsolated() throws {
        let root = try fixture(); try jpeg(root.appendingPathComponent("good.jpg")); try jpeg(root.appendingPathComponent("bad.jpg"))
        let scan = try SourceScanner.scan(root: root, inspect: { url in
            if url.lastPathComponent == "bad.jpg" { throw NSError(domain: NSPOSIXErrorDomain, code: 13) }
        })
        XCTAssertEqual(scan.photos.map(\.stem), ["good"])
        XCTAssertEqual(scan.issues.count, 1); XCTAssertEqual(scan.issues.first?.code, 13)
    }
    func testCancelledAndFailedResultsKeepPriorSnapshot() throws {
        let root = try fixture(); try jpeg(root.appendingPathComponent("good.jpg"))
        var snapshot = SourceSnapshot()
        XCTAssertTrue(snapshot.publish(try SourceScanner.scan(root: root)))
        let old = snapshot.result?.photos.map(\.id)
        let cancelled = try SourceScanner.scan(root: root, cancel: { true })
        XCTAssertTrue(cancelled.cancelled); XCTAssertFalse(snapshot.publish(cancelled))
        var failure = ScanResult(root: root); failure.issues = [.init(path: root.path, operation: "read", error: CocoaError(.fileReadNoPermission))]
        XCTAssertFalse(snapshot.publish(failure)); XCTAssertEqual(snapshot.result?.photos.map(\.id), old)
    }
    func testReadRejectsFileReplacedBySymlinkAfterScan() throws {
        let root = try fixture(); let outside = try fixture()
        let file = root.appendingPathComponent("A.jpg")
        try jpeg(file); try jpeg(outside.appendingPathComponent("secret.jpg"))
        let scan = try SourceScanner.scan(root: root)
        let photo = try XCTUnwrap(scan.photos.first)
        try FileManager.default.removeItem(at: file)
        try FileManager.default.createSymbolicLink(at: file, withDestinationURL: outside.appendingPathComponent("secret.jpg"))
        XCTAssertFalse(ImageReader.info(file).recognized)
        XCTAssertThrowsError(try ImageReader.preview(photo, maxPixel: 640))
    }
    func testReadRejectsParentReplacedBySymlinkAfterScan() throws {
        let root = try fixture(); let outside = try fixture()
        let dir = root.appendingPathComponent("shoot")
        try jpeg(dir.appendingPathComponent("A.jpg")); try jpeg(outside.appendingPathComponent("A.jpg"))
        let photo = try XCTUnwrap(SourceScanner.scan(root: root).photos.first)
        try FileManager.default.removeItem(at: dir)
        try FileManager.default.createSymbolicLink(at: dir, withDestinationURL: outside)
        XCTAssertThrowsError(try ImageReader.preview(photo, maxPixel: 640))
    }
    func testScannerRejectsLinkIntroducedBetweenEnumerationAndRead() throws {
        let root = try fixture(); let outside = try fixture()
        let file = root.appendingPathComponent("A.jpg")
        try jpeg(file); try jpeg(outside.appendingPathComponent("secret.jpg"))
        let scan = try SourceScanner.scan(root: root, inspect: { url in
            try FileManager.default.removeItem(at: url)
            try FileManager.default.createSymbolicLink(at: url, withDestinationURL: outside.appendingPathComponent("secret.jpg"))
        })
        XCTAssertTrue(scan.photos.isEmpty)
        XCTAssertEqual(scan.issues.count, 1)
    }
}
