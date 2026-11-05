import Foundation
import Darwin

public struct CatalogPathResolver: Sendable {
    public let root: URL
    public let oldRoot: String?
    public init(root: URL, oldRoot: String? = nil) { self.root = root; self.oldRoot = oldRoot }

    public func resolve(_ path: String, trashPhotoID: String? = nil, trashAssetID: String? = nil) -> (url: URL?, problem: String?) {
        guard !path.isEmpty, !path.utf8.contains(0) else { return (nil, "路径为空或包含无效字符") }
        let normalized = path.replacingOccurrences(of: "\\", with: "/")
        let components = SourcePath.components(normalized)
        guard !components.contains(".."), !components.contains(".") else { return (nil, "路径含有越界或相对跳转") }
        var relative: [String]
        let windows = normalized.hasPrefix("//") || (normalized.utf8.count >= 2 && normalized.utf8.dropFirst().first == 58)
        if windows {
            guard let oldRoot, !oldRoot.isEmpty else { return (nil, "Windows 路径尚未映射，请填写旧库根路径") }
            let old = oldRoot.replacingOccurrences(of: "\\", with: "/")
            let prefix = SourcePath.components(old)
            func absoluteDrive(_ value: String) -> Bool {
                let bytes = Array(value.utf8)
                return bytes.count >= 3 && ((65...90).contains(bytes[0]) || (97...122).contains(bytes[0])) && bytes[1] == 58 && bytes[2] == 47
            }
            let unc = normalized.hasPrefix("//") && old.hasPrefix("//") && components.count >= 3 && prefix.count >= 2
            guard !normalized.hasPrefix("//?/"), !old.hasPrefix("//?/"), !normalized.hasPrefix("//./"), !old.hasPrefix("//./"),
                  !prefix.contains(".."), !prefix.contains("."), unc || (absoluteDrive(normalized) && absoluteDrive(old))
            else { return (nil, "需要完整的盘符路径或 UNC 共享路径") }
            guard !prefix.isEmpty, components.count > prefix.count,
                  zip(components, prefix).allSatisfy({ $0.lowercased() == $1.lowercased() }) else { return (nil, "路径不在指定的旧库根目录内") }
            relative = Array(components.dropFirst(prefix.count))
        } else if normalized.hasPrefix("/") {
            let prefix = SourcePath.components(root.path)
            guard components.count > prefix.count, Array(components.prefix(prefix.count)) == prefix else { return (nil, "路径不在当前照片库内") }
            relative = Array(components.dropFirst(prefix.count))
        } else { relative = components }
        guard !relative.isEmpty else { return (nil, "照片路径为空") }
        if relative.first == ".片集" {
            guard relative.count == 5, relative[1] == "回收站", relative[2] == trashPhotoID, relative[3] == trashAssetID else {
                return (nil, "只能读取有对应照片与资产记录的回收站文件")
            }
        }
        var url = root
        for component in relative { url.appendPathComponent(component) }
        do {
            let fd = try SafeImageSource.fileDescriptor(url); Darwin.close(fd)
            return (url, nil)
        } catch {
            let code = (error as NSError).code
            if code == Int(ENOENT) { return (url, "文件缺失") }
            return (nil, "路径包含符号链接、不是普通文件或无法安全读取：" + error.localizedDescription)
        }
    }
}
