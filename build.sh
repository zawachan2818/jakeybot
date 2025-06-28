#!/bin/bash
pip uninstall -y discord discord.py py-cord || true
pip install py-cord==2.5.0
pip install -r requirements.txt
