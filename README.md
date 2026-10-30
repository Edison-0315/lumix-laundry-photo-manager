# LUMIX 洗衣机管理器 0.5

面向摄影师的 Windows 11 本机照片分类与修图管理工具。先在 SD 卡选片，再按活动、人物和修图阶段整理照片，关联 JPEG、RAW 与成片。

**[下载最新版本](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/latest)** · **[全部版本](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases)** · **[完整使用说明](docs/使用说明.md)**

## 功能宣传

[![功能宣传片预览](https://github.com/Edison-0315/lumix-laundry-photo-manager/raw/refs/heads/main/docs/media/preview.gif)](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/download/v0.7.0/LUMIX-Photo-Manager-Promo-1080p60.mp4)

[观看或下载完整宣传片（含片头，43.5 秒，1080p60，无音乐）](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/download/v0.7.0/LUMIX-Photo-Manager-Promo-1080p60.mp4)

## 使用

1. 在 Releases 下载对应版本的 Windows ZIP，完整解压后运行程序。
2. 先建立照片库与活动，在“选片”中选择来源并导入所选照片。
3. 使用本机人脸分组管理人物相册，检查“待分类”；通过自定义路径关联 Photoshop。
4. 按“选出原片 → 已修原片 → 成片”管理进度，再自行通过微信等方式分享。

来源 SD 卡只读，导入复制文件。正常使用不联网、不上传照片。Windows 便携包无需 Python，需要 Microsoft Edge WebView2 Runtime。旧版本界面名称和功能范围以该版本使用说明为准。

## 版本下载

0.1–0.5 使用原名称“片集”，0.6 起更名“洗衣机管理器”。每个发布页保留对应 Windows 程序包、源码包和 SHA-256 校验值。

| 版本 | 主要更新 | 发布页 |
|---|---|---|
| 0.1 | 首个 Windows 便携版：选片、导入、本机人脸分组、Photoshop 关联和原片归档。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.1.0) |
| 0.2 | 优化选片取消、批量选择和缩略图；补全文件夹浏览、成片标记及导入流程。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.2.0) |
| 0.3 | 支持 JPEG/RAW 分目录读取，增加照片库管理和照片删除入口。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.3.0) |
| 0.4 | 隔离不可读 SD 条目，补全活动创建、人物管理与人物文件夹浏览。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.4.0) |
| 0.5 | 完善回收站永久删除、多选、侧栏导航、人物文件夹示例与返回功能。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.5.0) |
| 0.6 | 更新洗衣机管理器品牌、活动删除、导入活动选择、照片参数与格式徽标。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.6.0) |
| 0.7 | 清理托管空目录，支持照片库回收删除，更新圆角与磨砂界面。 | [下载](https://github.com/Edison-0315/lumix-laundry-photo-manager/releases/tag/v0.7.0) |

## 源码开发

Python 3.12 x64；安装 requirements-dev.txt 后运行 python run.py。重新打包前用 python packaging/fetch_models.py 下载并校验模型。运行测试使用 python -m pytest，Windows 打包脚本为 packaging/build.ps1。

第三方依赖与模型许可见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) 和 licenses/。宣传片中公开示例照片的来源见 docs/media/materials.md。

由 Edison-0315 制作。LUMIX 字标用于本项目的个人设计展示，本项目与 Panasonic / LUMIX 无官方隶属关系。
