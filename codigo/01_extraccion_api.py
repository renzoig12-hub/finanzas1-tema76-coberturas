# Autor: Renzo Jhonel Ignacio Paucar
# Código de matrícula: 2024200504J
# Tema N.° 76 (Unidad II): Oro, cobre y renta fija soberana como coberturas en un portafolio peruano
# Fecha de extracción: 2026-11-22

"""
VÍA 1 - API.
(a) API REST del BCRP (BCRPData): índice bursátil, oro, cobre, rendimiento soberano,
    tipo de cambio y EMBIG Perú, en frecuencia diaria.
(b) Yahoo Finance mediante la librería yfinance: futuros de oro (GC=F) y cobre (HG=F).
Guarda los datos sin modificar en datos_crudos/ y registra cada pedido en log_ejecucion.txt.
Ejecutar desde la carpeta principal:  python codigo/01_extraccion_api.py
"""

import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

# ---------- 1. Parámetros congelados ----------
CODIGO_MATRICULA = "2024200504J"
FECHA_INICIO = "2012-01-01"
FECHA_CORTE = "2025-12-31"
FIN_YAHOO = "2026-01-01"      # yfinance excluye la fecha final: así el último día es 2025-12-31

SERIES_BCRP = {                       # código BCRP -> nombre corto
    "PD38026MD": "igbvl",             # Índice General Bursátil BVL (puntos)
    "PD04704XD": "oro_usd",           # Oro, Londres (US$ por onza troy)
    "PD04701XD": "cobre_cusd_lb",     # Cobre, Londres (centavos de US$ por libra)
    "PD31893DD": "rend_bono10_pen",   # Rendimiento del bono soberano a 10 años en S/ (%)
    "PD04638PD": "tc_pen_usd",        # TC interbancario venta (S/ por US$)
    "PD04709XD": "embig_pe",          # Spread EMBIG Perú (puntos básicos)
}
TICKERS_YAHOO = {                     # ticker -> nombre corto
    "GC=F": "oro_fut_usd",            # futuro de oro, COMEX (US$ por onza troy)
    "HG=F": "cobre_fut_usd_lb",       # futuro de cobre, COMEX (US$ por libra)
}
URL_BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
CABECERAS = {"User-Agent": f"UNCP-Finanzas1-Tema76 (estudiante {CODIGO_MATRICULA}; uso academico)"}
PAUSA_SEG = 1.5

# ---------- 2. Rutas relativas (nada de C:\Users\...) ----------
PROYECTO = Path(__file__).resolve().parent.parent   # carpeta que contiene a /codigo
CRUDOS = PROYECTO / "datos_crudos"
LOG = PROYECTO / "log_ejecucion.txt"
CRUDOS.mkdir(exist_ok=True)

def escribir_log(mensaje):
    """Escribe una línea con fecha y hora de Lima en pantalla y en el log."""
    ahora = datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ahora}] {mensaje}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")

# ---------- 3. BCRP: una serie por pedido ----------
escribir_log("=== Inicio 01_extraccion_api.py (BCRP API + Yahoo Finance) ===")
filas = []
for codigo, nombre in SERIES_BCRP.items():
    url = f"{URL_BASE}/{codigo}/json/{FECHA_INICIO}/{FECHA_CORTE}"
    respuesta = requests.get(url, headers=CABECERAS, timeout=60)
    try:
        datos = respuesta.json()
    except ValueError:
        escribir_log(f"ERROR {codigo}: HTTP {respuesta.status_code}, no devolvió JSON -> {respuesta.text[:150]}")
        continue
    for periodo in datos["periods"]:
        filas.append({
            "periodo": periodo["name"],          # fecha tal cual (ej. 02.Ene.12)
            "codigo_serie": codigo,
            "nombre_corto": nombre,
            "valor": periodo["values"][0],       # texto tal cual (incluye "n.d.")
        })
    escribir_log(f"{codigo} ({nombre}) | HTTP {respuesta.status_code} | {len(datos['periods'])} días | {url}")
    time.sleep(PAUSA_SEG)   # pausa entre pedidos

tabla_bcrp = pd.DataFrame(filas)
archivo_bcrp = CRUDOS / f"datos_crudos_bcrp_{CODIGO_MATRICULA}.csv"
tabla_bcrp.to_csv(archivo_bcrp, index=False, encoding="utf-8")
escribir_log(f"Guardado {archivo_bcrp.name} | filas: {len(tabla_bcrp)}")

# ---------- 4. Yahoo Finance: un ticker por pedido ----------
tablas_yahoo = []
for ticker, nombre in TICKERS_YAHOO.items():
    df = yf.download(ticker, start=FECHA_INICIO, end=FIN_YAHOO, auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):       # versiones nuevas: columnas en 2 niveles
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df.insert(1, "ticker", ticker)
    df.insert(2, "nombre_corto", nombre)
    tablas_yahoo.append(df)
    # yfinance no expone el código HTTP: se registra como n/d (no disponible)
    escribir_log(f"{ticker} ({nombre}) | HTTP n/d (yfinance {yf.__version__}) | {len(df)} días")
    time.sleep(PAUSA_SEG)

tabla_yahoo = pd.concat(tablas_yahoo, ignore_index=True)
archivo_yahoo = CRUDOS / f"datos_crudos_yahoo_{CODIGO_MATRICULA}.csv"
tabla_yahoo.to_csv(archivo_yahoo, index=False, encoding="utf-8")
escribir_log(f"Guardado {archivo_yahoo.name} | filas: {len(tabla_yahoo)}")
escribir_log("=== Fin 01_extraccion_api.py ===")
