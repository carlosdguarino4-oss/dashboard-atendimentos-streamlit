import codecs
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Dashboard de Atendimentos", page_icon="🏥", layout="wide")


MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

ORDEM_FAIXAS = ["0 a 12", "13 a 17", "18 a 29", "30 a 44", "45 a 59", "60 ou mais"]
PONTO_MEDIO_FAIXA = {
    "0 a 12": 6,
    "13 a 17": 15,
    "18 a 29": 23.5,
    "30 a 44": 37,
    "45 a 59": 52,
    "60 ou mais": 67.5,
}


def ler_lista_json_em_blocos(arquivo, tamanho_bloco=1024 * 1024):
    """Lê um array JSON aos poucos, sem colocar o arquivo inteiro na memória."""
    arquivo.seek(0)
    decodificador_utf8 = codecs.getincrementaldecoder("utf-8-sig")()
    decodificador_json = json.JSONDecoder()
    texto = ""
    posicao = 0
    iniciou_lista = False
    terminou_arquivo = False

    while True:
        if posicao > 0:
            texto = texto[posicao:]
            posicao = 0

        while True:
            while posicao < len(texto) and (texto[posicao].isspace() or texto[posicao] == ","):
                posicao += 1

            if not iniciou_lista:
                if posicao < len(texto):
                    if texto[posicao] != "[":
                        raise ValueError("O JSON precisa começar com uma lista: [ ... ]")
                    iniciou_lista = True
                    posicao += 1
                    continue

            while posicao < len(texto) and (texto[posicao].isspace() or texto[posicao] == ","):
                posicao += 1

            if posicao < len(texto) and texto[posicao] == "]":
                return

            try:
                item, nova_posicao = decodificador_json.raw_decode(texto, posicao)
                posicao = nova_posicao
                yield item
            except json.JSONDecodeError:
                break

        if terminou_arquivo:
            if texto[posicao:].strip():
                raise ValueError("O arquivo JSON está incompleto ou possui formato inválido.")
            return

        texto = texto[posicao:]
        posicao = 0
        bloco = arquivo.read(tamanho_bloco)
        if bloco:
            if isinstance(bloco, str):
                texto += bloco
            else:
                texto += decodificador_utf8.decode(bloco)
        else:
            texto += decodificador_utf8.decode(b"", final=True)
            terminou_arquivo = True


def obter_data(valor):
    if isinstance(valor, dict):
        valor = valor.get("$date")
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def limpar_texto(valor):
    if not isinstance(valor, str):
        return None
    texto = re.sub(r"\s+", " ", valor).strip(" .;,-").upper()
    return texto or None


def sem_acentos(texto):
    return "".join(
        letra for letra in unicodedata.normalize("NFD", texto)
        if unicodedata.category(letra) != "Mn"
    )


# Sinônimos são agrupados no mesmo sintoma. Acrescente termos aqui se necessário.
PADROES_SINTOMAS = {
    "Febre": r"\b(?:febre|febril|hipertermia)\b",
    "Tosse": r"\btosse\b",
    "Falta de ar": r"\b(?:dispneia|falta de ar|dificuldade (?:para |de |em )?respirar)\b",
    "Dor de cabeça": r"\b(?:cefaleia|dor (?:de |na )?cabeca)\b",
    "Dor abdominal": r"\b(?:dor(?:es)? (?:abdomina(?:l|is)|(?:na |de )barriga|no abdomen)|abdominalgia)\b",
    "Dor no peito": r"\b(?:dor (?:no peito|toracica)|precordialgia)\b",
    "Dor de garganta": r"\b(?:dor (?:de |na )garganta|odinofagia)\b",
    "Dor nas costas": r"\b(?:lombalgia|dor (?:lombar|nas costas)|dor.{0,35}coluna lombar)\b",
    "Dor muscular": r"\b(?:mialgia|dor(?:es)? muscular(?:es)?)\b",
    "Dor nas articulações": r"\b(?:artralgia|dor(?:es)? (?:articular(?:es)?|nas articulacoes))\b",
    "Náusea": r"\b(?:nausea[s]?|enjoo|ancia de vomito|ansia de vomito)\b",
    "Vômito": r"\b(?:vomito[s]?|vomitando|emese)\b",
    "Diarreia": r"\bdiarreia\b",
    "Tontura": r"\b(?:tontura[s]?|vertigem)\b",
    "Fraqueza": r"\b(?:fraqueza|astenia)\b",
    "Mal-estar": r"\bmal[ -]?estar\b",
    "Desmaio": r"\b(?:desmaio|desmaiou|sincope)\b",
    "Convulsão": r"\b(?:convulsao|convulsiva|convulsionando|crise epileptica)\b",
    "Coceira": r"\b(?:coceira|prurido)\b",
    "Manchas ou lesões na pele": r"\b(?:manchas (?:vermelhas|na pele)|erupcao|lesoes (?:na pele|cutaneas))\b",
    "Inchaço": r"\b(?:inchaco|edema|inchado|inchada)\b",
    "Congestão ou secreção nasal": r"\b(?:coriza|congestao nasal|secrecao nasal|nariz entupido)\b",
    "Dor ao urinar": r"\b(?:disuria|dor ao urinar|ardencia ao urinar|ardor ao urinar)\b",
    "Dor de ouvido": r"\b(?:otalgia|dor (?:de |no )ouvido)\b",
    "Sangramento": r"\b(?:sangramento|hemorragia|epistaxe)\b",
}
PADROES_SINTOMAS = {
    nome: re.compile(padrao) for nome, padrao in PADROES_SINTOMAS.items()
}


def extrair_sintomas(queixa):
    """Retorna cada sintoma uma única vez por registro, usando palavras-chave."""
    if not isinstance(queixa, str):
        return set()
    texto = sem_acentos(queixa.lower())
    # Remove trechos negativos até uma nova frase ou uma afirmação explícita.
    texto = re.sub(
        r"\b(?:nega(?:m)?|sem|ausencia de|nao apresenta|nao refere)\b.*?"
        r"(?=[.;\n]|\b(?:mas|porem|refere|apresenta|relata|queixa)\b|$)",
        " ", texto,
    )
    sintomas = {nome for nome, padrao in PADROES_SINTOMAS.items() if padrao.search(texto)}
    # 'Ânsia de vômito' é náusea, sem afirmar que houve vômito.
    texto_sem_ansia = re.sub(r"\b(?:ancia|ansia) de vomito\b", "", texto)
    if not PADROES_SINTOMAS["Vômito"].search(texto_sem_ansia):
        sintomas.discard("Vômito")
    return sintomas


def faixa_etaria(idade):
    if idade <= 12:
        return "0 a 12"
    if idade <= 17:
        return "13 a 17"
    if idade <= 29:
        return "18 a 29"
    if idade <= 44:
        return "30 a 44"
    if idade <= 59:
        return "45 a 59"
    return "60 ou mais"


def calcular_idade(nascimento, atendimento):
    idade = atendimento.year - nascimento.year
    if (atendimento.month, atendimento.day) < (nascimento.month, nascimento.day):
        idade -= 1
    return idade


def tabela_contagem(contador, nome_coluna, limite=None):
    itens = contador.most_common(limite)
    return pd.DataFrame(itens, columns=[nome_coluna, "Quantidade"])


st.title("🏥 Dashboard de Atendimentos Hospitalares")
st.write("Envie o arquivo JSON para gerar automaticamente os indicadores.")

arquivo = st.file_uploader("Selecione o arquivo JSON", type="json")

if arquivo is None:
    st.info("Aguardando o envio de um arquivo JSON.")
    st.stop()

queixas = Counter()
diagnosticos = Counter()
generos = Counter()
faixas_pacientes = Counter()
faixas_atendimentos = Counter()
meses = Counter()
total_pacientes = 0
total_atendimentos = 0

diagnosticos_invalidos = {
    "", "NAO DEFINIDO", "NÃO DEFINIDO", "NAO INFORMADO", "NÃO INFORMADO",
    "SEM DIAGNOSTICO", "SEM DIAGNÓSTICO",
}

try:
    with st.spinner("Lendo e analisando o arquivo..."):
        for paciente in ler_lista_json_em_blocos(arquivo):
            if not isinstance(paciente, dict):
                continue

            total_pacientes += 1
            nascimento = obter_data(paciente.get("dataNascimento"))

            genero = limpar_texto(paciente.get("sexo")) or "NÃO INFORMADO"
            genero = {"F": "Feminino", "M": "Masculino"}.get(genero, genero.title())
            generos[genero] += 1

            registros_validos = []
            for registro in paciente.get("registros", []):
                if not isinstance(registro, dict):
                    continue

                entrada = obter_data(registro.get("dataEntrada"))
                info = registro.get("informacoes", {})
                if not isinstance(info, dict):
                    info = {}

                # Cada registro é considerado um atendimento.
                total_atendimentos += 1
                registros_validos.append(entrada)

                if entrada:
                    meses[MESES[entrada.month]] += 1
                    if nascimento:
                        idade = calcular_idade(nascimento, entrada)
                        if 0 <= idade <= 120:
                            faixas_atendimentos[faixa_etaria(idade)] += 1

                queixas.update(extrair_sintomas(info.get("queixa")))

                diagnostico = limpar_texto(info.get("diagnostico"))
                if diagnostico and sem_acentos(diagnostico).strip(" .") not in {
                    sem_acentos(item) for item in diagnosticos_invalidos
                }:
                    diagnosticos[diagnostico] += 1

            # Para a distribuição de pacientes, usa a idade no atendimento mais recente.
            datas = [data for data in registros_validos if data]
            if nascimento and datas:
                idade_atual_no_conjunto = calcular_idade(nascimento, max(datas))
                if 0 <= idade_atual_no_conjunto <= 120:
                    faixas_pacientes[faixa_etaria(idade_atual_no_conjunto)] += 1

except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as erro:
    st.error(f"Não foi possível ler o arquivo: {erro}")
    st.stop()

st.success("Arquivo processado com sucesso!")

col1, col2, col3 = st.columns(3)
col1.metric("Pacientes", f"{total_pacientes:,}".replace(",", "."))
col2.metric("Atendimentos", f"{total_atendimentos:,}".replace(",", "."))
media = total_atendimentos / total_pacientes if total_pacientes else 0
col3.metric("Média por paciente", f"{media:.2f}".replace(".", ","))

st.divider()

col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("10 principais queixas")
    st.caption(
        "Sintomas agrupados por palavras-chave, contados uma vez por registro. "
        "Um registro pode conter vários sintomas. A filtragem é aproximada."
    )
    df_queixas = tabela_contagem(queixas, "Queixa", 10)
    st.dataframe(df_queixas, use_container_width=True, hide_index=True)
    if not df_queixas.empty:
        grafico = df_queixas.copy()
        grafico["Queixa"] = grafico["Queixa"].str.slice(0, 70)
        st.bar_chart(grafico.set_index("Queixa"), horizontal=True)
    else:
        st.info("Nenhum sintoma reconhecido nas queixas deste arquivo.")

with col_dir:
    st.subheader("10 principais diagnósticos")
    df_diagnosticos = tabela_contagem(diagnosticos, "Diagnóstico", 10)
    st.dataframe(df_diagnosticos, use_container_width=True, hide_index=True)
    if not df_diagnosticos.empty:
        st.bar_chart(df_diagnosticos.set_index("Diagnóstico"), horizontal=True)

col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("Gêneros")
    df_generos = tabela_contagem(generos, "Gênero")
    st.dataframe(df_generos, use_container_width=True, hide_index=True)
    if not df_generos.empty:
        st.bar_chart(df_generos.set_index("Gênero"))

with col_dir:
    st.subheader("Faixas etárias dos pacientes")
    df_faixas = pd.DataFrame({
        "Faixa etária": ORDEM_FAIXAS,
        "Quantidade": [faixas_pacientes[faixa] for faixa in ORDEM_FAIXAS],
    })
    st.dataframe(df_faixas, use_container_width=True, hide_index=True)
    st.bar_chart(df_faixas.set_index("Faixa etária"))

st.subheader("Meses com maior índice de atendimentos")
ordem_meses = list(MESES.values())
df_meses = pd.DataFrame({
    "Mês": ordem_meses,
    "Atendimentos": [meses[mes] for mes in ordem_meses],
}).sort_values("Atendimentos", ascending=False, ignore_index=True)
st.dataframe(df_meses, use_container_width=True, hide_index=True)
st.bar_chart(df_meses.set_index("Mês"))

st.subheader("Correlação entre faixa etária e quantidade de atendimentos")
df_correlacao = pd.DataFrame({
    "Faixa etária": ORDEM_FAIXAS,
    "Idade representativa": [PONTO_MEDIO_FAIXA[faixa] for faixa in ORDEM_FAIXAS],
    "Atendimentos": [faixas_atendimentos[faixa] for faixa in ORDEM_FAIXAS],
})

if df_correlacao["Atendimentos"].nunique() > 1:
    correlacao = df_correlacao["Idade representativa"].corr(df_correlacao["Atendimentos"])
    st.metric("Coeficiente de correlação de Pearson", f"{correlacao:.3f}")
    if correlacao > 0.3:
        interpretacao = "Há tendência de aumento dos atendimentos nas faixas de maior idade."
    elif correlacao < -0.3:
        interpretacao = "Há tendência de redução dos atendimentos nas faixas de maior idade."
    else:
        interpretacao = "Não há uma tendência linear forte entre idade e número de atendimentos."
    st.write(interpretacao)
else:
    st.info("Não existem dados variados suficientes para calcular a correlação.")

st.dataframe(df_correlacao, use_container_width=True, hide_index=True)
st.bar_chart(df_correlacao.set_index("Faixa etária")[["Atendimentos"]])

st.caption(
    "Critério: cada item de 'registros' conta como um atendimento. "
    "A idade é calculada na data do atendimento. Diagnósticos não definidos são ignorados."
)
