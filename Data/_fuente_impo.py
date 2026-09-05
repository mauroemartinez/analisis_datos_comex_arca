# -*- coding: utf-8 -*-
"""
Ubica que Parquet usar para consultas rapidas.

El pipeline ahora deja un solo archivo consolidado, Data/impo_historico.parquet,
y borra los impo_YYYYMM.parquet mensuales apenas quedan incorporados a el (ver
--keep-mensuales en descargar_historico_impo.py si se quieren conservar). Esta
funcion soporta ambos casos: si todavia hay algun impo_YYYYMM.parquet suelto
en Data/ (por ejemplo, un mes recien descargado que no se fusiono todavia), lo
usa; si no, cae al historico consolidado.
"""
from __future__ import annotations

import glob
import os
import re


def ubicar_fuente(here: str) -> tuple[str | None, bool]:
    """Devuelve (ruta_parquet, es_historico).

    ruta_parquet usa '/' (no barra invertida) para que duckdb y polars la
    acepten igual en Windows sin tener que escapar nada.
    """
    candidatos = glob.glob(os.path.join(here, "impo_*.parquet"))
    candidatos = [
        p for p in candidatos
        if re.fullmatch(r"impo_\d{6}\.parquet", os.path.basename(p))
    ]
    if candidatos:
        path = sorted(candidatos, key=lambda p: os.path.basename(p))[-1]
        return path.replace("\\", "/"), False

    historico = os.path.join(here, "impo_historico.parquet")
    if os.path.exists(historico):
        return historico.replace("\\", "/"), True
    return None, False
