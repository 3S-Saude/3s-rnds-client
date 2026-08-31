# RIRA — Registro de Informações da Regulação Assistencial

O módulo `rnds_client.rira` implementa o envio e a consulta de documentos RIRA
na RNDS.

A partir de dados de negócio simples (`RiraDocumentData`), o módulo monta um
**Bundle FHIR R4 do tipo `document`** com quatro recursos
(`Composition`, `Appointment`, `ServiceRequest`, `Condition`), valida invariantes
do manual da RNDS/DATASUS e faz o `POST` para o endpoint `fhir/r4/Bundle`. Para
inspecionar o JSON exato do Bundle, use [`dump_bundle_json`](#api-clientrira).

> Disponível a partir da versão **0.2.0** do `3s-rnds-client`
> (ver [Atualização de versão](#atualização-de-versão)).

---

## Índice

- [Visão geral](#visão-geral)
- [Instalação e configuração no Django](#instalação-e-configuração-no-django)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Modelo de dados: `RiraDocumentData`](#modelo-de-dados-riradocumentdata)
- [Ciclo de vida da regulação](#ciclo-de-vida-da-regulação)
- [API: `client.rira`](#api-clientrira)
- [Invariantes e validações](#invariantes-e-validações)
- [Lógica de substituição (`relatesTo`)](#lógica-de-substituição-relatesto)
- [Persistência local: `RNDSDocumentRecord`](#persistência-local-rndsdocumentrecord)
- [Log de depuração](#log-de-depuração)
- [Tratamento de erros](#tratamento-de-erros)
- [Atualização de versão](#atualização-de-versão)

---

## Visão geral

O RIRA registra na RNDS o andamento de uma solicitação regulada — desde a
solicitação inicial até o atendimento (ou a devolução ao solicitante). Cada
mudança de estado relevante gera um novo documento que **substitui** o anterior
(ver [Lógica de substituição](#lógica-de-substituição-relatesto)).

Fluxo de um envio:

1. A aplicação monta um `RiraDocumentData` com os dados da regulação.
2. `client.rira.criar_documento_<status>(dados)` monta o Bundle, envia e retorna
   o `id_rnds`.
3. Envios seguintes do mesmo `id_local` **substituem** o documento anterior
   (ver [Lógica de substituição](#lógica-de-substituição-relatesto)).

Pontos de entrada públicos: `RiraDocumentData` e `RiraFhirSettings`
(`from rnds_client.rira`), e `RiraCapability`, exposta como `client.rira`.

---

## Instalação e configuração no Django

O módulo é um **app Django** (usa o ORM para rastrear os envios). No projeto
consumidor:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "rnds_client.rira",
]
```

```bash
python manage.py migrate rnds_rira
```

A migração cria a tabela do [`RNDSDocumentRecord`](#persistência-local-rndsdocumentrecord).

---

## Variáveis de ambiente

Além das variáveis do cliente base ([README](../../../README.md#configuracao-no-django)),
o RIRA exige — **todas obrigatórias**; se faltar alguma, o primeiro envio falha:

| Variável                | Descrição                                                                                     |
|-------------------------|----------------------------------------------------------------------------------------------|
| `RIRA_NAMING_SYSTEM_ID` | Sufixo do NamingSystem que identifica o Bundle (`.../NamingSystem/BRRNDS-<id>`).             |
| `RIRA_COMP_PROFILE`     | URL do perfil FHIR do recurso `Composition`.                                                 |
| `RIRA_SR_PROFILE`       | URL do perfil FHIR do recurso `ServiceRequest`.                                              |
| `RIRA_APP_PROFILE`      | URL do perfil FHIR do recurso `Appointment`.                                                 |
| `RIRA_COND_PROFILE`     | URL do perfil FHIR do recurso `Condition`.                                                   |

Lista copiável (base + `RIRA_*`): seção
[Configuração no Django](../../../README.md#configuracao-no-django) do README.

---

## Modelo de dados: `RiraDocumentData`

`dataclass` de entrada (`rnds_client.rira.schemas.rira_document`). Datas são
strings no formato `dateTime` FHIR (ex.: `2024-01-15T10:00:00-03:00`).

### Campos obrigatórios

| Campo              | Tipo  | Descrição                                                                 |
|-------------------|-------|--------------------------------------------------------------------------|
| `id_local`         | `str` | Identificador da solicitação no sistema de origem. Chave de correlação (ver [Lógica de substituição](#lógica-de-substituição-relatesto)). |
| `id_paciente`      | `str` | CPF ou CNS do paciente.                                                 |
| `sigtap`           | `str` | Código do procedimento na Tabela SUS (SIGTAP).                          |
| `cid10`            | `str` | Código CID-10 do diagnóstico.                                           |
| `data_solicitacao` | `str` | Data/hora da solicitação. Ver [Resolução de datas](#resolução-de-datas). |
| `cnes_solicitante` | `str` | CNES do estabelecimento solicitante.                                    |
| `modalidade`       | `str` | Código da modalidade assistencial (`BRModalidadeAssistencial`).         |
| `carater`          | `str` | Prioridade/caráter da solicitação (`request-priority`: `routine`, `urgent`, `asap`, `stat`). |

### Campos opcionais

| Campo               | Tipo          | Efeito                                                                                    |
|--------------------|---------------|-----------------------------------------------------------------------------------------|
| `cnes_regulador`    | `str \| None`  | CNES do regulador. Quando presente, é o autor do documento.                             |
| `cnes_executante`   | `str \| None`  | CNES do estabelecimento executante.                                                     |
| `cbo_executante`    | `str \| None`  | CBO do profissional executante. **Obrigatório** para SIGTAP dos grupos 03 e 04.        |
| `data_autorizacao`  | `str \| None`  | Data da autorização. Ver [Resolução de datas](#resolução-de-datas).                     |
| `data_agendamento`  | `str \| None`  | Data do agendamento. Ver [Resolução de datas](#resolução-de-datas).                     |
| `data_atendimento`  | `str \| None`  | Data do atendimento. Ver [Resolução de datas](#resolução-de-datas).                     |
| `observacao`        | `str \| None`  | Observação clínica. Default: `"Sem observações"`.                                       |

### Resolução de datas

- `data_solicitacao` é sempre o início do período registrado.
- Para `booked` / `attended`, preencha `data_agendamento` **ou** `data_autorizacao`
  (senão o envio falha — ver [Invariantes e validações](#invariantes-e-validações)).
- A data final do período é a primeira preenchida entre: `data_atendimento` →
  `data_agendamento` → `data_autorizacao` → `data_solicitacao`.

### Validação dos valores

O módulo **não** valida os códigos que você passa (`id_paciente`, `sigtap`,
`cid10`, `carater`, `modalidade`, `cbo_executante`) nem o formato das datas — só
as duas invariantes de [Invariantes e validações](#invariantes-e-validações) são
checadas localmente. Códigos inválidos só são recusados pela própria RNDS, na
resposta ao envio.

---

## Ciclo de vida da regulação

Cada método envia um status de regulação. `booked` e `attended` exigem que uma
data de agendamento/autorização esteja preenchida (ver
[Resolução de datas](#resolução-de-datas)).

| Método `client.rira.*`                    | Status enviado           | Exige data de agendamento? |
|------------------------------------------|--------------------------|----------------------------|
| `criar_documento_pending`                 | `pending`                | Não                        |
| `criar_documento_booked`                  | `booked`                 | **Sim**                    |
| `criar_documento_attended`                | `attended`               | **Sim**                    |
| `criar_documento_returned_to_requester`   | `returned-to-requester`  | Não                        |

Sequência típica: `pending` → `booked` → `attended`, cada envio substituindo o
anterior (ver [Lógica de substituição](#lógica-de-substituição-relatesto)).

---

## API: `client.rira`

`RiraCapability`, acessível via `client.rira` após `RndsClient.create()`.

### Envio

```python
from rnds_client import RndsClient
from rnds_client.rira import RiraDocumentData

dados = RiraDocumentData(
    id_local="solicitacao-42",
    id_paciente="12345678901",
    sigtap="0301010010",
    cid10="M545",
    data_solicitacao="2024-01-15T10:00:00-03:00",
    cnes_solicitante="1234567",
    modalidade="09",
    carater="routine",
    cbo_executante="223505",
)

async def enviar():
    async with await RndsClient.create() as client:
        id_rnds = await client.rira.criar_documento_pending(dados)
        return id_rnds  # ex.: "1a2b3c4d-...."
```

| Método                                                | Retorno       | Descrição                                                                 |
|------------------------------------------------------|---------------|------------------------------------------------------------------------|
| `await criar_documento_pending(dados)`                | `str`         | Envia o documento com status `pending`. Retorna o `id_rnds`.          |
| `await criar_documento_booked(dados)`                 | `str`         | Envia com status `booked` (agendado).                                 |
| `await criar_documento_attended(dados)`               | `str`         | Envia com status `attended` (atendido).                               |
| `await criar_documento_returned_to_requester(dados)`  | `str`         | Envia com status `returned-to-requester` (devolvido ao solicitante).  |
| `await get_documento(id_rnds)`                        | `dict`        | Consulta o documento na RNDS (com retry). `{}` se a resposta for vazia. Não toca o banco local. |
| `await deletar_documento(id_rnds)`                    | `None`        | Remove o documento na RNDS (sem retry). **Não** remove o registro local — ver [Lógica de substituição](#lógica-de-substituição-relatesto). |
| `dump_bundle_json(dados, composition_status, id_rnds_anterior=None)` | `str` | Monta o Bundle e devolve o JSON indentado **sem enviar** (debug/inspeção). Síncrono; exige as variáveis `RIRA_*`. Não consulta o banco — passe `id_rnds_anterior` para simular a substituição. |

Todos os métodos são `async`, exceto `dump_bundle_json`.

---

## Invariantes e validações

Checadas ao montar o Bundle. A falha chega ao chamador como
`pydantic.ValidationError` com a mensagem do RIRA embutida — ver
[Tratamento de erros](#tratamento-de-erros).

### 1. Datas obrigatórias em `booked` / `attended`

`criar_documento_booked` e `criar_documento_attended` exigem `data_agendamento`
**ou** `data_autorizacao` preenchida em `RiraDocumentData`.

Mensagem (dentro do `ValidationError`):

```
status 'booked' exige start e end (invariante FHIR Appointment).
Preencha data_agendamento ou data_autorizacao em RiraDocumentData.
```

### 2. CBO obrigatório nos grupos SIGTAP 03 e 04

Se os dois primeiros dígitos do código SIGTAP forem `03` ou `04`
(procedimentos clínicos / cirúrgicos), `cbo_executante` é obrigatório.

Mensagem (dentro do `ValidationError`):

```
CBO obrigatório para procedimentos SIGTAP do grupo 03.
Preencha cbo_executante em RiraDocumentData.
```

---

## Lógica de substituição (`relatesTo`)

O módulo guarda **um** documento por `id_local`. A cada envio bem-sucedido do
mesmo `id_local`, o novo documento **substitui** o anterior na RNDS; o primeiro
envio não substitui nada. `id_local` distintos são independentes.

Sequência típica (mesmo `id_local` a cada etapa):

```python
dados = RiraDocumentData(id_local="solicitacao-42", ...)

await client.rira.criar_documento_pending(dados)
# ... regulação avança; preencha data_agendamento em `dados` ...
await client.rira.criar_documento_booked(dados)    # substitui o pending
# ... paciente atendido; preencha data_atendimento ...
await client.rira.criar_documento_attended(dados)  # substitui o booked
```

> **Atenção:** `deletar_documento` remove o documento na RNDS mas **não** apaga o
> registro local. Um `criar_documento_*` posterior para o mesmo `id_local` ainda
> tentará substituir o documento apagado. Se o fluxo previr exclusão, limpe o
> registro local por conta própria.

---

## Persistência local: `RNDSDocumentRecord`

O módulo mantém uma tabela `RNDSDocumentRecord` (app `rnds_rira`) com **uma linha
por `id_local`**: guarda o `id_rnds` e o último status enviados, para saber qual
documento substituir no envio seguinte.

Falhas ao ler/gravar essa tabela são **engolidas e apenas logadas** — não
interrompem o envio à RNDS, mas a substituição do próximo envio pode ficar
incompleta. Já uma falha no envio em si propaga ao chamador.

---

## Log de depuração

- Request/response de cada chamada à RNDS: [Modo debug](../../../README.md#modo-debug), no README.
- Inspecionar o Bundle sem enviar: [`dump_bundle_json`](#api-clientrira).

---

## Tratamento de erros

| Exceção                | Origem                                                                    |
|-----------------------|-------------------------------------------------------------------------|
| `pydantic.ValidationError` | Invariante do RIRA violada ao montar o Bundle (datas de `booked`/`attended` ou CBO nos grupos SIGTAP 03/04). A mensagem do RIRA vem em `str(exc)`. **Capture `pydantic.ValidationError`**, não `RiraValidationError` — o Pydantic embrulha a exceção do validator. |
| `RndsSubmissionError` | Envio sem retorno de ID (RNDS respondeu sem o header `Location`). |
| `KeyError`            | Variável `RIRA_*` ausente no ambiente (na 1ª chamada de envio ou `dump_bundle_json`). |
| `httpx.HTTPStatusError` / `httpx.HTTPError` | Erros de transporte / status HTTP da RNDS.        |

`RndsSubmissionError` e `RiraValidationError` são reexportadas em `rnds_client`.

---

## Atualização de versão

Entregue na versão **`0.2.0`** do `3s-rnds-client` (mudança **minor**,
retrocompatível). Passos de instalação: [Instalação e configuração no
Django](#instalação-e-configuração-no-django). Changelog:
[README, seção "Versão"](../../../README.md#versao).
