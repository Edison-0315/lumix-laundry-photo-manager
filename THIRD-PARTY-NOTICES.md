# Third-party notices

洗衣机管理器使用Python、pywebview、pythonnet、Pillow、NumPy、OpenCV、rawpy/LibRaw、ExifRead、Send2Trash、pywin32及其依赖。构建时将安装的发行包许可证复制到`licenses/`；完整安装版本记录在`requirements-lock.txt`。

- Python: Python Software Foundation License, https://www.python.org/psf/license/
- pywebview: BSD-3-Clause, https://github.com/r0x0r/pywebview
- pythonnet: MIT, https://github.com/pythonnet/pythonnet
- Pillow: MIT-CMU, https://github.com/python-pillow/Pillow
- NumPy: BSD-3-Clause and bundled library licenses, https://github.com/numpy/numpy
- OpenCV: Apache-2.0 and third-party notices, https://github.com/opencv/opencv
- rawpy: MIT wrapper; LibRaw: LGPL-2.1 or CDDL-1.0, https://github.com/letmaik/rawpy and https://www.libraw.org/download
- ExifRead: BSD-3-Clause, https://github.com/ianare/exif-py
- Send2Trash: BSD-3-Clause, https://github.com/arsenetar/send2trash
- pywin32: Mark Hammond license and included component licenses, https://github.com/mhammond/pywin32
- PyInstaller: GPL-2.0 with bootloader exception allowing distribution of generated applications, https://pyinstaller.org/en/stable/license.html

YuNet/SFace model files come from opencv/opencv_zoo at fixed commit `48b10fa505aeb51fbd127fc60a5c660040e823b7`. Each model's source URL, SHA-256 and adjacent license are included in`models/manifest.json`. YuNet's directory uses MIT; SFace's directory uses Apache-2.0. See the included original license text. Model thresholds are conservative initial engineering settings and imply no guaranteed recognition accuracy.

Microsoft Edge WebView2 Runtime is a system prerequisite and is not redistributed in this bundle. Public portrait photographs used during development are not included in the application or portable bundle.

Interface design references: Emil Kowalski's apple-design guidance (https://github.com/emilkowalski/skills), apple-ui-design (https://github.com/629611312/apple-ui-design), and AppleUI Design Pro's optical-core guidance (https://github.com/JettShyung/AppleUI-Design-Pro). The local SDF/displacement implementation is written for this project; no Apple fonts, logos, private shaders, or platform assets are included. The optical effect is a WebView2 approximation, not Apple's native Liquid Glass renderer.
