# LUMIX macOS 照片管理器

面向 Apple Silicon（M 系列）的 macOS 独立版。SwiftUI/AppKit 提供原生界面、动画和系统集成，应用内嵌 Python、图像依赖及 YuNet/SFace 模型，运行时无需另装 Python。当前提供本机预览版，按用户要求以核心功能可用为目标收尾，后续优先修复影响使用的问题。

## 使用

本机运行包、使用步骤及限制见 [预览版说明](docs/LOCAL_PREVIEW.md)；最近一次产物与验证见 [打包记录](docs/NATIVE_PACKAGING_VALIDATION.md)。当前为 0.1.2 (3)，本地 ad hoc 签名、未公证。

macOS 源码与 Windows 版共用 GitHub 仓库，在 [codex/macos 分支](https://github.com/Edison-0315/lumix-laundry-photo-manager/tree/codex/macos) 单独维护；Windows 的 `main` 分支及原有版本保持独立。

已接入来源只读扫描、JPEG/RAW/XMP 配对、筛选、跨目录选片、拖动框选及边缘滚动、缩略图/EXIF/大图；本机库新建/打开/最近记录、活动与复制导入、去重补齐、人物人工及自动整理、已修标记、成片版本/封面/解除、缺失文件找回、撤销归档、应用回收站和整库系统废纸篓。支持深/浅/系统外观、键盘选片和版本门控的原生玻璃材质。

来源与 `Reference/Windows` 只读。现阶段不开发 Windows 数据互通、旧库转换或双向写回；已有旧库只读浏览可保留。真实 DC-S5M2 RW2 已验证一张，其他相机和样本不据此宣称支持。

完整辅助审计、物理外置介质、更多复杂人脸/RAW、Photoshop 实际打开以及其他目标系统未做完整验证，按当前范围暂缓。正式分发的许可义务、签名和公证流程另行处理；这些专项不作为本轮本机使用的交付门槛，也不宣称已通过。

## 开发

打开 `macos/LaundryPhotoManager.xcodeproj`，选择 `LaundryPhotoManager` / My Mac。Debug、Release 固定 arm64，最低构建目标 macOS 14；当前实机验证 macOS 27.2。

首次准备运行组件：

```sh
/usr/bin/python3 -I -B macos/Runtime/prepare_runtime.py
/usr/bin/python3 -I -B macos/Models/prepare_models.py
```

日常构建运行：`./script/build_and_run.sh`。生成本机 Release app/zip：`/usr/bin/python3 -I -B macos/Packaging/package_local.py`。模型和运行时按固定摘要下载，源码构建首次需要网络；已生成 app 使用内嵌组件。

主要记录：

- [架构](docs/NATIVE_ARCHITECTURE.md)、[实施计划](docs/IMPLEMENTATION_PLAN.md)、[进度交接](docs/DEVELOPMENT_HANDOFF.md)
- [Windows 源码基线](docs/source-baseline.json)、[适配业务来源](macos/Backend/PROVENANCE.json)
- [来源交互](docs/NATIVE_INTERACTION_VALIDATION.md)、[导入整理](docs/NATIVE_IMPORT_VALIDATION.md)、[成片](docs/NATIVE_EXPORT_VALIDATION.md)
- [应用回收站](docs/NATIVE_TRASH_VALIDATION.md)、[整库回收](docs/NATIVE_LIBRARY_RECYCLE_VALIDATION.md)、[卷身份](docs/NATIVE_VOLUME_VALIDATION.md)
- [人物分类](docs/NATIVE_FACES_VALIDATION.md)、[外观](docs/NATIVE_APPEARANCE_VALIDATION.md)、[键盘](docs/NATIVE_KEYBOARD_VALIDATION.md)、[性能](docs/NATIVE_PERFORMANCE_VALIDATION.md)
- [第三方声明](macos/ThirdPartyNotices/README.txt)，也可从 app 帮助菜单打开

仅检查新增或受改动影响的部分，不重复已通过且未受影响的套件。不运行 Windows 项目的破坏性自测。
