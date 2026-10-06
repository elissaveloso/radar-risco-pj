# Criando bases - Objetivo estudo risco de credito PJ
# ETAPA 1A - GERAR O CADASTRO DE EMPRESAS (CLIENTES PJ)
from pathlib import Path    # monstar caminhos de pastas e arquivos
import numpy as np          # gerar numeros aleatorios
import pandas as pd         # monstar e salvar tabelas

# 1. configurações
PASTA = Path (__file__).parent                   # pasta do projeto (Projeto_1)
PASTA_ENTRADA = PASTA / "dados" / "entrada"      # onde os arquivos chegam
PASTA_ENTRADA.mkdir(parents=True, exist_ok=True) # cria as pastas que faltarem

rng = np.random.default_rng(42) # sorteador com semente 42 # os dados iguais em todas as execuções

N_EMPRESAS = 30000  # quantidade de empresas que vou simular

# 2. Tabela de empresas (clientes)
setores = ["Comércio", "Serviços", "Indústria", "Construção", "Agronegócio", "Transporte", "Tecnologia"]
peso_setores = [0.30, 0.25, 0.15, 0.10, 0.08, 0.07,0.05] # soma = 1

ufs = ["SP", "MG", "RJ", "PR", "RS", "SC", "BA", "PE", "GO", "CE"]
peso_ufs = [0.32, 0.12, 0.10, 0.09, 0.08, 0.07, 0.07, 0.06, 0.05, 0.04]

empresas = pd.DataFrame ({
    #ID SEQUENCIAL: EMP00001, EMP00002, ...
    "id_empresa": [f"EMP{i:05d}" for i in range (1, N_EMPRESAS + 1)],
    "setor":rng.choice(setores, size=N_EMPRESAS, p=peso_setores),
    "uf": rng.choice(ufs, size=N_EMPRESAS, p=peso_ufs),
    # anos de atividades: muitos cliente novos e poucos antigos (carteira PJ)
    "anos_atividade": np.clip(rng.exponential(8,N_EMPRESAS), 0.5, 40).round(1),
    # faturamento anual em R$ (distribuição assimetrica, como na realidade)
    "faturamento_anual": np.round(rng.lognormal(14.2, 1.3, N_EMPRESAS), -3),
})

# porte da empresa pelo faturamento (classificação simplificada para estudo) 
empresas ["porte"] = pd.cut(
    empresas["faturamento_anual"],
    bins=[0, 360_000, 4_800_000,50_000_000, np.inf],
    labels=["Micro", "Pequena", "Média", "Grande"],
).astype(str)

# score interno de 0 a 1000: maior = melhor pagador
# empresas mais antigas e maiores tendem a ter score maior

base_score = (
    510
    + 8 * np.minimum(empresas["anos_atividade"], 25)
    + 25 * (np.log10(empresas["faturamento_anual"]) -5)
    + rng.normal (0, 110, N_EMPRESAS)
)
empresas["score_interno"] = np.clip(base_score, 0, 1000).round(0).astype(int)

# 3. Salvar Cadastro
arquivo = PASTA_ENTRADA / "empresas_cadastro.csv"
empresas.to_csv(arquivo, index=False, encoding="utf-8-sig")

print(empresas.head(3))
print(empresas["porte"].value_counts())
print("cadastro salvo em:", arquivo)