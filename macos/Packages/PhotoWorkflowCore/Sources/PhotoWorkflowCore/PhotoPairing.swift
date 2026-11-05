import Foundation
import CryptoKit
public enum PhotoPairing {
    static func key(_ value: String) -> String { value.folding(options: [.caseInsensitive], locale: Locale(identifier: "en_US_POSIX")) }
    public static func groups(files: [FileAsset]) -> [PhotoGroup] {
        var groups: [String: PhotoGroup] = [:]
        var order: [String] = []
        for file in files.sorted(by: { $0.url.path < $1.url.path }) {
            var stem = file.url.deletingPathExtension().lastPathComponent
            if file.kind == .xmp, SourceExtensions.kind(stem) != nil {
                stem = URL(fileURLWithPath: stem).deletingPathExtension().lastPathComponent
            }
            let k = file.url.deletingLastPathComponent().standardizedFileURL.path + "\0" + key(stem)
            if groups[k] == nil {
                let id = SHA256.hash(data: Data(k.utf8)).map { String(format: "%02x", $0) }.joined()
                groups[k] = PhotoGroup(id: PhotoID(rawValue: String(id.prefix(32))), stem: stem, files: [])
                order.append(k)
            }
            groups[k]?.files.append(file)
        }
        var siblings: [String: [String]] = [:]
        for k in order {
            guard let g = groups[k], let first = g.files.first else { continue }
            let dir = first.url.deletingLastPathComponent()
            let name = key(dir.lastPathComponent)
            let expected: AssetKind? = ["jpeg", "jpg"].contains(name) ? .jpeg : ["raw", "rw2"].contains(name) ? .raw : nil
            let actual = Set(g.files.filter { $0.kind != .xmp }.map(\.kind))
            if let expected, actual == [expected] {
                siblings[dir.deletingLastPathComponent().standardizedFileURL.path + "\0" + key(g.stem), default: []].append(k)
            }
        }
        for candidates in siblings.values where candidates.count == 2 {
            guard let a = groups[candidates[0]], let b = groups[candidates[1]],
                  a.files.filter({ $0.kind != .xmp }).count == 1,
                  b.files.filter({ $0.kind != .xmp }).count == 1,
                  Set((a.files + b.files).filter { $0.kind != .xmp }.map(\.kind)) == [.jpeg, .raw] else { continue }
            groups[candidates[0]]?.files += b.files
            groups.removeValue(forKey: candidates[1])
        }
        return order.compactMap { groups[$0] }.filter { $0.files.contains { $0.kind == .jpeg || $0.kind == .raw } }
    }
}
public enum SourceExtensions {
    public static func kind(_ filename: String) -> AssetKind? {
        switch URL(fileURLWithPath: filename).pathExtension.lowercased() {
        case "jpg", "jpeg": .jpeg
        case "rw2", "dng", "cr2", "cr3", "nef", "arw", "raf", "orf": .raw
        case "xmp": .xmp
        default: nil
        }
    }
}
