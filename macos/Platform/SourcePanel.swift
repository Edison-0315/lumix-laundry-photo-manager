import AppKit
@MainActor enum SourcePanel {
    static func choose() -> URL? {
        let panel = NSOpenPanel()
        panel.title = "选择 SD 卡或照片来源"
        panel.prompt = "读取"
        panel.canChooseDirectories = true; panel.canChooseFiles = false
        panel.allowsMultipleSelection = false; panel.canCreateDirectories = false
        return panel.runModal() == .OK ? panel.url : nil
    }
}
