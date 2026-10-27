# Redes Neurais com dados de apuração do TSE

Estudo sobre a **progressão da apuração**: prever o resultado final de uma eleição
a partir de uma apuração parcial.

## Dados

Boletins de Urna (BU Web) do TSE — 1 registro por seção eleitoral, com o campo
`DT_BU_RECEBIDO` (hora exata em que a urna transmitiu). É o único arquivo público
que permite reconstruir a apuração minuto a minuto.

| Pleito | BUs | tem `DT_BU_RECEBIDO`? |
|---|---|---|
| 2014 | sim | não (zip sem CSV, formato antigo) |
| 2018 | sim | **não** — só `DT_ABERTURA` / `DT_ENCERRAMENTO` |
| 2022 1º e 2º turno | sim | **sim** |
| 2026 1º turno | sim | sim |
| 2026 2º turno (25/10) | **ainda não** | — |

O campo `DT_BU_RECEBIDO` só aparece a partir de 2022. Antes disso não dá para
reconstruir a ordem de transmissão — no máximo aproximar por `DT_ENCERRAMENTO`,
que é quando a seção fechou, não quando transmitiu. Comparação entre pleitos
antigos fica limitada a isso.

```bash
python src/baixar_tse.py 2022 2     # ~27 UFs, alguns GB
python src/montar_serie.py 2022 2   # gera os .parquet
```

## Estrutura

```
src/baixar_tse.py     baixa os BUs via API CKAN do TSE
src/montar_serie.py   BU bruto -> secoes_*.parquet + serie_*.parquet
dados/bruto/          CSVs do TSE (fora do git)
dados/processado/     parquet
```

`secoes_*.parquet` — 1 linha por seção: votos por candidato, aptos,
comparecimento, timestamps, município/zona.
`serie_*.parquet` — curva acumulada na ordem de chegada = o gráfico da TV.

## Roteiro

**Exp. 0 — separar matemática de informação (sem rede neural).**
`python src/exp0_funil.py 2022 2` — três painéis:
ordem real / ordem embaralhada 30× / funil teórico (±1,96 EP).
O funil aparece nos três, porque a variância de uma média acumulada cai com ~1/√n.
O que **só** aparece no painel A é o drift — urnas não chegam em ordem aleatória.
Esse excesso sobre o envelope aleatório é exatamente o que uma rede pode aprender;
o resto é aritmética.

**Exp. 1 — baseline sem rede.** `python src/exp1_baseline.py 2022 2`
Estimador de razão pós-estratificado. Única informação externa: `QT_APTOS`
(cadastro eleitoral, público antes da eleição) — nada do resultado final.

Erro absoluto (pp) na estimativa do resultado final de 2022:

| % apurado | B0 ingênuo | B1 por UF | B2 por município | cobertura munic. |
|---:|---:|---:|---:|---:|
| 1% | 7,33 | 0,57 | 5,51 | 24% |
| 5% | 4,27 | 1,65 | 2,43 | 44% |
| 10% | 2,91 | 0,82 | 1,33 | 58% |
| 50% | 1,21 | 0,82 | 0,82 | 92% |
| 80% | 0,60 | 0,41 | 0,31 | 97% |

**B1 (UF) é o baseline a bater: ~0,5–1,5 pp a partir de 1% apurado**, contra
2–7 pp do ingênuo. Mas é *instável* — oscila (0,57 → 1,43 → 0,51 → 1,65) sem
convergir de forma monótona. Valores como 0,06 pp em 0,25% apurado são sorte,
não competência; não usar ponto único como referência.

Por que UF bate município: com 0,25% apurado, **78% do eleitorado já está em UFs
com alguma seção apurada, contra 16% dos municípios**. Estrato fino sem cobertura
cai no fallback nacional, que é justamente o número enviesado. Município só supera
UF a partir de ~65% apurado.

**Teto deste approach:** sem prior externo, estratos vazios não têm para onde
recorrer. É isso que o Exp. 2+ precisa resolver — e é o argumento para usar o
**1º turno como prior** de cada estrato.

**Exp. 2 — MLP.**
Entrada: features da parcial (% apurado, resultado parcial, composição por UF
das urnas já apuradas, quanto cada UF ainda deve). Saída: % final.
Treino com milhares de cortes da apuração real + reamostragens da ordem.

**Exp. 3 — sequência.**
GRU/LSTM ou Transformer sobre a sequência de urnas. Aqui a ordem vira a
informação principal, e o modelo pode aprender a logística da transmissão.

**Exp. 4 — embeddings.**
Embedding por município/zona treinado junto. É a parte mais interessante: a rede
constrói sozinha um mapa político do Brasil, e dá pra visualizar com UMAP/t-SNE.

## Resultado do Exp. 0 (2022, 2º turno — 472.028 seções)

Reconstrução bateu o oficial: Lula 50,90% / Bolsonaro 49,10%. O pico inicial da
curva deu **57,3%**, contra os "57,7%" exibidos na TV — a diferença cabe no
critério de desempate de timestamp.

Erro em relação ao resultado final, por estágio da apuração:

| % apurado | curva real | ordem embaralhada (p95) | razão |
|---:|---:|---:|---:|
| 1% | 7,33 pp | 0,39 pp | 19× |
| 10% | 2,91 pp | 0,12 pp | 24× |
| 50% | 1,21 pp | 0,05 pp | 24× |

A curva real fica fora do p95 do embaralhado em **99,9%** do intervalo 0,1%–50%.
Ou seja: o funil estatístico é quase irrelevante na prática — **o que se vê na TV
é essencialmente geografia e logística de transmissão**, não ruído amostral.

O vaivém da curva (57% → 43,5% → 50,9%) é totalmente explicado pela ordem das UFs:

| fase | % Lula | UFs dominantes |
|---|---:|---|
| pico | 54,4% | ZZ (exterior) 81% — fuso à frente, amostra minúscula |
| fundo | 43,7% | DF 29%, PR 23% — transmitem cedo, ambas pró-Bolsonaro |
| final | 52,1% | SP 28%, MG 14%, RJ 10%, BA 8% + MA/PE fecham por último |

Mediana de transmissão: DF 2,5% · PR cedo · **SP 62,1% · MA 63,9% · PE 64,7% ·
MG 66,7%**. Correlação entre ordem de transmissão da UF e % de Lula na UF: **+0,25**
(sobre 27 unidades — direção clara, magnitude pouco robusta).

**Consequência para o projeto:** a feature mais informativa não é o resultado
parcial, é *quais seções ainda faltam*. Uma rede que recebe a composição
geográfica do que falta tem muito mais a aprender do que uma que só vê a curva.

## Armadilha principal

A série acumulada é quase uma constante: `y[t] ≈ y[t-1]`. Treinar uma rede para
prever o próximo ponto dá R² ~0,999 e **não aprendeu nada**. O alvo correto é
sempre o *resultado final*, nunca o próximo ponto.

Validação honesta: treinar em 2022 e testar em 2026 (quando sair). Validar dentro
do mesmo pleito vaza informação.

## Aplicação web (`apps/`)

Angular + FastAPI sobre os mesmos dados. O ponto arquitetural: **nada é calculado
duas vezes**. O ETL roda offline e caro; a API serve o resultado e é barata.

```
CSV do TSE (3 GB)          dados/bruto/
      │  agregar_municipios.py          ETL — batch, lento, roda sob demanda
      ▼
votos_municipio.parquet    dados/processado/
      │  montar_painel.py               modelagem — pivota, deriva %, regiões
      ▼
painel.parquet (22.848 linhas, ~1 MB)
      │
      ├── repositorio.py    só esta camada sabe que é parquet
      ├── servicos.py       regras de negócio (swing, decomposição)
      ├── main.py           HTTP: query string → serviço → JSON
      ▼
   Angular (apps/web)
```

**Por que separar assim.** As três camadas do backend têm motivos distintos para
mudar: `repositorio` muda se a fonte virar Postgres; `servicos` muda se a
definição de swing mudar; `main` muda se o contrato HTTP mudar. Hoje `servicos`
não importa nada de HTTP e `main` não conhece pandas — então dá para testar a
regra de negócio sem subir servidor.

**Por que parquet e não o CSV direto.** 3 GB de CSV viram 1 MB de parquet depois
de agregado. A API carrega tudo em memória no boot e responde sem I/O. O custo é
que a agregação precisa rodar de novo quando o TSE publica dados novos — troca
consciente: leitura muito frequente, escrita rara.

### Endpoints

| rota | o que faz |
|---|---|
| `GET /api/meta` | pleitos, candidatos, UFs e regiões disponíveis |
| `GET /api/agregado?ano&turno&nivel&regiao&uf` | resultado por região/UF/município |
| `GET /api/swing?ano_de&turno_de&ano_para&turno_para&nivel` | ganho/perda entre dois pleitos |
| `GET /api/decomposicao?...` | quanto cada recorte contribuiu para a variação nacional |

`nivel` ∈ `regiao` \| `uf` \| `municipio`.

### Rodar

```bash
cd apps/api && python -m uvicorn main:app --reload --port 8000
cd apps/web && npm start
```

Abra **http://localhost:4200** — não `127.0.0.1:4200`. O dev server do Vite faz
bind só em IPv6 (`[::1]`), então o endereço IPv4 recusa conexão. O proxy
(`proxy.conf.json`) encaminha `/api` para a porta 8000, então o front não precisa
saber onde a API mora.

### Mapa interativo

Mapa coroplético com as malhas oficiais do IBGE, SVG nativo — sem biblioteca de
mapas. Passe o mouse para ver o detalhe do recorte; clique num estado para entrar
nos municípios dele; "Brasil" na trilha volta.

```
src/app/core/geo.ts        baixa a malha e projeta lon/lat -> path SVG
src/app/mapa/escala.ts     escala de cor em classes discretas
src/app/mapa/mapa.ts       componente: hover, tooltip, clique
public/geo/uf.json         245 KB, carregado no boot
public/geo/mun/<UF>.json   3,1 MB no total, uma UF por vez
```

**Projeção**: equiretangular com correção de longitude por `cos(lat média)`.
Na faixa do Brasil (5°N a 34°S) a distorção é pequena e evita trazer uma
biblioteca de projeções só para um mapa de referência.

**Carga sob demanda**: a malha municipal só desce quando você entra no estado.
MG é o maior arquivo (444 KB, 853 municípios); carregar os 3,1 MB de uma vez
atrasaria o primeiro render sem necessidade.

**Classes discretas, não gradiente**: num mapa o olho compara áreas vizinhas, e
degraus nomeáveis são lidos com mais precisão. A legenda rotula as **fronteiras**
entre degraus, não cada degrau — metade do espaço, sem colisão de números.

**Steps do tema escuro são próprios, não um flip dos claros.** Validados com
`validate_palette.js --mode dark --ordinal`: matiz único, luminosidade monotônica,
ΔL ≥ 0,06 entre vizinhos e o degrau mais fraco acima de 3:1 contra o fundo. A
primeira versão ficava em 2,2:1 e os estados perto da divisa sumiam no preto.

**Duas perguntas diferentes, dois mapas.** O seletor "Pintar o mapa por" alterna
entre:

- **Variação entre os pleitos** — para onde o eleitorado se moveu. Centro em 0.
- **Resultado (chegada / partida)** — quem está à frente. Centro em 50%.

Elas podem ter respostas opostas no mesmo estado, e isso não é contradição. No
1º→2º turno de 2026 a variação foi positiva para Lula nos **28** recortes
(+4,50 a +9,28 pp), e ainda assim Flávio venceu em **14 estados**: em SP, Lula
subiu +7,96 pp e fechou em 46,15%. Um mapa só de variação fica inteiro vermelho
e esconde exatamente isso.

**Sem degrau neutro quando o centro é uma divisa.** Na variação, "perto de zero"
é uma categoria real (não mudou), então existe um degrau cinza. No resultado, 50%
é uma divisa categórica — um degrau neutro em volta dela pintaria de cinza
justamente as disputas apertadas, que são as mais interessantes. Com a banda, 4
estados saíam cinza; sem ela, os 27 se dividem em 14 azuis e 13 vermelhos.

**A escala do mapa se adapta ao recorte.** Ao entrar no Paraná, ela é
recalculada sobre os municípios paranaenses (±10,4 pp), não sobre o Brasil
(±3,3 pp). Sem isso o estado inteiro sairia de uma cor só.

### De-para TSE ↔ IBGE

As malhas são chaveadas por código IBGE; o TSE usa código próprio. O cruzamento
(`src/crosswalk_ibge.py`) é por nome normalizado dentro da UF — 99,7% casam
direto. Dos 15 restantes, 12 saem por similaridade acima de 0,90 (CAMACÃ/Camacan,
MUNHOZ DE MELLO/Munhoz de Melo). Os 3 abaixo do limiar ficam retidos para
conferência manual e viraram correções explícitas, cada uma com a justificativa
no código.

Uma delas importa: **BOA SAÚDE (RN)**. Por similaridade o vizinho mais próximo é
"Lagoa Salgada", que é **outro município** — Boa Saúde é o nome anterior de
*Januário Cicco*. Um limiar frouxo teria pintado o mapa com o dado errado em
silêncio.

Achado relacionado: **6 municípios mudaram de grafia entre 2022 e 2026**
(CAMACÃ→CAMACAN, SANTA ISABEL→IZABEL DO PARÁ, …). Como as comparações entre anos
casam por código *e* nome, eles sumiam das comparações. O painel agora canoniza o
nome pelo pleito mais recente.

### Decisões de interface

**Cor segue o candidato, não o sinal.** Vermelho é sempre Lula e azul sempre o
adversário, em todos os gráficos e nos dois temas. Os pares foram validados com o
script da skill `dataviz` (contraste, banda de luminosidade e separação para
daltonismo) — passam todos os testes em claro e escuro.

**A escala se adapta ao dado.** Quando todos os recortes se movem para o mesmo
lado (ex.: 1º→2º turno de 2026, em que Lula sobe em todo lugar), o gráfico ancora
na borda e lê como magnitude. Quando há ganhos *e* perdas (ex.: 2022→2026), ele
vira divergente com o zero no centro. Uma escala divergente fixa deixaria metade
do gráfico vazio no primeiro caso.

**Nome de urna vem de um mapa explícito** em `montar_painel.py`. O arquivo do TSE
só traz o nome civil, e "Lula" não é derivável de "LUIZ INÁCIO LULA DA SILVA" por
regra — e os dois Bolsonaro concorreram com o número 22, então a chave é (ano, nº).

## Dados de 2026 (atualizado 26/10/2026)

O TSE **já publicou o resultado consolidado do 2º turno** no arquivo
`votacao_secao_2026_BR.csv` — 499.205 de 499.206 seções. Os quatro pleitos
batem o oficial:

| pleito | Lula | Bolsonaro |
|---|---:|---:|
| 2022 1º turno | 48,43% | 43,20% (Jair) |
| 2022 2º turno | 50,90% | 49,10% (Jair) |
| 2026 1º turno | 45,16% | **47,03%** (Flávio) |
| 2026 2º turno | **51,79%** | 48,21% (Flávio) |

Flávio liderou o 1º turno e Lula virou no 2º — swing de **+6,62 pp**, positivo em
*todas* as regiões: Sudeste +7,56, Centro-Oeste +7,37, Sul +6,15, Nordeste +5,60,
Norte +5,36. São Paulo sozinho respondeu por +1,68 pp da virada nacional.

Os **Boletins de Urna** do 2º turno de 2026 (com `DT_BU_RECEBIDO`) ainda **não**
saíram — é o que falta para projeção ao vivo e para o Exp. 2+.

## Fontes

- https://dadosabertos.tse.jus.br/dataset/resultados-2022-boletim-de-urna
- https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna
