import SwiftUI
import PhotoWorkflowCore

struct LibraryWorkspace: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Bindable var model: LibraryModel
    @State private var showInspector = true
    @State private var showNewActivity = false
    @State private var activityName = ""
    @State private var showPerson = false
    @State private var assigningPerson = false
    @State private var personPhotoIDs: [PhotoID] = []
    @State private var personActivity: String?
    @State private var showWorkReport = false
    @State private var managedPerson: CatalogRecord?
    @State private var mergingPerson = false
    @State private var cardFrames: [GridSelectionItem: CGRect] = [:]
    @State private var confirmRecovery = false
    @State private var exportPhoto: PhotoGroup?
    @State private var deletion: LibraryDeletion?
    @State private var confirmDeletion = false
    @State private var confirmClassification = false
    @AppStorage("thumbnailSize") private var size = 240.0
    var body: some View {
        NavigationSplitView {
            List(selection: $model.activityID) {
                Label("全部活动", systemImage: "photo.stack").tag(String?.none)
                Section("活动") {
                    ForEach(model.activities) { activity in
                        Label(activity.text("name") ?? activity.id, systemImage: "folder")
                            .tag(Optional(activity.id))
                    }
                }
            }
            .navigationSplitViewColumnWidth(min: 180, ideal: 220, max: 320)
            .disabled(model.busy)
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(model.catalog == nil ? "照片库" : model.isManaged ? "本机照片库" : "只读浏览").font(.caption.bold())
                    Text(model.catalog?.root.path ?? "尚未打开照片库").font(.caption).textSelection(.enabled)
                    Text(model.isManaged ? "来源只复制，原始文件保持不变。" : "不修改数据库，不恢复旧操作日志。").font(.caption2).foregroundStyle(.secondary)
                }.padding().frame(maxWidth: .infinity, alignment: .leading)
            }
        } detail: {
            VStack(spacing: 0) {
                filters
                Divider()
                if model.catalog == nil {
                    ContentUnavailableView {
                        Label("打开现有照片库", systemImage: "photo.stack")
                    } description: {
                        Text("新建照片库，或打开本应用创建的照片库。")
                    } actions: {
                        Button("新建照片库…", action: model.create).disabled(model.busy)
                        Button("打开本机照片库…", action: model.openManaged).disabled(model.busy)
                        Button("只读打开照片库…", action: model.choose).disabled(model.busy)
                    }.frame(maxWidth: .infinity, maxHeight: .infinity).accessibilityIdentifier("libraryEmpty")
                } else if model.visible.isEmpty {
                    ContentUnavailableView("没有符合条件的照片", systemImage: "line.3.horizontal.decrease.circle")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else { gallery }
                Divider()
                status
                if let notice = model.libraryNotice {
                    HStack {
                        Text(notice).font(.caption).foregroundStyle(.secondary).accessibilityIdentifier("libraryRecycleNotice")
                        if let url = model.recycledLibraryURL { Button("在 Finder 中显示") { NSWorkspace.shared.activateFileViewerSelecting([url]) } }
                    }.padding(10)
                }
                if let error = model.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled).padding(10) }
            }
        }
        .navigationTitle("照片库")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button("新建照片库…", action: model.create)
                    Button("打开本机照片库…", action: model.openManaged)
                    Button("只读浏览旧库…", action: model.choose)
                    RecentLibrariesMenu(model: model)
                    Button("关闭照片库", action: model.closeLibrary).disabled(model.catalog == nil)
                    Divider()
                    Button("新建活动…") { activityName = ""; showNewActivity = true }.disabled(!model.canWrite)
                    Divider()
                    Button("将整个照片库移入系统废纸篓…", action: model.prepareRecycling).disabled(!model.isManaged || !model.canWrite)
                } label: { Label("照片库", systemImage: "folder.badge.plus") }
                .disabled(model.busy).accessibilityIdentifier("libraryActions")
            }
            ToolbarItemGroup {
                Button(action: model.reload) { Label("重新读取", systemImage: "arrow.clockwise") }
                    .disabled(model.busy || model.catalog == nil)
                Button { model.showDiagnostics = true } label: { Label("读取报告", systemImage: "doc.text.magnifyingglass") }
                    .disabled(model.catalog == nil).accessibilityIdentifier("libraryReport")
                Button { showInspector.toggle() } label: { Label("详情", systemImage: "sidebar.right") }
            }
        }
        .inspector(isPresented: $showInspector) {
            VStack(spacing: 0) {
                PhotoInspector(photo: model.current?.photo)
                if let item = model.current {
                    Divider()
                    ScrollView {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("原库记录").font(.headline)
                            Text("照片 ID：\(item.id.rawValue)").textSelection(.enabled)
                            Text("活动：\(item.activityID) · 人物：\(item.personID)").textSelection(.enabled)
                            if item.trashed { Text(model.isManaged ? "已在应用回收站，可恢复或永久删除。" : "回收站记录，只读查看。") }
                            if item.purging { Text("永久删除未完成，可重试永久删除；当前不能恢复。").foregroundStyle(.orange) }
                            ForEach(item.assets) { asset in
                                Text(asset.path).textSelection(.enabled)
                                if let problem = asset.problem { Text(problem).foregroundStyle(.orange) }
                            }
                        }.font(.caption).padding().frame(maxWidth: .infinity, alignment: .leading)
                    }.frame(maxHeight: 220)
                }
            }.inspectorColumnWidth(min: 240, ideal: 280, max: 400)
        }
        .sheet(item: $model.preview) { session in
            PhotoViewer(session: session, selected: model.selection.selected, togglePhoto: model.toggle)
        }
        .sheet(isPresented: $model.showDiagnostics) { CatalogReport(catalog: model.catalog) }
        .sheet(isPresented: $showPerson) {
            PersonSheet(model: model, assigning: assigningPerson, ids: personPhotoIDs, initialActivity: personActivity)
        }
        .sheet(item: $managedPerson) { person in ManagePersonSheet(model: model, person: person, merging: mergingPerson) }
        .sheet(item: $exportPhoto) { photo in ExportSheet(model: model, id: photo.id) }
        .sheet(item: $model.recycleContext) { context in LibraryRecycleSheet(model: model, context: context) }
        .sheet(isPresented: $showWorkReport) {
            VStack(alignment: .leading, spacing: 18) {
                if let report = model.lastReport { WorkReportView(report: report) }
                else if model.busy { ProgressView(model.progress) }
                if let error = model.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
                Button("关闭") { showWorkReport = false }.keyboardShortcut(.cancelAction)
            }.padding(24).frame(width: 560, height: 360)
        }
        .alert("新建活动", isPresented: $showNewActivity) {
            TextField("活动名称", text: $activityName)
            Button("创建") { model.createActivity(activityName) }.disabled(activityName.isEmpty)
            Button("取消", role: .cancel) {}
        }
        .confirmationDialog("回滚本机库的未完成操作？", isPresented: $confirmRecovery) {
            Button("检查并回滚") { model.recoverPending(); showWorkReport = true }
        } message: {
            Text("只回滚本库能确认归属的未完成文件操作。已完成照片保留；未知或被替换的文件保留并报告，不执行旧库历史 SQL。")
        }
        .confirmationDialog(deletion?.title ?? "确认操作", isPresented: $confirmDeletion, presenting: deletion) { action in
            Button(action.button, role: .destructive) { model.delete(action) }
        } message: { action in Text(action.message) }
        .confirmationDialog("自动整理当前活动的人物？", isPresented: $confirmClassification) {
            Button("开始自动整理") { model.classifyActivity() }
        } message: {
            Text("在本机按人脸相似度分组并整理到人物文件夹。已手动设置人物的照片跳过；任务可取消，已完成的照片保留结果。照片与特征不上传。")
        }
        .onChange(of: model.activityID) { _, _ in model.personID = nil }
    }
    private var filters: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Picker("人物", selection: $model.personID) {
                    Text("全部人物").tag(String?.none)
                    ForEach(model.people) { person in Text(person.text("name") ?? person.id).tag(Optional(person.id)) }
                }.frame(maxWidth: 240).accessibilityIdentifier("libraryPerson")
                Picker("阶段", selection: $model.stage) {
                    Text("全部").tag("all"); Text("待修原片").tag("pending"); Text("已修原片").tag("edited"); Text("成片").tag("exports")
                }.frame(width: 180).accessibilityIdentifier("libraryStage")
                Toggle("回收站", isOn: $model.showTrash).toggleStyle(.checkbox).accessibilityIdentifier("libraryTrash")
                Spacer()
            }
            if !model.isManaged { HStack {
                TextField("旧库根路径，如 D:\\照片库（Windows 路径需要映射）", text: $model.oldRoot)
                    .textFieldStyle(.roundedBorder).accessibilityIdentifier("legacyRoot")
                Button("应用路径映射", action: model.reload).disabled(model.catalog == nil)
            } }
        }.padding(12).disabled(model.busy)
    }
    private var gallery: some View {
        GeometryReader { viewport in
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: size, maximum: size), spacing: 14)], spacing: 14) {
                ForEach(model.visible) { item in
                    VStack(alignment: .leading, spacing: 6) {
                        PhotoImage(photo: item.photo, maxPixel: 640).aspectRatio(4/3, contentMode: .fit)
                        Text(item.photo.stem).font(.caption).lineLimit(1)
                        HStack {
                            Text(item.photo.edited ? "已修" : "待修")
                            Spacer()
                            if item.photo.primaryExportID != nil { Label("成片", systemImage: "checkmark.seal") }
                        }.font(.caption2).foregroundStyle(.secondary)
                    }.padding(7)
                    .background(model.selection.selected.contains(item.id) ? Color.accentColor.opacity(0.2) : Color.secondary.opacity(0.07), in: .rect(cornerRadius: 8))
                    .modifier(PhotoSelectionOutline(selected: model.selection.selected.contains(item.id)))
                    .animation(reduceMotion || model.isMarqueeSelecting ? nil : .smooth(duration: 0.16), value: model.selection.selected.contains(item.id))
                    .overlay { PhotoClickSurface(click: { model.click(item.id, shift: $0, additive: $1) }, doubleClick: { model.open(item.id, fromDoubleClick: true) }, context: { model.selection.contextClick(item.id) }, open: { model.open(item.id) }) }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel(item.photo.stem + (model.selection.selected.contains(item.id) ? "，已选中" : ""))
                    .accessibilityIdentifier("libraryPhoto:\(item.id.rawValue)")
                    .accessibilityAction { model.toggle(item.id) }
                    .accessibilityAction(named: Text("预览照片")) { model.open(item.id) }
                    .selectionFrame(.photo(item.id))
                }
            }.padding(16)
                .frame(maxWidth: .infinity, minHeight: viewport.size.height, alignment: .topLeading)
                .modifier(MarqueeSelection(frames: cardFrames, model: model))
                .coordinateSpace(name: "selectionGrid")
                .onPreferenceChange(GridCardFrames.self) { cardFrames = $0 }
        }.accessibilityIdentifier("libraryGrid")
        }
    }
    private var status: some View {
        HStack {
            if model.busy { ProgressView().controlSize(.small); Text(model.isManaged ? model.progress : "正在读取照片库…"); Button("取消", action: model.cancel).disabled(model.recycling) }
            else { Text("\(model.visible.count) 张照片 · 已选 \(model.selection.selected.count) 张 · \(model.canWrite ? "本机库" : "只读")").accessibilityIdentifier("libraryStatus") }
            Spacer()
            if model.canRecover {
                Button("处理未完成操作…") { confirmRecovery = true }.accessibilityIdentifier("recoverLibrary")
            }
            Menu("整理") {
                Button("自动整理当前活动人物…") { confirmClassification = true }
                    .disabled(!model.canWrite || model.activityID == nil || model.showTrash)
                Button("新建人物…") {
                    assigningPerson = false; personPhotoIDs = []; personActivity = model.activityID; showPerson = true
                }.disabled(!model.canWrite || model.writableActivities.isEmpty)
                Button("设置人物归属…") {
                    assigningPerson = true; personPhotoIDs = model.selectedActivePhotos.map(\.id)
                    personActivity = model.selectedActivityID; showPerson = true
                }.disabled(!model.canEditSelection || model.selectedActivityID == nil)
                Button("重命名当前人物…") { mergingPerson = false; managedPerson = model.currentPerson }
                    .disabled(!model.canWrite || model.currentPerson == nil || model.currentPerson?.text("role") != nil)
                Button("合并当前人物…") { mergingPerson = true; managedPerson = model.currentPerson }
                    .disabled(!model.canWrite || model.currentPerson == nil || model.currentPerson?.text("role") != nil)
                Divider()
                Button("标记已修") { model.setEdited(true) }.disabled(!model.canEditSelection)
                Button("恢复待修") { model.setEdited(false) }.disabled(!model.canEditSelection)
                Divider()
                Button("将 JPEG 标记为成片") { model.setFinished(true) }.disabled(!model.canEditSelection)
                Button("成片版本…") { exportPhoto = model.current?.photo }.disabled(model.current == nil)
                Button("撤销最近归档", action: model.undoLatest).disabled(!model.canWrite || model.latestUndoID == nil)
                Button("定位缺失文件…", action: model.relinkMissing).disabled(model.singlePhoto == nil)
                Divider()
                Button("移入回收站…") {
                    deletion = .photos(model.selectedActivePhotos.map(\.id)); confirmDeletion = true
                }.disabled(!model.canEditSelection)
                Button("恢复所选照片", action: model.restoreSelection).disabled(!model.canRestore)
                Button("永久删除所选…") {
                    deletion = .purge(model.selectedTrashPhotos.map(\.id)); confirmDeletion = true
                }.disabled(!model.canPurge)
                Button("移除当前人物分类…") {
                    if let id = model.currentPerson?.id { deletion = .person(id); confirmDeletion = true }
                }.disabled(!model.canWrite || model.currentPerson == nil || model.currentPerson?.text("role") != nil)
                Button("将当前活动移入回收站…") {
                    if let id = model.activityID { deletion = .activity(id); confirmDeletion = true }
                }.disabled(!model.canWrite || model.showTrash || model.activityID == nil)
                Divider()
                Button("在 Finder 中显示", action: model.revealCurrent).disabled(model.current == nil)
                Menu("在 Photoshop 中打开") {
                    Button("JPEG") { model.openInEditor(.jpeg) }.disabled(model.singlePhoto?.photo.files.contains { $0.kind == .jpeg } != true)
                    Button("RAW") { model.openInEditor(.raw) }.disabled(model.singlePhoto?.photo.files.contains { $0.kind == .raw } != true)
                }.disabled(model.singlePhoto == nil)
            }.disabled(model.busy).accessibilityIdentifier("libraryOrganize")
            if model.lastReport != nil {
                Button("处理结果") { showWorkReport = true }.buttonStyle(.borderless).accessibilityIdentifier("showWorkReport")
            }
            if let catalog = model.catalog {
                Button("\(catalog.issues.count) 条提示") { model.showDiagnostics = true }
                    .buttonStyle(.borderless).accessibilityIdentifier("libraryReadReport")
            }
            Slider(value: $size, in: 80...720, step: 20).frame(width: 110).accessibilityLabel("照片库缩略图大小")
        }.font(.caption).padding(12)
    }
}

private struct CatalogReport: View {
    let catalog: LegacyCatalog?
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("照片库读取报告").font(.title2)
            Text("本报告来自只读快照。历史 SQL 仅作为文本保存，不执行。 ").font(.caption).foregroundStyle(.secondary)
            if let catalog {
                List {
                    Section("数据表") {
                        ForEach(catalog.tables.keys.sorted(), id: \.self) { name in LabeledContent(name, value: "\(catalog.rows(name).count) 条") }
                    }
                    Section("读取提示") {
                        if catalog.issues.isEmpty { Text("未发现读取问题") }
                        ForEach(catalog.issues) { Text($0.message).font(.caption).textSelection(.enabled) }
                    }
                    Section("历史操作（不执行恢复）") {
                        ForEach(catalog.rows("operations")) { row in
                            DisclosureGroup("\(row.text("kind") ?? "未知") · \(row.text("phase") ?? "未知") · \(row.id)") {
                                Text(row.text("payload") ?? "NULL").font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                                if let error = row.text("error") { Text(error).foregroundStyle(.orange) }
                            }
                        }
                    }
                }
            }
            Button("关闭") { dismiss() }.keyboardShortcut(.cancelAction)
        }.padding(20).frame(width: 680, height: 520).accessibilityIdentifier("catalogReport")
    }
}
