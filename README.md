# Site Copetro

Site institucional da **COPETRO, Cooperativa de Economia e Crédito Mútuo dos Petroleiros no Estado de Minas Gerais**, com foco em empréstimo.

Flask + Jinja + CSS e JavaScript puros. Inclui painel de publicação de conteúdos, SEO/GEO, LGPD, acessibilidade auditada e deploy por Docker (EasyPanel).

## Sumário

1. [Rodando localmente](#rodando-localmente)
2. [Deploy no EasyPanel](#deploy-no-easypanel)
3. [Variáveis de ambiente](#variáveis-de-ambiente)
4. [Painel de publicação](#painel-de-publicação)
5. [Estrutura](#estrutura)
6. [Rotas](#rotas)
7. [Conteúdo e dados](#conteúdo-e-dados)
8. [Formulários e WhatsApp](#formulários-e-whatsapp)
9. [SEO e GEO](#seo-e-geo)
10. [LGPD](#lgpd)
11. [Segurança](#segurança)
12. [Acessibilidade e auditorias](#acessibilidade-e-auditorias)
13. [Performance](#performance)
14. [Convenções de design](#convenções-de-design)
15. [Pendências](#pendências)

---

## Rodando localmente

Com Docker:

```bash
docker compose up --build      # http://localhost:6000
```

O compose monta o volume `copetro-data` em `/data` (posts e imagens do painel). Para testar o painel, crie um `.env` a partir de `.env.example` e defina `ADMIN_PASSWORD`.

Sem Docker:

```bash
pip install -r requirements.txt

# PowerShell
$env:ADMIN_PASSWORD="uma-senha"; $env:COOKIE_SECURE="0"; python app.py
# Linux/macOS
ADMIN_PASSWORD=uma-senha COOKIE_SECURE=0 python app.py
```

`COOKIE_SECURE=0` só é necessário em `http://` local. Sem `DATA_DIR`, os dados ficam em `./data/`.

**Ao subir um servidor de teste, mate antes qualquer processo na porta.** No Windows dois processos podem ocupar a mesma porta e o antigo continua respondendo com código velho.

---

## Deploy no EasyPanel

> **O `docker build` não foi executado no ambiente de desenvolvimento** (sem Docker instalado). O Dockerfile, o entrypoint e o gunicorn tiveram a lógica testada por partes, mas o primeiro build real acontece no EasyPanel. Se falhar, o log do build indica a linha.

1. **Repositório.** O EasyPanel constrói a partir do Git. Esta pasta ainda não é um repositório: rode `git init`, faça o commit e envie ao GitHub (`.gitignore` e `.gitattributes` já estão prontos).
2. **App.** *Project → Create → App*.
3. **Source.** GitHub, escolha repositório e branch. **Build: Dockerfile** (caminho `Dockerfile`).
4. **Environment.** Cole as variáveis da seção abaixo. Obrigatórias: `SITE_URL`, `ADMIN_PASSWORD_HASH` (ou `ADMIN_PASSWORD`), `SECRET_KEY`.
5. **Mounts (obrigatório).** Volume com caminho **`/data`**. Sem ele, cada deploy apaga o que a equipe publicou.
6. **Domains.** Domínio, **porta `6000`**, HTTPS ligado.
7. **Deploy.**

Conferência após o deploy:

| Teste | Esperado |
|---|---|
| `/healthz` | `ok` |
| `/` | site com fontes e imagens |
| `/admin` | tela de login (404 se a senha não foi definida) |
| `/robots.txt`, `/sitemap.xml` | URLs com o seu domínio |

Atualizar: `git push` e *Deploy*. O que foi publicado pelo painel permanece, pois vive no volume.

Backup: tudo que é editável está em `/data` (`posts.json`, `posts.json.bak`, `uploads/`, `admin.log`). Ative o backup do volume no EasyPanel.

| Sintoma | Causa provável |
|---|---|
| 502 | Porta do domínio diferente de `6000` |
| `/admin` dá 404 | Senha não definida |
| Login não "pega" | `COOKIE_SECURE=1` acessando por `http://` |
| Conteúdos somem a cada deploy | Volume `/data` não montado |
| Canonical/sitemap com domínio errado | `SITE_URL` não definido |

---

## Variáveis de ambiente

Modelo comentado em [`.env.example`](.env.example).

| Variável | Padrão | Função |
|---|---|---|
| `SITE_URL` | `https://www.copetro.com.br` | URL pública sem barra final. Canonical, Open Graph, JSON-LD, sitemap, llms.txt. **Defina em produção.** |
| `ADMIN_PASSWORD_HASH` | vazio | Hash da senha do painel (preferível). |
| `ADMIN_PASSWORD` | vazio | Senha em texto. Sem uma das duas, `/admin` responde 404. |
| `SECRET_KEY` | derivada da senha | Assinatura das sessões do painel. |
| `WHATSAPP_NUMERO` | `553132014412` | Destino dos formulários, só dígitos com DDI. |
| `COOKIE_SECURE` | `1` | Cookie do painel só em HTTPS. `0` apenas em http local. |
| `TRUST_PROXY` | `1` | Confia em `X-Forwarded-*` (EasyPanel). `0` se exposto direto. |
| `CSP_MODE` | `enforce` | `enforce`, `report-only` ou `off`. |
| `DATA_DIR` | `/data` (container) | Posts e uploads. |
| `PORT` | `6000` | Porta interna. |
| `WEB_CONCURRENCY` / `WEB_THREADS` | `1` / `8` | Processos e threads do gunicorn. |
| `LOG_LEVEL` | `info` | Nível de log. |
| `ASSET_MIN` | `1` | `0` serve CSS/JS sem minificar. |

Gerar hash e chave:

```bash
python -c "from werkzeug.security import generate_password_hash as g; print(g('SUA_SENHA'))"
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Painel de publicação

Em **`/admin`**. Manual para a equipe, sem linguagem técnica: [`GUIA-DO-PAINEL.md`](GUIA-DO-PAINEL.md).

Permite criar, editar, publicar/despublicar e excluir conteúdos, enviar imagem de capa e pré-visualizar rascunhos.

- **Armazenamento** (`store.py`): `posts.json` no volume, gravação atômica com bloqueio por arquivo e cópia `.bak`. Se o arquivo ficar ilegível, nada é sobrescrito: o painel mostra erro e o site público segue com a última cópia boa em memória.
- **Semente:** os conteúdos originais (`static/data/posts.json`, `static/img/posts/`) são copiados para o volume **uma única vez**. Depois o volume manda: o que for excluído não volta no deploy.
- **Rascunhos** ficam fora de página pública, listagem, home, busca, sitemap e llms.txt. A prévia só existe no painel, com `noindex`.
- **Texto simples**, escapado na saída: não há HTML vindo do usuário, logo não há XSS por conteúdo.
- **Imagens:** validadas pelo conteúdo, regravadas como JPEG (descarta EXIF), máximo 1600 px e 8 MB; gera variante de 640 px para cartões e celular.

| Proteção | Como |
|---|---|
| Autenticação | Senha única, comparação em tempo constante, suporta hash |
| Força bruta | 5 erros por IP bloqueiam 15 min, com atraso por erro |
| CSRF | Token por sessão em todo POST |
| Sessão | Cookie `HttpOnly`, `SameSite=Lax`, `Secure`, caminho `/admin`, 8 h |
| Indexação | `X-Robots-Tag: noindex`, `no-store`, bloqueado no robots.txt |
| Auditoria | `admin.log` registra login, falhas e cada alteração |

O limite de login vive em memória por processo; por isso o padrão é 1 processo com 8 threads. Para escalar com vários processos ele precisaria de armazenamento compartilhado.

---

## Estrutura

```
app.py                  Rotas, SEO, segurança, cabeçalhos
admin.py                Painel de publicação (blueprint)
store.py                Posts e imagens (volume)
gunicorn.conf.py        Servidor
docker-entrypoint.sh    Prepara o volume e abre mão do root
Dockerfile, docker-compose.yml, .env.example
GUIA-DO-PAINEL.md       Manual da equipe

templates/              _base, páginas do site e admin/
static/css/             style.css, admin.css
static/js/              main.js, admin.js
static/fonts/           Poppins e Inter auto-hospedadas
static/img/             Logo, fotos WebP, hero, og-image, posts/ (semente)
static/docs/            PDFs de políticas e manuais
static/data/            posts.json (semente), documentos.json, convenios.json
scripts/                auditar_seo.py, minificar.py, extrair_posts.py, baixar_documentos.py
fontes/                 Material de trabalho (banners e imagens originais).
                        Fora da imagem Docker e da URL pública.
```

---

## Rotas

| Rota | Página |
|---|---|
| `/` | Home |
| `/a-copetro` | Quem somos, princípios, organização, conselheiros, estatuto |
| `/cooperativismo` | Cooperativismo |
| `/emprestimo` | Opções e simulador |
| `/conteudos`, `/conteudos/<slug>` | Listagem e artigos |
| `/convenios` | Parceiros |
| `/regulamentacoes` | Documentos em PDF |
| `/ouvidoria` | Ouvidoria |
| `/canal-de-denuncias` | Canal de ilicitudes (`/ilicitudes` redireciona 301) |
| `/onde-estamos`, `/fale-conosco` | Sede, mapa, contato |
| `/acessibilidade` | Declaração |
| `/politica-de-privacidade`, `/politica-de-cookies` | LGPD |
| `/area-do-associado` | Login (bloqueado, sem destino) |
| `/busca?q=` | Busca interna (`noindex`) |
| `/admin` | Painel |
| `/media/<arquivo>` | Imagens enviadas pelo painel |
| `/healthz` | Saúde (Docker/EasyPanel) |
| `/robots.txt`, `/sitemap.xml`, `/llms.txt` | Gerados |

**Nova página:** crie o template, acrescente uma linha em `PAGES` (`app.py`) e, se houver sinônimos de busca, em `BUSCA_EXTRA`. Sitemap, llms.txt e busca se atualizam. Se o template depender de contexto da view, inclua o nome em `TEMPLATES_COM_CONTEXTO`, senão a rota curinga `/<slug>` o serve vazio.

---

## Conteúdo e dados

| O que | Onde | Como editar |
|---|---|---|
| Conteúdos | volume `/data/posts.json` | **Painel `/admin`** |
| Convênios | `static/data/convenios.json` | Editar JSON e reimplantar |
| Documentos (PDF) | `static/docs/` + `documentos.json` | Editar e reimplantar |
| Páginas institucionais | `templates/*.html` | Editar e reimplantar |

Identificação da cooperativa (rodapé, Política de Privacidade e JSON-LD; altere nos três):

| Campo | Valor |
|---|---|
| CNPJ | 26.758.433/0001-02 |
| Sede | Av. Paraná, 485, Centro, Belo Horizonte, MG |
| Telefone / e-mail | (31) 3201-4412 / faleconosco@copetro.org.br |
| Ouvidoria | 0800 042 0003 / ouvidoria@copetro.org.br |
| Canal de Denúncias | (31) 3889-7155, 12h30 às 18h30, anônimo |

---

## Formulários e WhatsApp

Todos entregam no WhatsApp, **exceto o login da Área do Associado**: credencial nunca vai para o WhatsApp. Esse formulário fica bloqueado (`data-form-pending`) e o handler genérico ignora qualquer campo `password`.

Para ligar um formulário novo:

```html
<form data-whats-form data-whats-titulo="Assunto" novalidate>
```

O JS usa o `<label>` de cada campo como título, pula os vazios, valida obrigatórios, telefone, e-mail e consentimento LGPD, e abre `wa.me` com o texto pronto. Não há gravação em banco; para integrar um CRM, acrescente um `fetch` antes do `window.open` em `static/js/main.js`.

- **Simulador em duas etapas:** a 1ª qualifica (nome, WhatsApp, e-mail, associado, vínculo, finalidade, valor, prazo, renda, horário, consentimento); a 2ª já vem com valor e prazo. Price com taxa **ilustrativa** de 1,49% a.m. (`data-rate` em `emprestimo.html`).
- Máscaras de telefone e CPF são só apresentação: não confie nelas em back-end.
- O WhatsApp não gera protocolo. Se a Ouvidoria precisar de protocolo formal, ela exigirá back-end próprio.

---

## SEO e GEO

- Title, description, canonical, Open Graph e Twitter Card por página; um H1; hierarquia sem saltos; títulos até 62 caracteres.
- **JSON-LD:** FinancialService/Organization, WebSite, WebPage, BreadcrumbList, FAQPage, Service, DefinedTermSet, ContactPage, Blog e BlogPosting.
- Cada conteúdo tem imagem própria de compartilhamento e `article:*`.
- `sitemap.xml` com `lastmod` real; `robots.txt` libera GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended e CCBot e bloqueia `/admin`, `/busca`; `llms.txt` descreve a cooperativa.
- `noindex` em busca, 404 e prévia.

`python scripts/auditar_seo.py` percorre o sitemap com o cliente de teste do Flask e confere títulos, descrições, H1, canonical, OG, JSON-LD, imagens e links internos. Saída com código 1 em problema alto. Estado atual: **0 problemas**.

---

## LGPD

- Políticas de Privacidade (controlador, finalidades, bases legais, direitos do art. 18, Encarregado) e de Cookies (tabela e categorias).
- Banner de consentimento com aceitar tudo, só necessários e configurar. A escolha fica em `localStorage` e pode ser revista em **Gerenciar cookies** no rodapé.
- O evento `copetro:consentimento` é o gancho para Analytics/Pixel:

```js
document.addEventListener("copetro:consentimento", function (e) {
  if (e.detail.desempenho) { /* Analytics */ }
  if (e.detail.marketing)  { /* Pixel */ }
});
```

Ao ativar uma ferramenta, acrescente seus cookies à Política de Cookies **e** libere o domínio na CSP (`_CSP` em `app.py`).

- Fontes auto-hospedadas (o IP não vai ao Google). Terceiros declarados: **VLibras** e **OpenStreetMap**.

---

## Segurança

- **CSP** em modo enforce, sem script inline, só `self` e o caminho oficial do VLibras (validada com o painel do VLibras aberto).
- HSTS (só se a conexão original foi HTTPS), `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP.
- Arquivos versionados (`?v=`) com cache de 30 dias `immutable`; HTML sempre revalida.
- Container: processo web sem root (o entrypoint ajusta o dono do volume e rebaixa com `setpriv`), healthcheck, `.dockerignore` sem `.env`, `data/` e material de trabalho.

Recurso externo novo é bloqueado pela CSP até ser liberado. É proposital; use `CSP_MODE=report-only` para descobrir o que bloqueia.

---

## Acessibilidade e auditorias

| Ferramenta | Resultado |
|---|---|
| axe-core 4.13 (WCAG 2.0/2.1/2.2 A e AA + boas práticas) | **0 violações** em 46 varreduras (páginas × desktop/mobile × estados: banner, busca, acordeão, simulador etapa 2, menu mobile) |
| Lighthouse 13.5 | Acessibilidade **100**, SEO **100**, Boas práticas 96 (resto é imagem do VLibras, de terceiro) |
| Teclado e reflow (scripts próprios) | 42/42: ordem de foco, indicador visível, sem armadilha, Esc devolve foco, 320 px, zoom 200% e 400%, espaçamento de texto |

Ferramenta automática encontra só parte dos problemas e **não substitui** teste com leitor de tela e com pessoas que usam tecnologia assistiva.

Os scripts de teste ficam fora do projeto. Para reproduzir: instale `axe-core` e `lighthouse` por npm, injete o `axe.min.js` com Playwright (`add_init_script`, por causa da CSP) e rode `axe.run()`; para Lighthouse use `lighthouse http://127.0.0.1:6000/ --preset=desktop`.

---

## Performance

Lighthouse mobile: Performance **95 a 99**, CLS ≤ 0,03. Sustentam isso: fontes locais com preload, fotos WebP dimensionadas (922 KB para 311 KB), `srcset` nos conteúdos, CSS/JS minificados no build (`scripts/minificar.py`; a versão `.min` só é usada se for mais nova que a fonte), compressão e versionamento automático de arquivos.

---

## Convenções de design

| Token | Uso |
|---|---|
| `--green-600` `#009a44` | Detalhes e ícones (não texto) |
| `--green-btn` `#00873c` | Fundo de botão com texto branco |
| `--green-text` `#007a36` | Verde como texto em fundo claro |
| `--muted` | Texto de apoio (5,3:1) |

Poppins nos títulos, Inter no corpo.

- Sem travessões no texto do site.
- **FAQ é sempre a última seção antes do rodapé.**
- Nunca use `.lead` como nome de componente: é a classe do texto de destaque do site inteiro.
- `img { height: auto }`; altura fixa só com `object-fit: cover` proposital.
- A atribuição ao OpenStreetMap abaixo do mapa é exigência de licença. Não remova.
- O botão "Área do Associado" é inerte (`<span>`). Para religar, volte a `<a href>`.

---

## Pendências

Dependem da Copetro:

1. `SITE_URL`, senha do painel e `SECRET_KEY` de produção.
2. **Cargos dos seis conselheiros** (`/a-copetro#conselheiros`).
3. **Nome e e-mail do Encarregado (DPO)** (item da Política de Privacidade).
4. **Taxa real do simulador** e confirmação das modalidades de empréstimo.
5. Tabela de tarifas.
6. Demonstrações financeiras atuais (só há 2022).
7. Revisão jurídica das políticas.
8. Decisão sobre protocolo formal da Ouvidoria.
9. Ligar a Área do Associado quando existir.
10. Confirmar que o número 553132014412 está no WhatsApp Business.
11. Enviar o sitemap ao Search Console e validar o JSON-LD.
12. Teste em Safari/iOS e Android reais (só foi testado em Chromium emulado).
13. Primeiro build Docker no EasyPanel.
