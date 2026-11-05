import SwiftUI
import PhotoWorkflowCore

struct SourceImportSession: Identifiable {
    let id = UUID()
    let root: URL
    let photos: [PhotoGroup]
}

struct SourceImportSheet: View {
    let session: SourceImportSession
    @Bindable var library: LibraryModel
    let onOpenLibrary: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var activityID = ""
    @State private var activityName = ""
    @State private var format = ReadFormat.both
    @State private var started = false
    private var targetName: String {
        if activityID.isEmpty { return activityName.trimmingCharacters(in: .whitespacesAndNewlines) }
        return library.writableActivities.first { $0.id == activityID }?.text("name") ?? ""
    }
    private var hasFiles: Bool {
        session.photos.contains { photo in photo.files.contains { file in
            (format != .raw && file.kind == .jpeg) || (format != .jpeg && file.kind == .raw)
        } }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("导入所选照片").font(.title2).accessibilityIdentifier("sourceImportSheet")
            Text("\(session.photos.count) 张照片 · 来源只复制，原文件保留。").foregroundStyle(.secondary)
            Text(session.root.path).font(.caption).textSelection(.enabled)
            if started, let report = library.lastReport, !library.busy {
                WorkReportView(report: report)
            } else if !library.canWrite && !library.busy {
                Text("请先新建或打开本机照片库。旧照片库只能只读浏览。")
                HStack {
                    Button("新建照片库…", action: library.create)
                    Button("打开本机照片库…", action: library.openManaged)
                }
            } else {
                Form {
                    LabeledContent("照片库", value: library.catalog?.root.lastPathComponent ?? "")
                    Picker("活动", selection: $activityID) {
                        Text("新活动…").tag("")
                        ForEach(library.writableActivities) { item in Text(item.text("name") ?? item.id).tag(item.id) }
                    }.accessibilityIdentifier("importActivity")
                    if activityID.isEmpty {
                        TextField("新活动名称", text: $activityName).accessibilityIdentifier("newImportActivity")
                    }
                    Picker("导入格式", selection: $format) {
                        Text("全部已读取格式").tag(ReadFormat.both)
                        Text("仅 JPEG").tag(ReadFormat.jpeg)
                        Text("仅 RAW").tag(ReadFormat.raw)
                    }
                }.disabled(library.busy)
                if !hasFiles { Text("所选照片中没有此格式，请调整导入格式。").font(.caption).foregroundStyle(.orange) }
            }
            if library.busy {
                HStack { ProgressView().controlSize(.small); Text(library.progress).font(.caption); Spacer(); Button("取消任务", action: library.cancel) }
            }
            if let error = library.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
            Spacer(minLength: 0)
            HStack {
                Button(started && library.lastReport != nil ? "完成" : "取消") { dismiss() }.keyboardShortcut(.cancelAction).disabled(library.busy)
                Spacer()
                if started, library.lastReport != nil, !library.busy {
                    Button("查看照片库") { dismiss(); onOpenLibrary() }.keyboardShortcut(.defaultAction)
                } else {
                    Button("开始导入") {
                        started = true
                        library.importSelected(session.photos, root: session.root, activity: targetName, format: format)
                    }.disabled(!library.canWrite || library.busy || targetName.isEmpty || !hasFiles)
                        .keyboardShortcut(.defaultAction).accessibilityIdentifier("confirmImport")
                }
            }
        }.padding(24).frame(width: 560, height: 420)
            .interactiveDismissDisabled(library.busy)
            .onAppear { selectActivity() }
            .onChange(of: library.catalog?.root) { _, _ in selectActivity() }
    }
    private func selectActivity() {
        activityID = library.activityID ?? library.writableActivities.first?.id ?? ""
    }
}
