import XCTest
@testable import PhotoWorkflowCore
final class NavigationTests: XCTestCase {
    func testHistoryRestoresScrollOffsetsAndIgnoresLatePreviousRouteUpdates() {
        var nav = SourceNavigation()
        let initial = nav.route
        nav.rememberScrollOffset(650, for: initial)
        let folder = SourceRoute(location: .folder("Shoot"))
        nav.navigate(folder)
        XCTAssertEqual(nav.scrollOffset, 0)
        nav.rememberScrollOffset(320, for: folder)
        nav.rememberScrollOffset(999, for: initial)
        XCTAssertEqual(nav.scrollOffset, 320)
        nav.back(); XCTAssertEqual(nav.scrollOffset, 650)
        nav.forward(); XCTAssertEqual(nav.scrollOffset, 320)
        var filtered = folder; filtered.format = "raw"
        nav.navigate(filtered); XCTAssertEqual(nav.scrollOffset, 0)
        nav.rememberScrollOffset(180, for: filtered)
        nav.back(); XCTAssertEqual(nav.scrollOffset, 320)
        nav.forward(); XCTAssertEqual(nav.scrollOffset, 180)
        nav.reset(); XCTAssertEqual(nav.scrollOffset, 0)
    }
    private let root = URL(fileURLWithPath: "/SD/Source")
    private func photo(_ id: PhotoID, _ paths: [String]) -> PhotoGroup {
        PhotoGroup(id: id, stem: id.rawValue, files: paths.map { FileAsset(url: root.appendingPathComponent($0), kind: $0.hasSuffix("RW2") ? .raw : .jpeg) })
    }
    // Catch substring prefix matching, case folding, and flattening descendants.
    func testStructuralChildrenAndExactDirectPhotoMembership() {
        let a = photo("a", ["Shoot/JPEG/A.JPG", "Shoot/RAW/A.RW2"])
        let b = photo("b", ["Shoot2/B.JPG"])
        let c = photo("c", ["shoot/人像/C.JPG"])
        let star = photo("star", ["*/D.JPG"])
        let index = SourceFolderIndex(photos: [a,b,c,star], root: root)
        XCTAssertEqual(index.children(of: .folder("")), ["*", "Shoot", "Shoot2", "shoot"])
        XCTAssertEqual(index.children(of: .folder("Shoot")), ["Shoot/JPEG", "Shoot/RAW"])
        XCTAssertEqual(index.children(of: .all), [])
        XCTAssertEqual(index.directories(for: "a"), ["Shoot/JPEG", "Shoot/RAW"])
        XCTAssertTrue(index.contains("a", in: .folder("Shoot/JPEG")))
        XCTAssertTrue(index.contains("a", in: .folder("Shoot/RAW")))
        XCTAssertFalse(index.contains("a", in: .folder("Shoot")))
        XCTAssertFalse(index.descends("b", from: "Shoot"))
        XCTAssertFalse(index.descends("c", from: "Shoot"))
        XCTAssertTrue(index.descends("c", from: "shoot"))
        XCTAssertTrue(index.contains("star", in: .folder("*")))
        XCTAssertFalse(index.contains("a", in: .folder("*")))
        XCTAssertTrue(index.contains("a", in: .all))
    }
    func testLeadingCombiningMarkCannotSwallowPathSeparator() {
        let name = "\u{0301}Trip"
        let path = "A/" + name
        let index = SourceFolderIndex(photos: [photo("combining", [path + "/IMG.JPG"])], root: root)
        XCTAssertEqual(index.children(of: .folder("")), ["A"])
        XCTAssertEqual(index.children(of: .folder("A")), [path])
        XCTAssertTrue(index.descends("combining", from: "A"))
        XCTAssertEqual(SourceLocation.folder(path).label, name)
        XCTAssertEqual(SourceLocation.folder(path).parent, .folder("A"))
        XCTAssertEqual(SourceLocation.folder(path).breadcrumbs, [.folder(""), .folder("A"), .folder(path)])
    }
    func testOutsideRootDoesNotCreateNavigationEntries() {
        let outside = PhotoGroup(id: "outside", stem: "outside", files: [.init(url: URL(fileURLWithPath: "/SD/SourceOther/private/A.JPG"), kind: .jpeg)])
        let index = SourceFolderIndex(photos: [outside, photo("root", ["A.JPG"])], root: root)
        XCTAssertEqual(index.paths, [""])
        XCTAssertTrue(index.contains("root", in: .folder("")))
        XCTAssertFalse(index.contains("outside", in: .all))
    }
    func testBreadcrumbsAndParentPreserveUnicodeAndStarIdentity() {
        XCTAssertEqual(SourceLocation.folder("拍摄/*/JPEG").breadcrumbs, [.folder(""), .folder("拍摄"), .folder("拍摄/*"), .folder("拍摄/*/JPEG")])
        XCTAssertEqual(SourceLocation.folder("拍摄/*/JPEG").parent, .folder("拍摄/*"))
        XCTAssertNil(SourceLocation.folder("").parent)
        XCTAssertEqual(SourceLocation.all.breadcrumbs, [.folder(""), .all])
        XCTAssertNotEqual(SourceLocation.all, .folder("*"))
    }
    func testHistoryRestoresFiltersAndBranchesWithoutDuplicates() {
        var nav = SourceNavigation()
        let a = SourceRoute(location: .folder("A"), date: "2026-11-03", format: "raw")
        let b = SourceRoute(location: .folder("B"), format: "jpeg")
        nav.navigate(a); nav.navigate(a); nav.navigate(b)
        nav.back(); XCTAssertEqual(nav.route, a)
        nav.back(); XCTAssertEqual(nav.route, SourceRoute())
        XCTAssertFalse(nav.canGoBack)
        nav.forward(); XCTAssertEqual(nav.route, a)
        nav.navigate(SourceRoute(location: .folder("A"), date: "unknown", format: "raw"))
        XCTAssertFalse(nav.canGoForward)
        nav.back(); XCTAssertEqual(nav.route, a)
    }
    func testHistoryBoundsAndNewScanReset() {
        var nav = SourceNavigation()
        for i in 1...90 { nav.navigate(SourceRoute(location: .folder("\(i)"))) }
        for _ in 0..<80 { nav.back() }
        XCTAssertEqual(nav.route.location, .folder("10"))
        XCTAssertFalse(nav.canGoBack)
        XCTAssertTrue(nav.canGoForward)
        nav.reset()
        XCTAssertEqual(nav.route, SourceRoute())
        XCTAssertFalse(nav.canGoBack); XCTAssertFalse(nav.canGoForward)
    }
    func testFolderChoicesStayScopedAndDoubleClickRestoresSelection() {
        var folders = FolderChoices()
        folders.click("A", scope: .folder(""))
        folders.click("B", scope: .folder(""))
        folders.click("A/sub", scope: .folder("A"))
        folders.click("A", scope: .folder(""), deferFiltering: true)
        XCTAssertEqual(folders.selected(in: .folder("")), ["B"])
        XCTAssertEqual(folders.filtered(in: .folder("")), ["A", "B"])
        folders.doubleClick("A", scope: .folder(""))
        XCTAssertEqual(folders.selected(in: .folder("")), ["A", "B"])
        XCTAssertEqual(folders.selected(in: .folder("A")), ["A/sub"])
        folders.click("A", scope: .folder(""), deferFiltering: true); folders.finishFiltering()
        XCTAssertEqual(folders.filtered(in: .folder("")), ["B"])
    }
    func testVisibleFolderBulkSelectionPreservesHiddenChoices() {
        var folders = FolderChoices()
        folders.click("hidden", scope: .folder(""))
        folders.selectVisible(["A", "B"], scope: .folder(""))
        folders.deselectVisible(["A"], scope: .folder(""))
        XCTAssertEqual(folders.selected(in: .folder("")), ["B", "hidden"])
        folders.reset(); XCTAssertTrue(folders.selected(in: .folder("")).isEmpty)
    }
}
