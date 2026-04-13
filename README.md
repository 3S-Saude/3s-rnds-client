# 3s-rnds-client

`3s-rnds-client` e uma biblioteca Python assincrona para integracao com a RNDS em aplicacoes Django.

O pacote foi estruturado para publicacao no `pip`, com layout `src/`, metadata em `pyproject.toml` e namespace proprio em `rnds_client`.

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

## Estrutura do pacote

```text
src/rnds_client/
├── auth.py
├── base_client.py
├── capabilities/
├── client.py
├── exceptions.py
├── parsers.py
├── settings.py
└── tokens.py
```

## Uso rapido

```python
from rnds_client import RndsClient


async def buscar_paciente(identificador: str):
    async with await RndsClient.create() as client:
        return await client.pacientes.buscar_pessoa(identificador)
```

## Configuracao no Django

O pacote usa o cache padrao do Django para armazenar o token RNDS. Antes de usar o client, garanta que o projeto tenha `CACHES` configurado.

Exemplo de variaveis de ambiente:

```env
RNDS_API_URL=https://rn-ehr-services.saude.gov.br/api/
RNDS_AUTH_TOKEN_URL=https://ehr-auth.saude.gov.br/api/
CNS_SEC_SAUDE=
```

### Modo CERT

```env
RNDS_AUTH_METHOD=CERT
RNDS_CERT=/caminho/para/cert.pem
RNDS_KEY=/caminho/para/key.pem
```

### Modo API

```env
RNDS_AUTH_METHOD=API
RNDS_AUTH_LOGIN_URL=https://api-intermediaria.exemplo/login
RNDS_AUTH_TOKEN_URL=https://api-intermediaria.exemplo/token
RNDS_USER=usuario
RNDS_PASSWORD=senha
```

Se `RNDS_AUTH_METHOD` nao for informado, o pacote escolhe `API` quando houver `RNDS_USER` ou `RNDS_PASSWORD`; caso contrario, usa `CERT`.

## API publica

O ponto de entrada principal continua sendo `RndsClient`, com capacidades expostas por dominio:

- `client.pacientes`
- `client.estabelecimentos`
- `client.rira`

Uso explicito da infraestrutura base:

```python
from httpx import AsyncClient

from rnds_client.base_client import RndsBaseClient
from rnds_client.client import RndsClient
from rnds_client.settings import RndsSettings


async def criar_client_manual():
    settings = RndsSettings.from_environment()
    base_client = RndsBaseClient(settings=settings, http_client=AsyncClient())
    return RndsClient(base_client=base_client)
```

## Tratamento de erros

As excecoes proprias do pacote sao:

- `RndsConfigurationError`
- `RndsAuthenticationError`

Chamadas HTTP tambem podem propagar erros do `httpx`.
