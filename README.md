# Radar de Risco PJ

Projeto de estudo que reproduz a rotina mensal de uma área de risco de crédito PJ: receber as bases do mês, conferir a qualidade dos dados, calcular os indicadores de inadimplência e apontar riscos, pontos de atenção e oportunidades em um painel.

> **Os dados são 100% simulados.** Nenhuma empresa, contrato ou valor é real. Os números servem para praticar o método, não para tirar conclusões sobre o mercado.

## O problema

Todo mês chegam arquivos novos de contratos e de posição da carteira. Antes de qualquer análise, é preciso responder a quatro perguntas:

1. Os arquivos chegaram completos e estão confiáveis?
2. Como está a inadimplência da carteira e para onde ela caminha?
3. Onde estão os riscos e os pontos de atenção?
4. Onde há espaço para crescer com risco baixo?

## Como o projeto está organizado

| Arquivo | O que faz |
|---|---|
| `01_base_empresas.py` | Gera o cadastro simulado de 30.000 empresas |
| `01b_simular_sistema_origem.py` | Faz o papel do sistema do banco: gera os arquivos mensais de contratos e de posição |
| `02_carga_mensal.py` | Carrega os arquivos no banco (camada bruta) e registra cada carga |
| `03_tratamento.py` | Limpa os dados, marca os problemas e registra as ocorrências (camada tratada) |
| `04_alertas.py` | Calcula os indicadores, os alertas e o roll rate (camada resumo) |
| `05_rotina_mensal.py` | Roda os scripts 02, 03 e 04 em sequência, com um comando só |
| `app/painel.py` | Painel em Streamlit que lê as tabelas-resumo |
| `.streamlit/config.toml` | Tema (cores) do painel |

Os dados passam por três camadas:

- **Bruta**: os arquivos como chegaram, sem alteração.
- **Tratada**: os mesmos dados, limpos e com marcações (flags) nos registros problemáticos. Nada é apagado.
- **Resumo**: tabelas pequenas, prontas para o painel.

## Como rodar

Pré-requisitos: Python com as bibliotecas `pandas`, `numpy`, `streamlit` e `plotly`.

Primeira vez (gera os dados simulados):

```
python 01_base_empresas.py
python 01b_simular_sistema_origem.py
```

Rotina do mês (carga, tratamento e alertas):

```
python 05_rotina_mensal.py
```

Painel:

```
streamlit run app/painel.py
```

Todos os comandos são executados de dentro da pasta do projeto.

## A base

| Item | Volume |
|---|---|
| Empresas | 30.000 |
| Contratos | 201.161 |
| Datas-base | 13 (de 30/09/2024 a 30/09/2025) |
| Linhas de posição (bruta) | 1.473.612 |
| Linhas de posição (tratada) | 1.472.412 |

## Qualidade dos dados

Seis problemas foram encontrados nas cargas. Cada um foi registrado na tabela `qualidade_ocorrencias` com o tratamento aplicado.

| Problema | Mês | Linhas | Tratamento |
|---|---|---|---|
| Contrato sem rating | 12/2024 | 37 | Marcado com flag |
| Posições duplicadas | 02/2025 | 1.200 | Mantida uma linha por contrato e mês |
| Saldo devedor negativo | 04/2025 | 15 | Marcado com flag e fora dos indicadores |
| Data-base diferente do mês do arquivo | 06/2025 | 117.238 | Data recalculada pelo mês do arquivo |
| Produto fora do padrão | 08/2025 | 300 | Nome padronizado |
| Posição sem contrato (órfã) | 09/2025 | 50 | Marcada com flag e fora dos indicadores |

## Indicadores

| Indicador | Regra usada neste projeto |
|---|---|
| Over 30 | Saldo dos contratos com mais de 30 dias de atraso, dividido pelo saldo total |
| Over 90 | Saldo dos contratos com mais de 90 dias de atraso, dividido pelo saldo total |
| Participação | Saldo do segmento dividido pelo saldo da carteira no mês |
| Roll rate | De cada faixa de atraso no mês anterior, percentual de contratos que piorou e que regularizou no mês atual |

Over 30 e Over 90 são calculados por **saldo**. O roll rate é calculado por **quantidade de contratos**.

## Política de alertas

Os limites ficam em um único lugar, no início da Parte B do `04_alertas.py`.

| Tipo | Regra | Limite |
|---|---|---|
| RISCO | Over 30 do segmento subiu em 3 meses | 1,0 ponto percentual ou mais |
| ATENÇÃO | Over 90 do segmento em nível alto, sem alerta de risco | 3,0% ou mais |
| OPORTUNIDADE | Over 90 baixo e participação pequena na carteira | Over 90 até 1,8% e participação até 10% |

Os limites foram escolhidos para o estudo. Em uma carteira real, eles viriam da política de crédito e do apetite de risco da instituição.

## Achados (data-base 30/09/2025)

**Carteira**

| Indicador | 30/09/2024 | 30/09/2025 |
|---|---|---|
| Saldo | R$ 25,54 bi | R$ 27,36 bi |
| Contratos ativos | 105.161 | 120.940 |
| Over 30 | 3,33% | 3,94% |
| Over 90 | 2,30% | 2,73% |

**Alertas do mês**

| Tipo | Segmento | Situação |
|---|---|---|
| RISCO | Cartão empresarial (produto) | Over 30 subiu de 6,74% para 8,75% em 3 meses |
| RISCO | Construção (setor) | Over 30 subiu de 5,84% para 7,89% em 3 meses |
| ATENÇÃO | Transporte (setor) | Over 90 em 3,52% |
| OPORTUNIDADE | Antecipação de recebíveis (produto) | Over 90 de 1,42% com 7,7% da carteira |
| OPORTUNIDADE | Agronegócio (setor) | Over 90 de 1,74% com 8,3% da carteira |
| OPORTUNIDADE | Tecnologia (setor) | Over 90 de 1,64% com 4,8% da carteira |

**Roll rate (08/2025 para 09/2025)**

| Faixa de atraso em 08/2025 | Contratos | Saldo (R$ mi) | Piorou | Regularizou |
|---|---|---|---|---|
| Em dia | 106.649 | 25.350,2 | 1,6% | - |
| 1 a 30 dias | 1.569 | 331,5 | 56,7% | 43,3% |
| 31 a 60 dias | 906 | 191,2 | 71,0% | 29,0% |
| 61 a 90 dias | 634 | 150,3 | 81,4% | 18,6% |
| Mais de 90 dias | 3.182 | 661,9 | 95,9% | 4,1% |

Quanto mais tempo de atraso, menor a chance de regularização. O saldo em atenção (1 a 90 dias de atraso) soma R$ 673 milhões.

## Minhas Leituras e Comentários

Apesar do crescimento da carteira de R$ 25,54 bi para R$ 27,36 bi em 12 meses, e o Over 30 subiu de 3,33% para 3,94%. A alta não foi gradual: até 03/2025 o Over 30 ficou perto de 3,2%, e a partir de 04/2025 subiu todos os meses.
A piora da inadimplencia que representa pouco mais de 10% do saldo entre fev/2025 a set/2025 foi por conta do Cartão empresarial que passou de 5,20% para 8,75% de Over 30, e Construção de 3,78% para 7,89% no mesmo período.
O que eu faria: revisar as concessões recentes nesses dois segmentos antes de qualquer ajuste geral de política. A base mostra onde piorou, mas não mostra a causa.

**Oportunidade: risco baixo, mas com ressalvas**

Três segmentos combinam Over 90 baixo e participação pequena: Antecipação de recebíveis (1,42% de Over 90, 7,7% da carteira), Agronegócio (1,74% e 8,3%) e Tecnologia (1,64% e 4,8%).

Nenhum dos três é uma indicação automática de crescimento. Em Antecipação de recebíveis, o Over 90 ainda é o menor da carteira, mas subiu de 0,84% para 1,42% em 12 meses, enquanto a participação caiu de 8,5% para 7,7%. Em Tecnologia, o Over 90 oscila bastante: estava em 2,12% em 06/2025, acima do limite de oportunidade.

O que eu faria: tratar Agronegócio como o candidato mais estável, e pedir dados de rentabilidade e de demanda antes de propor crescimento em qualquer um deles. Risco baixo sozinho não justifica aumentar a exposição.

## Limitações

- Os dados são simulados: os padrões encontrados foram embutidos pelo gerador e não representam o mercado.
- A base não tem recuperação nem perda efetiva, então não é possível calcular perda esperada.
- A base mostra **onde** a inadimplência piorou, mas não **por quê**. A causa precisaria de outras informações (mudança de política, cenário do setor, perfil das novas concessões).
- "Oportunidade" aqui significa risco baixo e participação pequena. A decisão de crescer dependeria também de rentabilidade, demanda e capacidade operacional, que não estão na base.
- O teste da rotina mensal foi feito sem um mês novo de verdade, porque a base termina em 09/2025.

## Dicionário de dados

**bruta_empresas** (cadastro)

| Coluna | Significado |
|---|---|
| id_empresa | Identificador da empresa |
| setor | Setor de atividade |
| uf | Estado |
| anos_atividade | Tempo de atividade, em anos |
| faturamento_anual | Faturamento anual, em R$ |
| porte | Micro, Pequena, Média ou Grande |
| score_interno | Score de 0 a 1000; quanto maior, melhor |

**tratada_contratos**

| Coluna | Significado |
|---|---|
| id_contrato | Identificador do contrato |
| id_empresa | Empresa que tomou o crédito |
| produto_original | Nome do produto como veio no arquivo |
| produto | Nome do produto padronizado |
| canal | Canal de contratação |
| data_liberacao | Data em que o crédito foi liberado |
| prazo_meses | Prazo do contrato, em meses |
| valor_liberado | Valor liberado, em R$ |
| taxa_mensal | Taxa de juros ao mês, em % |
| rating | Classificação de risco, de A (melhor) a E (pior) |
| flag_rating_nulo | 1 se o contrato veio sem rating |
| flag_produto_corrigido | 1 se o nome do produto foi padronizado |

**tratada_posicao** (fotografia mensal da carteira)

| Coluna | Significado |
|---|---|
| ref_carga | Mês do arquivo de origem (AAAAMM) |
| data_base_original | Data-base como veio no arquivo |
| data_base | Data-base corrigida pelo mês do arquivo |
| id_contrato | Identificador do contrato |
| saldo_devedor | Saldo devedor na data-base, em R$ |
| dias_atraso | Dias de atraso na data-base |
| flag_saldo_negativo | 1 se o saldo veio negativo |
| flag_orfa | 1 se a posição não tem contrato correspondente |

**Tabelas-resumo**

| Tabela | Conteúdo |
|---|---|
| indicadores_mensais | Contratos, saldo, Over 30, Over 90 e participação por mês e por segmento |
| alertas | Alertas do último mês |
| roll_rate | Movimento entre faixas de atraso do penúltimo para o último mês |
| qualidade_ocorrencias | Problemas de qualidade encontrados e o tratamento aplicado |
| controle_cargas | Registro de cada arquivo carregado |


