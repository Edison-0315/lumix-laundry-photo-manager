import Foundation
/// Derived entirely from accepted scan members, without traversing the source again.
public struct SourceFolderIndex: Sendable {
    public let paths: [String]
    private let members: [PhotoID: Set<String>]
    public init(photos: [PhotoGroup], root: URL) {
        let rootParts = root.standardizedFileURL.pathComponents
        var paths: Set<String> = [""]
        var members: [PhotoID: Set<String>] = [:]
        for photo in photos {
            for file in photo.files {
                let parts = file.url.deletingLastPathComponent().standardizedFileURL.pathComponents
                guard parts.starts(with: rootParts) else { continue }
                let relative = Array(parts.dropFirst(rootParts.count))
                members[photo.id, default: []].insert(relative.joined(separator: "/"))
                for i in relative.indices { paths.insert(relative[...i].joined(separator: "/")) }
            }
        }
        self.paths = paths.sorted(); self.members = members
    }
    public func directories(for id: PhotoID) -> Set<String> { members[id] ?? [] }
    public func children(of location: SourceLocation) -> [String] {
        guard case .folder(let path) = location else { return [] }
        let parent = SourcePath.components(path)
        return paths.filter {
            let child = SourcePath.components($0)
            return child.count == parent.count + 1 && child.starts(with: parent)
        }
    }
    public func contains(_ id: PhotoID, in location: SourceLocation) -> Bool {
        let dirs = directories(for: id)
        switch location { case .all: return !dirs.isEmpty; case .folder(let path): return dirs.contains(path) }
    }
    public func descends(_ id: PhotoID, from path: String) -> Bool {
        let parent = SourcePath.components(path)
        return directories(for: id).contains { SourcePath.components($0).starts(with: parent) }
    }
}
