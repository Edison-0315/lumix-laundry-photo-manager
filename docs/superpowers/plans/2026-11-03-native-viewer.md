# 原生预览缩放和平移实现计划

> **面向 AI 代理的工作者：** 使用 executing-plans 和 test-driven-development 逐任务执行。

**目标：** 在 P1 的现有只读预览内完成指针锚点缩放、拖动、适应、100% 和切图复位。

**架构：** PhotoWorkflowCore 的 ViewportTransform 管理图像像素到画布 points 的变换。SwiftUI 持有预览状态和工具栏；局部 NSViewRepresentable 仅负责精确滚轮、指针、拖动和绘制。图像继续通过安全只读 ImageIO 管线解码。

**技术栈：** Swift 6、macOS 14+、SwiftUI、AppKit、CoreGraphics、ImageIO、Xcode。

**规格：** docs/NATIVE_ARCHITECTURE.md §原生预览；docs/IMPLEMENTATION_PLAN.md P1；/Users/edison/Downloads/MACOS_MIGRATION.md §3.11。

## 全局约束

- 用户已授权按阶段继续；本细化计划直接在现有 feature/native-p1 执行。
- Windows 参考只读；来源无写操作；无 Python 运行依赖。
- 预览仍为最长边 4096 的解码图；100% 明示为预览像素与显示像素一一对应。原片全分辨率检视留后续解码工作。
- 缩放范围 2%–1600%；适应不放大；按钮乘 1.25 / 0.8；滚轮因子 exp(clamp(-pixels * .0018, -.4, .4))。
- 坐标为 points；比例显示按 backing scale 换算为显示像素。拖动跟手且限边；本增量无弹簧、惯性或来源转场动画，减少动态时同样即时响应。P1 不整体标记完成。

## 审查重点（Review Focus）

- letterbox 外指针应夹到图像边缘，缩放不突然居中；单元测试覆盖。
- Retina 和屏幕切换后 100% 仍为一预览像素对一显示像素；单元测试及本机人工检查。
- 快速切图/关闭后旧解码不能覆盖新照片；按照片隔离 SwiftUI 生命周期，取消复验。
- 原生按钮的空格激活不能被预览截获；仅画布聚焦时处理空格且忽略重复，UI/人工检查。
- 加载失败能重试；切图始终重置 fit，冻结序列和选择不被缩放操作改变；UI 测试覆盖。

### Task 1：可测试的画布几何

文件：核心包 Sources/PhotoWorkflowCore/ViewportTransform.swift；Tests/PhotoWorkflowCoreTests/ViewportTests.swift。

Interfaces：初始化 image/viewport/backingScale；scale、offset、isFitted、pixelScale、imageRect 只读；fit、actualSize、zoom(factor:anchor:)、scroll(pixels:anchor:)、pan(by:)、resize(to:backingScale:)；画布/偏移采用 CGPoint/CGSize。

- [x] 写 API 空实现与失败测试：fit 横竖小图；非中心锚点误差≤2显示像素；letterbox；连续输入及上下限；拖动限边；Retina100%；resize 保留 fit 或实际比例；零尺寸安全。
- [x] `swift test --package-path macos/Packages/PhotoWorkflowCore`，预期断言失败。
- [x] 实现几何，缩放使用较宽可见边限制（48 points），拖动使用普通边界。
- [x] 同命令通过并提交。

### Task 2：原生画布与工具栏

文件：Features/Viewer/{PhotoViewer,ViewerCanvas,ViewerImage}.swift；UITests/SourceUITests.swift；docs/NATIVE_VIEWER_VALIDATION.md。

Interfaces：消费 Task 1 ViewportTransform；ImagePipeline.load 返回只读 JPEG Data；NSView 发事件回调，SwiftUI 持有变换唯一状态。

- [x] 扩展真实来源 UI 测试，先在旧预览断言缩放工具不存在而失败。原有来源测试基线 A 等待 10 秒失败后随后找到 A；将来源完成等待改为 30 秒并 guard，避免超时后继续交互掩盖证据。
- [x] 实现 SwiftUI 工具栏（fit、100%、±、比例、前后张、选择、重试）；按照片隔离加载状态、解码后检查取消。
- [x] 实现 NSViewRepresentable：精确滚轮/普通滚轮换算、拖动、捏合、backing scale 更新。画布有焦点才处理方向键/空格/Esc，不抢按钮；空格不重复。
- [x] 完整 Xcode 测试通过；`./script/build_and_run.sh --verify`；CUA 检查滚轮、拖动、按钮、切图及来源只读哈希；记录本机限制。
- [x] 提交；独立审查整个增量，Important 用 RED→GREEN 修复；记录未完成 P1 能力，不推送或发布。
