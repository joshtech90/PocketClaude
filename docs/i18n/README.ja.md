<div align="center">

<img src="../../assets/logo.png" alt="PocketClot" width="160" height="160">

# PocketClot

**スマホで使えるあなた専用の Claude — ご自身の Pro/Max サブスクリプション、Anthropic API キー、または AWS Bedrock のいずれかで動作。ご自身のハードウェアでホスティングされます。**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android%2012%2B%20%7C%20Web-blue)](#)
[![Server](https://img.shields.io/badge/server-Python%203.10%2B-yellow)](#)
[![Status](https://img.shields.io/badge/status-public%20beta-green)](#)

[English](../../README.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português (BR)](README.pt-BR.md) · [中文](README.zh.md) · **日本語**

</div>

---

## 概要

**PocketClot** は、Anthropic の [Claude](https://claude.ai) 向けのセルフホスト型チャットフロントエンドです。小さな Python サーバーがご自身の Linux マシン（Mini-PC、Raspberry Pi、古いノート PC、NAS）で動作し、ネイティブ Android アプリと内蔵 Web UI が [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) または Cloudflare トンネル経由で、どこからでもサーバーと通信します。

**バックエンドはユーザーごとに選択可能**で、アプリ内でいつでも切り替えられます。

- **Pro/Max サブスクリプション**（デフォルト）— サーバー上のローカル `claude` CLI の OAuth セッションを使用します。API キーは不要で、お持ちの Pro/Max クォータで動作します。
- **Anthropic API キー** — [Anthropic Console](https://console.anthropic.com) から取得した `sk-ant-…` を使用し、従量課金で利用できます。
- **AWS Bedrock** — お手持ちの AWS 認証情報を使用し、Bedrock 固有のモデル ID で Claude Opus 4.7 に対応します。

**なぜこれが存在するのか。** Anthropic の公式 Claude アプリは素晴らしいものです — PocketClot は、それらが（まだ）対応していない部分のために存在します。

- **オープンソース。** 監査することも、フォークすることも、拡張することも自由です。怪しいテレメトリも、突然の機能削除もありません。
- **追加機能。** TTS 読み上げ（3 つのプロバイダー、ロック画面コントロール対応）、画像生成、ChatGPT スタイルの長文メッセージ折りたたみ、全チャット横断の全文検索、暗号化バックアップ、4 種類から選べるシステムプロンプトモード。
- **マルチユーザー、ひとつのサブスクリプション。** Pro/Max プランをご家族や同僚と共有できます — 各ユーザーは個別のチャット、個別の設定、そして画像生成や TTS 用に独自の API キーを持てます。
- **クリーンなもうひとつの「Claude」。** 2 つの Anthropic アカウントを使い分けずに、プライベートと仕事を厳密に分けたいですか？ ご自身のサーバーを立ち上げて、公式クライアントと並行してログインするだけで完了です。
- **データはあなたのものです。** 会話はご自身のハードウェア上の SQLite データベースに保存されます。移行も、バックアップも、直接クエリすることもできます — すべてあなたのものです。

**追加の Anthropic API キーは不要です。** 認証には、ローカルにインストールされた Claude Code CLI が使用する OAuth セッション（`claude login`）を使います。PocketClot が CLI を起動し、残りの処理は CLI が担当します — すでにお支払いいただいている Pro/Max のクォータ上で動作します。

> **ご注意** — これはセルフホスト型の趣味プロジェクトであり、Anthropic 公式の製品ではありません。ご自身の Pro/Max サブスクリプションを持ち込んで使う形になります。私たちはあなたの会話を見たり、プロキシしたりすることは決してありません。

## ハイライト

- 💬 **ネイティブ Android クライアント**（Kotlin + Jetpack Compose、Web ラッパーではありません）と、フォールバック / デスクトップ向けの内蔵 **Web UI**
- 👨‍👩‍👧 **scrypt パスワードハッシュによるマルチユーザー認証** — 家族やチーム全員で 1 つの Pro/Max アカウントを共有しつつ、それぞれが個別のチャットと設定を持てます
- 📡 **SSE ストリーミング** — 適切なバックプレッシャー、リトライインターセプター、60 秒のキープアライブ接続を備え、Tailscale Funnel 越しでも安定動作
- 📎 **柔軟なファイル添付** — 画像、PDF、コード、設定ファイル、JSON、CSV、あらゆるテキスト形式に対応。インライン埋め込み、または Claude の `Read` ツール経由での参照
- 🔍 **チャット履歴全体の全文検索**（SQLite FTS5）と、アプリ内のヒット箇所へのジャンプ機能
- 🔊 **3 種類の TTS プロバイダー**で読み上げ可能 — Microsoft Edge（無料、セットアップ不要）、Gemini Direct API（無料枠あり）、Google Cloud TTS（Chirp 3 HD、月 100 万文字まで無料）。Media3 によるロック画面オーディオコントロール対応
- 🎨 **Gemini Nano Banana による画像生成** — 専用画面、ギャラリー、共有、画像から画像への編集
- 🎭 **4 つのシステムプロンプトモード** — Standard（Anthropic デフォルト）、Permissive、Ultra-Liberal、Custom
- 🛠 **チャットごとのスキル切り替え** — WebSearch、WebFetch、Bash 実行
- 🔐 **AES-256 暗号化バックアップ**で会話と設定を保存
- 🌐 **7 言語対応** — 英語、ドイツ語、スペイン語、フランス語、ブラジルポルトガル語、簡体字中国語、日本語
- 🌗 ライト/ダークテーマ対応のエッジツーエッジ Material You デザイン

## アーキテクチャ

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

1 つのリポジトリに、2 つのコンポーネントがあります。

| パス        | 内容                                                                       |
|-------------|----------------------------------------------------------------------------|
| `server/`   | Python FastAPI バックエンドと内蔵 Web UI。`claude` CLI を起動します。      |
| `app/`      | Android クライアント（Kotlin + Jetpack Compose、Material 3）。             |

## クイックスタート

### 1 — サーバーをインストール（Linux ホスト、約 5 分）

新しい Ubuntu / Debian / Fedora マシンで実行します。

```bash
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash
```

インストーラーは `pocket-claude` システムユーザーを作成し、コードを `/opt/pocket-claude/` に配置し、Claude Code CLI をインストールし、Python の依存関係を venv にインストールし、systemd ユニットを書き込み、ポート `8787`（ループバック）で起動します。

### 2 — Pro/Max アカウントで Claude にログイン

```bash
sudo -u pocket-claude -H claude login
```

OAuth フローがターミナルで実行されます。Claude Code が使用するのと同じログインです。

### 3 — 永続 URL でサーバーを公開（Tailscale Funnel、無料）

```bash
sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh
```

完了すると公開 URL が表示されます — `https://your-host.your-tailnet.ts.net` のような形式です。なお、deploy フォルダにはカスタムドメインを使いたい場合向けの Cloudflare Named Tunnel セットアップスクリプトもあります。

### 4 — Android アプリをインストール

[最新リリース](https://github.com/joshtech90/PocketClot/releases)から APK をダウンロードするか、自分でビルドします。

```bash
cd app && ./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

アプリを開いて → **プロファイルを追加** → URL と初期管理者パスワード（サーバー初回起動時に `/opt/pocket-claude/data/INITIAL_PASSWORD.txt` に出力されます）を入力します。初回ログイン時にパスワードを変更してください。

### 5 — （オプション）アプリの代わりに Web UI を使う

トンネル URL を任意のブラウザで開くだけです。Web UI は同じ FastAPI プロセスから配信されます。

Cloudflare 経由のセットアップ、ホスト間移行、毎日のアップデートワークフロー、トラブルシューティングを含む完全なセットアップガイドはこちら: **[`server/deploy/README.md`](../../server/deploy/README.md)**。

## マルチユーザー

初回起動後、`Admin` ユーザーが作成され、初期パスワードが `/opt/pocket-claude/data/INITIAL_PASSWORD.txt` に書き込まれます。アプリの**ユーザー**画面（管理者のみ）からユーザーを追加できます — 各ユーザーは自分専用の会話、設定、API キーを持ちつつ、すべてあなたの 1 つの Pro/Max サブスクリプションを通して動作します。

## TTS 読み上げ

ユーザーごとに選択可能な 3 つのプロバイダー。

| プロバイダー           | 音声品質 | セットアップ                  | コスト                                              |
|------------------------|----------|-------------------------------|-----------------------------------------------------|
| **Microsoft Edge**     | 良好     | なし                          | 無料（Microsoft がホスティング）                    |
| **Gemini Direct**      | 優秀     | AI Studio API キー            | 無料枠（キーごとに 1 日 10 リクエスト）             |
| **Google Cloud TTS**   | 優秀（Chirp 3 HD） | サービスアカウント JSON | 月 100 万文字まで無料、以降は 100 万文字あたり約 $16 |

アプリ内: **設定 → 読み上げ → プロバイダー**から、お好みのものを選択します。自動読み上げ、ボイスピッカー、再生速度、Gemini Direct 無料枠向けマルチキー プール機能を備えています。

## 画像生成（Gemini Nano Banana）

ご自身の AI Studio API キーをご用意ください（カジュアル用途なら無料枠で十分です）。専用画面、ギャラリー、他アプリへの共有、画像から画像への編集に対応。キーが設定されていない場合は UI 上で無効化されます。

## 技術スタック

**サーバー。** Python 3.10+、FastAPI、Uvicorn、SSE 用に `sse-starlette`、aiosqlite、SQLite + FTS5、[`claude-agent-sdk`](https://pypi.org/project/claude-agent-sdk/)、パスワードハッシュ用に `scrypt`（標準ライブラリ）、AES-256 バックアップ用に `pyzipper`、`edge-tts` + Google Cloud TTS SDK + Gemini Direct 用 REST。

**アプリ。** Kotlin 2.0.21、Android Gradle Plugin 8.7.3、compileSdk 35、minSdk 31、Jetpack Compose Material 3（BOM 2024.12.01）、OkHttp + okhttp-sse、DataStore Preferences、Coil 3、AndroidX Media3（ExoPlayer + MediaSession）、Markdown 用に `compose-richtext`。

**Web UI。** 素の JavaScript、ビルドステップなし、同じ FastAPI プロセスから静的ファイルとして配信。

## ロードマップ

- [ ] iOS クライアント
- [ ] システムインストールスクリプトのワンライナー代替としての Docker / Docker Compose デプロイ
- [ ] アプリ側での音声入力（Whisper ベース）
- [ ] 会話ごとのツールバジェット

## コントリビューション

プルリクエストを受け付けています。ワークフローについては [CONTRIBUTING.md](../../CONTRIBUTING.md) を参照してください。

## ライセンス

MIT — [LICENSE](../../LICENSE) を参照。

## 謝辞

- Claude と Claude Code CLI を提供してくれた [Anthropic](https://www.anthropic.com/)
- ゼロコンフィグの公開トンネルを個人利用で無料にしてくれている [Tailscale](https://tailscale.com/)
- きれいな CLI 起動インターフェースを提供する [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python)
- Compose、FastAPI、SQLite の各チームの皆さん
