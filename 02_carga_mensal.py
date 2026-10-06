# BASE BRUTA
# Rotina: todo mes chegam arquivos novos em dados/entrada/aaaa-mm.
# etapas: 
    # 1. criar banco radar_pj.db
    # 2. carregar o cadastro da empresa
    # 3. carregar cada mes  que ainda não foi rodado
    # 4. registro tudo na tabela de controle 
# camada bruta 

from pathlib import Path
from datetime import datetime
import sqlite3
import pandas as pd

# configuração

PASTA = Path(__file__).parent
PASTA_ENTRADA = PASTA / "dados" / "entrada"
BANCO = PASTA / "dados" / "radar_pj.db"

conn = sqlite3.connect(BANCO)          # conecta (cria o arquivo se não existir)

# Tabela de conferecia / controle
# Cada linha registra: qual mês, qual arquivo, em qual tabela entrou,
# quantas linhas e quando a carga foi feita.

conn.execute("""
    CREATE TABLE IF NOT EXISTS controle_cargas (
        referencia  TEXT,
        arquivo     TEXT,
        tabela      TEXT,
        linhas      INTEGER,
        data_carga  TEXT
    )
""")


def registrar(referencia, arquivo, tabela, linhas):
    """Grava uma linha no log de cargas."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO controle_cargas VALUES (?, ?, ?, ?, ?)",
                 (referencia, arquivo, tabela, linhas, agora))


def ja_carregado(referencia):
    """Responde True se aquele mês já está no log."""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM controle_cargas WHERE referencia = ?", (referencia,))
    return cursor.fetchone()[0] > 0

# Cadastro de empresas 
if not ja_carregado("cadastro"):
    empresas = pd.read_csv(PASTA_ENTRADA / "empresas_cadastro.csv")
    empresas.to_sql("bruta_empresas", conn, if_exists="replace", index=False)
    registrar("cadastro", "empresas_cadastro.csv", "bruta_empresas", len(empresas))
    conn.commit()
    print(f"Cadastro carregado: {len(empresas):,} empresas")
else:
    print("Cadastro: já carregado antes, pulando.")

# carga de cada mes
# lista as pastas de mês (2024-09, 2024-10, ...) em ordem

pastas_mes = sorted(p for p in PASTA_ENTRADA.iterdir() if p.is_dir())

for pasta in pastas_mes:
    ref = pasta.name.replace("-", "")                 # "2024-10" -> "202410"
    arq_contratos = pasta / f"contratos_{ref}.csv"
    arq_posicao = pasta / f"posicao_{ref}.csv"

    # 4.1 mês já carregado? pula (evita duplicar os dados)
    if ja_carregado(ref):
        print(f"{ref}: já carregado antes, pulando.")
        continue

    # 4.2 algum arquivo faltando? avisa e NÃO carrega o mês pela metade
    faltando = [a.name for a in (arq_contratos, arq_posicao) if not a.exists()]
    if faltando:
        print(f"{ref}: ATENÇÃO! Arquivo(s) faltando: {faltando}. Mês não carregado.")
        continue

    # 4.3 ler os arquivos e marcar de qual mês vieram
    contratos = pd.read_csv(arq_contratos)
    posicao = pd.read_csv(arq_posicao)
    contratos["ref_carga"] = ref
    posicao["ref_carga"] = ref

    # 4.4 gravar no banco (append = acrescentar ao que já existe)
    contratos.to_sql("bruta_contratos", conn, if_exists="append", index=False)
    posicao.to_sql("bruta_posicao", conn, if_exists="append", index=False)

    # 4.5 registrar no log e confirmar a gravação
    registrar(ref, arq_contratos.name, "bruta_contratos", len(contratos))
    registrar(ref, arq_posicao.name, "bruta_posicao", len(posicao))
    conn.commit()
    print(f"{ref}: carregado ({len(contratos):,} contratos | {len(posicao):,} posições)")

# resumo final
resumo = pd.read_sql("""
    SELECT tabela, COUNT(DISTINCT referencia) AS meses, SUM(linhas) AS linhas
    FROM controle_cargas
    GROUP BY tabela
""", conn)
print("\nResumo do banco:")
print(resumo.to_string(index=False))

conn.close()

