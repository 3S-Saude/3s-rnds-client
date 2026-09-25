# RIRA 0.3.2: estados e conciliação detalhada

Esta versão acrescenta os estados `absence` e `cancelled` ao Bundle RIRA. `absence` produz `Appointment.noshow` e `ServiceRequest.completed`; `cancelled` produz `Appointment.cancelled` e `ServiceRequest.revoked`. `returned-to-requester` continua `Appointment.waitlist`/`ServiceRequest.on-hold` e não deve representar uma devolução pelo prestador.

`consultar_rira(system, value)` consulta o identificador local e obtém o Bundle de cada candidato. O resultado contém `status_rira`, `predecessor_composition_id` e `dados_clinicos` normalizados, além dos IDs. O consumidor deve comparar o conteúdo e a relação `replaces` antes de confirmar uma resposta de POST incerta. Múltiplos candidatos ou documentos incompletos exigem análise.

Uma `Location` versionada (`.../Bundle/<id>/_history/<versão>`) preserva o ID do Bundle na consulta, sem alterar a URL original no resultado. Códigos de SIGTAP, CID-10, CBO, modalidade e estado são extraídos pelo `coding.system` esperado; sistema ausente ou códigos conflitantes para o mesmo sistema produzem `None`, impedindo confirmação automática indevida.

Em `dados_clinicos`, `appointment_start` e `appointment_end` são os valores efetivamente serializados no `Appointment`: eles não identificam se a origem foi agendamento, autorização ou atendimento. `observacao` contém o texto de `Condition.note`, inclusive o padrão `Sem observações` quando nenhuma observação foi informada. O consumidor deve comparar esses valores com a projeção FHIR do snapshot, sem expor a observação em logs ou respostas operacionais.

Depois de um POST aceito, o cliente exige ID do Bundle ou `Location` e ID da Composition. Se a Composition não constar da resposta, consulta o documento; se continuar ausente, levanta `ResultadoRiraIncerto` com código `composition_id_ausente`.

O mapeamento foi confrontado com os exemplos 07 (falta), 09 (negado), 11–13 (cadeia de substituições) fornecidos pelo DATASUS e com o guia de implementação RIRA 1.0.0. Exclusão permanece uma operação explícita de documento e não equivale a `cancelled`.
