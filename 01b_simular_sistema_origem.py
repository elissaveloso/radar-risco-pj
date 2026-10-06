# =====================================================================
# ETAPA 1B - SIMULAR O "SISTEMA DE ORIGEM" DO BANCO
# ---------------------------------------------------------------------
# No trabalho, os arquivos de contratos e de posição mensal chegam
# prontos do sistema do banco. Aqui, este script faz o papel desse
# sistema: ele cria, mês a mês, os arquivos que você vai processar
# na rotina (carga, conferência, indicadores e análise).
#
# Período das datas-base: 30/09/2024 a 30/09/2025 (13 fotografias).
# Contratos liberados desde out/2022 formam o estoque inicial da carteira.
#
# ATENÇÃO: dados 100% SIMULADOS. Nenhuma empresa ou contrato é real.
# Pré-requisito: rodar antes o 01a_gerar_empresas.py.
# =====================================================================

from pathlib import Path
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------
# 1. CONFIGURAÇÕES
# ---------------------------------------------------------------------
PASTA = Path(__file__).parent
PASTA_ENTRADA = PASTA / "dados" / "entrada"

rng = np.random.default_rng(2024)          # semente fixa: resultado reprodutível

CONTRATOS_POR_MES = 8000                   # novas liberações por mês
INICIO = pd.Period("2022-10", freq="M")    # 1º mês de liberação simulado
FIM = pd.Period("2025-09", freq="M")       # último mês simulado
JANELA_INICIO = pd.Period("2024-09", freq="M")  # 1ª data-base entregue

meses = pd.period_range(INICIO, FIM, freq="M")  # lista de todos os meses
N_MESES = len(meses)                             # 36 meses
idx_janela = meses.get_loc(JANELA_INICIO)        # posição de set/2024 na lista
idx_piora = meses.get_loc(pd.Period("2025-03", freq="M"))  # início de uma piora

# ---------------------------------------------------------------------
# 2. LER O CADASTRO DE EMPRESAS (gerado na etapa 1A)
# ---------------------------------------------------------------------
empresas = pd.read_csv(PASTA_ENTRADA / "empresas_cadastro.csv")
N_EMP = len(empresas)

# ---------------------------------------------------------------------
# 3. CRIAR TODOS OS CONTRATOS (out/2022 a set/2025)
# ---------------------------------------------------------------------
N = CONTRATOS_POR_MES * N_MESES
mes_lib = np.repeat(np.arange(N_MESES), CONTRATOS_POR_MES)   # mês de liberação (0..35)

# empresas com score melhor pegam mais crédito (o banco prefere bons clientes)
peso_emp = (empresas["score_interno"] / empresas["score_interno"].sum()).values
idx_emp = rng.choice(N_EMP, size=N, p=peso_emp)
emp = empresas.iloc[idx_emp].reset_index(drop=True)

produtos = np.array(["Capital de giro", "Antecipação de recebíveis",
                     "Conta garantida", "Cartão empresarial",
                     "Financiamento de máquinas"])
produto = rng.choice(produtos, size=N, p=[0.35, 0.25, 0.15, 0.15, 0.10])

canais = np.array(["Agência", "Digital", "Parceiro"])
canal = rng.choice(canais, size=N, p=[0.50, 0.35, 0.15])

# prazo em meses depende do produto
opcoes_prazo = {"Capital de giro": [12, 24, 36],
                "Antecipação de recebíveis": [3, 6],
                "Conta garantida": [12], "Cartão empresarial": [12],
                "Financiamento de máquinas": [36, 48, 60]}
prazo = np.zeros(N, dtype=int)
for p, opcoes in opcoes_prazo.items():
    m = produto == p
    prazo[m] = rng.choice(opcoes, size=m.sum())

# rating de A (melhor) a E (pior), a partir do score interno
rating = pd.cut(emp["score_interno"], bins=[-1, 450, 550, 650, 750, 1000],
                labels=["E", "D", "C", "B", "A"]).astype(str).values

# taxa de juros ao mês (%): pior rating = taxa maior
taxa_base = pd.Series({"A": 1.4, "B": 1.9, "C": 2.5, "D": 3.2, "E": 4.0})
taxa = (taxa_base[rating].values + rng.normal(0, 0.25, N)).clip(0.9).round(2)

# valor liberado: entre 2% e 20% do faturamento anual, mínimo R$ 5 mil
valor = np.maximum(emp["faturamento_anual"].values * rng.uniform(0.02, 0.20, N),
                   5000).round(-2)

# dia da liberação dentro do mês (1 a 28)
datas_lib = (meses[mes_lib].to_timestamp()
             + pd.to_timedelta(rng.integers(0, 28, N), unit="D"))

contratos = pd.DataFrame({
    "id_contrato": [f"CTR{i:07d}" for i in range(1, N + 1)],
    "id_empresa": emp["id_empresa"].values,
    "produto": produto,
    "canal": canal,
    "data_liberacao": datas_lib.strftime("%Y-%m-%d"),
    "prazo_meses": prazo,
    "valor_liberado": valor,
    "taxa_mensal": taxa,
    "rating": rating,
})

# ---------------------------------------------------------------------
# 4. RISCO DE CADA CONTRATO (chance de entrar em atraso a cada mês)
# ---------------------------------------------------------------------
# Regras de negócio embutidas na simulação (é o que a análise deve DESCOBRIR):
risco_setor = {"Comércio": 0.2, "Serviços": 0.1, "Indústria": -0.1,
               "Construção": 0.5, "Agronegócio": -0.4, "Transporte": 0.3,
               "Tecnologia": 0.0}
risco_produto = {"Capital de giro": 0.2, "Antecipação de recebíveis": -0.9,
                 "Conta garantida": 0.4, "Cartão empresarial": 0.6,
                 "Financiamento de máquinas": -0.2}

logit = (-4.6
         - 0.006 * (emp["score_interno"].values - 600)
         - 0.04 * np.minimum(emp["anos_atividade"].values, 15)
         + emp["setor"].map(risco_setor).values
         + pd.Series(produto).map(risco_produto).values
         + 0.5 * ((canal == "Digital") & (emp["porte"].values == "Micro")))
chance_atraso = 1 / (1 + np.exp(-logit))   # prob. mensal de sair de "em dia"

# piora a partir de mar/2025 em Construção e Cartão empresarial
segmento_piora = (emp["setor"].values == "Construção") | (produto == "Cartão empresarial")

# ---------------------------------------------------------------------
# 5. SIMULAR A VIDA DE CADA CONTRATO, MÊS A MÊS
# ---------------------------------------------------------------------
# status: 0 = ativo | 1 = liquidado (pago) | 2 = baixado a prejuízo
status = np.zeros(N, dtype=int)
dias = np.zeros(N, dtype=int)          # dias de atraso no fim do mês
saldo = valor.astype(float).copy()     # saldo devedor
pagas = np.zeros(N, dtype=int)         # parcelas pagas

chance_cura = {30: 0.45, 60: 0.30, 90: 0.18}   # chance de regularizar por faixa
fotos = []                                      # posições das datas-base

for t in range(N_MESES):
    ativo = (mes_lib < t) & (status == 0)   # contratos que já existiam

    # --- atualizar quem já estava na carteira ---
    fator = np.where((t >= idx_piora) & segmento_piora, 1.9, 1.0)
    em_dia = ativo & (dias == 0)
    atrasado = ativo & (dias > 0)

    # quem está em dia pode entrar em atraso
    entra = em_dia & (rng.random(N) < chance_atraso * fator)
    dias[entra] = rng.integers(1, 30, entra.sum())

    # quem estava em atraso: regulariza (cura) ou rola +30 dias
    p_cura = np.select([dias <= 30, dias <= 60, dias <= 90],
                       [chance_cura[30], chance_cura[60], chance_cura[90]], 0.04)
    cura = atrasado & (rng.random(N) < p_cura)
    rola = atrasado & ~cura
    dias[cura] = 0
    dias[rola] += 30

    # quem está em dia paga a parcela e reduz o saldo
    paga = ativo & (dias == 0)
    pagas[paga] += 1
    saldo[paga] = valor[paga] * np.clip(1 - pagas[paga] / prazo[paga], 0, 1)

    # liquidação: terminou de pagar ou quitou antes (1% ao mês)
    liquida = paga & ((pagas >= prazo) | (rng.random(N) < 0.01))
    status[liquida] = 1
    # baixa a prejuízo: mais de 360 dias de atraso
    status[ativo & (dias > 360)] = 2

    # --- gravar a fotografia do mês (só dentro da janela) ---
    if t >= idx_janela:
        na_foto = ((mes_lib < t) & (status == 0)) | (mes_lib == t)
        data_base = meses[t].to_timestamp(how="end").strftime("%Y-%m-%d")
        fotos.append(pd.DataFrame({
            "data_base": data_base,
            "id_contrato": contratos["id_contrato"].values[na_foto],
            "saldo_devedor": saldo[na_foto].round(2),
            "dias_atraso": dias[na_foto],
        }))

# ---------------------------------------------------------------------
# 6. GRAVAR OS ARQUIVOS MENSAIS (um lote por data-base)
# ---------------------------------------------------------------------
contratos["mes_lib"] = meses[mes_lib].strftime("%Y-%m")

for k, t in enumerate(range(idx_janela, N_MESES)):
    ref = meses[t].strftime("%Y%m")
    pasta_mes = PASTA_ENTRADA / meses[t].strftime("%Y-%m")
    pasta_mes.mkdir(exist_ok=True)
    posicao = fotos[k].copy()

    # 1º mês: carga inicial com todo o estoque; depois, só as novas liberações
    if k == 0:
        ids_foto = set(posicao["id_contrato"])
        novos = contratos[contratos["id_contrato"].isin(ids_foto)].copy()
    else:
        novos = contratos[contratos["mes_lib"] == meses[t].strftime("%Y-%m")].copy()
    novos = novos.drop(columns="mes_lib")

    # ---- PROBLEMAS DE QUALIDADE ESCONDIDOS (como na vida real) ----
    # Não leia esta parte antes de fazer a etapa de checagens! ;)
    if ref == "202412":
        novos.loc[novos.sample(37, random_state=1).index, "rating"] = np.nan
    if ref == "202502":
        posicao = pd.concat([posicao, posicao.sample(1200, random_state=2)])
    if ref == "202504":
        i = posicao.sample(15, random_state=3).index
        posicao.loc[i, "saldo_devedor"] = -posicao.loc[i, "saldo_devedor"]
    if ref == "202506":
        posicao["data_base"] = "2025-05-31"
    if ref == "202508":
        i = novos[novos["produto"] == "Capital de giro"].sample(300, random_state=4).index
        novos.loc[i, "produto"] = "Capital de Giro "
    if ref == "202509":
        orfaos = pd.DataFrame({
            "data_base": "2025-09-30",
            "id_contrato": [f"CTR9{i:06d}" for i in range(50)],
            "saldo_devedor": rng.uniform(5000, 90000, 50).round(2),
            "dias_atraso": 0,
        })
        posicao = pd.concat([posicao, orfaos])

    novos.to_csv(pasta_mes / f"contratos_{ref}.csv", index=False, encoding="utf-8-sig")
    posicao.to_csv(pasta_mes / f"posicao_{ref}.csv", index=False, encoding="utf-8-sig")
    print(f"{ref}: {len(novos):>7,} contratos | {len(posicao):>7,} linhas de posição")

print("Arquivos gerados em:", PASTA_ENTRADA)
