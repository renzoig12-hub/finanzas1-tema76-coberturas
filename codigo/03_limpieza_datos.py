# Autor: Renzo Jhonel Ignacio Paucar
# Código de matrícula: 2024200504J
# Tema N.° 76 (Unidad II): Oro, cobre y renta fija soberana como coberturas en un portafolio peruano
# Fecha de extracción: 2026-11-22 (BCRP, Yahoo) y 2026-11-25 (SBS)

"""
LIMPIEZA Y UNIÓN DE DATOS. Funciona sin internet: solo lee datos_crudos/.
1. BCRP: fechas "02.Ene.12" -> fecha; "n.d." -> vacío (NaN), sin rellenar.
2. Yahoo: precio de cierre (Close; en futuros es igual a Adj Close).
3. SBS: tasas cupón cero en decimal -> porcentaje (x100).
4. Valores atípicos aislados (un solo día que cae y al día siguiente vuelve): se marcan como
   vacío en los datos procesados, con regla objetiva (ver UMBRAL_ATIPICO). El crudo no se toca.
5. Muestra común: días con IGBVL, oro, cobre, tipo de cambio y tasa SBS 10 años en soles.
   Los retornos se calculan entre días consecutivos de esa muestra (no se inventa ningún precio).
6. Guarda datos_procesados/datos_procesados_2024200504J.csv (y una copia .xlsx para Excel).
Ejecutar desde la carpeta principal:  python codigo/03_limpieza_datos.py
"""

import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# ---------- 1. Parámetros congelados ----------
CODIGO_MATRICULA = "2024200504J"
FECHA_INICIO = "2012-01-01"
FECHA_CORTE = "2025-12-31"
MESES_BCRP = {"Ene": "01", "Feb": "02", "Mar": "03", "Abr": "04", "May": "05", "Jun": "06",
              "Jul": "07", "Ago": "08", "Set": "09", "Oct": "10", "Nov": "11", "Dic": "12"}
SBS_ARCHIVOS = {   # nombre de variable -> (moneda en el nombre del archivo, plazo en días)
    "tasa_cc10a_pen_sbs": ("soles", "3600"),
    "tasa_cc5a_pen_sbs": ("soles", "1800"),
    "tasa_cc10a_usd_sbs": ("dolares", "3600"),
    "tasa_cc5a_usd_sbs": ("dolares", "1800"),
}
NUCLEO = ["igbvl", "oro_usd", "cobre_cusd_lb", "tc_pen_usd", "tasa_cc10a_pen_sbs"]
PRECIOS_REVISAR = ["igbvl", "oro_usd", "cobre_cusd_lb", "tc_pen_usd", "oro_fut_usd", "cobre_fut_usd_lb"]
UMBRAL_ATIPICO = 15.0   # % : el día cae (o sube) más de 15 % y al día siguiente se revierte más de 15 %
REVERSION_MAX = 2.0     # % : y la suma de ambos retornos es menor a 2 % (vuelve casi al mismo nivel)

# ---------- 2. Rutas relativas ----------
PROYECTO = Path(__file__).resolve().parent.parent
CRUDOS = PROYECTO / "datos_crudos"
PROCESADOS = PROYECTO / "datos_procesados"
LOG = PROYECTO / "log_ejecucion.txt"
PROCESADOS.mkdir(exist_ok=True)

def escribir_log(mensaje):
    """Escribe una línea con fecha y hora de Lima en pantalla y en el log."""
    ahora = datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ahora}] {mensaje}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")

def ret_log(serie):
    """Retorno logarítmico en porcentaje entre filas consecutivas."""
    return 100 * np.log(serie).diff()

def atipicos_aislados(serie):
    """Fechas de valores aislados: salto mayor al umbral que se revierte al día siguiente."""
    valida = serie.dropna()
    r = ret_log(valida)
    r_sig = r.shift(-1)
    marca = ((r.abs() > UMBRAL_ATIPICO) & (r_sig.abs() > UMBRAL_ATIPICO)
             & (np.sign(r) != np.sign(r_sig)) & ((r + r_sig).abs() < REVERSION_MAX))
    return valida.index[marca]

escribir_log("=== Inicio 03_limpieza_datos.py (sin conexión: solo datos_crudos/) ===")

# ---------- 3. BCRP ----------
bcrp = pd.read_csv(CRUDOS / f"datos_crudos_bcrp_{CODIGO_MATRICULA}.csv", dtype=str)
partes = bcrp["periodo"].str.split(".", expand=True)
bcrp["fecha"] = pd.to_datetime(partes[0] + "-" + partes[1].map(MESES_BCRP) + "-20" + partes[2],
                               format="%d-%m-%Y", errors="raise")
bcrp["valor_num"] = pd.to_numeric(bcrp["valor"].replace("n.d.", np.nan), errors="raise")
ancho_bcrp = bcrp.pivot(index="fecha", columns="nombre_corto", values="valor_num")
escribir_log(f"BCRP: {ancho_bcrp.shape[0]} días x {ancho_bcrp.shape[1]} series | "
             f"n.d. por serie: {ancho_bcrp.isna().sum().to_dict()}")

# ---------- 4. Yahoo ----------
yahoo = pd.read_csv(CRUDOS / f"datos_crudos_yahoo_{CODIGO_MATRICULA}.csv")
yahoo["fecha"] = pd.to_datetime(yahoo["Date"], format="%Y-%m-%d")
ancho_yahoo = yahoo.pivot(index="fecha", columns="nombre_corto", values="Close")
escribir_log(f"Yahoo: {ancho_yahoo.shape[0]} días x {ancho_yahoo.shape[1]} series | "
             f"Close igual a Adj Close: {bool((yahoo['Close'] == yahoo['Adj Close']).all())}")

# ---------- 5. SBS ----------
series_sbs = {}
for nombre, (moneda, plazo) in SBS_ARCHIVOS.items():
    t = pd.read_csv(CRUDOS / "sbs" / f"datos_crudos_sbs_{moneda}_{plazo}d_{CODIGO_MATRICULA}.csv", dtype=str)
    series_sbs[nombre] = pd.Series(pd.to_numeric(t["Tasa (%)"], errors="raise").values * 100,
                                   index=pd.to_datetime(t["Fecha"], format="%d/%m/%Y"))
ancho_sbs = pd.DataFrame(series_sbs)
ancho_sbs.index.name = "fecha"
escribir_log(f"SBS: {ancho_sbs.shape[0]} días x {ancho_sbs.shape[1]} series (decimal x100 -> %)")

# ---------- 6. Unión por fecha (calendario base: BCRP) ----------
for nombre, t in [("BCRP", ancho_bcrp), ("Yahoo", ancho_yahoo), ("SBS", ancho_sbs)]:
    if t.index.duplicated().any():
        raise ValueError(f"{nombre}: hay fechas repetidas")
datos = ancho_bcrp.join(ancho_yahoo, how="left").join(ancho_sbs, how="left")
datos = datos.loc[FECHA_INICIO:FECHA_CORTE]
escribir_log(f"Fechas fuera del calendario BCRP: Yahoo {(~ancho_yahoo.index.isin(datos.index)).sum()}, "
             f"SBS {(~ancho_sbs.index.isin(datos.index)).sum()}")

# ---------- 7. Valores atípicos aislados -> vacío (documentado) ----------
for col in PRECIOS_REVISAR:
    for fecha in atipicos_aislados(datos[col]):
        escribir_log(f"Atípico aislado: {col} {fecha:%d/%m/%Y} = {datos.at[fecha, col]} -> vacío (crudo intacto)")
        datos.at[fecha, col] = np.nan

# ---------- 8. Muestra común y variables ----------
pos_base = pd.Series(np.arange(len(datos)), index=datos.index)
comun = datos.dropna(subset=NUCLEO).copy()
comun["oro_pen"] = comun["oro_usd"] * comun["tc_pen_usd"]                    # S/ por onza
comun["cobre_pen_lb"] = comun["cobre_cusd_lb"] / 100 * comun["tc_pen_usd"]  # S/ por libra

proc = pd.DataFrame(index=comun.index)
proc["dias_habiles_desde_anterior"] = pos_base[comun.index].diff()
for col in ["igbvl", "oro_pen", "cobre_pen_lb", "tc_pen_usd", "tasa_cc10a_pen_sbs", "tasa_cc5a_pen_sbs",
            "tasa_cc10a_usd_sbs", "embig_pe", "rend_bono10_pen", "oro_usd", "oro_fut_usd"]:
    proc[col] = comun[col]
proc["r_igbvl"] = ret_log(comun["igbvl"])
proc["r_oro_pen"] = ret_log(comun["oro_pen"])
proc["r_cobre_pen"] = ret_log(comun["cobre_pen_lb"])
proc["r_tc"] = ret_log(comun["tc_pen_usd"])
proc["r_bono10_pen_sbs"] = -10 * comun["tasa_cc10a_pen_sbs"].diff()   # cupón cero 10 años: r = -10·Δy
proc["r_bono5_pen_sbs"] = -5 * comun["tasa_cc5a_pen_sbs"].diff()      # cupón cero 5 años: r = -5·Δy
proc["r_bono10_usd_sbs"] = -10 * comun["tasa_cc10a_usd_sbs"].diff()   # en dólares
proc["d_embig"] = comun["embig_pe"].diff()                            # puntos básicos
proc["d_rend10_pen_bcrp"] = comun["rend_bono10_pen"].diff()           # cotejo con la SBS
proc["d_tasa10_pen_sbs"] = comun["tasa_cc10a_pen_sbs"].diff()
proc["r_oro_usd"] = ret_log(comun["oro_usd"])
proc["r_oro_fut_usd"] = ret_log(comun["oro_fut_usd"])                 # vacío si Yahoo no cotizó
proc = proc.iloc[1:]                                                  # el primer día no tiene retorno
proc.index.name = "fecha"

# ---------- 9. Controles ----------
assert proc[["r_igbvl", "r_oro_pen", "r_cobre_pen", "r_tc", "r_bono10_pen_sbs"]].notna().all().all()
assert len(proc) >= 3200, "La muestra tiene menos de 3 200 observaciones (mínimo del TEMARIO)"
escribir_log(f"Muestra común: {len(proc)} retornos | {proc.index.min():%d/%m/%Y} a {proc.index.max():%d/%m/%Y} | "
             f"saltos: {proc['dias_habiles_desde_anterior'].value_counts().sort_index().to_dict()}")
escribir_log(f"Cotejo BCRP vs SBS (Δ bono 10a S/): corr = {proc['d_rend10_pen_bcrp'].corr(proc['d_tasa10_pen_sbs']):.3f} | "
             f"oro spot BCRP vs futuro Yahoo: corr = {proc['r_oro_usd'].corr(proc['r_oro_fut_usd']):.3f}")

# ---------- 10. Guardar ----------
archivo = PROCESADOS / f"datos_procesados_{CODIGO_MATRICULA}.csv"
proc.reset_index().to_csv(archivo, index=False, encoding="utf-8", date_format="%Y-%m-%d", float_format="%.10g")
proc.reset_index().to_excel(archivo.with_suffix(".xlsx"), index=False)   # copia para Excel (no va a GitHub)
sha = hashlib.sha256(archivo.read_bytes()).hexdigest()
escribir_log(f"Guardado {archivo.name} | {len(proc)} filas x {proc.shape[1] + 1} columnas | SHA-256 {sha}")
escribir_log("=== Fin 03_limpieza_datos.py ===")
