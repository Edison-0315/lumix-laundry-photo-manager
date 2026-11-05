# Apple Silicon 运行组件

使用 Astral python-build-standalone 的 CPython 3.12.16 / aarch64-apple-darwin 与原版同版本 Pillow 13.0.0、NumPy 2.5.4、OpenCV headless 4.13.0.92、rawpy 0.27.1。来源 URL、版本和 SHA-256 固定于 runtime-lock.json；只接受匹配摘要的下载。

首次从源码构建前运行：

```sh
/usr/bin/python3 -I -B macos/Runtime/prepare_runtime.py
```

模型首次准备：`/usr/bin/python3 -I -B macos/Models/prepare_models.py`。下载摘要与原版清单一致；模型和许可证随 app 打包。

Codex Run 的 build_and_run.sh 会先执行运行时及模型准备步骤。Xcode 资源阶段将生成的 Python/ 复制至 app/Contents/Resources/Python，随后对内嵌的 Mach-O 可执行文件、扩展和动态库签名。生成目录和下载缓存不入 Git。运行 app 时不使用 Xcode 的 Python，缺失内置组件时明确报错；单元测试的显式 helperURL 仍允许使用宿主解释器。

运行时使用 -I -B，禁用外部 Python 路径和字节码写入。Pillow 的许可证保留于 dist-info/licenses，CPython 许可证保留于 lib/python3.12/LICENSE.txt。额外原生依赖及实际 wheel/模型许可现已汇总于 macos/ThirdPartyNotices 并随 app 打包，可从帮助菜单打开索引；来源与 SHA-256 见该目录 manifest.json。完整发行前仍需核对所选分发方式的许可义务，完成 Developer ID 签名/公证策略与目标系统验收；当前不发布。

上游：[Astral 下载和运行说明](https://github.com/astral-sh/python-build-standalone/blob/main/docs/running.rst)、[Pillow 13.0.0](https://pypi.org/project/Pillow/13.0.0/)。
