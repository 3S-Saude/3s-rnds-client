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

## Uso rapido

```python
from rnds_client import RndsClient


async def buscar_paciente(identificador: str):
    async with await RndsClient.create() as client:
        return await client.pacientes.buscar_pessoa(identificador)
```

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

## Configuracao no Django

O pacote usa o cache padrao do Django para armazenar o token RNDS. Antes de usar o client, garanta que o projeto tenha `CACHES` configurado.

Exemplo de variaveis de ambiente:

```env
RNDS_API_URL=https://rn-ehr-services.saude.gov.br/api/
RNDS_AUTH_TOKEN_URL=https://ehr-auth.saude.gov.br/api/
RNDS_CNS_GESTOR=
```

Para compatibilidade com configuracoes legadas, a biblioteca tambem aceita `CNS_SEC_SAUDE`.

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

Metodos de pacientes:

- `client.pacientes.buscar_pessoa(identificador)`
- `client.pacientes.buscar_pessoa_debug(identificador, force_refresh_token=True)`

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
