import XCTest
import Foundation
import Darwin

final class LibraryRecycleBackendTests: XCTestCase {
    func testProtocolValidationAndSystemTrashShareOneCoordinatedTransaction() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("Lumix-recycle-bridge-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let physical = try XCTUnwrap(realpath(directory.path, nil)); defer { free(physical) }
        let base = URL(fileURLWithPath: String(cString: physical)); defer { try? FileManager.default.removeItem(at: base) }
        let root = base.appendingPathComponent("本机库")
        let helper = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("Backend/main.py")
        let backend = NativeLibraryBackend(helperURL: helper)
        func parameters(_ values: [String: Any]) throws -> Data { try JSONSerialization.data(withJSONObject: values) }
        do {
            _ = try await backend.request("create", params: parameters(["root": root.path]))
            let result = try await backend.request("inspect_recycle")
            let plan = try JSONDecoder().decode(LibraryRecyclePlan.self, from: result)
            let context = try LibraryRecycleContext(plan)
            let moved = try await backend.recycle(context, params: parameters(["token": plan.token, "name": plan.name]))
            let destination = try XCTUnwrap(moved)
            await backend.close()
            XCTAssertFalse(FileManager.default.fileExists(atPath: root.path))
            XCTAssertTrue(FileManager.default.fileExists(atPath: destination.appendingPathComponent(".片集/catalog.sqlite3").path))
            try FileManager.default.moveItem(at: destination, to: root)
            _ = try await backend.request("open", params: parameters(["root": root.path]))
            await backend.close()
        } catch { await backend.close(); throw error }
    }
}
