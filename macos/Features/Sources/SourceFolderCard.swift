import SwiftUI
import AppKit
import PhotoWorkflowCore
struct SourceFolderCard: View {
    let path: String
    let model: AppModel
    private var selected: Bool { model.folderChoices.selected(in: model.location).contains(path) }
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ZStack {
                Rectangle().fill(.secondary.opacity(0.07))
                if model.examples(in: path).isEmpty {
                    Image(systemName: "folder.fill").font(.system(size: 48)).foregroundStyle(.secondary)
                } else {
                    HStack(spacing: 3) {
                        ForEach(model.examples(in: path)) { photo in PhotoImage(photo: photo, maxPixel: 640) }
                    }.padding(10)
                    Image(systemName: "folder.fill").font(.title2).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading).padding(6)
                }
            }.aspectRatio(4 / 3, contentMode: .fit).clipped()
            Text(SourceLocation.folder(path).label).font(.caption).lineLimit(1)
            Text("双击或按 Return 进入").font(.caption2).foregroundStyle(.secondary)
        }
        .padding(7)
        .background(selected ? Color.accentColor.opacity(0.2) : Color.secondary.opacity(0.07), in: .rect(cornerRadius: 8))
        .modifier(PhotoSelectionOutline(selected: selected))
        .overlay { FolderClickSurface(click: { model.clickFolder(path) }, doubleClick: { model.doubleClickFolder(path) }, open: { model.openLocation(.folder(path)) }) }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(path + (selected ? "，已选择" : ""))
        .accessibilityIdentifier("folderCard:\(path)")
        .accessibilityAction { model.clickFolder(path) }
        .accessibilityAction(named: Text("打开文件夹")) { model.openLocation(.folder(path)) }
    }
}
private struct FolderClickSurface: NSViewRepresentable {
    let click: () -> Void
    let doubleClick: () -> Void
    let open: () -> Void
    func makeNSView(context: Context) -> ClickView { let view = ClickView(); view.focusRingType = .exterior; return view }
    func updateNSView(_ view: ClickView, context: Context) { view.click = click; view.doubleClick = doubleClick; view.open = open }
    final class ClickView: NSView {
        var click: (() -> Void)?
        var doubleClick: (() -> Void)?
        var open: (() -> Void)?
        override var acceptsFirstResponder: Bool { true }
        override var focusRingMaskBounds: NSRect { bounds }
        override func drawFocusRingMask() { NSBezierPath(roundedRect: bounds, xRadius: 8, yRadius: 8).fill() }
        override func setFrameSize(_ newSize: NSSize) { super.setFrameSize(newSize); noteFocusRingMaskChanged() }
        override func mouseDown(with event: NSEvent) {
            window?.makeFirstResponder(self)
            if event.clickCount == 1 { click?() }
            else if event.clickCount == 2 { doubleClick?() }
        }
        override func keyDown(with event: NSEvent) {
            guard event.modifierFlags.intersection([.command, .control, .option]).isEmpty else { super.keyDown(with: event); return }
            if event.keyCode == 36 || event.keyCode == 76 { open?() }
            else if event.keyCode == 49 { if !event.isARepeat { click?() } }
            else { super.keyDown(with: event) }
        }
    }
}
