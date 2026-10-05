# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/data \
    PORT=6000

# usuario sem privilegios: o processo web nunca roda como root
RUN groupadd --system --gid 1000 app \
 && useradd  --system --uid 1000 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

# dependencias antes do codigo: o cache de camadas sobrevive a mudancas de HTML/CSS
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app app.py admin.py store.py gunicorn.conf.py docker-entrypoint.sh ./
COPY --chown=app:app templates/ templates/
COPY --chown=app:app static/ static/
COPY scripts/minificar.py scripts/minificar.py

# gera style.min.css e main.min.js: o site passa a servir as versoes menores
RUN python scripts/minificar.py

# o checkout no Windows pode trazer fim de linha CRLF, que quebra o #!/bin/sh
RUN sed -i 's/\r$//' docker-entrypoint.sh \
 && chmod +x docker-entrypoint.sh \
 && mkdir -p /data \
 && chown app:app /data

# posts publicados e imagens enviadas pelo painel moram aqui: monte um volume
VOLUME ["/data"]

EXPOSE 6000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import os,sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','6000'), timeout=4).status == 200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
