import SwiftUI
import PhotoWorkflowCore

struct ManagePersonSheet: View {
    @Bindable var model: LibraryModel
    let person: CatalogRecord
    let merging: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var target = ""
    @State private var started = false
    private var targets: [CatalogRecord] {
        (model.catalog?.rows("people") ?? []).filter { $0.id != person.id && $0.text("activity_id") == person.text("activity_id") }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(merging ? "合并人物" : "重命名人物").font(.title2)
            Text(person.text("name") ?? "").foregroundStyle(.secondary)
            if merging {
                Text("照片和归属将转移到目标人物，成功后移除原人物。")
                Picker("合并到", selection: $target) {
                    Text("选择人物").tag("")
                    ForEach(targets) { item in Text(item.text("name") ?? item.id).tag(item.id) }
                }.accessibilityIdentifier("mergeTarget")
            } else { TextField("人物名称", text: $name).accessibilityIdentifier("renamePersonName") }
            if model.busy {
                HStack { ProgressView().controlSize(.small); Text(model.progress).font(.caption)
                    if merging { Button("取消任务", action: model.cancel) }
                }
            }
            if let error = model.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
            HStack {
                Button("取消") { dismiss() }.keyboardShortcut(.cancelAction).disabled(model.busy)
                Spacer()
                Button(merging ? "合并" : "保存") {
                    started = true
                    if merging { model.mergePerson(person.id, into: target) }
                    else { model.renamePerson(person.id, name: name.trimmingCharacters(in: .whitespacesAndNewlines)) }
                }.keyboardShortcut(.defaultAction).accessibilityIdentifier("confirmManagePerson")
                    .disabled(model.busy || !model.canWrite || (merging ? target.isEmpty : name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty))
            }
        }.padding(24).frame(width: 460).interactiveDismissDisabled(model.busy)
            .onAppear { name = person.text("name") ?? "" }
            .onChange(of: model.busy) { _, busy in if started && !busy && model.error == nil { dismiss() } }
    }
}
