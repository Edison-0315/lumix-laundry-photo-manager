# 来源目录导航与 Apple Silicon 验收

2026-11-03；本轮基线043a200，保留本地 feature/native-p1，不改 Windows 参考、旧库或用户照片。

## 支持范围

按用户明确要求，仅面向 Apple Silicon（M系列）：Xcode Debug/Release 与测试目标均固定 ARCHS=arm64，不安排 Intel/Universal 构建。最低部署仍为macOS14，实际运行验收为M2/macOS27.2/Xcode27.2；低版本系统实机未验收。

## 已交付行为

- 来源根与每个目录只显示直接子文件夹和直接归属照片；全部子文件夹是独立虚拟位置。JPEG/RAW兄弟目录中的同一照片组在两边都可见。
- 原生侧栏单击进入；主区文件夹单击独立多选、双击恢复点击前选择后进入、Return进入。文件夹选择按位置存储，与照片选片集合独立；来源切换保留照片选择。
- 结构卡片不会因日期/格式筛选消失，封面最多3张，按日期/格式选示例；只看已选分别过滤文件夹和照片。Cmd+A仅选当前显示项目，保留隐藏范围选择。
- 面包屑、后退/前进、上级目录；历史最多80项，保存位置/日期/格式，重复状态不追加，回退后新导航清除前进。新目录重置日期/只看已选、保留格式。前进与Cmd+]为原生版新增交互。
- Cmd+[后退、Cmd+]前进、Cmd+Up上级；预览/读取问题sheet/扫描期间禁用导航。新扫描只在成功发布时清空历史、文件夹选择与照片选择；取消/失败保留旧会话。
- 目录只从已接受的扫描成员构建内存索引，没有新增文件系统遍历或写入口。真实名为星号的目录与虚拟全部视图使用不同枚举身份。

## 自动测试与实机证据

核心新增7项：直接孩子与直属照片、大小写/Unicode/真实星号、兄弟配对两侧、外部根路径排除、路线筛选恢复/重复/分叉、80项上限/重置、独立scope及双击筛选延迟、可见全选保留隐藏选择。

Xcode `19-31-59`完整结果：**37通过、0失败、0跳过**（31核心XCTest、3AppKit组件、3XCUITest）。界面场景通过真实系统目录选择，验证根→JPEG、独立文件夹双击、照片选择保留、日期恢复、工具栏返回/前进、Return、原生命令菜单、预览禁用、新扫描重置。SwiftPM单独运行31项核心也通过。

XCTest在本机合成标点Cmd+[时没有激活快捷键；没有据此改写产品键盘处理。CUA用真实鼠标获取Other卡片焦点→Return进入→Cmd+[，确认回到来源根。自动化走相同原生命令菜单，真实快捷键单独记录。日期/格式选择器已补明确的可访问性标签和ID。

Xcode同步NSOpenPanel的main-thread warning仍可见；不声称零运行警告。

## 构建与完整性

```sh
swift test --package-path macos/Packages/PhotoWorkflowCore
xcodebuild -quiet -project macos/LaundryPhotoManager.xcodeproj -scheme LaundryPhotoManager -destination 'platform=macOS,arch=arm64' -derivedDataPath build test CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES
xcodebuild -quiet -project macos/LaundryPhotoManager.xcodeproj -scheme LaundryPhotoManager -configuration Release -destination 'generic/platform=macOS' -derivedDataPath build/ReleaseValidation build CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES
```

Debug/Release最终架构、签名、审查结果在下方补记。两套自建合成来源共8个文件，全列表和SHA-256在读取/导航测试前后完全一致；Windows72源文件哈希一致，参考检出无改动。

## 分阶段边界

目录切换从网格顶部显示，后退尚不恢复先前滚动位置；没有弹簧/来源转场。框选、边缘滚动、真实RW2、完整EXIF和大规模性能仍留P1/P8继续。预览仍为最长边4096的解码图；跨端黄金库、旧库只读兼容与P2–P9尚未完成，不宣称Windows功能对等。实体捏合/跨屏、完整无障碍和低系统版本仍需另验；Intel已按用户要求移出范围。

Debug与Release的主可执行文件经 `lipo -archs` 实测均仅为 `arm64`；Release `codesign --verify --deep --strict`通过。Release应用位于 `build/ReleaseValidation/Build/Products/Release/LaundryPhotoManager.app`，属于本地ad hoc签名构建，未发布。

## 独立审查与修复轮

审查发现3项Important、无Critical和独立Minor：

- 以组合字符开头的合法目录名会把斜杠合成同一Swift Character，导致孩子/parent/面包屑跳层。核心改用UTF-8的U+002F解析路径组件；直属与后代比较均按组件进行，卡片名称共用同一解析规则。组合字符回归在修复前6项断言失败。
- 后退/前进没有像参考实现一样清除onlySelected，可能把返回目录隐藏。现在恢复route时清除此筛选，保留照片和文件夹的选择集合。
- 双击照片取消共享延迟任务后，FolderChoices的筛选快照未释放。现在在恢复双击前照片选择之前统一结束两类延迟状态，避免未选文件夹持续可见或被Cmd+A重新选中。

原生集成测试直接编译生产AppModel/SourcePanel，使用临时自建RAW配对字节夹具，不把它当作真实RAW解码证据。修复前两个AppModel回归失败，扫描失败保留/成功重置的对照测试通过。修复用RED→GREEN验证，不另派复审。

### Unicode身份边界

组合字符路径分隔与普通Unicode目录已覆盖；NFC/NFD字节不同但规范等价的两个目录名的独立身份未获实际卷验收。当前Swift字符串会规范等价比较，在能同时保存这类名字的外部卷上可能合并显示/索引；不能把当前测试称作覆盖所有Unicode文件系统身份。卷身份契约和跨端黄金库仍需在旧库写入前补齐。本版本来源只读。

## 最终修复验收

`Test-LaundryPhotoManager-2026.11.03_19-47-57-+0800.xcresult`：**41通过、0失败、0跳过**（32核心、6原生组件/应用模型、3UI）。SwiftPM32项通过。三个Important均已RED→GREEN；无延期Minor。

CUA最终实际读取组合字符目录 `A/\u{0301}Trip/IMG.JPG`：来源根只出现A，进入A后只出现组合字符子目录，继续进入后显示IMG；面包屑保留A，Cmd+Up/后退/前进均未跳层。另确认真实星号目录只有自己的1张照片，而全部视图为5张。

最终修复后重新构建Debug/Release；两者签名严格验证通过，lipo均仅arm64。原两套8文件、嵌套/星号夹具7文件、组合字符夹具1文件，前后完整列表和SHA-256均未变；Windows72文件哈希与参考检出仍无变化。

最终启动的是 `build/ReleaseValidation/Build/Products/Release/LaundryPhotoManager.app` 的实际Release进程，非Debug替身；CUA再次确认系统选择来源→真实读取组合字符JPEG→正确面包屑/照片显示，读取后夹具全列表与哈希不变。应用保持运行，工作保留本地 `feature/native-p1`，未合并、推送或发布。

## 常用EXIF详情增量

已补快门、光圈、ISO、焦距、曝光补偿、带转向的像素尺寸，按JPEG→RAW→export填补缺失字段，拍摄日期保留当地时间并支持Digitized/TIFF回退。逐文件显示大小和独立读取问题，仅全部大小可读时显示合计；刷新重新读取，切图丢弃旧任务结果。非倒数形式的亚秒曝光使用等值十进制秒显示。

新增3项元数据测试先失败后通过；最终完整Xcode测试44通过、0失败、0跳过。Release重新构建、严格签名验证通过，架构仅arm64。

用户提供的真实DC-S5M2 RW2在本机原生链路成功读取：1/60s、f/4、ISO160、24mm、6000×4000；生成4096×2731预览，文件大小27609600字节。原文件SHA-256/大小/修改时间未变。个人RAW与生成预览仅存放在被忽略的build测试目录，未提交到Git；此证据只覆盖该样本和当前macOS，不代表所有RW2。Windows72文件哈希保持不变。本轮按用户要求简化流程，未增加独立审查和重复计划文档。

## 2026-11-04 轻量界面增量

预览缩放工具条采用macOS26+系统Liquid Glass；旧系统回退regularMaterial，降低透明度时使用实色背景。增加选片状态与详情开合动效，减少动态效果时关闭这些新增动画。未引入其他运行时。

针对预览的现有UI场景1通过、0失败、0跳过（实际缩放、切图、选择保持、损坏图重试）；未重复完整44项测试。结果：`Test-LaundryPhotoManager-2026.11.04_11-42-59-+0800.xcresult`。Release构建与严格签名验证通过，仅arm64；CUA在实际Release中读取合成ViewerSource并打开大图，确认玻璃工具条与画布正常显示。降低透明度/减少动态及旧系统回退仅实现，未切换系统设置实测。原有NSOpenPanel主线程警告仍存在。Windows参考检出无改动。

## 2026-11-04 拖动框选

使用SwiftUI手势从网格空白处框选照片或文件夹，Command/Shift叠加，空白单击清选，Esc恢复拖动前的选择；缩回框时按起始快照重算，“只看已选”在松手前保持布局。仅支持当前可见区域，边缘自动滚动尚未实现。

新增2项模型测试先失败后通过，模型组5项与核心35项通过。实际CUA鼠标分别框选3张照片、4个文件夹成功；现有双击预览场景通过。最终框选UI测试`Test-LaundryPhotoManager-2026.11.04_12-06-47-+0800.xcresult`为1通过、0失败、0跳过，覆盖照片、空白清选、文件夹。自动化曾使用触摸接口及失效坐标，已改为SDK的macOS鼠标拖动接口并重新获取坐标；早期AppKit框选尝试已移除。Release已构建并严格验签，仅arm64；Windows参考未修改。未重复完整测试套件，边缘滚动与界面Esc/修饰键组合另待自动化覆盖。
