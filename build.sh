#!/usr/bin/env bash

echo "🔧 ビルド開始..."

# 念のため不要な競合ライブラリを削除
pip uninstall -y discord discord.py py-cord wavelink || true

pip install aiofiles

pip install python-dotenv

pip install PyYAML

pip install pymongo

pip install google-genai>=1.3.0

pip install motor

pip install PyNaCl

pip install wavelink

# py-cordを先に入れる（依存なしで）
pip install py-cord==2.5.0

# 残りのライブラリをまとめて
pip install -r requirements.txt

echo "✅ ビルド完了！"