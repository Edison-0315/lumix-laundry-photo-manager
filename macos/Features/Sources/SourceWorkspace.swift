import SwiftUI
import PhotoWorkflowCore
struct SourceWorkspace: View {
    @Bindable var model: AppModel
    @Bindable var library: LibraryModel
    let onOpenLibrary: () -> Void
    @State private var importSession: SourceImportSession?
    @State private var showInspector = true
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @AppStorage("thumbnailSize") private var thumbnailSize = 240.0
    var body: some View {
        NavigationSplitView {
            List(selection: $model.location) {
                Section("选片来源") {
                    Label("全部子文件夹", systemImage: "photo.on.rectangle").tag(SourceLocation.all)
                    ForEach(model.folders, id: \.self) { path in
                        Label(path.isEmpty ? "来源根目录" : path, systemImage: "folder").tag(SourceLocation.folder(path)).help(path)
                    }
                }
            }.disabled(!model.canNavigate).navigationSplitViewColumnWidth(min: 180, ideal: 220, max: 300)
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("当前来源").font(.caption).foregroundStyle(.secondary)
                    Text(model.root?.path ?? "尚未选择").font(.caption).lineLimit(3).textSelection(.enabled)
                    Text("来源只读").font(.caption2).foregroundStyle(.secondary)
                }.padding().frame(maxWidth: .infinity, alignment: .leading)
            }
        } detail: {
            VStack(spacing: 0) {
                if model.root != nil {
                    SourceBreadcrumbs(model: model).disabled(!model.canNavigate)
                    Divider()
                }
                HStack {
                    Picker("日期", selection: $model.date) {
                        Text("所有日期").tag("all")
                        ForEach(Array(Set(model.photos.map(\.dateKey))).sorted(), id: \.self) { day in Text(day == "unknown" ? "拍摄日期未知" : day).tag(day) }
                    }.frame(maxWidth: 200).accessibilityLabel("日期").accessibilityIdentifier("sourceDate")
                    Picker("格式", selection: $model.format) { Text("所有格式").tag("all"); Text("JPEG").tag("jpeg"); Text("RAW").tag("raw") }.frame(width: 150).accessibilityLabel("格式").accessibilityIdentifier("sourceFormat")
                    Toggle("只看已选", isOn: $model.onlySelected).toggleStyle(.checkbox)
                    Spacer()
                }.padding(12).disabled(!model.canNavigate)
                Divider()
                if model.photos.isEmpty {
                    ContentUnavailableView {
                        Label("从 SD 卡开始选片", systemImage: "sdcard")
                    } description: { Text("选择照片文件夹，读取 JPEG、RAW 和伴随 XMP。") }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .accessibilityIdentifier("sourceEmpty")
                } else { PhotoGrid(model: model, size: thumbnailSize).id(model.navigation.route).id(model.sourceVersion) }
                Divider()
                HStack {
                    Text("\(model.visible.count) 张照片 · 已选 \(model.selection.selected.count) 张 · 已选 \(model.folderChoices.selected(in: model.location).count) 个文件夹").font(.caption).monospacedDigit().accessibilityIdentifier("sourceSelectionStatus")
                    Spacer()
                    Button("导入所选…") {
                        if let root = model.root { importSession = SourceImportSession(root: root, photos: model.importPhotos) }
                    }.disabled(!model.canNavigate || model.importPhotos.isEmpty || library.busy).accessibilityIdentifier("importSelected")
                    Image(systemName: "photo").accessibilityHidden(true)
                    Slider(value: $thumbnailSize, in: 80...720, step: 20).frame(width: 110).accessibilityLabel("缩略图大小")
                }.padding(12)
                if model.busy {
                    HStack { ProgressView().controlSize(.small); Text(model.progress).font(.caption); Spacer(); Button("取消读取") { model.cancel() } }.padding(12)
                }
                if let message = model.message {
                    HStack {
                        Text(message).font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        if !model.issues.isEmpty { Button("查看 \(model.issues.count) 条问题") { model.showIssues = true } }
                    }.padding(.horizontal, 12).padding(.bottom, 8)
                }
            }
        }
        .navigationTitle("选片")
        .toolbar {
            ToolbarItemGroup(placement: .navigation) {
                Button(action: model.goBack) { Label("后退", systemImage: "chevron.left") }
                    .disabled(!model.canGoBack).accessibilityIdentifier("sourceBack")
                Button(action: model.goForward) { Label("前进", systemImage: "chevron.right") }
                    .disabled(!model.canGoForward).accessibilityIdentifier("sourceForward")
                Button(action: model.goUp) { Label("上级文件夹", systemImage: "arrow.up") }
                    .disabled(!model.canGoUp).accessibilityIdentifier("sourceUp")
            }
            ToolbarItem(placement: .primaryAction) {
                Button { model.chooseSource() } label: { Label("选择来源", systemImage: "folder.badge.plus") }.accessibilityIdentifier("chooseSource").disabled(model.busy || library.busy)
            }
            ToolbarItemGroup(placement: .automatic) {
                Picker("读取格式", selection: $model.readFormat) { Text("JPEG 和 RAW").tag(ReadFormat.both); Text("仅 JPEG").tag(ReadFormat.jpeg); Text("仅 RAW").tag(ReadFormat.raw) }.labelsHidden().pickerStyle(.menu).frame(width: 140).disabled(model.busy)
                Button {
                    withAnimation(reduceMotion ? nil : .smooth(duration: 0.2)) { showInspector.toggle() }
                } label: { Label("详情", systemImage: "sidebar.right") }
            }
        }
        .inspector(isPresented: $showInspector) { PhotoInspector(photo: model.current).inspectorColumnWidth(min: 240, ideal: 280, max: 360) }
        .sheet(item: $model.preview) { session in
            PhotoViewer(session: session, selected: model.selection.selected, togglePhoto: { model.click($0, shift: false, additive: false) })
        }
        .sheet(item: $importSession) { session in
            SourceImportSheet(session: session, library: library, onOpenLibrary: onOpenLibrary)
        }
        .sheet(isPresented: $model.showIssues) {
            VStack(alignment: .leading) {
                Text("读取问题").font(.title2)
                List(model.issues) { issue in VStack(alignment: .leading) { Text(issue.path).textSelection(.enabled); Text("\(issue.operation) · 错误 \(issue.code)：\(issue.message)").foregroundStyle(.secondary) } }
                Button("关闭") { model.showIssues = false }.keyboardShortcut(.cancelAction)
            }.padding().frame(width: 650, height: 420)
        }
    }
}
