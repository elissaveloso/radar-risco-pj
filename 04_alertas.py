# INDICADORES RESUMIDOS E ALERTAS AUTOMÁTICOS
    # Rotina: depois da carga (02) e do tratamento (03), este script:
    #   A. calcula os indicadores de cada mês e grava numa tabela-resumo;
    #   B. compara os indicadores com limites e grava os alertas.
    # O painel (etapa 6) vai ler estas duas tabelas, que são pequenas e rápidas.

from pathlib import Path
import sqlite3
import pandas as pd

BANCO = Path(__file__).parent / "dados" / "radar_pj.db"
conn = sqlite3.connect(BANCO)

# PARTE A - TABELA-RESUMO: indicadores_mensais
# Cada item: (nome da visão, coluna usada para agrupar)
visoes = [
    ("carteira", "'Total'"),      # a carteira inteira, sem abrir
    ("produto",  "c.produto"),
    ("setor",    "e.setor"),
]

partes = []                       # aqui vou juntar o resultado de cada visão
for dimensao, coluna in visoes:
    consulta = f"""
        SELECT
            p.data_base,
            '{dimensao}'                                         AS dimensao,
            {coluna}                                             AS segmento,
            COUNT(*)                                             AS contratos,
            ROUND(SUM(p.saldo_devedor) / 1e6, 1)                 AS saldo_mi,
            ROUND(100.0 * SUM(CASE WHEN p.dias_atraso > 30 THEN p.saldo_devedor ELSE 0 END)
                        / SUM(p.saldo_devedor), 2)               AS over30_pct,
            ROUND(100.0 * SUM(CASE WHEN p.dias_atraso > 90 THEN p.saldo_devedor ELSE 0 END)
                        / SUM(p.saldo_devedor), 2)               AS over90_pct
        FROM tratada_posicao p
        JOIN tratada_contratos c ON c.id_contrato = p.id_contrato
        JOIN bruta_empresas   e ON e.id_empresa  = c.id_empresa
        WHERE p.flag_saldo_negativo = 0
          AND p.flag_orfa = 0
        GROUP BY p.data_base, {coluna}
    """
    partes.append(pd.read_sql(consulta, conn))
    print(f"visão calculada: {dimensao}")

indicadores = pd.concat(partes)   # empilha as três visões numa tabela só

# participação de cada segmento no saldo do mês, dentro da minha visão
total_mes = indicadores.groupby(["data_base", "dimensao"])["saldo_mi"].transform("sum")
indicadores["part_pct"] = (100 * indicadores["saldo_mi"] / total_mes).round(1)

indicadores.to_sql("indicadores_mensais", conn, if_exists="replace", index=False)
print("linhas em indicadores_mensais:", len(indicadores))

# PARTE B - ALERTAS
# ---- LIMITES (a política de alerta: mude aqui, e só aqui) ----
LIMITE_PIORA_OVER30 = 1.0    # pontos de aumento do Over 30 em 3 meses - RISCO
LIMITE_NIVEL_OVER90 = 3.0    # Over 90 igual ou acima disso            - ATENÇÃO
LIMITE_BOM_OVER90   = 1.8    # Over 90 igual ou abaixo disso ...
LIMITE_PART_PEQUENA = 10.0   # ... e participação até isso             - OPORTUNIDADE

# mês atual e o mês de 3 meses atrás
datas = sorted(indicadores["data_base"].unique())
mes_atual, mes_anterior = datas[-1], datas[-4]
print(f"\ncomparando {mes_anterior} com {mes_atual}")

conn.execute("DROP TABLE IF EXISTS alertas")
conn.execute("""CREATE TABLE alertas (
                    data_base TEXT, tipo TEXT, dimensao TEXT,
                    segmento TEXT, mensagem TEXT)""")

# ---- RISCO: o Over 30 piorou muito em 3 meses ----
conn.execute("""
    INSERT INTO alertas
    SELECT a.data_base, 'RISCO', a.dimensao, a.segmento,
           'Over 30 subiu de ' || b.over30_pct || '% para ' || a.over30_pct || '% em 3 meses'
    FROM indicadores_mensais a
    JOIN indicadores_mensais b
      ON b.dimensao = a.dimensao AND b.segmento = a.segmento
    WHERE a.data_base = ? AND b.data_base = ?
      AND a.over30_pct - b.over30_pct >= ?
""", (mes_atual, mes_anterior, LIMITE_PIORA_OVER30))

# ---- ATENÇÃO: nível alto de Over 90, mesmo sem piora recente ----
conn.execute("""
    INSERT INTO alertas
    SELECT a.data_base, 'ATENÇÃO', a.dimensao, a.segmento,
           'Over 90 em ' || a.over90_pct || '%, acima do limite'
    FROM indicadores_mensais a
    WHERE a.data_base = ?
      AND a.over90_pct >= ?
      AND a.segmento NOT IN (SELECT segmento FROM alertas WHERE tipo = 'RISCO')
""", (mes_atual, LIMITE_NIVEL_OVER90))

# ---- OPORTUNIDADE: risco baixo e fatia pequena da carteira ----
conn.execute("""
    INSERT INTO alertas
    SELECT a.data_base, 'OPORTUNIDADE', a.dimensao, a.segmento,
           'Over 90 de ' || a.over90_pct || '% com ' || a.part_pct || '% da carteira'
    FROM indicadores_mensais a
    WHERE a.data_base = ?
      AND a.dimensao <> 'carteira'
      AND a.over90_pct <= ?
      AND a.part_pct  <= ?
""", (mes_atual, LIMITE_BOM_OVER90, LIMITE_PART_PEQUENA))
conn.commit()

print("\n--- alertas do mês ---")
for tipo, dimensao, segmento, mensagem in conn.execute(
        "SELECT tipo, dimensao, segmento, mensagem FROM alertas ORDER BY tipo DESC"):
    print(f"[{tipo}] {dimensao} / {segmento}: {mensagem}")

# PARTE C - ROLL RATE: do penúltimo para o último mês
    # dos contratos de cada faixa de atraso no mês anterior,
    # quantos pioraram e quantos regularizaram no mês atual?
refs = [linha[0] for linha in conn.execute(
    "SELECT DISTINCT ref_carga FROM tratada_posicao ORDER BY ref_carga")]
ref_atual, ref_anterior = refs[-1], refs[-2]

roll_rate = pd.read_sql("""
    WITH anterior AS (
        SELECT id_contrato, saldo_devedor, dias_atraso
        FROM tratada_posicao
        WHERE ref_carga = ? AND flag_saldo_negativo = 0 AND flag_orfa = 0
    ),
    atual AS (
        SELECT id_contrato, dias_atraso
        FROM tratada_posicao
        WHERE ref_carga = ? AND flag_saldo_negativo = 0 AND flag_orfa = 0
    )
    SELECT
        CASE
            WHEN a.dias_atraso = 0   THEN '0) em dia'
            WHEN a.dias_atraso <= 30 THEN '1) 1 a 30 dias'
            WHEN a.dias_atraso <= 60 THEN '2) 31 a 60 dias'
            WHEN a.dias_atraso <= 90 THEN '3) 61 a 90 dias'
            ELSE                          '4) mais de 90 dias'
        END                                                  AS faixa_anterior,
        COUNT(*)                                             AS contratos,
        ROUND(SUM(a.saldo_devedor) / 1e6, 1)                 AS saldo_mi,
        ROUND(100.0 * SUM(CASE WHEN s.dias_atraso > a.dias_atraso THEN 1 ELSE 0 END)
                    / COUNT(*), 1)                           AS piorou_pct,
        ROUND(100.0 * SUM(CASE WHEN s.dias_atraso = 0 AND a.dias_atraso > 0 THEN 1 ELSE 0 END)
                    / COUNT(*), 1)                           AS regularizou_pct
    FROM anterior a
    JOIN atual s ON s.id_contrato = a.id_contrato
    GROUP BY faixa_anterior
    ORDER BY faixa_anterior
""", conn, params=(ref_anterior, ref_atual))

roll_rate["ref_anterior"] = ref_anterior      # guarda quais meses foram comparados
roll_rate["ref_atual"] = ref_atual
roll_rate.to_sql("roll_rate", conn, if_exists="replace", index=False)

print(f"\n--- roll rate de {ref_anterior} para {ref_atual} ---")
print(roll_rate[["faixa_anterior", "contratos", "saldo_mi",
                 "piorou_pct", "regularizou_pct"]].to_string(index=False))

conn.close()
