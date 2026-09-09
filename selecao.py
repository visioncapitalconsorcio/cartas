#!/usr/bin/env python3
"""
Seleção diária — Vision / Cartas Contempladas
Aplica as regras de negócio sobre as cotas coletadas e escreve os
arquivos do dia em pastas separadas por grupo.

Uso: python3 selecao.py [cotas.json] [--raiz saida] [--hoje DD/MM/AAAA]
                        [--fone 5535999999999] [--piso 0] [--passo 50]
"""
import argparse, json, math, os, re
from datetime import date, datetime, timedelta

# Valores padrão. Uma marca (marcas/*.json) sobrescreve tudo isto —
# é o que permite Vision e Cartas Alê usarem o mesmo motor.
AGIO_CREDITO = 0.05   # 5% sobre o VALOR DO CRÉDITO, igual nos dois grupos
PASSO  = 50      # arredondamento para cima, em reais
PISO   = 0       # ganho mínimo por carta
VIP_MIN = 100_000
JANELA_REPETICAO = 15   # dias sem republicar a mesma carta
ADMINISTRADORAS = None  # None = todas; ["porto"] = só cartas da Porto


def carregar_marca(caminho):
    """Lê marcas/<marca>.json e aplica os parâmetros dessa marca."""
    global AGIO_CREDITO, VIP_MIN, ADMINISTRADORAS
    m = json.load(open(caminho, encoding="utf-8"))
    faltando = [c for c in ("nome", "gerador", "fone", "agio_credito")
                if c not in m]
    if faltando:
        raise SystemExit(f"{caminho}: faltam os campos {faltando}")
    m["fone"] = normalizar_fone(m["fone"], caminho)
    AGIO_CREDITO = m["agio_credito"]
    VIP_MIN = m.get("vip_min", VIP_MIN)
    ADMINISTRADORAS = [a.lower() for a in m.get("administradoras") or []] or None
    return m


def normalizar_fone(bruto, origem="marca"):
    """
    O número vai direto para uma URL do wa.me, que só aceita dígitos.
    Escrever "11 91247-6544" — o formato natural de quem digita — produzia
    `https://wa.me/11 91247-6544`, um link quebrado que ninguém percebe até
    um cliente clicar. Aqui o número é limpo e conferido.
    """
    texto = str(bruto)
    if texto.upper().startswith("SUBSTITUIR"):
        raise SystemExit(f"{origem}: o campo 'fone' ainda é um placeholder. "
                         f"Preencha antes de rodar.")
    digitos = re.sub(r"\D", "", texto)
    if len(digitos) in (10, 11):          # veio sem o código do país
        digitos = "55" + digitos
    if not (digitos.startswith("55") and len(digitos) in (12, 13)):
        raise SystemExit(
            f"{origem}: '{bruto}' não é um WhatsApp válido para o link.\n"
            f"Esperado 55 + DDD + número, só dígitos. "
            f"Ex.: 5511912476544 (também aceito: '11 91247-6544').")
    if digitos != texto:
        print(f"fone normalizado: {bruto!r} -> {digitos}")
    return digitos


def da_administradora(c):
    """
    Algumas marcas só podem vender cartas de uma administradora — a Alê é
    funcionária da Porto e só comercializa Porto. O casamento é por trecho
    do nome, porque a tabela traz PORTO, PORTO AF e PORTO VP como
    administradoras distintas e todas são Porto.
    """
    if not ADMINISTRADORAS:
        return True
    adm = (c.get("adm") or "").lower()
    return any(a in adm for a in ADMINISTRADORAS)


def entrada_final(c, passo=PASSO, piso=PISO):
    """
    O ágio incide sobre o CRÉDITO, não sobre a entrada, e é o mesmo nos dois
    grupos. Antes era um percentual da entrada, o que fazia carta pequena
    render quase nada e carta grande render demais pelo mesmo trabalho.
    """
    ganho = max(c["credito"] * AGIO_CREDITO, piso)
    return math.ceil((c["entrada"] + ganho) / passo) * passo


def vigente(c, hoje):
    """Descarta cotas com vencimento já passado."""
    return datetime.strptime(c["venc"], "%d/%m/%Y").date() >= hoje


def chave(c):
    """Identidade da carta sem usar o ID de cota da LuME."""
    return f'{c["credito"]}|{c["entrada"]}|{c["adm"].strip().lower()}'


def publicadas_recentemente(raiz, hoje, janela=JANELA_REPETICAO):
    """
    Lê os cartas.json dos dias anteriores e devolve as chaves já enviadas
    na janela. Sem isto a mesma carta reaparece no grupo poucos dias
    depois — o assinante nota e a lista perde credibilidade.
    """
    vistas = set()
    if not os.path.isdir(raiz):
        return vistas
    for nome in os.listdir(raiz):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", nome):
            continue
        try:
            dia = date.fromisoformat(nome)
        except ValueError:
            continue
        if not (0 <= (hoje - dia).days <= janela) or dia == hoje:
            continue
        for grupo in ("COMUM", "VIP"):
            caminho = os.path.join(raiz, nome, grupo, "cartas.json")
            if os.path.isfile(caminho):
                try:
                    for c in json.load(open(caminho, encoding="utf-8")):
                        vistas.add(chave(c))
                except (ValueError, KeyError):
                    pass
    return vistas


def selecionar_vip(cotas, hoje, passo, piso, bloqueadas):
    elegiveis = [c for c in cotas
                 if c["credito"] >= VIP_MIN and vigente(c, hoje)
                 and chave(c) not in bloqueadas]
    # ordena pelo menor peso da entrada sobre o crédito — o argumento de venda
    elegiveis.sort(key=lambda c: entrada_final(c, passo, piso) / c["credito"])
    vistos, saida = set(), []
    for c in elegiveis:
        k = (c["credito"], c["entrada"], c["adm"])   # evita cotas gêmeas
        if k in vistos:
            continue
        vistos.add(k)
        saida.append(c)
        if len(saida) == 10:
            break
    return saida


def selecionar_comum(cotas, hoje, bloqueadas):
    """5 imóveis + 5 veículos, espalhados pelas faixas de crédito."""
    saida = []
    for seg in ("imovel", "veiculo"):
        pool = sorted([c for c in cotas if c["seg"] == seg and vigente(c, hoje)
                       and chave(c) not in bloqueadas],
                      key=lambda c: c["credito"])
        if not pool:
            continue
        passo_faixa = max(len(pool) // 5, 1)
        escolhidas, usados = [], set()
        for i in range(5):
            j = min(i * passo_faixa, len(pool) - 1)
            while j in usados and j + 1 < len(pool):
                j += 1
            if j in usados:
                continue
            usados.add(j)
            escolhidas.append(pool[j])
        saida += escolhidas
    return saida


def codigo(c, i):
    return ("IM" if c["seg"] == "imovel" else "VE") + f"-{i+1:03d}"


def brl(n):
    return f"{n:,.2f}".replace(",", "~").replace(".", ",").replace("~", ".")


def composta(c):
    return bool(c.get("composta")) and len(c.get("blocos") or []) > 1


def linha_parcelas(c):
    """
    A composição inteira, sempre. Anunciar só o primeiro degrau de uma
    carta escalonada esconde metade do contrato do cliente.
    """
    if composta(c):
        partes = " + ".join(f'{b["parcelas"]}x R$ {brl(b["valor"])}'
                            for b in c["blocos"])
        return f'Parcelas escalonadas: {partes} ({c["parcelas"]} no total)'
    return f'{c["parcelas"]}x R$ {brl(c["valorParcela"])}'


def legenda(cartas, grupo, fone, hoje, passo, piso):
    titulo = "SELEÇÃO VIP" if grupo == "vip" else "CARTAS DO DIA"
    linhas = [f"*{titulo} — {hoje.strftime('%d/%m/%Y')}*", ""]
    for i, c in enumerate(cartas):
        ef = entrada_final(c, passo, piso)
        seg = "Imóvel" if c["seg"] == "imovel" else "Veículo"
        linhas.append(f"{codigo(c,i)} — {seg} {c['adm']}")
        if composta(c):
            linhas.append(f"Crédito R$ {brl(c['credito'])} · Entrada R$ {brl(ef)}")
            linhas.append(linha_parcelas(c))
        else:
            linhas.append(f"Crédito R$ {brl(c['credito'])} · Entrada R$ {brl(ef)} "
                          f"· {linha_parcelas(c)}")
        linhas.append("")
    linhas.append("Gostou de alguma? Chame aqui com o código:")
    linhas.append(f"https://wa.me/{fone}?text=Tenho%20interesse%20na%20carta%20")
    return "\n".join(linhas)


def rodar(cotas, fone, raiz="saida", hoje=None, passo=PASSO, piso=PISO,
          gerador="gerador-cartas-vision.html", nome="Vision"):
    hoje = hoje or date.today()

    if ADMINISTRADORAS:
        antes = len(cotas)
        cotas = [c for c in cotas if da_administradora(c)]
        print(f"filtro de administradora {ADMINISTRADORAS}: "
              f"{len(cotas)} de {antes} cotas")
        if len(cotas) < 20:
            print(f"  atenção: só {len(cotas)} cotas passaram no filtro — "
                  f"os grupos podem sair incompletos")

    bloqueadas = publicadas_recentemente(raiz, hoje)
    if bloqueadas:
        print(f"{len(bloqueadas)} cartas bloqueadas por terem saído "
              f"nos últimos {JANELA_REPETICAO} dias")

    pasta_dia = os.path.join(raiz, hoje.isoformat())
    for grupo, cartas in (("comum", selecionar_comum(cotas, hoje, bloqueadas)),
                          ("vip",   selecionar_vip(cotas, hoje, passo, piso,
                                                   bloqueadas))):
        destino = os.path.join(pasta_dia, grupo.upper())
        os.makedirs(destino, exist_ok=True)
        with open(f"{destino}/cartas.json", "w", encoding="utf-8") as f:
            json.dump(cartas, f, ensure_ascii=False, indent=1)
        with open(f"{destino}/legenda.txt", "w", encoding="utf-8") as f:
            f.write(legenda(cartas, grupo, fone, hoje, passo, piso))
        n_comp = sum(1 for c in cartas if composta(c))
        extra = f" ({n_comp} escalonada{'s' if n_comp > 1 else ''})" if n_comp else ""
        print(f"{grupo.upper():6s} {len(cartas)} cartas{extra} → {destino}")

    # o renderizador precisa dos mesmos passo/piso, senão o PNG mostra uma
    # entrada e a legenda mostra outra
    with open(os.path.join(pasta_dia, "params.json"), "w", encoding="utf-8") as f:
        json.dump({"passo": passo, "piso": piso, "gerador": gerador,
                   "agio_credito": AGIO_CREDITO,
                   "marca": nome, "data": hoje.isoformat()},
                  f, ensure_ascii=False, indent=1)
    return pasta_dia


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cotas", nargs="?", default="cotas.json")
    ap.add_argument("--raiz", default="saida")
    ap.add_argument("--hoje")
    ap.add_argument("--marca", help="marcas/vision.json, marcas/ale.json …")
    ap.add_argument("--fone")
    ap.add_argument("--passo", type=int, default=PASSO)
    ap.add_argument("--piso", type=int, default=PISO)
    a = ap.parse_args()

    marca = carregar_marca(a.marca) if a.marca else {}
    fone = a.fone or marca.get("fone") or "5535999999999"
    passo = a.passo if a.passo != PASSO else marca.get("passo", PASSO)
    piso = a.piso if a.piso != PISO else marca.get("piso", PISO)

    hoje = datetime.strptime(a.hoje, "%d/%m/%Y").date() if a.hoje else date.today()
    cotas = json.load(open(a.cotas, encoding="utf-8"))
    if marca:
        print(f"marca: {marca['nome']} "
              f"(ágio {AGIO_CREDITO:.0%} sobre o crédito)")
    print(f"{len(cotas)} cotas na entrada")
    fora = sum(1 for c in cotas if not vigente(c, hoje))
    print(f"{fora} descartadas por vencimento vencido\n")
    rodar(cotas, fone=fone, raiz=a.raiz, hoje=hoje, passo=passo, piso=piso,
          gerador=marca.get("gerador", "gerador-cartas-vision.html"),
          nome=marca.get("nome", "Vision"))
