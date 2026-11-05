# 原生预览第二增量验收记录

2026-11-03。基于 `feature/native-p1`；只读照片预览，不含旧库读写。

## 本次实现

- SwiftUI 负责前后张、选择、适应窗口、100%、缩放按钮和加载/错误/重试状态。
- 局部 AppKit NSView 负责滚轮、捏合、拖动、画布键盘事件和 CGImage 绘制；SwiftUI Binding 是变换状态的唯一来源。
- 纯 Swift ViewportTransform 用图像像素和画布 points 计算变换。比例显示以显示像素计算，100% 是一个解码预览像素对应一个显示像素。
- 最长边仍为 4096 像素的 JPEG 预览，100% 不表示相机原片全分辨率。沿用 ImageIO、JPEG 优先、EXIF 转向和安全文件描述符；没有新增运行时。
- 缩放按钮 ×1.25 / ×0.8；范围 2%–1600%；滚轮按连续目标累计；图外锚点夹至图像边缘并允许留黑以避免跳回中心。拖动使用普通可见边界。
- 切图取消旧读取，每张新图从 fit 开始；读取和错误发布前复查取消状态。冻结照片序列和原有选片状态保持。

## 自动验证

几何 7 项：横/竖/小图 fit、1×/2× backing scale 下非中心锚点误差≤2显示像素、letterbox、连续滚轮及上下限、拖动限边与复位、Retina100%及屏幕密度变化、空画布及无效输入。

新增读取权限回归：已知可读 JPEG 位于只允许搜索（0111）的父目录下时应能解码；保留文件、父目录、枚举后替换为符号链接的全部拒绝用例。使用 libc realpath 构造测试路径，避免 Foundation 将临时路径改写到 /var 链接。

实际测试命令：

```sh
swift test --package-path macos/Packages/PhotoWorkflowCore
xcodebuild -quiet -project macos/LaundryPhotoManager.xcodeproj -scheme LaundryPhotoManager -destination 'platform=macOS,arch=arm64' -derivedDataPath build test CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES
./script/build_and_run.sh --verify
```

完整结果及最终审查结论在下方补记。Xcode 的 NSOpenPanel 同步 runModal 路径仍报告 main-thread warning；界面选择器能完成操作，不能声称零运行警告。

## 人工检查（CUA、本机 Retina）

用 `script/make_viewer_fixture.swift` 生成的横图3600×2400、竖图1600×3200和坏JPEG验证，没有使用个人照片。白色左上标记、黑色右下标记确认方向正确。

- 横图 fit 41%，滚轮向上后61%，100%后滚轮到149%；拖动使棋盘交界按鼠标位移移动。
- 竖图 fit31%，在左侧留黑处滚轮后46%，图像左边保持在同一位置，没有跳回画布中心。
- 画布长按空格后切到竖图、再返回横图，横图仍为“已选中”；切图复位 fit。
- 坏图展示重试入口；重试保留原文件和当前序列。发现错误页方向键失效，追加 UI 回归修复，最终结果另记。

这些检查证明本机事件路由可用；≤2显示像素的数值断言来自几何测试，没有用肉眼截图宣称测得该精度。

## 安全读取修正

基线 Xcode 测试曾在读取父目录的 openat 上阻塞，采样及 lsof 确认来源是合成夹具。逐级 O_RDONLY 额外要求父目录读取权限；0111 夹具复现 EACCES。改为一次 `open(... O_NOFOLLOW_ANY ...)`：内核拒绝整个路径中的链接，随后 fstat 只接受普通文件，并持续持有描述符给 ImageIO。没有退回普通路径重开，也不申请扩大系统权限。该标志见 [Apple XNU 7195 fcntl.h](https://github.com/apple-oss-distributions/xnu/blob/xnu-7195.81.3/bsd/sys/fcntl.h#L165)。

## 尚未验收

- 真 RW2 相机样本、macOS14/Intel实机、跨实体显示器切换；1×/2×密度变换仅核心测试覆盖。
- 实体触控板捏合和按钮获得键盘焦点后的原生空格激活，尚未以硬件/自动化实测；事件处理仅在画布 NSView 内，不设全局空格拦截。
- 原片全分辨率、框选/边缘滚动、弹簧/惯性/来源转场、来源历史、大库性能和完整无障碍细节仍留 P1 后续。
- P0跨端黄金库与 P2–P9 尚未完成；本版本不能替代 Windows 完整工作流。

## 最终补记

- `2026.11.03_15-28-39-+0800.xcresult`：22项核心 XCTest +2项XCUITest，24通过、0失败、0跳过。错误页重试后按 Left 能返回上一张；该回归在修复前15-24-13运行明确失败。
- 画布在加载/错误状态持续存在，读取成功不会重新抢走按钮焦点。迟到图片通过照片生命周期隔离和取消复验丢弃。
- UI来源5文件（原4文件+本轮显式生成的坏JPEG）、人工来源3文件，应用读取前后完整文件列表和SHA-256完全相同；原Windows72文件清单哈希一致。没有读取旧库或个人照片。

## 独立审查与修复

独立审查无 Critical、无 Minor，发现2项 Important，均进入同一修复轮：

1. 切图重建画布时无条件获取 first responder，可能把键盘聚焦的“下一张”按钮后续空格变成选片。现在仅在没有其他响应目标、窗口自身或旧画布响应时获取焦点，保留工具栏已有控制焦点。Xcode 直接编译实际 ViewerCanvas 进行 NSWindow/NSButton 回归；旧实现明确失败，画布原有键盘导航继续通过。
2. 100% 的奇偶尺寸可产生半显示像素原点，导致插值变模糊。纯几何新增奇偶图像、1×/2×密度、拖动、密度切换回归（旧实现10项断言失败）；100%只对齐原点，不改变尺寸/比例。另用实际 NSView 的0.25point位置复现 backing 偏移（旧绘制失败），绘制时使用 backingAlignedRect 的原点再对齐真实 backing store，保留矩形原尺寸。

原首选审查模型因额度未启动，实际审查由替代可用模型独立完成；没有把调用失败算成审查。没有派第二轮复审，修复通过回归及完整套件验证。

后续范围判断保持原计划：真RAW和全分辨率、惯性/转场与框选/来源历史/库功能尚未交付；实体捏合、跨屏、macOS14/Intel及完整无障碍尚未验收。因此当前不能当作完整Windows替代版。

### 本轮最终通过结果

`build/Logs/Test/Test-LaundryPhotoManager-2026.11.03_19-05-22-+0800.xcresult`：**29通过、0失败、0跳过**（24核心 XCTest、3原生AppKit XCTest、2 XCUITest）。SwiftPM 单独运行24核心测试也通过。来源选择先确认解析路径行再提交，避免只确认输入文字；此前一次setup skip与参数错误运行没有被算作通过。

原生组件测试直接复用生产 ViewerCanvas.swift，验证按钮键盘焦点不被新照片抢走、原画布键盘导航能延续、画布处于小数point位置时100%仍对齐实际backing像素且尺寸不变。AppKit的对齐调用按要求指定每轴min和max，实际仅取其原点。

最终修复提交 `a9088df` 后再次运行构建入口成功，进程启动与原生主窗口经CUA确认，`codesign --verify --deep --strict`通过。来源两套夹具的全部文件列表/哈希与读取前一致，Windows72文件清单及参考检出保持不变。工作保留在本地 `feature/native-p1`，没有推送或发布。
