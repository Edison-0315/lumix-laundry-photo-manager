import SwiftUI

struct LibraryRecycleSheet: View {
    @Bindable var model: LibraryModel
    let context: LibraryRecycleContext
    @State private var name = ""
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("将整个照片库移入系统废纸篓").font(.title2).accessibilityIdentifier("libraryRecycleSheet")
            Text(context.plan.name).font(.headline)
            Text(context.plan.root).font(.caption).textSelection(.enabled)
            Text("\(context.plan.photoCount) 张照片（含应用回收站）· \(context.plan.fileCount) 个文件 · \(ByteCountFormatter.string(fromByteCount: context.plan.bytes, countStyle: .file))")
                .font(.callout).accessibilityIdentifier("libraryRecycleCounts")
            Text("整个文件夹及其中所有文件会移入系统废纸篓，包括照片、版本和数据库。库外来源文件保留；失败时不会改为永久删除。")
                .foregroundStyle(.secondary)
            TextField("输入照片库名称确认", text: $name).textFieldStyle(.roundedBorder).accessibilityIdentifier("confirmLibraryName")
                .disabled(model.busy)
            if model.busy { ProgressView(model.progress).controlSize(.small) }
            if let error = model.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
            HStack {
                Button("取消") { dismiss() }.keyboardShortcut(.cancelAction).disabled(model.busy)
                Spacer()
                Button("移入系统废纸篓", role: .destructive) { model.recycleLibrary(context, name: name) }
                    .disabled(model.busy || !model.canWrite || name != context.plan.name)
                    .accessibilityIdentifier("confirmRecycleLibrary")
            }
        }.padding(24).frame(width: 560).interactiveDismissDisabled(model.busy)
    }
}
