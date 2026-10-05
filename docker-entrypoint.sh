#!/bin/sh
# Garante que o volume de dados exista e pertenca ao usuario da aplicacao, e entao
# abre mao do root. Volumes montados pelo EasyPanel costumam chegar como root:
# sem este passo, o painel nao conseguiria gravar nada.
set -e

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR/uploads"

if [ "$(id -u)" = "0" ]; then
  chown -R app:app "$DATA_DIR" 2>/dev/null || true
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi

exec "$@"
