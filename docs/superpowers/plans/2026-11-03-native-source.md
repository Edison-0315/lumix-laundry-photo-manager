# 原生来源读取首个增量实现计划

> **面向 AI 代理的工作者：** 使用 executing-plans 逐任务实现，按 test-driven-development 验证。

**目标：** 交付可由 Xcode 构建的 SwiftUI 应用和只读来源读取纵向流程；P0完成，P1按已验收范围报告。

**架构：** 本地 PhotoWorkflowCore 包负责模型、纯查询与选择状态。原生应用负责后台扫描、ImageIO读取与SwiftUI展示；没有库写入口。

**技术栈：** Swift 6、macOS14+、SwiftUI、局部AppKit、ImageIO、CryptoKit、Xcode。

**规格：** docs/NATIVE_ARCHITECTURE.md；docs/IMPLEMENTATION_PLAN.md；/Users/edison/Downloads/MACOS_MIGRATION.md。

## 全局约束

- Windows参考不改；无Python/Node/WebView运行依赖。
- 来源只读；新扫描取消/全失败不替换旧结果。
- 真RW2、复杂框选和锚点缩放必须单独验收，未验证不称P1整体完成。
- 用户已批准阶段计划并要求继续；本细化计划按原阶段范围执行。

## 审查重点（Review Focus）

- 同名不同拍摄目录不得错误配对，模糊兄弟目录不合并。
- 符号链接不得逃逸来源；单条错误不终止其他条目。
- 取消/失败和迟到图像不能清掉旧扫描/选择或覆盖新照片。
- 成片和edited独立；拍摄日期不得UTC换日。
- 来源扫描、缩略图、元数据不得新增或修改源文件。

### Task 1：业务契约与核心包

文件：macos/Packages/PhotoWorkflowCore/Package.swift；Sources/PhotoWorkflowCore/{PhotoModels,PhotoPairing,SelectionState,LegacySignature}.swift；Tests/PhotoWorkflowCoreTests/ContractTests.swift。

- [x] 定义最小API和失败测试：同目录JPEG/RAW/XMP；明确兄弟目录；歧义和不同拍摄目录分开；edited+成片可重叠；日期保留；单击叠加/Shift/右键/可见全选/双击恢复；signature按sorted tuple-list原格式。
- [x] 运行 `swift test --package-path macos/Packages/PhotoWorkflowCore`，确认断言因未实现失败。
- [x] 实现 PhotoGroup、FileAsset、ReadFormat、StageFilter、PhotoPairing.groups(files:)、SelectionState、LegacySignature.hash(members:)。
- [x] 同命令全绿；提交。

### Task 2：只读扫描与图像读取

文件：核心包 Sources/PhotoWorkflowCore/{SourceScanner,ImageReader}.swift；Tests/PhotoWorkflowCoreTests/SourceTests.swift。图像读取依赖ImageIO/CoreGraphics，无AppKit；预览返回JPEG Data。

- [x] 写失败测试：真实临时JPEG/假RAW/XMP配对、链接排除、坏图保留、单条读取注入失败继续、取消不发布、旧结果保留、来源前后SHA/文件名不变、EXIF转向。
- [x] 运行全套，确认失败；实现scan(root:format:cancel:progress:)与ImageReader，逐条诊断、协作取消。
- [x] 实现来源会话发布纯逻辑，只接受未取消且有效的新结果；图像下采样和EXIF日期读取。
- [x] 同命令全绿；提交。

### Task 3：Xcode原生只读界面和可运行交付

文件：macos/LaundryPhotoManager.xcodeproj、App/{LaundryPhotoManagerApp,AppModel}.swift、Features/{Sources,Culling,Inspector,Viewer}、Platform/SourcePanel.swift、script/build_and_run.sh、.codex/environments/environment.toml。

- [x] 添加原生UI测试：空状态和选择来源入口、设置入口；模型测试验证旧结果保留和选择契约（复用前两任务）。
- [x] Xcode测试确认UI尚不可用；实现WindowGroup、NavigationSplitView、真实来源选择、取消/结果诊断、缩略图、目录/格式/日期筛选、详情、基础大图、选择与菜单。
- [x] `xcodebuild -project macos/LaundryPhotoManager.xcodeproj -scheme LaundryPhotoManager -destination 'platform=macOS,arch=arm64' -derivedDataPath build test CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES` 通过；`./script/build_and_run.sh --verify` 构建并启动。
- [x] 独立审查后修复重要问题；记录精确验收范围，未通过的P1能力留待下一增量，不称完整迁移完成。
- [x] 提交并保持本地开发分支，不合并/推送/发布。
