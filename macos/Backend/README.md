# macOS 本机库业务服务

此目录复用 Windows 0.12.1 的业务服务，来源提交和原始摘要见 `PROVENANCE.json`。原参考检出不修改、不直接导入运行。界面和来源/旧库读取仍为 SwiftUI/Swift。

入口 `main.py` 是私有标准输入/输出 JSON 协议，没有 HTTP 服务、WebView 或任意 SQL/动态方法入口。只通过 `ManagedLibrary` 新建或打开本应用的库，旧库继续由 Swift 只读读取。`pianji.library.Library` 的原自动初始化/恢复入口已关闭。

`managed.py` 验证来源标记、根和数据库身份，持有生命周期锁；新库不能嵌套在现有库或本次会话的只读来源中。活动与固定分类在同一数据库事务内创建，照片目录在首次文件事务中分配。

`safeos.py` 用 Darwin RENAME_EXCL 和目录描述符发布/移动文件，拒绝符号链接；复制保持来源只读。`fileops.py` 是 macOS 日志适配，记录暂存身份后写字节，失败只回滚可证明归属的文件。未知 partial/外来文件保留。打开不自动恢复；显式恢复也只处理本库、当前 macOS 格式，不执行历史 SQL。未完成操作或 purge 会阻止普通写入。

当前 app 内置 CPython 3.12.16 / arm64 与 Pillow 13.0.0、NumPy/OpenCV/rawpy，采用 `-I -B` 隔离和禁写字节码；来源与摘要固定于 `../Runtime/runtime-lock.json`。成片、找回和撤销已接入，完整验证见 `docs/NATIVE_EXPORT_VALIDATION.md`。OpenCV 与 YuNet/SFace 模型已随 app 打包，新增自动人物分类跳过人工归属、支持取消及逐照片报告；完整第三方许可汇总及最终发行签名仍待完成。回收站、恢复和基于本库身份收据的永久删除已接入；purge 中断计划先持久化隔离路径，再删除，重试绕过普通写闸门但仍校验库和操作状态。整库统计/确认通过私有 token 和最新来源保护复核，实际回收由 Swift 原生 FileManager 在文件协调区间执行。

新增成片测试可用：`macos/Runtime/Python/bin/python3 -B -m unittest discover -s macos/BackendTests -p test_exports.py`。仅运行本次新增或受影响的用例，未受影响的既有结果不重复验证。仅使用新建隔离临时目录；不运行参考项目的破坏性自测。

人物分类新增验证准备：先运行 `macos/Models/prepare_models.py` 与 `script/make_face_fixture.py --sample-only`，再按需选择 `macos/BackendTests/test_faces.py` 中的新增/受影响用例。人像测试夹具为公开样本，仅存放于忽略的 build/；不打包私人照片。
