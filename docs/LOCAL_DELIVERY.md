# macOS 本机版收尾

日期：2026-11-05。按用户最新要求，macOS 为次要开发版，以核心功能可用、基本检查通过为交付标准；复杂联动和完整专项验收暂缓。此记录核对当前实现和已有验证，不重复执行未受影响的测试。

## 核心功能核对

对照只读参考 `Reference/Windows/README.md`、`pianji/bridge.py` 及本机实现：

| 工作流 | 当前实现 | 已有验证记录 |
|---|---|---|
| 来源读取、JPEG/RAW/XMP 配对、日期/格式筛选 | `App/AppModel.swift`、核心包扫描与配对 | NATIVE_SOURCE_NAVIGATION_VALIDATION、NATIVE_SOURCE_VALIDATION |
| 文件夹浏览、缩略图调整、跨目录选择、拖动多选/边缘滚动 | Sources、Culling；独立照片/文件夹选择 | NATIVE_INTERACTION_VALIDATION |
| 详情、EXIF、大图、指向缩放/拖动、切图及键盘选择 | Inspector、Viewer | NATIVE_VIEWER_VALIDATION、NATIVE_KEYBOARD_VALIDATION |
| 新建/打开/关闭/最近照片库、活动 | LibraryModel、RecentLibraries、后台 managed | NATIVE_BACKEND_VALIDATION、NATIVE_IMPORT_VALIDATION |
| 所选照片/文件夹复制导入、去重及格式补齐 | SourceImportSheet、后台 import | NATIVE_IMPORT_VALIDATION |
| 人物创建、归属、重命名、合并及已修标记 | 人物表单、LibraryModel、后台 people/stages | NATIVE_IMPORT_VALIDATION |
| 本机自动人物整理、进度、取消和报告 | 后台 YuNet/SFace、WorkReport | NATIVE_FACES_VALIDATION |
| 成片版本/封面/解除保留、缺失找回、撤销归档 | ExportSheet、LibraryModel、后台 exports | NATIVE_EXPORT_VALIDATION |
| Finder 定位和配置 Photoshop.app 打开 | Platform/ExternalEditor；不自动标已修 | NATIVE_EXPORT_VALIDATION；Photoshop 实际安装联动未验 |
| 照片/人物/活动回收、恢复、永久删除及中断重试 | LibraryDeletion、后台 trash/permanent | NATIVE_TRASH_VALIDATION |
| 整库名称确认后交系统废纸篓 | LibraryRecycleSheet、LibraryRecycler | NATIVE_LIBRARY_RECYCLE_VALIDATION（含 GUI 补验） |
| SwiftUI 界面、动画、原生玻璃、深浅外观 | App 场景与 Features；macOS 26+ glassEffect、旧系统材质回退 | NATIVE_APPEARANCE_VALIDATION、NATIVE_ACCESSIBILITY_VALIDATION |
| Xcode Debug/Release、仅 arm64、独立运行组件 | xcodeproj、Runtime、Models、Packaging | NATIVE_PACKAGING_VALIDATION |

以上为功能工作流覆盖，不声称每个 Windows 桥接方法都保持相同界面：最近记录目前提供整体清除；空目录随人物/活动删除及永久删除清理，没有独立的手动全库清理按钮。这些便利入口不影响上述核心流程，暂不增加。

## 当前交付与本次基本检查

交付：`build/LocalPackages/20261105-203330/LUMIX 洗衣机管理器.app`，0.1.2 (3)，同目录有 zip、使用说明与 package.json。

- 直接比对交付包中 23 个后台 Python 文件与当前源文件，全部一致；交付主程序与现有 Release 主程序字节一致。当前 `macos/` 和 `script/` 相对 HEAD 无改动。
- 实际执行 `lipo -archs` 为 arm64；`codesign --verify --deep --strict` 成功；zip SHA-256 与 package.json 一致。当前包为 ad hoc 签名，未公证、未发布。
- 读取现存紧凑窗口 xcresult：1 通过、0 失败、0 跳过。读取最近初始化/清理检查日志：24 项 OK。本次没有重跑这些测试。
- 更早功能测试沿用各阶段记录；部分旧 xcresult 已被 Xcode 轮换清理，不宣称本轮重新执行或仍持有所有原始结果。
- `Reference/Windows` 当前 git 状态干净。本次仅更新文档，未操作用户照片或切换系统设置。

## 保留边界

Windows 数据互通、旧库转换和双向写回按用户决定暂缓；已有旧库只读查看保留。Photoshop 实机、更广相机/人脸样本、物理外置介质、其他系统版本、完整辅助功能与正式分发专项均未宣称通过，按最新范围不作为本轮门槛。

本机库暂时绑定创建路径；不要移动整个库后继续写入。已知限制及操作步骤见 LOCAL_PREVIEW.md。后续优先处理实际使用中影响核心功能的问题。
