public struct SelectionState: Sendable {
    public var selected: Set<PhotoID> = []
    public var current: PhotoID?
    public var anchor: PhotoID?
    private var beforeClick: (PhotoID, Set<PhotoID>)?
    private var heldFilterSelection: Set<PhotoID>?
    public init() {}
    public var filteredSelection: Set<PhotoID> { heldFilterSelection ?? selected }
    public mutating func finishFiltering() { heldFilterSelection = nil }
    public mutating func click(_ id: PhotoID, visible: [PhotoID], shift: Bool = false, additive: Bool = false, deferFiltering: Bool = false) {
        if deferFiltering { heldFilterSelection = heldFilterSelection ?? selected }
        beforeClick = (id, selected)
        if shift, let anchor, let a = visible.firstIndex(of: anchor), let b = visible.firstIndex(of: id) {
            if !additive { selected.removeAll() }
            selected.formUnion(visible[min(a,b)...max(a,b)])
        } else {
            if selected.contains(id) { selected.remove(id) } else { selected.insert(id) }
            anchor = id
        }
        current = id
    }
    public mutating func doubleClick(_ id: PhotoID) {
        if let beforeClick, beforeClick.0 == id { selected = beforeClick.1 }
        beforeClick = nil; current = id; heldFilterSelection = nil
    }
    public mutating func contextClick(_ id: PhotoID) {
        if !selected.contains(id) { selected = [id] }
        current = id; anchor = id; beforeClick = nil
    }
    public mutating func selectVisible(_ ids: [PhotoID]) { selected.formUnion(ids) }
    public mutating func deselectVisible(_ ids: [PhotoID]) { selected.subtract(ids) }
    public mutating func marquee(_ hits: Set<PhotoID>, starting: Self, visible: [PhotoID], additive: Bool, deferFiltering: Bool) {
        self = starting
        selected = additive ? starting.selected.union(hits) : hits
        if current.map({ selected.contains($0) }) != true { current = visible.first { selected.contains($0) } }
        anchor = current; beforeClick = nil
        heldFilterSelection = deferFiltering ? starting.filteredSelection : nil
    }
}
