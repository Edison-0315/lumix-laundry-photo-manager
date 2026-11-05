import SwiftUI
import AppKit
import Observation
import PhotoWorkflowCore
import UniformTypeIdentifiers

@MainActor @Observable final class LibraryModel {
    private(set) var catalog: LegacyCatalog?
    private(set) var busy = false
    private(set) var isManaged = false
    private(set) var canWrite = false
    var progress = ""
    var protectedSourceRoots: Set<URL> = []
    var oldRoot = ""
    var error: String?
    var activityID: String?
    var personID: String?
    var stage = "all"
    var showTrash = false
    var showDiagnostics = false
    var selection = SelectionState()
    var preview: PreviewSession?
    var lastReport: WorkReport?
    var recycleContext: LibraryRecycleContext?
    var libraryNotice: String?
    var recycledLibraryURL: URL?
    private(set) var recycling = false
    private(set) var recents: [RecentLibrary] = {
        guard let data = UserDefaults.standard.data(forKey: "recentLibraries.v1"),
              let entries = try? JSONDecoder().decode([RecentLibrary].self, from: data) else { return [] }
        return Array(entries.filter { $0.path.hasPrefix("/") }.prefix(10))
    }()
    private var task: Task<Void, Never>?
    private var requestID = UUID()
    private let backend = NativeLibraryBackend()
    private var writing = false
    private var marqueeStart: (selection: SelectionState, visible: [PhotoID])?
    var isMarqueeSelecting: Bool { marqueeStart != nil }
    var activities: [CatalogRecord] {
        let deleted = Set(catalog?.rows("deleted_activities").compactMap { $0.text("activity_id") } ?? [])
        return (catalog?.rows("activities") ?? []).filter { showTrash || !deleted.contains($0.id) }
    }
    var people: [CatalogRecord] { (catalog?.rows("people") ?? []).filter { activityID == nil || $0.text("activity_id") == activityID } }
    var writableActivities: [CatalogRecord] {
        let deleted = Set(catalog?.rows("deleted_activities").compactMap { $0.text("activity_id") } ?? [])
        return (catalog?.rows("activities") ?? []).filter { !deleted.contains($0.id) }
    }
    var selectedActivePhotos: [CatalogPhoto] {
        (catalog?.photos ?? []).filter { selection.selected.contains($0.id) && !$0.trashed && !$0.purging }
    }
    var canEditSelection: Bool { canWrite && !busy && !showTrash && !selectedActivePhotos.isEmpty && selectedActivePhotos.count == selection.selected.count }
    var selectedActivityID: String? {
        let ids = Set(selectedActivePhotos.map(\.activityID))
        return ids.count == 1 ? ids.first : nil
    }
    var selectedTrashPhotos: [CatalogPhoto] {
        (catalog?.photos ?? []).filter { selection.selected.contains($0.id) && ($0.trashed || $0.purging) }
    }
    var canRestore: Bool { canWrite && !busy && !selectedTrashPhotos.isEmpty && selectedTrashPhotos.count == selection.selected.count && !selectedTrashPhotos.contains(where: \.purging) }
    var canPurge: Bool {
        isManaged && !busy && !selectedTrashPhotos.isEmpty && selectedTrashPhotos.count == selection.selected.count &&
        !(catalog?.rows("operations").contains { $0.text("phase") != "committed" } ?? true)
    }
    func restoreSelection() {
        guard canRestore else { return }
        perform("restore_photos", params: ["ids": selectedTrashPhotos.map { $0.id.rawValue }], reportTitle: "恢复结果")
    }
    func delete(_ action: LibraryDeletion) {
        guard isManaged, !busy else { return }
        switch action {
        case .photos(let ids):
            guard canWrite else { return }
            perform("trash_photos", params: ["ids": ids.map(\.rawValue)], reportTitle: "移入回收站结果")
        case .person(let id):
            guard canWrite else { return }
            perform("delete_people", params: ["ids": [id]], reportTitle: "移除人物分类结果")
        case .activity(let id):
            guard canWrite else { return }
            perform("delete_activity", params: ["activity_id": id], reportTitle: "活动移入回收站结果")
        case .purge(let ids):
            perform("purge_trash", params: ["ids": ids.map(\.rawValue)], reportTitle: "永久删除结果")
        }
    }
    var currentPerson: CatalogRecord? { catalog?.rows("people").first { $0.id == personID } }
    var singlePhoto: CatalogPhoto? {
        guard canEditSelection, selectedActivePhotos.count == 1, let current, selection.selected.contains(current.id) else { return nil }
        return current
    }
    var latestUndoID: String? {
        catalog?.rows("operations").last { $0.text("kind") == "move" && $0.text("phase") == "committed" && $0.text("error") == nil }?.id
    }
    func setFinished(_ value: Bool) {
        guard canEditSelection else { return }
        perform("set_finished", params: ["ids": selectedActivePhotos.map { $0.id.rawValue }, "value": value], reportTitle: value ? "标记成片结果" : "解除成片结果")
    }
    func chooseExport(_ id: PhotoID) {
        guard canWrite, !busy else { return }
        let panel = NSOpenPanel()
        panel.title = "关联导出的成片"; panel.prompt = "关联"
        panel.allowedContentTypes = [.jpeg, .png, .tiff, .webP]
        panel.canChooseFiles = true; panel.canChooseDirectories = false; panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url { perform("link_export", params: ["photo_id": id.rawValue, "path": url.path]) }
    }
    func setCover(_ id: PhotoID, asset: String) {
        guard canWrite else { return }
        perform("set_export_cover", params: ["photo_id": id.rawValue, "asset_id": asset])
    }
    func unlinkExport(_ id: PhotoID, asset: String) {
        guard canWrite else { return }
        perform("unlink_export", params: ["photo_id": id.rawValue, "asset_id": asset])
    }
    func undoLatest() {
        guard canWrite, let id = latestUndoID else { return }
        perform("undo_operation", params: ["operation_id": id])
    }
    func relinkMissing() {
        guard let photo = singlePhoto else { return }
        let panel = NSOpenPanel()
        panel.title = "选择用于找回缺失文件的文件夹"; panel.prompt = "查找"
        panel.canChooseDirectories = true; panel.canChooseFiles = false; panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let root = panel.url {
            perform("relink_missing", params: ["photo_id": photo.id.rawValue, "root": root.path], reportTitle: "缺失文件找回结果")
        }
    }
    func revealAsset(_ asset: CatalogAsset) {
        guard let url = asset.url, ExternalEditor.reveal(url) else { error = "文件缺失或不可安全读取。"; return }
    }
    func revealCurrent() {
        guard let asset = current?.assets.first(where: { $0.id == current?.photo.primaryExportID }) ?? current?.assets.first(where: { $0.kind == .jpeg || $0.kind == .raw }) else { return }
        revealAsset(asset)
    }
    func openInEditor(_ kind: AssetKind) {
        guard let photo = singlePhoto, let url = photo.assets.first(where: { $0.kind == kind })?.url else { return }
        busy = true; progress = "正在打开 Photoshop…"; error = nil
        ExternalEditor.open(url) { [weak self] message in
            guard let self else { return }
            self.busy = false
            if let message { self.error = message }
            else { self.perform("record_opened", params: ["photo_id": photo.id.rawValue]) }
        }
    }
    var canRecover: Bool { isManaged && !busy && (catalog?.rows("operations").contains { $0.text("phase") != "committed" } ?? false) }
    func recoverPending() {
        guard canRecover else { return }
        perform("recover", params: [:], reportTitle: "未完成操作检查结果")
    }
    var visible: [CatalogPhoto] {
        let deleted = Set(catalog?.rows("deleted_activities").compactMap { $0.text("activity_id") } ?? [])
        return (catalog?.photos ?? []).filter { item in
            (showTrash ? item.trashed || item.purging : !item.trashed && !item.purging && !deleted.contains(item.activityID)) &&
            (activityID == nil || item.activityID == activityID) && (personID == nil || item.personID == personID) &&
            (stage == "all" || (stage == "pending" && !item.photo.edited) || (stage == "edited" && item.photo.edited) || (stage == "exports" && item.photo.primaryExportID != nil))
        }
    }
    var current: CatalogPhoto? { visible.first { $0.id == selection.current } }
    func choose() {
        guard !busy else { return }
        let panel = NSOpenPanel()
        panel.title = "只读打开照片库（选择包含 .片集 的文件夹）"; panel.prompt = "只读打开"
        panel.canChooseDirectories = true; panel.canChooseFiles = false
        panel.canCreateDirectories = false; panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let root = panel.url {
            if catalog?.root != root { oldRoot = "" }
            load(root)
        }
    }
    func create() {
        guard !busy else { return }
        let panel = NSSavePanel()
        panel.title = "新建本机照片库"; panel.prompt = "新建"
        panel.nameFieldStringValue = "我的照片库"; panel.canCreateDirectories = false
        panel.directoryURL = catalog?.root.deletingLastPathComponent() ?? FileManager.default.urls(for: .picturesDirectory, in: .userDomainMask).first
        if panel.runModal() == .OK, let root = panel.url {
            perform("create", params: ["root": root.path, "protected_roots": protectedSourceRoots.map(\.path)])
        }
    }
    func openManaged() {
        guard !busy else { return }
        let panel = NSOpenPanel()
        panel.title = "打开本应用新建的照片库"; panel.prompt = "打开"
        panel.canChooseDirectories = true; panel.canChooseFiles = false
        panel.canCreateDirectories = false; panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let root = panel.url { perform("open", params: ["root": root.path]) }
    }
    func openRecent(_ entry: RecentLibrary) {
        guard !busy else { return }
        if entry.managed { perform("open", params: ["root": entry.path]) }
        else { oldRoot = entry.oldRoot; load(entry.root) }
    }
    func clearRecents() { recents = []; UserDefaults.standard.removeObject(forKey: "recentLibraries.v1") }
    private var recycleScope: [String: Any] {
        ["protected_roots": protectedSourceRoots.map(\.path), "blocked_paths": [Bundle.main.bundleURL.path]]
    }
    func prepareRecycling() {
        guard isManaged, canWrite, !busy else { return }
        busy = true; writing = true; error = nil; progress = "正在统计照片库…"
        let data: Data
        do { data = try JSONSerialization.data(withJSONObject: recycleScope) }
        catch { self.error = error.localizedDescription; busy = false; writing = false; return }
        task = Task {
            do {
                let result = try await backend.request("inspect_recycle", params: data)
                let plan = try JSONDecoder().decode(LibraryRecyclePlan.self, from: result)
                recycleContext = try LibraryRecycleContext(plan)
            } catch { self.error = error.localizedDescription }
            busy = false; writing = false; task = nil
        }
    }
    func recycleLibrary(_ context: LibraryRecycleContext, name: String) {
        guard isManaged, canWrite, !busy, catalog?.root.path == context.plan.root else { return }
        var parameters = recycleScope
        parameters["token"] = context.plan.token; parameters["name"] = name
        let data: Data
        do { data = try JSONSerialization.data(withJSONObject: parameters) }
        catch { self.error = error.localizedDescription; return }
        busy = true; recycling = true; error = nil; progress = "正在移入系统废纸篓…"
        task = Task {
            do {
                let destination = try await backend.recycle(context, params: data)
                await backend.close()
                recents.removeAll { $0.path == context.plan.root }
                if let data = try? JSONEncoder().encode(recents) { UserDefaults.standard.set(data, forKey: "recentLibraries.v1") }
                catalog = nil; isManaged = false; canWrite = false; oldRoot = ""
                activityID = nil; personID = nil; stage = "all"; showTrash = false
                selection = SelectionState(); preview = nil; showDiagnostics = false; lastReport = nil
                recycleContext = nil; marqueeStart = nil
                libraryNotice = "已将“\(context.plan.name)”移入系统废纸篓，可在 Finder 中取回。"
                recycledLibraryURL = destination
            } catch {
                self.error = error.localizedDescription
                if let state = try? await backend.request("state"), let value = try? JSONDecoder().decode(NativeLibraryState.self, from: state) { canWrite = value.writable }
                else { canWrite = false }
            }
            busy = false; recycling = false; task = nil
        }
    }
    private func remember(_ root: URL, managed: Bool) {
        recents.removeAll { $0.path == root.path }
        recents.insert(RecentLibrary(path: root.path, managed: managed, oldRoot: managed ? "" : oldRoot), at: 0)
        recents = Array(recents.prefix(10))
        if let data = try? JSONEncoder().encode(recents) { UserDefaults.standard.set(data, forKey: "recentLibraries.v1") }
    }
    func closeLibrary() {
        guard !busy else { return }
        busy = true
        task = Task {
            await backend.close()
            catalog = nil; isManaged = false; canWrite = false; oldRoot = ""
            activityID = nil; personID = nil; stage = "all"; showTrash = false
            selection = SelectionState(); preview = nil; showDiagnostics = false
            lastReport = nil; error = nil; progress = ""; marqueeStart = nil
            recycleContext = nil; libraryNotice = nil; recycledLibraryURL = nil
            busy = false; task = nil
        }
    }
    func createActivity(_ name: String) {
        guard canWrite else { return }
        perform("create_activity", params: ["name": name])
    }
    func createPerson(activity: String, name: String) {
        guard canWrite else { return }
        perform("create_person", params: ["activity_id": activity, "name": name])
    }
    func classifyActivity() {
        guard canWrite, !busy, !showTrash, let activityID else { return }
        perform("classify_activity", params: ["activity_id": activityID], reportTitle: "自动人物整理结果")
    }
    func assign(_ ids: [PhotoID], person: String) {
        guard canWrite else { return }
        perform("set_person", params: ["ids": ids.map(\.rawValue), "person_id": person], reportTitle: "人物归属结果")
    }
    func setEdited(_ value: Bool) {
        guard canEditSelection else { return }
        perform("set_edited", params: ["ids": selectedActivePhotos.map { $0.id.rawValue }, "value": value], reportTitle: value ? "标记已修结果" : "恢复待修结果")
    }
    func renamePerson(_ id: String, name: String) {
        guard canWrite else { return }
        perform("rename_person", params: ["person_id": id, "name": name])
    }
    func mergePerson(_ source: String, into target: String) {
        guard canWrite else { return }
        perform("merge_people", params: ["source_id": source, "target_id": target], reportTitle: "人物合并结果")
    }
    func importSelected(_ photos: [PhotoGroup], root: URL, activity: String, format: ReadFormat) {
        guard canWrite, !photos.isEmpty else { return }
        let groups: [[String: Any]] = photos.map { photo in
            ["id": photo.id.rawValue, "stem": photo.stem, "captured_at": photo.capturedAt as Any? ?? NSNull(),
             "files": photo.files.map { ["kind": $0.kind.rawValue, "path": $0.url.path] }]
        }
        perform("import", params: ["source_root": root.path, "groups": groups, "activity": activity, "formats": format.rawValue], reportTitle: "导入结果")
    }
    func reload() {
        if isManaged { perform("state", params: [:]) }
        else if let root = catalog?.root { load(root) }
    }
    private func perform(_ method: String, params: [String: Any], reportTitle: String? = nil) {
        guard !busy else { return }
        let data: Data
        var guardedParams = params
        guardedParams["protected_roots"] = protectedSourceRoots.map(\.path)
        do { data = try JSONSerialization.data(withJSONObject: guardedParams) }
        catch { self.error = error.localizedDescription; return }
        busy = true; writing = true; error = nil; progress = "正在处理本机照片库…"
        if reportTitle != nil { lastReport = nil }
        let id = UUID(); requestID = id
        task = Task {
            do {
                var operationError: String?
                var result: Data?
                do {
                    result = try await backend.request(method, params: data) { [weak self] done, total, message in
                        Task { @MainActor in if self?.requestID == id && self?.busy == true { self?.progress = "\(message) \(done) / \(total)" } }
                    }
                } catch { operationError = error.localizedDescription }
                let stateData = try await backend.request("state")
                let state = try JSONDecoder().decode(NativeLibraryState.self, from: stateData)
                guard let path = state.root else { throw NativeBackendError(message: operationError ?? "尚未打开本机照片库") }
                let root = URL(fileURLWithPath: path)
                let value = try await Task.detached(priority: .userInitiated) { try LegacyCatalog.read(root: root) }.value
                guard requestID == id else { return }
                install(value); isManaged = true; canWrite = state.writable
                remember(root, managed: true)
                if let reportTitle, let result {
                    let details = try JSONDecoder().decode(BatchDetails.self, from: result)
                    lastReport = WorkReport(title: reportTitle, importing: method == "import", details: details)
                    if method == "import", let activity = details.activityID {
                        activityID = activity; personID = nil; stage = "all"; showTrash = false
                    }
                    if method == "classify_activity" { personID = nil }
                }
                error = operationError
                progress = state.pending.isEmpty ? "本机照片库已就绪" : "存在未完成操作，写入暂不可用。请先检查读取报告。"
            } catch {
                guard requestID == id else { return }
                self.error = error.localizedDescription; canWrite = false
            }
            if requestID == id { busy = false; writing = false; task = nil }
        }
    }
    private func load(_ root: URL) {
        guard !busy else { return }
        busy = true; error = nil
        let id = UUID(); requestID = id; let oldRoot = oldRoot.trimmingCharacters(in: .whitespacesAndNewlines)
        task = Task.detached(priority: .userInitiated) { [self] in
            do {
                let value = try LegacyCatalog.read(root: root, oldRoot: oldRoot.isEmpty ? nil : oldRoot)
                try Task.checkCancellation()
                await publish(value, id: id)
            } catch { await fail(error, id: id) }
        }
    }
    private func publish(_ value: LegacyCatalog, id: UUID) async {
        guard requestID == id else { return }
        if isManaged { await backend.close() }
        isManaged = false; canWrite = false
        install(value)
        remember(value.root, managed: false)
        busy = false; task = nil
    }
    private func install(_ value: LegacyCatalog) {
        let changedRoot = catalog?.root != value.root
        catalog = value
        let ids = Set(value.photos.map(\.id))
        selection.selected.formIntersection(ids)
        if let current = selection.current, !ids.contains(current) { selection.current = nil }
        if let anchor = selection.anchor, !ids.contains(anchor) { selection.anchor = nil }
        if !showTrash, let activityID, value.rows("deleted_activities").contains(where: { $0.text("activity_id") == activityID }) { self.activityID = nil; personID = nil }
        if let personID, !value.rows("people").contains(where: { $0.id == personID }) { self.personID = nil }
        if changedRoot {
            recycleContext = nil; libraryNotice = nil; recycledLibraryURL = nil
            activityID = nil; personID = nil; stage = "all"; showTrash = false
            selection = SelectionState(); preview = nil; showDiagnostics = false
            lastReport = nil
        }
    }
    private func fail(_ error: Error, id: UUID) {
        guard requestID == id else { return }
        self.error = error is CancellationError ? "读取已取消，保留此前照片库。" : "读取失败，保留此前照片库：" + error.localizedDescription
        busy = false; task = nil
    }
    func cancel() { guard !recycling else { return }; if writing { backend.cancel() } else { task?.cancel() } }
    func click(_ id: PhotoID, shift: Bool, additive: Bool) {
        selection.click(id, visible: visible.map(\.id), shift: shift, additive: additive)
    }
    func toggle(_ id: PhotoID) { click(id, shift: false, additive: false) }
    func open(_ id: PhotoID, fromDoubleClick: Bool = false) {
        guard !busy, let item = visible.first(where: { $0.id == id }), (isManaged || !item.trashed), !item.purging else { return }
        if fromDoubleClick { selection.doubleClick(id) } else { selection.current = id }
        let photos = visible.filter { (isManaged || !$0.trashed) && !$0.purging }.map(\.photo)
        preview = PreviewSession(photos: photos, current: id)
    }
    func selectVisible() { selection.selectVisible(visible.map(\.id)) }
    func deselectVisible() { selection.deselectVisible(visible.map(\.id)) }
}

extension LibraryModel: MarqueeSelecting {
    var canMarquee: Bool { !busy && preview == nil && !showDiagnostics }
    func beginMarquee() {
        guard canMarquee, marqueeStart == nil else { return }
        marqueeStart = (selection, visible.map(\.id))
    }
    func updateMarquee(photos: Set<PhotoID>, folders: Set<String>, additive: Bool) {
        guard let start = marqueeStart else { return }
        selection.marquee(photos.intersection(start.visible), starting: start.selection, visible: start.visible, additive: additive, deferFiltering: false)
    }
    func endMarquee(cancelled: Bool) {
        if cancelled, let start = marqueeStart { selection = start.selection }
        marqueeStart = nil
    }
}
