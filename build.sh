#!/usr/bin/env bash
echo "🔧 ビルド開始..."

# 念のため不要な競合ライブラリを削除
pip uninstall -y discord discord.py py-cord wavelink || true

# 最新pipにしておく（重要）
pip install --upgrade pip

# 依存関係をまとめて一括インストール
pip install -r requirements.txt

echo "✅ ビルド完了！"