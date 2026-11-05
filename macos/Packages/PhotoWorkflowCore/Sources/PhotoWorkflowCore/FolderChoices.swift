/// Main-grid folder choices are scoped by location and independent of photo picks.
public struct FolderChoices: Sendable {
    private var groups: [SourceLocation: Set<String>] = [:]
    private var held: [SourceLocation: Set<String>] = [:]
    private var beforeClick: (key: String, scope: SourceLocation, selected: Set<String>)?
    public init() {}
    public var allSelected: Set<String> { groups.values.reduce(into: Set<String>()) { $0.formUnion($1) } }
    public func selected(in scope: SourceLocation) -> Set<String> { groups[scope] ?? [] }
    public func filtered(in scope: SourceLocation) -> Set<String> { held[scope] ?? selected(in: scope) }
    public mutating func click(_ key: String, scope: SourceLocation, deferFiltering: Bool = false) {
        let old = selected(in: scope)
        beforeClick = (key, scope, old)
        if deferFiltering, held[scope] == nil { held[scope] = old }
        if old.contains(key) { groups[scope, default: []].remove(key) }
        else { groups[scope, default: []].insert(key) }
    }
    public mutating func doubleClick(_ key: String, scope: SourceLocation) {
        if let beforeClick, beforeClick.key == key, beforeClick.scope == scope { groups[scope] = beforeClick.selected }
        beforeClick = nil; held[scope] = nil
    }
    public mutating func finishFiltering() { held.removeAll(); beforeClick = nil }
    public mutating func selectVisible(_ keys: [String], scope: SourceLocation) {
        groups[scope, default: []].formUnion(keys); finishFiltering()
    }
    public mutating func deselectVisible(_ keys: [String], scope: SourceLocation) {
        groups[scope, default: []].subtract(keys); finishFiltering()
    }
    public mutating func reset() { self = FolderChoices() }
    public mutating func marquee(_ hits: Set<String>, starting: Self, scope: SourceLocation, additive: Bool, deferFiltering: Bool) {
        self = starting
        groups[scope] = additive ? starting.selected(in: scope).union(hits) : hits
        beforeClick = nil
        if deferFiltering { held[scope] = starting.filtered(in: scope) }
        else { held[scope] = nil }
    }
}
