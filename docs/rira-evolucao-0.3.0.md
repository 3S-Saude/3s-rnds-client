# 3s-rnds-client 0.3.0 — contrato RIRA (para o gerenciamento diário)

O consumidor passou a ser **dono da
identidade e da cadeia de substituição** RIRA (`RiraDocumento` / `RiraEnvioDocumento`,
tentativa imutável, auditoria, conciliação). A lib 0.2.0 resolvia a substituição
sozinha via tabela local e devolvia só uma `str` truncada do `Location`, o que:

- criava **dupla fonte de verdade** (tabela da lib × modelos do core);
- **deduzia** o id da `Composition` truncando a URL do Bundle — inseguro: o manual
  RNDS mostra sufixos distintos (`...-i0b0` no Bundle, `...-c0m1` na Composition);
- não classificava erro (transitório / rejeitado / incerto);
- não oferecia consulta por `(identifier.system, identifier.value)` — pilar do
  fluxo anti-duplicidade em resposta perdida;
- logava o Bundle FHIR inteiro em `DEBUG` (CPF/CNS, CID-10, texto clínico).

## O que mudou

| Área | 0.2.0 | 0.3.0 |
|---|---|---|
| API de envio | `criar_documento_{pending,booked,attended,returned_to_requester}(dados) -> str` (removida) | `enviar_rira(dados, identificador_local, *, status_rira, identifier_system=None, predecessor_composition_id=None) -> ResultadoEnvioRira` |
| Consulta | `get_documento(id_rnds) -> dict` | `+ consultar_rira(identifier_system, identifier_value) -> list[ResultadoEnvioRira]` (404 → `[]`, sem os 5 retries) |
| Retorno | `str` (último segmento do `Location`) | `ResultadoEnvioRira(http_status, location_rnds` **bruto**`, id_rnds_bundle, id_rnds_composition, ...)` — ids **distintos**, lidos da resposta FHIR (com *fallback* `GET Bundle/{id}` para extrair a Composition) |
| Substituição | resolvida pela lib via `RNDSDocumentRecord` | `predecessor_composition_id` **explícito**; `Composition.from_rira(..., predecessor_composition_id)` |
| Estado local | app Django `rnds_client.rira` + `RNDSDocumentRecord` + migração | **removidos** — lib *stateless* |
| Erros | `httpx.*` cru / `RiraValidationError` embrulhado em `pydantic.ValidationError` | `ErroRiraTransitorio(codigo, retry_after)`, `ErroRiraRejeitado(codigo, http_status)`, `ResultadoRiraIncerto(codigo)` — ver `sender.classificar_erro_http` |
| Naming System | só via env `RIRA_NAMING_SYSTEM_ID` | env **ou** `identifier_system=` por chamada (`RiraFhirSettings.bundle_id_system_override`) |
| Log | Bundle + `response.text` + headers crus em `DEBUG` | só `method`, `url`, `body_len`, `status`, `location` |

### Classificação de erro (`sender.classificar_erro_http`)

- `ReadTimeout`/`ConnectTimeout`/`WriteTimeout`/`PoolTimeout` antes da resposta → `ErroRiraTransitorio(codigo="timeout")`; **após** o POST (`apos_post=True`) → `ResultadoRiraIncerto(codigo="resposta_perdida")`.
- `HTTPStatusError` 408/429/500/502/503/504 → `ErroRiraTransitorio(codigo="http_<status>", retry_after=<Retry-After>)`.
- Demais 4xx / `OperationOutcome` de erro → `ErroRiraRejeitado(codigo="http_4xx", http_status=<status>)`.
- `RiraValidationError` (CBO grupo 03/04, datas de Appointment) → `ErroRiraRejeitado(codigo="completude")`.
- `ConnectError`/`TransportError`/`RemoteProtocolError` → `ErroRiraTransitorio(codigo="conexao")`.

## Integração do consumidor

1. `pip install 3s-rnds-client>=0.3.0` (ou o checkout editável desta branch).
2. Garantir que `"rnds_client.rira"` **não** está em `INSTALLED_APPS` (a lib não é
   mais app Django). Se a `0.2.0` chegou a ser instalada, `DROP TABLE
   rnds_rira_rndsdocumentrecord` e limpar `django_migrations` do app `rnds_rira`.
3. Chamar `enviar_rira(dados, identificador_local, status_rira=...)` e, na
   substituição, passar `predecessor_composition_id` = o `id_rnds_composition` do
   último envio confirmado (**não** o id do Bundle).
4. Tratar as três exceções normalizadas na máquina de estados.

## Pendências (registrar antes de produção)

- **Fonte primária dos ids na resposta do POST**: confirmar no barramento RNDS se
  o `POST /Bundle` type=`document` devolve corpo com `Bundle.id` + `Composition.id`
  ou só o header `Location`. O *fallback* `GET Bundle/{id}` cobre os dois, mas a
  fonte primária precisa ser confirmada em homologação.
- **RIRA × MIRA**, versão/URL do modelo informacional e do profile computacional
  vigente, valor definitivo do Naming System, e aceitação de cadeia com mais de
  uma substituição — pré-requisitos de liberação, não valores a inventar no código.
- Verificação de profile FHIR contra as `StructureDefinition` continua fora da lib;
  homologação RNDS é a validação real.
