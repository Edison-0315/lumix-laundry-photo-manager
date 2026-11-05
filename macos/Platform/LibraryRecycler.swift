import Foundation
import Darwin

struct LibraryRecyclePlan: Decodable, Sendable {
    let token: String
    let name: String
    let root: String
    let rootIdentity: [Int64]
    let catalogIdentity: [Int64]
    let photoCount: Int
    let fileCount: Int
    let bytes: Int64
    enum CodingKeys: String, CodingKey {
        case token, name, root, bytes
        case rootIdentity = "root_identity", catalogIdentity = "catalog_identity"
        case photoCount = "photo_count", fileCount = "file_count"
    }
}
struct LibraryRecycleError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

/// Holds the previewed directory open, so a replaced name cannot reuse its inode.
final class LibraryRecycleContext: Identifiable, @unchecked Sendable {
    let plan: LibraryRecyclePlan
    var id: String { plan.token }
    private let fd: Int32
    init(_ plan: LibraryRecyclePlan) throws {
        self.plan = plan
        fd = Darwin.open(plan.root, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC)
        guard fd >= 0 else { throw LibraryRecycleError(message: "无法安全读取照片库目录") }
        try verify(URL(fileURLWithPath: plan.root))
    }
    deinit { Darwin.close(fd) }
    private func identity(_ status: stat) -> [Int64] { [Int64(status.st_dev), Int64(status.st_ino)] }
    func verify(_ root: URL) throws {
        var held = stat()
        guard fstat(fd, &held) == 0, identity(held) == plan.rootIdentity,
              root.path == plan.root else { throw LibraryRecycleError(message: "照片库目录位置或身份已变化，请重新预览") }
        let current = Darwin.open(root.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC)
        guard current >= 0 else { throw LibraryRecycleError(message: "照片库目录已移动或不可安全读取") }
        defer { Darwin.close(current) }
        var named = stat()
        guard fstat(current, &named) == 0, identity(named) == plan.rootIdentity else {
            throw LibraryRecycleError(message: "照片库目录被替换，未执行回收")
        }
        let database = Darwin.open(root.appendingPathComponent(".片集/catalog.sqlite3").path, O_RDONLY | O_NOFOLLOW_ANY | O_NONBLOCK | O_CLOEXEC)
        guard database >= 0 else { throw LibraryRecycleError(message: "照片库数据库不可安全读取") }
        defer { Darwin.close(database) }
        var info = stat()
        guard fstat(database, &info) == 0, info.st_mode & S_IFMT == S_IFREG, identity(info) == plan.catalogIdentity else {
            throw LibraryRecycleError(message: "照片库数据库被替换，未执行回收")
        }
    }
    func originalStillAtPath() -> Bool {
        let current = Darwin.open(plan.root, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC)
        guard current >= 0 else { return false }; defer { Darwin.close(current) }
        var status = stat()
        return fstat(current, &status) == 0 && identity(status) == plan.rootIdentity
    }
}

enum LibraryRecycler {
    static func systemTransfer(_ root: URL) throws -> URL? {
        var result: NSURL?
        try FileManager.default.trashItem(at: root, resultingItemURL: &result)
        return result.map { $0 as URL }
    }
    static func recycle(_ context: LibraryRecycleContext, transfer: (URL) throws -> URL? = systemTransfer, validate: () throws -> Void = {}) throws -> URL? {
        let coordinator = NSFileCoordinator(filePresenter: nil)
        var coordinationError: NSError?
        var operationError: Error?
        var result: URL?
        var performed = false
        coordinator.coordinate(writingItemAt: URL(fileURLWithPath: context.plan.root), options: .forDeleting, error: &coordinationError) { root in
            do {
                try validate()
                try context.verify(root)
                result = try transfer(root)
                guard !context.originalStillAtPath() else { throw LibraryRecycleError(message: "系统回收未完成，照片库仍在原位置") }
                performed = true
            } catch { operationError = error }
        }
        if let operationError { throw operationError }
        if let coordinationError { throw coordinationError }
        guard performed else { throw LibraryRecycleError(message: "系统文件协调未完成，未执行回收") }
        return result
    }
}
