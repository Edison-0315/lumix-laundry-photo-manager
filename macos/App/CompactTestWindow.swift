#if DEBUG
import SwiftUI
import AppKit

/// Deterministic geometry for the compact-window UI test; absent from Release.
struct CompactTestWindow: NSViewRepresentable {
    func makeNSView(context: Context) -> Probe { Probe() }
    func updateNSView(_ view: Probe, context: Context) {}
    final class Probe: NSView {
        private var configured = false
        override func hitTest(_ point: NSPoint) -> NSView? { nil }
        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            guard let window else { return }
            NotificationCenter.default.addObserver(self, selector: #selector(configureWindow),
                name: NSWindow.didBecomeKeyNotification, object: window)
            if window.isKeyWindow { configureWindow() }
        }
        @objc private func configureWindow() {
            guard !configured, let window else { return }
            configured = true
            guard window.styleMask.contains(.resizable), window.minSize.width <= 1000,
                  window.minSize.height <= 800 else { return }
            var frame = window.frame; frame.size = NSSize(width: 1000, height: 800)
            window.setFrame(frame, display: true)
        }
    }
}
#endif
