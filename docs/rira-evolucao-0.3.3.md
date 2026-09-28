# RIRA 0.3.3 — resultado incerto e diagnóstico seguro

Esta versão mantém o Bundle e a consulta da `0.3.2`.

## Resposta ao POST

- HTTP `408` ou `5xx` recebido após a tentativa de POST não prova que a RNDS
  deixou de gravar o documento. O cliente devolve `ResultadoRiraIncerto` com
  `codigo=http_<status>` e `http_status`; o integrador deve consultar pelo
  identificador local antes de decidir sobre outro POST.
- HTTP `429` continua transitório e preserva `Retry-After`. Erros de conexão
  comprovadamente anteriores ao POST também continuam transitórios.
- A consulta de conciliação deve comparar identificador, conteúdo e predecessor;
  uma resposta vazia isolada não comprova ausência definitiva quando a RNDS
  ainda estiver processando o documento.

## Rejeições FHIR

Para respostas `OperationOutcome` de rejeição, `ErroRiraRejeitado` expõe
`codigo_fhir` apenas quando `issue.code` pertence à lista controlada e
`campo_fhir` apenas quando `issue.expression` é um caminho de recurso FHIR
validado. `issue.diagnostics`, `details.text` e o corpo bruto não são incluídos
nesses campos. Eles podem conter dados clínicos e não devem ser copiados para
logs ou APIs de acompanhamento. Quando a RNDS não informa um
`OperationOutcome` utilizável, os campos adicionais ficam vazios e o código
HTTP permanece disponível.
