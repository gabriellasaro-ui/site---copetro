"""Configuracao do gunicorn. Tudo ajustavel por variavel de ambiente."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '6000')}"

# Um processo com varias threads: o limite de tentativas de login do painel vive
# em memoria, e com um unico processo ele vale para todos. O site e leve (HTML
# renderizado na hora e arquivos estaticos), entao 8 threads atendem folgado.
# Para escalar com mais processos, o limite de login precisa de um armazenamento
# compartilhado.
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = int(os.environ.get("WEB_THREADS", "8"))
worker_class = "gthread"

timeout = 60
graceful_timeout = 30
keepalive = 5

# recicla o processo de tempos em tempos: higiene de memoria
max_requests = 2000
max_requests_jitter = 200

# o heartbeat do gunicorn em /dev/shm evita travar em sistemas de arquivos de overlay
worker_tmp_dir = "/dev/shm"

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# atras do proxy do EasyPanel: confia em X-Forwarded-Proto para saber que e HTTPS
forwarded_allow_ips = "*"
