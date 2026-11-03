# LUMIX 洗衣机管理器 · v0.12.1 正式版

面向摄影师的 Windows 11 本机照片分类与修图管理工具。先在 SD 卡选片，再按活动、人物和修图阶段整理照片，关联 JPEG、RAW 与成片。

**[下载 Windows 正式版](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/download/v0.12.1/LUMIX-Photo-Manager-Windows-0.12.1.zip)** · **[全部版本](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases)** · **[完整使用说明](docs/使用说明.md)**

## 更新宣传片

[![0.12.1 更新宣传片](docs/media/update-0.12.1-preview.gif)](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/download/v0.12.1/LUMIX-Update-0.12.1-1080p60.mp4)

[观看或下载完整宣传片（90.35 秒，1080p60，无音乐、无旁白）](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/download/v0.12.1/LUMIX-Update-0.12.1-1080p60.mp4)。展示真实 Windows 应用的导航、预览、窗口与文件夹动效、缩略图修复和模块架构。保留旋转融合片头并加入“更新”，片尾附 Edison-0315 与 GitHub。

## 本次更新

- **缩略图调整更自然：** 文件夹封面保持 4:3，卡片宽度跟随 80–720 滑杆，长名称两行显示；连续输入按显示帧合并，减少重复样式计算。
- **累计交互与动效升级：** 收录 0.8–0.12 的深色玻璃、连续导航、指向缩放预览、窗口与弹窗开合，以及文件夹进入和返回转场。快速反向操作和减少动态均有对应处理。
- **模块架构整理：** 前端拆分为组合入口、功能控制器和共享基础；后端按来源、导入、人物、成片、回收站、活动和照片读取组织服务。复用统一照片库、锁和文件日志，保留 .片集 格式与已有桥接接口。

[详细更新日志与架构说明](docs/发布说明-0.12.1.md) · [代码地图](docs/代码地图.md)

## 使用

1. 下载 Windows ZIP，完整解压后运行“洗衣机管理器.exe”。无需 Python，需要 Microsoft Edge WebView2 Runtime。
2. 新建或打开照片库，建立活动；在“选片”读取 SD 卡或来源文件夹，导入所选照片。
3. 使用本机人脸分组整理人物，检查“待分类”，通过自定义路径关联本地 Photoshop。
4. 按“选出原片 → 已修原片 → 成片”管理进度，随后自行通过微信等工具分享。

侧栏单击进入；主区单击选择或取消、可多选，双击进入或预览。预览中滚轮围绕鼠标缩放，左右键切图，空格切换选择。现有照片库继续使用；换版本前关闭旧程序。

SD 来源只读，导入只复制。正常使用不上传照片。照片删除先进入应用回收站；永久删除另行确认。整库删除输入库名确认后交 Windows 系统回收站处理。

## 下载与校验

发布页包含 Windows 便携包、对应源码包、宣传片 MP4、可编辑宣传片工程和 SHA-256 校验文件。此次保留之前验证的 0.12.1 程序包与源码包内容，未重新构建 Windows 程序，未包含 macOS 开发内容。

## 版本下载

0.1–0.5 使用原名称“片集”，0.6 起更名“洗衣机管理器”。每个发布页保留对应 Windows 程序包、源码包和 SHA-256 校验值。

| 版本 | 主要更新 | 发布页 |
|---|---|---|
| **0.12.1 正式版** | 缩略图比例与连续调整修复；累计玻璃动效升级；前后端模块化。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.12.1) |
| 0.1 | 首个 Windows 便携版：选片、导入、本机人脸分组、Photoshop 关联和原片归档。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.1.0) |
| 0.2 | 优化选片取消、批量选择和缩略图；补全文件夹浏览、成片标记及导入流程。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.2.0) |
| 0.3 | 支持 JPEG/RAW 分目录读取，增加照片库管理和照片删除入口。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.3.0) |
| 0.4 | 隔离不可读 SD 条目，补全活动创建、人物管理与人物文件夹浏览。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.4.0) |
| 0.5 | 完善回收站永久删除、多选、侧栏导航、人物文件夹示例与返回功能。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.5.0) |
| 0.6 | 更新洗衣机管理器品牌、活动删除、导入活动选择、照片参数与格式徽标。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.6.0) |
| 0.7 | 清理托管空目录，支持照片库回收删除，更新圆角与磨砂界面。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.7.0) |

## 源码开发

Python 3.12 x64；安装 requirements-dev.txt 后运行 python run.py。重新打包前用 python packaging/fetch_models.py 下载并校验模型。运行测试使用 python -m pytest，Windows 打包脚本为 packaging/build.ps1。

第三方依赖与模型许可见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) 和 licenses/。旧宣传片素材来源见 docs/media/materials.md；更新宣传片素材与许可见发布附件的可编辑工程。

由 Edison-0315 制作。LUMIX 字标用于本项目的个人设计展示，本项目与 Panasonic / LUMIX 无官方隶属关系。
