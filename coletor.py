#!/usr/bin/env python3
"""
Coletor da tabela da LuME — Vision / Cartas Contempladas

Lê a tabela pública de cotas e escreve `cotas.json` no formato que o
selecao.py consome.

Sem dependências externas: usa só a biblioteca padrão, para rodar em
qualquer Mac sem pip install.

Uso:
    python3 coletor.py                        # busca da web
    python3 coletor.py --html lume.html       # parseia um HTML já salvo
    python3 coletor.py --csv lista.csv        # usa o "Download da lista completa"

O QUE A TABELA REAL FAZ (conferido em 29/08/2026, 209 linhas):

  * A coluna DISPONÍVEL não traz a palavra "Reservada". As cotas fora de
    venda são marcadas pela CLASSE da linha (`bgVermelho`) e não têm o
    link "VER". Filtrar por texto não pega nenhuma — por isso lemos a
    classe do <tr>.
  * As parcelas compostas ficam na coluna VALOR DAS PARCELAS
    ("120 X 6.986 + 3 X 6.003 + 53 X 5.058,00"), não na coluna PARCELAS,
    que traz só o total (176). Há casos de dois e de três blocos.
  * `bgCinza` é só zebra de linha alternada — não significa nada.

REGRA INEGOCIÁVEL: o ID de cota da LuME (?cota=41641) NUNCA é lido nem
gravado. Ele não existe no cotas.json.
"""
import argparse, csv, json, os, re, sys, unicodedata
from datetime import date, datetime
from html.parser import HTMLParser

URL = "https://cartascontempladas.com.br/ver-todas-as-cartas-contempladas/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# classes de <tr> que marcam cota indisponível
CLASSES_INDISPONIVEL = ("bgvermelho",)


# ---------------------------------------------------------------- utilidades

def sem_acento(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def dinheiro(txt):
    """'R$ 19.200' -> 19200.0 ; '2.932,91' -> 2932.91 ; '' -> None"""
    if not txt:
        return None
    t = re.sub(r"[^\d,.\-]", "", txt)
    if not t:
        return None
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


BLOCO_RE = re.compile(r"(\d+)\s*[xX]\s*([\d.,]+)")


def blocos_de_parcela(valor_txt, total_txt):
    """
    Devolve [(qtd, valor), ...].

      '607'                                   -> [(None, 607.0)]  simples
      '53 X 1.809 + 20 X 957'                 -> [(53,1809.0),(20,957.0)]
      '120 X 6.986 + 3 X 6.003 + 53 X 5.058'  -> três blocos

    `total_txt` é a coluna PARCELAS, usada quando o valor é simples.
    """
    achados = BLOCO_RE.findall(valor_txt or "")
    if achados:
        return [(int(n), dinheiro(v)) for n, v in achados]
    v = dinheiro(valor_txt)
    n = re.search(r"\d+", total_txt or "")
    return [(int(n.group()) if n else None, v)] if v is not None else []


def codigo_estavel(c):
    """
    Código curto e sempre o mesmo para a mesma cota. O IM-001 do card é
    posicional e muda todo dia; no site o parceiro precisa citar uma carta
    no WhatsApp e você achar. Derivado dos dados da cota — nunca do ID da
    LuME, que não entra em lugar nenhum.
    """
    import hashlib
    base = f'{c["seg"]}|{c["credito"]}|{c["entrada"]}|{c["adm"].strip().lower()}|{c["parcelas"]}'
    h = hashlib.sha1(base.encode()).digest()
    alfabeto = "ACDEFGHJKLMNPQRTUVWXY3479"   # sem letras/números ambíguos
    n = int.from_bytes(h[:4], "big")
    sufixo = "".join(alfabeto[(n >> (5 * i)) % len(alfabeto)] for i in range(4))
    return ("IM" if c["seg"] == "imovel" else "VE") + "-" + sufixo


def segmento(txt):
    t = sem_acento(txt)
    if "imov" in t or "imob" in t:
        return "imovel"
    if "veic" in t or "auto" in t or "carro" in t or "moto" in t:
        return "veiculo"
    return None


def data_br(txt):
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", txt or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(), "%d/%m/%Y").date()
    except ValueError:
        return None


# ------------------------------------------------------------- leitura HTML

class LeitorTabela(HTMLParser):
    """
    Extrai as tabelas como listas de linhas. Cada linha é
    {"cels": [texto, ...], "classe": "bgVermelho", "links": ["VER", ...]}.
    A classe do <tr> importa: é ela que marca cota indisponível.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tabelas = []
        self._tab = self._lin = self._cel = None
        self._classe = self._href = ""

    def handle_starttag(self, tag, attrs):
        at = dict(attrs)
        if tag == "table":
            self._tab = []
        elif tag == "tr" and self._tab is not None:
            self._lin, self._classe, self._href = [], at.get("class", "") or "", ""
        elif tag == "a" and self._lin is not None and not self._href:
            # o href leva o ID da cota. Ele serve só para buscar as regras
            # nesta execução e NUNCA é gravado em lugar nenhum.
            href = at.get("href") or ""
            if "informacao-da-carta" in href or "cota=" in href:
                self._href = href
        elif tag in ("td", "th") and self._lin is not None:
            self._cel = []
        elif self._cel is not None and tag in ("br", "p", "div", "li", "tr"):
            # sem isto, "Valor das<br>Parcelas" vira "Valor dasParcelas"
            # e o casamento de colunas falha
            self._cel.append(" ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._cel is not None:
            self._cel.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cel is not None:
            self._lin.append(re.sub(r"\s+", " ", "".join(self._cel)).strip())
            self._cel = None
        elif tag == "tr" and self._lin is not None:
            if self._lin:
                self._tab.append({"cels": self._lin, "classe": self._classe,
                                  "href": self._href})
            self._lin = None
        elif tag == "table" and self._tab is not None:
            if self._tab:
                self.tabelas.append(self._tab)
            self._tab = None


COLUNAS = {
    "seg":      ("segmento", "bem"),
    "adm":      ("administradora", "adm"),
    "credito":  ("valor do credito", "credito"),
    "entrada":  ("entrada",),
    "parcelas": ("parcelas", "prazo"),
    "valor":    ("valor das parcelas", "valor da parcela", "valor parcela"),
    "venc":     ("vencimento",),
    "status":   ("disponivel", "status", "situacao"),
}


def mapear_colunas(cabecalho):
    """Casa nome de coluna com campo. Não depende da ordem das colunas."""
    idx = {}
    limpos = [sem_acento(c) for c in cabecalho]
    for campo, apelidos in COLUNAS.items():
        for apelido in apelidos:                 # apelido mais específico 1º
            for i, nome in enumerate(limpos):
                if i in idx.values() or apelido not in nome:
                    continue
                idx[campo] = i
                break
            if campo in idx:
                break
    return idx


def escolher_tabela(tabelas):
    melhor, melhor_idx = None, None
    for t in tabelas:
        if len(t) < 2:
            continue
        idx = mapear_colunas(t[0]["cels"])
        if "credito" in idx and "entrada" in idx:
            if melhor is None or len(t) > len(melhor):
                melhor, melhor_idx = t, idx
    return melhor, melhor_idx


def linhas_do_html(texto):
    p = LeitorTabela()
    p.feed(texto)
    tabela, idx = escolher_tabela(p.tabelas)
    if not tabela:
        raise SystemExit("Não achei a tabela de cotas no HTML. "
                         "A página mudou de estrutura — ajuste COLUNAS.")
    faltando = [c for c in ("seg", "adm", "credito", "entrada", "parcelas",
                            "valor", "venc") if c not in idx]
    if faltando:
        raise SystemExit(f"Colunas não encontradas: {faltando}. "
                         f"Cabeçalho lido: {tabela[0]['cels']}")
    maior = max(idx.values())
    for linha in tabela[1:]:
        cels = linha["cels"]
        if len(cels) <= maior:
            continue
        r = {k: cels[i] for k, i in idx.items()}
        r["_classe"] = linha["classe"]
        r["_href"] = linha.get("href", "")
        yield r


def linhas_do_csv(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        amostra = f.read(4096)
        f.seek(0)
        sep = ";" if amostra.count(";") > amostra.count(",") else ","
        leitor = csv.reader(f, delimiter=sep)
        idx = mapear_colunas(next(leitor))
        maior = max(idx.values(), default=0)
        for linha in leitor:
            if len(linha) > maior:
                r = {k: linha[i] for k, i in idx.items()}
                r["_classe"] = ""
                yield r


CACHE_REGRAS = "regras-lume.json"


def chave_regra(r):
    """As regras são iguais para toda cota da mesma administradora e
    segmento — conferido em 08/09/2026 comparando três cotas de quatro
    grupos. Por isso o coletor busca ~30 páginas, não uma por cota."""
    return f'{(r.get("seg") or "").strip().upper()}|{(r.get("adm") or "").strip().upper()}'


def buscar_regras(brutas, forcar=False):
    """
    Lê a página de cada cota só uma vez por administradora e guarda o bloco
    'REGRAS PARA USO'. O ID da cota é usado para montar a URL e descartado
    em seguida — não entra no cache nem no cotas.json.
    """
    import urllib.request
    cache = {}
    if os.path.isfile(CACHE_REGRAS) and not forcar:
        try:
            cache = json.load(open(CACHE_REGRAS, encoding="utf-8"))
        except ValueError:
            cache = {}

    faltando = {}
    for r in brutas:
        k = chave_regra(r)
        if k not in cache and r.get("_href"):
            faltando.setdefault(k, r["_href"])

    if faltando:
        print(f"buscando regras de {len(faltando)} administradoras…")
    for k, href in faltando.items():
        try:
            req = urllib.request.Request(href, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                cache[k] = extrair_regras(resp.read().decode("utf-8", "replace"))
        except Exception as e:
            print(f"  aviso: não consegui as regras de {k} ({e})")
            cache[k] = ""
    if faltando:
        with open(CACHE_REGRAS, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    return cache


class LeitorRegras(HTMLParser):
    """Extrai o texto de <div class="listaRegras">."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.dentro, self.nivel, self.partes = False, 0, []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "") or ""
        if not self.dentro and "listaregras" in cls.lower():
            self.dentro, self.nivel = True, 1
        elif self.dentro:
            self.nivel += 1
        if self.dentro and tag in ("br", "p", "div", "li", "h2", "h3"):
            self.partes.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.dentro:
            self.partes.append(data)

    def handle_endtag(self, tag):
        if self.dentro:
            self.nivel -= 1
            if self.nivel <= 0:
                self.dentro = False


def extrair_regras(texto):
    p = LeitorRegras()
    p.feed(texto)
    bruto = "".join(p.partes)
    linhas = [re.sub(r"[ \t]+", " ", l).strip() for l in bruto.split("\n")]
    linhas = [l for l in linhas if l and not re.fullmatch(r"REGRAS PARA USO:?", l, re.I)]
    return limpar_regras("\n".join(linhas))


def limpar_regras(texto):
    """
    A LuME emenda os itens sem separador — "8 anosCaminhões/VUC: 08 anos".
    Quebra antes de cada rótulo novo (Maiúscula … dois-pontos) e tira o
    título repetido.
    """
    t = re.sub(r"^\s*REGRAS PARA USO:?\s*", "", texto, flags=re.I)
    t = re.sub(r"(?<=[a-zà-ú0-9).,\]])(?=[A-ZÀ-Ú][^\n:]{2,45}:)", "\n", t)
    # "Taxa de Transferência" costuma vir sem dois-pontos e emendada
    t = re.sub(r"(?<=[a-zà-ú0-9).,\]])(?=Taxa de Transfer)", "\n", t, flags=re.I)
    t = re.sub(r"(?<=[a-zà-ú0-9).,\]])(?=Forma de cobran)", "\n", t, flags=re.I)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return "\n".join(l.strip() for l in t.split("\n") if l.strip()).strip()


def baixar():
    import urllib.request
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


# ------------------------------------------------------------------ limpeza

def indisponivel(r):
    classe = sem_acento(r.get("_classe", ""))
    if any(c in classe for c in CLASSES_INDISPONIVEL):
        return True
    st = sem_acento(r.get("status", ""))
    return bool(st) and ("reserv" in st or "vendid" in st or "indispon" in st)


def normalizar(bruta, hoje):
    rel = {"lidas": 0, "indisponiveis": 0, "vencidas": 0, "gemeas": 0,
           "compostas": 0, "incompletas": 0, "divergencia_total": 0}
    vistas, saida = set(), []

    for r in bruta:
        rel["lidas"] += 1

        # 1. cota fora de venda (classe bgVermelho / status reservado)
        if indisponivel(r):
            rel["indisponiveis"] += 1
            continue

        seg = segmento(r.get("seg", ""))
        credito = dinheiro(r.get("credito"))
        entrada = dinheiro(r.get("entrada"))
        venc = data_br(r.get("venc", ""))
        blocos = blocos_de_parcela(r.get("valor"), r.get("parcelas"))

        if not (seg and credito and entrada and venc and blocos):
            rel["incompletas"] += 1
            continue

        # 2. vencimento já passado
        if venc < hoje:
            rel["vencidas"] += 1
            continue

        composta = len(blocos) > 1
        if composta:
            rel["compostas"] += 1
            n_parcelas = sum(n for n, _ in blocos if n)
            total_col = re.search(r"\d+", r.get("parcelas") or "")
            if total_col and int(total_col.group()) != n_parcelas:
                # a soma dos blocos não bate com a coluna PARCELAS:
                # confiamos nos blocos e registramos o caso
                rel["divergencia_total"] += 1
        else:
            n_parcelas = blocos[0][0]

        v_parcela = blocos[0][1]
        if not (n_parcelas and v_parcela):
            rel["incompletas"] += 1
            continue

        cota = {
            "_regra": chave_regra(r),
            "seg": seg,
            "adm": (r.get("adm") or "").strip(),
            "credito": round(credito),
            "entrada": round(entrada),
            "parcelas": n_parcelas,
            "valorParcela": round(v_parcela, 2),
            "venc": venc.strftime("%d/%m/%Y"),
        }
        if composta:
            cota["composta"] = True
            cota["blocos"] = [{"parcelas": n, "valor": round(v, 2)}
                              for n, v in blocos if n and v]

        cota["cod"] = codigo_estavel(cota)

        # 3. cotas gêmeas — mesmo crédito, entrada e administradora
        chave = (cota["credito"], cota["entrada"], sem_acento(cota["adm"]))
        if chave in vistas:
            rel["gemeas"] += 1
            continue
        vistas.add(chave)

        saida.append(cota)

    return saida, rel


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Coletor da tabela da LuME")
    ap.add_argument("--html", help="parseia um HTML já salvo em vez de buscar")
    ap.add_argument("--csv", help="usa o CSV do 'Download da lista completa'")
    ap.add_argument("--saida", default="cotas.json")
    ap.add_argument("--hoje", help="data de referência DD/MM/AAAA (padrão: hoje)")
    ap.add_argument("--sem-regras", action="store_true",
                    help="não busca as regras de uso (mais rápido, offline)")
    ap.add_argument("--regras-forcar", action="store_true",
                    help="rebusca todas as regras, ignorando o cache")
    a = ap.parse_args()

    hoje = data_br(a.hoje) if a.hoje else date.today()

    if a.csv:
        bruta, origem = list(linhas_do_csv(a.csv)), a.csv
    else:
        texto = open(a.html, encoding="utf-8", errors="replace").read() \
            if a.html else baixar()
        bruta, origem = list(linhas_do_html(texto)), (a.html or URL)

    cotas, rel = normalizar(bruta, hoje)

    regras = {} if a.sem_regras else buscar_regras(bruta, a.regras_forcar)
    if os.path.isfile(CACHE_REGRAS) and a.sem_regras:
        regras = json.load(open(CACHE_REGRAS, encoding="utf-8"))
    sem = 0
    for c in cotas:
        c["regras"] = regras.get(c.pop("_regra", ""), "")
        sem += not c["regras"]
    if sem:
        print(f"  {sem} cotas sem texto de regras")

    with open(a.saida, "w", encoding="utf-8") as f:
        json.dump(cotas, f, ensure_ascii=False, indent=1)

    print(f"origem: {origem}")
    print(f"{rel['lidas']} linhas lidas")
    print(f"  - {rel['indisponiveis']} indisponíveis (linha marcada em vermelho)")
    print(f"  - {rel['vencidas']} com vencimento anterior a {hoje.strftime('%d/%m/%Y')}")
    print(f"  - {rel['gemeas']} cotas gêmeas")
    print(f"  - {rel['incompletas']} com campo faltando ou ilegível")
    print(f"{len(cotas)} cotas válidas → {a.saida}")
    print(f"  ({rel['compostas']} de parcela composta, mantidas e marcadas)")
    if rel["divergencia_total"]:
        print(f"  atenção: em {rel['divergencia_total']} cotas a soma dos blocos "
              f"não bate com a coluna PARCELAS — usei a soma dos blocos")

    im = sum(1 for c in cotas if c["seg"] == "imovel")
    print(f"\nsegmentos: {im} imóveis, {len(cotas) - im} veículos")


if __name__ == "__main__":
    main()
