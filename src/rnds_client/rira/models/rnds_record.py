from __future__ import annotations

from django.db import models


class RNDSDocumentRecord(models.Model):
    id_local = models.CharField(max_length=100, unique=True)
    id_rnds = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=30, null=True, blank=True)
    erro = models.TextField(null=True, blank=True)
    enviado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "rnds_rira"
        verbose_name = "Registro RNDS"
        verbose_name_plural = "Registros RNDS"

    def __str__(self) -> str:
        return f"{self.id_local} → {self.id_rnds or 'pendente'}"
