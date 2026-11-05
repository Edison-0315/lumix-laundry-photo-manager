import XCTest
import Foundation
import Darwin
import PhotoWorkflowCore

final class NativeBackendTests: XCTestCase {
    // A fill-until-length pipe read deadlocks on the helper's short greeting/result lines.
    @MainActor func testNativeProcessRoundTripImportAndReadOnlyBoundary() async throws {
        executionTimeAllowance = 30
        let parent = FileManager.default.temporaryDirectory.appendingPathComponent("Lumix-process-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
        let physical = try XCTUnwrap(realpath(parent.path, nil)); defer { free(physical) }
        let base = URL(fileURLWithPath: String(cString: physical))
        defer { try? FileManager.default.removeItem(at: base) }
        let root = base.appendingPathComponent("本机库")
        let source = base.appendingPathComponent("SD")
        try FileManager.default.createDirectory(at: source, withIntermediateDirectories: true)
        let file = source.appendingPathComponent("A.JPG"), bytes = Data("synthetic source".utf8)
        try bytes.write(to: file)
        let helper = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("Backend/main.py")
        let backend = NativeLibraryBackend(helperURL: helper)
        func params(_ value: [String: Any]) throws -> Data { try JSONSerialization.data(withJSONObject: value) }
        do {
            let created = try await backend.request("create", params: params(["root": root.path]))
            XCTAssertTrue(try JSONDecoder().decode(NativeLibraryState.self, from: created).writable)
            let payload: [String: Any] = ["source_root": source.path, "activity": "活动", "groups": [
                ["id": "scan-a", "stem": "A", "captured_at": "2026-11-04T00:15:00", "files": [["id": "f", "kind": "jpeg", "path": file.path]]]
            ]]
            _ = try await backend.request("import", params: params(payload))
            let snapshot = try await Task.detached { try LegacyCatalog.read(root: root) }.value
            XCTAssertEqual(snapshot.photos.count, 1)
            XCTAssertEqual(snapshot.photos.first?.photo.capturedAt, "2026-11-04T00:15:00")
            XCTAssertEqual(try Data(contentsOf: file), bytes)
            let photo = try XCTUnwrap(snapshot.photos.first)
            let personData = try await backend.request("create_person", params: params(["activity_id": photo.activityID, "name": "Alice"]))
            let person = try XCTUnwrap(JSONSerialization.jsonObject(with: personData) as? [String: Any])
            let personID = try XCTUnwrap(person["id"] as? String)
            _ = try await backend.request("set_person", params: params(["ids": [photo.id.rawValue], "person_id": personID]))
            _ = try await backend.request("set_edited", params: params(["ids": [photo.id.rawValue], "value": true]))
            let organized = try await Task.detached { try LegacyCatalog.read(root: root) }.value
            let moved = try XCTUnwrap(organized.photos.first)
            XCTAssertEqual(moved.personID, personID)
            XCTAssertTrue(moved.photo.edited)
            XCTAssertTrue(try XCTUnwrap(moved.assets.first).path.contains("Alice/已修原片"))
            XCTAssertEqual(try Data(contentsOf: file), bytes)
            XCTAssertEqual(try Data(contentsOf: XCTUnwrap(moved.photo.files.first).url), bytes)
            let old = base.appendingPathComponent("旧库")
            try FileManager.default.createDirectory(at: old, withIntermediateDirectories: true)
            do { _ = try await backend.request("open", params: params(["root": old.path])); XCTFail("Unmarked library must stay read-only") }
            catch { XCTAssertTrue(error.localizedDescription.contains("只读")) }
            XCTAssertTrue(try FileManager.default.contentsOfDirectory(atPath: old.path).isEmpty)
            let state = try await backend.request("state")
            XCTAssertEqual(try JSONDecoder().decode(NativeLibraryState.self, from: state).root, root.path)
            await backend.close()
        } catch { await backend.close(); throw error }
    }
}
