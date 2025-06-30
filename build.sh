#!/bin/bash

# 安全のため競合をアンインストール
pip uninstall -y discord discord.py py-cord

# 依存をインストール
pip install -r requirements.txt
