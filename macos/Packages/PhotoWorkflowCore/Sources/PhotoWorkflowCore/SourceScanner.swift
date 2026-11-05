import Foundation
import Darwin
public struct ScanIssue: Identifiable, Hashable, Sendable {
    public var id: String { path + operation + message }
    public let path: String
    public let operation: String
    public let message: String
    public let code: Int
    public init(path: String, operation: String, error: Error) {
        self.path = path; self.operation = operation; message = error.localizedDescription; code = (error as NSError).code
    }
}
public struct ScanResult: Sendable {
    public var root: URL
    public var photos: [PhotoGroup] = []
    public var issues: [ScanIssue] = []
    public var cancelled = false
    public init(root: URL) { self.root = root }
}
public struct SourceSnapshot: Sendable {
    public var result: ScanResult?
    public init() {}
    @discardableResult public mutating func publish(_ incoming: ScanResult) -> Bool {
        guard !incoming.cancelled, !incoming.photos.isEmpty || incoming.issues.isEmpty else { return false }; result = incoming; return true
    }
}
public enum SourceScanner {
    public static func scan(root: URL, format: ReadFormat = .both, cancel: () -> Bool = { false }, progress: (Int, Int) -> Void = { _,_ in }, inspect: (URL) throws -> Void = { _ in }) throws -> ScanResult {
        try read(root: root, format: format, cancel: cancel, progress: progress, inspect: inspect)
    }
}
extension SourceScanner {
    private static func read(root: URL, format: ReadFormat, cancel: () -> Bool, progress: (Int, Int) -> Void, inspect: (URL) throws -> Void) throws -> ScanResult {
        let root = root.standardizedFileURL.resolvingSymlinksInPath()
        guard try root.resourceValues(forKeys: [.isDirectoryKey]).isDirectory == true else { throw CocoaError(.fileReadInvalidFileName) }
        var result = ScanResult(root: root)
        let keys: Set<URLResourceKey> = [.isSymbolicLinkKey, .isDirectoryKey, .isRegularFileKey, .isAliasFileKey]
        guard let enumerator = FileManager.default.enumerator(at: root, includingPropertiesForKeys: Array(keys), errorHandler: { url, error in
            result.issues.append(.init(path: url.path, operation: "枚举目录", error: error)); return true
        }) else { throw CocoaError(.fileReadNoPermission) }
        var files: [FileAsset] = []
        progress(0, 0)
        for case let url as URL in enumerator {
            if cancel() { result.cancelled = true; return result }
            do {
                let values = try url.resourceValues(forKeys: keys)
                if values.isSymbolicLink == true || values.isAliasFile == true { enumerator.skipDescendants(); continue }
                guard values.isRegularFile == true, let kind = SourceExtensions.kind(url.lastPathComponent), format.includes(kind) else { continue }
                let components = url.resolvingSymlinksInPath().pathComponents
                guard components.starts(with: root.pathComponents) else { continue }
                try inspect(url)
                // Open for read only so OS-level denial is distinguished from an unsupported decoder.
                let fd = try SafeImageSource.fileDescriptor(url)
                defer { close(fd) }
                var byte: UInt8 = 0
                guard pread(fd, &byte, 1, 0) >= 0 else { throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno)) }
                files.append(.init(url: url, kind: kind))
            } catch { result.issues.append(.init(path: url.path, operation: "读取文件", error: error)) }
        }
        var groups = PhotoPairing.groups(files: files)
        for i in groups.indices {
            if cancel() { result.cancelled = true; return result }
            let candidates = groups[i].files.sorted { ($0.kind == .jpeg ? 0 : 1) < ($1.kind == .jpeg ? 0 : 1) }.filter { $0.kind != .xmp }
            for candidate in candidates {
                let info = ImageReader.info(candidate.url)
                if let date = info.capturedAt { groups[i].capturedAt = date; break }
            }
            if let primary = candidates.first, !ImageReader.info(primary.url).recognized {
                groups[i].warning = "系统无法读取此照片的图像信息，仍保留原文件。"
            }
            progress(i + 1, groups.count)
        }
        if cancel() { result.cancelled = true; return result }
        result.photos = groups
        return result
    }
}
