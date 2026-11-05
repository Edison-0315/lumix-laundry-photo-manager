import Foundation
import XCTest
import PhotoWorkflowCore

final class SourceNavigationModelTests: XCTestCase {
    @MainActor func testSourceScanRefusesOpenWritableLibraryAndOverlappingDirectories() async throws {
        let source = try fixture()
        let model = AppModel(); try await scan(model, root: source)
        let before = model.photos.map(\.id)
        model.writableLibraryRoot = source.appendingPathComponent("A")
        for candidate in [source, source.appendingPathComponent("A")] {
            model.scan(candidate)
            XCTAssertFalse(model.busy)
            XCTAssertTrue(model.message?.contains("照片库") == true)
            XCTAssertEqual(model.photos.map(\.id), before)
        }
        model.writableLibraryRoot = source
        model.scan(source.appendingPathComponent("A"))
        XCTAssertFalse(model.busy)
        XCTAssertEqual(model.photos.map(\.id), before)
        model.writableLibraryRoot = nil
        try await scan(model, root: source.appendingPathComponent("A"))
        XCTAssertEqual(model.photos.count, 1)
    }
    @MainActor func testImportIncludesFolderDescendantsAndHiddenPhotoPicksOnce() async throws {
        let model = AppModel(); try await scan(model, root: fixture())
        model.openLocation(.folder(""))
        let rootPhoto = try XCTUnwrap(model.visible.first)
        model.click(rootPhoto.id, shift: false, additive: false); model.clickFolder("A")
        model.openLocation(.folder("A"))
        let child = try XCTUnwrap(model.visible.first)
        XCTAssertEqual(Set(model.importPhotos.map(\.id)), [rootPhoto.id, child.id])
        model.click(child.id, shift: false, additive: false)
        model.format = "jpeg"
        XCTAssertTrue(model.visible.isEmpty)
        XCTAssertEqual(model.importPhotos.count, 2)
        try await scan(model, root: fixture())
        XCTAssertTrue(model.importPhotos.isEmpty)
    }
    // A shrinking box must remove prior hits; Escape must restore the entire starting selection.
    @MainActor func testMarqueeReplacesRetractsAndCancelsWithStableSelectedFilter() async throws {
        let model = AppModel(); try await scan(model, root: fixture())
        model.openLocation(.folder("")); model.selectVisible(); model.onlySelected = true
        let photo = try XCTUnwrap(model.visible.first)
        model.beginMarquee()
        model.updateMarquee(photos: [], folders: [], additive: false)
        XCTAssertTrue(model.selection.selected.isEmpty)
        XCTAssertTrue(model.folderChoices.selected(in: model.location).isEmpty)
        XCTAssertEqual(model.visible.map(\.id), [photo.id])
        XCTAssertEqual(model.visibleFolders, ["A"])
        model.updateMarquee(photos: [photo.id], folders: ["A"], additive: false)
        XCTAssertEqual(model.selection.selected, [photo.id])
        model.updateMarquee(photos: [], folders: [], additive: false)
        model.endMarquee(cancelled: true)
        XCTAssertEqual(model.selection.selected, [photo.id])
        XCTAssertEqual(model.folderChoices.selected(in: model.location), ["A"])
        model.beginMarquee(); model.updateMarquee(photos: [], folders: [], additive: false)
        model.endMarquee()
        XCTAssertTrue(model.visible.isEmpty); XCTAssertTrue(model.visibleFolders.isEmpty)
    }
    // Additive dragging must preserve picks in another directory, even when the box shrinks.
    @MainActor func testMarqueeAddsToStartingPicksRatherThanAccumulatingEveryHit() async throws {
        let model = AppModel(); try await scan(model, root: fixture())
        model.openLocation(.folder("A")); model.selectVisible()
        let hidden = try XCTUnwrap(model.visible.first)
        model.openLocation(.folder(""))
        let rootPhoto = try XCTUnwrap(model.visible.first)
        model.beginMarquee()
        model.updateMarquee(photos: [rootPhoto.id], folders: ["A"], additive: true)
        XCTAssertEqual(model.selection.selected, [hidden.id, rootPhoto.id])
        XCTAssertEqual(model.folderChoices.selected(in: model.location), ["A"])
        model.updateMarquee(photos: [], folders: [], additive: true)
        model.endMarquee()
        XCTAssertEqual(model.selection.selected, [hidden.id])
        XCTAssertTrue(model.folderChoices.selected(in: model.location).isEmpty)
    }
    private func fixture() throws -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("Lumix-nav-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root.appendingPathComponent("A"), withIntermediateDirectories: true)
        try Data("synthetic unsupported RAW".utf8).write(to: root.appendingPathComponent("R.RW2"))
        try Data("synthetic unsupported RAW".utf8).write(to: root.appendingPathComponent("A/S.RW2"))
        addTeardownBlock { try FileManager.default.removeItem(at: root) }
        return root
    }
    @MainActor private func scan(_ model: AppModel, root: URL) async throws {
        model.scan(root)
        let deadline = Date().addingTimeInterval(5)
        while model.busy && Date() < deadline { try await Task.sleep(for: .milliseconds(10)) }
        XCTAssertFalse(model.busy, "Source scan must finish")
    }
    // Old history carried the child's onlySelected state and hid parent folders.
    @MainActor func testHistoryClearsOnlySelectedWithoutClearingPicks() async throws {
        let model = AppModel(); try await scan(model, root: fixture())
        model.openLocation(.folder(""))
        let rootPhoto = try XCTUnwrap(model.visible.first)
        model.click(rootPhoto.id, shift: false, additive: false)
        model.openLocation(.folder("A")); model.onlySelected = true
        model.goBack()
        XCTAssertFalse(model.onlySelected)
        XCTAssertEqual(model.visibleFolders, ["A"])
        XCTAssertEqual(model.selection.selected, [rootPhoto.id])
        model.onlySelected = true; model.goForward()
        XCTAssertFalse(model.onlySelected)
        XCTAssertEqual(model.visible.map(\.stem), ["S"])
        XCTAssertEqual(model.selection.selected, [rootPhoto.id])
    }
    // Cancelling the common timer must release both kinds of held filters.
    @MainActor func testPhotoPreviewCannotLeaveCancelledFolderVisible() async throws {
        let model = AppModel(); try await scan(model, root: fixture())
        model.openLocation(.folder("")); model.selectVisible(); model.onlySelected = true
        let photo = try XCTUnwrap(model.visible.first)
        model.clickFolder("A")
        model.click(photo.id, shift: false, additive: false)
        model.doubleClick(photo.id)
        XCTAssertNotNil(model.preview)
        model.preview = nil
        XCTAssertTrue(model.folderChoices.selected(in: .folder("")).isEmpty)
        XCTAssertTrue(model.visibleFolders.isEmpty)
        model.selectVisible()
        XCTAssertTrue(model.folderChoices.selected(in: .folder("")).isEmpty)
        XCTAssertEqual(model.selection.selected, [photo.id])
    }
    @MainActor func testFailedScanKeepsNavigationAndSuccessfulScanResetsIt() async throws {
        let root = try fixture(); let model = AppModel()
        try await scan(model, root: root)
        model.openLocation(.folder("")); model.selectVisible()
        model.openLocation(.folder("A")); model.format = "raw"
        let oldPicks = model.selection.selected
        try await scan(model, root: root.appendingPathComponent("does-not-exist"))
        XCTAssertEqual(model.location, .folder("A")); XCTAssertEqual(model.format, "raw")
        XCTAssertTrue(model.canGoBack); XCTAssertEqual(model.selection.selected, oldPicks)
        XCTAssertEqual(model.folderChoices.selected(in: .folder("")), ["A"])
        try await scan(model, root: fixture())
        XCTAssertEqual(model.location, .all); XCTAssertEqual(model.format, "all")
        XCTAssertFalse(model.canGoBack); XCTAssertFalse(model.canGoForward)
        XCTAssertTrue(model.selection.selected.isEmpty)
        XCTAssertTrue(model.folderChoices.selected(in: .folder("")).isEmpty)
    }
}
