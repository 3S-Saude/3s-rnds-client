# 3s-rnds-client

`3s-rnds-client` e uma biblioteca Python assincrona para integracao com a RNDS em aplicacoes Django.

## Instalacao

```bash
pip install 3s-rnds-client
```

## Visao geral

O cliente concentra a infraestrutura comum de:

- autenticacao `CERT` e `API`
- cache de token RNDS usando o cache configurado do Django
- transporte HTTP assincrono com `httpx`
- retry automatico em falhas transientes
- organizacao por capacidades de dominio
- envio e consulta de documentos RIRA (Registro de Informacoes da Regulacao Assistencial)

## Uso rapido

```python
from rnds_client import RndsClient


async def buscar_paciente(identificador: str):
    async with await RndsClient.create() as client:
        return await client.pacientes.buscar_pessoa(identificador)
```

### Verificacao

Com as variaveis de ambiente configuradas, `RndsClient.create()` sem erro ja
indica que autenticacao e configuracao estao ok. Para um teste ponta a ponta,
chame `buscar_pessoa` com um CPF (11 digitos) ou CNS conhecido: o retorno e um
`dict` normalizado (`nome`, `cns`, `cpf`, `data_nascimento`, `sexo`, ...), ou
`None` se a RNDS nao encontrar a pessoa.

## Modo debug

Para diagnosticar problemas de autenticacao e de consumo da API da RNDS, use `buscar_pessoa_debug`.
O metodo imprime no terminal do servidor o passo a passo do processo, incluindo:

- variaveis e configuracoes relevantes do fluxo
- identificador normalizado e URL final da busca
- leitura do cache de token
- autenticacao `API` ou `CERT`
- headers enviados
- status e corpo das respostas HTTP
- retries e payload final formatado

Exemplo de uso:

```python
from rnds_client import RndsClient


async def buscar_paciente_debug(identificador: str):
    async with await RndsClient.create() as client:
        return await client.pacientes.buscar_pessoa_debug(identificador)
```

Por padrao, `buscar_pessoa_debug` usa `force_refresh_token=True` para forcar a autenticacao e exibir o fluxo completo.
Se quiser reproduzir o comportamento padrao da biblioteca tentando reutilizar o token em cache, passe `force_refresh_token=False`.

```python
from rnds_client import RndsClient


async def buscar_paciente_debug_com_cache(identificador: str):
    async with await RndsClient.create() as client:
        return await client.pacientes.buscar_pessoa_debug(
            identificador,
            force_refresh_token=False,
        )
```

Os logs do modo debug mascaram parcialmente tokens e senha antes de exibi-los.

Alem disso, `RndsBaseClient` emite logs de nivel `DEBUG` (logger
`rnds_client.base_client`) com o request e o response de toda chamada a RNDS.
Os headers `Authorization` e `X-Authorization-Server` sao mascarados como `***`.

```python
import logging

logging.getLogger("rnds_client.base_client").setLevel(logging.DEBUG)
```

## Configuracao no Django

O pacote usa o cache padrao do Django para armazenar o token RNDS. Antes de usar o client, garanta que o projeto tenha `CACHES` configurado.

A biblioteca le estas variaveis do ambiente do processo — defina-as como preferir (`.env` do seu projeto, secrets de CI, `export`...):

```env
# RNDS base
RNDS_API_URL=
RNDS_AUTH_TOKEN_URL=
RNDS_CNS_GESTOR=

# Auth CERT
RNDS_CERT=
RNDS_KEY=

# Auth API
RNDS_AUTH_LOGIN_URL=
RNDS_USER=
RNDS_PASSWORD=

# RIRA (so com rnds_client.rira)
RIRA_NAMING_SYSTEM_ID=
RIRA_COMP_PROFILE=
RIRA_SR_PROFILE=
RIRA_APP_PROFILE=
RIRA_COND_PROFILE=
```

- `RNDS_API_URL` e `RNDS_AUTH_TOKEN_URL` sao sempre obrigatorias. `RNDS_CNS_GESTOR` e opcional (aceita tambem `CNS_SEC_SAUDE`, por compatibilidade).
- Autenticacao: use o bloco **CERT** (`RNDS_CERT`, `RNDS_KEY`) ou o bloco **API** (`RNDS_AUTH_LOGIN_URL`, `RNDS_USER`, `RNDS_PASSWORD`).
- Sem `RNDS_AUTH_METHOD`, o pacote escolhe `API` quando houver `RNDS_USER` ou `RNDS_PASSWORD`; caso contrario, `CERT`.
- As `RIRA_*` so sao lidas se voce usar `rnds_client.rira`; o que cada uma faz esta em [src/rnds_client/rira/README.md](src/rnds_client/rira/README.md#variáveis-de-ambiente).

## RIRA (Registro de Informacoes da Regulacao Assistencial)

O modulo `rnds_client.rira` envia a RNDS o andamento de uma solicitacao regulada:
a cada mudanca de status (`pending` -> `booked` -> `attended`, ou
`returned-to-requester`), monta um documento FHIR a partir de um `RiraDocumentData`
e faz um `POST`.

**Configuracao:** so as variaveis de ambiente `RIRA_*` (bloco `RIRA` da secao
[Configuracao no Django](#configuracao-no-django)).

**O estado fica com quem chama.** Como o modulo nao persiste nada, o consumidor
guarda o identificador local da solicitacao e os ids que a RNDS devolve; em cada
atualizacao de status, informa qual documento esta sendo substituido
(`predecessor_composition_id`).

Setup, uso, campos e regras: **[src/rnds_client/rira/README.md](src/rnds_client/rira/README.md)**.

## API publica

O ponto de entrada principal continua sendo `RndsClient`, com capacidades expostas por dominio:

- `client.pacientes`
- `client.estabelecimentos`
- `client.rira`

Metodos de pacientes:

- `client.pacientes.buscar_pessoa(identificador)`
- `client.pacientes.buscar_pessoa_debug(identificador, force_refresh_token=True)`

Metodos de RIRA: `enviar_rira` / `consultar_rira`, `get_documento`,
`deletar_documento`, `dump_bundle_json` — ver
[src/rnds_client/rira/README.md](src/rnds_client/rira/README.md#api-clientrira).

Uso explicito da infraestrutura base:

```python
from httpx import AsyncClient

from rnds_client.base_client import RndsBaseClient
from rnds_client.client import RndsClient
from rnds_client.settings import RndsSettings


async def criar_client_manual():
    settings = RndsSettings.from_environment()
    http_client = AsyncClient(timeout=120.0)
    base_client = RndsBaseClient(settings=settings, http_client=http_client)
    return RndsClient(base_client=base_client)
```

Clientes HTTP injetados manualmente mantem a configuracao definida pelo consumidor.
O cliente criado por `RndsClient.create()` usa 120 segundos para conexao, leitura,
escrita e espera por conexao disponivel.

## Tratamento de erros

As excecoes proprias do pacote sao:

- `RndsConfigurationError`
- `RndsAuthenticationError`
- Do modulo RIRA, `enviar_rira` converte qualquer falha em um destes tres erros:
  - `ErroRiraTransitorio` — timeout, erro de conexao ou HTTP 408/429/5xx; vale
    re-tentar (traz `retry_after` quando a RNDS informa).
  - `ErroRiraRejeitado` — HTTP 4xx funcional ou invariante local violada;
    re-tentar igual nao resolve.
  - `ResultadoRiraIncerto` — o `POST` foi feito mas a resposta se perdeu; concilie
    por `identifier` antes de reenviar.

  `RndsSubmissionError` e `RiraValidationError` continuam exportadas, mas so
  aparecem fora do fluxo de `enviar_rira` (ex.: `RiraValidationError` sobe como
  `pydantic.ValidationError` ao usar `dump_bundle_json`). Detalhes em
  [Tratamento de erros](src/rnds_client/rira/README.md#tratamento-de-erros).

Chamadas HTTP tambem podem propagar erros do `httpx`.

## Versao

Versao atual: `0.3.0` (contrato RIRA *stateless* — ver
[docs/rira-evolucao-0.3.0.md](docs/rira-evolucao-0.3.0.md)).

- Novo modulo/app `rnds_client.rira` para envio e consulta de documentos RIRA.
- Nova dependencia: `pydantic>=2.0` (schemas FHIR).
- `RndsBaseClient` passa a logar request/response em nivel `DEBUG` (com headers sensiveis mascarados).
- Novos simbolos em `rnds_client`: `RiraDocumentData`, `RiraFhirSettings`, `RiraValidationError`, `RndsSubmissionError`.
- `rnds_client.__version__` realinhado para `0.2.0`.

Ao atualizar de `0.1.x`: rode `pip install -U 3s-rnds-client` (o `pydantic` vem
junto). Quem usa apenas `client.pacientes` / `client.estabelecimentos` nao
precisa de mais nada; para habilitar o RIRA, siga a secao
[RIRA](#rira-registro-de-informacoes-da-regulacao-assistencial).

## Desenvolvimento

### Ambiente e testes

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .          # instala o pacote + django, httpx, pydantic
python -m unittest discover -s tests -v
```

A suite usa `unittest` (nao ha `pytest` nas dependencias) e nao precisa de
`DJANGO_SETTINGS_MODULE` — nenhum modulo do pacote depende do ORM.

### Estrutura do pacote

- `src/rnds_client/` — cliente base: `base_client`, `auth`, `tokens`, `settings`, `parsers`, `client`.
- `src/rnds_client/capabilities/` — uma capability por arquivo (`patients.py`, `establishments.py`, `rira.py`), exposta em `RndsClient` como `client.pacientes` / `client.estabelecimentos` / `client.rira`.
- `src/rnds_client/<nome>/` — quando a capability tem lógica própria além da chamada HTTP, vira um subpacote com `schemas/`, `services/` e `README.md` (ver `rnds_client.rira`). O pacote é *stateless* — sem `models/`/`migrations/`.


### Versao e publicacao

- SemVer. `version` em `pyproject.toml` e `rnds_client.__version__` devem casar.
- A publicacao no PyPI e automatica no merge do PR em `main` (`.github/workflows/publish.yml`).
