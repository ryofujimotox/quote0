# デプロイ




## 前提

実装・振る舞い: [AGENTS.md](../AGENTS.md)

| 項目 | 内容 | その他 |
|------|------|------|
| OS | **Linux** | - |
| タイムゾーン | ホスト OS を **Asia/Tokyo** に設定する | cron の時刻はホスト OS のタイムゾーンで解釈する |
| 配置 | `/home/scripts/handy-calendar/` に配置する | 初回の取得は「セットアップ」の `git clone` |
| 実行 | 毎日 **0:00 JST** に cron で `.venv/bin/python -m handy_calendar` を実行 | 手動実行は「動作確認」 |
| 秘密情報 | `.env` | [AGENTS.md](../AGENTS.md) の「設定（環境変数）」。作成・設定は「環境変数（`.env`）」 |
| Python | ホスト **3.12**（`.python-version`） | `python3.12` が無いときは「Python 3.12 のインストール」 |



## セットアップ

```bash
# リポジトリを clone し、作業ディレクトリへ移動
git clone https://github.com/ryofujimotox/handy-calendar /home/scripts/handy-calendar
cd /home/scripts/handy-calendar

# 仮想環境を作成し、依存パッケージを入れる
python3.12 -m venv .venv
.venv/bin/python --version
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```



### 環境変数（`.env`）

```bash
cd /home/scripts/handy-calendar
cp -n .env.example .env
chmod 600 .env
```

[AGENTS.md](../AGENTS.md) の「設定（環境変数）」どおり `.env` を設定する。

予定タイトルや URL などの詳細ログを確認したいときだけ、`.env` の `HANDY_CALENDAR_DEBUG=1` を一時的に設定する。通常運用では空のままにする。



### 動作確認

バッチを手動で 1 回実行する。

```bash
cd /home/scripts/handy-calendar
.venv/bin/python -m handy_calendar
echo $?
```

- **終了コード 0** が出たら OK（詳細は [AGENTS.md](../AGENTS.md) の「成功または失敗時の挙動」を参照）
- 失敗時は stderr の日本語メッセージを確認する。



### ローカル単体テスト

ローカルで単体テストを実行するときだけ、開発依存を入れて実行する（本番運用の cron 実行環境には入れない）。

```bash
cd /home/scripts/handy-calendar
.venv/bin/pip install -r requirements-dev.txt # 初回のみ
.venv/bin/python -m pytest
```

- 失敗 0 件で終了すれば OK（観点は [AGENTS.md](../AGENTS.md) の「単体テスト（最小仕様）」を参照）



### cron 登録

`crontab -e` でエディタを開き、次の 1 行を追加する。

```bash
crontab -e
```

```cron
0 0 * * * cd /home/scripts/handy-calendar && .venv/bin/python -m handy_calendar
```

`crontab -l` で登録内容を確認する。

```bash
crontab -l
```

- 上記 1 行が表示されれば OK



## 更新

```bash
cd /home/scripts/handy-calendar
git pull
.venv/bin/pip install -r requirements.txt
```

すぐ Dot に反映したいときは、「セットアップ」の「動作確認」を再実行する（cron は通常そのまま）。

`.python-version` を上げたときは、文末「Python 3.12 のインストール」のあと、下記で `.venv` を作り直す。

```bash
cd /home/scripts/handy-calendar
rm -rf .venv
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```



## Python 3.12 のインストール

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

RHEL / AlmaLinux / Rocky:

```bash
sudo dnf install -y python3.12
```



### 確認

```bash
python3.12 --version
```

- `Python 3.12.` で始まれば OK
