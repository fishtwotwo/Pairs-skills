# Mac 安装分支

## 范围与包

内置包在 `assets/macos/wechat-cli-v2.0.2-darwin-arm64.zip`，来源为 https://github.com/r266-tech/wechat-cli-releases/releases/tag/v2.0.2 。支持 Apple Silicon（M 系列、arm64），不支持 Intel Mac；请使用原生 arm64 Python。保留 Mac 包原始内容、SHA-256 和来源记录，不与 Windows EXE 混用。Mac 包及内部文件已在 Windows 离线校验，但未在真实 Mac 安装或读取测试。

包清单标记 signing_mode=adhoc、notarization_status=not_configured，不能宣称经过 Apple Developer ID 签名或公证。目标 Mac 如出现系统安全阻止，由用户按其安全政策决定；不要自动关闭 Gatekeeper、SIP、清除隔离属性或绕过系统警告。

## 安装步骤（由目标 Mac 的执行助手引导）

1. 先读 SKILL.md 和 boundaries.md；确认 macOS arm64、微信 4.x 与本机 Python 3.10+。安装请求只授权安装，不授权查询聊天。
2. 执行 `python3 scripts/verify_macos.py assets/macos/wechat-cli-v2.0.2-darwin-arm64.zip`。哈希校验不能替代来源信任或 Apple 签名校验。通过后用系统解压工具解压到独立目录，检查包内安装说明及脚本，不使用 `curl | shell`。
3. 根据包内 install.sh 先 dry-run，再在用户授权下安装 CLI。使用该包内安装脚本，不加自动初始化/后台 watcher 的选项。默认运行位置为 `~/.local/share/wechat-cli`；以目标机实际安装结果为准。若脚本拒绝签名/来源，不修改验证代码绕过。
4. 用本技能 setup_local.py 配置目标机：`python3 scripts/setup_local.py --bundle-root <迁移包根目录> --db-root <直接含db_storage的本机账号目录> --cli-dir ~/.local/share/wechat-cli --wechat-exe /Applications/WeChat.app --confirm-setup`。不复制 Windows 数据目录、数据库或密钥。
5. 首次密钥初始化须单独说明并取得用户明确同意：`wxkey bootstrap` 可能退出并重新打开微信、请求系统管理员密码，并将经验证的管理员密码保存在用户本机钥匙串，供后续刷新使用。不同意此取舍就停止初始化。密码只能由用户在本机可信系统界面输入，不发给 AI、不放进命令或日志。
6. 在获授权的初始化流程中，由用户处理 macOS 的完全磁盘访问等必要系统权限，目标文件通常是运行目录中的 wechat-cli 和 wxkey；不自动扩大到其他应用。
7. 获授权后使用 `python3 scripts/reader.py status --authorized`。未准备好密钥时会提示 mac_bootstrap_required，不会误调用 Windows 辅助程序或悄悄重启微信。仅在用户指定联系人/群与时间后做小范围 read 验收。

## 限制

普通查询继续使用 strict-read-only。Mac 读不到记录时先处理对应权限/本机配置，不退回 Windows 原生扫描。repair 在密钥缺失时要求显式 bootstrap；repair-images 的 Windows 适配器不在 Mac 运行。图片、语音完整性仍需单独核验。其他 AI 工具不具备 Codex 卡片能力时返回文字或本地文件。
