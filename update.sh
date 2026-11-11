#!/bin/bash
# update.sh — refresh proxy lists in this repo from proxy-tool output
set -e
SRC=/home/nikitos/proxy-tool
cd "$(dirname "$0")"

if [ ! -d "$SRC/proxylist" ]; then
    echo "run: python3 $SRC/proxy_tool.py -o $SRC/proxylist first"
    exit 1
fi

cp "$SRC/proxylist/alive.txt" "$SRC/proxylist/alive.json" . 2>/dev/null
cp "$SRC/proxylist/"*.txt . 2>/dev/null || true
rm -rf by-country
cp -r "$SRC/proxylist/by-country" . 2>/dev/null || true
cp "$SRC/proxy_tool.py" .

git add -A
git commit -m "proxy update $(date -u +%Y-%m-%d) — $(wc -l < alive.txt) alive" || echo "nothing to commit"
git push origin master
