import SwiftUI

/// A shape cue keeps selection legible without relying on accent color alone.
struct PhotoSelectionOutline: ViewModifier {
    let selected: Bool
    @Environment(\.colorSchemeContrast) private var contrast
    func body(content: Content) -> some View {
        content
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(selected ? Color.accentColor : .clear, lineWidth: contrast == .increased ? 3 : 2)
                    .allowsHitTesting(false)
            }
            .overlay(alignment: .topTrailing) {
                if selected {
                    Image(systemName: "checkmark.circle.fill")
                        .symbolRenderingMode(.palette).foregroundStyle(.white, Color.accentColor)
                        .font(.title3).padding(8)
                        .allowsHitTesting(false).accessibilityHidden(true)
                }
            }
    }
}
