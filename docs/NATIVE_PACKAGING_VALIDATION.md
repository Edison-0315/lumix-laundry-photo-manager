# 本机运行包验证

2026-11-05，P9 本地交付增量；仅 arm64，不推送、上传或公证。

## 产物

`build/LocalPackages/20261105-183441/`：

- `LUMIX 洗衣机管理器.app`：0.1.0 (1)，Xcode Release，本地 ad hoc 签名。
- `LUMIX-macOS-arm64-local.zip`：SHA-256 `72b4fa71ad1f6fa697e15b2d931b6ae761df10fc44d7d2476c301a98f18d333e`。
- `使用说明.md`、`package.json`：功能、使用步骤、限制及本次构建来源。当前包是在相关源码提交前生成，package.json 明确标记 source_dirty=true，不冒充干净提交构建。

重复构建命令：`/usr/bin/python3 -I -B macos/Packaging/package_local.py`。已有正确 Release 构建时可用 `--skip-build`；该模式仍核对资源、版本锁、签名和许可摘要，不重新执行既有业务套件。每次生成独立的时间戳目录，不覆盖旧包。

## 新增检查

- 实际 app 中所有 158 个 Mach-O（含主程序、解释器、扩展和动态库）均为 arm64。
- 动态加载引用未发现宿主绝对路径；仅系统绝对路径和相对/rpath 引用。otool -L 同时列出库自身的 LC_ID_DYLIB，检查时根据 otool -D 排除该标识；OpenCV /DLC 的自身标识不是运行时外部加载依赖，未改动已验证的上游二进制。
- app 的 Backend、Models、ThirdPartyNotices 与当前源资源摘要一致；模型和运行时版本锁与许可清单一致。
- 60 份许可/声明文本随 app 打包，摘要逐项吻合。CPython 原生依赖许可按同版本同平台 pgo+lto 完整包 PYTHON.json 选取；完整包下载 SHA 固定于 ThirdPartyNotices/manifest.json。其余文本来自实际内嵌 wheel 和模型目录，包含 pip 的 vendored 声明及 LibRaw LGPL 文本。
- 原始 Release、复制后的中文路径 app、zip 解压后的 app 均通过 codesign --verify --deep --strict。
- 实际从中文路径运行包启动，主窗口可用；帮助 → 第三方许可成功在系统文本编辑器打开包内 README.txt。未重跑既有模型推理、来源和业务套件；运行时未变，沿用 NATIVE_PERFORMANCE_VALIDATION.md 已有搬移/隔离宿主 Python 的证据。

上游说明明确 install-only 会省略 PYTHON.json 及安装树之外文件，因此本次另取固定完整包的许可，不将 CPython 自身 LICENSE 当作所有原生依赖的许可替代：[归档说明](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst)。

## 尚未宣称通过

当前是本机预览版，不是公证发行版；其他 macOS 实机、完整辅助功能、物理外置介质、更多 RAW/人脸样本及 Photoshop 实际打开仍待验收。正式分发前仍须核对所选分发方式的源码提供/重新链接等许可义务与签名策略。生成本地 app/zip 不构成发布，也不表示全部 P0–P9 已完成。

## 0.1.1 (2) 更新

当前包：`build/LocalPackages/20261105-192523/`，替代早先预览。zip SHA-256：`e55b5eb34f577ee397609be0f7aaf0a21987d3f29d95eaf7c15bb752fa9696f8`。包含系统工具栏高 CPU 规避、命名辅助预览、图片标签和文件夹焦点环；测试尺寸配置仅 Debug 启用，不进入 Release。

Xcode Release 构建、本机打包脚本的资源/许可摘要、158 个 arm64 二进制及 zip 往返签名检查通过。最终 app 实际启动、来源辅助预览与图片 AX 标签检查通过；空闲约两分钟 ps 为 0.0% CPU。业务、模型和文件事务未改变，未重复这些套件。package.json 继续如实标记打包时 source_dirty=true；正式分发与其余验收限制仍保留。

## 0.1.2 (3) 更新

当前包：`build/LocalPackages/20261105-203330/`。zip SHA-256：`c8a7004ee7015a3dffeb074e030228b01d0ec7644c54b58e6d4c2d87aa038aa5`。

包含新库初始化排他发布、空目录隔离清理和清理失败路径报告；详情见 NATIVE_INITIALIZATION_CLEANUP_VALIDATION.md。Debug/Release 构建、后台资源摘要、包内架构/许可及 zip 往返签名检查通过。没有重复不受影响的界面、导航、模型或性能套件；本版未重新进行 GUI 启动验收。打包时 source_dirty=true 仍如实记录，未公证、未发布，其余阶段剩余范围不变。
