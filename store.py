"""Armazenamento dos conteúdos editáveis (posts e imagens enviadas).

Tudo que o painel de publicação grava vive em DATA_DIR, que em produção é um
volume persistente. O que vem versionado no repositório (static/data/posts.json
e static/img/posts/) funciona apenas como semente, copiada na primeira
inicialização quando o volume ainda está vazio.

Sem dependências além da Pillow: o bloqueio entre processos usa um arquivo de
trava, que funciona igual em Linux e Windows.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import threading
import time
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import date

from PIL import Image, ImageOps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.abspath(os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data")))
POSTS_FILE = os.path.join(DATA_DIR, "posts.json")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
LOG_FILE = os.path.join(DATA_DIR, "admin.log")

# Semente versionada no repositório.
SEED_POSTS = os.path.join(BASE_DIR, "static", "data", "posts.json")
SEED_IMAGES = os.path.join(BASE_DIR, "static", "img", "posts")

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

CATEGORIAS = ["Institucional", "Cooperativismo", "Comunidade", "Segurança",
              "Saúde", "Crédito", "Educação financeira", "Eventos", "Notícias"]

IMG_MD_LARGURA = 640          # variante media, usada nos cartoes e no celular
IMG_MAX_BYTES = 8 * 1024 * 1024
IMG_MAX_LARGURA = 1600
IMG_FORMATOS = {"JPEG", "PNG", "WEBP"}

# Recusa imagens gigantes antes de decodificar (proteção contra "bomba" de pixels).
Image.MAX_IMAGE_PIXELS = 40_000_000

_thread_lock = threading.Lock()


# --------------------------------------------------------------------------
# Inicialização
# --------------------------------------------------------------------------

def iniciar() -> None:
    """Cria as pastas e semeia o volume, uma unica vez.

    A semente (posts e imagens originais) so e copiada quando o volume ainda nao
    tem posts.json. Depois disso o volume e a fonte da verdade: o que a equipe
    apagar pelo painel nao volta a cada deploy.
    """
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    if os.path.exists(POSTS_FILE):
        _garantir_variantes()
        return

    if os.path.exists(SEED_POSTS):
        shutil.copyfile(SEED_POSTS, POSTS_FILE)
        if os.path.isdir(SEED_IMAGES):
            for nome in os.listdir(SEED_IMAGES):
                destino = os.path.join(UPLOADS_DIR, nome)
                if not os.path.exists(destino):
                    shutil.copyfile(os.path.join(SEED_IMAGES, nome), destino)
    else:
        with open(POSTS_FILE, "w", encoding="utf-8") as fh:
            fh.write("[]")
    _garantir_variantes()


def _garantir_variantes() -> None:
    """Gera a versao media das imagens que ainda nao a tem. Barato e idempotente."""
    for nome in os.listdir(UPLOADS_DIR):
        gerar_md(nome)


# --------------------------------------------------------------------------
# Bloqueio entre processos
# --------------------------------------------------------------------------

@contextmanager
def _bloqueio(timeout: float = 10.0):
    caminho = POSTS_FILE + ".lock"
    limite = time.time() + timeout
    with _thread_lock:
        while True:
            try:
                fd = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                # trava esquecida por um processo que caiu
                try:
                    if time.time() - os.path.getmtime(caminho) > 30:
                        os.remove(caminho)
                        continue
                except OSError:
                    pass
                if time.time() > limite:
                    raise TimeoutError("Não foi possível obter o bloqueio de gravação.")
                time.sleep(0.05)
        try:
            yield
        finally:
            os.close(fd)
            try:
                os.remove(caminho)
            except OSError:
                pass


# --------------------------------------------------------------------------
# Leitura e escrita
# --------------------------------------------------------------------------

class ArmazenamentoCorrompido(RuntimeError):
    """posts.json existe, mas nao pode ser lido. Nada deve ser gravado por cima."""


_ultimo_bom: list[dict] = []


def _ler(estrito: bool = False) -> list[dict]:
    """Le os posts.

    Leitura publica (estrito=False): em erro transitorio tenta de novo e, se o
    arquivo estiver ilegivel, serve a ultima copia boa em memoria em vez de
    mostrar o site vazio.

    Escrita (estrito=True): arquivo ilegivel levanta erro. Gravar em cima de um
    JSON que so parecia vazio apagaria o conteudo inteiro.
    """
    global _ultimo_bom
    ultimo_erro: Exception | None = None

    for _ in range(8):
        try:
            with open(POSTS_FILE, encoding="utf-8") as fh:
                dados = json.load(fh)
            if not isinstance(dados, list):
                raise ValueError("posts.json nao e uma lista")
            _ultimo_bom = dados
            return dados
        except FileNotFoundError:
            return []
        except (OSError, ValueError) as exc:
            # no Windows, um leitor concorrente pode barrar a troca do arquivo
            ultimo_erro = exc
            time.sleep(0.04)

    if estrito:
        raise ArmazenamentoCorrompido(f"Nao foi possivel ler {POSTS_FILE}: {ultimo_erro}")
    return list(_ultimo_bom)


def _gravar(posts: list[dict]) -> None:
    tmp = POSTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(posts, fh, ensure_ascii=False, indent=1)
        fh.flush()
        os.fsync(fh.fileno())

    # copia de seguranca da versao anterior: protege de erro de edicao manual
    if os.path.exists(POSTS_FILE):
        try:
            shutil.copyfile(POSTS_FILE, POSTS_FILE + ".bak")
        except OSError:
            pass

    # troca atomica. No Windows, falha enquanto alguem le o arquivo: insiste.
    for tentativa in range(60):
        try:
            os.replace(tmp, POSTS_FILE)
            return
        except PermissionError:
            if tentativa == 59:
                raise
            time.sleep(0.05)


def _normalizar(post: dict) -> dict:
    post.setdefault("publicado", True)
    post.setdefault("subtitulo", "")
    post.setdefault("imagem", "")
    post.setdefault("resumo", "")
    post.setdefault("paragrafos", [])
    return post


def todos() -> list[dict]:
    """Todos os posts, rascunhos inclusive, do mais novo para o mais antigo."""
    posts = [_normalizar(p) for p in _ler()]
    posts.sort(key=lambda p: p.get("data_iso", ""), reverse=True)
    # ordem manual (painel): quem tem "ordem" vem primeiro, do menor para o maior
    posts.sort(key=lambda p: p["ordem"] if isinstance(p.get("ordem"), int) else 10**9)
    return posts


def publicados() -> list[dict]:
    return [p for p in todos() if p.get("publicado", True)]


def obter(slug: str) -> dict | None:
    return next((p for p in todos() if p["slug"] == slug), None)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def data_por_extenso(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def slugificar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:80].strip("-") or "conteudo"


def _slug_livre(base: str, existentes: set[str]) -> str:
    if base not in existentes:
        return base
    n = 2
    while f"{base}-{n}" in existentes:
        n += 1
    return f"{base}-{n}"


def resumo_automatico(paragrafos: list[str], limite: int = 155, minimo: int = 110) -> str:
    """Resumo para busca e compartilhamento.

    Junta parágrafos até ter corpo suficiente: o primeiro, sozinho, costuma ser
    uma frase de abertura curta demais para servir de meta description.
    """
    texto = ""
    for par in paragrafos:
        par = par.strip()
        if not par:
            continue
        texto = f"{texto} {par}".strip()
        if len(texto) >= minimo:
            break
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(",;:.- ") + "..."


# --------------------------------------------------------------------------
# Operações de edição
# --------------------------------------------------------------------------

def criar(campos: dict) -> dict:
    with _bloqueio():
        posts = _ler(estrito=True)
        slug = _slug_livre(slugificar(campos["titulo"]), {p["slug"] for p in posts})
        post = _montar(campos, slug)
        ordens = [p["ordem"] for p in posts if isinstance(p.get("ordem"), int)]
        if ordens:
            post["ordem"] = min(ordens) - 1        # novo conteúdo entra em primeiro
        posts.append(post)
        _gravar(posts)
    registrar("criou", slug)
    return post


def atualizar(slug: str, campos: dict) -> dict | None:
    with _bloqueio():
        posts = _ler(estrito=True)
        for i, p in enumerate(posts):
            if p["slug"] == slug:
                imagem_antiga = p.get("imagem", "")
                novo = _montar(campos, slug)
                if campos.get("imagem"):
                    pass                                   # upload novo substitui
                elif campos.get("remover_imagem"):
                    novo["imagem"] = ""                    # pediu para tirar
                else:
                    novo["imagem"] = imagem_antiga         # mantém a atual
                if isinstance(p.get("ordem"), int):
                    novo["ordem"] = p["ordem"]             # edição não muda a posição
                posts[i] = novo
                _gravar(posts)
                break
        else:
            return None
    # a imagem substituída ou removida deixa de ser usada
    if imagem_antiga and novo["imagem"] != imagem_antiga:
        _remover_imagem_orfa(imagem_antiga)
    registrar("editou", slug)
    return novo


def alternar_publicacao(slug: str) -> bool | None:
    with _bloqueio():
        posts = _ler(estrito=True)
        for p in posts:
            if p["slug"] == slug:
                p["publicado"] = not p.get("publicado", True)
                estado = p["publicado"]
                _gravar(posts)
                break
        else:
            return None
    registrar("publicou" if estado else "despublicou", slug)
    return estado


def reordenar(slugs: list[str]) -> bool:
    """Grava a ordem manual. `slugs` é a lista na ordem desejada;
    o que faltar nela vai para o fim, na ordem atual."""
    with _bloqueio():
        posts = _ler(estrito=True)
        existentes = {p["slug"] for p in posts}
        pedida = [s for s in dict.fromkeys(slugs) if s in existentes]
        ordenados = sorted(
            (_normalizar(p) for p in posts),
            key=lambda p: (p["ordem"] if isinstance(p.get("ordem"), int) else 10**9,
                           -int(p.get("data_iso", "0").replace("-", "") or 0)))
        final = pedida + [p["slug"] for p in ordenados if p["slug"] not in pedida]
        posicao = {s: i + 1 for i, s in enumerate(final)}
        for p in posts:
            p["ordem"] = posicao[p["slug"]]
        _gravar(posts)
    registrar("reordenou", ",".join(pedida[:3]))
    return True


def excluir(slug: str) -> bool:
    with _bloqueio():
        posts = _ler(estrito=True)
        alvo = next((p for p in posts if p["slug"] == slug), None)
        if not alvo:
            return False
        posts = [p for p in posts if p["slug"] != slug]
        _gravar(posts)
    _remover_imagem_orfa(alvo.get("imagem", ""))
    registrar("excluiu", slug)
    return True


def _montar(campos: dict, slug: str) -> dict:
    paragrafos = campos["paragrafos"]
    return {
        "slug": slug,
        "titulo": campos["titulo"],
        "subtitulo": campos.get("subtitulo", ""),
        "categoria": campos["categoria"],
        "data": data_por_extenso(campos["data_iso"]),
        "data_iso": campos["data_iso"],
        "resumo": campos.get("resumo") or resumo_automatico(paragrafos),
        "imagem": campos.get("imagem", ""),
        "paragrafos": paragrafos,
        "publicado": bool(campos.get("publicado", True)),
    }


# --------------------------------------------------------------------------
# Imagens
# --------------------------------------------------------------------------

class ImagemInvalida(ValueError):
    pass


def salvar_imagem(arquivo) -> str:
    """Valida, reprocessa e grava uma imagem enviada. Devolve o nome do arquivo.

    A imagem é decodificada e gravada de novo como JPEG: isso descarta EXIF
    (inclusive localização), metadados e qualquer conteúdo que não seja pixel.
    """
    dados = arquivo.read(IMG_MAX_BYTES + 1)
    if not dados:
        raise ImagemInvalida("O arquivo está vazio.")
    if len(dados) > IMG_MAX_BYTES:
        raise ImagemInvalida("A imagem passa de 8 MB.")

    try:
        Image.open(io.BytesIO(dados)).verify()
        im = Image.open(io.BytesIO(dados))
    except Exception:
        raise ImagemInvalida("O arquivo não é uma imagem válida.")

    if im.format not in IMG_FORMATOS:
        raise ImagemInvalida("Use uma imagem JPG, PNG ou WebP.")

    try:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            fundo = Image.new("RGB", im.size, (255, 255, 255))
            fundo.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
            im = fundo
        else:
            im = im.convert("RGB")
    except Exception:
        raise ImagemInvalida("Não foi possível processar a imagem.")

    if im.width > IMG_MAX_LARGURA:
        altura = round(im.height * IMG_MAX_LARGURA / im.width)
        im = im.resize((IMG_MAX_LARGURA, altura), Image.LANCZOS)

    nome = uuid.uuid4().hex[:16] + ".jpg"
    im.save(os.path.join(UPLOADS_DIR, nome), "JPEG",
            quality=85, optimize=True, progressive=True)
    gerar_md(nome)
    return nome


def variante_md(nome: str) -> str:
    base, ext = os.path.splitext(nome)
    return f"{base}-md{ext}"


def gerar_md(nome: str) -> None:
    """Cria a versao de 640px de uma imagem enviada, se ainda nao existir."""
    if nome.endswith(("-md.jpg", "-md.jpeg", "-md.png", "-md.webp")):
        return
    origem = os.path.join(UPLOADS_DIR, nome)
    destino = os.path.join(UPLOADS_DIR, variante_md(nome))
    if os.path.exists(destino) or not os.path.exists(origem):
        return
    try:
        with Image.open(origem) as im:
            if im.width <= IMG_MD_LARGURA:
                return  # ja e pequena: o srcset usa so a original
            im = im.convert("RGB")
            altura = round(im.height * IMG_MD_LARGURA / im.width)
            im.resize((IMG_MD_LARGURA, altura), Image.LANCZOS).save(
                destino, "JPEG", quality=82, optimize=True, progressive=True)
    except Exception:
        pass


def descartar_imagem(nome: str) -> None:
    """Remove uma imagem recém-enviada cujo formulário foi recusado."""
    _remover_imagem_orfa(nome)


def _remover_imagem_orfa(nome: str) -> None:
    """Apaga a imagem só se nenhum post a usa mais."""
    if not nome or "/" in nome or "\\" in nome:
        return
    if any(p.get("imagem") == nome for p in _ler()):
        return
    for arquivo in (nome, variante_md(nome)):
        try:
            os.remove(os.path.join(UPLOADS_DIR, arquivo))
        except OSError:
            pass


# --------------------------------------------------------------------------
# Registro de ações
# --------------------------------------------------------------------------

def registrar(acao: str, slug: str, ip: str = "") -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{acao}\t{slug}\t{ip}\n")
    except OSError:
        pass
