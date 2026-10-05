"""Extrai os posts publicos da Copetro para um JSON servido pelo site."""
import html, json, os, re, urllib.request
from datetime import date
from PIL import Image

BASE = r"C:/Users/Gabriel/Documents/Projetos/site - copetro"
IMGDIR = os.path.join(BASE, "static", "img", "posts")
os.makedirs(IMGDIR, exist_ok=True)

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

# categoria editorial por slug (o WordPress de origem nao usa categorias)
CATEGORIAS = {
    "26-de-agosto-copetro-56-anos-uma-entidade-feita-de-gente": "Institucional",
    "juntos-construimos-mais-que-resultados": "Cooperativismo",
    "homenagem-da-copetro": "Comunidade",
    "proteja-se-contra-golpes-digitais": "Segurança",
    "voce-esta-cuidando-do-seu-sorriso": "Saúde",
}


def buscar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def limpar(txt):
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", txt, flags=re.S | re.I)
    txt = re.sub(r"<br\s*/?>", "\n", txt, flags=re.I)
    txt = re.sub(r"</p>", "\n\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = html.unescape(txt)
    txt = txt.replace("\u00a0", " ").replace("\u2014", ",").replace("\u2013", "-")
    linhas = [re.sub(r"[ \t]+", " ", l).strip() for l in txt.split("\n")]
    return [l for l in linhas if l]


def data_br(iso):
    d = date.fromisoformat(iso[:10])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}", iso[:10]


posts = buscar("https://copetro.org.br/wp-json/wp/v2/posts"
               "?per_page=8&_embed=wp:featuredmedia&_fields=id,date,slug,title,content,_links,_embedded")

saida = []
for p in posts:
    slug = p["slug"]
    titulo = " ".join(limpar(p["title"]["rendered"]))
    paras = limpar(p["content"]["rendered"])

    # a primeira linha do corpo costuma ser um antetitulo/linha fina.
    # so vira subtitulo se nao for a repeticao do proprio titulo.
    def norm(x):
        return re.sub(r"[^a-z0-9]+", "", x.lower())

    subtitulo = ""
    if len(paras) > 1 and len(paras[0]) < 95 and not paras[0].endswith("."):
        cand = paras[0]
        if norm(cand) not in norm(titulo):
            subtitulo = cand if not cand.isupper() else cand.capitalize()
        paras.pop(0)

    # o titulo nunca e alterado alem da normalizacao de caixa
    titulo = re.sub(r"\s{2,}", " ", titulo).strip(" ,-–")
    if titulo.isupper():
        titulo = titulo.capitalize()

    # imagem destacada
    img_nome = ""
    try:
        media = p["_embedded"]["wp:featuredmedia"][0]
        src = media["source_url"]
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            bruto = r.read()
        tmp = os.path.join(IMGDIR, "_tmp")
        open(tmp, "wb").write(bruto)
        im = Image.open(tmp).convert("RGB")
        # apara tarjas brancas
        px = im.load(); w, h = im.size
        branco = lambda y: all(min(px[x, y]) >= 246 for x in range(0, w, 8))
        t = 0
        while t < h and branco(t): t += 1
        b = h - 1
        while b > t and branco(b): b -= 1
        im = im.crop((0, t, w, b + 1))
        cw, ch = im.size
        alvo = 1.6
        if cw / ch > alvo:
            nw = int(ch * alvo); im = im.crop(((cw - nw) // 2, 0, (cw - nw) // 2 + nw, ch))
        else:
            nh = int(cw / alvo); im = im.crop((0, (ch - nh) // 2, cw, (ch - nh) // 2 + nh))
        img_nome = f"{slug}.jpg"
        im.resize((880, 550), Image.LANCZOS).save(
            os.path.join(IMGDIR, img_nome), quality=85, optimize=True, progressive=True)
        os.remove(tmp)
    except Exception as e:
        print("  sem imagem:", slug, e)

    legivel, iso = data_br(p["date"])
    saida.append({
        "slug": slug,
        "titulo": titulo,
        "subtitulo": subtitulo,
        "categoria": CATEGORIAS.get(slug, "Notícias"),
        "data": legivel,
        "data_iso": iso,
        "resumo": (paras[0][:180] + "...") if paras else "",
        "imagem": img_nome,
        "paragrafos": paras,
    })
    print(f"{iso}  {saida[-1]['categoria']:14} {len(paras):>2} par.  {titulo[:52]}")

destino = os.path.join(BASE, "static", "data")
os.makedirs(destino, exist_ok=True)
json.dump(saida, open(os.path.join(destino, "posts.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\n{len(saida)} posts -> static/data/posts.json")
