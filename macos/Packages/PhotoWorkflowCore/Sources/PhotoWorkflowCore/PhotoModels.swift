import Foundation
public struct Identifier<Tag>: Hashable, Codable, Sendable, ExpressibleByStringLiteral, RawRepresentable {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }
    public init(stringLiteral value: String) { rawValue = value }
}
public enum PhotoTag: Sendable {}
public typealias PhotoID = Identifier<PhotoTag>
public enum AssetKind: String, Codable, Sendable { case jpeg, raw, xmp, export }
public struct FileAsset: Hashable, Sendable {
    public let url: URL
    public let kind: AssetKind
    public init(url: URL, kind: AssetKind) { self.url = url; self.kind = kind }
}
public struct PhotoGroup: Identifiable, Hashable, Sendable {
    public let id: PhotoID
    public var stem: String
    public var files: [FileAsset]
    public var capturedAt: String?
    public var warning: String?
    public var edited = false
    public var primaryExportID: String?
    public var dateKey: String { capturedAt.map { String($0.prefix(10)) } ?? "unknown" }
    public init(id: PhotoID, stem: String, files: [FileAsset], capturedAt: String? = nil) {
        self.id = id; self.stem = stem; self.files = files; self.capturedAt = capturedAt
    }
}
public enum ReadFormat: String, CaseIterable, Sendable { case both, jpeg, raw
    public func includes(_ kind: AssetKind) -> Bool { self == .both || (self == .jpeg ? kind == .jpeg : kind == .raw || kind == .xmp) }
}
public enum StageFilter: Sendable { case all, pending, edited, exports
    public func includes(_ p: PhotoGroup) -> Bool {
        switch self { case .all: true; case .pending: !p.edited; case .edited: p.edited; case .exports: p.primaryExportID != nil }
    }
}
