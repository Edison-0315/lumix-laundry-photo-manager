import SwiftUI
import PhotoWorkflowCore

struct PersonSheet: View {
    @Bindable var model: LibraryModel
    let assigning: Bool
    let ids: [PhotoID]
    let initialActivity: String?
    @Environment(\.dismiss) private var dismiss
    @State private var activityID = ""
    @State private var personID = ""
    @State private var name = ""
    @State private var started = false
    private var people: [CatalogRecord] { (model.catalog?.rows("people") ?? []).filter { $0.text("activity_id") == activityID } }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(assigning ? "设置人物归属" : "新建人物").font(.title2)
            if assigning { Text("将 \(ids.count) 张照片整理到同一人物文件夹。").foregroundStyle(.secondary) }
            Form {
                Picker("活动", selection: $activityID) {
                    ForEach(model.writableActivities) { activity in Text(activity.text("name") ?? activity.id).tag(activity.id) }
                }.disabled(assigning).accessibilityIdentifier("personActivity")
                if assigning {
                    Picker("人物", selection: $personID) {
                        Text("选择人物").tag("")
                        ForEach(people) { person in Text(person.text("name") ?? person.id).tag(person.id) }
                    }.accessibilityIdentifier("assignPerson")
                } else { TextField("人物名称", text: $name).accessibilityIdentifier("newPersonName") }
            }.disabled(model.busy)
            if model.busy { HStack { ProgressView().controlSize(.small); Text(model.progress).font(.caption) } }
            if let error = model.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
            HStack {
                Button("取消") { dismiss() }.keyboardShortcut(.cancelAction).disabled(model.busy)
                Spacer()
                Button(assigning ? "应用" : "创建") {
                    started = true
                    if assigning { model.assign(ids, person: personID) }
                    else { model.createPerson(activity: activityID, name: name.trimmingCharacters(in: .whitespacesAndNewlines)) }
                }.keyboardShortcut(.defaultAction)
                    .disabled(model.busy || !model.canWrite || activityID.isEmpty || (assigning ? personID.isEmpty : name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty))
                    .accessibilityIdentifier("confirmPerson")
            }
        }.padding(24).frame(width: 460).interactiveDismissDisabled(model.busy)
            .onAppear { activityID = initialActivity ?? model.activityID ?? model.writableActivities.first?.id ?? "" }
            .onChange(of: model.busy) { _, busy in if started && !busy && model.error == nil { dismiss() } }
    }
}
