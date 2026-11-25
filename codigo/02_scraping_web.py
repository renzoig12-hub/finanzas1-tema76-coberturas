# Autor: Renzo Jhonel Ignacio Paucar
# Código de matrícula: 2024200504J
# Tema N.° 76 (Unidad II): Oro, cobre y renta fija soberana como coberturas en un portafolio peruano
# Fecha de extracción: 2026-11-25

"""
VÍA 2 - Web scraping (formulario ASP.NET) de la SBS.
Página "Comparativo de un Plazo en un Intervalo de Tiempo" de las curvas cupón cero:
    https://www.sbs.gob.pe/app/pu/CCID/Paginas/cc_unperiodo.aspx
Para cada curva soberana y cada plazo, se consulta un año a la vez (2012 a 2025) y se obtiene
la tasa diaria de ese plazo. robots.txt de la SBS: la ruta /app/ no está restringida.
Curvas: CCPSS (Perú Soles Soberana) y CCPEDS (Perú Exterior Dólares - Soberana).
Plazos: 3600 días (10 años, variable principal) y 1800 días (5 años, robustez).
Guarda cada tabla sin modificar (texto tal cual) en datos_crudos/sbs/, un CSV por curva y plazo.
Si se corta, al volver a ejecutarlo omite las combinaciones curva-plazo ya guardadas.
Ejecutar desde la carpeta principal:
    python codigo/02_scraping_web.py            # descarga completa (unos 20 a 30 minutos)
    python codigo/02_scraping_web.py --prueba   # solo soles, 10 años, 2012 (no guarda CSV)
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------- 1. Parámetros congelados ----------
CODIGO_MATRICULA = "2024200504J"
FECHA_INICIO = "2012-01-01"
FECHA_CORTE = "2025-12-31"
URL_SBS = "https://www.sbs.gob.pe/app/pu/CCID/Paginas/cc_unperiodo.aspx"
CURVAS = {"CCPSS": "soles", "CCPEDS": "dolares"}   # código SBS -> nombre corto
PLAZOS_DIAS = ["3600", "1800"]                     # 10 años y 5 años
CABECERAS = {"User-Agent": f"UNCP-Finanzas1-Tema76 (estudiante {CODIGO_MATRICULA}; uso academico)"}
PAUSA_SEG = 1.5             # pausa entre solicitudes (la consigna exige al menos 1 s)
REINTENTOS = 3
ENCABEZADO_SBS = ["Sec.", "Fecha", "Periodo (días)", "Tasa (%)"]   # encabezado que muestra la página
MODO_PRUEBA = "--prueba" in sys.argv

# ---------- 2. Rutas relativas ----------
PROYECTO = Path(__file__).resolve().parent.parent
CRUDOS_SBS = PROYECTO / "datos_crudos" / "sbs"
LOG = PROYECTO / "log_ejecucion.txt"
CRUDOS_SBS.mkdir(parents=True, exist_ok=True)

def escribir_log(mensaje):
    """Escribe una línea con fecha y hora de Lima en pantalla y en el log."""
    ahora = datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ahora}] {mensaje}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")

class FormularioSBS:
    """Maneja el formulario ASP.NET: cada paso devuelve los campos ocultos que exige el siguiente."""

    def __init__(self):
        self.sesion = requests.Session()
        self.sesion.headers.update(CABECERAS)
        self.valores = {"cboTipoCurva": "", "cboFechas1": "", "cboFechas2": "", "cboPlazo": ""}
        respuesta = self.sesion.get(URL_SBS, timeout=60)
        escribir_log(f"SBS abrir página | HTTP {respuesta.status_code} | {URL_SBS}")
        self.sopa = BeautifulSoup(respuesta.text, "lxml")

    def enviar(self, campo, valor, descripcion):
        """Cambia un campo (o pulsa 'Consultar' si campo es None) y guarda la nueva página."""
        time.sleep(PAUSA_SEG)
        datos = {c["name"]: c.get("value", "") for c in self.sopa.select("input[type=hidden]") if c.get("name")}
        if campo:
            self.valores[campo] = valor
        # Solo se envían los desplegables con valor: uno vacío provoca HTTP 500 en la SBS
        datos.update({k: v for k, v in self.valores.items() if v})
        datos["__EVENTTARGET"] = campo or ""
        if campo is None:
            datos["btnConsultar"] = "  Consultar  "
        respuesta = self.sesion.post(URL_SBS, data=datos, timeout=120)
        escribir_log(f"SBS {descripcion} | HTTP {respuesta.status_code}")
        respuesta.raise_for_status()
        self.sopa = BeautifulSoup(respuesta.text, "lxml")

    def fechas_disponibles(self):
        """Fechas (dd/mm/aaaa) del desplegable 'Fecha de Inicio' para la curva elegida."""
        return [op.get("value") for op in self.sopa.select("#cboFechas1 option") if op.get("value")]

    def tabla_resultado(self):
        """Filas de la tabla de resultados, con el texto tal como aparece en la página."""
        filas = []
        for fila in self.sopa.find_all("tr"):
            celdas = [c.get_text(strip=True) for c in fila.find_all("td", recursive=False)]
            if len(celdas) == 4 and len(celdas[1]) == 10 and celdas[1][2] == "/" and celdas[1][5] == "/":
                filas.append(celdas)
        return pd.DataFrame(filas, columns=ENCABEZADO_SBS)

def descargar_anio(curva, plazo, fecha_ini, fecha_fin):
    """Una consulta completa (un año de un plazo). Reintenta con una sesión nueva si falla."""
    for intento in range(1, REINTENTOS + 1):
        try:
            formulario = FormularioSBS()
            formulario.enviar("cboTipoCurva", curva, f"curva {curva}")
            formulario.enviar("cboFechas1", fecha_ini, f"fecha inicio {fecha_ini}")
            formulario.enviar("cboFechas2", fecha_fin, f"fecha fin {fecha_fin}")
            formulario.enviar("cboPlazo", plazo, f"plazo {plazo} días")
            formulario.enviar(None, None, f"consultar {curva} {plazo} {fecha_ini}-{fecha_fin}")
            tabla = formulario.tabla_resultado()
            if len(tabla) > 0 and (tabla["Periodo (días)"] == plazo).all():
                return tabla
            escribir_log(f"SBS {curva} {plazo} {fecha_ini}: intento {intento}, tabla vacía o con otro plazo")
        except requests.RequestException as error:
            escribir_log(f"SBS {curva} {plazo} {fecha_ini}: intento {intento}, error {type(error).__name__}")
        time.sleep(5 * intento)
    return None

# ---------- 3. Fechas: primer y último día disponible de cada año, para cada curva ----------
def rangos_anuales(curva):
    """Lista de (primer día, último día) de cada año del periodo, según las fechas que ofrece la SBS."""
    formulario = FormularioSBS()
    formulario.enviar("cboTipoCurva", curva, f"curva {curva} (lista de fechas)")
    fechas = pd.to_datetime(pd.Series(formulario.fechas_disponibles()), format="%d/%m/%Y")
    fechas = fechas[(fechas >= FECHA_INICIO) & (fechas <= FECHA_CORTE)].sort_values()
    escribir_log(f"{curva}: {len(fechas)} fechas en el periodo ({fechas.iloc[0]:%d/%m/%Y} a {fechas.iloc[-1]:%d/%m/%Y})")
    return [(g.iloc[0].strftime("%d/%m/%Y"), g.iloc[-1].strftime("%d/%m/%Y")) for _, g in fechas.groupby(fechas.dt.year)]

escribir_log("=== Inicio 02_scraping_web.py (SBS, un plazo en un intervalo de tiempo) ===")
combinaciones = [(c, p) for c in CURVAS for p in PLAZOS_DIAS]
if MODO_PRUEBA:
    combinaciones = [("CCPSS", "3600")]
    escribir_log("MODO PRUEBA: solo soles, 10 años, 2012; no se guarda el CSV")

# ---------- 4. Descarga: una consulta por curva, plazo y año ----------
rangos_por_curva = {}
for curva, plazo in combinaciones:
    archivo = CRUDOS_SBS / f"datos_crudos_sbs_{CURVAS[curva]}_{plazo}d_{CODIGO_MATRICULA}.csv"
    if archivo.exists() and not MODO_PRUEBA:
        escribir_log(f"{archivo.name} ya existe, se omite")
        continue
    if curva not in rangos_por_curva:
        rangos_por_curva[curva] = rangos_anuales(curva)
    rangos = rangos_por_curva[curva][:1] if MODO_PRUEBA else rangos_por_curva[curva]
    tablas, fallidos = [], []
    for fecha_ini, fecha_fin in rangos:
        tabla = descargar_anio(curva, plazo, fecha_ini, fecha_fin)
        if tabla is None:
            fallidos.append(fecha_ini[-4:])
            continue
        tabla.insert(0, "curva", curva)        # identificador de la curva consultada
        tablas.append(tabla)
        escribir_log(f"SBS {curva} {plazo} días {fecha_ini[-4:]} | filas: {len(tabla)}")
    if not tablas:
        escribir_log(f"{curva} {plazo}: sin datos descargados")
        continue
    tabla_total = pd.concat(tablas, ignore_index=True)
    if MODO_PRUEBA:
        print(tabla_total.head(5).to_string())
        print("...")
        print(tabla_total.tail(3).to_string())
    else:
        tabla_total.to_csv(archivo, index=False, encoding="utf-8")
    escribir_log(f"{curva} {plazo} días | filas: {len(tabla_total)} | años fallidos: {fallidos or 'ninguno'}"
                 + ("" if MODO_PRUEBA else f" | guardado {archivo.name}"))

escribir_log("=== Fin 02_scraping_web.py ===")
