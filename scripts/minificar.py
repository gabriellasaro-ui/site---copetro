"""Gera style.min.css e main.min.js ao lado dos originais.

Roda no build da imagem Docker. Localmente nao e necessario: sem os arquivos .min,
o site usa os originais, que sao mais faceis de depurar.
"""
import os
import sys

import rcssmin
import rjsmin

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALVOS = [
    ("static/css/style.css", rcssmin.cssmin, "static/css/style.min.css"),
    ("static/css/admin.css", rcssmin.cssmin, "static/css/admin.min.css"),
    ("static/js/main.js", rjsmin.jsmin, "static/js/main.min.js"),
    ("static/js/admin.js", rjsmin.jsmin, "static/js/admin.min.js"),
]

total_antes = total_depois = 0
for origem, fn, destino in ALVOS:
    src = os.path.join(RAIZ, origem)
    with open(src, encoding="utf-8") as fh:
        texto = fh.read()
    saida = fn(texto)
    with open(os.path.join(RAIZ, destino), "w", encoding="utf-8") as fh:
        fh.write(saida)
    a, d = len(texto.encode()), len(saida.encode())
    total_antes += a
    total_depois += d
    print(f"{origem:24} {a/1024:6.1f} KB -> {d/1024:6.1f} KB  ({100 - round(100 * d / a)}% menor)")
print(f"{'total':24} {total_antes/1024:6.1f} KB -> {total_depois/1024:6.1f} KB")
sys.exit(0)
