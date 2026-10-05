"""Auditoria de SEO técnico do site, sem navegador.

Percorre todas as URLs do sitemap pelo cliente de teste do Flask e confere o que
mais pesa em busca tradicional e em busca por IA: título e descrição (tamanho e
duplicidade), H1 único, hierarquia de títulos, canonical, Open Graph, dados
estruturados, imagens, links internos, conteúdo mínimo e arquivos de
rastreamento.

Uso:  python scripts/auditar_seo.py
Sai com código 1 se houver problema de severidade ALTA.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("COOKIE_SECURE", "0")

from app import SITE_URL, app  # noqa: E402

ALTA, MEDIA, BAIXA = "ALTA", "MEDIA", "BAIXA"
problemas: list[tuple[str, str, str, str]] = []  # (severidade, url, regra, detalhe)


def falha(sev, url, regra, detalhe=""):
    problemas.append((sev, url, regra, detalhe))


class Pagina(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titulo = ""
        self.meta: dict[str, str] = {}
        self.links: list[str] = []
        self.canonical = ""
        self.heads: list[tuple[int, str]] = []
        self.imgs: list[dict] = []
        self.jsonld: list[str] = []
        self.texto: list[str] = []
        self.lang = ""
        self._em = ""
        self._buf = ""
        self._ld = False
        self._ignora = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self._em = "title"; self._buf = ""
        elif tag == "meta":
            chave = a.get("name") or a.get("property")
            if chave:
                self.meta[chave] = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href", "")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._em = tag; self._buf = ""
        elif tag == "img":
            self.imgs.append(a)
        elif tag == "script":
            if a.get("type") == "application/ld+json":
                self._ld = True; self._buf = ""
            else:
                self._ignora += 1
        elif tag in ("style", "noscript"):
            self._ignora += 1

    def handle_endtag(self, tag):
        if tag == "title" and self._em == "title":
            self.titulo = self._buf.strip(); self._em = ""
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._em == tag:
            self.heads.append((int(tag[1]), re.sub(r"\s+", " ", self._buf).strip())); self._em = ""
        elif tag == "script":
            if self._ld:
                self.jsonld.append(self._buf); self._ld = False
            elif self._ignora:
                self._ignora -= 1
        elif tag in ("style", "noscript") and self._ignora:
            self._ignora -= 1

    def handle_data(self, d):
        if self._em or self._ld:
            self._buf += d
        if not self._ignora and not self._ld:
            self.texto.append(d)


def urls_do_sitemap(cli):
    xml = cli.get("/sitemap.xml").get_data(as_text=True)
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    return [u.replace(SITE_URL, "") or "/" for u in locs]


def tipos_ld(no):
    t = no.get("@type", [])
    return t if isinstance(t, list) else [t]


def checar_jsonld(url, blocos):
    nos = []
    for b in blocos:
        try:
            dado = json.loads(b)
        except ValueError as e:
            falha(ALTA, url, "JSON-LD invalido", str(e)[:80]); continue
        nos += dado.get("@graph", [dado]) if isinstance(dado, dict) else dado

    tipos = {t for n in nos for t in tipos_ld(n)}
    if "Organization" not in tipos and "FinancialService" not in tipos:
        falha(ALTA, url, "sem entidade Organization no JSON-LD")

    for n in nos:
        ts = tipos_ld(n)
        if "BlogPosting" in ts:
            for campo in ("headline", "datePublished", "author", "publisher", "mainEntityOfPage"):
                if campo not in n:
                    falha(ALTA, url, f"BlogPosting sem {campo}")
            if "image" not in n:
                falha(MEDIA, url, "BlogPosting sem image (perde destaque no Google Discover)")
        if "FAQPage" in ts:
            for q in n.get("mainEntity", []):
                if not q.get("name") or not q.get("acceptedAnswer", {}).get("text"):
                    falha(ALTA, url, "FAQPage com pergunta ou resposta vazia")
        if "BreadcrumbList" in ts:
            pos = [i.get("position") for i in n.get("itemListElement", [])]
            if pos != list(range(1, len(pos) + 1)):
                falha(ALTA, url, "BreadcrumbList com posicoes fora de ordem", str(pos))
        if "FinancialService" in ts and "Organization" in ts:
            for campo in ("name", "url", "logo", "address", "telephone"):
                if campo not in n:
                    falha(MEDIA, url, f"Organization sem {campo}")
    return tipos


def main() -> int:
    cli = app.test_client()
    urls = urls_do_sitemap(cli)
    print(f"Auditando {len(urls)} URLs do sitemap\n")

    titulos, descricoes = defaultdict(list), defaultdict(list)
    linhas = []

    for u in urls:
        r = cli.get(u)
        if r.status_code != 200:
            falha(ALTA, u, f"retorna {r.status_code}"); continue
        pg = Pagina(); pg.feed(r.get_data(as_text=True))
        desc = pg.meta.get("description", "")
        texto = re.sub(r"\s+", " ", " ".join(pg.texto)).strip()
        palavras = len(texto.split())

        # --- titulo
        t = pg.titulo
        if not t:
            falha(ALTA, u, "sem <title>")
        else:
            titulos[t].append(u)
            if len(t) > 62:
                falha(MEDIA, u, "title longo (corta nos resultados)", f"{len(t)} car.: {t[:50]}...")
            if len(t) < 20:
                falha(BAIXA, u, "title curto demais", f"{len(t)} car.: {t}")

        # --- descricao
        if not desc:
            falha(ALTA, u, "sem meta description")
        else:
            descricoes[desc].append(u)
            if len(desc) > 165:
                falha(MEDIA, u, "description longa (corta)", f"{len(desc)} car.")
            if len(desc) < 70:
                falha(MEDIA, u, "description curta", f"{len(desc)} car.")

        # --- h1 e hierarquia
        h1s = [h for h in pg.heads if h[0] == 1]
        if len(h1s) != 1:
            falha(ALTA, u, "deveria ter exatamente 1 H1", f"tem {len(h1s)}")
        ant = 0
        for nivel, txt in pg.heads:
            if ant and nivel > ant + 1:
                falha(BAIXA, u, "salto na hierarquia de titulos", f"H{ant} -> H{nivel}: {txt[:40]}")
                break
            ant = nivel

        # --- canonical e idioma
        esperado = SITE_URL + (u if u != "/" else "")
        if pg.canonical != esperado and pg.canonical != esperado + "/":
            falha(ALTA, u, "canonical diferente da URL", f"{pg.canonical} != {esperado}")
        if pg.lang != "pt-BR":
            falha(MEDIA, u, "lang diferente de pt-BR", pg.lang)
        if "viewport" not in pg.meta:
            falha(ALTA, u, "sem meta viewport")

        # --- compartilhamento
        for k in ("og:title", "og:description", "og:image", "og:url", "twitter:card"):
            if not pg.meta.get(k):
                falha(MEDIA, u, f"sem {k}")
        if pg.meta.get("og:image", "").startswith("http://"):
            falha(MEDIA, u, "og:image em http")

        # --- imagens
        for im in pg.imgs:
            src = im.get("src", "")
            if "alt" not in im:
                falha(ALTA, u, "imagem sem alt", src[:50])
            if not (im.get("width") and im.get("height")) and "vlibras" not in src:
                falha(BAIXA, u, "imagem sem width/height (causa salto de layout)", src[:50])

        # --- conteudo
        if palavras < 120 and u not in ("/busca",):
            falha(MEDIA, u, "conteudo fino", f"{palavras} palavras")

        # --- links internos
        for href in pg.links:
            if href.startswith("/") and not href.startswith("//"):
                alvo = href.split("#")[0].split("?")[0] or u
                if alvo.startswith("/static/") or alvo.startswith("/media/"):
                    rr = cli.get(alvo)
                else:
                    rr = cli.get(alvo)
                if rr.status_code not in (200, 301, 302):
                    falha(ALTA, u, "link interno quebrado", f"{href} -> {rr.status_code}")

        tipos = checar_jsonld(u, pg.jsonld)
        linhas.append((u, len(t), len(desc), palavras, ",".join(sorted(tipos - {"FinancialService"}))[:34]))

    # --- duplicidades entre paginas
    for t, lista in titulos.items():
        if len(lista) > 1:
            falha(ALTA, ", ".join(lista[:3]), "title duplicado", t[:60])
    for d, lista in descricoes.items():
        if len(lista) > 1:
            falha(MEDIA, ", ".join(lista[:3]), "description duplicada", d[:60])

    # --- arquivos de rastreamento
    robots = cli.get("/robots.txt").get_data(as_text=True)
    if "Sitemap:" not in robots:
        falha(ALTA, "/robots.txt", "sem linha Sitemap")
    for caminho in ("/admin", "/busca"):
        if f"Disallow: {caminho}" not in robots:
            falha(MEDIA, "/robots.txt", f"nao bloqueia {caminho}")
    if cli.get("/llms.txt").status_code != 200:
        falha(BAIXA, "/llms.txt", "ausente")
    for p in ("/admin", "/admin/entrar", "/busca?q=x"):
        h = cli.get(p, follow_redirects=True).get_data(as_text=True)
        if "noindex" not in h and "noindex" not in (cli.get(p, follow_redirects=True).headers.get("X-Robots-Tag", "")):
            falha(ALTA, p, "pagina que nao deve ser indexada sem noindex")

    # --- tabela
    print(f"{'URL':42} {'title':>5} {'desc':>5} {'pal.':>5}  schema")
    print("-" * 100)
    for u, lt, ld, pal, sch in linhas:
        print(f"{u[:42]:42} {lt:>5} {ld:>5} {pal:>5}  {sch}")

    ordem = {ALTA: 0, MEDIA: 1, BAIXA: 2}
    problemas.sort(key=lambda p: (ordem[p[0]], p[1]))
    print(f"\n{'=' * 100}\nPROBLEMAS: {len(problemas)}")
    for sev in (ALTA, MEDIA, BAIXA):
        grupo = [p for p in problemas if p[0] == sev]
        if not grupo:
            continue
        print(f"\n[{sev}] {len(grupo)}")
        for _, url, regra, det in grupo:
            print(f"  {url[:46]:46} {regra}" + (f"  ({det})" if det else ""))
    if not problemas:
        print("Nenhum problema encontrado.")

    return 1 if any(p[0] == ALTA for p in problemas) else 0


if __name__ == "__main__":
    sys.exit(main())
