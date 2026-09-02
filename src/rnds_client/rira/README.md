# RIRA — Registro de Informações da Regulação Assistencial

O módulo `rnds_client.rira` implementa o envio e a consulta de documentos RIRA
na RNDS.

A partir de dados de negócio simples (`RiraDocumentData`), o módulo monta um
**Bundle FHIR R4 do tipo `document`** com quatro recursos
(`Composition`, `Appointment`, `ServiceRequest`, `Condition`), valida invariantes
do manual da RNDS/DATASUS e faz o `POST` para o endpoint `fhir/r4/Bundle`. Para
inspecionar o JSON exato do Bundle, use [`dump_bundle_json`](#api-clientrira).

> Contrato **`0.3.0`** — *stateless*: o módulo **não** é um app Django, não roda
> `migrate` e não grava nada em banco. Ele não guarda estado de envio — quem chama
> é dono do identificador local e da cadeia de substituição. Ver
> [Atualização de versão](#atualização-de-versão) e
> [`docs/rira-evolucao-0.3.0.md`](../../../docs/rira-evolucao-0.3.0.md).

---

## Índice

- [Visão geral](#visão-geral)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Modelo de dados: `RiraDocumentData`](#modelo-de-dados-riradocumentdata)
- [Ciclo de vida da regulação](#ciclo-de-vida-da-regulação)
- [API: `client.rira`](#api-clientrira)
- [Resultado: `ResultadoEnvioRira`](#resultado-resultadoenviorira)
- [Invariantes e validações](#invariantes-e-validações)
- [Lógica de substituição (`relatesTo`)](#lógica-de-substituição-relatesto)
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
2. `await client.rira.enviar_rira(dados, identificador_local, status_rira=...)`
   monta o Bundle, envia e devolve um `ResultadoEnvioRira`.
3. Envios seguintes do mesmo `identificador_local` **substituem** o documento
   anterior — o chamador passa o `predecessor_composition_id`
   (ver [Lógica de substituição](#lógica-de-substituição-relatesto)).

Pontos de entrada públicos (`from rnds_client.rira`): `RiraDocumentData`,
`RiraFhirSettings`, `ResultadoEnvioRira`, as exceções `ErroRiraTransitorio` /
`ErroRiraRejeitado` / `ResultadoRiraIncerto`, e `RiraCapability`, exposta como
`client.rira`.

Para usar, bastam as [variáveis de ambiente](#variáveis-de-ambiente) e um
`RndsClient`.

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

O `identifier.system` do Bundle vem de `RIRA_NAMING_SYSTEM_ID` por padrão; o
chamador pode sobrepor por envio passando `identifier_system=` a `enviar_rira`
(útil quando o Naming System vem de uma credencial).

Lista copiável (base + `RIRA_*`): seção
[Configuração no Django](../../../README.md#configuracao-no-django) do README.

---

## Modelo de dados: `RiraDocumentData`

`dataclass` de entrada (`rnds_client.rira.schemas.rira_document`). Datas são
strings no formato `dateTime` FHIR (ex.: `2024-01-15T10:00:00-03:00`).

### Campos obrigatórios

| Campo              | Tipo  | Descrição                                                                 |
|-------------------|-------|--------------------------------------------------------------------------|
| `id_local`         | `str` | Identificador da solicitação no sistema de origem. É sobrescrito pelo `identificador_local` passado a `enviar_rira`. Chave de correlação (ver [Lógica de substituição](#lógica-de-substituição-relatesto)). |
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

`enviar_rira` recebe o `status_rira` da etapa. `booked` e `attended` exigem que
uma data de agendamento/autorização esteja preenchida (ver
[Resolução de datas](#resolução-de-datas)).

| `status_rira`            | Exige data de agendamento? |
|--------------------------|----------------------------|
| `pending`                | Não                        |
| `booked`                 | **Sim**                    |
| `attended`               | **Sim**                    |
| `returned-to-requester`  | Não                        |

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
        resultado = await client.rira.enviar_rira(
            dados, "solicitacao-42", status_rira="pending"
        )
        return resultado.id_rnds_bundle  # ex.: "1a2b3c4d-...."
```

| Método                                                                                                              | Retorno                    | Descrição                                                                                                                                    |
|-------------------------------------------------------------------------------------------------------------------|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| `await enviar_rira(dados, identificador_local, *, status_rira, identifier_system=None, predecessor_composition_id=None)` | `ResultadoEnvioRira`       | Monta o Bundle, envia e devolve o [resultado](#resultado-resultadoenviorira). `identificador_local` vira o `identifier.value` do Bundle. Passe `predecessor_composition_id` para substituir um documento anterior. |
| `await consultar_rira(identifier_system, identifier_value)`                                                        | `list[ResultadoEnvioRira]` | Consulta por `GET .../identifier?system=&value=&docType=RA` (manual §8.2). 404 / resposta vazia → `[]`.                                        |
| `await get_documento(id_rnds)`                                                                                    | `dict`                     | Consulta o documento na RNDS (com retry). `{}` se a resposta for vazia.                                                                       |
| `await deletar_documento(id_rnds)`                                                                                | `None`                     | Remove o documento na RNDS (sem retry).                                                                                                       |
| `dump_bundle_json(dados, composition_status, predecessor_composition_id=None)`                                     | `str`                      | Monta o Bundle e devolve o JSON indentado **sem enviar** (debug/inspeção). Síncrono; exige as variáveis `RIRA_*`.                             |

Todos os métodos são `async`, exceto `dump_bundle_json`.

`status_rira` aceita `pending`, `booked`, `attended`, `returned-to-requester`;
qualquer outro valor levanta `ValueError`.

---

## Resultado: `ResultadoEnvioRira`

`dataclass` congelado (`rnds_client.rira.results`), devolvido por `enviar_rira` e
por cada item de `consultar_rira`:

| Campo                 | Tipo          | Descrição                                                                                       |
|-----------------------|---------------|-----------------------------------------------------------------------------------------------|
| `http_status`         | `int`         | Status HTTP da resposta (ex.: `201`).                                                          |
| `location_rnds`       | `str \| None`  | Header `Location` **bruto** (URL completa do Bundle criado), sem truncar.                       |
| `id_rnds_bundle`      | `str \| None`  | Id do Bundle na RNDS, lido do corpo FHIR da resposta (ou do `Location`).                        |
| `id_rnds_composition` | `str \| None`  | Id da `Composition` — lido do corpo da resposta ou por `GET Bundle/{id}`. É o alvo do `relatesTo` do próximo envio. |
| `codigo_erro`         | `str \| None`  | Preenchido só em cenários de erro tratados sem exceção.                                         |
| `mensagem_sanitizada` | `str \| None`  | Mensagem de erro já sanitizada (sem dado clínico).                                              |

Para a substituição, guarde `id_rnds_composition` e passe-o como
`predecessor_composition_id` no envio seguinte.

---

## Invariantes e validações

Checadas ao montar o Bundle. A falha é convertida por `enviar_rira` em
`ErroRiraRejeitado(codigo="completude")` — ver
[Tratamento de erros](#tratamento-de-erros). Ao usar `dump_bundle_json`
diretamente, a falha chega como `pydantic.ValidationError` com a mensagem do RIRA
embutida.

### 1. Datas obrigatórias em `booked` / `attended`

`status_rira` `booked` e `attended` exigem `data_agendamento` **ou**
`data_autorizacao` preenchida em `RiraDocumentData`.

Mensagem:

```
status 'booked' exige start e end (invariante FHIR Appointment).
Preencha data_agendamento ou data_autorizacao em RiraDocumentData.
```

### 2. CBO obrigatório nos grupos SIGTAP 03 e 04

Se os dois primeiros dígitos do código SIGTAP forem `03` ou `04`
(procedimentos clínicos / cirúrgicos), `cbo_executante` é obrigatório.

Mensagem:

```
CBO obrigatório para procedimentos SIGTAP do grupo 03.
Preencha cbo_executante em RiraDocumentData.
```

---

## Lógica de substituição (`relatesTo`)

A biblioteca **não guarda estado**. A cadeia é responsabilidade do chamador:

- O `identifier.value` do Bundle é o `identificador_local` passado a `enviar_rira`.
  Envios com o mesmo valor são a mesma regulação; valores distintos são
  independentes.
- O **primeiro** envio de uma regulação não passa `predecessor_composition_id` —
  não gera `Composition.relatesTo`.
- Cada envio seguinte passa `predecessor_composition_id` = o
  `id_rnds_composition` devolvido pelo envio anterior. A lib gera
  `relatesTo.code = "replaces"`, `targetReference = "Composition/<id>"`.

```python
r1 = await client.rira.enviar_rira(dados, "solicitacao-42", status_rira="pending")
# ... regulação avança; preencha data_agendamento em `dados` ...
r2 = await client.rira.enviar_rira(
    dados, "solicitacao-42", status_rira="booked",
    predecessor_composition_id=r1.id_rnds_composition,
)
# ... paciente atendido; preencha data_atendimento ...
r3 = await client.rira.enviar_rira(
    dados, "solicitacao-42", status_rira="attended",
    predecessor_composition_id=r2.id_rnds_composition,
)
```

O manual §8.3 prevê a substituição "uma única vez" por documento; cadeias mais
longas (dias sucessivos) dependem de homologação — a lib não impõe esse limite,
o consumidor decide.

---

## Log de depuração

- Request/response de cada chamada à RNDS: [Modo debug](../../../README.md#modo-debug), no README.
  O corpo do Bundle e o corpo da resposta **não** são logados — só `method`, `url`,
  `status`, `body_len` e `location`.
- Inspecionar o Bundle sem enviar: [`dump_bundle_json`](#api-clientrira).

---

## Tratamento de erros

`enviar_rira` normaliza tudo em três exceções (`from rnds_client.rira`):

| Exceção                | Quando                                                                                              | Atributos                       |
|-----------------------|--------------------------------------------------------------------------------------------------|---------------------------------|
| `ErroRiraTransitorio` | Timeout/DNS/conexão antes da resposta; HTTP `408`, `429`, `5xx`. Vale re-tentar.                    | `codigo`, `retry_after \| None`  |
| `ErroRiraRejeitado`   | HTTP `4xx` funcional; invariante local violada (`codigo="completude"`). Não adianta re-tentar igual. | `codigo`, `http_status \| None`  |
| `ResultadoRiraIncerto`| POST enviado mas resposta perdida (timeout/queda após o POST, ou aceite sem `Location` nem corpo). Concilie por `identifier` antes de reenviar. | `codigo`                        |

`RndsSubmissionError` e `RiraValidationError` seguem reexportadas em `rnds_client`
(a segunda é a exceção crua do validator, vista só via `dump_bundle_json`).

---

## Atualização de versão

Contrato **`0.3.0`** — *stateless*. Mudanças em relação à `0.2.0` (nunca
integrada por nenhum consumidor) e o passo a passo estão em
[`docs/rira-evolucao-0.3.0.md`](../../../docs/rira-evolucao-0.3.0.md). Changelog:
[README, seção "Versão"](../../../README.md#versao).
