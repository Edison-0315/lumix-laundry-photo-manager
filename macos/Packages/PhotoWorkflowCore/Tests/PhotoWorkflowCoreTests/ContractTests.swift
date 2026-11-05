import XCTest
@testable import PhotoWorkflowCore
final class ContractTests: XCTestCase {
    func asset(_ path: String, _ kind: AssetKind) -> FileAsset { .init(url: URL(fileURLWithPath: "/SD/" + path), kind: kind) }
    // A basename-only merge would lose separate shoots and collapse ambiguous siblings.
    func testPairingSameDirectoryAndDoubleExtensionSidecar() {
        let rows = PhotoPairing.groups(files: [asset("A.JPG", .jpeg), asset("a.RW2", .raw), asset("A.RW2.xmp", .xmp)])
        XCTAssertEqual(rows.count, 1)
        XCTAssertEqual(rows.first?.files.count, 3)
        XCTAssertEqual(rows.first?.stem, "A")
    }
    func testOnlyExplicitUnambiguousSiblingFormatsPair() {
        XCTAssertEqual(PhotoPairing.groups(files: [asset("shoot/JPEG/A.jpg", .jpeg), asset("shoot/RAW/A.rw2", .raw)]).count, 1)
        XCTAssertEqual(PhotoPairing.groups(files: [asset("shoot/JPEG/A.jpg", .jpeg), asset("shoot/JPG/A.jpg", .jpeg), asset("shoot/RAW/A.rw2", .raw)]).count, 3)
        XCTAssertEqual(PhotoPairing.groups(files: [asset("first/A.jpg", .jpeg), asset("second/A.rw2", .raw)]).count, 2)
        XCTAssertTrue(PhotoPairing.groups(files: [asset("alone.xmp", .xmp)]).isEmpty)
    }
    func testIndependentStageAndLocalDate() {
        var p = PhotoGroup(id: "p", stem: "A", files: [], capturedAt: "2026-11-03T00:15:00")
        p.primaryExportID = "x"
        XCTAssertTrue(StageFilter.pending.includes(p)); XCTAssertTrue(StageFilter.exports.includes(p))
        p.edited = true
        XCTAssertTrue(StageFilter.edited.includes(p)); XCTAssertTrue(StageFilter.exports.includes(p))
        XCTAssertEqual(p.dateKey, "2026-11-03")
    }
    func testDistinctCaseSensitiveShootPathsStaySeparate() {
        XCTAssertEqual(PhotoPairing.groups(files: [asset("Shoot/A.JPG", .jpeg), asset("shoot/A.RW2", .raw)]).count, 2)
        XCTAssertEqual(PhotoPairing.groups(files: [asset("Shoot/JPEG/A.JPG", .jpeg), asset("shoot/RAW/A.RW2", .raw)]).count, 2)
    }
    func testToggleRangeContextAndVisibleSelection() {
        var s = SelectionState(); s.selected = ["hidden"]
        s.click("a", visible: ["a", "b", "c"]); s.click("c", visible: ["a", "b", "c"])
        XCTAssertEqual(s.selected, ["hidden", "a", "c"])
        s.doubleClick("c"); XCTAssertEqual(s.selected, ["hidden", "a"])
        s.click("a", visible: ["a", "b", "c"])
        s.click("c", visible: ["a", "b", "c"], shift: true)
        XCTAssertEqual(s.selected, ["a", "b", "c"])
        s.contextClick("b"); XCTAssertEqual(s.selected.count, 3)
        s.contextClick("other"); XCTAssertEqual(s.selected, ["other"])
        s.selectVisible(["a", "b"]); XCTAssertEqual(s.selected, ["other", "a", "b"])
    }
    func testSignatureMatchesPythonTupleListEncoding() {
        // SHA256 of [('jpeg', 'abc'), ('raw', 'def')], independently calculated fixture.
        XCTAssertEqual(LegacySignature.hash(members: [(.raw, "def"), (.jpeg, "abc")]), "789ee53eccfe5c24b1bef0bb69519593f1cb8da2cf5b068bc6b2f7d1a8de3574")
    }
    func testOnlySelectedKeepsDoubleClickTargetUntilFilteringFinishes() {
        var s = SelectionState(); s.selected = ["a"]
        s.click("a", visible: ["a"], deferFiltering: true)
        XCTAssertTrue(s.selected.isEmpty)
        XCTAssertEqual(s.filteredSelection, ["a"])
        s.doubleClick("a")
        XCTAssertEqual(s.selected, ["a"])
        s.click("a", visible: ["a"], deferFiltering: true)
        s.finishFiltering()
        XCTAssertTrue(s.filteredSelection.isEmpty)
    }
}
