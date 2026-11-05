import Foundation

public enum CatalogValue: Sendable, Equatable {
    case null, integer(Int64), real(Double), text(String), blob(Data)
    public var string: String? { if case .text(let value) = self { return value }; return nil }
    public var int: Int64? { if case .integer(let value) = self { return value }; return nil }
}
public struct CatalogRecord: Identifiable, Sendable {
    public let ordinal: Int
    public let values: [String: CatalogValue]
    public var id: String { text("id") ?? text("photo_id") ?? text("activity_id") ?? String(ordinal) }
    public func text(_ column: String) -> String? { values[column]?.string }
    public func integer(_ column: String) -> Int64? { values[column]?.int }
}
public struct CatalogIssue: Identifiable, Sendable {
    public let id: String
    public let message: String
}
public struct CatalogAsset: Identifiable, Sendable {
    public let id: String
    public let path: String
    public let url: URL?
    public let kind: AssetKind?
    public let problem: String?
}
public struct CatalogPhoto: Identifiable, Sendable {
    public var id: PhotoID { photo.id }
    public var photo: PhotoGroup
    public let activityID: String
    public let personID: String
    public let assets: [CatalogAsset]
    public let trashed: Bool
    public let purging: Bool
}
public struct LegacyCatalog: Sendable {
    public let root: URL
    public let tables: [String: [CatalogRecord]]
    public let photos: [CatalogPhoto]
    public let issues: [CatalogIssue]
    public func rows(_ table: String) -> [CatalogRecord] { tables[table] ?? [] }
    public static func read(root: URL, oldRoot: String? = nil) throws -> Self {
        let db = try CatalogDatabase(root: root)
        let schema: [(String, String)] = [
            ("activities", "id name folder"), ("people", "id activity_id name folder role embedding"),
            ("photos", "id activity_id person_id stem captured_at edited manual_person opened_at primary_export_id signature"),
            ("assets", "id photo_id kind path sha256"), ("operations", "id kind phase payload error"),
            ("detached_exports", "id photo_id path sha256"), ("import_members", "activity_id kind sha256 photo_id"),
            ("trashed_photos", "photo_id payload deleted_at"), ("purges", "photo_id payload error"), ("deleted_activities", "activity_id")
        ]
        let actualTables = Set(try db.query("SELECT name FROM sqlite_schema WHERE type='table'").compactMap { $0.text("name") })
        var tables: [String: [CatalogRecord]] = [:]
        for (name, columns) in schema {
            guard actualTables.contains(name) else { throw CatalogReadError("旧库缺少数据表：" + name) }
            let actualColumns = Set(try db.query("PRAGMA table_info(\"\(name)\")").compactMap { $0.text("name") })
            guard columns.split(separator: " ").allSatisfy({ actualColumns.contains(String($0)) }) else { throw CatalogReadError("旧库数据表结构不兼容：" + name) }
            tables[name] = try db.query("SELECT * FROM \"\(name)\" ORDER BY rowid")
        }
        var issues: [CatalogIssue] = []
        func issue(_ id: String, _ message: String) { issues.append(.init(id: id, message: message)) }
        let resolver = CatalogPathResolver(root: root, oldRoot: oldRoot)
        let trashed = Set((tables["trashed_photos"] ?? []).compactMap { $0.text("photo_id") })
        var assetsByPhoto: [String: [CatalogAsset]] = [:]
        for row in tables["assets"] ?? [] {
            let key = "asset:\(row.ordinal)"
            let path = row.text("path") ?? ""
            let photoID = row.text("photo_id") ?? ""
            let resolved = resolver.resolve(path, trashPhotoID: trashed.contains(photoID) ? photoID : nil, trashAssetID: row.id)
            let kind = row.text("kind").flatMap(AssetKind.init(rawValue:))
            let problem = resolved.problem ?? (kind == nil ? "未知文件类型" : nil)
            if let problem { issue(key, path + "：" + problem) }
            assetsByPhoto[row.text("photo_id") ?? "", default: []].append(.init(id: row.id, path: path, url: kind == nil ? nil : resolved.url, kind: kind, problem: problem))
        }
        for row in tables["detached_exports"] ?? [] {
            if let problem = resolver.resolve(row.text("path") ?? "").problem { issue("detached:\(row.ordinal)", "已解除关联的成片：" + problem) }
        }
        for table in ["operations", "trashed_photos", "purges"] {
            for row in tables[table] ?? [] {
                let payload = row.text("payload") ?? ""
                let json = payload.data(using: .utf8).flatMap { try? JSONSerialization.jsonObject(with: $0) }
                let recognized = table == "trashed_photos" ? json is [[String: Any]] : json is [String: Any]
                if !recognized { issue("json:\(table):\(row.ordinal)", "\(table) 中的 JSON 无法识别；保留原文，不执行恢复") }
                if table == "operations", row.text("phase") != "committed" { issue("operation:\(row.ordinal)", "存在未完成操作 \(row.id)；保持只读，不自动恢复") }
                if table == "purges" { issue("purge:\(row.ordinal)", "照片 \(row.id) 存在未完成永久删除；只展示记录，禁止恢复或删除") }
            }
        }
        let purging = Set((tables["purges"] ?? []).compactMap { $0.text("photo_id") })
        let activityIDs = Set((tables["activities"] ?? []).compactMap { $0.text("id") })
        let personActivity = Dictionary((tables["people"] ?? []).compactMap { row -> (String, String)? in
            guard let id = row.text("id"), let activity = row.text("activity_id") else { return nil }; return (id, activity)
        }, uniquingKeysWith: { first, _ in first })
        var photos: [CatalogPhoto] = []
        for row in tables["photos"] ?? [] {
            guard let id = row.text("id"), let activity = row.text("activity_id"), let person = row.text("person_id") else { throw CatalogReadError("照片记录缺少有效 ID 或归属") }
            if !activityIDs.contains(activity) || personActivity[person] != activity { issue("photo-owner:\(row.ordinal)", "照片 \(id) 的活动或人物关系不完整，保留记录") }
            let assets = assetsByPhoto[id] ?? []
            var photo = PhotoGroup(id: PhotoID(rawValue: id), stem: row.text("stem") ?? id,
                                   files: assets.compactMap { item in guard let url = item.url, let kind = item.kind else { return nil }; return FileAsset(url: url, kind: kind) }, capturedAt: row.text("captured_at"))
            photo.edited = row.integer("edited") != nil && row.integer("edited") != 0
            photo.primaryExportID = row.text("primary_export_id")
            if assets.isEmpty || assets.contains(where: { $0.problem != nil }) { photo.warning = "部分文件缺失、尚未映射或不可安全读取。" }
            photos.append(.init(photo: photo, activityID: activity, personID: person, assets: assets, trashed: trashed.contains(id), purging: purging.contains(id)))
        }
        photos.sort { ($0.photo.capturedAt ?? "") < ($1.photo.capturedAt ?? "") }
        return .init(root: root, tables: tables, photos: photos, issues: issues)
    }
}
