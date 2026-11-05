/// U+002F is a filesystem separator even when the next scalar is a combining
/// mark. Swift Character boundaries must not be used to parse path components.
enum SourcePath {
    static func components(_ path: String) -> [String] {
        path.utf8.split(separator: 0x2F).map { String(decoding: $0, as: UTF8.self) }
    }
}
