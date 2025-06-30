#!/bin/bash

echo "🔧 ビルド開始：環境の初期化中..."

# 古い仮想環境を削除（Render上では .venv に作られることが多い）
rm -rf .venv

echo "🧹 discord/discord.py をアンインストール中..."
pip uninstall -y discord discord.py

echo "📦 依存パッケージをインストール中..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ ビルド完了！"