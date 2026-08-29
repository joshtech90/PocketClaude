<div align="center">

<img src="../../assets/logo.png" alt="PocketClot" width="160" height="160">

# PocketClot

**你的私人 Claude，运行在你的手机上 —— 由你自己的 Pro/Max 订阅、Anthropic API key 或 AWS Bedrock 任选其一驱动。托管在你自己的硬件上。**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android%2012%2B%20%7C%20Web-blue)](#)
[![Server](https://img.shields.io/badge/server-Python%203.10%2B-yellow)](#)
[![Status](https://img.shields.io/badge/status-public%20beta-green)](#)

[English](../../README.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português (BR)](README.pt-BR.md) · **中文** · [日本語](README.ja.md)

</div>

---

## 关于

**PocketClot** 是为 Anthropic [Claude](https://claude.ai) 打造的自托管聊天前端。一个小巧的 Python 服务运行在你自己的 Linux 主机上（Mini-PC、Raspberry Pi、旧笔记本、NAS）；原生 Android 应用和内置 Web UI 通过 [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) 或 Cloudflare 隧道，从任何地方与之通信。

**按用户分别选择后端**，随时可以在 App 内切换：

- **Pro/Max 订阅**（默认）—— 使用服务器上本地 `claude` CLI 的 OAuth 会话，无需 API key，跑在你的 Pro/Max 配额上。
- **Anthropic API key** —— 来自 [Anthropic Console](https://console.anthropic.com) 的 `sk-ant-…`，按用量计费。
- **AWS Bedrock** —— 使用你的 AWS 凭证，通过 Bedrock 专用的模型 ID 支持 Claude Opus 4.7。

**为什么要做这个。** Anthropic 官方的 Claude 应用已经很出色 —— PocketClot 的存在，是为了填补那些它们（目前）还没做的事：

- **开源。** 可审计、可 fork、可扩展。没有不透明的遥测，也不会突然砍掉功能。
- **额外特性。** TTS 朗读（三家提供方、锁屏播放控件）、图像生成、ChatGPT 风格的长消息折叠、横跨所有聊天记录的全文检索、加密备份、四种可切换的系统提示词模式。
- **多用户，一份订阅。** 把你的 Pro/Max 套餐与家人或同事共享 —— 每个用户都有各自私密的聊天、独立的设置，以及自己用于图像生成和 TTS 的 API key。
- **一个干净的"第二个 Claude"。** 想要严格区分个人与工作场景，又不想为此同时折腾两个 Anthropic 账号？自己起一台服务，和官方客户端并排登录即可。
- **数据归你所有。** 你的对话保存在你自己硬件上的 SQLite 数据库里。可以迁移、可以备份、可以直接查询 —— 它就是你的。

**无需额外的 Anthropic API key。** 认证使用的是你本地安装的 Claude Code CLI 所使用的 OAuth 会话（`claude login`）。PocketClot 调起 CLI，剩下的事情由 CLI 处理 —— 全部跑在你已经付费的那份 Pro/Max 额度之上。

> **注意** —— 这是一个自托管的业余项目，并非 Anthropic 官方产品。你需要自备 Pro/Max 订阅。我们从不查看或代理你的对话。

## 亮点

- 💬 **原生 Android 客户端**（Kotlin + Jetpack Compose，非 Web 包壳），以及作为备选/桌面方案的内置 **Web UI**
- 👨‍👩‍👧 **多用户认证**，使用 scrypt 密码哈希 —— 全家/全团队共享一个 Pro/Max 账号，每个人都有各自的私密聊天和设置
- 📡 **SSE 流式传输**，具备恰当的背压控制、重试拦截器，以及 60 秒连接保活（在 Tailscale Funnel 上也很稳）
- 📎 **宽松的文件附件支持** —— 图片、PDF、代码、配置、JSON、CSV、任意文本格式。可内联，也可通过 Claude `Read` 工具引用
- 🔍 **全文检索**横跨整个聊天历史（SQLite FTS5），应用内可跳转到匹配位置
- 🔊 **三种 TTS 提供方**用于朗读 —— Microsoft Edge（免费，免配置）、Gemini Direct API（免费层），以及 Google Cloud TTS（Chirp 3 HD，每月 100 万字符免费）。通过 Media3 提供锁屏音频控件
- 🎨 通过 Gemini Nano Banana 实现**图像生成** —— 独立界面、画廊、分享、图生图编辑
- 🎭 **四种系统提示词模式** —— Standard（Anthropic 默认）、Permissive、Ultra-Liberal、Custom
- 🛠 **逐聊天的技能开关** —— WebSearch、WebFetch、Bash 执行
- 🔐 对话与设置的 **AES-256 加密备份**
- 🌐 **7 种语言** —— 英语、德语、西班牙语、法语、巴西葡萄牙语、简体中文、日语
- 🌗 全面屏 Material You 设计，支持浅色与深色主题

## 架构

```
                ┌───────────────────────────┐
                │  PocketClot (Android)  │
                │      or built-in web UI   │
                └─────────────┬─────────────┘
                              │ HTTPS  (persistent URL)
                              ▼
              ┌─────────────────────────────────┐
              │  Tailscale Funnel               │
              │  (or Cloudflare Named Tunnel)   │
              └─────────────┬───────────────────┘
                              │ outbound tunnel — no port forwarding
                              ▼
                ┌────────────────────────────┐
                │      Your Linux host       │
                │   ┌──────────────────────┐ │
                │   │  pocket-claude.svc   │ │ ── FastAPI + SQLite (FTS5)
                │   │   (systemd unit)     │ │
                │   │     │                │ │
                │   │     └─ spawns:       │ │
                │   │        claude-code   │ │ ── your Pro/Max OAuth
                │   └──────────────────────┘ │
                │   ┌──────────────────────┐ │
                │   │   tailscaled.svc     │ │
                │   └──────────────────────┘ │
                └────────────────────────────┘
```

两个组件，一个仓库：

| 路径        | 说明                                                                       |
|-------------|----------------------------------------------------------------------------|
| `server/`   | Python FastAPI 后端 + 内置 Web UI，负责调起 `claude` CLI。                |
| `app/`      | Android 客户端（Kotlin + Jetpack Compose，Material 3）。                  |

## 快速开始

### 1 —— 安装服务端（Linux 主机，约 5 分钟）

在一台全新的 Ubuntu / Debian / Fedora 主机上：

```bash
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash
```

安装脚本会创建系统用户 `pocket-claude`、将代码放到 `/opt/pocket-claude/`、安装 Claude Code CLI、把 Python 依赖装到 venv，写入一个 systemd 单元，并在端口 `8787`（loopback）上启动。

### 2 —— 用你的 Pro/Max 账号登录 Claude

```bash
sudo -u pocket-claude -H claude login
```

OAuth 流程会在终端中运行。和 Claude Code 使用的是同一套登录。

### 3 —— 用一个持久 URL 暴露服务（Tailscale Funnel，免费）

```bash
sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh
```

完成后会打印公网 URL —— 形如 `https://your-host.your-tailnet.ts.net`。或者，deploy 目录里也有一个 Cloudflare Named Tunnel 的安装脚本，方便你使用自定义域名。

### 4 —— 安装 Android 应用

可以直接从 [最新版本](https://github.com/joshtech90/PocketClot/releases) 下载 APK，或者自己构建：

```bash
cd app && ./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

打开应用 → **添加配置** → 输入你的 URL 和初始管理员密码（首次启动服务时写入到 `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`）。首次登录后请修改密码。

### 5 —— （可选）用 Web UI 代替应用

直接在任意浏览器中打开你的隧道 URL。Web UI 由同一个 FastAPI 进程提供服务。

完整安装说明，包括 Cloudflare 路径、主机间迁移、日常更新流程以及故障排查：**[`server/deploy/README.md`](../../server/deploy/README.md)**。

## 多用户

首次启动后会创建一个 `Admin` 用户，初始密码写入到 `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`。在应用里通过 **用户** 界面（仅限管理员）添加更多用户 —— 每个人都有自己的对话、设置和 API 密钥，全部都跑在你这一份 Pro/Max 订阅之上。

## TTS 朗读

三种提供方，可按用户分别选择：

| 提供方              | 音质                  | 配置                         | 费用                                              |
|---------------------|-----------------------|------------------------------|---------------------------------------------------|
| **Microsoft Edge**  | 良好                  | 无                           | 免费（由 Microsoft 托管）                        |
| **Gemini Direct**   | 优秀                  | AI Studio API key            | 免费层（每个 key 每天 10 次请求）                |
| **Google Cloud TTS** | 优秀（Chirp 3 HD）   | 服务账号 JSON                | 每月 100 万字符免费，之后约 16 美元/百万字符     |

在应用中：**设置 → 朗读 → 提供方**，选你合适的。支持自动朗读、声音选择器、语速调节，以及面向 Gemini Direct 免费层的多 key 池。

## 图像生成（Gemini Nano Banana）

自备 AI Studio API key（休闲使用免费层足够）。独立界面、画廊、分享到其他应用、图生图编辑。如果没有配置 key，UI 中相关功能会被禁用。

## 技术栈

**服务端。** Python 3.10+、FastAPI、Uvicorn、用于 SSE 的 `sse-starlette`、aiosqlite、SQLite + FTS5、[`claude-agent-sdk`](https://pypi.org/project/claude-agent-sdk/)、用于密码哈希的 `scrypt`（标准库），用于 AES-256 备份的 `pyzipper`，以及 `edge-tts` + Google Cloud TTS SDK + 面向 Gemini Direct 的 REST。

**应用。** Kotlin 2.0.21、Android Gradle Plugin 8.7.3、compileSdk 35、minSdk 31、Jetpack Compose Material 3（BOM 2024.12.01）、OkHttp + okhttp-sse、DataStore Preferences、Coil 3、AndroidX Media3（ExoPlayer + MediaSession），以及用于 Markdown 的 `compose-richtext`。

**Web UI。** 原生 JS，无构建步骤，作为静态文件由同一个 FastAPI 进程提供。

## 路线图

- [ ] iOS 客户端
- [ ] Docker / Docker Compose 部署，作为系统安装脚本的一键替代方案
- [ ] 应用端的语音输入（基于 Whisper）
- [ ] 按对话设置工具预算

## 贡献

接受 Pull Request。工作流程请参见 [CONTRIBUTING.md](../../CONTRIBUTING.md)。

## 许可证

MIT —— 参见 [LICENSE](../../LICENSE)。

## 致谢

- [Anthropic](https://www.anthropic.com/) 提供 Claude 和 Claude Code CLI
- [Tailscale](https://tailscale.com/) 让零配置的公网隧道对个人用户免费可用
- [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python) 提供干净的 CLI-spawning 接口
- Compose、FastAPI 与 SQLite 团队
