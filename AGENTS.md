# macOS 开发约定

- 默认使用 `/Users/edison/.agents/skills/using-superpowers/SKILL.md` 组织构建开发，按任务加载技能和插件。
- 原生实现仅在 macos/；Reference/Windows 为只读业务参考，不修改或运行其破坏性自测。
- 用户已同意 docs/NATIVE_ARCHITECTURE.md 与 docs/IMPLEMENTATION_PLAN.md 后继续开发；按阶段实现，无需反复询问是否继续。
- 来源只读，禁止自动写旧库或自动恢复 Windows 操作日志。未完成能力须如实标记。
- 本仓库独立于 Windows 项目，当前开发分支 feature/native-p1；不自行推送或发布。

- 用户指定仅支持 Apple Silicon（M 系列）：Debug/Release 固定 arm64；不安排 Intel 或 Universal 构建与验收。

- 用户最新范围（2026-11-04 晚）：现阶段按 macOS 独立版开发，Windows 数据互通、旧库转换及双向往返兼容暂不需要，不作为完成门槛；已实现只读查看可保留，不继续扩展跨端兼容。原 Windows 项目仍只读参考。
- 验证仅覆盖新增或实际受改动影响的部分；已通过且未受影响的功能不重复测试。
- 用户最新范围（2026-11-05 晚）：macOS 为次要开发版，以 Windows 已有核心功能能用为目标，基本检查通过即可收尾；不增加复杂联动或严格专项验收，不切换系统辅助设置。当前本机交付核对见 docs/LOCAL_DELIVERY.md，后续优先修复实际影响使用的问题。
- GitHub 上传授权（2026-11-05）：用户要求与 Windows 版共用 Edison-0315/lumix-laundry-photo-manager 仓库，分开 macOS 版本。本轮允许推送 macOS 独立分支 codex/macos；不覆盖或合并 Windows main，不修改既有 Windows 版本。此前“不自行推送或发布”继续约束未另行授权的操作。
