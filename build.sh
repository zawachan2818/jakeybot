#!/bin/bash

# キャッシュ削除（Renderに効く場合あり）
rm -rf ~/.cache/pip

# 強制アンインストール
pip uninstall -y discord.py discord py-cord || true

# 明示的に py-cord を入れ直す
pip install py-cord==2.5.0

# 他のライブラリをインストール
pip install -r requirements.txt
