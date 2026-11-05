import AppKit

/// The grid owns selection; this bridge only moves its enclosing scroll view.
@MainActor final class MarqueeAutoscroll {
    weak var view: NSView?
    func pointerInContent() -> CGPoint? {
        guard let view, let window = view.window, window.isKeyWindow else { return nil }
        return view.convert(window.convertPoint(fromScreen: NSEvent.mouseLocation), from: nil)
    }
    @discardableResult func scroll(at point: CGPoint) -> Bool {
        guard let view, let scroll = view.enclosingScrollView, let document = scroll.documentView else { return false }
        let clip = scroll.contentView
        let visible = view.convert(clip.bounds, from: clip)
        guard point.x >= visible.minX - 24, point.x <= visible.maxX + 24 else { return false }
        let band = min(40.0, visible.height / 3)
        guard band > 0 else { return false }
        let amount: CGFloat
        if point.y < visible.minY + band {
            amount = -14 * min(1, (visible.minY + band - point.y) / band)
        } else if point.y > visible.maxY - band {
            amount = 14 * min(1, (point.y - visible.maxY + band) / band)
        } else { return false }
        let old = clip.bounds.origin
        var proposed = clip.bounds
        proposed.origin.y += amount * (document.isFlipped ? 1 : -1)
        let target = clip.constrainBoundsRect(proposed).origin
        guard abs(target.y - old.y) > 0.01 else { return false }
        clip.scroll(to: target); scroll.reflectScrolledClipView(clip)
        return true
    }
}
