#!/usr/bin/env python3
"""
Site do parceiro — Vision / Cartas Contempladas

Página única com o catálogo completo de cotas disponíveis, na identidade
da Vision. O parceiro filtra pelo que o cliente procura, abre a carta, vê o
custo total do cliente e a própria comissão, e copia a mensagem pronta.

Uso: python3 site.py

Uma página só, com o catálogo inteiro. O parceiro abre a carta e escolhe ali
mesmo com qual dos três consultores quer falar.

As marcas de marcas/*.json (Cartas Alê, Cred Cris) NÃO entram aqui. Aqueles
parceiros recebem as cartas em PNG pelo Google Drive, por outro caminho; este
site é para os parceiros que não têm consultor fixo.

Rodapé, FAQ e contatos saem de config.json — editável sem mexer aqui.

O que a página NÃO mostra:
  * o ágio, nem a parte da Vision;
  * o ID de cota da LuME, que não existe no cotas.json;
  * comparação com financiamento — mostra o custo real e para aí.
Sai com noindex: o endereço é secreto, não público.
"""
import argparse, html, json, math, os
from datetime import datetime

from coletor import codigo_estavel
from selecao import brl, composta, linha_parcelas, normalizar_fone

AQUI = os.path.dirname(os.path.abspath(__file__))
SEG_ROTULO = {"imovel": "Imóvel", "veiculo": "Veículo",
              "maquinario": "Maquinário"}


def logo_base64():
    caminho = os.path.join(AQUI, "logo-vision.b64")
    return open(caminho).read().strip() if os.path.isfile(caminho) else ""


def preparar(cotas, marca):
    """
    Filtra por administradora quando a marca exige, precifica e calcula.

    Ágio e comissão podem vir das variáveis de ambiente AGIO_CREDITO e
    COMISSAO_CREDITO. É o que permite manter as margens fora do código num
    repositório público: os números ficam em Secrets do GitHub e o JSON
    guarda só um valor de referência.

    Os dois números não são independentes. O ágio é o que a Vision põe em
    cima da entrada da LuME; a comissão do parceiro sai de dentro dele. Com
    5% e 2%, sobram 3% para a casa. Se um dia a comissão for configurada
    acima do ágio, a Vision estaria pagando para vender — e nada na página
    acusaria, porque o ágio não aparece em lugar nenhum. Daí a trava.
    """
    agio = float(os.environ.get("AGIO_CREDITO") or marca.get("agio_credito", 0.05))
    com = float(os.environ.get("COMISSAO_CREDITO")
                or marca.get("comissao_credito", 0.02))
    if com >= agio:
        raise SystemExit(
            f"Comissão ({com:.1%}) igual ou maior que o ágio ({agio:.1%}). "
            "A comissão do parceiro sai de dentro do ágio; assim a Vision "
            "venderia no prejuízo. Corrija os Secrets AGIO_CREDITO e "
            "COMISSAO_CREDITO antes de publicar.")
    passo, piso = marca.get("passo", 50), marca.get("piso", 0)
    admins = [a.lower() for a in marca.get("administradoras") or []]

    saida = []
    for c in cotas:
        if admins and not any(a in (c.get("adm") or "").lower() for a in admins):
            continue
        ef = math.ceil((c["entrada"] + max(c["credito"] * agio, piso))
                       / passo) * passo
        if composta(c):
            parcelas_total = sum(b["parcelas"] * b["valor"] for b in c["blocos"])
        else:
            parcelas_total = c["parcelas"] * c["valorParcela"]
        total = ef + parcelas_total
        saida.append({**c,
                      "cod": c.get("cod") or codigo_estavel(c),
                      "entradaFinal": ef,
                      "parcelasTotal": round(parcelas_total),
                      "custoTotal": round(total),
                      "acima": round(total / c["credito"] - 1, 4),
                      "comissao": round(c["credito"] * com),
                      "peso": round(ef / c["credito"], 4)})
    saida.sort(key=lambda c: c["credito"])
    return saida


def dados_js(cartas):
    """A lista vai como dado para o JS, não como HTML repetido 188 vezes."""
    campos = ("cod", "seg", "adm", "credito", "entradaFinal", "parcelas",
              "valorParcela", "parcelasTotal", "custoTotal", "acima",
              "comissao", "peso", "regras")
    enxuto = []
    for c in cartas:
        d = {k: c.get(k) for k in campos}
        d["parc"] = linha_parcelas(c) if composta(c) else ""
        enxuto.append(d)
    return json.dumps(enxuto, ensure_ascii=False, separators=(",", ":"))


def equipe_de(cfg):
    """
    Os três consultores, na ordem do config.json. Neste site o parceiro
    escolhe com quem falar na hora de reservar — antes tudo caía num número
    só. Os parceiros com consultor fixo (Alê, Cred Cris) não usam o site:
    recebem os cards em PNG pelo Drive.
    """
    return [{"nome": c.get("nome", ""), "fone": c["_fone"]}
            for c in (cfg.get("consultores") or {}).values() if c.get("_fone")]


# ---------------------------------------------------------------- aparência
# As administradoras entram como selo colorido com o nome escrito, não como
# logotipo. Reproduzir a marca de terceiro numa página comercial sugeriria
# um credenciamento que a Vision não tem com cada uma delas, e as artes não
# são nossas para distribuir. A cor da casa dá o reconhecimento imediato que
# o Leonardo queria, sem se apropriar de nada.
CORES_ADM = {
    "PORTO": "#0B3B8F", "PORTO AF": "#0B3B8F", "PORTO VP": "#0B3B8F",
    "ITAU": "#D96A00", "BRADESCO": "#B00A28", "SANTANDER": "#C8102E",
    "CAIXA": "#0B6BA8", "BCO BRASIL": "#0B3D91", "SICREDI": "#3B8A2E",
    "SICOOB": "#0A5B54", "UNICOOB": "#1C7A46", "YAMAHA": "#B8121B",
    "VOLKS": "#0B2354", "EMBRACON": "#B3161F", "CNP": "#1A5BA0",
    "SERVOPA": "#A81733", "RODOBENS": "#0F7FA8", "MAGALU": "#0B6BD1",
    "CANOPUS": "#C05B12", "H S": "#5B2A86",
}
PALETA_RESERVA = ["#3F4A57", "#6B4A7A", "#2F6B5E", "#7A5230", "#4A5A8C"]


def cor_adm(nome):
    n = (nome or "").strip().upper()
    if n in CORES_ADM:
        return CORES_ADM[n]
    return PALETA_RESERVA[sum(map(ord, n)) % len(PALETA_RESERVA)]


# Ícones desenhados aqui, em SVG, e não buscados de CDN: a página precisa
# abrir inteira sem depender de rede de terceiro.
ICONE_SEG = {
    "imovel": ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="M3 10.5 12 3l9 7.5"/><path d="M5.5 9.5V20h13V9.5"/>'
               '<path d="M9.8 20v-5.4h4.4V20"/></svg>'),
    "veiculo": ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M4 16.5v2.2h2.6v-2.2"/><path d="M17.4 16.5v2.2H20v-2.2"/>'
                '<path d="M3 16.5v-4l1.9-4.4A2 2 0 0 1 6.7 7h10.6a2 2 0 0 1 1.8 1.1'
                'L21 12.5v4z"/><path d="M4.6 12.4h14.8"/><circle cx="7.3" cy="14.6" '
                'r=".9"/><circle cx="16.7" cy="14.6" r=".9"/></svg>'),
    "maquinario": ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                   'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
                   '<circle cx="7" cy="16.5" r="3.5"/><circle cx="17.5" cy="17.5" '
                   'r="2.5"/><path d="M7 13V7h5l2.4 5.5"/><path d="M12 7h4l1.5 8"/>'
                   '</svg>'),
}
ZAP_SVG = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
           '<path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 '
           '4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 '
           '9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2zm0 '
           '18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.19 '
           '8.19 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23a8.18 8.18 0 0 1 5.82 '
           '2.42 8.18 8.18 0 0 1 2.41 5.82c0 4.54-3.7 8.23-8.23 8.23zm4.52-6.16c-.25-.12'
           '-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.24-.64.8-.79.97-.14.16-.29.18'
           '-.54.06-.25-.13-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.01'
           '-.38.11-.5.11-.11.25-.29.37-.44.12-.14.16-.25.25-.41.08-.17.04-.31-.02-.43'
           '-.06-.12-.56-1.34-.76-1.84-.2-.48-.4-.42-.56-.43l-.47-.01c-.17 0-.43.06-.66'
           '.31s-.86.85-.86 2.07.89 2.4 1.01 2.56c.12.17 1.75 2.67 4.23 3.74.59.26 1.05'
           '.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.14'
           '-1.18-.06-.11-.22-.17-.47-.29z"/></svg>')


# O CSS e o JS ficam em texto puro, fora de f-string. Numa f-string cada
# chave de CSS e cada bloco de JS teria de ser duplicado, e uma chave
# esquecida no meio de 400 linhas quebra a página inteira sem avisar.
CSS = """
  :root{
    --tinta:#0B0B0C;      /* preto do cabeçalho e do rodapé */
    --papel:#FFFFFF;
    --nevoa:#F4F4F5;      /* fundo da página, atrás dos cartões */
    --linha:#E5E5E8;
    --linha2:#EFEFF1;
    --t1:#101013;
    --t2:#4B4B53;
    --t3:#82828C;
    --zap:#25D366;
    --zap-esc:#128C4B;
    --sans:'Geist','Inter',system-ui,-apple-system,sans-serif;
    --mono:'Geist Mono','IBM Plex Mono',ui-monospace,monospace;
    --grade:170px 128px 1fr 1fr 68px 1fr 1fr 118px 132px;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--nevoa);color:var(--t1);font-family:var(--sans);
    font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
  button,input,select{font:inherit;color:inherit}
  button{cursor:pointer;background:none;border:0}

  /* ---------- cabeçalho preto ---------- */
  header.barra{background:var(--tinta);color:#fff}
  .barra-in{max-width:1360px;margin:0 auto;padding:20px 26px;
    display:flex;align-items:center;gap:15px;flex-wrap:wrap}
  .barra-in img{height:40px;width:auto;display:block}
  .barra-in h1{font-size:20px;font-weight:600;letter-spacing:-.01em}
  .barra-in .sub{font-family:var(--mono);font-size:10px;letter-spacing:.22em;
    text-transform:uppercase;color:#8E9096;margin-top:3px}

  /* ---------- filtros ---------- */
  .filtros{background:var(--papel);border-bottom:1px solid var(--linha);
    position:sticky;top:0;z-index:30}
  .filtros-in{max-width:1360px;margin:0 auto;padding:16px 26px 14px;
    display:flex;flex-direction:column;gap:12px}
  .fl{display:flex;flex-wrap:wrap;gap:9px;align-items:center}
  .rot{font-family:var(--mono);font-size:9.5px;letter-spacing:.2em;
    text-transform:uppercase;color:var(--t3);margin-right:2px}
  .pill{border:1px solid var(--linha);background:var(--papel);border-radius:999px;
    padding:8px 15px;font-size:14px;color:var(--t2);display:flex;gap:7px;
    align-items:center;transition:.13s}
  .pill:hover{border-color:#C9C9CF}
  .pill.on{background:var(--tinta);border-color:var(--tinta);color:#fff}
  .pill .n{font-family:var(--mono);font-size:11px;opacity:.6}
  .pill svg{width:16px;height:16px}
  .campo{display:flex;align-items:center;gap:8px;border:1px solid var(--linha);
    border-radius:999px;padding:7px 15px;background:var(--papel)}
  .campo span{font-family:var(--mono);font-size:9.5px;letter-spacing:.16em;
    text-transform:uppercase;color:var(--t3);white-space:nowrap}
  .campo input{border:0;outline:0;background:none;width:86px;font-size:14px;
    font-variant-numeric:tabular-nums}
  input[type=search]{border:1px solid var(--linha);border-radius:999px;
    padding:8px 16px;background:var(--papel);outline:0;min-width:230px;flex:1;
    max-width:330px}
  input[type=search]:focus,.campo:focus-within{border-color:var(--tinta)}
  select{border:1px solid var(--linha);border-radius:999px;padding:8px 34px 8px 15px;
    background:var(--papel) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M2.5 4.5 6 8l3.5-3.5' stroke='%2382828C' stroke-width='1.4' fill='none' stroke-linecap='round'/%3E%3C/svg%3E") no-repeat right 13px center/12px;
    appearance:none;outline:0;color:var(--t2);max-width:280px}
  .limpar{color:var(--t3);font-size:13.5px;text-decoration:underline;
    text-underline-offset:3px}
  .limpar:hover{color:var(--t1)}
  .marca-f{border:1px solid var(--linha);border-radius:999px;padding:5px 12px;
    font-size:12.5px;color:var(--t2);display:flex;gap:6px;align-items:center}
  /* [hidden] sozinho não vence o display:flex acima — sem esta linha as 20
     administradoras aparecem todas de uma vez e o "todas" não serve de nada. */
  .marca-f[hidden]{display:none}
  .marca-f i{width:8px;height:8px;border-radius:99px;display:block;flex:none}
  .marca-f.on{border-color:var(--tinta);background:var(--tinta);color:#fff}
  .mais-marcas{font-size:12.5px;color:var(--t3);text-decoration:underline;
    text-underline-offset:3px}
  .btn-filtros{display:none;border:1px solid var(--tinta);border-radius:999px;
    padding:8px 16px;font-size:14px;font-weight:500;gap:7px;align-items:center}
  .btn-filtros .n2{font-family:var(--mono);font-size:11px;background:var(--tinta);
    color:#fff;border-radius:99px;padding:1px 6px}
  /* No celular a barra de filtros inteira ocupava a tela toda e empurrava as
     cartas para fora da primeira dobra. Segmento e busca ficam à vista; o
     resto abre no botão. E ela deixa de ser fixa: presa no topo, um bloco
     desse tamanho não sobraria espaço para a lista. */
  @media (max-width:820px){
    .filtros{position:static}
    .filtros-in{padding:14px 18px}
    .fl.secundaria{display:none}
    .filtros.aberto .fl.secundaria{display:flex}
    .btn-filtros{display:flex}
    .rot{width:100%}
    /* flex:1 no meio de uma linha apertada espremia a busca até virar "Bu".
       No celular ela toma a linha inteira. */
    input[type=search]{flex:1 1 100%;max-width:none;min-width:0}
    select{flex:1}
    .conta-bar{padding:16px 18px 10px}
    main{padding:0 18px 44px}
    section.faq,.pe{padding-left:18px;padding-right:18px}
    .barra-in{padding:16px 18px}
  }

  /* ---------- barra de contagem ---------- */
  .conta-bar{max-width:1360px;margin:0 auto;padding:20px 26px 12px;
    display:flex;align-items:center;gap:14px;flex-wrap:wrap}
  .conta-bar b{font-family:var(--mono);font-size:12.5px;letter-spacing:.1em;
    color:var(--t2);font-weight:500}
  .ativos{display:flex;gap:6px;flex-wrap:wrap}
  .tag{background:var(--papel);border:1px solid var(--linha);border-radius:999px;
    padding:4px 8px 4px 11px;font-size:12.5px;color:var(--t2);display:flex;
    gap:6px;align-items:center}
  .tag em{font-style:normal;color:var(--t3);font-size:15px;line-height:1;
    padding:0 3px}
  .tag:hover em{color:var(--t1)}
  .modo{margin-left:auto;display:flex;align-items:center;gap:9px;
    font-size:13.5px;color:var(--t2);cursor:pointer;user-select:none}
  .modo input{appearance:none;width:38px;height:22px;border-radius:99px;
    background:#D9D9DE;position:relative;cursor:pointer;transition:.16s;flex:none}
  .modo input:checked{background:var(--tinta)}
  .modo input::after{content:"";position:absolute;top:3px;left:3px;width:16px;
    height:16px;border-radius:99px;background:#fff;transition:.16s}
  .modo input:checked::after{transform:translateX(16px)}

  /* ---------- tabela ---------- */
  main{max-width:1360px;margin:0 auto;padding:0 26px 60px}
  .quadro{background:var(--papel);border:1px solid var(--linha);
    border-radius:14px;overflow:hidden}
  .cab{display:grid;grid-template-columns:var(--grade);gap:16px;
    padding:13px 20px;border-bottom:1px solid var(--linha);background:#FAFAFB}
  .cab span{font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;
    text-transform:uppercase;color:var(--t3)}
  .cab .dir,.linha-c .dir{text-align:right}
  ul{list-style:none}
  .linha-c{display:grid;grid-template-columns:var(--grade);gap:16px;
    padding:15px 20px;border-bottom:1px solid var(--linha2);align-items:center;
    width:100%;text-align:left;transition:background .12s}
  .linha-c:last-child{border-bottom:0}
  .linha-c:hover{background:#FBFBFC}
  .seg{display:flex;align-items:center;gap:10px;min-width:0}
  .seg-ic{width:34px;height:34px;border-radius:9px;background:var(--nevoa);
    display:grid;place-items:center;color:var(--t2);flex:none}
  .seg-ic svg{width:19px;height:19px}
  .seg-txt{min-width:0}
  .seg-txt b{display:block;font-size:13.5px;font-weight:500;color:var(--t1)}
  .seg-txt span{font-family:var(--mono);font-size:10.5px;letter-spacing:.09em;
    color:var(--t3)}
  .selo{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;
    font-weight:500;color:var(--t1);min-width:0}
  .selo i{width:9px;height:9px;border-radius:99px;flex:none}
  .selo span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .val{font-size:15.5px;font-variant-numeric:tabular-nums;color:var(--t1)}
  .val.forte{font-weight:600}
  .sub2{display:block;font-size:11.5px;color:var(--t3);
    font-variant-numeric:tabular-nums;margin-top:1px}
  .parc-n{font-family:var(--mono);font-size:15px;color:var(--t1)}
  .escada{display:inline-block;font-size:11px;color:#8A5A00;background:#FFF4DB;
    border-radius:5px;padding:1px 6px;margin-top:2px}
  .acao{display:flex;gap:7px;justify-content:flex-end}
  .ver{border:1px solid var(--linha);border-radius:8px;padding:8px 13px;
    font-size:13px;color:var(--t2);white-space:nowrap}
  .linha-c:hover .ver{border-color:var(--tinta);color:var(--t1)}
  .zap{width:36px;height:36px;border-radius:8px;background:var(--zap);
    color:#fff;display:grid;place-items:center;flex:none;text-decoration:none}
  .zap:hover{background:var(--zap-esc)}
  .zap svg{width:19px;height:19px}
  /* Modo cliente: some com tudo que fala de comissão, não só com os valores.
     Escondendo só os números, o cabeçalho continuava dizendo "SUA COMISSÃO"
     em cima de uma coluna vazia — para o cliente ao lado, isso entrega o
     mesmo que o número. Some a coluna inteira, e a grade se refaz sem ela. */
  body.cliente [data-com]{display:none}
  body.cliente{--grade:170px 128px 1fr 1fr 68px 1fr 1fr 132px}
  #vazio{display:none;background:var(--papel);border:1px solid var(--linha);
    border-radius:14px;padding:46px 26px;text-align:center;color:var(--t3)}
  #vazio b{display:block;color:var(--t1);font-size:16px;margin-bottom:6px}

  /* ---------- celular: a tabela vira cartão ---------- */
  @media (max-width:1080px){
    .cab{display:none}
    .quadro{background:none;border:0;border-radius:0}
    ul{display:grid;gap:11px}
    .linha-c{grid-template-columns:1fr 1fr;gap:12px 16px;background:var(--papel);
      border:1px solid var(--linha);border-radius:12px;padding:15px 16px}
    .linha-c:last-child{border-bottom:1px solid var(--linha)}
    .seg,.acao{grid-column:1/-1}
    .acao .ver{flex:1;text-align:center}
    .linha-c .dir{text-align:left}
    .cel-k{display:block;font-family:var(--mono);font-size:9px;
      letter-spacing:.16em;text-transform:uppercase;color:var(--t3);
      margin-bottom:2px}
  }
  @media (min-width:1081px){ .cel-k{display:none} }

  /* ---------- detalhe ---------- */
  dialog{margin:auto;border:1px solid var(--linha);background:var(--papel);
    color:var(--t1);border-radius:16px;padding:0;width:min(620px,94vw);
    max-height:92vh;overflow:auto;box-shadow:0 24px 70px rgba(0,0,0,.22)}
  dialog::backdrop{background:rgba(10,10,12,.5)}
  .d-top{display:flex;align-items:center;gap:11px;flex-wrap:wrap;
    padding:17px 22px 15px;border-bottom:1px solid var(--linha);
    position:sticky;top:0;background:var(--papel);z-index:2}
  .d-cod{font-family:var(--mono);font-size:15px;letter-spacing:.08em}
  .d-fechar{margin-left:auto;border:1px solid var(--linha);border-radius:8px;
    padding:7px 13px;font-size:13px;color:var(--t2)}
  .d-fechar:hover{border-color:var(--tinta);color:var(--t1)}
  .d-corpo{padding:6px 22px}
  .lin{display:flex;justify-content:space-between;align-items:baseline;gap:16px;
    padding:11px 0;border-bottom:1px solid var(--linha2)}
  .lin .k{font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;
    text-transform:uppercase;color:var(--t3)}
  .lin .v{font-size:16px;font-variant-numeric:tabular-nums;text-align:right}
  .lin.destaque{border-bottom:0;padding-top:14px}
  .lin.destaque .v{font-size:23px;font-weight:600}
  .regras{margin:12px 22px 4px;padding:15px 16px;background:var(--nevoa);
    border-radius:10px}
  .regras h3,.reservar h3,.semelhantes h3{font-family:var(--mono);font-size:9.5px;
    letter-spacing:.18em;text-transform:uppercase;color:var(--t3);
    font-weight:500;margin-bottom:9px}
  .regras pre{font-family:var(--sans);font-size:13.5px;line-height:1.6;
    color:var(--t2);white-space:pre-wrap;word-break:break-word}
  .aviso-taxa{margin-top:11px;padding-top:11px;border-top:1px solid var(--linha);
    font-size:12.5px;color:var(--t3)}
  .acoes{display:flex;gap:9px;padding:14px 22px 6px}
  .acoes button{flex:1;border:1px solid var(--tinta);background:var(--tinta);
    color:#fff;border-radius:9px;padding:12px;font-weight:600}
  .reservar{padding:14px 22px 18px}
  .reservar p{font-size:13.5px;color:var(--t2);margin-bottom:11px}
  .cons{display:flex;flex-wrap:wrap;gap:9px}
  .cons a{flex:1;min-width:152px;display:flex;align-items:center;gap:10px;
    padding:11px 13px;border:1px solid var(--linha);border-radius:10px;
    text-decoration:none;color:var(--t1);transition:.13s}
  .cons a:hover{border-color:var(--zap);background:#F2FCF6}
  .cons .ic{width:32px;height:32px;border-radius:8px;background:var(--zap);
    color:#fff;display:grid;place-items:center;flex:none}
  .cons .ic svg{width:18px;height:18px}
  .cons b{font-size:13.5px;font-weight:600;display:block;line-height:1.25}
  .cons em{font-style:normal;font-family:var(--mono);font-size:9.5px;
    letter-spacing:.14em;text-transform:uppercase;color:var(--t3)}
  .semelhantes{padding:0 22px 20px}
  .sem{display:flex;justify-content:space-between;gap:14px;width:100%;
    padding:11px 13px;margin-bottom:6px;font-size:13.5px;text-align:left;
    border:1px solid var(--linha);border-radius:9px;color:var(--t2)}
  .sem:hover{border-color:var(--tinta)}
  .sem b{color:var(--t1);font-variant-numeric:tabular-nums}
  .sem em{color:var(--t3);font-family:var(--mono);font-size:11px;
    font-style:normal}

  /* ---------- perguntas ---------- */
  section.faq{max-width:1360px;margin:0 auto;padding:8px 26px 50px}
  section.faq h2{font-family:var(--mono);font-size:9.5px;letter-spacing:.2em;
    text-transform:uppercase;color:var(--t3);margin-bottom:12px}
  details{border-bottom:1px solid var(--linha);background:var(--papel);
    padding:0 16px}
  details:first-of-type{border-radius:12px 12px 0 0;
    border-top:1px solid var(--linha)}
  details:last-of-type{border-radius:0 0 12px 12px}
  summary{padding:14px 0;cursor:pointer;font-weight:500;list-style:none}
  summary::-webkit-details-marker{display:none}
  summary::before{content:"+  ";color:var(--t3);font-family:var(--mono)}
  details[open] summary::before{content:"\\2212  "}
  details p{padding:0 0 15px;color:var(--t2);max-width:74ch;font-size:14.5px}

  /* ---------- rodapé preto ---------- */
  footer{background:var(--tinta);color:#B9BBC0}
  .pe{max-width:1360px;margin:0 auto;padding:34px 26px 40px;display:grid;
    gap:26px;grid-template-columns:1fr}
  @media (min-width:820px){.pe{grid-template-columns:1.35fr 1fr 1fr}}
  .plantao{grid-column:1/-1;background:#141416;border:1px solid #232327;
    border-radius:12px;padding:18px 20px;display:flex;flex-wrap:wrap;
    gap:14px 22px;align-items:center}
  .plantao b{color:#fff;font-weight:600}
  .plantao div{font-size:14px}
  .plantao-zaps{margin-left:auto;display:flex;flex-wrap:wrap;gap:8px}
  .plantao-zaps a{background:var(--zap);color:#fff;padding:10px 17px;
    border-radius:8px;font-weight:600;text-decoration:none;white-space:nowrap;
    display:flex;align-items:center;gap:8px;font-size:14px}
  .plantao-zaps a:hover{background:var(--zap-esc)}
  .plantao-zaps svg{width:17px;height:17px}
  .bloco{display:flex;flex-direction:column;gap:7px;font-size:14px}
  .bloco h2{font-family:var(--mono);font-size:9.5px;letter-spacing:.2em;
    text-transform:uppercase;color:#6E7076;font-weight:500;margin-bottom:4px}
  .bloco a{color:#D6D7DA;text-decoration:none;width:fit-content;
    display:flex;align-items:center;gap:8px}
  .bloco a:hover{color:#fff;text-decoration:underline}
  .bloco a svg{width:15px;height:15px;color:var(--zap);flex:none}
  .nota{grid-column:1/-1;font-size:12.5px;color:#6E7076;max-width:86ch;
    padding-top:8px;border-top:1px solid #232327}
"""


JS = r"""
const CARTAS = __CARTAS__;
const ROT    = __ROT__;
const EQUIPE = __EQUIPE__;
const CORES  = __CORES__;
const ICONES = __ICONES__;
const ZAP    = __ZAP__;

const $ = s => document.querySelector(s);
const lista = $('#lista'), vazio = $('#vazio'), conta = $('#conta');
const deEl = $('#de'), ateEl = $('#ate'), qEl = $('#q');
const ordemEl = $('#ordem'), modoEl = $('#modo'), ativosEl = $('#ativos');

/* Estado dos filtros num objeto só: cada peça da interface lê e escreve
   daqui, e as etiquetas de "filtro ativo" saem dele sem duplicar regra. */
const F = { seg: '', adm: '', de: 0, ate: 0, q: '' };

const brl  = n => n.toLocaleString('pt-BR',
  {minimumFractionDigits: 2, maximumFractionDigits: 2});
const brl0 = n => n.toLocaleString('pt-BR', {maximumFractionDigits: 0});
const esc  = s => String(s).replace(/[&<>"]/g,
  m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const num  = v => { const d = String(v).replace(/\D/g, ''); return d ? +d : 0; };
const corDe = a => CORES[a] || '#5A5A66';
const icone = s => ICONES[s] || ICONES.imovel;

/* ---------- filtro ---------- */
/* Cada critério é uma função à parte para que os contadores possam medir
   "quantas cartas sobram se eu ignorar este critério" — sem isso o número
   ao lado de cada botão mentiria assim que outro filtro estivesse ligado. */
const testes = {
  seg: c => !F.seg || c.seg === F.seg,
  adm: c => !F.adm || c.adm === F.adm,
  faixa: c => (!F.de || c.credito >= F.de) && (!F.ate || c.credito <= F.ate),
  q: c => !F.q || (c.cod + ' ' + c.adm).toLowerCase().includes(F.q),
};
const passa = (c, menos) => Object.keys(testes)
  .every(k => k === menos || testes[k](c));

function filtrar() {
  const r = CARTAS.filter(c => passa(c));
  const ord = {
    peso: (a, b) => a.peso - b.peso,
    credito: (a, b) => b.credito - a.credito,
    'credito-asc': (a, b) => a.credito - b.credito,
    entrada: (a, b) => a.entradaFinal - b.entradaFinal,
    parcela: (a, b) => a.valorParcela - b.valorParcela,
    comissao: (a, b) => b.comissao - a.comissao,
  }[ordemEl.value];
  return r.sort(ord);
}

/* ---------- linha da tabela ---------- */
function linha(c) {
  const valorParc = c.parc
    ? '<span class="escada">escalonada</span>'
    : '<span class="val">R$ ' + brl(c.valorParcela) + '</span>';
  return '<li><button class="linha-c" data-cod="' + c.cod + '">' +
    '<span class="seg"><span class="seg-ic">' + icone(c.seg) + '</span>' +
      '<span class="seg-txt"><b>' + (ROT[c.seg] || c.seg) + '</b>' +
      '<span>' + c.cod + '</span></span></span>' +
    '<span class="selo"><i style="background:' + corDe(c.adm) + '"></i>' +
      '<span>' + esc(c.adm) + '</span></span>' +
    '<span class="dir"><span class="cel-k">Crédito</span>' +
      '<span class="val forte">R$ ' + brl0(c.credito) + '</span></span>' +
    '<span class="dir"><span class="cel-k">Entrada</span>' +
      '<span class="val">R$ ' + brl0(c.entradaFinal) + '</span>' +
      '<span class="sub2">' + Math.round(c.peso * 100) + '% do crédito</span></span>' +
    '<span class="dir"><span class="cel-k">Parcelas</span>' +
      '<span class="parc-n">' + c.parcelas + 'x</span></span>' +
    '<span class="dir"><span class="cel-k">Valor das parcelas</span>' +
      valorParc + '</span>' +
    '<span class="dir"><span class="cel-k">Custo total</span>' +
      '<span class="val">R$ ' + brl0(c.custoTotal) + '</span>' +
      '<span class="sub2">+' + Math.round(c.acima * 100) + '% s/ crédito</span></span>' +
    '<span class="dir" data-com><span class="cel-k">Sua comissão</span>' +
      '<span class="val">R$ ' + brl0(c.comissao) + '</span></span>' +
    '<span class="acao"><span class="ver">Ver carta</span>' +
      '<span class="zap" data-zap="' + c.cod + '">' + ZAP + '</span></span>' +
    '</button></li>';
}

/* ---------- etiquetas dos filtros ligados ---------- */
function etiquetas() {
  const t = [];
  if (F.seg) t.push(['seg', ROT[F.seg] || F.seg]);
  if (F.adm) t.push(['adm', F.adm]);
  if (F.de || F.ate) t.push(['faixa',
    (F.de ? 'de R$ ' + brl0(F.de) : 'até R$ ' + brl0(F.ate)) +
    (F.de && F.ate ? ' a R$ ' + brl0(F.ate) : '')]);
  if (F.q) t.push(['q', '"' + F.q + '"']);
  ativosEl.innerHTML = t.map(([k, r]) =>
    '<button class="tag" data-tira="' + k + '">' + esc(r) + '<em>&times;</em></button>'
  ).join('');
}

function contadores() {
  document.querySelectorAll('.pill[data-seg]').forEach(b => {
    const v = b.dataset.seg;
    b.querySelector('.n').textContent =
      CARTAS.filter(c => (!v || c.seg === v) && passa(c, 'seg')).length;
  });
  document.querySelectorAll('.marca-f').forEach(b => {
    const v = b.dataset.adm;
    const n = CARTAS.filter(c => (!v || c.adm === v) && passa(c, 'adm')).length;
    b.style.opacity = n ? 1 : .35;
  });
}

function render() {
  aplicarModo();   /* antes de filtrar: pode trocar a ordenação escolhida */
  const r = filtrar();
  lista.innerHTML = r.map(linha).join('');
  conta.textContent = r.length + (r.length === 1 ? ' carta' : ' cartas');
  vazio.style.display = r.length ? 'none' : 'block';
  etiquetas();
  contadores();
  contarFiltros();
}

/* ---------- modo cliente ---------- */
/* Vale para a tela toda enquanto o parceiro procura junto com o cliente:
   coluna de comissão, linha da comissão no detalhe, o rótulo do cabeçalho e
   a ordenação "maior comissão" no menu. Se essa ordenação estiver escolhida
   na hora de ligar o modo, ela é trocada — o próprio menu diria em voz alta
   que a lista está ordenada por comissão. */
try { modoEl.checked = localStorage.getItem('modoCliente') === '1'; } catch (e) {}
const optComissao = ordemEl.querySelector('option[value="comissao"]');
function aplicarModo() {
  const c = modoEl.checked;
  document.body.classList.toggle('cliente', c);
  if (c && ordemEl.value === 'comissao') ordemEl.value = 'peso';
  /* A opção sai do DOM, não fica só com hidden: o Safari do iPhone ignora
     hidden em <option>, e mesmo no Chrome o texto continuava aparecendo na
     leitura da página. Sair e voltar é o único jeito que vale nos dois. */
  if (c) optComissao.remove();
  else if (!optComissao.parentNode) ordemEl.appendChild(optComissao);
  try { localStorage.setItem('modoCliente', c ? '1' : '0'); } catch (e) {}
}

/* ---------- detalhe ---------- */
const dlg = document.createElement('dialog');
document.body.appendChild(dlg);

const semelhantes = c => CARTAS
  .filter(o => o.cod !== c.cod && o.seg === c.seg &&
               Math.abs(o.credito - c.credito) / c.credito <= 0.25)
  .sort((a, b) => Math.abs(a.credito - c.credito) -
                  Math.abs(b.credito - c.credito))
  .slice(0, 4);

const textoReserva = c => 'Tenho interesse na carta ' + c.cod +
  ' — crédito R$ ' + brl(c.credito) + '. Ela está disponível?';

function mensagemCliente(c) {
  const parc = c.parc || (c.parcelas + 'x de R$ ' + brl(c.valorParcela));
  return '*Carta contemplada ' + c.cod + '* — ' + (ROT[c.seg] || c.seg) +
    '\n\nCrédito: R$ ' + brl(c.credito) +
    '\nEntrada: R$ ' + brl(c.entradaFinal) +
    '\nParcelas: ' + parc +
    '\nCusto total: R$ ' + brl(c.custoTotal) +
    '\n\nA disponibilidade é confirmada na reserva. Me chame para garantir esta carta.';
}

function abrir(cod) {
  const c = CARTAS.find(x => x.cod === cod);
  if (!c) return;
  const parc = c.parc || (c.parcelas + 'x de R$ ' + brl(c.valorParcela));
  const sem = semelhantes(c);
  dlg.innerHTML =
    '<div class="d-top"><span class="seg-ic">' + icone(c.seg) + '</span>' +
      '<span class="d-cod">' + c.cod + '</span>' +
      '<span class="selo"><i style="background:' + corDe(c.adm) + '"></i>' +
      '<span>' + esc(c.adm) + '</span></span>' +
      '<button class="d-fechar" id="fechar">Fechar</button></div>' +
    '<div class="d-corpo">' +
      '<div class="lin"><span class="k">Crédito</span><span class="v">R$ ' +
        brl(c.credito) + '</span></div>' +
      '<div class="lin"><span class="k">Entrada</span><span class="v">R$ ' +
        brl(c.entradaFinal) + '</span></div>' +
      '<div class="lin"><span class="k">Parcelas</span><span class="v">' +
        parc + '</span></div>' +
      '<div class="lin"><span class="k">Total das parcelas</span>' +
        '<span class="v">R$ ' + brl(c.parcelasTotal) + '</span></div>' +
      '<div class="lin" data-com><span class="k">Sua comissão</span>' +
        '<span class="v">R$ ' + brl(c.comissao) + '</span></div>' +
      '<div class="lin destaque"><span class="k">Custo total do cliente</span>' +
        '<span class="v">R$ ' + brl(c.custoTotal) + '<br><span class="k">+' +
        Math.round(c.acima * 100) + '% sobre o crédito</span></span></div>' +
    '</div>' +
    '<div class="regras"><h3>Regras para uso desta carta</h3><pre>' +
      (c.regras ? esc(c.regras)
        : 'Regras não informadas para esta administradora. Confirme com a ' +
          'Vision antes de fechar.') + '</pre>' +
      (c.regras ? '<p class="aviso-taxa">A taxa de transferência é cobrada ' +
        'pela administradora e <b>não está incluída no custo total ' +
        'acima</b>.</p>' : '') + '</div>' +
    '<div class="acoes">' +
      '<button id="copiar">Copiar mensagem para o cliente</button></div>' +
    '<div class="reservar"><h3>Reservar esta carta</h3>' +
      '<p>Chame qualquer um dos três — todos atendem esta lista. A mensagem ' +
      'já vai com o código da carta.</p>' +
      '<div class="cons">' + EQUIPE.map(p =>
        '<a href="https://wa.me/' + p.fone + '?text=' +
        encodeURIComponent(textoReserva(c)) +
        '" target="_blank" rel="noopener"><span class="ic">' + ZAP + '</span>' +
        '<span><b>' + esc(p.nome) + '</b><em>WhatsApp</em></span></a>'
      ).join('') + '</div></div>' +
    '<div class="semelhantes"><h3>Cartas semelhantes</h3>' +
      (sem.length ? sem.map(s =>
        '<button class="sem" data-cod="' + s.cod + '">' +
        '<span><b>R$ ' + brl0(s.credito) + '</b> · entrada R$ ' +
        brl0(s.entradaFinal) + '</span><em>' + s.cod + '</em></button>').join('')
       : '<p style="color:var(--t3);font-size:13.5px">Nenhuma carta parecida ' +
         'hoje.</p>') + '</div>';
  dlg.querySelector('#fechar').onclick = () => dlg.close();
  dlg.querySelector('#copiar').onclick = async (e) => {
    const b = e.currentTarget;
    try {
      await navigator.clipboard.writeText(mensagemCliente(c));
      b.textContent = 'Mensagem copiada';
    } catch (err) { b.textContent = 'Não consegui copiar'; }
    setTimeout(() => b.textContent = 'Copiar mensagem para o cliente', 2200);
  };
  dlg.querySelectorAll('.sem').forEach(b =>
    b.onclick = () => { dlg.close(); abrir(b.dataset.cod); });
  dlg.showModal();   /* o modo cliente já vem da classe no body */
}

/* ---------- eventos ---------- */
/* O ícone verde na linha abre o WhatsApp direto, sem passar pelo detalhe:
   quem já conhece a carta não quer mais um clique no caminho. Fala com o
   primeiro consultor da lista; para escolher outro, o detalhe traz os três. */
lista.addEventListener('click', e => {
  const z = e.target.closest('[data-zap]');
  if (z && EQUIPE.length) {
    e.stopPropagation();
    const c = CARTAS.find(x => x.cod === z.dataset.zap);
    window.open('https://wa.me/' + EQUIPE[0].fone + '?text=' +
      encodeURIComponent(textoReserva(c)), '_blank', 'noopener');
    return;
  }
  const b = e.target.closest('.linha-c');
  if (b) abrir(b.dataset.cod);
});

document.querySelectorAll('.pill[data-seg]').forEach(b => b.onclick = () => {
  F.seg = b.dataset.seg;
  document.querySelectorAll('.pill[data-seg]').forEach(o =>
    o.classList.toggle('on', o === b));
  render();
});
document.querySelectorAll('.marca-f').forEach(b => b.onclick = () => {
  F.adm = (F.adm === b.dataset.adm) ? '' : b.dataset.adm;
  document.querySelectorAll('.marca-f').forEach(o =>
    o.classList.toggle('on', o.dataset.adm === F.adm && F.adm));
  render();
});
document.querySelectorAll('.faixa').forEach(b => b.onclick = () => {
  const [de, ate] = b.dataset.faixa.split('-').map(Number);
  const ligado = F.de === de && F.ate === ate;
  F.de = ligado ? 0 : de;
  F.ate = ligado ? 0 : ate;
  deEl.value = F.de ? brl0(F.de) : '';
  ateEl.value = F.ate ? brl0(F.ate) : '';
  document.querySelectorAll('.faixa').forEach(o =>
    o.classList.toggle('on', o === b && !ligado));
  render();
});
[deEl, ateEl].forEach(el => el.addEventListener('input', () => {
  const n = num(el.value);
  el.value = n ? brl0(n) : '';
  F[el.id] = n;
  document.querySelectorAll('.faixa').forEach(o => o.classList.remove('on'));
  render();
}));
qEl.addEventListener('input', () => { F.q = qEl.value.trim().toLowerCase();
  render(); });
ordemEl.addEventListener('change', render);
modoEl.addEventListener('change', render);

ativosEl.addEventListener('click', e => {
  const t = e.target.closest('[data-tira]');
  if (!t) return;
  const k = t.dataset.tira;
  if (k === 'faixa') { F.de = F.ate = 0; deEl.value = ateEl.value = '';
    document.querySelectorAll('.faixa').forEach(o => o.classList.remove('on')); }
  else if (k === 'q') { F.q = ''; qEl.value = ''; }
  else if (k === 'adm') { F.adm = '';
    document.querySelectorAll('.marca-f').forEach(o => o.classList.remove('on')); }
  else { F.seg = '';
    document.querySelectorAll('.pill[data-seg]').forEach(o =>
      o.classList.toggle('on', !o.dataset.seg)); }
  render();
});

$('#limpar').onclick = () => {
  F.seg = F.adm = F.q = ''; F.de = F.ate = 0;
  deEl.value = ateEl.value = qEl.value = '';
  ordemEl.value = 'peso';
  document.querySelectorAll('.marca-f,.faixa').forEach(o =>
    o.classList.remove('on'));
  document.querySelectorAll('.pill[data-seg]').forEach(o =>
    o.classList.toggle('on', !o.dataset.seg));
  render();
};

/* No celular os filtros secundários ficam recolhidos. O contador no botão
   diz quantos estão ligados, senão o parceiro fecha o painel e esquece que
   deixou um filtro preso — e conclui que a lista encolheu sozinha. */
$('#btn-filtros').onclick = () => $('.filtros').classList.toggle('aberto');
function contarFiltros() {
  const n = (F.adm ? 1 : 0) + (F.de || F.ate ? 1 : 0);
  const el = $('#n-filtros');
  el.textContent = n;
  el.hidden = !n;
}

$('#mais-marcas').onclick = (e) => {
  const esconde = document.querySelectorAll('.marca-f.extra');
  const abrindo = esconde[0].hidden;
  esconde.forEach(o => o.hidden = !abrindo);
  e.currentTarget.textContent = abrindo
    ? 'mostrar menos' : 'todas as administradoras';
};

render();
"""


# Faixas de crédito prontas: o parceiro raramente sabe o número exato que o
# cliente procura, mas sabe a ordem de grandeza. Os limites saem do que a
# LuME publica de fato — carro popular, carro melhor, apartamento, casa.
FAIXAS = [("0-60000", "Até 60 mil"), ("60000-120000", "60 a 120 mil"),
          ("120000-250000", "120 a 250 mil"), ("250000-0", "Acima de 250 mil")]


def pagina(cartas, cfg, segmentos, quando, equipe):
    insta = (cfg.get("instagram") or "").lstrip("@")
    faq = cfg.get("faq") or []

    # As administradoras vêm do que existe hoje na lista, ordenadas por
    # quantidade: as quatro maiores ficam à vista e o resto abre no "todas".
    contagem = {}
    for c in cartas:
        contagem[c["adm"]] = contagem.get(c["adm"], 0) + 1
    ordenadas = sorted(contagem, key=lambda a: (-contagem[a], a))

    pills_seg = '<button class="pill on" data-seg="">Todas<span class="n"></span></button>'
    pills_seg += "".join(
        f'<button class="pill" data-seg="{s}">{ICONE_SEG.get(s, "")}'
        f'{SEG_ROTULO.get(s, s.title())}<span class="n"></span></button>'
        for s in segmentos)

    faixas_html = "".join(
        f'<button class="pill faixa" data-faixa="{v}">{r}</button>'
        for v, r in FAIXAS)

    marcas_html = "".join(
        f'<button class="marca-f{"" if i < 6 else " extra"}" data-adm="{html.escape(a)}"'
        f'{"" if i < 6 else " hidden"}><i style="background:{cor_adm(a)}"></i>'
        f'{html.escape(a)}</button>' for i, a in enumerate(ordenadas))

    faq_html = "".join(
        f'<details><summary>{html.escape(q["p"])}</summary>'
        f'<p>{html.escape(q["r"])}</p></details>' for q in faq)

    plantao_html = "".join(
        f'<a href="https://wa.me/{p["fone"]}" target="_blank" rel="noopener">'
        f'{ZAP_SVG}{html.escape(p["nome"].split()[0])}</a>' for p in equipe)
    equipe_html = "".join(
        f'<a href="https://wa.me/{p["fone"]}" target="_blank" rel="noopener">'
        f'{ZAP_SVG}{html.escape(p["nome"])}</a>' for p in equipe)

    js = (JS.replace("__CARTAS__", dados_js(cartas))
            .replace("__ROT__", json.dumps(SEG_ROTULO, ensure_ascii=False))
            .replace("__EQUIPE__", json.dumps(equipe, ensure_ascii=False))
            .replace("__CORES__", json.dumps(
                {a: cor_adm(a) for a in contagem}, ensure_ascii=False))
            .replace("__ICONES__", json.dumps(ICONE_SEG, ensure_ascii=False))
            .replace("__ZAP__", json.dumps(ZAP_SVG)))

    return f'''<!DOCTYPE html>
<!-- gerado em {quando} — fora da vista do parceiro de propósito; serve só
     para conferir, no código-fonte, se a publicação travou num dia antigo -->
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="theme-color" content="#0B0B0C">
<title>Vision — Cartas contempladas disponíveis</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
</head>
<body>

<header class="barra">
  <div class="barra-in">
    <img src="{logo_base64()}" alt="Vision">
    <div>
      <h1>Cartas contempladas</h1>
      <div class="sub">Área do parceiro · Vision</div>
    </div>
  </div>
</header>

<div class="filtros">
  <div class="filtros-in">
    <div class="fl">
      <span class="rot">Segmento</span>
      {pills_seg}
      <button class="btn-filtros" id="btn-filtros">Filtros
        <span class="n2" id="n-filtros" hidden>0</span></button>
    </div>
    <div class="fl secundaria">
      <span class="rot">Crédito</span>
      {faixas_html}
      <div class="campo"><span>De</span>
        <input id="de" type="text" inputmode="numeric" placeholder="mín."></div>
      <div class="campo"><span>Até</span>
        <input id="ate" type="text" inputmode="numeric" placeholder="máx."></div>
    </div>
    <div class="fl secundaria">
      <span class="rot">Administradora</span>
      {marcas_html}
      <button class="mais-marcas" id="mais-marcas">todas as administradoras</button>
    </div>
    <div class="fl">
      <input id="q" type="search" placeholder="Buscar por código ou administradora">
      <select id="ordem">
        <option value="peso">Menor entrada sobre o crédito</option>
        <option value="entrada">Menor entrada</option>
        <option value="parcela">Menor parcela</option>
        <option value="credito">Maior crédito</option>
        <option value="credito-asc">Menor crédito</option>
        <option value="comissao">Maior comissão</option>
      </select>
      <button class="limpar" id="limpar">Limpar filtros</button>
    </div>
  </div>
</div>

<div class="conta-bar">
  <b id="conta"></b>
  <div class="ativos" id="ativos"></div>
  <label class="modo"><input type="checkbox" id="modo">Modo cliente</label>
</div>

<main>
  <div class="quadro">
    <div class="cab">
      <span>Segmento</span><span>Administradora</span>
      <span class="dir">Valor do crédito</span><span class="dir">Entrada</span>
      <span class="dir">Parcelas</span><span class="dir">Valor das parcelas</span>
      <span class="dir">Custo total</span>
      <span class="dir" data-com>Sua comissão</span>
      <span></span>
    </div>
    <ul id="lista"></ul>
  </div>
  <div id="vazio"><b>Nenhuma carta com esses filtros</b>
    Tente outra faixa de crédito ou limpe os filtros.</div>
</main>

<section class="faq">
  <h2>Dúvidas frequentes</h2>
  {faq_html}
</section>

<footer>
  <div class="pe">
    <div class="plantao">
      <div><b>Plantão de dúvidas</b><br>
        Dúvida sobre uma carta específica? Chame qualquer um dos três com o
        código em mãos.</div>
      <div class="plantao-zaps">{plantao_html}</div>
    </div>
    <div class="bloco">
      <h2>Vision</h2>
      <div>{html.escape(cfg.get("endereco", ""))}</div>
      <div>CNPJ {html.escape(cfg.get("cnpj", ""))}</div>
    </div>
    <div class="bloco">
      <h2>Consultores</h2>
      {equipe_html}
    </div>
    <div class="bloco">
      <h2>Atendimento</h2>
      <div>{html.escape(cfg.get("horario", ""))}</div>
      <a href="https://instagram.com/{html.escape(insta)}" target="_blank"
         rel="noopener">Instagram @{html.escape(insta)}</a>
    </div>
    <p class="nota">As cartas saem da lista ao longo do dia — a
      disponibilidade é confirmada no momento da reserva. O custo total é a
      soma da entrada com todas as parcelas restantes da cota. As
      administradoras aparecem identificadas pelo nome; a Vision não
      representa nenhuma delas.</p>
  </div>
</footer>

<script>{js}</script>
</body>
</html>'''


def gerar(cotas, cfg, destino, quando):
    cartas = preparar(cotas, {"nome": "Vision"})
    segmentos = sorted({c["seg"] for c in cartas})
    equipe = equipe_de(cfg)
    if not equipe:
        raise SystemExit("Nenhum consultor com WhatsApp válido em config.json — "
                         "a página sairia sem como reservar carta nenhuma.")
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(pagina(cartas, cfg, segmentos, quando, equipe))
    # o log da rodada mostra as margens em vigor. Como o ágio não aparece na
    # página, é aqui que dá para conferir se o Secret está no valor certo.
    a = float(os.environ.get("AGIO_CREDITO") or 0.05)
    k = float(os.environ.get("COMISSAO_CREDITO") or 0.02)
    print(f"margens: ágio {a:.1%} do crédito na entrada · "
          f"comissão do parceiro {k:.1%} · fica com a Vision {a - k:.1%}")
    print(f"Vision {len(cartas):3d} cartas · "
          f"{len(equipe)} consultores → {destino}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cotas", nargs="?", default="cotas.json")
    # --marca e --todas geravam uma página por parceiro. A Alê e a Cred Cris
    # não usam o site — recebem os PNGs pelo Drive — então as páginas foram
    # removidas. As opções continuam aceitas e ignoradas só para não quebrar
    # o workflow que já está no ar.
    ap.add_argument("--marca", help=argparse.SUPPRESS)
    ap.add_argument("--todas", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--saida", default="site")
    a = ap.parse_args()

    cfg = json.load(open("config.json", encoding="utf-8"))
    pendentes = [k for k, v in cfg.items()
                 if isinstance(v, str) and v.startswith("PREENCHER")]
    if pendentes:
        print("AVISO: config.json ainda com placeholder em: " + ", ".join(pendentes))
        print("       O rodapé sai incompleto até você preencher.\n")
    for chave, c in (cfg.get("consultores") or {}).items():
        try:
            c["_fone"] = normalizar_fone(c.get("fone", ""), f"consultor {chave}")
        except SystemExit:
            c["_fone"] = ""
            print(f"AVISO: WhatsApp do consultor '{chave}' inválido — "
                  f"os botões dele não vão abrir conversa.")

    cotas = json.load(open(a.cotas, encoding="utf-8"))
    quando = datetime.now().strftime("%d/%m/%Y às %Hh%M")

    if a.marca or a.todas:
        print("NOTA: --marca/--todas não fazem mais nada. O site é uma página\n"
              "      só; Alê e Cred Cris recebem as cartas pelo Drive.\n")

    gerar(cotas, cfg, os.path.join(a.saida, "index.html"), quando)


if __name__ == "__main__":
    main()
