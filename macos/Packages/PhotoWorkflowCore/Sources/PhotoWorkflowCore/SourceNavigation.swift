public enum SourceLocation: Hashable, Sendable {
    case all
    case folder(String)
    public var label: String {
        switch self { case .all: "全部子文件夹"; case .folder(let path): SourcePath.components(path).last ?? "来源根目录" }
    }
    public var parent: SourceLocation? {
        switch self {
        case .all: .folder("")
        case .folder(""): nil
        case .folder(let path): .folder(SourcePath.components(path).dropLast().joined(separator: "/"))
        }
    }
    public var breadcrumbs: [SourceLocation] {
        switch self {
        case .all: return [.folder(""), .all]
        case .folder(let path):
            let parts = SourcePath.components(path)
            return [.folder("")] + parts.indices.map { i in .folder(parts[...i].joined(separator: "/")) }
        }
    }
}
public struct SourceRoute: Hashable, Sendable {
    public var location: SourceLocation
    public var date: String
    public var format: String
    public init(location: SourceLocation = .all, date: String = "all", format: String = "all") {
        self.location = location; self.date = date; self.format = format
    }
}
public struct SourceNavigation: Sendable {
    public private(set) var route = SourceRoute()
    public private(set) var scrollOffset: Double = 0
    private struct Entry: Sendable { let route: SourceRoute; let offset: Double }
    private var past: [Entry] = []
    private var future: [Entry] = []
    public var canGoBack: Bool { !past.isEmpty }
    public var canGoForward: Bool { !future.isEmpty }
    public init() {}
    public mutating func rememberScrollOffset(_ offset: Double, for route: SourceRoute) {
        // A disappearing grid may deliver one final update after navigation.
        guard route == self.route, offset.isFinite, offset >= 0 else { return }
        scrollOffset = offset
    }
    public mutating func navigate(_ route: SourceRoute) {
        guard route != self.route else { return }
        past.append(Entry(route: self.route, offset: scrollOffset))
        if past.count > 80 { past.removeFirst() }
        future.removeAll(); self.route = route; scrollOffset = 0
    }
    public mutating func back() {
        guard let previous = past.popLast() else { return }
        future.append(Entry(route: route, offset: scrollOffset)); route = previous.route; scrollOffset = previous.offset
    }
    public mutating func forward() {
        guard let next = future.popLast() else { return }
        past.append(Entry(route: route, offset: scrollOffset)); route = next.route; scrollOffset = next.offset
    }
    public mutating func reset() { self = SourceNavigation() }
}
