# ROTINA DO MÊS (um comando só)
# Todo mês, quando chegam os arquivos novos em dados/entrada, a rotina é sempre a mesma, na mesma ordem:
    #   1. carga       -> coloca os arquivos novos no banco (camada bruta)
    #   2. tratamento  -> limpa, marca os problemas e registra as ocorrências
    #   3. alertas     -> recalcula indicadores, alertas e roll rate
# Este script roda os três em sequência. Se um deles der erro, ele PARA:
# não faz sentido calcular alertas em cima de uma carga que falhou.
#
# Como usar (no Terminal, dentro da pasta Projeto_1):
#     python 05_rotina_mensal.py
# Depois, no painel: menu dos três pontinhos > Clear cache, e tecla R.

from pathlib import Path
from datetime import datetime
import subprocess      # permite que um script rode outros scripts
import sys             # dá acesso ao Python que está em uso
import time            # para medir quanto tempo cada etapa leva

PASTA = Path(__file__).parent

# os scripts da rotina, NA ORDEM em que precisam rodar
ETAPAS = [
    ("Carga dos arquivos", "02_carga_mensal.py"),
    ("Tratamento e qualidade", "03_tratamento.py"),
    ("Indicadores e alertas", "04_alertas.py"),
]

print("=" * 60)
print("ROTINA DO MÊS - início em", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
print("=" * 60)

inicio_total = time.time()

for numero, (descricao, arquivo) in enumerate(ETAPAS, start=1):
    print(f"\n>>> Etapa {numero} de {len(ETAPAS)}: {descricao} ({arquivo})")
    inicio = time.time()

    # roda o script como se você tivesse digitado "python arquivo.py"
    resultado = subprocess.run([sys.executable, str(PASTA / arquivo)])

    # returncode 0 = terminou sem erro; qualquer outro número = deu erro
    if resultado.returncode != 0:
        print(f"\n*** ERRO na etapa {numero} ({arquivo}). Rotina interrompida. ***")
        print("Leia a mensagem de erro acima, corrija e rode a rotina de novo.")
        sys.exit(1)                      # encerra avisando que houve erro

    print(f"<<< Etapa {numero} concluída em {time.time() - inicio:.0f} segundos")

print("\n" + "=" * 60)
print(f"ROTINA CONCLUÍDA em {time.time() - inicio_total:.0f} segundos")
print("Próximo passo: abrir o painel e conferir os alertas do mês.")
print("=" * 60)