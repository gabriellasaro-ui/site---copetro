from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta

from flask import (Flask, Response, abort, redirect, render_template, request,
                   send_from_directory)
from werkzeug.middleware.proxy_fix import ProxyFix

import store
from admin import bp as admin_bp

try:  # compressao opcional: sem a biblioteca o site funciona igual, so mais pesado
    from flask_compress import Compress
except ImportError:  # pragma: no cover
    Compress = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# URL canônica do site. Em produção, defina SITE_URL no ambiente.
SITE_URL = os.environ.get("SITE_URL", "https://www.copetro.com.br").rstrip("/")

# Numero que recebe os formularios pelo WhatsApp: formato internacional, so digitos.
# O padrao e o numero oficial da Copetro, (31) 3201-4412, que atende no WhatsApp Business.
# Para trocar sem mexer no codigo, defina WHATSAPP_NUMERO no ambiente.
WHATSAPP_NUMERO = os.environ.get("WHATSAPP_NUMERO", "553132014412")

# pastas explícitas: funciona rodando de qualquer diretório (python "caminho/app.py")
app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

# Em desenvolvimento recarrega o HTML a cada request; em producao, nao.
_DEV = os.environ.get("FLASK_ENV", "production") == "development"
app.config["TEMPLATES_AUTO_RELOAD"] = _DEV

# --- sessao do painel -----------------------------------------------------
# A chave vem de SECRET_KEY. Sem ela, deriva da senha do painel: estavel entre
# os processos do gunicorn e invalida as sessoes quando a senha muda.
_segredo = os.environ.get("SECRET_KEY") or hashlib.sha256(
    ("copetro-painel|" + (os.environ.get("ADMIN_PASSWORD_HASH")
                          or os.environ.get("ADMIN_PASSWORD") or "")).encode()
).hexdigest()
app.secret_key = _segredo
app.config.update(
    SESSION_COOKIE_NAME="copetro_admin",
    SESSION_COOKIE_PATH="/admin",          # o cookie nunca vai para as paginas publicas
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1") != "0",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,   # teto do upload (a imagem tem limite proprio)
    SEND_FILE_MAX_AGE_DEFAULT=timedelta(days=30),
    JSON_AS_ASCII=False,
)

# Atras do proxy do EasyPanel (Traefik): confia em X-Forwarded-* para saber que a
# conexao original era HTTPS e qual o IP real. Desligue com TRUST_PROXY=0 se o
# container for exposto direto.
if os.environ.get("TRUST_PROXY", "1") != "0":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

if Compress is not None:
    Compress(app)

# volume de dados: cria as pastas e semeia o conteudo na primeira execucao
store.iniciar()
app.register_blueprint(admin_bp)

# Registro único de páginas: alimenta o sitemap.xml e o llms.txt.
# (slug, prioridade, frequência, título, resumo para o llms.txt)
PAGES = [
    ("index", "1.0", "weekly", "Home",
     "Apresenta a Copetro, os principais serviços (empréstimo, área do "
     "associado, convênios) e as últimas notícias."),
    ("emprestimo", "0.9", "monthly", "Empréstimo",
     "Linhas de crédito para associados, simulador de parcelas, passo a passo "
     "da contratação e dúvidas frequentes sobre empréstimo."),
    ("a-copetro", "0.8", "monthly", "A Copetro",
     "Quem somos, visão, missão, princípios, estatuto social e as "
     "regulamentações que regem a cooperativa."),
    ("cooperativismo", "0.8", "monthly", "Cooperativismo",
     "O que é cooperativismo, cooperativismo de crédito, os 7 princípios, os "
     "símbolos e os direitos e deveres do associado."),
    ("convenios", "0.6", "monthly", "Convênios",
     "Benefícios e condições exclusivas para associados em saúde, educação, "
     "comércio e serviços."),
    ("conteudos", "0.6", "weekly", "Conteúdos",
     "Notícias, dicas e informações sobre cooperativismo e educação financeira."),
    ("regulamentacoes", "0.7", "yearly", "Regulamentações",
     "Políticas, manuais e regulamentos públicos da cooperativa: ouvidoria, "
     "código de ética, regimento interno, prevenção à lavagem de dinheiro, "
     "segurança cibernética e proteção de dados."),
    ("canal-de-denuncias", "0.6", "yearly", "Canal de Denúncias",
     "Canal para denúncia de ilicitudes e violações do Código de Ética. "
     "Pode ser anônima, pelo telefone (31) 3889-7155, das 12h30 às 18h30."),
    ("ouvidoria", "0.7", "yearly", "Ouvidoria",
     "Canal de última instância para reclamações não resolvidas no atendimento. "
     "Telefone 0800-042-0003 e e-mail ouvidoria@copetro.org.br."),
    ("onde-estamos", "0.6", "yearly", "Onde estamos",
     "Endereço da sede em Belo Horizonte, horário de atendimento e como chegar."),
    ("acessibilidade", "0.3", "yearly", "Acessibilidade",
     "Recursos de acessibilidade do site e como relatar barreiras encontradas."),
    ("fale-conosco", "0.7", "monthly", "Fale Conosco",
     "Canais de atendimento, formulário de contato, como se associar e "
     "perguntas frequentes."),
    ("politica-de-privacidade", "0.3", "yearly", "Política de Privacidade",
     "Como a Copetro trata dados pessoais, conforme a LGPD (Lei 13.709/2018)."),
    ("politica-de-cookies", "0.3", "yearly", "Política de Cookies",
     "Quais cookies o site utiliza e como gerenciar suas preferências."),
]

PAGE_SLUGS = {slug for slug, *_ in PAGES}

# Documentos e convenios sao conteudo versionado no repositorio.
# Os posts, que o painel edita, vivem no volume de dados (ver store.py).
_DOCS_FILE = os.path.join(STATIC_DIR, "data", "documentos.json")
_CONVENIOS_FILE = os.path.join(STATIC_DIR, "data", "convenios.json")


def carregar_posts():
    """Posts publicados, do mais novo para o mais antigo. Rascunhos ficam de fora."""
    return store.publicados()


def carregar_documentos():
    """Politicas e manuais publicos, agrupados na ordem do JSON."""
    try:
        with open(_DOCS_FILE, encoding="utf-8") as fh:
            docs = json.load(fh)
    except (OSError, ValueError):
        return []
    grupos = {}
    for d in docs:
        grupos.setdefault(d["grupo"], []).append(d)
    return list(grupos.items())


def carregar_convenios():
    """Rede de parceiros, agrupada por area."""
    try:
        with open(_CONVENIOS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def page_url(slug):
    return SITE_URL + ("/" if slug == "index" else f"/{slug}")


@app.route("/")
def home():
    return render_template("index.html", posts=carregar_posts()[:4])


@app.route("/conteudos")
def conteudos():
    return render_template("conteudos.html", posts=carregar_posts())


@app.route("/conteudos/<slug>")
def conteudo(slug):
    posts = carregar_posts()
    post = next((p for p in posts if p["slug"] == slug), None)
    if post is None:
        abort(404)
    outros = [p for p in posts if p["slug"] != slug][:3]
    return render_template("conteudo.html", post=post, outros=outros)


# Termos extras de busca por pagina (sinonimos que o usuario digita,
# mas que nao aparecem no titulo nem no resumo)
BUSCA_EXTRA = {
    "emprestimo": "credito simulador parcela financiamento consignado antecipacao 13o plr taxa juros",
    "a-copetro": "quem somos historia missao visao principios estatuto",
    "cooperativismo": "cooperativa principios simbolos direitos deveres assembleia",
    "fale-conosco": "contato telefone email endereco duvidas faq associar",
    "ouvidoria": "reclamacao protocolo bacen 0800 manifestacao sugestao elogio",
    "canal-de-denuncias": "denuncia ilicitude anonima etica fraude assedio compliance",
    "regulamentacoes": "politicas manuais documentos pdf codigo de etica regimento balanco estatuto",
    "onde-estamos": "endereco sede mapa como chegar horario atendimento presencial",
    "acessibilidade": "libras vlibras leitor de tela teclado contraste inclusao",
    "convenios": "beneficios parceiros descontos vantagens",
    "area-do-associado": "login acesso senha portal",
    "politica-de-privacidade": "lgpd dados pessoais titular dpo encarregado",
    "politica-de-cookies": "cookies consentimento rastreamento",
    "conteudos": "noticias blog artigos dicas",
}


def indice_busca():
    """Monta o indice em memoria: paginas do registro + conteudos publicados."""
    itens = []
    for slug, _, _, titulo, resumo in PAGES:
        url = "/" if slug == "index" else f"/{slug}"
        itens.append({
            "titulo": titulo, "url": url, "tipo": "Página", "resumo": resumo,
            "busca": f"{titulo} {resumo} {BUSCA_EXTRA.get(slug, '')}".lower(),
        })
    for a in carregar_posts():
        itens.append({
            "titulo": a["titulo"], "url": f"/conteudos/{a['slug']}",
            "tipo": a["categoria"], "resumo": a["resumo"],
            "busca": f"{a['titulo']} {a['subtitulo']} {' '.join(a['paragrafos'])}".lower(),
        })
    return itens


def sem_acento(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


@app.route("/busca")
def busca():
    termo = (request.args.get("q") or "").strip()
    resultados = []
    if len(termo) >= 2:
        alvo = sem_acento(termo.lower())
        palavras = [p for p in alvo.split() if len(p) > 1]
        for item in indice_busca():
            campo = sem_acento(item["busca"])
            titulo = sem_acento(item["titulo"].lower())
            acertos = sum(1 for p in palavras if p in campo)
            if not acertos:
                continue
            # titulo pesa mais que corpo
            peso = acertos * 10 + sum(5 for p in palavras if p in titulo)
            resultados.append((peso, item))
        resultados.sort(key=lambda r: -r[0])
    return render_template("busca.html", termo=termo,
                           resultados=[r[1] for r in resultados])


@app.route("/convenios")
def convenios():
    grupos = carregar_convenios()
    total = sum(len(g["parceiros"]) for g in grupos)
    return render_template("convenios.html", grupos=grupos, total=total)


@app.route("/ilicitudes")
def ilicitudes():
    """Endereço antigo do canal de denúncias: mantém os links que já circulam."""
    return redirect("/canal-de-denuncias", code=301)


@app.route("/regulamentacoes")
def regulamentacoes():
    return render_template("regulamentacoes.html", grupos=carregar_documentos())


# Templates que dependem de contexto da view e nao podem ser servidos
# pela rota curinga (seriam renderizados vazios ou quebrariam).
TEMPLATES_COM_CONTEXTO = {"busca", "conteudo", "conteudos", "regulamentacoes",
                          "convenios", "index"}


@app.route("/lp/<slug>")
@app.route("/<slug>")
def lp(slug):
    # templates internos (base, parciais) não são páginas navegáveis
    if slug.startswith("_") or slug in TEMPLATES_COM_CONTEXTO:
        abort(404)
    path = os.path.join(TEMPLATES_DIR, f"{slug}.html")
    if not os.path.exists(path):
        abort(404)
    return render_template(f"{slug}.html")


@app.route("/lp/help")
def list_slugs():
    slug_list = [
        f for f in os.listdir(TEMPLATES_DIR)
        if f.endswith(".html") and not f.startswith("_")
    ]
    return {str(i): f.replace(".html", "") for i, f in enumerate(slug_list)}


# --------------------------------------------------------------------------
# SEO / GEO
# --------------------------------------------------------------------------

@app.route("/robots.txt")
def robots():
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /lp/",
        "Disallow: /admin",
        "Disallow: /busca",
        "",
        "# Rastreadores de IA: conteúdo liberado para indexação e citação.",
        "User-agent: GPTBot",
        "Allow: /",
        "",
        "User-agent: OAI-SearchBot",
        "Allow: /",
        "",
        "User-agent: ClaudeBot",
        "Allow: /",
        "",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        "User-agent: Google-Extended",
        "Allow: /",
        "",
        "User-agent: Applebot-Extended",
        "Allow: /",
        "",
        "User-agent: CCBot",
        "Allow: /",
        "",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


def _ultima_alteracao(slug: str) -> str:
    """Data de modificacao do template da pagina: lastmod real, nao a data de hoje."""
    nome = "index" if slug == "index" else slug
    caminho = os.path.join(TEMPLATES_DIR, f"{nome}.html")
    try:
        return datetime.fromtimestamp(os.path.getmtime(caminho)).date().isoformat()
    except OSError:
        return date.today().isoformat()


@app.route("/sitemap.xml")
def sitemap():
    posts = carregar_posts()
    # a listagem e a home mudam quando sai conteudo novo
    ultimo_post = posts[0]["data_iso"] if posts else None

    def mod(slug):
        base = _ultima_alteracao(slug)
        if ultimo_post and slug in ("index", "conteudos"):
            return max(base, ultimo_post)
        return base

    urls = "".join(
        f"<url><loc>{page_url(slug)}</loc><lastmod>{mod(slug)}</lastmod>"
        f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        for slug, prio, freq, _, _ in PAGES
    )
    urls += "".join(
        f"<url><loc>{SITE_URL}/conteudos/{p['slug']}</loc>"
        f"<lastmod>{p['data_iso']}</lastmod>"
        f"<changefreq>yearly</changefreq><priority>0.5</priority></url>"
        for p in carregar_posts()
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    return Response(xml, mimetype="application/xml")


@app.route("/llms.txt")
def llms_txt():
    """Resumo estruturado do site para modelos de linguagem (padrão llms.txt)."""
    lines = [
        "# Copetro",
        "",
        "> Cooperativa de Economia e Crédito Mútuo fundada em 1970, com atuação em "
        "Minas Gerais. Oferece linhas de crédito, benefícios e serviços financeiros "
        "exclusivamente aos seus associados, no modelo de cooperativismo de crédito.",
        "",
        "Na Copetro, quem usa os serviços também é dono da cooperativa: as decisões "
        "são tomadas em assembleia, no princípio de um associado, um voto. As "
        "sobras apuradas no exercício retornam aos associados.",
        "",
        "## Páginas",
        "",
    ]
    for slug, _, _, title, summary in PAGES:
        lines.append(f"- [{title}]({page_url(slug)}): {summary}")

    artigos = carregar_posts()
    if artigos:
        lines += ["", "## Conteúdos publicados", ""]
        for a in artigos:
            lines.append(f"- [{a['titulo']}]({SITE_URL}/conteudos/{a['slug']}) "
                         f"({a['data']}, {a['categoria']})")

    lines += [
        "",
        "## Observações",
        "",
        "- Os produtos de crédito são destinados a associados da cooperativa.",
        "- O simulador de empréstimo do site usa taxa ilustrativa e não constitui "
        "proposta de crédito; as condições dependem de análise.",
        "- A Copetro nunca solicita senhas, códigos de verificação ou pagamentos "
        "por telefone, e-mail ou mensagem.",
        f"- Contato: {SITE_URL}/fale-conosco",
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


# --------------------------------------------------------------------------

@app.context_processor
def inject_seo():
    """Disponibiliza a URL canônica da página atual para os templates."""
    path = request.path.rstrip("/") or "/"
    return {"site_url": SITE_URL, "canonical_url": SITE_URL + path,
            "whatsapp": WHATSAPP_NUMERO}


# --------------------------------------------------------------------------
# Midia enviada pelo painel
# --------------------------------------------------------------------------

@app.route("/media/<path:nome>")
def media(nome):
    """Serve as imagens do volume de dados. send_from_directory recusa '..'."""
    return send_from_directory(store.UPLOADS_DIR, nome, max_age=2592000)


@app.template_filter("truncar")
def truncar(texto, limite=155):
    """Corta em fim de palavra, sem deixar pontuacao pendurada, para meta description."""
    t = " ".join((texto or "").split())
    if len(t) <= limite:
        return t
    return t[:limite].rsplit(" ", 1)[0].rstrip(",;:.- ") + "..."


@app.template_global("media_url")
def media_url(nome):
    from flask import url_for
    return url_for("media", nome=nome)


@app.template_global("asset")
def asset(caminho):
    """URL de um CSS/JS do site, preferindo a versao minificada quando ela existe.

    A .min so vale se for MAIS NOVA que o original: assim, depois de editar o
    codigo sem rodar scripts/minificar.py, o site serve o original e nao uma
    copia velha. ASSET_MIN=0 desliga a escolha por completo.
    """
    from flask import url_for
    if os.environ.get("ASSET_MIN", "1") != "0":
        base, ext = os.path.splitext(caminho)
        mini = f"{base}.min{ext}"
        try:
            if (os.path.getmtime(os.path.join(STATIC_DIR, mini))
                    >= os.path.getmtime(os.path.join(STATIC_DIR, caminho))):
                caminho = mini
        except OSError:
            pass
    return url_for("static", filename=caminho)


@app.template_global("media_srcset")
def media_srcset(nome):
    """srcset com a versao de 640px e a original, para o navegador escolher."""
    from flask import url_for
    md = store.variante_md(nome)
    if not os.path.exists(os.path.join(store.UPLOADS_DIR, md)):
        return ""
    return f"{url_for('media', nome=md)} {store.IMG_MD_LARGURA}w, {url_for('media', nome=nome)} {_largura(nome)}w"


_dimensoes: dict = {}


def _dim(nome):
    """(largura, altura) reais da imagem, lidas do cabecalho e guardadas em memoria."""
    from PIL import Image
    caminho = os.path.join(store.UPLOADS_DIR, nome)
    try:
        chave = (nome, os.path.getmtime(caminho))
    except OSError:
        return (880, 550)
    if chave not in _dimensoes:
        try:
            with Image.open(caminho) as im:
                _dimensoes[chave] = (im.width, im.height)
        except Exception:
            _dimensoes[chave] = (880, 550)
    return _dimensoes[chave]


def _largura(nome):
    return _dim(nome)[0]


@app.template_global("media_dim")
def media_dim(nome):
    """width/height reais para os atributos do <img>: reservam o espaco e evitam salto de layout."""
    from markupsafe import Markup
    w, h = _dim(nome)
    return Markup(f'width="{w}" height="{h}"')  # Markup: sem isso o Jinja escapa as aspas


@app.url_defaults
def _versionar_arquivos(endpoint, values):
    """Acrescenta ?v=<mtime> aos arquivos estaticos e de midia.

    Com a versao na URL, o navegador pode guardar por 30 dias e, ao trocar um
    arquivo, a URL muda sozinha: nada de cache velho nem de limpar na mao.
    """
    if "v" in values:
        return
    if endpoint == "static" and values.get("filename"):
        base, chave = STATIC_DIR, "filename"
    elif endpoint == "media" and values.get("nome"):
        base, chave = store.UPLOADS_DIR, "nome"
    else:
        return
    try:
        values["v"] = int(os.path.getmtime(os.path.join(base, values[chave])))
    except OSError:
        pass


# --------------------------------------------------------------------------
# Saude, cabecalhos de seguranca e cache
# --------------------------------------------------------------------------

@app.route("/healthz")
def healthz():
    """Verificacao de saude para o Docker e o EasyPanel: leve, sem template."""
    return Response("ok", mimetype="text/plain",
                    headers={"Cache-Control": "no-store"})


# Politica de conteudo. As fontes sao auto-hospedadas (static/fonts), entao nada do
# Google e carregado. Cada origem externa liberada abaixo tem um motivo:
#   vlibras.gov.br + CDN      tradutor de Libras do Governo Federal. O plugin
#                             redireciona para o jsDelivr, entao liberamos so o
#                             caminho do repositorio oficial, nao o CDN inteiro
#   openstreetmap.org         mapa embutido (so em frame-src)
#   frame-src vlibras.gov.br  o painel do VLibras roda num iframe do proprio dominio
# 'unsafe-inline' em style-src existe por causa dos atributos style="" nos
# templates; scripts inline nao sao permitidos.
_VL = "https://vlibras.gov.br https://cdn.jsdelivr.net/gh/spbgovbr-vlibras/"
_CSP = "; ".join([
    "default-src 'self'",
    f"script-src 'self' {_VL} 'wasm-unsafe-eval'",
    f"style-src 'self' 'unsafe-inline' {_VL}",
    f"font-src 'self' data: {_VL}",
    f"img-src 'self' data: blob: {_VL}",
    f"media-src 'self' blob: {_VL}",
    f"connect-src 'self' {_VL}",
    "frame-src https://www.openstreetmap.org https://vlibras.gov.br",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'",
])
_CSP_MODO = os.environ.get("CSP_MODE", "enforce")  # enforce | report-only | off


@app.after_request
def _cabecalhos(resp):
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "SAMEORIGIN")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy",
                 "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")

    if request.is_secure:  # so vale quando a conexao original foi HTTPS
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    if _CSP_MODO == "enforce":
        h.setdefault("Content-Security-Policy", _CSP)
    elif _CSP_MODO == "report-only":
        h.setdefault("Content-Security-Policy-Report-Only", _CSP)

    # cache: arquivo versionado (?v=) e imutavel; HTML sempre revalida
    if request.endpoint in ("static", "media") and "v" in request.args:
        h["Cache-Control"] = "public, max-age=2592000, immutable"
    elif resp.mimetype == "text/html" and "Cache-Control" not in h:
        h["Cache-Control"] = "no-cache"
    return resp


@app.errorhandler(404)
def not_found(e):
    return render_template("_404.html"), 404


@app.errorhandler(400)
def requisicao_ruim(e):
    return Response(getattr(e, "description", "Requisição inválida."),
                    status=400, mimetype="text/plain; charset=utf-8")


@app.errorhandler(413)
def grande_demais(e):
    return Response("O arquivo enviado é grande demais.", status=413,
                    mimetype="text/plain; charset=utf-8")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "6000")), debug=_DEV)
