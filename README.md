# Cartas contempladas — site do parceiro

Coleta a tabela do Grupo LuME, precifica com o ágio da Vision e publica um
catálogo estático para os parceiros credenciados.

## Como roda

`.github/workflows/atualizar.yml` executa a cada 30 minutos, das 6h às 20h
de Brasília, e também sempre que alguém aperta **Run workflow**:

1. `coletor.py` lê a tabela e as regras de uso de cada administradora
   (cache em `regras-lume.json`, ~31 páginas por rodada, não uma por cota);
2. `site.py` gera `site/index.html` e as variantes por parceiro;
3. o resultado é comitado e publicado.

## Margens

`AGIO_CREDITO` e `COMISSAO_CREDITO` são lidos das variáveis de ambiente e,
na falta delas, do `marcas/*.json`. Em repositório público, cadastre os dois
em **Settings › Secrets and variables › Actions** e deixe o JSON com valores
de referência — assim a margem real não fica no código.

## Contatos e rodapé

Tudo em `config.json`: WhatsApp, Instagram, endereço, CNPJ, horário e o FAQ.

## O que nunca entra aqui

O ID de cota da LuME. Ele é usado só para montar a URL das regras durante a
execução e descartado em seguida — não existe no `cotas.json` nem no site.
