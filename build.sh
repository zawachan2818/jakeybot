#!/bin/bash

# 念のためのクリーンアップ
pip uninstall -y discord discord.py py-cord

# 依存関係インストール
pip install -r requirements.txt

# 最後にもう一度 discord.py 系を削除して py-cord を明示的に入れる
pip uninstall -y discord discord.py
pip install py-cord==2.5.0