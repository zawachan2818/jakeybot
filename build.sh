#!/bin/bash

# 念のため旧バージョン削除
pip uninstall -y discord.py || true
pip uninstall -y py-cord || true

# 正しいバージョンを再インストール
pip install -r requirements.txt
