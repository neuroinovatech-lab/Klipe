#!/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js não encontrado. Instale com: brew install node"
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "Instalando dependências do Klipe..."
  npm install
fi

PORT="${PORT:-3002}"
(sleep 2; open "http://127.0.0.1:${PORT}") &
node editor-server.js
