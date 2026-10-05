"""Painel de publicação de conteúdos.

Acesso por senha única, definida no ambiente (ADMIN_PASSWORD ou, melhor,
ADMIN_PASSWORD_HASH). Sem uma das duas, o painel inteiro responde 404, como se
não existisse. O cookie de sessão só trafega em /admin, nunca nas páginas
públicas.
"""
from __future__ import annotations

import hmac
import os
import re
import secrets
import time
from datetime import date, datetime
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, make_response, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash

import store

bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="templates")

SENHA = os.environ.get("ADMIN_PASSWORD", "")
SENHA_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
ATIVO = bool(SENHA or SENHA_HASH)

# Limite de tentativas de login por IP: 5 erros bloqueiam por 15 minutos.
_MAX_TENTATIVAS = 5
_JANELA = 15 * 60
_tentativas: dict[str, list[float]] = {}


# --------------------------------------------------------------------------
# Segurança
# --------------------------------------------------------------------------

@bp.errorhandler(store.ArmazenamentoCorrompido)
def _armazenamento_corrompido(exc):
    return render_template("admin/erro.html", mensagem=(
        "O arquivo de conteúdos está ilegível e nada foi alterado. "
        "Existe uma cópia de segurança em posts.json.bak no volume de dados.")), 500


@bp.before_request
def _antes():
    if not ATIVO:
        abort(404)


@bp.after_request
def _depois(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def _token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


@bp.app_context_processor
def _contexto():
    return {"csrf_token": _token}


def _checar_csrf() -> None:
    enviado = request.form.get("csrf", "")
    esperado = session.get("csrf", "")
    if not esperado or not hmac.compare_digest(enviado, esperado):
        abort(400, "Sessão expirada. Recarregue a página e tente de novo.")


def exige_login(view):
    @wraps(view)
    def interno(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin.entrar", prox=request.path))
        return view(*a, **kw)
    return interno


def _senha_confere(informada: str) -> bool:
    if SENHA_HASH:
        return check_password_hash(SENHA_HASH, informada)
    return hmac.compare_digest(informada.encode(), SENHA.encode())


def _bloqueado(ip: str) -> bool:
    agora = time.time()
    recentes = [t for t in _tentativas.get(ip, []) if agora - t < _JANELA]
    _tentativas[ip] = recentes
    return len(recentes) >= _MAX_TENTATIVAS


# --------------------------------------------------------------------------
# Sessão
# --------------------------------------------------------------------------

@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    if session.get("admin"):
        return redirect(url_for("admin.lista"))

    erro = ""
    ip = request.remote_addr or "?"

    if request.method == "POST":
        _checar_csrf()
        if _bloqueado(ip):
            erro = "Muitas tentativas. Aguarde alguns minutos e tente de novo."
        elif _senha_confere(request.form.get("senha", "")):
            _tentativas.pop(ip, None)
            session.clear()
            session["admin"] = True
            session.permanent = True
            store.registrar("entrou", "-", ip)
            destino = request.args.get("prox", "")
            # só redireciona para dentro do painel
            if not destino.startswith("/admin") or destino.startswith("//"):
                destino = url_for("admin.lista")
            return redirect(destino)
        else:
            _tentativas.setdefault(ip, []).append(time.time())
            store.registrar("login-falhou", "-", ip)
            time.sleep(0.6)  # desestimula tentativa em massa
            erro = "Senha incorreta."

    return render_template("admin/entrar.html", erro=erro)


@bp.route("/sair", methods=["POST"])
def sair():
    _checar_csrf()
    session.clear()
    return redirect(url_for("admin.entrar"))


# --------------------------------------------------------------------------
# Conteúdos
# --------------------------------------------------------------------------

@bp.route("")      # /admin, sem barra: a rota curinga /<slug> do site o capturaria
@bp.route("/")
@exige_login
def lista():
    return render_template("admin/lista.html", posts=store.todos())


@bp.route("/novo", methods=["GET", "POST"])
@exige_login
def novo():
    if request.method == "POST":
        _checar_csrf()
        campos, erros = _ler_formulario(request.form, request.files)
        if not erros:
            post = store.criar(campos)
            flash("Conteúdo criado.", "ok")
            return redirect(url_for("admin.editar", slug=post["slug"]))
        return render_template("admin/form.html", post=_para_form(request.form),
                               erros=erros, novo=True,
                               categorias=store.CATEGORIAS), 400

    return render_template("admin/form.html", post={
        "titulo": "", "subtitulo": "", "categoria": store.CATEGORIAS[0],
        "data_iso": date.today().isoformat(), "corpo": "", "resumo": "",
        "imagem": "", "publicado": True,
    }, erros=[], novo=True, categorias=store.CATEGORIAS)


@bp.route("/<slug>/editar", methods=["GET", "POST"])
@exige_login
def editar(slug):
    post = store.obter(slug)
    if not post:
        abort(404)

    if request.method == "POST":
        _checar_csrf()
        campos, erros = _ler_formulario(request.form, request.files)
        if not erros:
            store.atualizar(slug, campos)
            flash("Alterações salvas.", "ok")
            return redirect(url_for("admin.editar", slug=slug))
        dados = _para_form(request.form)
        dados["slug"], dados["imagem"] = slug, post.get("imagem", "")
        return render_template("admin/form.html", post=dados, erros=erros,
                               novo=False, categorias=store.CATEGORIAS), 400

    dados = dict(post)
    dados["corpo"] = "\n\n".join(post["paragrafos"])
    return render_template("admin/form.html", post=dados, erros=[], novo=False,
                           categorias=store.CATEGORIAS)


@bp.route("/<slug>/publicar", methods=["POST"])
@exige_login
def publicar(slug):
    _checar_csrf()
    estado = store.alternar_publicacao(slug)
    if estado is None:
        abort(404)
    flash("Conteúdo publicado." if estado else "Conteúdo voltou para rascunho.", "ok")
    return redirect(request.form.get("voltar") or url_for("admin.lista"))


@bp.route("/reordenar", methods=["POST"])
@exige_login
def reordenar():
    """Arrastar e soltar: recebe os slugs na nova ordem."""
    _checar_csrf()
    slugs = [x for x in request.form.get("ordem", "").split(",") if x]
    store.reordenar(slugs)
    return ("", 204)


@bp.route("/<slug>/mover", methods=["POST"])
@exige_login
def mover(slug):
    """Sem JavaScript: primeiro, subir ou descer uma posição."""
    _checar_csrf()
    slugs = [p["slug"] for p in store.todos()]
    if slug not in slugs:
        abort(404)
    i = slugs.index(slug)
    acao = request.form.get("acao")
    slugs.pop(i)
    novo = {"primeiro": 0, "subir": max(i - 1, 0), "descer": i + 1}.get(acao, i)
    slugs.insert(novo, slug)
    store.reordenar(slugs)
    flash("Conteúdo agora é o primeiro da página." if acao == "primeiro" else "Ordem atualizada.", "ok")
    return redirect(url_for("admin.lista"))


@bp.route("/<slug>/excluir", methods=["POST"])
@exige_login
def excluir(slug):
    _checar_csrf()
    if not store.excluir(slug):
        abort(404)
    flash("Conteúdo excluído.", "ok")
    return redirect(url_for("admin.lista"))


@bp.route("/<slug>/previa")
@exige_login
def previa(slug):
    post = store.obter(slug)
    if not post:
        abort(404)
    outros = [p for p in store.publicados() if p["slug"] != slug][:3]
    return render_template("conteudo.html", post=post, outros=outros, previa=True)


# --------------------------------------------------------------------------
# Leitura e validação do formulário
# --------------------------------------------------------------------------

def _para_form(form) -> dict:
    return {
        "titulo": form.get("titulo", ""),
        "subtitulo": form.get("subtitulo", ""),
        "categoria": form.get("categoria", ""),
        "data_iso": form.get("data_iso", ""),
        "corpo": form.get("corpo", ""),
        "resumo": form.get("resumo", ""),
        "publicado": form.get("publicado") == "1",
        "imagem": "",
    }


def _ler_formulario(form, arquivos) -> tuple[dict, list[str]]:
    erros: list[str] = []

    titulo = re.sub(r"\s+", " ", form.get("titulo", "")).strip()
    subtitulo = re.sub(r"\s+", " ", form.get("subtitulo", "")).strip()
    resumo = re.sub(r"\s+", " ", form.get("resumo", "")).strip()
    categoria = form.get("categoria", "")
    data_iso = form.get("data_iso", "").strip()
    corpo = form.get("corpo", "").replace("\r\n", "\n").replace("\r", "\n")

    if not titulo:
        erros.append("Informe o título.")
    elif len(titulo) > 140:
        erros.append("O título passa de 140 caracteres.")
    if len(subtitulo) > 160:
        erros.append("O subtítulo passa de 160 caracteres.")
    if len(resumo) > 220:
        erros.append("O resumo passa de 220 caracteres.")
    if categoria not in store.CATEGORIAS:
        erros.append("Escolha uma categoria da lista.")

    try:
        datetime.strptime(data_iso, "%Y-%m-%d")
    except ValueError:
        erros.append("Informe uma data válida.")

    paragrafos = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n\s*\n", corpo) if p.strip()]
    if not paragrafos:
        erros.append("Escreva o texto do conteúdo.")
    elif sum(len(p) for p in paragrafos) > 30000:
        erros.append("O texto passa de 30.000 caracteres.")

    imagem = ""
    envio = arquivos.get("imagem")
    if envio and envio.filename:
        try:
            imagem = store.salvar_imagem(envio)
        except store.ImagemInvalida as exc:
            erros.append(str(exc))

    # formulario recusado: a imagem que acabou de subir nao pode ficar orfa no disco
    if erros and imagem:
        store.descartar_imagem(imagem)
        imagem = ""

    campos = {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "resumo": resumo,
        "categoria": categoria,
        "data_iso": data_iso,
        "paragrafos": paragrafos,
        "imagem": imagem,
        "remover_imagem": form.get("remover_imagem") == "1",
        "publicado": form.get("publicado") == "1",
    }
    return campos, erros
