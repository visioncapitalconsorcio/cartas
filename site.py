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
    """
    agio = float(os.environ.get("AGIO_CREDITO") or marca.get("agio_credito", 0.05))
    com = float(os.environ.get("COMISSAO_CREDITO")
                or marca.get("comissao_credito", 0.02))
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


def pagina(cartas, cfg, segmentos, quando, equipe):
    insta = (cfg.get("instagram") or "").lstrip("@")
    faq = cfg.get("faq") or []

    ops_seg = "".join(
        f'<button class="fseg" data-v="{s}">{SEG_ROTULO.get(s, s.title())}</button>'
        for s in segmentos)
    faq_html = "".join(
        f'<details><summary>{html.escape(q["p"])}</summary>'
        f'<p>{html.escape(q["r"])}</p></details>' for q in faq)

    plantao_html = "".join(
        f'<a href="https://wa.me/{p["fone"]}" target="_blank" rel="noopener">'
        f'{html.escape(p["nome"].split()[0])}</a>' for p in equipe)
    equipe_html = "".join(
        f'<a href="https://wa.me/{p["fone"]}" target="_blank" rel="noopener">'
        f'{html.escape(p["nome"])} · WhatsApp</a>' for p in equipe)

    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>Vision — Cartas contempladas disponíveis</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>
  :root{{
    --void:#0B0B0C; --sup:#141416; --sup2:#191A1D; --linha:#1B1C20;
    --s1:#FDFDFD; --s2:#C9CCD1; --s3:#9CA0A6; --s4:#6B6E72;
    --sans:'Geist','Inter',system-ui,-apple-system,sans-serif;
    --mono:'Geist Mono','IBM Plex Mono',ui-monospace,monospace;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--void);color:var(--s2);font-family:var(--sans);
    font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}}
  .wrap{{max-width:1180px;margin:0 auto;padding:24px 18px 90px}}
  a{{color:inherit}}
  :focus-visible{{outline:2px solid var(--s2);outline-offset:2px}}

  .topo{{display:flex;align-items:center;gap:18px;flex-wrap:wrap;
    padding-bottom:20px;border-bottom:1px solid var(--linha)}}
  .topo img{{width:46px;height:auto;display:block}}
  .topo h1{{font-size:20px;font-weight:600;letter-spacing:-.015em;
    color:var(--s1);line-height:1.2}}
  .topo .sub{{font-family:var(--mono);font-size:10px;letter-spacing:.24em;
    text-transform:uppercase;color:var(--s4);margin-top:3px}}
  .quando{{margin-left:auto;font-family:var(--mono);font-size:11px;
    letter-spacing:.08em;color:var(--s4);text-align:right;line-height:1.5}}

  .busca{{padding:22px 0 18px;border-bottom:1px solid var(--linha);
    display:flex;flex-direction:column;gap:14px}}
  .rot{{font-family:var(--mono);font-size:10px;letter-spacing:.2em;
    text-transform:uppercase;color:var(--s4)}}
  .linha-f{{display:flex;flex-wrap:wrap;gap:9px;align-items:center}}
  button,select,input{{font-family:var(--sans);font-size:14px;color:var(--s2);
    background:var(--sup);border:1px solid var(--linha);border-radius:8px;
    padding:10px 15px;cursor:pointer}}
  input{{cursor:text}}
  button:hover,select:hover{{border-color:#33353B;color:var(--s1)}}
  button.on{{background:var(--s1);border-color:var(--s1);color:var(--void);
    font-weight:600}}
  .campo{{display:flex;align-items:center;gap:9px;background:var(--sup);
    border:1px solid var(--linha);border-radius:8px;padding:0 14px 0 15px}}
  .campo span{{font-family:var(--mono);font-size:10px;letter-spacing:.14em;
    text-transform:uppercase;color:var(--s4);white-space:nowrap}}
  .campo input{{border:0;background:none;padding:10px 0;width:120px;
    font-variant-numeric:tabular-nums}}
  #q{{flex:1;min-width:200px}}

  .barra2{{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
    padding:16px 0 0}}
  .conta{{font-family:var(--mono);font-size:11px;letter-spacing:.1em;
    color:var(--s3)}}
  .toggle{{margin-left:auto;display:flex;align-items:center;gap:9px;
    font-size:13px;color:var(--s3);cursor:pointer;user-select:none}}
  .toggle input{{appearance:none;width:38px;height:21px;border-radius:99px;
    background:var(--sup);border:1px solid var(--linha);position:relative;
    padding:0;transition:background .15s}}
  .toggle input::after{{content:"";position:absolute;top:2px;left:2px;
    width:15px;height:15px;border-radius:50%;background:var(--s3);
    transition:transform .15s}}
  .toggle input:checked{{background:var(--s1);border-color:var(--s1)}}
  .toggle input:checked::after{{transform:translateX(17px);background:var(--void)}}

  ul{{list-style:none;display:flex;flex-direction:column;gap:1px;
    margin-top:14px;background:var(--linha);border:1px solid var(--linha);
    border-radius:10px;overflow:hidden}}
  li{{background:var(--void)}}
  .carta{{display:grid;gap:12px 20px;padding:16px 18px;align-items:start;
    grid-template-columns:1fr;width:100%;text-align:left;background:none;
    border:0;border-radius:0}}
  .carta:hover{{background:var(--sup2)}}
  @media (min-width:900px){{
    .carta{{grid-template-columns:152px 1fr 1fr .85fr 1fr .9fr}}
  }}
  .ident{{display:flex;flex-wrap:wrap;align-items:center;gap:8px}}
  .cod{{font-family:var(--mono);font-size:13px;font-weight:500;
    letter-spacing:.06em;color:var(--s1)}}
  .chip{{font-family:var(--mono);font-size:9px;letter-spacing:.14em;
    text-transform:uppercase;padding:3px 9px;border-radius:99px;
    border:1px solid var(--linha);color:var(--s3);white-space:nowrap}}
  .adm{{font-size:12px;color:var(--s4)}}
  .col{{display:flex;flex-direction:column;gap:1px;min-width:0}}
  .col .k{{font-family:var(--mono);font-size:9px;letter-spacing:.16em;
    text-transform:uppercase;color:var(--s4)}}
  .col b{{font-size:16px;font-weight:600;color:var(--s1);
    font-variant-numeric:tabular-nums;letter-spacing:-.01em}}
  .col .m{{font-size:11.5px;color:var(--s4);font-variant-numeric:tabular-nums}}
  .col.total b{{font-size:17px}}
  .oculto{{display:none !important}}
  .vazio{{padding:46px 6px;color:var(--s3);text-align:center;display:none}}

  dialog{{margin:auto;border:1px solid var(--linha);background:var(--sup);
    color:var(--s2);border-radius:12px;padding:0;max-width:620px;
    width:calc(100% - 32px);max-height:88vh;overflow:auto}}
  dialog::backdrop{{background:rgba(0,0,0,.74)}}
  .d-top{{display:flex;align-items:center;gap:11px;flex-wrap:wrap;
    padding:19px 22px 15px;border-bottom:1px solid var(--linha)}}
  .d-top .cod{{font-size:16px}}
  .d-fechar{{margin-left:auto;padding:7px 13px;font-size:13px}}
  .d-corpo{{padding:16px 22px 4px}}
  .lin{{display:flex;justify-content:space-between;align-items:baseline;
    gap:16px;padding:11px 0;border-bottom:1px solid var(--linha)}}
  .lin .k{{font-family:var(--mono);font-size:10px;letter-spacing:.16em;
    text-transform:uppercase;color:var(--s4)}}
  .lin .v{{font-size:16px;color:var(--s1);font-variant-numeric:tabular-nums;
    text-align:right}}
  .lin.destaque{{border-bottom:0}}
  .lin.destaque .v{{font-size:21px;font-weight:600}}
  .acoes{{display:flex;flex-wrap:wrap;gap:9px;padding:16px 22px 18px}}
  .acoes button,.acoes a{{flex:1;min-width:172px;text-align:center;
    text-decoration:none;padding:12px;font-weight:500}}
  .acoes .primaria{{background:var(--s1);border-color:var(--s1);
    color:var(--void);font-weight:600}}
  .reservar{{padding:0 22px 18px}}
  .reservar h3{{font-family:var(--mono);font-size:10px;letter-spacing:.2em;
    text-transform:uppercase;color:var(--s4);font-weight:500;margin-bottom:7px}}
  .reservar p{{font-size:13.5px;color:var(--s3);margin-bottom:11px}}
  .reservar .cons{{display:flex;flex-wrap:wrap;gap:9px}}
  .reservar .cons a{{flex:1;min-width:150px;display:flex;flex-direction:column;
    gap:2px;align-items:center;padding:12px 10px;border:1px solid var(--linha);
    border-radius:9px;background:var(--sup);text-decoration:none}}
  .reservar .cons a:hover{{border-color:var(--s1)}}
  .reservar .cons b{{color:var(--s1);font-size:14px;font-weight:600}}
  .reservar .cons em{{font-family:var(--mono);font-size:10px;letter-spacing:.16em;
    text-transform:uppercase;color:var(--s4);font-style:normal}}
  .regras{{margin:14px 0 2px;padding:15px 16px;background:var(--void);
    border:1px solid var(--linha);border-radius:9px}}
  .regras h3{{font-family:var(--mono);font-size:10px;letter-spacing:.2em;
    text-transform:uppercase;color:var(--s4);font-weight:500;margin-bottom:9px}}
  .regras pre{{font-family:var(--sans);font-size:13.5px;line-height:1.6;
    color:var(--s2);white-space:pre-wrap;word-break:break-word;margin:0}}
  .aviso-taxa{{margin-top:11px;padding-top:11px;border-top:1px solid var(--linha);
    font-size:12.5px;color:var(--s4)}}
  .semelhantes{{padding:0 22px 20px}}
  .semelhantes h3{{font-family:var(--mono);font-size:10px;letter-spacing:.2em;
    text-transform:uppercase;color:var(--s4);font-weight:500;margin-bottom:9px}}
  .sem{{display:flex;justify-content:space-between;gap:14px;width:100%;
    padding:11px 13px;margin-bottom:6px;font-size:13.5px;text-align:left}}
  .sem b{{color:var(--s1);font-variant-numeric:tabular-nums}}
  .sem em{{color:var(--s4);font-family:var(--mono);font-size:11px;
    font-style:normal}}

  section.faq{{margin-top:46px;padding-top:26px;border-top:1px solid var(--linha)}}
  section.faq h2,footer h2{{font-family:var(--mono);font-size:10px;
    letter-spacing:.24em;text-transform:uppercase;color:var(--s4);
    font-weight:500;margin-bottom:12px}}
  details{{border-bottom:1px solid var(--linha)}}
  summary{{padding:13px 0;cursor:pointer;color:var(--s1);font-weight:500;
    list-style:none}}
  summary::-webkit-details-marker{{display:none}}
  summary::before{{content:"+  ";color:var(--s4);font-family:var(--mono)}}
  details[open] summary::before{{content:"−  "}}
  details p{{padding:0 0 15px;color:var(--s3);max-width:70ch;font-size:14.5px}}

  footer{{margin-top:44px;padding-top:26px;border-top:1px solid var(--linha);
    display:grid;gap:24px;grid-template-columns:1fr}}
  @media (min-width:760px){{footer{{grid-template-columns:1.3fr 1fr 1fr}}}}
  .plantao{{grid-column:1/-1;background:var(--sup);border:1px solid var(--linha);
    border-radius:10px;padding:18px 20px;display:flex;flex-wrap:wrap;
    gap:14px 22px;align-items:center}}
  .plantao b{{color:var(--s1);font-weight:600}}
  .plantao div{{font-size:14px;color:var(--s3)}}
  .plantao-zaps{{margin-left:auto;display:flex;flex-wrap:wrap;gap:8px}}
  .plantao-zaps a{{background:var(--s1);color:var(--void);
    padding:11px 20px;border-radius:8px;font-weight:600;text-decoration:none;
    white-space:nowrap}}
  .bloco{{display:flex;flex-direction:column;gap:6px;font-size:14px;
    color:var(--s3)}}
  .bloco a{{color:var(--s2);text-decoration:none;width:fit-content}}
  .bloco a:hover{{color:var(--s1);text-decoration:underline}}
  .nota{{grid-column:1/-1;font-size:12.5px;color:var(--s4);max-width:82ch;
    padding-top:6px}}
</style>
</head>
<body>
<div class="wrap">

  <div class="topo">
    <img src="{logo_base64()}" alt="Vision">
    <div>
      <h1>Cartas contempladas</h1>
      <div class="sub">Área do parceiro · Vision</div>
    </div>
    <div class="quando">Atualizado<br>{quando}</div>
  </div>

  <div class="busca">
    <div>
      <div class="rot">O que o cliente procura</div>
      <div class="linha-f" style="margin-top:10px">
        <button class="fseg on" data-v="">Todos</button>
        {ops_seg}
        <div class="campo"><span>Crédito de aprox.</span>
          <input id="alvo" type="text" inputmode="numeric" placeholder="30.000"></div>
        <input id="q" type="search" placeholder="Buscar por código ou administradora">
      </div>
    </div>
    <div class="linha-f">
      <select id="ordem">
        <option value="proximo">Mais próximo do valor procurado</option>
        <option value="peso">Menor entrada sobre o crédito</option>
        <option value="credito">Maior crédito</option>
        <option value="credito-asc">Menor crédito</option>
        <option value="comissao">Maior comissão</option>
      </select>
      <button id="limpar">Limpar filtros</button>
    </div>
  </div>

  <div class="barra2">
    <span class="conta" id="conta"></span>
    <label class="toggle"><input type="checkbox" id="modo">
      Modo cliente — esconde a comissão</label>
  </div>

  <ul id="lista"></ul>
  <p class="vazio" id="vazio">Nenhuma carta com esses filtros.<br>
     Tente outro valor de crédito ou limpe os filtros.</p>

  <section class="faq">
    <h2>Dúvidas frequentes</h2>
    {faq_html}
  </section>

  <footer>
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
      soma da entrada com todas as parcelas restantes da cota.</p>
  </footer>

</div>

<script>
const CARTAS = {dados_js(cartas)};
const ROT = {json.dumps(SEG_ROTULO, ensure_ascii=False)};
const EQUIPE = {json.dumps(equipe, ensure_ascii=False)};
const lista = document.getElementById('lista');
const vazio = document.getElementById('vazio');
const conta = document.getElementById('conta');
const alvoEl = document.getElementById('alvo');
const qEl = document.getElementById('q');
const ordemEl = document.getElementById('ordem');
const modoEl = document.getElementById('modo');
let seg = '';

const brl = n => n.toLocaleString('pt-BR',
  {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
const brl0 = n => n.toLocaleString('pt-BR', {{maximumFractionDigits: 0}});
const numAlvo = () => {{
  const d = alvoEl.value.replace(/\\D/g, '');
  return d ? parseInt(d, 10) : 0;
}};
const parcelasTexto = c =>
  c.parc ? c.parcelas + 'x escalonadas' : c.parcelas + 'x R$ ' + brl(c.valorParcela);

/* O interruptor fica lembrado: o parceiro não reativa a cada visita. */
try {{ modoEl.checked = localStorage.getItem('modoCliente') === '1'; }} catch (e) {{}}
function aplicarModo() {{
  document.querySelectorAll('[data-com]').forEach(el =>
    el.classList.toggle('oculto', modoEl.checked));
  try {{ localStorage.setItem('modoCliente', modoEl.checked ? '1' : '0'); }}
  catch (e) {{}}
}}

function filtrar() {{
  const alvo = numAlvo(), q = qEl.value.trim().toLowerCase();
  const r = CARTAS.filter(c =>
    (!seg || c.seg === seg) &&
    (!q || (c.cod + ' ' + c.adm).toLowerCase().includes(q)) &&
    (!alvo || Math.abs(c.credito - alvo) / alvo <= 0.30));
  const ord = {{
    proximo: (a, b) => alvo
      ? Math.abs(a.credito - alvo) - Math.abs(b.credito - alvo)
      : a.peso - b.peso,
    peso: (a, b) => a.peso - b.peso,
    credito: (a, b) => b.credito - a.credito,
    'credito-asc': (a, b) => a.credito - b.credito,
    comissao: (a, b) => b.comissao - a.comissao,
  }}[ordemEl.value];
  return r.sort(ord);
}}

function linha(c) {{
  const detalhe = c.parc ? 'escalonadas' : 'R$ ' + brl(c.valorParcela);
  return '<li><button class="carta" data-cod="' + c.cod + '">' +
    '<span class="ident"><span class="cod">' + c.cod + '</span>' +
      '<span class="chip">' + (ROT[c.seg] || c.seg) + '</span>' +
      '<span class="adm">' + c.adm + '</span></span>' +
    '<span class="col"><span class="k">Crédito</span><b>R$ ' +
      brl(c.credito) + '</b></span>' +
    '<span class="col"><span class="k">Entrada</span><b>R$ ' +
      brl(c.entradaFinal) + '</b><span class="m">' +
      Math.round(c.peso * 100) + '% do crédito</span></span>' +
    '<span class="col"><span class="k">Parcelas</span><b>' + c.parcelas +
      'x</b><span class="m">' + detalhe + '</span></span>' +
    '<span class="col total"><span class="k">Custo total</span><b>R$ ' +
      brl(c.custoTotal) + '</b><span class="m">+' +
      Math.round(c.acima * 100) + '% sobre o crédito</span></span>' +
    '<span class="col" data-com><span class="k">Sua comissão</span><b>R$ ' +
      brl(c.comissao) + '</b></span></button></li>';
}}

function render() {{
  const r = filtrar();
  lista.innerHTML = r.map(linha).join('');
  conta.textContent = r.length + (r.length === 1 ? ' carta' : ' cartas');
  vazio.style.display = r.length ? 'none' : 'block';
  aplicarModo();
}}

const dlg = document.createElement('dialog');
document.body.appendChild(dlg);

function semelhantes(c) {{
  return CARTAS
    .filter(o => o.cod !== c.cod && o.seg === c.seg &&
                 Math.abs(o.credito - c.credito) / c.credito <= 0.25)
    .sort((a, b) => Math.abs(a.credito - c.credito) -
                    Math.abs(b.credito - c.credito))
    .slice(0, 4);
}}

function mensagemCliente(c) {{
  const parc = c.parc || (c.parcelas + 'x de R$ ' + brl(c.valorParcela));
  return '*Carta contemplada ' + c.cod + '* — ' + (ROT[c.seg] || c.seg) +
    '\\n\\nCrédito: R$ ' + brl(c.credito) +
    '\\nEntrada: R$ ' + brl(c.entradaFinal) +
    '\\nParcelas: ' + parc +
    '\\nCusto total: R$ ' + brl(c.custoTotal) +
    '\\n\\nA disponibilidade é confirmada na reserva. Me chame para garantir esta carta.';
}}

function abrir(cod) {{
  const c = CARTAS.find(x => x.cod === cod);
  if (!c) return;
  const parc = c.parc || (c.parcelas + 'x de R$ ' + brl(c.valorParcela));
  const sem = semelhantes(c);
  dlg.innerHTML =
    '<div class="d-top"><span class="cod">' + c.cod + '</span>' +
      '<span class="chip">' + (ROT[c.seg] || c.seg) + '</span>' +
      '<span class="adm">' + c.adm + '</span>' +
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
    '<div style="padding:0 22px">' +
      (c.regras
        ? '<div class="regras"><h3>Regras para uso desta carta</h3><pre>' +
          c.regras.replace(/[&<>]/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[m])) +
          '</pre><p class="aviso-taxa">A taxa de transferência é cobrada pela ' +
          'administradora e <b>não está incluída no custo total acima</b>.</p></div>'
        : '<div class="regras"><h3>Regras para uso desta carta</h3>' +
          '<pre>Regras não informadas para esta administradora. ' +
          'Confirme com a Vision antes de fechar.</pre></div>') +
    '</div>' +
    '<div class="acoes">' +
      '<button class="primaria" id="copiar">Copiar mensagem para o cliente</button>' +
    '</div>' +
    '<div class="reservar"><h3>Reservar esta carta</h3>' +
      '<p>Chame qualquer um dos três — todos atendem esta lista. A mensagem ' +
      'já vai com o código da carta.</p>' +
      '<div class="cons">' + EQUIPE.map(p =>
        '<a href="https://wa.me/' + p.fone + '?text=' + encodeURIComponent(
          'Tenho interesse na carta ' + c.cod + ' — crédito R$ ' +
          brl(c.credito) + '. Ela está disponível?') +
        '" target="_blank" rel="noopener"><b>' + p.nome +
        '</b><em>WhatsApp</em></a>').join('') + '</div>' +
    '</div>' +
    '<div class="semelhantes"><h3>Cartas semelhantes</h3>' +
      (sem.length ? sem.map(s =>
        '<button class="sem" data-cod="' + s.cod + '">' +
        '<span><b>R$ ' + brl0(s.credito) + '</b> · entrada R$ ' +
        brl0(s.entradaFinal) + '</span><em>' + s.cod + '</em></button>').join('')
       : '<p style="color:var(--s4);font-size:13.5px">Nenhuma carta parecida hoje.</p>') +
    '</div>';
  dlg.querySelector('#fechar').onclick = () => dlg.close();
  dlg.querySelector('#copiar').onclick = async (e) => {{
    const b = e.currentTarget;
    try {{
      await navigator.clipboard.writeText(mensagemCliente(c));
      b.textContent = 'Mensagem copiada';
    }} catch (err) {{ b.textContent = 'Não consegui copiar'; }}
    setTimeout(() => b.textContent = 'Copiar mensagem para o cliente', 2200);
  }};
  dlg.querySelectorAll('.sem').forEach(b =>
    b.onclick = () => {{ dlg.close(); abrir(b.dataset.cod); }});
  aplicarModo();
  dlg.showModal();
}}

lista.addEventListener('click', e => {{
  const b = e.target.closest('.carta');
  if (b) abrir(b.dataset.cod);
}});
document.querySelectorAll('.fseg').forEach(b => b.onclick = () => {{
  document.querySelectorAll('.fseg').forEach(o => o.classList.remove('on'));
  b.classList.add('on');
  seg = b.dataset.v;
  render();
}});
alvoEl.addEventListener('input', () => {{
  const d = alvoEl.value.replace(/\\D/g, '');
  alvoEl.value = d ? parseInt(d, 10).toLocaleString('pt-BR') : '';
  render();
}});
qEl.addEventListener('input', render);
ordemEl.addEventListener('change', render);
modoEl.addEventListener('change', aplicarModo);
document.getElementById('limpar').onclick = () => {{
  alvoEl.value = ''; qEl.value = ''; ordemEl.value = 'proximo';
  document.querySelectorAll('.fseg').forEach(o => o.classList.remove('on'));
  document.querySelector('.fseg').classList.add('on');
  seg = '';
  render();
}};
render();
</script>
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
