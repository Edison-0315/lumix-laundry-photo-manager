# Release 来源目录性能基线

2026-11-05，当前 MacBook Air / 16 GB / macOS 27.2，Release arm64。本轮建立来源浏览的实际运行基线，不代表所有图库规模与系统版本均已验收。

## 夹具与操作

隔离目录 `build/fixtures/FolderPerformanceSource`：Small 下 22 个、Large 下 200 个拍摄文件夹，每个包含一张从既有合成夹具复制的 3600 × 2400 JPEG，共 222 张。来源只读，没有使用用户照片库。

实际 app 读取全部 222 张，进入 Large 的 200 个文件夹网格并滚动至 Shoot129 附近，再进入 Small 的 22 个文件夹并滚动至 Shoot013 附近。页面保持可操作。两种规模是本轮操作矩阵，不将混合采样数字解释成两个规模各自的独立测量。

## Instruments 记录

Time Profiler 通过 PID 附加到已确认路径的 Release app，45 秒采集正常结束。原始 `.trace`、CPU/XML 导出和汇总保留在忽略目录 `build/Performance/`，不提交含本机环境信息的原始记录。

| 项目 | 结果 |
| --- | --- |
| 原始记录 | `FolderBrowsing-20261105.trace` |
| 记录跨度 | 45.876 秒 |
| CPU 统计桶 | 10 ms |
| 加权平均 CPU | 6.39%，Instruments 原始口径 |
| 10 ms 桶峰值 | 250% |
| 95 百分位桶 | 80% |
| Running 样本 | 2733，主线程 2373 |
| 浏览后单次 RSS | 168512 KiB，约 165 MiB |
| 后续空闲单次 ps CPU | 0.0% |

平均值包含交互间隔，峰值来自短统计桶；这些是 CPU 基线，不能用来声称固定帧率或长期没有泄漏。此次没有据此改变现有缓存或目录索引，后续有可复现卡顿再针对热点优化。小屏、完整辅助功能矩阵和更大图库仍未在本轮完成。

## 本轮 Release 运行组件检查

Release 构建成功（`/tmp/lumix-p8-release-build.log`），主程序架构 arm64。为避免重复稳定的导入/成片业务，`macos/Runtime/validate_portable.py` 增加 `--faces-only` 窄范围入口：

```sh
/usr/bin/python3 -I -B macos/Runtime/validate_portable.py \
  build/ReleaseValidation/Build/Products/Release/LaundryPhotoManager.app --faces-only
```

app 复制到临时中文/空格路径后，deep strict 签名验证成功；157 个内嵌 Mach-O 均为 arm64。PATH/PYTHONHOME/PYTHONPATH 指向不存在目录，内置 NumPy 2.5.4、OpenCV 4.13.0、rawpy 0.27.1 和 YuNet/SFace 仍成功载入，对固定公开夹具检测到 1 张脸。使用本地开发签名，尚未公证；完整许可证汇总及最终交付仍留在 P9。
