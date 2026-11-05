import SwiftUI

struct RecentLibrary: Codable, Identifiable {
    let path: String
    let managed: Bool
    let oldRoot: String
    var id: String { path }
    var root: URL { URL(fileURLWithPath: path) }
}

struct RecentLibrariesMenu: View {
    @Bindable var model: LibraryModel
    var onOpen: () -> Void = {}
    var body: some View {
        Menu("最近打开的照片库") {
            if model.recents.isEmpty { Text("暂无记录") }
            ForEach(model.recents) { entry in
                Button(entry.root.lastPathComponent + (entry.managed ? "" : "（只读）")) { onOpen(); model.openRecent(entry) }
                    .help(entry.path)
            }
            Divider()
            Button("清除最近记录", action: model.clearRecents).disabled(model.recents.isEmpty)
        }.disabled(model.busy)
    }
}
