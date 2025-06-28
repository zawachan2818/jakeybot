#!/bin/bash

# 不要パッケージを強制削除
pip uninstall -y discord.py || true
pip uninstall -y discord || true
pip uninstall -y py-cord || true

# 必要パッケージのみ再インストール
pip install -r requirements.txt
