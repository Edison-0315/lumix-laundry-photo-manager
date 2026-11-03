# 0.12 窗口与文件夹开合 实现计划

> 使用 writing-plans/executing-plans 在 feature/photo-manager 内联执行。用户明确要求窗口打开/关闭、文件夹进入/返回增加动画，沿用using-superpowers、apple-design（主）、apple-ui-design、appleui-design-pro，并参考三份Apple官方资料。

**目标：** 开合有对应的空间关系，可中断，不延迟选择或改变照片管理规则。

**实现选择：** Windows主窗口只调原生Form透明度，不缩放窗口边界或重排照片；使用UI线程计时器，结束时仍执行既有任务/库清理。应用弹窗采用短缩放/淡入且关闭反向，保留HTML dialog和焦点语义。人物及SD文件夹通过View Transitions的一次性快照关联来源卡片与照片区；返回按稳定scope/key定位新生成的卡片，不保留失效DOM。Windows WebView2为目标；缺少API、键盘或减少动态直接切换。

**参考：**
- https://developer.apple.com/cn/videos/play/wwdc2024/10145/：来源身份、缩放过渡、持续交互与中断。
- https://developer.apple.com/design/human-interface-guidelines/motion：简短、有因果、可取消、成对路径。
- https://developer.apple.com/design/human-interface-guidelines/materials：玻璃用于功能层；照片内容不涂玻璃。

## 文件与步骤

- [x] window_motion.py及test_window_motion.py：先验证启动/关闭中间值、启动中关闭、重复关闭清理一次、减少动态立即；app.py绑定原生窗口并实际验证。
- [x] workspace-motion.js及ui_v012.cjs：人物/SD文件夹进入与返回、稳定来源标识、滚动恢复、快速反向、快照不拦截点击、API缺失及减少动态/键盘回退。
- [x] gallery.js传入来源，app.js/navigation.js把返回身份写入历史并在完成读取后提交过渡；chrome-motion.js已有主导航动效保持。
- [x] dialogs.js/glass.css：弹窗来源位置、较清楚的轻缩放与对称关闭；逐帧检查关闭及快速重开，不改变焦点/按钮语义。
- [x] 全量回归、独立审查、实际Windows开合和文件夹动效录制；本地构建0.12，不覆盖旧包。
- [x] Windows/源码ZIP完整性与SHA-256校验后交付。

## 执行记录

窗口4项和界面最初3项失败后实现；录制发现footer被缩放快照遮盖，补失败回归并修复，独立复核通过。最终8个新UI场景、13组新旧UI及107项Python通过。原生源码与实际exe开合验证、缺少loaded回退、包内文件夹/弹窗录制均通过。详见0.12验证记录。

## 必须保持

主网格单击多选/取消、双击进入/预览；侧栏单击导航；SD只读；库与文件安全不变。关闭主窗口仍取消/等待现有任务并释放库锁，不能先跳过清理。动画期间不得吞掉最新导航；无帧计时或API错误时可正常打开/关闭。长列表、1040×720、返回滚动与焦点可达。材质沿用0.11深色，无新增运行依赖。完整交付前校验新资源随包、ZIP CRC与SHA-256。
