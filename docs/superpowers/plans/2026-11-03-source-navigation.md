# 来源文件夹与历史导航实现计划

> **面向 AI 代理的工作者：** 使用 executing-plans 与 test-driven-development 逐任务实现。现有独立 feature/native-p1 为已授权工作区。

**目标：** 补齐 P1 来源直接子目录卡片、独立文件夹选择、面包屑、返回/前进，保持跨目录照片选择；构建仅面向 M 系列。

**架构：** 核心包提供 SourceLocation（all 与 folder 独立，避免真实星号文件夹冲突）、SourceFolderIndex、SourceNavigation 与 FolderChoices。SwiftUI 负责目录卡片/面包屑/命令；局部 AppKit 仅提供点击次数与 Enter。AppModel 在成功发布扫描后重建目录索引并清历史；取消/失败保留旧快照与导航。

**技术栈：** Swift6、SwiftUI、必要 AppKit、Xcode、macOS14+、arm64。

**规格：** docs/NATIVE_ARCHITECTURE.md；docs/IMPLEMENTATION_PLAN.md P1；/Users/edison/Downloads/MACOS_MIGRATION.md §2.2；参考 navigation.js、choice-list.js、core/queries.js、features/sidebar.js。

## 全局约束

- 用户要求仅 M 系列：所有 Debug/Release 设 ARCHS=arm64，不构建/验收 Intel；最低 macOS14 不变。
- 来源只读，不修改 Reference/Windows、旧库或用户照片；测试仅合成夹具。
- 侧栏单击导航，主区文件夹单击独立多选、双击恢复首次点击前集合并进入、Enter进入；Cmd+A同时覆盖当前可见文件夹和照片，保留不可见选择。
- 进入不同位置重置日期与只看已选，保留格式和照片选择；后退/前进恢复 location/date/format，不改变选片。历史最多80项；后退后新导航清前进；成功新扫描清历史与文件夹选择；失败/取消不清。
- 目录结构只来自已有已扫描照片成员路径，不增加文件系统遍历。只显示直接孩子；目录卡片结构不因日期/格式消失，示例图应用日期/格式，onlySelected应用独立文件夹选择。
- 前进是 macOS 新增交互；返回采用Cmd+[，前进Cmd+]，上级Cmd+Up。历史不保存滚动位置，本增量明确记录此限制，不称P1全部完成。

## 审查重点（Review Focus）

- 星号真实目录、同名不同父级、大小写、Unicode不能混成同一位置；核心测试。
- 配对照片的JPEG/RAW位于不同兄弟目录时，两处都能直接看到同一照片组；后代照片不能泄入父级直接视图；核心测试。
- 回退后改日期/格式清前进，重复位置不增长历史，80项后仍能正确回退；核心测试。
- 仅看已选时文件夹双击不能先消失；独立scope不覆盖照片选择；核心与UI测试。
- 预览/问题sheet/扫描进行时禁用导航快捷键；新扫描不能回到旧路径；UI及核心测试。

### Task 1：目录与导航状态核心

文件：核心包 Sources/PhotoWorkflowCore/{SourceNavigation,SourceFolderIndex,FolderChoices}.swift；Tests/PhotoWorkflowCoreTests/NavigationTests.swift；Xcode工程/AGENTS/架构文档。

Interfaces：SourceLocation enum(all,folder(String))；SourceRoute(location,date,format)；SourceNavigation.route/back/forward/canGoBack/canGoForward/navigate/reset；SourceFolderIndex(paths,directories(for:),children(of:),contains(photo:in:),descends(photo:from:))；FolderChoices.selected/filtered/click/doubleClick/finishFiltering/selectVisible/deselectVisible/reset。

- [x] 空实现+失败测试：直接子目录、case/Unicode/star区分、兄弟配对两侧、外部路径排除、路线与日期/格式恢复、重复/分叉/80项/重置、独立scope与双击筛选延迟。
- [x] `swift test --package-path macos/Packages/PhotoWorkflowCore` 预期断言失败。
- [x] 实现以上值状态；Xcode Debug/Release ARCHS=arm64，更新支持范围；同测试全通过并提交。

### Task 2：原生浏览与命令

文件：App/AppModel.swift、LaundryPhotoManagerApp.swift、Features/Sources/{SourceWorkspace,SourceBreadcrumbs,SourceFolderCard}.swift、Features/Culling/PhotoGrid.swift、UITests/SourceUITests.swift、验证记录。

Interfaces：消费Task1路线/索引/独立文件夹集合；AppModel保持唯一导航状态；新扫描只在publish成功时重置。

- [x] 扩展真实来源UI用例：root→卡片双击JPEG→back→forward→parent，选择保留、筛选恢复、Cmd+A仅当前可见、folder双击恢复、预览禁用导航。旧界面应在新入口断言失败。
- [x] 接入卡片、面包屑和导航工具栏/菜单；只有来源根下已知路径可进入；忙/模态禁用；照片过滤不包含后代。
- [x] 完整 Xcode 测试通过；Debug运行、Release构建、lipo确认均仅arm64；CUA验证路径导航/选择，夹具与Windows72哈希不变。
- [x] 提交；独立审查本增量一次，Important以RED→GREEN修复；记录剩余P1，保留本地分支。
