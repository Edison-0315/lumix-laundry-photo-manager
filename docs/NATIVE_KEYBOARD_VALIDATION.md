# 照片卡片键盘增量

2026-11-05，P8。来源与照片库共用的原生点击视图现在可取得键盘焦点：空格切换选中，Return 或数字键盘 Enter 打开预览；空格自动重复不会连续切换，带 Command/Control/Option 的事件交回响应链。卡片使用 AppKit 焦点环，键盘焦点与选中勾选分别表达。

照片库打开预览区分真实双击与普通打开。只有双击恢复首次点击之前的选择；键盘和菜单打开保留当前选择，避免空格刚选中的照片在打开时被撤回。既有鼠标单击叠加规则不变。

新增 `testPhotoCardKeyboardToggleAndOpenPreserveSelection` 先因空格未取消选择而失败，实装后通过。实际界面检查了来源与本机库的空格取消/选中、Return 打开及选中状态保留，同时覆盖受影响的库双击行为。结果：`build/Logs/Test/Test-LaundryPhotoManager-2026.11.05_09-34-58-+0800.xcresult`，1 项通过、0 失败、0 跳过；没有重跑无关文件事务或完整业务套件。

测试仅使用已有隔离夹具，不写用户原片。网格方向键步进尚未增加；完整 Tab/VoiceOver、系统辅助设置切换与性能矩阵仍待后续验收。

焦点环接口参考：[AppKit focusRingMaskBounds](https://developer.apple.com/documentation/appkit/nsview/focusringmaskbounds) 与 [drawFocusRingMask](https://developer.apple.com/documentation/appkit/nsview/drawfocusringmask())。

后续补齐文件夹原生焦点环、来源/库卡片“预览照片”辅助动作及图片朗读标签；新增紧凑窗口与有限自定义控件审计通过，来源辅助动作实测打开预览并保持选片。完整 VoiceOver/Tab 仍未验收，见 `NATIVE_ACCESSIBILITY_VALIDATION.md`。
