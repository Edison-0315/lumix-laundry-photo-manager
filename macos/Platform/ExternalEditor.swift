import AppKit
import Darwin
import UniformTypeIdentifiers

@MainActor enum ExternalEditor {
    static var configuredURL: URL? {
        let path = UserDefaults.standard.string(forKey: "photoshopPath") ?? ""
        if !path.isEmpty { return URL(fileURLWithPath: path) }
        return NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.adobe.Photoshop")
    }
    static func choose() -> URL? {
        let panel = NSOpenPanel()
        panel.title = "选择 Adobe Photoshop"; panel.prompt = "选择"
        panel.allowedContentTypes = [.application]; panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.directoryURL = URL(fileURLWithPath: "/Applications")
        guard panel.runModal() == .OK, let url = panel.url else { return nil }
        guard Bundle(url: url)?.bundleIdentifier?.hasPrefix("com.adobe.Photoshop") == true else { return nil }
        UserDefaults.standard.set(url.path, forKey: "photoshopPath")
        return url
    }
    static func readable(_ url: URL) -> Bool {
        let fd = Darwin.open(url.path, O_RDONLY | O_NOFOLLOW_ANY | O_NONBLOCK | O_CLOEXEC)
        guard fd >= 0 else { return false }; defer { Darwin.close(fd) }
        var value = stat()
        return fstat(fd, &value) == 0 && value.st_mode & S_IFMT == S_IFREG
    }
    static func reveal(_ url: URL) -> Bool {
        guard readable(url) else { return false }
        NSWorkspace.shared.activateFileViewerSelecting([url]); return true
    }
    static func open(_ url: URL, completion: @escaping @MainActor (String?) -> Void) {
        guard readable(url) else { completion("文件缺失或不可安全读取，请先定位文件。"); return }
        guard let editor = configuredURL ?? choose() else { completion("请选择有效的 Photoshop.app。"); return }
        NSWorkspace.shared.open([url], withApplicationAt: editor, configuration: .init()) { _, error in
            let message = error?.localizedDescription
            Task { @MainActor in completion(message) }
        }
    }
}
