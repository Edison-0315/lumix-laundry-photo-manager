import SwiftUI
import AppKit
@main struct LaundryPhotoManagerApp: App {
    @State private var model = AppModel()
    @State private var library = LibraryModel()
    @State private var workspace = "source"
    @AppStorage("appearance") private var appearance = "dark"
    private var preferredScheme: ColorScheme? { appearance == "dark" ? .dark : appearance == "light" ? .light : nil }
    var body: some Scene {
        WindowGroup("LUMIX 洗衣机管理器", id: "main") {
            TabView(selection: $workspace) {
                SourceWorkspace(model: model, library: library, onOpenLibrary: { workspace = "library" }).tabItem { Label("选片", systemImage: "sdcard") }.tag("source")
                LibraryWorkspace(model: library).tabItem { Label("照片库", systemImage: "photo.stack") }.tag("library")
            }.frame(minWidth: 1000, minHeight: 680)
                .background {
                    #if DEBUG
                    if ProcessInfo.processInfo.arguments.contains("--compact-window") { CompactTestWindow().accessibilityHidden(true) }
                    #endif
                }
                .onChange(of: model.protectedSourceRoots, initial: true) { _, roots in
                    library.protectedSourceRoots.formUnion(roots)
                }
                .onChange(of: library.isManaged ? library.catalog?.root : nil, initial: true) { _, root in
                    model.writableLibraryRoot = root
                }
                .preferredColorScheme(preferredScheme)
        }
        .defaultSize(width: 1280, height: 820)
        .windowToolbarStyle(.expanded)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("新建照片库…") { workspace = "library"; library.create() }.keyboardShortcut("n").disabled(library.busy)
                Button("打开本机照片库…") { workspace = "library"; library.openManaged() }.keyboardShortcut("o", modifiers: [.command, .option]).disabled(library.busy)
                Button("选择照片来源…") { workspace = "source"; model.chooseSource() }.keyboardShortcut("o").disabled(model.busy || library.busy)
                Button("只读打开照片库…") { workspace = "library"; library.choose() }.keyboardShortcut("o", modifiers: [.command, .shift]).disabled(library.busy)
                RecentLibrariesMenu(model: library, onOpen: { workspace = "library" })
                Button("关闭照片库", action: library.closeLibrary).disabled(library.busy || library.catalog == nil)
            }
            CommandGroup(replacing: .help) {
                Button("第三方许可…") {
                    if let url = Bundle.main.url(forResource: "README", withExtension: "txt", subdirectory: "ThirdPartyNotices") {
                        NSWorkspace.shared.open(url)
                    }
                }
            }
            CommandMenu("浏览") {
                Button("后退", action: model.goBack).keyboardShortcut("[", modifiers: .command).disabled(workspace != "source" || !model.canGoBack)
                Button("前进", action: model.goForward).keyboardShortcut("]", modifiers: .command).disabled(workspace != "source" || !model.canGoForward)
                Button("上级文件夹", action: model.goUp).keyboardShortcut(.upArrow, modifiers: .command).disabled(workspace != "source" || !model.canGoUp)
            }
            CommandMenu("选片") {
                Button("全选当前显示") {
                    if let editor = NSApp.keyWindow?.firstResponder as? NSTextView { editor.selectAll(nil) }
                    else if workspace == "source" { model.selectVisible() } else { library.selectVisible() }
                }.keyboardShortcut("a")
                Button("取消当前显示的选择") {
                    guard !(NSApp.keyWindow?.firstResponder is NSTextView) else { return }
                    if workspace == "source" { model.deselectVisible() } else { library.deselectVisible() }
                }.keyboardShortcut("a", modifiers: [.command, .shift])
            }
        }
        Settings {
            Form {
                Text("本机照片管理").font(.headline)
                Text("照片和人物整理均在本机完成，来源文件保持不变。")
                Picker("外观", selection: $appearance) {
                    Text("跟随系统").tag("system")
                    Text("深色").tag("dark")
                    Text("浅色").tag("light")
                }.pickerStyle(.segmented).accessibilityIdentifier("appearanceSetting")
                EditorSettings()
            }.padding(24).frame(width: 420).preferredColorScheme(preferredScheme).accessibilityIdentifier("appSettings")
        }
    }
}
