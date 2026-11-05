import Foundation
import Observation
import PhotoWorkflowCore
import AppKit
import Darwin
@MainActor @Observable final class AppModel {
    var snapshot = SourceSnapshot()
    var selection = SelectionState()
    var navigation = SourceNavigation()
    var folderChoices = FolderChoices()
    private(set) var sourceIndex: SourceFolderIndex?
    private(set) var sourceVersion = UUID()
    var location: SourceLocation {
        get { navigation.route.location }
        set { openLocation(newValue) }
    }
    var format: String {
        get { navigation.route.format }
        set {
            guard canNavigate else { return }
            var route = navigation.route; route.format = newValue; navigation.navigate(route)
        }
    }
    var date: String {
        get { navigation.route.date }
        set {
            guard canNavigate else { return }
            var route = navigation.route; route.date = newValue; navigation.navigate(route)
        }
    }
    var onlySelected = false
    var readFormat: ReadFormat = .both
    var writableLibraryRoot: URL?
    var busy = false
    var progress = ""
    var message: String?
    var showIssues = false
    var preview: PreviewSession?
    private var scanID = UUID()
    private var pendingSourceRoot: URL?
    private var scanTask: Task<Void, Never>?
    private var filterTask: Task<Void, Never>?
    private var marqueeStart: (selection: SelectionState, folders: FolderChoices, photos: [PhotoID], paths: Set<String>)?
    var isMarqueeSelecting: Bool { marqueeStart != nil }
    var photos: [PhotoGroup] { snapshot.result?.photos ?? [] }
    var importPhotos: [PhotoGroup] {
        let folders = folderChoices.allSelected
        return photos.filter { photo in
            selection.selected.contains(photo.id) || folders.contains { sourceIndex?.descends(photo.id, from: $0) == true }
        }
    }
    var root: URL? { snapshot.result?.root }
    var protectedSourceRoots: [URL] { [root, pendingSourceRoot].compactMap { $0 } }
    var current: PhotoGroup? { visible.first { $0.id == selection.current } }
    var canNavigate: Bool { root != nil && !busy && preview == nil && !showIssues }
    var canGoBack: Bool { canNavigate && navigation.canGoBack }
    var canGoForward: Bool { canNavigate && navigation.canGoForward }
    var canGoUp: Bool { canNavigate && location.parent != nil }
    var visible: [PhotoGroup] {
        photos.filter { p in
            sourceIndex?.contains(p.id, in: location) == true && matchesFilters(p) &&
            (!onlySelected || selection.filteredSelection.contains(p.id))
        }
    }
    var folders: [String] { sourceIndex?.paths ?? [] }
    var visibleFolders: [String] {
        (sourceIndex?.children(of: location) ?? []).filter {
            !onlySelected || folderChoices.filtered(in: location).contains($0)
        }
    }
    func directories(_ photo: PhotoGroup) -> Set<String> { sourceIndex?.directories(for: photo.id) ?? [] }
    private func matchesFilters(_ photo: PhotoGroup) -> Bool {
        (format == "all" || photo.files.contains { $0.kind.rawValue == format }) && (date == "all" || photo.dateKey == date)
    }
    func examples(in path: String) -> [PhotoGroup] {
        Array(photos.lazy.filter { self.sourceIndex?.descends($0.id, from: path) == true && self.matchesFilters($0) }.prefix(3))
    }
    func openLocation(_ target: SourceLocation) {
        guard canNavigate else { return }
        if case .folder(let path) = target, !folders.contains(path) { return }
        guard target != location else { return }
        finishFiltering()
        navigation.navigate(SourceRoute(location: target, date: "all", format: format))
        onlySelected = false; selection.current = nil
    }
    func goBack() {
        guard canGoBack else { return }
        finishFiltering(); navigation.back(); onlySelected = false; selection.current = nil
    }
    func goForward() {
        guard canGoForward else { return }
        finishFiltering(); navigation.forward(); onlySelected = false; selection.current = nil
    }
    func goUp() { if let parent = location.parent { openLocation(parent) } }
    func clickFolder(_ path: String) {
        guard canNavigate, visibleFolders.contains(path) else { return }
        folderChoices.click(path, scope: location, deferFiltering: onlySelected)
        deferSelectionFiltering()
    }
    func doubleClickFolder(_ path: String) {
        guard canNavigate, visibleFolders.contains(path) else { return }
        folderChoices.doubleClick(path, scope: location)
        openLocation(.folder(path))
    }
    private func finishFiltering() {
        endMarquee(cancelled: true)
        filterTask?.cancel(); selection.finishFiltering(); folderChoices.finishFiltering()
    }
    private func deferSelectionFiltering() {
        filterTask?.cancel()
        if onlySelected {
            filterTask = Task { [weak self] in
                do { try await Task.sleep(for: .seconds(NSEvent.doubleClickInterval + 0.1)) } catch { return }
                self?.selection.finishFiltering(); self?.folderChoices.finishFiltering()
            }
        }
    }
    func chooseSource() {
        guard !busy, let url = SourcePanel.choose() else { return }
        scan(url)
    }
    func scan(_ url: URL) {
        guard !busy else { return }
        if let library = writableLibraryRoot {
            let source = physicalDirectory(url).pathComponents
            let target = physicalDirectory(library).pathComponents
            if source.starts(with: target) || target.starts(with: source) {
                message = "照片来源不能与当前可写照片库重叠，请选择独立目录。"
                return
            }
        }
        busy = true; pendingSourceRoot = url; progress = "正在查找照片…"; message = nil
        let id = UUID(); scanID = id; let readFormat = readFormat
        scanTask = Task.detached(priority: .userInitiated) { [self] in
            do {
                let result = try SourceScanner.scan(root: url, format: readFormat, cancel: { Task.isCancelled }, progress: { done, total in
                    guard done % 20 == 0 || done == total else { return }
                    Task { @MainActor in if self.scanID == id { self.progress = total == 0 ? "正在查找照片…" : "读取照片信息 \(done) / \(total)" } }
                })
                await finish(result, id: id)
            } catch { await fail(error, id: id) }
        }
    }
    private func physicalDirectory(_ url: URL) -> URL {
        guard let path = url.path.withCString({ Darwin.realpath($0, nil) }) else { return url.standardizedFileURL }
        defer { free(path) }
        return URL(fileURLWithFileSystemRepresentation: path, isDirectory: true, relativeTo: nil)
    }
    private func finish(_ result: ScanResult, id: UUID) {
        guard id == scanID else { return }
        let published = snapshot.publish(result)
        if published {
            finishFiltering()
            sourceIndex = SourceFolderIndex(photos: result.photos, root: result.root)
            navigation.reset(); folderChoices.reset(); selection = SelectionState()
            sourceVersion = UUID()
            onlySelected = false; preview = nil
        }
        message = result.cancelled ? "读取已取消，保留此前选片。" : published ? "已读取 \(result.photos.count) 张照片" : "读取失败，保留此前选片。"
        // Failed scans also retain their diagnostics without replacing the previous snapshot.
        issues = result.issues
        busy = false; pendingSourceRoot = nil; scanTask = nil
    }
    var issues: [ScanIssue] = []
    private func fail(_ error: Error, id: UUID) {
        guard id == scanID else { return }
        message = "读取失败：" + error.localizedDescription + "；保留此前选片。"
        busy = false; pendingSourceRoot = nil; scanTask = nil
    }
    func cancel() { scanTask?.cancel(); progress = "正在停止读取…" }
    func beginMarquee() {
        guard canNavigate, marqueeStart == nil else { return }
        filterTask?.cancel()
        marqueeStart = (selection, folderChoices, visible.map(\.id), Set(visibleFolders))
    }
    func updateMarquee(photos: Set<PhotoID>, folders: Set<String>, additive: Bool) {
        guard let start = marqueeStart else { return }
        selection.marquee(photos.intersection(start.photos), starting: start.selection, visible: start.photos,
                          additive: additive, deferFiltering: onlySelected)
        folderChoices.marquee(folders.intersection(start.paths), starting: start.folders, scope: location,
                              additive: additive, deferFiltering: onlySelected)
    }
    func endMarquee(cancelled: Bool = false) {
        guard let start = marqueeStart else { return }
        marqueeStart = nil
        if cancelled { selection = start.selection; folderChoices = start.folders }
        selection.finishFiltering(); folderChoices.finishFiltering()
    }
    func click(_ id: PhotoID, shift: Bool, additive: Bool) {
        selection.click(id, visible: visible.map(\.id), shift: shift, additive: additive, deferFiltering: onlySelected)
        deferSelectionFiltering()
    }
    func doubleClick(_ id: PhotoID) {
        guard canNavigate else { return }
        finishFiltering(); selection.doubleClick(id); openPreview(id)
    }
    func openPreview(_ id: PhotoID) {
        guard canNavigate, visible.contains(where: { $0.id == id }) else { return }
        preview = PreviewSession(photos: visible, current: id)
    }
    func selectVisible() {
        guard canNavigate else { return }
        let folderKeys = visibleFolders
        selection.selectVisible(visible.map(\.id)); folderChoices.selectVisible(folderKeys, scope: location)
    }
    func deselectVisible() {
        guard canNavigate else { return }
        let folderKeys = visibleFolders
        selection.deselectVisible(visible.map(\.id)); folderChoices.deselectVisible(folderKeys, scope: location)
    }
}
struct PreviewSession: Identifiable {
    let id = UUID()
    let photos: [PhotoGroup]
    var current: PhotoID
}
