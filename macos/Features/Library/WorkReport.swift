import SwiftUI

struct BatchDetails: Decodable, Sendable {
    let imported: [String]?
    let updated: [String]?
    let skipped: Int?
    let photoIDs: [String]?
    let operations: [String]?
    let errors: [WorkIssue]?
    let cancelled: Bool?
    let activityID: String?
    let recovered: [String]?
    let relinked: [String]?
    let deleted: [String]?
    let deletedPeople: [String]?
    let classified: Int?
    enum CodingKeys: String, CodingKey {
        case imported, updated, skipped, operations, errors, cancelled, recovered, relinked, classified
        case photoIDs = "photo_ids", activityID = "activity_id"
        case deleted, deletedPeople = "deleted_people"
    }
}
struct WorkIssue: Decodable, Identifiable, Sendable {
    let id = UUID()
    let name: String?
    let recordID: String?
    let message: String
    enum CodingKeys: String, CodingKey { case name, message, errors; case recordID = "id" }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        name = try values.decodeIfPresent(String.self, forKey: .name)
        recordID = try values.decodeIfPresent(String.self, forKey: .recordID)
        if let text = try values.decodeIfPresent(String.self, forKey: .message) { message = text }
        else { message = try values.decode([String].self, forKey: .errors).joined(separator: "\n") }
    }
}
struct WorkReport: Identifiable, Sendable {
    let id = UUID()
    let title: String
    let importing: Bool
    let details: BatchDetails
    var summary: String {
        if let recovered = details.recovered { return "已回滚 \(recovered.count) 条未完成操作" }
        if let relinked = details.relinked { return "找回 \(relinked.count) 个文件" }
        if let deleted = details.deleted { return "永久删除 \(deleted.count) 张照片" }
        if let people = details.deletedPeople { return "移除 \(people.count) 个人物分类 · 整理 \(details.photoIDs?.count ?? 0) 张照片" }
        if let classified = details.classified { return "整理 \(classified) 张照片 · 跳过 \(details.skipped ?? 0) 张" }
        if importing { return "新增 \(details.imported?.count ?? 0) 张 · 补齐 \(details.updated?.count ?? 0) 张 · 跳过 \(details.skipped ?? 0) 张" }
        return "完成 \(details.photoIDs?.count ?? details.operations?.count ?? 0) 张 · 跳过 \(details.skipped ?? 0) 张"
    }
}
struct WorkReportView: View {
    let report: WorkReport
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(report.title).font(.title2)
            Text(report.summary).monospacedDigit().accessibilityIdentifier("workReportSummary")
            if report.details.cancelled == true { Label("已取消，已完成的照片组保留。", systemImage: "pause.circle").foregroundStyle(.secondary) }
            if let errors = report.details.errors, !errors.isEmpty {
                Text("\(errors.count) 项未完成").foregroundStyle(.orange)
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(errors) { issue in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(issue.name ?? issue.recordID ?? "照片").font(.caption.bold())
                                Text(issue.message).font(.caption).foregroundStyle(.secondary)
                            }.textSelection(.enabled)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }
            } else if report.details.cancelled != true { Label("处理已结束", systemImage: "checkmark.circle").foregroundStyle(.secondary) }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}
