import PhotoWorkflowCore

enum LibraryDeletion {
    case photos([PhotoID]), person(String), activity(String), purge([PhotoID])
    var title: String {
        switch self {
        case .photos(let ids): "将 \(ids.count) 张照片移入回收站？"
        case .person: "移除此人物分类？"
        case .activity: "将此活动移入回收站？"
        case .purge(let ids): "永久删除 \(ids.count) 张照片？"
        }
    }
    var button: String {
        switch self { case .photos, .activity: "移入回收站"; case .person: "移除分类"; case .purge: "永久删除" }
    }
    var message: String {
        switch self {
        case .photos: "照片及关联成片将移到应用回收站，之后可以恢复。来源文件保留。"
        case .person: "照片转入同活动的待分类。回收站中的照片恢复后也归入待分类，文件保留。"
        case .activity: "活动中的照片移到应用回收站。全部成功后隐藏活动，恢复照片会重新显示活动。"
        case .purge: "此操作不能撤销。仅删除本库回收站中能确认身份的文件；中断后可重试，已删除的照片不能恢复。"
        }
    }
}
