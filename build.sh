#!/bin/bash

# 不要なdiscord.pyがある場合に削除（念のため）
pip uninstall -y discord.py || true

# 必要な依存関係をインストール
pip install -r requirements.txt
