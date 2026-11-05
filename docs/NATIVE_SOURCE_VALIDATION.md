# 首个原生来源增量验证

日期：2026-11-03。环境：Apple M2 / arm64，macOS27.2，Xcode27.2，macOS SDK27.2。部署目标14.0；未做macOS14或Intel实机验证。

> 历史首增量记录；当前预览能力与安全读取更新见 [第二增量验收](NATIVE_VIEWER_VALIDATION.md)。

## 交付范围

原生 Xcode 工程、shared scheme、本地 Swift6 核心包、核心/原生UI测试、LLDB启动入口及Codex Run已建立。应用使用SwiftUI的WindowGroup、NavigationSplitView、Inspector、Settings、Commands，照片点击和右键由窄AppKit桥接处理。应用链接系统框架，无Python/Node/WebView运行依赖。

已实现：

- 原生选目录；读取JPEG/RAW/XMP，区分读取格式，明确兄弟格式目录配对，歧义不合并。
- 扫描/预览只读，逐条错误报告、取消与旧快照保留；来源目录、日期、格式和只看已选筛选。
- 真实JPEG缩略图与EXIF方向处理、拍摄本地日期、相机/镜头基础信息、文件位置；无法解码时保留记录。
- 主区叠加选择、Shift范围、可见范围全选、右键选择规则、双击保留选择；冻结预览序列、前后张、预览选择、适应窗口显示。
- 旧版Python tuple-list导入signature编码的固定样例；edited和主成片独立谓词。

这不是完整P1或Windows替代版。尚未实现/验收：框选与边缘滚动、精确锚点缩放/拖动/100%、来源文件夹卡片与返回历史、完整EXIF参数和大规模性能、全部无障碍细节、真实RW2解码。库、活动、人物、导入/写事务、成片、删除恢复、人脸识别仍按P2–P9继续。跨端黄金库夹具和正式迁移协议也未完成，不宣称P0所有兼容准备已结束。

## 测试证据

核心命令：

```sh
swift test --package-path macos/Packages/PhotoWorkflowCore
```

当前14项XCTest通过。测试先运行API占位实现得到失败，再实现通过；审查修复均补充RED→GREEN用例。原生测试命令：

```sh
xcodebuild -project macos/LaundryPhotoManager.xcodeproj \
  -scheme LaundryPhotoManager -destination 'platform=macOS,arch=arm64' \
  -derivedDataPath build test CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES
```

实测完整Xcode套件：14项核心 + 2项XCUITest通过，0失败、0跳过。原生UI覆盖空状态/设置菜单，以及系统选择目录→真实扫描→只看已选→双击打开预览并保留选择。系统选择器在另一服务异步导航，测试确认完整路径并等待目标目录内容出现后才读取；不能用“按过Return”作为选对目录的证据。若其他环境无法提交GoTo路径，该端到端测试会显式报告setup skip，不能算通过；本机最终运行没有触发该分支。

提交后最终复核的xcresult为`build/Logs/Test/Test-LaundryPhotoManager-2026.11.03_14-47-03-+0800.xcresult`；xcresulttool返回Passed、passedTests16、failedTests0、skippedTests0。

测试scheme的PreAction在`build/fixtures/UITestSource`生成专属合成JPEG/假RAW/XMP样例。假RAW只验证配对，不能作为RW2成功解码证据。应用始终经真实NSOpenPanel选择该夹具，未增加绕过目录选择的产品测试后门。

核心夹具扫描及预览前后比较全部文件名与SHA-256；JPEG转向100×50→40×80通过。原生CUA另确认了实际来源目录、两张照片、配对资产及相机日期详情，并复现了仅看已选双击问题。自建来源不含用户照片。

## 独立审查与修复

独立只读审查发现两项Important，无Critical、无Minor：

1. 整个目录路径case-fold误合并大小写敏感卷上的不同拍摄目录。已改为保留目录路径身份，stem仍做不区分大小写的配对；新增独立目录回归。
2. 扫描后路径被替换成符号链接，元数据/预览可能读取来源外内容。已统一安全打开：逐级openat + O_NOFOLLOW、验证普通文件、持有描述符，并通过pread数据提供器交给ImageIO；扫描初读也使用相同入口。覆盖文件、父目录及枚举后替换三类回归。

审查者还指出只看已选可能吞掉双击，随后CUA实际复现并修复：选择即时变化，过滤移除延后至系统双击间隔结束；第二次点击可恢复原集合并打开冻结序列。核心和原生UI均覆盖该规则。

## 本地构建与边界

`./script/build_and_run.sh --verify`为统一构建/启动/进程确认；支持`--debug`、`--logs`、`--telemetry`。本地ad hoc开发签名，未进行发布签名或公证。

最终运行该入口后构建与进程启动确认通过，`codesign --verify --deep --strict`通过；CUA直接确认原生窗口、两张合成JPEG缩略图、A照片JPEG/RAW/XMP配对及日期/相机详情。此次读取/预览前后再次比较合成来源的完整目录树与全部文件SHA-256，均未变化。界面当前显示的是明确的合成测试夹具，不是用户照片或真实RW2解码证据。

保留独立本地分支`feature/native-p1`，不合并、不推送、不发布。Windows参考副本的72项应用/构建源码摘要保持一致，未打开或写入真实旧照片库。

按阶段暂不判断的范围与代价：精确缩放/框选未交付，当前不能完全替代原选片交互；没有真RW2样本，不能承诺对应相机支持；P2–P9尚未实施，当前不能管理或写回Windows库；没有macOS14/Intel实机，只承诺本机验证范围。后续仍先补齐P1，再进入只读旧库兼容。
