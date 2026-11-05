import SwiftUI
import PhotoWorkflowCore
struct SourceBreadcrumbs: View {
    let model: AppModel
    var body: some View {
        HStack {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(Array(model.location.breadcrumbs.enumerated()), id: \.element) { index, location in
                        if index > 0 { Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.secondary).accessibilityHidden(true) }
                        Button(location.label) { model.openLocation(location) }
                            .disabled(location == model.location)
                            .accessibilityIdentifier(location == .folder("") ? "sourceRoot" : "sourceCrumb:\(location.label)")
                    }
                }.buttonStyle(.borderless)
            }
            Text(model.location.label).font(.caption).foregroundStyle(.secondary).lineLimit(1).frame(maxWidth: 140, alignment: .trailing)
                .accessibilityIdentifier("sourceLocation")
        }.padding(.horizontal, 12).padding(.vertical, 8)
    }
}
