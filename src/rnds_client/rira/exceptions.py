from __future__ import annotations


class RiraValidationError(ValueError):
    pass


class RndsSubmissionError(RuntimeError):
    pass


class ErroRiraTransitorio(RuntimeError):

    def __init__(self, mensagem: str, *, codigo: str, retry_after: int | None = None) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.retry_after = retry_after


class ErroRiraRejeitado(RuntimeError):

    def __init__(
        self,
        mensagem: str,
        *,
        codigo: str,
        http_status: int | None = None,
        codigo_fhir: str | None = None,
        campo_fhir: str | None = None,
    ) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.http_status = http_status
        self.codigo_fhir = codigo_fhir
        self.campo_fhir = campo_fhir


class ResultadoRiraIncerto(RuntimeError):

    def __init__(self, mensagem: str, *, codigo: str, http_status: int | None = None) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.http_status = http_status
