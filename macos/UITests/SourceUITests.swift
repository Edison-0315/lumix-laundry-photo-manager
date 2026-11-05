import XCTest
import Darwin
final class SourceUITests: XCTestCase {
    @MainActor func testCompactWindowKeepsSourceAndLibraryControlsReachable() throws {
        continueAfterFailure = false
        let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures")
        let app = XCUIApplication(); defer { app.terminate() }
        var auditIssues: [String] = []
        func audit(_ page: String) throws {
            // Audit the custom photo controls changed here. Full-window findings for
            // system menus, slider subelements and containers remain documented separately.
            try app.performAccessibilityAudit(for: [.sufficientElementDescription, .action]) { issue in
                guard let element = issue.element else { return true }
                let customPhoto = element.identifier.hasPrefix("libraryPhoto:") || element.identifier.hasPrefix("photoPreviewImage:") ||
                    (element.elementType == .button && element.label == "A，已选中")
                guard customPhoto else { return true }
                let detail = page + ": " + issue.compactDescription + "\n" + element.debugDescription
                auditIssues.append(detail)
                let attachment = XCTAttachment(string: detail); attachment.name = "Accessibility issue"; attachment.lifetime = .keepAlways; self.add(attachment)
                return true // Fail once below if any custom photo control has an issue.
            }
        }
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES", "-thumbnailSize", "120", "--compact-window"]
        app.launch(); app.activate()
        let window = app.windows.firstMatch
        XCTAssertTrue(window.waitForExistence(timeout: 10))
        let compact = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            let frame = app.windows.firstMatch.frame
            return frame.width <= 1020 && frame.height <= 820
        }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [compact], timeout: 5), .completed)
        let resized = XCTAttachment(screenshot: window.screenshot()); resized.name = "Resized window"; resized.lifetime = .keepAlways; add(resized)
        // The 680-point content minimum also needs the native title/toolbar height.
        XCTAssertLessThanOrEqual(window.frame.width, 1020)
        XCTAssertLessThanOrEqual(window.frame.height, 820)
        app.menuBars.menuBarItems["File"].click(); app.menuItems["选择照片来源…"].click()
        try chooseFixtureFolder(app, root: fixtures.appendingPathComponent("UITestSource/JPEG"), expectedEntry: "A.JPG")
        let photo = app.buttons["A"]; XCTAssertTrue(photo.waitForExistence(timeout: 10)); photo.click()
        for control in [app.popUpButtons["sourceDate"], app.popUpButtons["sourceFormat"], app.checkBoxes["只看已选"], app.buttons["importSelected"], app.sliders["缩略图大小"]] {
            XCTAssertTrue(control.isHittable, control.debugDescription)
            XCTAssertTrue(window.frame.contains(control.frame), control.debugDescription)
        }
        XCTAssertTrue(app.images.matching(NSPredicate(format: "identifier BEGINSWITH %@", "photoPreviewImage:")).firstMatch.waitForExistence(timeout: 5))
        try audit("source")
        let sourceImage = XCTAttachment(screenshot: window.screenshot()); sourceImage.name = "Compact source"; sourceImage.lifetime = .keepAlways; add(sourceImage)
        app.menuBars.menuBarItems["File"].click(); app.menuItems["打开本机照片库…"].click()
        try chooseFixtureFolder(app, root: fixtures.appendingPathComponent("NativeFaces"), expectedEntry: "Fixture Ready")
        XCTAssertTrue(app.staticTexts["libraryStatus"].waitForExistence(timeout: 10))
        for control in [app.popUpButtons["libraryPerson"], app.popUpButtons["libraryStage"], app.checkBoxes["libraryTrash"], app.menuButtons["libraryOrganize"], app.sliders["照片库缩略图大小"]] {
            XCTAssertTrue(control.isHittable, control.debugDescription)
            XCTAssertTrue(window.frame.contains(control.frame), control.debugDescription)
        }
        let libraryPhoto = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "libraryPhoto:")).firstMatch
        XCTAssertTrue(libraryPhoto.waitForExistence(timeout: 5)); libraryPhoto.click()
        XCTAssertTrue(app.images.matching(NSPredicate(format: "identifier BEGINSWITH %@", "photoPreviewImage:")).firstMatch.waitForExistence(timeout: 5))
        try audit("library")
        let libraryImage = XCTAttachment(screenshot: window.screenshot()); libraryImage.name = "Compact library"; libraryImage.lifetime = .keepAlways; add(libraryImage)
        XCTAssertTrue(auditIssues.isEmpty, "Custom photo accessibility issues: \(auditIssues.count). See attachments.")
    }
    @MainActor func testPhotoCardKeyboardToggleAndOpenPreserveSelection() throws {
        continueAfterFailure = false
        let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures")
        let app = XCUIApplication(); defer { app.terminate() }
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.buttons["chooseSource"].click()
        try chooseFixtureFolder(app, root: fixtures.appendingPathComponent("UITestSource/JPEG"), expectedEntry: "A.JPG")
        let source = app.buttons["A"]; XCTAssertTrue(source.waitForExistence(timeout: 10)); source.click()
        app.typeKey(.space, modifierFlags: [])
        XCTAssertEqual(app.staticTexts["sourceSelectionStatus"].value as? String, "1 张照片 · 已选 0 张 · 已选 0 个文件夹")
        app.typeKey(.space, modifierFlags: [])
        app.typeKey(.return, modifierFlags: [])
        XCTAssertTrue(app.buttons["viewerActualSize"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["已选中"].exists)
        app.buttons["关闭"].click()
        let info = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: fixtures.appendingPathComponent("faces-ui.json"))) as? [String:Any])
        let ids = try XCTUnwrap(info["photos"] as? [String])
        app.menuBars.menuBarItems["File"].click(); app.menuItems["打开本机照片库…"].click()
        try chooseFixtureFolder(app, root: fixtures.appendingPathComponent("NativeFaces"), expectedEntry: "Fixture Ready")
        let photo = app.buttons["libraryPhoto:" + (try XCTUnwrap(ids.first))]
        XCTAssertTrue(photo.waitForExistence(timeout: 10)); photo.click()
        app.typeKey(.space, modifierFlags: [])
        XCTAssertTrue((app.staticTexts["libraryStatus"].value as? String ?? "").contains("已选 0 张"))
        app.typeKey(.space, modifierFlags: [])
        app.typeKey(.return, modifierFlags: [])
        XCTAssertTrue(app.buttons["viewerActualSize"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["已选中"].exists)
        app.buttons["关闭"].click()
        photo.doubleClick()
        XCTAssertTrue(app.buttons["viewerActualSize"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["已选中"].exists)
    }
    @MainActor func testSourceBackAndForwardRestoreScrolledPhoto() throws {
        continueAfterFailure = false
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures/AutoscrollSource")
        let app = XCUIApplication(); defer { app.terminate() }
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES", "-thumbnailSize", "120"]
        app.launch(); app.activate(); app.buttons["chooseSource"].click()
        try chooseFixtureFolder(app, root: root, expectedEntry: "Item000.JPG")
        XCTAssertTrue(app.buttons["Item000"].waitForExistence(timeout: 15))
        let grid = app.scrollViews["sourceGrid"]
        grid.scroll(byDeltaX: 0, deltaY: -650)
        let visible = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Item")).allElementsBoundByIndex
            .filter { $0.isHittable && $0.frame.minY >= grid.frame.minY + 10 && $0.frame.maxY <= grid.frame.maxY - 10 }
            .sorted { $0.frame.minY < $1.frame.minY }
        let anchor = try XCTUnwrap(visible.first).label
        XCTAssertNotEqual(anchor, "Item000")
        app.buttons["sourceRoot"].click()
        XCTAssertTrue(app.buttons["Item000"].isHittable)
        app.buttons["sourceBack"].click()
        let returnedState = XCTAttachment(string: "Expected: \(anchor)\n" + app.debugDescription)
        returnedState.lifetime = .keepAlways; add(returnedState)
        let returned = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: app.buttons[anchor])
        XCTAssertEqual(XCTWaiter.wait(for: [returned], timeout: 5), .completed)
        XCTAssertFalse(app.buttons["Item000"].isHittable)
        app.buttons["sourceForward"].click()
        XCTAssertTrue(app.buttons["Item000"].isHittable)
        app.buttons["sourceBack"].click()
        XCTAssertTrue(app.buttons[anchor].isHittable)
        app.buttons["chooseSource"].click()
        XCTAssertTrue(app.dialogs["open-panel"].images["Item000.JPG"].waitForExistence(timeout: 10))
        app.buttons["OKButton"].click()
        let reset = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: app.buttons["Item000"])
        XCTAssertEqual(XCTWaiter.wait(for: [reset], timeout: 10), .completed)
    }
    @MainActor func testMarqueeAutoscrollKeepsEarlierSelectionsAndStopsOnRelease() throws {
        continueAfterFailure = false
        let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures")
        // The UI runner cannot create Desktop fixtures under host privacy controls.
        let root = fixtures.appendingPathComponent("AutoscrollSource")
        XCTAssertTrue(FileManager.default.fileExists(atPath: root.appendingPathComponent("Item079.JPG").path))
        let app = XCUIApplication(); defer { app.terminate() }
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES", "-thumbnailSize", "120"]
        app.launch(); app.activate(); app.buttons["chooseSource"].click()
        try chooseFixtureFolder(app, root: root, expectedEntry: "Item000.JPG")
        XCTAssertTrue(app.buttons["Item000"].waitForExistence(timeout: 15))
        let grid = app.scrollViews["sourceGrid"]
        let visibleBefore = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Item")).allElementsBoundByIndex.filter(\.isHittable).count
        let start = grid.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 3, dy: 3))
        let edge = grid.coordinate(withNormalizedOffset: CGVector(dx: 0.99, dy: 0.99))
        start.click(forDuration: 0.1, thenDragTo: edge, withVelocity: .slow, thenHoldForDuration: 2)
        let statusText = app.staticTexts["sourceSelectionStatus"]
        let status = statusText.value as? String ?? statusText.label
        let pattern = try NSRegularExpression(pattern: "已选 (\\d+) 张")
        let range = NSRange(status.startIndex..., in: status)
        let match = try XCTUnwrap(pattern.firstMatch(in: status, range: range))
        let countRange = try XCTUnwrap(Range(match.range(at: 1), in: status))
        XCTAssertGreaterThan(try XCTUnwrap(Int(status[countRange])), visibleBefore)
        XCTAssertFalse(app.buttons["Item000，已选中"].isHittable)
        let selected = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@ AND label CONTAINS %@", "Item", "已选中")).allElementsBoundByIndex.first(where: \.isHittable)
        let card = try XCTUnwrap(selected); let restingFrame = card.frame
        // A delayed predicate checks the drag task has stopped without changing selection.
        let deadline = Date().addingTimeInterval(0.3)
        let settled = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in Date() >= deadline }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [settled], timeout: 2), .completed)
        XCTAssertEqual(card.frame.minY, restingFrame.minY, accuracy: 1)
        // Returning to the top must reveal the original selected card.
        grid.scroll(byDeltaX: 0, deltaY: 5000)
        XCTAssertTrue(app.buttons["Item000，已选中"].waitForExistence(timeout: 5))
    }
    @MainActor func testWholeLibrarySystemTrashRequiresNameAndRetainsData() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures")
        let info = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: fixtures.appendingPathComponent("recycle-ui.json"))) as? [String:String])
        let root = URL(fileURLWithPath: try XCTUnwrap(info["root"]))
        let source = URL(fileURLWithPath: try XCTUnwrap(info["source"])), before = try Data(contentsOf: source)
        let fd = Darwin.open(root.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC)
        XCTAssertGreaterThanOrEqual(fd, 0); defer { Darwin.close(fd) }
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.menuBars.menuBarItems["File"].click(); app.menuItems["打开本机照片库…"].click()
        try chooseFixtureFolder(app, root: root, expectedEntry: "Fixture Ready")
        let photoID = "libraryPhoto:" + (try XCTUnwrap(info["photo"]))
        XCTAssertTrue(app.buttons[photoID].waitForExistence(timeout: 10))
        app.menuButtons["libraryActions"].click(); app.menuItems["将整个照片库移入系统废纸篓…"].click()
        XCTAssertTrue(app.staticTexts["libraryRecycleSheet"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["confirmRecycleLibrary"].isEnabled)
        app.textFields["confirmLibraryName"].click(); app.textFields["confirmLibraryName"].typeText("wrong")
        XCTAssertFalse(app.buttons["confirmRecycleLibrary"].isEnabled)
        app.textFields["confirmLibraryName"].typeKey("a", modifierFlags: .command)
        app.textFields["confirmLibraryName"].typeText(root.lastPathComponent)
        app.buttons["confirmRecycleLibrary"].click()
        XCTAssertTrue(app.staticTexts["libraryRecycleNotice"].waitForExistence(timeout: 15))
        XCTAssertFalse(FileManager.default.fileExists(atPath: root.path))
        XCTAssertEqual(try Data(contentsOf: source), before)
        var path = [CChar](repeating: 0, count: Int(MAXPATHLEN))
        XCTAssertEqual(fcntl(fd, F_GETPATH, &path), 0)
        let recycled = URL(fileURLWithPath: String(cString: path))
        XCTAssertNotEqual(recycled.path, root.path)
        XCTAssertEqual(recycled.deletingLastPathComponent().standardizedFileURL,
                       URL(fileURLWithPath: String(cString: try XCTUnwrap(getpwuid(getuid())).pointee.pw_dir)).appendingPathComponent(".Trash").standardizedFileURL)
        var retained = stat()
        XCTAssertEqual(fstat(fd, &retained), 0)
        XCTAssertTrue((retained.st_mode & S_IFMT) == S_IFDIR)
        // The UI runner lacks permission to move items out of Trash. Host-side
        // fixture cleanup restores this exact root; native integration covers reopen.
        let receipt = XCTAttachment(string: recycled.path)
        receipt.name = "Disposable library retained in system Trash"; receipt.lifetime = .keepAlways
        add(receipt)
    }
    @MainActor func testNativePendingPurgeAllowsRetryButBlocksRestore() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures")
        let info = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: fixtures.appendingPathComponent("purge-ui.json"))) as? [String:String])
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.menuBars.menuBarItems["File"].click(); app.menuItems["打开本机照片库…"].click()
        try chooseFixtureFolder(app, root: URL(fileURLWithPath: try XCTUnwrap(info["root"])), expectedEntry: "Fixture Ready")
        let photo = app.buttons["libraryPhoto:" + (try XCTUnwrap(info["photo"]))]
        app.checkBoxes["libraryTrash"].click(); XCTAssertTrue(photo.waitForExistence(timeout: 10)); photo.click()
        app.menuButtons["libraryOrganize"].click()
        XCTAssertFalse(app.menuItems["恢复所选照片"].isEnabled)
        XCTAssertTrue(app.menuItems["永久删除所选…"].isEnabled)
        app.menuItems["永久删除所选…"].click(); app.buttons["永久删除"].click()
        let removed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: photo)
        XCTAssertEqual(XCTWaiter.wait(for: [removed], timeout: 10), .completed)
        app.buttons["showWorkReport"].click()
        XCTAssertTrue((app.staticTexts["workReportSummary"].value as? String ?? app.staticTexts["workReportSummary"].label).contains("永久删除 1 张"))
    }
    @MainActor func testNativeTrashRestoreAndPurgeKeepSource() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures")
        let info = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: fixtures.appendingPathComponent("trash-ui.json"))) as? [String:String])
        let source = URL(fileURLWithPath: try XCTUnwrap(info["source"])), before = try Data(contentsOf: source)
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.menuBars.menuBarItems["File"].click(); app.menuItems["打开本机照片库…"].click()
        try chooseFixtureFolder(app, root: URL(fileURLWithPath: try XCTUnwrap(info["root"])), expectedEntry: "Fixture Ready")
        let photo = app.buttons["libraryPhoto:" + (try XCTUnwrap(info["photo"]))]
        XCTAssertTrue(photo.waitForExistence(timeout: 10)); photo.click()
        app.menuButtons["libraryOrganize"].click(); app.menuItems["移入回收站…"].click(); app.buttons["移入回收站"].click()
        let trashed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: photo)
        XCTAssertEqual(XCTWaiter.wait(for: [trashed], timeout: 10), .completed)
        app.checkBoxes["libraryTrash"].click(); XCTAssertTrue(photo.waitForExistence(timeout: 5))
        photo.doubleClick()
        XCTAssertTrue(app.buttons["viewerActualSize"].waitForExistence(timeout: 5))
        app.buttons["关闭"].click()
        app.menuButtons["libraryOrganize"].click(); app.menuItems["恢复所选照片"].click()
        let restored = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: photo)
        XCTAssertEqual(XCTWaiter.wait(for: [restored], timeout: 10), .completed)
        app.checkBoxes["libraryTrash"].click(); XCTAssertTrue(photo.waitForExistence(timeout: 5))
        app.menuButtons["libraryOrganize"].click(); app.menuItems["移入回收站…"].click(); app.buttons["移入回收站"].click()
        let again = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: photo)
        XCTAssertEqual(XCTWaiter.wait(for: [again], timeout: 10), .completed)
        app.checkBoxes["libraryTrash"].click(); XCTAssertTrue(photo.waitForExistence(timeout: 5))
        app.menuButtons["libraryOrganize"].click(); app.menuItems["永久删除所选…"].click(); app.buttons["永久删除"].click()
        let deleted = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: photo)
        XCTAssertEqual(XCTWaiter.wait(for: [deleted], timeout: 10), .completed)
        app.buttons["showWorkReport"].click()
        XCTAssertTrue((app.staticTexts["workReportSummary"].value as? String ?? app.staticTexts["workReportSummary"].label).contains("永久删除 1 张"))
        XCTAssertEqual(try Data(contentsOf: source), before)
    }
    @MainActor func testNativeExportVersionsAndCoverWithBundledRuntime() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures")
        let values = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: fixtures.appendingPathComponent("export-ui.json"))) as? [String:String])
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.menuBars.menuBarItems["File"].click(); app.menuItems["打开本机照片库…"].click()
        try chooseFixtureFolder(app, root: URL(fileURLWithPath: try XCTUnwrap(values["root"])), expectedEntry: "Fixture Ready")
        let photo = app.buttons["libraryPhoto:" + (try XCTUnwrap(values["photo"]))]
        XCTAssertTrue(photo.waitForExistence(timeout: 10)); photo.click()
        app.menuButtons["libraryOrganize"].click(); app.menuItems["将 JPEG 标记为成片"].click()
        XCTAssertTrue(app.buttons["showWorkReport"].waitForExistence(timeout: 10))
        app.buttons["showWorkReport"].click()
        XCTAssertTrue((app.staticTexts["workReportSummary"].value as? String ?? app.staticTexts["workReportSummary"].label).contains("完成 1 张"))
        app.buttons["关闭"].click()
        app.menuButtons["libraryOrganize"].click(); app.menuItems["成片版本…"].click()
        XCTAssertTrue(app.staticTexts["exportSheet"].waitForExistence(timeout: 5))
        let covers = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "exportCover:"))
        XCTAssertEqual(covers.count, 1)
        app.buttons["linkExport"].click()
        app.dialogs["open-panel"].typeKey("g", modifierFlags: [.command, .shift])
        let path = app.textFields["PathTextField"]
        XCTAssertTrue(path.waitForExistence(timeout: 5)); path.typeKey("a", modifierFlags: .command)
        let file = try XCTUnwrap(values["version"])
        for chunk in stride(from: 0, to: Array(file).count, by: 24) {
            path.typeText(String(Array(file)[chunk..<min(chunk+24,Array(file).count)]))
        }
        XCTAssertEqual(path.value as? String, file)
        let goto = app.sheets["GoToWindow"]
        XCTAssertTrue(goto.descendants(matching: .any)[file].waitForExistence(timeout: 10))
        path.typeKey(.return, modifierFlags: [])
        if goto.exists { goto.typeKey(.return, modifierFlags: []) }
        XCTAssertTrue(app.dialogs["open-panel"].images["Version 2.JPG"].waitForExistence(timeout: 10))
        app.dialogs["open-panel"].images["Version 2.JPG"].click(); app.buttons["OKButton"].click()
        let two = XCTNSPredicateExpectation(predicate: NSPredicate(format: "count == 2"), object: covers)
        XCTAssertEqual(XCTWaiter.wait(for: [two], timeout: 10), .completed)
        covers.element(boundBy: 0).click()
        let coverChanged = XCTNSPredicateExpectation(predicate: NSPredicate(format: "enabled == true"), object: covers.element(boundBy: 1))
        XCTAssertEqual(XCTWaiter.wait(for: [coverChanged], timeout: 10), .completed)
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "unlinkExport:")).element(boundBy: 0).click()
        let one = XCTNSPredicateExpectation(predicate: NSPredicate(format: "count == 1"), object: covers)
        XCTAssertEqual(XCTWaiter.wait(for: [one], timeout: 10), .completed)
        app.buttons["关闭"].click()
        app.popUpButtons["libraryStage"].click(); app.menuItems["成片"].click()
        XCTAssertTrue(photo.exists)
    }
    @MainActor func testNativeRecoveryIsExplicitAndNeverExecutesHistoricalSQL() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.menuBars.menuBarItems["File"].click(); app.menuItems["打开本机照片库…"].click()
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures/NativeRecovery")
        try chooseFixtureFolder(app, root: root, expectedEntry: "Fixture Ready")
        XCTAssertTrue(app.buttons["recoverLibrary"].waitForExistence(timeout: 10))
        app.menuButtons["libraryActions"].click(); XCTAssertFalse(app.menuItems["新建活动…"].isEnabled)
        app.typeKey(.escape, modifierFlags: [])
        app.buttons["recoverLibrary"].click(); app.buttons["检查并回滚"].click()
        XCTAssertTrue(app.staticTexts["workReportSummary"].waitForExistence(timeout: 10))
        XCTAssertTrue((app.staticTexts["workReportSummary"].value as? String ?? app.staticTexts["workReportSummary"].label).contains("已回滚 1 条"))
        app.buttons["关闭"].click()
        XCTAssertFalse(app.buttons["recoverLibrary"].exists)
        app.menuButtons["libraryActions"].click(); XCTAssertTrue(app.menuItems["新建活动…"].isEnabled)
    }
    @MainActor func testNativeImportPersonAndEditedWorkflow() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.menuBars.menuBarItems["File"].click(); app.menuItems["打开本机照片库…"].click()
        let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures")
        try chooseFixtureFolder(app, root: fixtures.appendingPathComponent("NativeWorkflow"), expectedEntry: "Fixture Ready")
        app.menuBars.menuBarItems["File"].click(); app.menuItems["选择照片来源…"].click()
        try chooseFixtureFolder(app, root: fixtures.appendingPathComponent("UITestSource"), expectedEntry: "JPEG")
        XCTAssertTrue(app.buttons["A"].waitForExistence(timeout: 10)); app.buttons["A"].click()
        app.buttons["B"].click()
        app.buttons["importSelected"].click()
        XCTAssertTrue(app.buttons["confirmImport"].waitForExistence(timeout: 5))
        app.popUpButtons["importActivity"].click(); app.menuItems["新活动…"].click()
        app.textFields["newImportActivity"].click(); app.textFields["newImportActivity"].typeText("UI-" + UUID().uuidString.prefix(8))
        app.buttons["confirmImport"].click()
        XCTAssertTrue(app.staticTexts["workReportSummary"].waitForExistence(timeout: 15))
        XCTAssertTrue((app.staticTexts["workReportSummary"].value as? String ?? app.staticTexts["workReportSummary"].label).contains("新增 2 张"))
        app.buttons["查看照片库"].click()
        let photo = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "libraryPhoto:")).firstMatch
        XCTAssertTrue(photo.waitForExistence(timeout: 5))
        let importedID = photo.identifier
        let grid = app.scrollViews["libraryGrid"]
        let start = grid.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 3, dy: 3))
        let last = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "libraryPhoto:")).element(boundBy: 1)
        let end = grid.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: grid.frame.width - 3, dy: last.frame.maxY - grid.frame.minY - 3))
        start.click(forDuration: 0.1, thenDragTo: end)
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@ AND label CONTAINS %@", "libraryPhoto:", "已选中")).count, 2)
        app.menuButtons["libraryOrganize"].click(); app.menuItems["新建人物…"].click()
        XCTAssertTrue(app.textFields["newPersonName"].waitForExistence(timeout: 5))
        app.textFields["newPersonName"].click(); app.textFields["newPersonName"].typeText("Alice")
        app.buttons["confirmPerson"].click()
        XCTAssertTrue(app.menuButtons["libraryOrganize"].waitForExistence(timeout: 10))
        app.menuButtons["libraryOrganize"].click(); app.menuItems["设置人物归属…"].click()
        app.popUpButtons["assignPerson"].click(); app.menuItems["Alice"].click(); app.buttons["confirmPerson"].click()
        XCTAssertTrue(app.menuButtons["libraryOrganize"].waitForExistence(timeout: 10))
        app.menuButtons["libraryOrganize"].click(); app.menuItems["标记已修"].click()
        let idle = XCTNSPredicateExpectation(predicate: NSPredicate(format: "enabled == true"), object: app.menuButtons["libraryOrganize"])
        XCTAssertEqual(XCTWaiter.wait(for: [idle], timeout: 10), .completed)
        app.popUpButtons["libraryStage"].click(); app.menuItems["已修原片"].click()
        XCTAssertTrue(photo.exists)
        app.popUpButtons["libraryPerson"].click(); app.menuItems["Alice"].click()
        XCTAssertTrue(photo.exists)
        app.menuButtons["libraryOrganize"].click(); app.menuItems["重命名当前人物…"].click()
        let rename = app.textFields["renamePersonName"]
        XCTAssertTrue(rename.waitForExistence(timeout: 5)); rename.click(); rename.typeKey("a", modifierFlags: .command); rename.typeText("Alice New")
        XCTAssertEqual(rename.value as? String, "Alice New")
        app.buttons["confirmManagePerson"].click()
        XCTAssertTrue(app.menuButtons["libraryOrganize"].waitForExistence(timeout: 10))
        app.popUpButtons["libraryPerson"].click()
        XCTAssertTrue(app.menuItems["Alice New"].exists); app.menuItems["Alice New"].click()
        app.menuButtons["libraryOrganize"].click(); app.menuItems["合并当前人物…"].click()
        app.popUpButtons["mergeTarget"].click(); app.menuItems["合照"].click(); app.buttons["confirmManagePerson"].click()
        XCTAssertTrue(app.menuButtons["libraryOrganize"].waitForExistence(timeout: 10))
        app.popUpButtons["libraryPerson"].click(); app.menuItems["合照"].click()
        XCTAssertTrue(photo.exists)
        app.popUpButtons["libraryStage"].click(); app.menuItems["待修原片"].click()
        XCTAssertFalse(photo.exists)
        app.menuBars.menuBarItems["File"].click(); app.menuItems["关闭照片库"].click()
        XCTAssertTrue(app.descendants(matching: .any)["libraryEmpty"].waitForExistence(timeout: 10))
        app.menuBars.menuBarItems["File"].click(); app.menuItems["最近打开的照片库"].click(); app.menuItems["NativeWorkflow"].click()
        XCTAssertTrue(app.buttons[importedID].waitForExistence(timeout: 10))
    }
    @MainActor func testReadOnlyLibraryMappingStagesAndReport() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.menuBars.menuBarItems["File"].click(); app.menuItems["只读打开照片库…"].click()
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures/LegacyLibrary")
        try chooseFixtureFolder(app, root: root, expectedEntry: "活动")
        XCTAssertTrue(app.buttons["libraryPhoto:library-a"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["libraryPhoto:library-b"].exists)
        XCTAssertFalse(app.buttons["libraryPhoto:library-trash"].exists)
        app.textFields["legacyRoot"].click(); app.textFields["legacyRoot"].typeText("D:/照片库")
        app.buttons["应用路径映射"].click()
        XCTAssertTrue(app.buttons["libraryPhoto:library-a"].waitForExistence(timeout: 10))
        app.buttons["libraryPhoto:library-a"].doubleClick()
        XCTAssertTrue(app.buttons["viewerActualSize"].waitForExistence(timeout: 5))
        app.buttons["viewerActualSize"].click()
        XCTAssertEqual(app.staticTexts["viewerScale"].value as? String, "100%")
        app.buttons["关闭"].click()
        app.popUpButtons["libraryStage"].click(); app.menuItems["成片"].click()
        XCTAssertTrue(app.buttons["libraryPhoto:library-b"].exists)
        XCTAssertFalse(app.buttons["libraryPhoto:library-a"].exists)
        app.buttons["libraryPhoto:library-b"].doubleClick()
        XCTAssertTrue(app.buttons["viewerActualSize"].waitForExistence(timeout: 5))
        app.buttons["关闭"].click()
        app.buttons["libraryReadReport"].click()
        XCTAssertTrue(app.descendants(matching: .any)["catalogReport"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["import_members"].exists)
    }
    @MainActor func testDraggingFromGapSelectsPhotosAndFolders() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        try openFixtureSource(app)
        let grid = app.scrollViews["sourceGrid"]
        XCTAssertTrue(grid.waitForExistence(timeout: 5))
        // Start in the 16pt padding rather than on a card's native click surface.
        let start = grid.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 3, dy: 3))
        app.activate(); start.click()
        let last = app.buttons["C"]
        let end = grid.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: grid.frame.width - 3, dy: last.frame.maxY - grid.frame.minY - 3))
        start.click(forDuration: 0.1, thenDragTo: end)
        let screenshot = XCTAttachment(screenshot: app.screenshot()); screenshot.lifetime = .keepAlways; add(screenshot)
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "A，已选中")).firstMatch.waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "B，已选中")).firstMatch.exists)
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "C，已选中")).firstMatch.exists)
        // A blank click clears the selection; folders use the same marquee surface.
        app.scrollViews["sourceGrid"].coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 3, dy: 3)).click()
        XCTAssertTrue(app.buttons["A"].exists)
        app.buttons["sourceRoot"].click()
        let folderGrid = app.scrollViews["sourceGrid"]
        let folderStart = folderGrid.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 3, dy: 3))
        folderStart.click(forDuration: 0.1, thenDragTo: app.buttons["folderCard:ZZBroken"].coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.95)))
        XCTAssertTrue(app.buttons["folderCard:JPEG"].label.contains("已选择"))
        XCTAssertTrue(app.buttons["folderCard:Other"].label.contains("已选择"))
        XCTAssertTrue(app.buttons["folderCard:RAW"].label.contains("已选择"))
        XCTAssertTrue(app.buttons["folderCard:ZZBroken"].label.contains("已选择"))
    }
    @MainActor func testNativeEmptyStateAndSettings() {
        let app = XCUIApplication(); app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch()
        XCTAssertTrue(app.buttons["chooseSource"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.descendants(matching: .any)["sourceEmpty"].exists)
        app.activate()
        app.menuBars.menuBarItems["LaundryPhotoManager"].click()
        app.menuItems["Settings…"].click()
        XCTAssertTrue(app.descendants(matching: .any)["appSettings"].waitForExistence(timeout: 5))
        app.terminate()
    }
    @MainActor func testOnlySelectedDoubleClickPreservesAndOpensPreview() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        try openFixtureSource(app)
        app.buttons["A"].click()
        XCTAssertTrue(app.descendants(matching: .any)["detailShutter"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.descendants(matching: .any)["detailISO"].exists)
        app.checkBoxes["只看已选"].click()
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "A")).firstMatch.doubleClick()
        XCTAssertTrue(app.buttons["关闭"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["已选中"].exists)
        XCTAssertTrue(app.buttons["viewerActualSize"].waitForExistence(timeout: 5))
        app.buttons["viewerActualSize"].click()
        XCTAssertEqual(app.staticTexts["viewerScale"].value as? String, "100%")
        app.buttons["viewerZoomIn"].click()
        XCTAssertEqual(app.staticTexts["viewerScale"].value as? String, "125%")
        app.buttons["viewerZoomOut"].click()
        XCTAssertEqual(app.staticTexts["viewerScale"].value as? String, "100%")
        app.buttons["关闭"].click()
        app.checkBoxes["只看已选"].click()
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "A")).firstMatch.doubleClick()
        app.buttons["viewerActualSize"].click()
        app.buttons["viewerZoomIn"].click()
        app.buttons["viewerNext"].click()
        XCTAssertEqual(app.staticTexts["viewerMode"].value as? String, "适应窗口")
        XCTAssertTrue(app.buttons["选中照片"].exists)
        app.buttons["viewerPrevious"].click()
        XCTAssertTrue(app.buttons["已选中"].exists)
        app.buttons["viewerFit"].click()
        XCTAssertEqual(app.staticTexts["viewerMode"].value as? String, "适应窗口")
        app.buttons["viewerNext"].click()
        app.buttons["viewerNext"].click()
        XCTAssertTrue(app.buttons["viewerRetry"].waitForExistence(timeout: 5))
        app.buttons["viewerRetry"].click()
        XCTAssertTrue(app.buttons["viewerRetry"].waitForExistence(timeout: 5))
        app.sheets.firstMatch.typeKey(.leftArrow, modifierFlags: [])
        XCTAssertFalse(app.buttons["viewerRetry"].exists)
    }
    @MainActor func testFolderNavigationHistoryAndSelection() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); defer { app.terminate() }
        try openFixtureSource(app)
        XCTAssertTrue(app.buttons["sourceRoot"].exists)
        app.buttons["A"].click()
        app.buttons["sourceRoot"].click()
        let jpeg = app.buttons["folderCard:JPEG"]
        XCTAssertTrue(jpeg.waitForExistence(timeout: 5))
        jpeg.click()
        app.checkBoxes["只看已选"].click()
        jpeg.doubleClick()
        XCTAssertEqual(app.staticTexts["sourceLocation"].value as? String, "JPEG")
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "A，已选中")).firstMatch.exists)
        app.popUpButtons["sourceDate"].click(); app.menuItems["2026-11-03"].click()
        app.buttons["sourceRoot"].click()
        app.buttons["sourceBack"].click()
        XCTAssertEqual(app.staticTexts["sourceLocation"].value as? String, "JPEG")
        XCTAssertEqual(app.popUpButtons["sourceDate"].value as? String, "2026-11-03")
        app.buttons["sourceForward"].click()
        XCTAssertEqual(app.staticTexts["sourceLocation"].value as? String, "来源根目录")
        XCTAssertTrue(app.buttons["folderCard:JPEG"].label.contains("已选择"))
        app.windows.firstMatch.typeKey("a", modifierFlags: .command)
        XCTAssertTrue(app.buttons["folderCard:Other"].label.contains("已选择"))
        app.buttons["folderCard:Other"].click()
        app.windows.firstMatch.typeKey(.return, modifierFlags: [])
        XCTAssertEqual(app.staticTexts["sourceLocation"].value as? String, "Other")
        // XCTest punctuation synthesis did not activate Cmd+[ on this host;
        // exercise the same native menu command here, real keys are CUA-checked.
        app.menuBars.menuBarItems["浏览"].click(); app.menuItems["后退"].click()
        XCTAssertEqual(app.staticTexts["sourceLocation"].value as? String, "来源根目录")
        app.buttons["folderCard:JPEG"].doubleClick()
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "A")).firstMatch.doubleClick()
        XCTAssertTrue(app.buttons["已选中"].waitForExistence(timeout: 5))
        app.menuBars.menuBarItems["浏览"].click()
        XCTAssertFalse(app.menuItems["后退"].isEnabled)
        app.menuBars.menuBarItems["浏览"].typeKey(.escape, modifierFlags: [])
        app.buttons["关闭"].click()
        XCTAssertEqual(app.staticTexts["sourceLocation"].value as? String, "JPEG")
        app.windows.firstMatch.typeKey(.upArrow, modifierFlags: .command)
        XCTAssertEqual(app.staticTexts["sourceLocation"].value as? String, "来源根目录")
        app.buttons["folderCard:JPEG"].doubleClick()
        app.buttons["chooseSource"].click()
        XCTAssertTrue(app.dialogs["open-panel"].images["JPEG"].waitForExistence(timeout: 10))
        app.buttons["OKButton"].click()
        let reset = XCTNSPredicateExpectation(predicate: NSPredicate(format: "value == %@", "全部子文件夹"), object: app.staticTexts["sourceLocation"])
        XCTAssertEqual(XCTWaiter.wait(for: [reset], timeout: 10), .completed)
        XCTAssertFalse(app.buttons["sourceBack"].isEnabled)
        XCTAssertTrue(app.buttons["A"].exists)
    }
    @MainActor private func openFixtureSource(_ app: XCUIApplication) throws {
        // Prepared by the scheme on the host, outside XCTest's protected container.
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("build/fixtures/UITestSource")
        XCTAssertTrue(FileManager.default.fileExists(atPath: root.appendingPathComponent("JPEG/A.JPG").path))
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]; app.launch(); app.activate()
        app.buttons["chooseSource"].click()
        try chooseFixtureFolder(app, root: root, expectedEntry: "JPEG")
        guard app.buttons["A"].waitForExistence(timeout: 30) else { XCTFail("Source scan did not publish A"); return }
    }
    @MainActor private func chooseFixtureFolder(_ app: XCUIApplication, root: URL, expectedEntry: String) throws {
        app.dialogs["open-panel"].typeKey("g", modifierFlags: [.command, .shift])
        let pathField = app.textFields["PathTextField"]
        XCTAssertTrue(pathField.waitForExistence(timeout: 5))
        pathField.typeKey("a", modifierFlags: .command)
        // Keep synthetic key events short and verify the complete path before
        // interacting with the separate file-picker navigation service.
        let characters = Array(root.path)
        for start in stride(from: 0, to: characters.count, by: 24) {
            // Resolve the active Go To field again between short text batches.
            let currentField = app.textFields["PathTextField"]
            XCTAssertTrue(currentField.waitForExistence(timeout: 5))
            currentField.typeText(String(characters[start..<min(start + 24, characters.count)]))
        }
        XCTAssertEqual(pathField.value as? String, root.path)
        let goTo = app.sheets["GoToWindow"]
        // Wait for the picker to resolve the typed path, beyond field text alone.
        XCTAssertTrue(goTo.descendants(matching: .any)[root.path].waitForExistence(timeout: 10))
        // Keypad Enter commits Go To on the current macOS picker service.
        pathField.typeKey(.enter, modifierFlags: [])
        if goTo.exists { goTo.typeKey(.enter, modifierFlags: []) }
        let committedPath = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: goTo)
        if XCTWaiter.wait(for: [committedPath], timeout: 10) != .completed {
            // Setup was blocked in the OS file-picker service, before our
            // scanning/selection UI was reached. Keep this explicitly visible.
            throw XCTSkip("Xcode 27.2 file-picker service did not commit the Go To path; source/selection scenario requires native CUA verification on this host.")
        }
        // The picker navigates in a separate service after Go To closes.
        // Never press Read while it still shows the previous directory.
        guard app.dialogs["open-panel"].images[expectedEntry].waitForExistence(timeout: 10) else {
            XCTFail("Synthetic source directory did not finish opening"); return
        }
        app.buttons["OKButton"].click()
    }

}
