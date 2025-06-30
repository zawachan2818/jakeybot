#!/usr/bin/env bash

echo "🔧 ビルド開始..."

# 一応全部アンインストールしてから綺麗に入れ直し
pip uninstall -y discord discord.py py-cord wavelink || true

# py-cordのみ依存なしで入れる（wavelinkが勝手にdiscord.pyを入れないように）
pip install py-cord==2.5.0 --no-deps

# 次にwavelinkだけ入れる（py-cord対応）
pip install wavelink==3.4.1

# その他すべてrequirements.txtから
pip install -r requirements.txt

echo "✅ ビルド完了！"