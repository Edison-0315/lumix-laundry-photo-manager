import XCTest
import Foundation
import Darwin

final class LibraryRecyclerTests: XCTestCase {
    private func fixture(_ body: (URL, LibraryRecycleContext) throws -> Void) throws {
        let base = FileManager.default.temporaryDirectory.appendingPathComponent("Lumix-native-recycle-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        let physical = try XCTUnwrap(realpath(base.path, nil)); defer { free(physical) }
        let folder = URL(fileURLWithPath: String(cString: physical)); defer { try? FileManager.default.removeItem(at: folder) }
        let root = folder.appendingPathComponent("独立照片库")
        try FileManager.default.createDirectory(at: root.appendingPathComponent(".片集"), withIntermediateDirectories: true)
        let database = root.appendingPathComponent(".片集/catalog.sqlite3")
        try Data("test catalog".utf8).write(to: database)
        try Data("original photo".utf8).write(to: root.appendingPathComponent("A.JPG"))
        func identity(_ path: URL) -> [Int64] {
            var value = stat(); XCTAssertEqual(lstat(path.path, &value), 0)
            return [Int64(value.st_dev), Int64(value.st_ino)]
        }
        let plan = LibraryRecyclePlan(token: "test", name: root.lastPathComponent, root: root.path, rootIdentity: identity(root), catalogIdentity: identity(database), photoCount: 1, fileCount: 2, bytes: 26)
        try body(root, LibraryRecycleContext(plan))
    }
    func testSystemTrashMovesDisposableLibraryAndCanBeRecovered() throws {
        try fixture { root, context in
            let destination = try XCTUnwrap(LibraryRecycler.recycle(context))
            XCTAssertFalse(FileManager.default.fileExists(atPath: root.path))
            XCTAssertEqual(try Data(contentsOf: destination.appendingPathComponent("A.JPG")), Data("original photo".utf8))
            // Restore this test's exact directory; leave no test folder in Trash.
            try FileManager.default.moveItem(at: destination, to: root)
            XCTAssertTrue(context.originalStillAtPath())
        }
    }
    func testSystemFailureRetainsOriginalWithoutPermanentDeleteFallback() throws {
        try fixture { root, context in
            XCTAssertThrowsError(try LibraryRecycler.recycle(context, transfer: { _ in throw CocoaError(.fileWriteNoPermission) }))
            XCTAssertTrue(context.originalStillAtPath())
            XCTAssertEqual(try Data(contentsOf: root.appendingPathComponent("A.JPG")), Data("original photo".utf8))
        }
    }
    func testReplacedDirectoryNeverReachesSystemTrash() throws {
        try fixture { root, context in
            let original = root.appendingPathExtension("original")
            try FileManager.default.moveItem(at: root, to: original)
            try FileManager.default.createDirectory(at: root, withIntermediateDirectories: false)
            var invoked = false
            XCTAssertThrowsError(try LibraryRecycler.recycle(context, transfer: { _ in invoked = true; return nil }))
            XCTAssertFalse(invoked)
            XCTAssertEqual(try Data(contentsOf: original.appendingPathComponent("A.JPG")), Data("original photo".utf8))
        }
    }
}
