# 安装、换电脑与其他 AI 工具

## 先选平台

- Windows x64：按下方 Windows 步骤，使用包内 Windows 本地预览版运行组件。
- Mac Apple Silicon：使用 `assets/macos` 的官方 arm64 安装包，完整步骤和密码/钥匙串取舍见 [macos.md](macos.md)。Mac 分支尚未实机验收。
- Intel Mac、手机或平板：本包不提供可运行组件；不将 arm64 Mac 包描述为支持所有 Mac。

## 组成与兼容性

技能说明不是完整运行软件。Windows 运行需 x64、Python 3.10+、已登录的个人微信 4.x、CLI 与同目录 libWCDB.dll，以及本机数据库密钥。当前实测：Windows、微信 4.2.0.12、CLI 2.0.3-local.1。Mac 使用原生 Python、wechat-cli、libWCDB.dylib 和 wxkey；不可使用 Windows EXE。其他版本需单独验证，不承诺全部适配。图片批量解码尚未跑通。

配套迁移包由 `scripts/make_portable.py --workspace <已验证工作目录> --output <ZIP路径>` 生成，仅复制明确定义的技能、运行文件、辅助源码、许可证与桥接源码。包不包含密钥、账号配置、真实数据目录、状态快照、日志或正文。包中 local-settings.json 使用空值模板。

## 新 Windows 电脑

1. 将迁移包解压到用户选择的独立目录。先检查 package-manifest.json、文件 SHA-256 和来源；自己生成的清单只用于检测传输变更，不是发行商签名。若 DLL 缺少微软运行库，从微软官方安装相应 Visual C++ x64 Runtime，不从不明网站下载单个 DLL。
2. 从 Python 官方来源安装 Python，确认微信版本、登录状态和数据目录。不要复制旧电脑的 `.config/wxcli`、`.wechat-cli`、数据库或密钥文件进技能包。
3. 需要图片扫描时安装包内 `requirements-image.txt` 指定依赖到解压目录 `build-tools/python-libs`。普通文字读取不依赖此目录。保留第三方许可证，不把本机配置放入源码仓库。
4. 用目标电脑的 Python 运行 `wechat-reader/scripts/setup_local.py --bundle-root <解压目录> --db-root <直接包含db_storage的账号目录> --confirm-setup`。脚本只检查文件并写路径配置，不读取微信或自动扫描密钥，不修改系统 PATH。
5. 将 `wechat-reader` 文件夹复制到目标 AI 工具支持的技能目录；复制后再运行一次 setup_local.py 更新该副本的本机路径。如果已有同名技能，先比较版本并备份，不直接覆盖。
6. 经用户授权后执行 `scripts/reader.py status --authorized`；缺密钥时，明确说明将读取本机微信进程并保存本机密钥，再执行一次 `repair --authorized`。不要打印或转移密钥。
7. 只有用户指定测试联系人/群和时间段后，才执行小范围 `read --chat <会话> --period today --authorized`；验证实时读取、分页、消息时间与媒体缺失。未通过时不声称迁移成功。

本机包已包含 CLI 和 DLL；若必须重新构建，原始项目为 https://github.com/r266-tech/wx-cli ，基础提交 00de55e7a87c4efe0527b06afffaf6e8b5c66143；新版数据库辅助程序来源与固定提交见包内 wechat-key-helper/SOURCE.txt。编译需 Go、Visual Studio 2022 C++、Windows SDK 与 CMake；不要盲用官方 latest 安装器替换这套预览版。桥源码随包保留。

## 其他 AI 工具

需要能读本地文件、执行程序并遵守授权边界的桌面/命令行 AI。让它先完整读取 SKILL.md 及 boundaries.md，再按当前请求调用脚本；不支持技能自动发现的工具可把这两个文件作为本机任务说明显式加载。各工具的技能路径不同，以其当前文档为准，不自动修改其他工具配置。

仅能网页聊天、不能执行本机程序的 AI 不能直接读取微信。可由用户明确授权先导出最小范围到本机，再由用户决定提供给哪个服务；不要偷偷上传。visualize 是 Codex 的可选展示能力；其他 AI 不具备时返回普通文字或本地 Markdown，不伪造可交互预览。操作系统和工具原有审批不可绕过。
