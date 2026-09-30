# RIRA — evolução 0.3.4

## CBO em documentos cancelados

O evento `cancelled` gera `ServiceRequest.status=revoked` e
`Appointment.status=cancelled`. Nesse estado, CBO é opcional também nos
grupos SIGTAP 03/04. A origem deve mapear explicitamente cancelamento ou
negativa para esse evento.

Sem CBO, os campos `ServiceRequest.performerType` e `Appointment.specialty`
não são serializados. Se informado, o código é preservado nos dois
recursos. O Bundle mantém Composition, Appointment, ServiceRequest e
Condition; substituições mantêm `Composition.relatesTo.code=replaces`.

Os demais eventos continuam exigindo CBO para procedimentos 03/04:
`pending`, `booked`, `attended`, `absence` e `returned-to-requester`.
A dispensa não altera as regras de datas, identificação, consulta,
comparação clínica, tratamento de rejeição ou resultado incerto.

## Evidência e limite

A exceção foi solicitada pelo integrador após um teste em homologação:
três cancelamentos do grupo 03 sem CBO foram aceitos com HTTP 201 e
recuperados por consulta. Outros dois casos retornaram HTTP 500 (grupo 04)
e HTTP 422 (grupo 03), sem referência a CBO no diagnóstico capturado.
Esse teste não confirma aceitação de todos os procedimentos ou uma
exceção oficial geral; respostas remotas continuam sendo tratadas.

Esta versão é stateless e não exige migrações. Atualize o pacote em todos
os processos do integrador antes de habilitar a nova regra. O contrato
anterior permanece em [rira-evolucao-0.3.3.md](rira-evolucao-0.3.3.md).
