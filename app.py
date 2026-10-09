# ==========================================================
# RetailPulse - Panel de ventas y segmentación RFM de clientes
# ==========================================================

# Importamos Streamlit, la librería que convierte este script en una página web
import streamlit as st
# Importamos pandas para trabajar con las tablas de datos
import pandas as pd
# Importamos Plotly Express para crear gráficos interactivos de forma sencilla
import plotly.express as px
# Importamos Path para construir rutas de archivos que funcionen en cualquier computador
from pathlib import Path

# ----------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL DE LA PÁGINA
# ----------------------------------------------------------

# Configuramos título de la pestaña, ícono y diseño ancho (aprovecha toda la pantalla)
st.set_page_config(page_title="RetailPulse", page_icon="📈", layout="wide")

# Guardamos la carpeta donde vive este archivo para encontrar los datos sin importar desde dónde se ejecute
CARPETA = Path(__file__).parent

# Definimos el orden en que queremos mostrar los segmentos (del mejor al peor cliente)
ORDEN_SEGMENTOS = ["Campeones", "Clientes Leales", "Potenciales", "En Riesgo", "Perdidos"]

# Asignamos un color fijo a cada segmento para que sea el mismo en todos los gráficos
COLORES = {
    "Campeones": "#1B7F5C",        # verde oscuro: los mejores clientes
    "Clientes Leales": "#4CAF93",  # verde claro: clientes fieles
    "Potenciales": "#4C78A8",      # azul: clientes con espacio para crecer
    "En Riesgo": "#F2A541",        # naranja: alerta, se están alejando
    "Perdidos": "#C0504D",         # rojo: clientes que ya no compran
}

# Diccionario para mostrar los nombres de los meses en español
MESES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
         7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}

# Inyectamos un poco de CSS para darle un aspecto limpio y profesional a la página
st.markdown(
    """
    <style>
    /* Reducimos el espacio vacío de arriba para ganar pantalla */
    .block-container {padding-top: 2rem;}
    /* Damos estilo de tarjeta a cada KPI; colores semitransparentes que funcionan en modo claro y oscuro */
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.10);
        border: 1px solid rgba(128, 128, 128, 0.35);
        border-radius: 12px;
        padding: 16px 20px;
    }
    /* El título de la tarjeta usa el color del tema (se ve en claro y en oscuro) */
    div[data-testid="stMetricLabel"] {opacity: 0.85;}
    /* Ajustamos el tamaño del número grande; su color lo decide el tema automáticamente */
    div[data-testid="stMetricValue"] {font-size: 1.9rem;}
    </style>
    """,
    unsafe_allow_html=True,  # permitimos que Streamlit interprete el HTML/CSS de arriba
)


# ----------------------------------------------------------
# 2. CARGA DE DATOS (con caché para que sea rápido)
# ----------------------------------------------------------

# @st.cache_data guarda el resultado en memoria: los CSV se leen UNA sola vez, no en cada clic
@st.cache_data(show_spinner="Cargando datos...")
def cargar_datos():
    # Leemos las ventas (archivo comprimido .gz) y convertimos InvoiceDate a fecha
    ventas = pd.read_csv(CARPETA / "data" / "ventas_limpias.csv.gz", parse_dates=["InvoiceDate"])
    # Leemos la tabla de clientes con su RFM y su segmento
    clientes = pd.read_csv(CARPETA / "data" / "clientes_rfm.csv")
    # Creamos la columna Mes (primer día de cada mes) para poder agrupar ventas por mes
    ventas["Mes"] = ventas["InvoiceDate"].dt.to_period("M").dt.to_timestamp()
    # Traemos el Segmento de cada cliente a la tabla de ventas, buscando por Customer ID
    ventas["Segmento"] = ventas["Customer ID"].map(clientes.set_index("Customer ID")["Segmento"])
    # Convertimos textos repetidos a tipo "category" para ahorrar memoria y acelerar filtros
    for columna in ["Description", "Country", "Segmento"]:
        # Cada columna de texto se transforma a categoría
        ventas[columna] = ventas[columna].astype("category")
    # Reducimos el tamaño de los números enteros para ahorrar memoria
    ventas["Customer ID"] = ventas["Customer ID"].astype("int32")
    # Lo mismo con el número de factura
    ventas["Invoice"] = ventas["Invoice"].astype("int32")
    # Devolvemos las dos tablas listas para usar
    return ventas, clientes


# Ejecutamos la función; gracias a la caché, solo tarda la primera vez
ventas, clientes = cargar_datos()


# ----------------------------------------------------------
# 3. BARRA LATERAL CON FILTROS
# ----------------------------------------------------------

# Título de la barra lateral
st.sidebar.title("📈 RetailPulse")
# Pequeña descripción para el usuario
st.sidebar.caption("Filtra los datos y todo el panel se actualiza.")

# Calculamos la fecha mínima disponible en los datos
fecha_min = ventas["InvoiceDate"].min().date()
# Calculamos la fecha máxima disponible en los datos
fecha_max = ventas["InvoiceDate"].max().date()

# Selector de rango de fechas, que arranca con todo el periodo disponible
rango = st.sidebar.date_input(
    "Rango de fechas",
    value=(fecha_min, fecha_max),  # valor inicial: periodo completo
    min_value=fecha_min,           # no permite elegir antes del primer dato
    max_value=fecha_max,           # no permite elegir después del último dato
)

# Si la persona eligió dos fechas (inicio y fin), las usamos tal cual
if isinstance(rango, (tuple, list)) and len(rango) == 2:
    # Separamos la fecha de inicio y la de fin
    fecha_ini, fecha_fin = rango
# Si solo eligió una fecha (aún está escogiendo la segunda), usamos esa misma como inicio y fin
else:
    # Tomamos la fecha elegida (si viene en lista, el primer elemento)
    fecha_ini = fecha_fin = rango[0] if isinstance(rango, (tuple, list)) else rango

# Lista de países ordenada alfabéticamente (quitamos los valores no usados de la categoría)
lista_paises = sorted(ventas["Country"].cat.categories.tolist())
# Selector múltiple de países; si se deja vacío, se usan todos
paises_sel = st.sidebar.multiselect(
    "País", lista_paises, default=[], placeholder="Todos los países",
    help="Déjalo vacío para incluir todos los países.",
)

# Selector múltiple de segmentos RFM; por defecto vienen todos marcados
segmentos_sel = st.sidebar.multiselect(
    "Segmento de cliente", ORDEN_SEGMENTOS, default=ORDEN_SEGMENTOS,
    help="Segmentos creados con el análisis RFM (Recencia, Frecuencia y Monto).",
)

# Una línea divisoria para separar los filtros de la nota final
st.sidebar.divider()
# Nota informativa sobre la moneda de los datos
st.sidebar.caption("Moneda: libras esterlinas (£). Fuente: Online Retail II.")

# Si la persona no dejó ningún segmento marcado, usamos todos para evitar una pantalla vacía
if not segmentos_sel:
    # Asignamos todos los segmentos
    segmentos_sel = ORDEN_SEGMENTOS
# Si no eligió países, usamos todos
if not paises_sel:
    # Asignamos todos los países
    paises_sel = lista_paises


# ----------------------------------------------------------
# 4. APLICAR LOS FILTROS A LOS DATOS
# ----------------------------------------------------------

# Convertimos la fecha de inicio a Timestamp (fecha con hora 00:00)
inicio = pd.Timestamp(fecha_ini)
# Sumamos un día a la fecha final para incluir TODAS las horas de ese último día
fin = pd.Timestamp(fecha_fin) + pd.Timedelta(days=1)

# Creamos una máscara (verdadero/falso por fila) que cumple las tres condiciones a la vez
mascara = (
    (ventas["InvoiceDate"] >= inicio)           # desde la fecha de inicio
    & (ventas["InvoiceDate"] < fin)             # hasta el final de la fecha fin
    & (ventas["Country"].isin(paises_sel))      # solo los países elegidos
    & (ventas["Segmento"].isin(segmentos_sel))  # solo los segmentos elegidos
)
# Nos quedamos únicamente con las filas que cumplen los filtros
df = ventas[mascara]


# ----------------------------------------------------------
# 5. ENCABEZADO DE LA PÁGINA
# ----------------------------------------------------------

# Título principal de la página
st.title("RetailPulse")
# Subtítulo explicando para qué sirve el panel
st.caption("Panel de ventas y segmentación de clientes para tomar decisiones comerciales.")

# Si los filtros no dejan ningún dato, avisamos y detenemos la app para no mostrar errores
if df.empty:
    # Mensaje de advertencia amigable
    st.warning("No hay datos con los filtros elegidos. Prueba ampliando el rango de fechas, país o segmento.")
    # Detenemos la ejecución del resto del script
    st.stop()


# ----------------------------------------------------------
# 6. TARJETAS KPI
# ----------------------------------------------------------

# Ingresos totales: suma de todo el dinero vendido
ingresos_totales = df["Ingreso"].sum()
# Número de clientes: contamos Customer ID distintos
n_clientes = df["Customer ID"].nunique()
# Número de pedidos: contamos facturas distintas (una factura tiene muchas líneas)
n_pedidos = df["Invoice"].nunique()
# Ticket promedio: cuánto dinero deja cada pedido en promedio
ticket_promedio = ingresos_totales / n_pedidos

# Creamos 4 columnas iguales para colocar una tarjeta en cada una
c1, c2, c3, c4 = st.columns(4)
# Tarjeta 1: ingresos totales con formato de miles
c1.metric("Ingresos totales", f"£{ingresos_totales:,.0f}")
# Tarjeta 2: número de clientes
c2.metric("Número de clientes", f"{n_clientes:,}")
# Tarjeta 3: ticket promedio con 2 decimales
c3.metric("Ticket promedio", f"£{ticket_promedio:,.2f}")
# Tarjeta 4: número de pedidos
c4.metric("Número de pedidos", f"{n_pedidos:,}")

# Espacio en blanco entre las tarjetas y los gráficos
st.write("")


# ----------------------------------------------------------
# 7. GRÁFICO DE LÍNEA: INGRESOS POR MES
# ----------------------------------------------------------

# Subtítulo de la sección
st.subheader("Evolución de ingresos por mes")
# Sumamos el ingreso de cada mes
mensual = df.groupby("Mes", observed=True)["Ingreso"].sum().reset_index()
# Creamos el gráfico de línea con puntos marcados
fig_mes = px.line(mensual, x="Mes", y="Ingreso", markers=True,
                  labels={"Mes": "Mes", "Ingreso": "Ingresos (£)"})
# Ponemos color a la línea y la hacemos un poco más gruesa
fig_mes.update_traces(line_color="#1F77B4", line_width=3)
# Fondo blanco, márgenes ajustados y etiquetas de fecha por mes
fig_mes.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_title=None, yaxis_tickprefix="£", yaxis_tickformat=",.0f")
# Mostramos el gráfico en la página
st.plotly_chart(fig_mes)
# Nota aclaratoria: el primer y el último mes pueden estar incompletos
st.caption("Nota: el primer y el último mes del periodo pueden estar incompletos, por eso a veces parecen caídas.")


# ----------------------------------------------------------
# 8. TOP 10 PRODUCTOS Y SEGMENTOS RFM (dos columnas)
# ----------------------------------------------------------

# Creamos dos columnas para poner gráficos lado a lado
col_izq, col_der = st.columns(2)

# ---- Columna izquierda: Top 10 productos ----
with col_izq:
    # Subtítulo de la sección
    st.subheader("Top 10 productos por ingreso")
    # Sumamos el ingreso por producto y nos quedamos con los 10 mayores
    top10 = (df.groupby("Description", observed=True)["Ingreso"].sum()
             .nlargest(10).reset_index())
    # Creamos barras horizontales (los nombres largos se leen mejor así)
    fig_top = px.bar(top10, x="Ingreso", y="Description", orientation="h",
                     labels={"Ingreso": "Ingresos (£)", "Description": ""})
    # Color uniforme para las barras
    fig_top.update_traces(marker_color="#1F77B4")
    # Ordenamos para que el producto más vendido quede arriba
    fig_top.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
                          yaxis={"categoryorder": "total ascending"}, xaxis_tickprefix="£")
    # Mostramos el gráfico
    st.plotly_chart(fig_top)

# ---- Columna derecha: segmentos RFM ----
with col_der:
    # Subtítulo de la sección
    st.subheader("Ingreso por segmento RFM")
    # Calculamos clientes únicos e ingreso por segmento
    seg = (df.groupby("Segmento", observed=True)
           .agg(Clientes=("Customer ID", "nunique"), Ingreso=("Ingreso", "sum"))
           .reindex(ORDEN_SEGMENTOS).dropna().reset_index())
    # Treemap: el tamaño del rectángulo representa el ingreso de cada segmento
    fig_tree = px.treemap(seg, path=["Segmento"], values="Ingreso", color="Segmento",
                          color_discrete_map=COLORES, custom_data=["Clientes"])
    # Texto dentro de cada rectángulo: nombre, ingreso y número de clientes
    fig_tree.update_traces(texttemplate="<b>%{label}</b><br>£%{value:,.0f}<br>%{customdata[0]:,} clientes",
                           hovertemplate="%{label}<br>Ingreso: £%{value:,.0f}<br>Clientes: %{customdata[0]:,}<extra></extra>")
    # Ajustamos márgenes
    fig_tree.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    # Mostramos el treemap
    st.plotly_chart(fig_tree)

# Subtítulo para el gráfico de clientes por segmento
st.subheader("Número de clientes por segmento RFM")
# Gráfico de barras con la cantidad de clientes de cada segmento
fig_cli = px.bar(seg, x="Segmento", y="Clientes", color="Segmento",
                 color_discrete_map=COLORES, text="Clientes",
                 category_orders={"Segmento": ORDEN_SEGMENTOS})
# Mostramos el número encima de cada barra, con separador de miles
fig_cli.update_traces(texttemplate="%{text:,}", textposition="outside")
# Quitamos la leyenda (los nombres ya están en el eje) y dejamos fondo limpio
fig_cli.update_layout(template="plotly_white", showlegend=False, xaxis_title=None,
                      yaxis_title="Clientes", margin=dict(l=10, r=10, t=10, b=10))
# Mostramos el gráfico
st.plotly_chart(fig_cli)


# ----------------------------------------------------------
# 9. TABLA DESCARGABLE DE CLIENTES PARA MARKETING
# ----------------------------------------------------------

# Subtítulo de la sección
st.subheader("Clientes para campañas de marketing")
# Texto explicativo de cómo usar la tabla
st.caption("Elige un segmento, revisa la lista y descárgala para contactarlos.")

# Selector para escoger un segmento concreto (o todos los segmentos filtrados)
segmento_tabla = st.selectbox("Segmento a exportar", ["Todos los segmentos filtrados"] + segmentos_sel)

# Si eligió un segmento concreto, filtramos las ventas a ese segmento
if segmento_tabla != "Todos los segmentos filtrados":
    # Nos quedamos solo con las ventas de ese segmento
    df_tabla = df[df["Segmento"] == segmento_tabla]
# Si eligió "todos", usamos las ventas ya filtradas tal cual
else:
    # Usamos todas las ventas filtradas
    df_tabla = df

# Resumimos las ventas por cliente dentro del periodo filtrado
por_cliente = (df_tabla.groupby("Customer ID", observed=True)
               .agg(Pais=("Country", "last"),               # último país registrado del cliente
                    Pedidos_periodo=("Invoice", "nunique"),   # pedidos en el periodo filtrado
                    Ingreso_periodo=("Ingreso", "sum"),       # dinero gastado en el periodo filtrado
                    Ultima_compra=("InvoiceDate", "max"))     # fecha de su última compra
               .reset_index())
# Convertimos el país a texto simple
por_cliente["Pais"] = por_cliente["Pais"].astype(str)
# Dejamos la fecha sin hora para que sea más legible
por_cliente["Ultima_compra"] = por_cliente["Ultima_compra"].dt.date
# Unimos con la tabla RFM para agregar segmento, puntajes y métricas históricas
tabla = por_cliente.merge(
    clientes[["Customer ID", "Segmento", "Recencia", "Frecuencia", "Monto", "R", "F", "M"]],
    on="Customer ID", how="left")
# Ordenamos de mayor a menor gasto para ver primero a los clientes más valiosos
tabla = tabla.sort_values("Ingreso_periodo", ascending=False)
# Redondeamos el dinero a 2 decimales
tabla["Ingreso_periodo"] = tabla["Ingreso_periodo"].round(2)
# Redondeamos también el monto histórico
tabla["Monto"] = tabla["Monto"].round(2)

# Mostramos cuántos clientes tiene la tabla
st.write(f"**{len(tabla):,} clientes** en la lista")
# Mostramos la tabla (sin la columna de índice) con altura fija para que no sea larguísima
st.dataframe(tabla, hide_index=True, height=350)

# Botón de descarga: convertimos la tabla a CSV (utf-8-sig para que Excel lea bien los acentos)
st.download_button(
    label="⬇️ Descargar lista en CSV",
    data=tabla.to_csv(index=False).encode("utf-8-sig"),   # contenido del archivo
    file_name="clientes_" + segmento_tabla.lower().replace(" ", "_") + ".csv",  # nombre del archivo
    mime="text/csv",                                      # tipo de archivo
)


# ----------------------------------------------------------
# 10. SECCIÓN DE INSIGHTS (conclusiones que se actualizan con los filtros)
# ----------------------------------------------------------

# Línea divisoria antes de las conclusiones
st.divider()
# Subtítulo de la sección
st.subheader("💡 Insights")

# ---- Insight 1: concentración del ingreso ----
# Segmento que más ingreso aporta dentro de los filtros actuales
seg_top = seg.sort_values("Ingreso", ascending=False).iloc[0]
# Porcentaje del ingreso que aporta ese segmento
pct_ingreso = seg_top["Ingreso"] / seg["Ingreso"].sum() * 100
# Porcentaje de clientes que representa ese segmento
pct_clientes = seg_top["Clientes"] / seg["Clientes"].sum() * 100
# Mostramos la conclusión en una caja azul
st.info(
    f"**1. Pocos clientes sostienen el negocio.** El segmento **{seg_top['Segmento']}** "
    f"representa el **{pct_clientes:.0f}%** de los clientes pero genera el **{pct_ingreso:.0f}%** "
    f"del ingreso. Perder a uno de ellos duele mucho más que perder a un cliente ocasional, "
    f"así que conviene un trato preferente (atención prioritaria, acceso anticipado a novedades)."
)

# ---- Insight 2: oportunidad de reactivación ----
# Buscamos la fila del segmento "En Riesgo" dentro de los datos filtrados
fila_riesgo = seg[seg["Segmento"] == "En Riesgo"]
# Si ese segmento está presente en los filtros, mostramos el insight específico
if not fila_riesgo.empty:
    # Número de clientes en riesgo
    n_riesgo = int(fila_riesgo["Clientes"].iloc[0])
    # Dinero que esos clientes han generado en el periodo filtrado
    ing_riesgo = fila_riesgo["Ingreso"].iloc[0]
    # Mostramos la conclusión en una caja amarilla de advertencia
    st.warning(
        f"**2. La reactivación es la oportunidad más rentable.** Hay **{n_riesgo:,}** clientes "
        f"'En Riesgo' que ya compraron **£{ing_riesgo:,.0f}** en el periodo, pero llevan tiempo sin volver. "
        f"Una campaña personalizada (recordatorio, descuento por tiempo limitado) cuesta mucho menos "
        f"que conseguir clientes nuevos. Puedes descargar la lista en la sección anterior."
    )
# Si el segmento no está seleccionado, damos un mensaje alternativo
else:
    # Invitamos a incluir el segmento para ver este análisis
    st.warning("**2. Reactivación.** Incluye el segmento 'En Riesgo' en el filtro para ver cuánto "
               "dinero está en juego con clientes que dejaron de comprar.")

# ---- Insight 3: estacionalidad ----
# Fila del mes con más ingreso
mes_pico = mensual.sort_values("Ingreso", ascending=False).iloc[0]
# Promedio mensual de ingresos
promedio_mes = mensual["Ingreso"].mean()
# Cuánto por encima del promedio estuvo el mes pico (en %)
sobre_promedio = (mes_pico["Ingreso"] / promedio_mes - 1) * 100
# Nombre del producto estrella del periodo
producto_top = top10["Description"].iloc[0]
# Mostramos la conclusión en una caja verde
st.success(
    f"**3. La demanda es estacional.** El mejor mes fue **{MESES[mes_pico['Mes'].month]} de {mes_pico['Mes'].year}** "
    f"con **£{mes_pico['Ingreso']:,.0f}**, un **{sobre_promedio:.0f}%** por encima del promedio mensual. "
    f"El producto líder fue **{producto_top.title()}**. Conviene preparar inventario y campañas "
    f"con anticipación antes de los meses fuertes."
)

# Pie de página con crédito
st.caption("RetailPulse · Hecho con Streamlit y Plotly")
