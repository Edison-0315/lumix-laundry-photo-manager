import Foundation
import SQLite3
import Darwin

public struct CatalogReadError: LocalizedError, Sendable {
    public let message: String
    public var errorDescription: String? { message }
    init(_ message: String) { self.message = message }
}

/// SQLite only opens our disposable copy. Original DB, WAL and SHM are never opened by SQLite.
private struct CatalogSourceFile: Equatable {
    let bytes: Data
    let device: dev_t
    let inode: ino_t
    let modified: timespec
    static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.device == rhs.device && lhs.inode == rhs.inode && lhs.modified.tv_sec == rhs.modified.tv_sec &&
        lhs.modified.tv_nsec == rhs.modified.tv_nsec && lhs.bytes == rhs.bytes
    }
    static func read(_ url: URL, optional: Bool = false) throws -> Self? {
        let fd: Int32
        do { fd = try SafeImageSource.fileDescriptor(url) }
        catch { if optional && (error as NSError).code == Int(ENOENT) { return nil }; throw error }
        defer { Darwin.close(fd) }
        var before = stat(); guard fstat(fd, &before) == 0 else { throw CatalogReadError("无法检查数据库文件") }
        guard before.st_size <= 512 * 1024 * 1024 else { throw CatalogReadError("数据库快照文件超过 512 MB，暂不支持此规模") }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
        let bytes = try handle.readToEnd() ?? Data()
        var after = stat(); guard fstat(fd, &after) == 0,
            before.st_size == after.st_size, bytes.count == after.st_size,
            before.st_mtimespec.tv_sec == after.st_mtimespec.tv_sec, before.st_mtimespec.tv_nsec == after.st_mtimespec.tv_nsec
        else { throw CatalogReadError("照片库正在变化，请关闭其他照片管理程序后重新读取") }
        return .init(bytes: bytes, device: after.st_dev, inode: after.st_ino, modified: after.st_mtimespec)
    }
}

final class CatalogDatabase {
    private var handle: OpaquePointer?
    private let temporary: URL
    private var ownsTemporary = false
    init(root: URL) throws {
        guard let physical = realpath(FileManager.default.temporaryDirectory.path, nil) else { throw CatalogReadError("无法访问临时目录") }
        let tempRoot = URL(fileURLWithPath: String(cString: physical), isDirectory: true)
        free(physical)
        temporary = tempRoot.appendingPathComponent("Lumix-readonly-" + UUID().uuidString, isDirectory: true)
        let meta = root.appendingPathComponent(".片集", isDirectory: true)
        let names = ["catalog.sqlite3", "catalog.sqlite3-wal", "catalog.sqlite3-journal"]
        var original: [String: CatalogSourceFile] = [:]
        for name in names {
            try Task.checkCancellation()
            if let file = try CatalogSourceFile.read(meta.appendingPathComponent(name), optional: name != names[0]) { original[name] = file }
        }
        guard original[names[0]] != nil else { throw CatalogReadError("未找到 .片集/catalog.sqlite3") }
        guard original[names[2]]?.bytes.isEmpty != false else { throw CatalogReadError("旧库含有事务恢复日志，请在 Windows 原程序中完成恢复后再读取") }
        for name in names {
            guard try CatalogSourceFile.read(meta.appendingPathComponent(name), optional: name != names[0]) == original[name]
            else { throw CatalogReadError("数据库或 WAL 在快照期间发生变化，请关闭其他程序后重试") }
        }
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: false)
        ownsTemporary = true
        do {
            for name in names.prefix(2) {
                if let file = original[name], !file.bytes.isEmpty { try file.bytes.write(to: temporary.appendingPathComponent(name), options: .withoutOverwriting) }
            }
            let code = sqlite3_open_v2(temporary.appendingPathComponent(names[0]).path, &handle, SQLITE_OPEN_READWRITE | SQLITE_OPEN_NOFOLLOW, nil)
            guard code == SQLITE_OK else { throw failure("无法打开数据库快照") }
            sqlite3_busy_timeout(handle, 1000)
            try execute("PRAGMA trusted_schema=OFF; PRAGMA query_only=ON; BEGIN;")
            let check = try query("PRAGMA quick_check(1)")
            guard check.first?.text("quick_check") == "ok" else { throw CatalogReadError("数据库完整性检查未通过") }
        } catch {
            let originalError = error
            cleanup()
            throw originalError
        }
    }
    deinit { cleanup() }
    private func cleanup() {
        sqlite3_close_v2(handle); handle = nil
        if ownsTemporary { ownsTemporary = false; try? FileManager.default.removeItem(at: temporary) }
    }
    private func failure(_ message: String) -> CatalogReadError {
        CatalogReadError(message + "：" + (handle.map { String(cString: sqlite3_errmsg($0)) } ?? "SQLite 错误"))
    }
    private func execute(_ sql: String) throws {
        guard sqlite3_exec(handle, sql, nil, nil, nil) == SQLITE_OK else { throw failure("读取失败") }
    }
    func query(_ sql: String) throws -> [CatalogRecord] {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(handle, sql, -1, &statement, nil) == SQLITE_OK else { throw failure("无法读取旧库结构") }
        defer { sqlite3_finalize(statement) }
        var rows: [CatalogRecord] = []
        while true {
            let code = sqlite3_step(statement)
            if code == SQLITE_DONE { return rows }
            guard code == SQLITE_ROW else { throw failure("读取照片库失败") }
            if rows.count % 100 == 0 { try Task.checkCancellation() }
            var values: [String: CatalogValue] = [:]
            for column in 0..<sqlite3_column_count(statement) {
                let name = String(cString: sqlite3_column_name(statement, column))
                switch sqlite3_column_type(statement, column) {
                case SQLITE_INTEGER: values[name] = .integer(sqlite3_column_int64(statement, column))
                case SQLITE_FLOAT: values[name] = .real(sqlite3_column_double(statement, column))
                case SQLITE_TEXT:
                    let count = Int(sqlite3_column_bytes(statement, column))
                    let bytes = UnsafeBufferPointer(start: sqlite3_column_text(statement, column), count: count)
                    guard let string = String(bytes: bytes, encoding: .utf8) else { throw CatalogReadError("旧库文本不是有效的 UTF-8") }
                    values[name] = .text(string)
                case SQLITE_BLOB:
                    let count = Int(sqlite3_column_bytes(statement, column))
                    values[name] = .blob(sqlite3_column_blob(statement, column).map { Data(bytes: $0, count: count) } ?? Data())
                default: values[name] = .null
                }
            }
            rows.append(.init(ordinal: rows.count, values: values))
        }
    }
}
