第三方软件许可 / Third-party notices

本应用在本机使用下列开源组件。完整许可文本位于相邻目录；manifest.json 记录版本、原始文件位置和 SHA-256。源码构建清单另见 Resources/Python/.lumix-runtime-lock.json 与 Resources/Models/manifest.json。

CPython 3.12.16：Python Software Foundation / CNRI 许可及其原生组件许可。
发行来源：https://github.com/astral-sh/python-build-standalone/releases/tag/20261026
CPython/ 内文本取自相同版本、平台及构建类型的完整发行包，补齐 install_only_stripped 包省略的原生依赖许可。所需许可路径来自该包的 PYTHON.json。
上游归档说明：https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst

Pillow 13.0.0、NumPy 2.5.4、OpenCV headless 4.13.0.92、rawpy 0.27.1，以及运行时自带的 pip 26.2.2：PythonPackages/ 保留各实际安装包的许可、第三方许可和作者声明，包括 rawpy 使用的 LibRaw LGPL 2.1 文本。以上均为未修改的上游二进制包；来源及摘要固定于运行时清单。
源码与构建信息：
https://github.com/python-pillow/Pillow/tree/13.0.0
https://github.com/numpy/numpy/tree/v2.5.4
https://github.com/opencv/opencv-python/tree/4.13.0.92
https://github.com/letmaik/rawpy/tree/v0.27.1
https://github.com/LibRaw/LibRaw
https://github.com/pypa/pip/tree/26.2.2

YuNet / SFace：Models/ 保留模型原始 MIT / Apache 2.0 许可。模型固定于 opencv_zoo 提交 48b10fa505aeb51fbd127fc60a5c660040e823b7。
https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7

本文件是组件索引，具体权利、条件和免责声明以各原文为准。当前应用是本地开发构建，尚未公证或对外发行；正式分发前仍须核对所选分发方式的源码提供及重新链接等义务。
