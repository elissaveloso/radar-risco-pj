
# ETAPA 6 -  FRONTEND - RADAR DE RISCO PJ
# Para abrir o painel, rode no terminal (dentro da pasta Projeto_1):
     # streamlit run app/painel.py
# O painel só LÊ as tabelas-resumo geradas pelos scripts anteriores.

from pathlib import Path
import sqlite3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# o banco fica uma pasta acima de "app", dentro de "dados"
BANCO = Path(__file__).parent.parent / "dados" / "radar_pj.db"

# configuração da página: título da aba do navegador e largura total
st.set_page_config(page_title="Radar de Risco PJ", layout="wide")

# ---------------------------------------------------------------------
# VISUAL DO PAINEL (cores e formato dos cartões e dos painéis)
# ---------------------------------------------------------------------
# CSS é a linguagem que define a aparência de uma página da web.
# Aqui ele cria o "cartão com degradê" e a moldura dos gráficos.
st.markdown("""
<style>
.cartao {
    border-radius: 6px;                 /* cantos arredondados */
    padding: 18px 20px;                 /* espaço interno */
    color: white;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);   /* sombra suave */
    margin-bottom: 18px;
}
.cartao .valor  { font-size: 1.9rem; font-weight: 700; line-height: 1.2; }
.cartao .rotulo { font-size: 0.8rem; letter-spacing: 0.08em;
                  text-transform: uppercase; opacity: 0.9; }
.cartao .extra  { font-size: 0.85rem; margin-top: 10px; opacity: 0.95; }

/* painel em volta de cada gráfico */
[data-testid="stPlotlyChart"] {
    border-radius: 6px;
    overflow: hidden;                   /* corta o gráfico nos cantos arredondados */
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}
</style>
""", unsafe_allow_html=True)


def cartao(rotulo, valor, extra, cor):
    """Desenha um cartão colorido: a cor começa forte e escurece para a direita."""
    st.markdown(f"""
    <div class="cartao" style="background: linear-gradient(90deg, {cor} 0%, #16181f 100%);">
        <div class="valor">{valor}</div>
        <div class="rotulo">{rotulo}</div>
        <div class="extra">{extra}</div>
    </div>
    """, unsafe_allow_html=True)


@st.cache_data                      # guarda o resultado para não reler o banco a cada clique
def ler_tabela(consulta):
    """Roda uma consulta no banco e devolve uma tabela (DataFrame)."""
    conn = sqlite3.connect(BANCO)
    tabela = pd.read_sql(consulta, conn)
    conn.close()
    return tabela


# PARTE DOS DADOS
carteira = ler_tabela("""
    SELECT * FROM indicadores_mensais
    WHERE dimensao = 'carteira'
    ORDER BY data_base
""")
atual = carteira.iloc[-1]           # último mês
anterior = carteira.iloc[-2]        # mês anterior, para mostrar a variação

# CABEÇALHO
st.title("Radar de Risco PJ")
st.caption(f"Data-base: {atual['data_base']}  |  Dados simulados para estudo")

# INDICADORES PRINCIPAIS (os "cartões" do topo)
col1, col2, col3, col4 = st.columns(4)

# seta para cima ou para baixo, conforme a variação no mês
def seta(variacao):
    return "▲" if variacao > 0 else "▼"

var_saldo = (atual["saldo_mi"] - anterior["saldo_mi"]) / 1000
var_contratos = atual["contratos"] - anterior["contratos"]
var_over30 = atual["over30_pct"] - anterior["over30_pct"]
var_over90 = atual["over90_pct"] - anterior["over90_pct"]

with col1:
    cartao("Saldo da carteira",
           f"R$ {atual['saldo_mi'] / 1000:.2f} bi",
           f"{seta(var_saldo)} {var_saldo:+.2f} bi no mês",
           "#17b6c9")                   # verde-água
with col2:
    cartao("Contratos ativos",
           f"{atual['contratos']:,.0f}".replace(",", "."),
           f"{seta(var_contratos)} {var_contratos:+,.0f} no mês".replace(",", "."),
           "#8b5cf6")                   # roxo
with col3:
    cartao("Over 30",
           f"{atual['over30_pct']:.2f}%",
           f"{seta(var_over30)} {var_over30:+.2f} p.p. no mês",
           "#4c8dff")                   # azul (mesma cor da linha Over 30)
with col4:
    cartao("Over 90",
           f"{atual['over90_pct']:.2f}%",
           f"{seta(var_over90)} {var_over90:+.2f} p.p. no mês",
           "#ff8a3d")                   # laranja (mesma cor da linha Over 90)

# EVOLUÇÃO DA INADIMPLÊNCIA (gráfico de linhas)
st.subheader("Evolução do atraso da carteira")

PAINEL = "#16181f"      # fundo dos gráficos (um tom mais claro que a página)
AZUL = "#4c8dff"        # cor da série Over 30
LARANJA = "#ff8a3d"     # cor da série Over 90
# rótulo do mês no eixo: "2025-09-30" vira "09/2025"
meses = pd.to_datetime(carteira["data_base"]).dt.strftime("%m/%Y")

grafico = go.Figure()
for coluna, nome, cor in [("over30_pct", "Over 30", AZUL),
                          ("over90_pct", "Over 90", LARANJA)]:
    grafico.add_trace(go.Scatter(
        x=meses, y=carteira[coluna], name=nome,
        mode="lines+markers",
        line=dict(color=cor, width=3, shape="spline"), marker=dict(size=8),
        hovertemplate="%{y:.2f}%<extra>" + nome + "</extra>",
    ))
    # rótulo direto no último ponto de cada linha
    grafico.add_annotation(
        x=meses.iloc[-1], y=carteira[coluna].iloc[-1],
        text=f"{nome}: {carteira[coluna].iloc[-1]:.2f}%",
        showarrow=False, xanchor="left", xshift=10,
    )

grafico.update_layout(
    height=400,
    margin=dict(l=20, r=130, t=20, b=20),
    paper_bgcolor=PAINEL, plot_bgcolor=PAINEL,  # fundo do gráfico
    hovermode="x unified",                      # uma caixa com as duas séries
    legend=dict(orientation="h", y=1.1),
    yaxis=dict(ticksuffix="%", rangemode="tozero"),
)
st.plotly_chart(grafico, width="stretch")

# ALERTAS DO MÊS
st.subheader("Alertas do mês")
alertas = ler_tabela("SELECT * FROM alertas")

col_risco, col_atencao, col_oportunidade = st.columns(3)

with col_risco:
    st.markdown("**Riscos**")
    for _, a in alertas[alertas["tipo"] == "RISCO"].iterrows():
        st.error(f"**{a['segmento']}**  \n{a['mensagem']}", icon="🔴")

with col_atencao:
    st.markdown("**Pontos de atenção**")
    for _, a in alertas[alertas["tipo"] == "ATENÇÃO"].iterrows():
        st.warning(f"**{a['segmento']}**  \n{a['mensagem']}", icon="🟡")

with col_oportunidade:
    st.markdown("**Oportunidades**")
    for _, a in alertas[alertas["tipo"] == "OPORTUNIDADE"].iterrows():
        st.success(f"**{a['segmento']}**  \n{a['mensagem']}", icon="🟢")

# ABAS DE DETALHE
st.subheader("Detalhes")
aba_segmento, aba_atencao, aba_qualidade = st.tabs(
    ["Por segmento", "Atenção (roll rate)", "Qualidade dos dados"])
# ----- ABA 1: indicadores por produto ou por setor -----
with aba_segmento:
    visao = st.selectbox("Abrir a carteira por:", ["produto", "setor"])

    segmentos = ler_tabela("""
        SELECT * FROM indicadores_mensais
        WHERE dimensao <> 'carteira'
    """)
    # fica só com a visão escolhida e o último mês; ordena do menor para o maior
    recorte = segmentos[(segmentos["dimensao"] == visao)
                        & (segmentos["data_base"] == atual["data_base"])]
    recorte = recorte.sort_values("over30_pct")

    barras = go.Figure()
    for coluna, nome, cor in [("over90_pct", "Over 90", LARANJA),
                              ("over30_pct", "Over 30", AZUL)]:
        barras.add_trace(go.Bar(
            y=recorte["segmento"], x=recorte[coluna], name=nome,
            orientation="h", marker_color=cor,
            text=recorte[coluna].map("{:.2f}%".format), textposition="outside",
            hovertemplate="%{x:.2f}%<extra>" + nome + "</extra>",
        ))
    barras.update_layout(
        height=90 + 60 * len(recorte),
        margin=dict(l=20, r=70, t=20, b=20),
        paper_bgcolor=PAINEL, plot_bgcolor=PAINEL,
        barmode="group", bargap=0.3,
        legend=dict(orientation="h", y=1.08, traceorder="reversed"),
        xaxis=dict(ticksuffix="%"),
    )
    st.plotly_chart(barras, width="stretch")

    st.caption("Tabela com os mesmos números do gráfico")
    st.dataframe(
        recorte.sort_values("over30_pct", ascending=False)[
            ["segmento", "contratos", "saldo_mi", "part_pct", "over30_pct", "over90_pct"]],
        hide_index=True, width="stretch",
    )

# ----- ABA 2: ocorrências de qualidade e controle das cargas -----
with aba_qualidade:
    st.markdown("**Ocorrências encontradas e tratadas**")
    st.dataframe(ler_tabela("SELECT * FROM qualidade_ocorrencias ORDER BY ref_carga"),
                 hide_index=True, width="stretch")

    st.markdown("**Controle das cargas**")
    st.dataframe(ler_tabela("""
        SELECT tabela,
               COUNT(DISTINCT referencia) AS meses_carregados,
               SUM(linhas)                AS linhas,
               MAX(data_carga)            AS ultima_carga
        FROM controle_cargas
        GROUP BY tabela
    """), hide_index=True, width="stretch")
# ----- ABA 3: roll rate - o que aconteceu com quem estava atrasado -----
with aba_atencao:
    roll = ler_tabela("SELECT * FROM roll_rate")
    st.caption(f"Movimento dos contratos de {roll['ref_anterior'].iloc[0]} "
               f"para {roll['ref_atual'].iloc[0]}")

    # saldo "em atenção": atrasado de 1 a 90 dias, ainda não inadimplente
    em_atencao = roll[roll["faixa_anterior"].str[0].isin(["1", "2", "3"])]
    st.metric("Saldo em atenção (1 a 90 dias de atraso)",
              f"R$ {em_atencao['saldo_mi'].sum():,.0f} mi".replace(",", "."))

    # barras empilhadas: de cada faixa, quanto regularizou e quanto piorou
    atrasados = roll[roll["faixa_anterior"] != "0) em dia"]
    faixas = atrasados["faixa_anterior"].str[3:]          # tira o "1) " do começo

    VERDE = "#22c58b"       # regularizou (bom)
    VERMELHO = "#f0556a"    # piorou (ruim)
    empilhado = go.Figure()
    for coluna, nome, cor in [("regularizou_pct", "Regularizou", VERDE),
                              ("piorou_pct", "Piorou", VERMELHO)]:
        empilhado.add_trace(go.Bar(
            x=faixas, y=atrasados[coluna], name=nome,
            marker=dict(color=cor, line=dict(color="#16181f", width=2)),
            text=atrasados[coluna].map("{:.1f}%".format), textposition="inside",
            textfont=dict(color="white"),
            hovertemplate="%{y:.1f}%<extra>" + nome + "</extra>",
        ))
    empilhado.update_layout(
        height=400, barmode="stack", bargap=0.45,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor=PAINEL, plot_bgcolor=PAINEL,
        legend=dict(orientation="h", y=1.1),
        yaxis=dict(ticksuffix="%"),
        xaxis=dict(title="Faixa de atraso no mês anterior"),
    )
    st.plotly_chart(empilhado, width="stretch")

    st.dataframe(roll[["faixa_anterior", "contratos", "saldo_mi",
                       "piorou_pct", "regularizou_pct"]],
                 hide_index=True, width="stretch")

