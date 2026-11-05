import SwiftUI
import AppKit
import PhotoWorkflowCore
struct PhotoGrid: View {
    let model: AppModel
    let size: Double
    private let route: SourceRoute
    private let sourceVersion: UUID
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var cardFrames: [GridSelectionItem: CGRect] = [:]
    init(model: AppModel, size: Double) {
        self.model = model; self.size = size; self.route = model.navigation.route; self.sourceVersion = model.sourceVersion
    }
    var body: some View {
        GeometryReader { viewport in
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: size, maximum: size), spacing: 14)], spacing: 14) {
                ForEach(model.visibleFolders, id: \.self) { path in
                    SourceFolderCard(path: path, model: model)
                        .selectionFrame(.folder(path))
                }
                ForEach(model.visible) { photo in
                    VStack(alignment: .leading, spacing: 6) {
                        PhotoImage(photo: photo, maxPixel: 640).aspectRatio(4/3, contentMode: .fit)
                        Text(photo.stem).lineLimit(1).font(.caption)
                        HStack { Text(photo.dateKey == "unknown" ? "日期未知" : photo.dateKey); Spacer(); Text(photo.files.contains { $0.kind == .raw } ? "RAW" : "JPEG") }.font(.caption2).foregroundStyle(.secondary)
                    }
                    .padding(7)
                    .background(model.selection.selected.contains(photo.id) ? Color.accentColor.opacity(0.2) : Color.secondary.opacity(0.07), in: .rect(cornerRadius: 8))
                    .modifier(PhotoSelectionOutline(selected: model.selection.selected.contains(photo.id)))
                    .animation(reduceMotion || model.isMarqueeSelecting ? nil : .smooth(duration: 0.16), value: model.selection.selected.contains(photo.id))
                    .overlay { PhotoClickSurface(click: { shift, additive in model.click(photo.id, shift: shift, additive: additive) }, doubleClick: { model.doubleClick(photo.id) }, context: { model.selection.contextClick(photo.id) }, open: { model.openPreview(photo.id) }) }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel(photo.stem + (model.selection.selected.contains(photo.id) ? "，已选中" : ""))
                    .accessibilityAction { model.click(photo.id, shift: false, additive: false) }
                    .accessibilityAction(named: Text("预览照片")) { model.openPreview(photo.id) }
                    .help(photo.warning ?? photo.stem)
                    .selectionFrame(.photo(photo.id))
                }
            }.padding(16)
            .frame(maxWidth: .infinity, minHeight: viewport.size.height, alignment: .topLeading)
            .modifier(MarqueeSelection(frames: cardFrames, model: model))
            .background {
                SourceScrollRestoration(offset: model.navigation.scrollOffset) { offset in
                    guard sourceVersion == model.sourceVersion, route == model.navigation.route,
                          offset != model.navigation.scrollOffset else { return }
                    model.navigation.rememberScrollOffset(offset, for: route)
                }
            }
            .coordinateSpace(name: "selectionGrid")
            .onPreferenceChange(GridCardFrames.self) { cardFrames = $0 }
        }
        .accessibilityIdentifier("sourceGrid")
        }
    }
}
/// SwiftUI owns selection; this bridge supplies AppKit click counts and modifier keys.
struct PhotoClickSurface: NSViewRepresentable {
    let click: (Bool, Bool) -> Void
    let doubleClick: () -> Void
    let context: () -> Void
    let open: () -> Void
    func makeNSView(context: Context) -> ClickView { let view = ClickView(); view.focusRingType = .exterior; return view }
    func updateNSView(_ view: ClickView, context: Context) { view.click = click; view.doubleClick = doubleClick; view.prepareContext = self.context; view.open = open }
    final class ClickView: NSView {
        var click: ((Bool, Bool) -> Void)?
        var doubleClick: (() -> Void)?
        var prepareContext: (() -> Void)?
        var open: (() -> Void)?
        override var acceptsFirstResponder: Bool { true }
        override var focusRingMaskBounds: NSRect { bounds }
        override func drawFocusRingMask() { NSBezierPath(roundedRect: bounds, xRadius: 8, yRadius: 8).fill() }
        override func setFrameSize(_ newSize: NSSize) { super.setFrameSize(newSize); noteFocusRingMaskChanged() }
        override func mouseDown(with event: NSEvent) {
            window?.makeFirstResponder(self)
            if event.clickCount == 1 { click?(event.modifierFlags.contains(.shift), !event.modifierFlags.intersection([.command, .control]).isEmpty) }
            else if event.clickCount == 2 { doubleClick?() }
        }
        override func keyDown(with event: NSEvent) {
            guard event.modifierFlags.intersection([.command, .control, .option]).isEmpty else { super.keyDown(with: event); return }
            switch event.keyCode {
            case 36, 76: open?()
            case 49: if !event.isARepeat { click?(false, false) }
            default: super.keyDown(with: event)
            }
        }
        override func menu(for event: NSEvent) -> NSMenu? {
            window?.makeFirstResponder(self)
            prepareContext?()
            let menu = NSMenu()
            let item = NSMenuItem(title: "查看大图", action: #selector(openPhoto), keyEquivalent: "")
            item.target = self; menu.addItem(item); return menu
        }
        @objc private func openPhoto() { open?() }
    }
}
