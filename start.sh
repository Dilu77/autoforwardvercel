#!/bin/bash
pip3 install -U -r requirements.txt
echo "Starting Live Forward Bot..."
gunicorn app:app & python3 main.py
