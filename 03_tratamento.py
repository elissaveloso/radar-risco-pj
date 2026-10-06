from pathlib import Path
import sqlite3

BANCO = Path(__file__).parent / "dados" / "radar_pj.db"
conn = sqlite3.connect(BANCO)          # conecta (cria o arquivo se não existir)

consulta = """
SELECT produto, LENGTH(produto) AS tamanho, COUNT(*) AS qtd
FROM bruta_contratos
GROUP BY produto
"""
for linha in conn.execute(consulta):
    print(linha)

# apaga a tratada antiga (se existir) para o script poder rodar várias vezes
conn.execute("DROP TABLE IF EXISTS tratada_contratos")

# cria a tratada a partir da bruta
conn.execute("""
CREATE TABLE tratada_contratos AS
SELECT
    id_contrato,
    id_empresa,
    produto                          AS produto_original,   -- guarda como veio
    CASE
        WHEN TRIM(produto) = 'Capital de Giro' THEN 'Capital de giro'               -- padroniza o Giro
        ELSE TRIM(produto)
    END                              AS produto,
    canal,
    data_liberacao,
    prazo_meses,
    valor_liberado,
    taxa_mensal,
    rating,
    CASE WHEN rating IS NULL THEN 1 ELSE 0 END AS flag_rating_nulo,
    CASE WHEN produto <> TRIM(produto) OR produto = '___' THEN 1 ELSE 0 END AS flag_produto_corrigido
FROM bruta_contratos
""")
conn.commit()      # confirma a gravação no arquivo do banco

print(conn.execute("SELECT COUNT(*) FROM bruta_contratos").fetchone())
print(conn.execute("SELECT COUNT(*) FROM tratada_contratos").fetchone())
for l in conn.execute("""SELECT produto, LENGTH(produto), COUNT(*)
                         FROM tratada_contratos GROUP BY produto"""):
    print(l)
print(conn.execute("""SELECT SUM(flag_produto_corrigido), SUM(flag_rating_nulo)
                      FROM tratada_contratos""").fetchone())

# corrigir o caminho da pasta
BANCO = Path(__file__).parent / "dados" / "radar_pj.db"

# TRATADA_POSICAO - a posição mensal limpa
# Regras de tratamento (sem mexer na base bruta)
#   1. duplicadas  -> fica uma linha por contrato em cada mês
#   2. data errada -> data_base passa a ser o último dia do mês do arquivo
#   3. saldo negativo       -> marcado com flag_saldo_negativo
#   4. posição sem contrato -> marcada com flag_orfa
conn.execute("DROP TABLE IF EXISTS tratada_posicao")

conn.execute("""
CREATE TABLE tratada_posicao AS
WITH sem_duplicadas AS (
    -- DISTINCT elimina as linhas repetidas idênticas
    SELECT DISTINCT ref_carga, id_contrato, saldo_devedor, dias_atraso, data_base
    FROM bruta_posicao
)
SELECT
    p.ref_carga,
    p.data_base                                   AS data_base_original,  -- guarda como veio
    -- último dia do mês do arquivo: 202506 -> 2025-06-01 -> +1 mês -> -1 dia
    DATE(SUBSTR(p.ref_carga, 1, 4) || '-' || SUBSTR(p.ref_carga, 5, 2) || '-01',
         '+1 month', '-1 day')                    AS data_base,
    p.id_contrato,
    p.saldo_devedor,
    p.dias_atraso,
    CASE WHEN p.saldo_devedor < 0   THEN 1 ELSE 0 END AS flag_saldo_negativo,
    CASE WHEN c.id_contrato IS NULL THEN 1 ELSE 0 END AS flag_orfa
FROM sem_duplicadas p
LEFT JOIN tratada_contratos c ON c.id_contrato = p.id_contrato
""")

# converter para índices: deixar as consultas das próximas etapas mais rápidas
conn.execute("CREATE INDEX IF NOT EXISTS ix_pos_contrato ON tratada_posicao (id_contrato)")
conn.execute("CREATE INDEX IF NOT EXISTS ix_pos_ref ON tratada_posicao (ref_carga)")
conn.commit()

# conferência da tratada_posicao
print("\n--- tratada_posicao ---")
print("linhas na bruta:  ", conn.execute("SELECT COUNT(*) FROM bruta_posicao").fetchone()[0])
print("linhas na tratada:", conn.execute("SELECT COUNT(*) FROM tratada_posicao").fetchone()[0])
print("ainda duplicadas: ", conn.execute("""
    SELECT COUNT(*) FROM (SELECT 1 FROM tratada_posicao
                          GROUP BY ref_carga, id_contrato HAVING COUNT(*) > 1)""").fetchone()[0])
print("flags (negativo, órfã):", conn.execute(
    "SELECT SUM(flag_saldo_negativo), SUM(flag_orfa) FROM tratada_posicao").fetchone())
print("datas de junho:", conn.execute(
    "SELECT DISTINCT data_base_original, data_base FROM tratada_posicao WHERE ref_carga = '202506'").fetchone())

# QUALIDADE_OCORRENCIAS - o registro do que foi encontrado e tratado
# Cada item: (problema, tratamento, consulta que devolve mês e nº de linhas)
checagens = [
    ("Posições duplicadas", "Mantida uma linha por contrato e mês",
     """SELECT ref_carga, COUNT(*) - COUNT(DISTINCT id_contrato)
        FROM bruta_posicao GROUP BY ref_carga
        HAVING COUNT(*) > COUNT(DISTINCT id_contrato)"""),
    ("Data-base diferente do mês do arquivo", "Data recalculada pelo mês do arquivo",
     """SELECT ref_carga, COUNT(*) FROM tratada_posicao
        WHERE data_base <> data_base_original GROUP BY ref_carga"""),
    ("Saldo devedor negativo", "Marcado com flag e fora dos indicadores",
     """SELECT ref_carga, COUNT(*) FROM tratada_posicao
        WHERE flag_saldo_negativo = 1 GROUP BY ref_carga"""),
    ("Posição sem contrato (órfã)", "Marcada com flag e fora dos indicadores",
     """SELECT ref_carga, COUNT(*) FROM tratada_posicao
        WHERE flag_orfa = 1 GROUP BY ref_carga"""),
    ("Contrato sem rating", "Marcado com flag",
     """SELECT ref_carga, COUNT(*) FROM bruta_contratos
        WHERE rating IS NULL GROUP BY ref_carga"""),
    ("Produto fora do padrão", "Nome padronizado",
     """SELECT ref_carga, COUNT(*) FROM bruta_contratos
        WHERE produto <> TRIM(produto) GROUP BY ref_carga"""),
]

conn.execute("DROP TABLE IF EXISTS qualidade_ocorrencias")
conn.execute("""CREATE TABLE qualidade_ocorrencias (
                    problema TEXT, ref_carga TEXT, linhas INTEGER, tratamento TEXT)""")

for problema, tratamento, consulta in checagens:
    for ref_carga, linhas in conn.execute(consulta).fetchall():
        conn.execute("INSERT INTO qualidade_ocorrencias VALUES (?, ?, ?, ?)",
                     (problema, ref_carga, linhas, tratamento))
conn.commit()

print("\n--- qualidade_ocorrencias ---")
for linha in conn.execute("SELECT problema, ref_carga, linhas FROM qualidade_ocorrencias"):
    print(linha)

conn.close()



