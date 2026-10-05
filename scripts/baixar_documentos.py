"""Baixa os documentos publicos da Copetro e gera o indice em JSON."""
import json, os, urllib.request

BASE = r"C:/Users/Gabriel/Documents/Projetos/site - copetro"
DEST = os.path.join(BASE, "static", "docs")
os.makedirs(DEST, exist_ok=True)

# (titulo, grupo, arquivo de origem)
DOCS = [
    ("Manual de Ouvidoria", "Atendimento e relacionamento",
     "MANUALDEOUVIDORIARev04.pdf"),
    ("Política Institucional de Relacionamento com Clientes e Usuários", "Atendimento e relacionamento",
     "POLITICAINSTITUCIONALRCRev01.pdf"),

    ("Código de Ética", "Governança",
     "CODIGOETICARev02.pdf"),
    ("Regimento Interno", "Governança",
     "REGIMENTOINTERNOREV06.pdf"),
    ("Regulamento Eleitoral", "Governança",
     "REGULAMENTOELEITORALRev01.pdf"),
    ("Política de Sucessão de Administradores", "Governança",
     "POLITICASUCESSAOADMINISTRADORES.pdf"),
    ("Política de Recrutamento e Seleção", "Governança",
     "POLITICARECRUTAMENTOSELECAORev01.pdf"),

    ("Prevenção Contra Lavagem de Dinheiro", "Conformidade e segurança",
     "PREVENCAOCONTRALAVAGEMDINHEIROrev09.pdf"),
    ("Política de Segurança Cibernética", "Conformidade e segurança",
     "POLITICASEGURANCACIBERNETICARev01.pdf"),
    ("Política Interna de Proteção de Dados", "Conformidade e segurança",
     "POLITICAINTERNAPROTECAODADOS.pdf"),

    ("Política de Responsabilidade Socioambiental", "Responsabilidade socioambiental",
     "POLITICARESPONSABILIDADESOCIOAMBIENTALRev04.pdf"),
]

RAIZ = "https://copetro.org.br/wp-content/uploads/2022/01/"
saida = []

for titulo, grupo, arquivo in DOCS:
    dst = os.path.join(DEST, arquivo)
    try:
        req = urllib.request.Request(RAIZ + arquivo, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dados = r.read()
        if not dados.startswith(b"%PDF"):
            print(f"  !! {arquivo} nao e PDF"); continue
        open(dst, "wb").write(dados)
        kb = len(dados) // 1024
        saida.append({"titulo": titulo, "grupo": grupo, "arquivo": arquivo, "kb": kb})
        print(f"{kb:>5} KB  {titulo}")
    except Exception as e:
        print(f"  !! {arquivo}: {e}")

destino = os.path.join(BASE, "static", "data", "documentos.json")
json.dump(saida, open(destino, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\n{len(saida)} documentos -> static/data/documentos.json")
