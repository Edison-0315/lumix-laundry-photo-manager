import SwiftUI
import AppKit
import PhotoWorkflowCore

enum GridSelectionItem: Hashable {
    case photo(PhotoID)
    case folder(String)
}
struct GridCardFrames: PreferenceKey {
    static let defaultValue: [GridSelectionItem: CGRect] = [:]
    static func reduce(value: inout [GridSelectionItem: CGRect], nextValue: () -> [GridSelectionItem: CGRect]) {
        value.merge(nextValue(), uniquingKeysWith: { _, new in new })
    }
}
extension View {
    func selectionFrame(_ item: GridSelectionItem) -> some View {
        background {
            GeometryReader { geometry in
                Color.clear.preference(key: GridCardFrames.self, value: [item: geometry.frame(in: .named("selectionGrid"))])
            }
        }
    }
}

@MainActor protocol MarqueeSelecting: AnyObject {
    var canMarquee: Bool { get }
    func beginMarquee()
    func updateMarquee(photos: Set<PhotoID>, folders: Set<String>, additive: Bool)
    func endMarquee(cancelled: Bool)
}
extension AppModel: MarqueeSelecting { var canMarquee: Bool { canNavigate } }

struct MarqueeSelection: ViewModifier {
    let frames: [GridSelectionItem: CGRect]
    let model: any MarqueeSelecting
    @State private var box: CGRect?
    @State private var active = false
    @State private var rejected = false
    @State private var additive = false
    @State private var origin: CGPoint?
    @State private var trackedFrames: [GridSelectionItem: CGRect] = [:]
    @State private var scroller = MarqueeAutoscroll()
    @FocusState private var focused: Bool

    func body(content: Content) -> some View {
        content
            .contentShape(Rectangle())
            .simultaneousGesture(DragGesture(minimumDistance: 6, coordinateSpace: .named("selectionGrid"))
                .onChanged { value in
                    guard !rejected, model.canMarquee else { return }
                    if !active {
                        guard !frames.values.contains(where: { $0.contains(value.startLocation) }) else { rejected = true; return }
                        additive = !NSEvent.modifierFlags.intersection([.command, .shift, .control]).isEmpty
                        focused = true; model.beginMarquee(); active = true
                        origin = value.startLocation; trackedFrames = frames
                    }
                    updateBox(ending: value.location)
                }
                .onEnded { _ in finish(cancelled: false) })
            .simultaneousGesture(SpatialTapGesture(coordinateSpace: .named("selectionGrid")).onEnded { value in
                guard model.canMarquee, !active, !frames.values.contains(where: { $0.contains(value.location) }),
                      NSEvent.modifierFlags.intersection([.command, .shift, .control]).isEmpty else { return }
                model.beginMarquee(); model.updateMarquee(photos: [], folders: [], additive: false); model.endMarquee(cancelled: false)
            })
            .overlay(alignment: .topLeading) {
                if let box {
                    Rectangle().fill(Color.accentColor.opacity(0.15))
                        .overlay { Rectangle().strokeBorder(Color.accentColor, lineWidth: 1) }
                        .frame(width: box.width, height: box.height)
                        .offset(x: box.minX, y: box.minY)
                        .allowsHitTesting(false).accessibilityHidden(true)
                }
            }
            .focusable().focusEffectDisabled().focused($focused)
            .background { MarqueeScrollProbe(driver: scroller) }
            .onChange(of: frames) { _, current in
                guard active else { return }
                // Lazy grids discard offscreen preferences; retain geometry for this drag
                // so scrolling does not lose earlier hits and shrinking still retracts them.
                trackedFrames.merge(current, uniquingKeysWith: { _, new in new })
                if let box { updateSelection(in: box) }
            }
            .task(id: active) {
                guard active else { return }
                while !Task.isCancelled {
                    do { try await Task.sleep(for: .milliseconds(33)) } catch { return }
                    guard active else { return }
                    // Mouse-up may be observed before SwiftUI delivers onEnded.
                    // Commit the drag rather than treating a normal release as Escape.
                    guard NSEvent.pressedMouseButtons & 1 != 0 else { finish(cancelled: false); return }
                    guard let point = scroller.pointerInContent() else { finish(cancelled: true); return }
                    if scroller.scroll(at: point), let moved = scroller.pointerInContent() {
                        updateBox(ending: moved)
                    }
                }
            }
            .onExitCommand { finish(cancelled: true); rejected = true }
            .onDisappear { finish(cancelled: true) }
            .onChange(of: model.canMarquee) { _, enabled in if !enabled { finish(cancelled: true) } }
    }
    private func updateBox(ending end: CGPoint) {
        guard let start = origin else { return }
        let rect = CGRect(x: min(start.x, end.x), y: min(start.y, end.y), width: abs(end.x - start.x), height: abs(end.y - start.y))
        box = rect; updateSelection(in: rect)
    }
    private func updateSelection(in rect: CGRect) {
        let hits = trackedFrames.filter { $0.value.intersects(rect) }.map(\.key)
        let photos = Set(hits.compactMap { if case .photo(let id) = $0 { return id }; return nil })
        let folders = Set(hits.compactMap { if case .folder(let path) = $0 { return path }; return nil })
        model.updateMarquee(photos: photos, folders: folders, additive: additive)
    }
    private func finish(cancelled: Bool) {
        if active { model.endMarquee(cancelled: cancelled) }
        box = nil; active = false; rejected = false; origin = nil; trackedFrames = [:]
    }
}

private struct MarqueeScrollProbe: NSViewRepresentable {
    let driver: MarqueeAutoscroll
    func makeNSView(context: Context) -> ProbeView {
        let view = ProbeView(); driver.view = view; return view
    }
    func updateNSView(_ view: ProbeView, context: Context) { driver.view = view }
    final class ProbeView: NSView {
        override var isFlipped: Bool { true }
        override func hitTest(_ point: NSPoint) -> NSView? { nil }
    }
}
