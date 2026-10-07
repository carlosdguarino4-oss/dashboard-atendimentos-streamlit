# Dashboard de atendimentos

Projeto simples, desenvolvido inteiramente em Python com Streamlit.

## Como executar

Abra o PowerShell nesta pasta e rode:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run projIntG.py
```

Depois, selecione no navegador o arquivo JSON exportado do sistema.

## Indicadores

- 10 principais queixas;
- 10 principais diagnósticos;
- distribuição por gênero;
- distribuição por faixa etária;
- meses com mais atendimentos;
- correlação entre faixa etária e quantidade de atendimentos.

Cada item presente em `registros` é considerado um atendimento. O arquivo é lido em
blocos, permitindo analisar arquivos grandes sem carregá-los inteiros na memória.

## Formato do JSON

Use `exemplo.json` para testar com dados inteiramente fictícios. O arquivo deve ser
uma lista de pacientes com `sexo`, `dataNascimento` e uma lista `registros`.
Cada registro contém `dataEntrada` e `informacoes`, com `queixa` e `diagnostico`.
Datas podem ser textos ISO (`2026-10-07T12:00:00Z`) ou objetos com a chave `$date`.

As queixas são agrupadas por palavras-chave de sintomas. A filtragem de negações
é aproximada. Os gêneros são obtidos do campo `sexo`. Meses somam todos os anos.
A faixa etária dos pacientes usa o último registro; a faixa dos atendimentos usa
a idade em cada registro. A correlação é descritiva, entre idades representativas
das seis faixas e suas contagens, com 67,5 como referência para 60 anos ou mais.

O arquivo real com dados dos pacientes não faz parte deste repositório.
