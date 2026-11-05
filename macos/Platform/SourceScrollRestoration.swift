import AppKit
import SwiftUI

struct SourceScrollRestoration: NSViewRepresentable {
    let offset: Double
    let onOffset: (Double) -> Void
    func makeNSView(context: Context) -> SourceScrollProbe { SourceScrollProbe() }
    func updateNSView(_ view: SourceScrollProbe, context: Context) {
        view.initialOffset = offset
        view.onOffset = { value in DispatchQueue.main.async { onOffset(value) } }
        view.needsLayout = true
    }
    static func dismantleNSView(_ view: SourceScrollProbe, coordinator: ()) { view.detach() }
}

/// SwiftUI owns history. This non-interactive view only restores/observes the clip.
@MainActor final class SourceScrollProbe: NSView {
    var initialOffset: Double = 0
    var onOffset: ((Double) -> Void)?
    private weak var clip: NSClipView?
    private var restored = false
    private var scheduled = false
    override var isFlipped: Bool { true }
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
    override func viewDidMoveToSuperview() { super.viewDidMoveToSuperview(); detach(); needsLayout = true }
    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        if window == nil { detach() }
        else { needsLayout = true }
    }
    override func layout() {
        super.layout()
        guard !restored, !scheduled else { return }
        scheduled = true
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.scheduled = false; self.restoreIfReady()
        }
    }
    func restoreIfReady() {
        guard let scroll = enclosingScrollView, let document = scroll.documentView else { return }
        let current = scroll.contentView
        if clip !== current {
            detach(); clip = current; current.postsBoundsChangedNotifications = true
            NotificationCenter.default.addObserver(self, selector: #selector(boundsChanged), name: NSView.boundsDidChangeNotification, object: current)
        }
        guard !restored, bounds.height > 0, current.bounds.height > 0,
              document.bounds.height + 1 >= bounds.height else { return }
        restored = true
        var target = current.bounds
        target.origin.y = CGFloat(initialOffset)
        current.scroll(to: current.constrainBoundsRect(target).origin)
        scroll.reflectScrolledClipView(current)
        recordOffset()
    }
    @objc private func boundsChanged(_ notification: Notification) { recordOffset() }
    func recordOffset() {
        guard restored, let clip else { return }
        onOffset?(Double(max(0, clip.bounds.minY)))
    }
    func detach() {
        NotificationCenter.default.removeObserver(self, name: NSView.boundsDidChangeNotification, object: clip)
        clip = nil
        restored = false
    }
}
