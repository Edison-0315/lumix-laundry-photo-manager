import SwiftUI
import PhotoWorkflowCore
struct PhotoViewer: View {
    let session: PreviewSession
    let selected: Set<PhotoID>
    let togglePhoto: (PhotoID) -> Void
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var index: Int
    init(session: PreviewSession, selected: Set<PhotoID>, togglePhoto: @escaping (PhotoID) -> Void) {
        self.session = session; self.selected = selected; self.togglePhoto = togglePhoto
        _index = State(initialValue: session.photos.firstIndex { $0.id == session.current } ?? 0)
    }
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Button { move(-1) } label: { Image(systemName: "chevron.left") }
                    .disabled(index == 0).accessibilityLabel("上一张").accessibilityIdentifier("viewerPrevious")
                Button { move(1) } label: { Image(systemName: "chevron.right") }
                    .disabled(index + 1 >= session.photos.count).accessibilityLabel("下一张").accessibilityIdentifier("viewerNext")
                Text("\(index + 1) / \(session.photos.count)").monospacedDigit()
                Spacer()
                if session.photos.indices.contains(index) {
                    let selected = selected.contains(session.photos[index].id)
                    Button(action: toggleSelection) {
                        Label(selected ? "已选中" : "选中照片", systemImage: selected ? "checkmark.circle.fill" : "circle")
                            .contentTransition(reduceMotion ? .identity : .symbolEffect(.replace))
                    }
                    .tint(selected ? .accentColor : nil)
                    .animation(reduceMotion ? nil : .smooth(duration: 0.18), value: selected)
                }
                Button("关闭") { dismiss() }.keyboardShortcut(.cancelAction)
            }
            if session.photos.indices.contains(index) {
                ViewerImage(photo: session.photos[index], previous: { move(-1) }, next: { move(1) },
                            toggleSelection: toggleSelection, close: { dismiss() })
                    .id(session.photos[index].id)
            }
        }.padding(16).frame(minWidth: 800, idealWidth: 1000, minHeight: 550, idealHeight: 700)
    }
    private func move(_ delta: Int) {
        let target = index + delta
        if session.photos.indices.contains(target) { index = target }
    }
    private func toggleSelection() {
        guard session.photos.indices.contains(index) else { return }
        togglePhoto(session.photos[index].id)
    }
}
