import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import cloudinary
import cloudinary.uploader
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Almacén IA Pro", layout="wide")

# --- 2. CONFIG CLOUDINARY ---
cloudinary.config( 
  cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"], 
  api_key = st.secrets["CLOUDINARY_API_KEY"], 
  api_secret = st.secrets["CLOUDINARY_API_SECRET"] 
)

# --- 3. CONFIGURACIÓN DEL MODELO ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-3-flash-preview') 
conn = st.connection("gsheets", type=GSheetsConnection)

# URL de la imagen por defecto
URL_SIN_IMAGEN = "https://res.cloudinary.com/daquubngv/image/upload/v1778660130/sin_imagen_zy2jcx.jpg"

# --- 4. FUNCIONES DE DATOS ---
def leer_datos():
    df = conn.read(spreadsheet=st.secrets["spreadsheet_url"], ttl=0)
    if df.empty:
        return pd.DataFrame(columns=["ID", "Categoria", "Fecha", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"])
    # Limpieza y conversión de tipos
    df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
    df['Compra'] = pd.to_numeric(df['Compra'], errors='coerce').fillna(0.0)
    df['Venta'] = pd.to_numeric(df['Venta'], errors='coerce').fillna(0.0)
    return df

df_inventario = leer_datos()

# Cálculo de nuevo ID sugerido
try:
    ids_numericos = pd.to_numeric(df_inventario["ID"], errors='coerce').dropna()
    nuevo_id_sug = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
except:
    nuevo_id_sug = 1

st.title("👕 Gestor de Inventario Pro")

# --- 5. PESTAÑAS PRINCIPALES ---
tab1, tab2, tab3 = st.tabs(["➕ Registrar Prenda", "📋 Ver e Interactuar", "📊 Análisis y Gráficos"])

# --- TAB 1: REGISTRO ---
with tab1:
    if 'modo_registro' not in st.session_state: st.session_state.modo_registro = None

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("📸 Registrar por Imagen", use_container_width=True):
            st.session_state.modo_registro = "imagen"
            if 'datos_ia' in st.session_state: del st.session_state.datos_ia
    with col_b2:
        if st.button("📝 Registro Manual", use_container_width=True):
            st.session_state.modo_registro = "manual"

    st.divider()

    if st.session_state.modo_registro == "imagen":
        archivo_foto = st.file_uploader("Sube la foto de la prenda", type=["jpg", "png", "jpeg"])
        if archivo_foto:
            if 'datos_ia' not in st.session_state:
                with st.spinner("🤖 IA Analizando..."):
                    img_pil = Image.open(archivo_foto)
                    prompt = "Analiza la prenda. Responde ESTRICTAMENTE: CATEGORIA / COLOR. Sin etiquetas ni asteriscos."
                    resp = model.generate_content([prompt, img_pil])
                    try:
                        p = resp.text.split("/")
                        cat_l = p[0].strip(); col_l = p[1].strip()
                        st.session_state.datos_ia = {"cat": cat_l, "color": col_l}
                    except:
                        st.session_state.datos_ia = {"cat": "Revisar", "color": "Revisar"}

            c_ia = st.session_state.datos_ia["cat"]
            cl_ia = st.session_state.datos_ia["color"]
            
            # Buscar coincidencias para pre-rellenar
            match = df_inventario[(df_inventario["Categoria"].str.lower() == c_ia.lower()) & (df_inventario["Color"].str.lower() == cl_ia.lower())]
            id_f, t_f, cp_f, vt_f = str(nuevo_id_sug), "", 0.0, 0.0
            
            if not match.empty:
                art = match.iloc[0]
                id_f, t_f, cp_f, vt_f = str(art['ID']), str(art['Talla']), float(art['Compra']), float(art['Venta'])
                st.success(f"🔍 Coincidencia encontrada (ID: {id_f}).")

            with st.form("form_ia"):
                f_id = st.text_input("ID Artículo", value=id_f)
                c_1, c_2 = st.columns(2)
                f_cat = c_1.text_input("Categoría", value=c_ia)
                f_col = c_2.text_input("Color", value=cl_ia)
                f_talla = c_1.text_input("Talla", value=t_f)
                f_stock = c_2.number_input("Cantidad", min_value=1)
                f_compra = c_1.number_input("Compra (€)", value=cp_f, format="%.2f")
                f_venta = c_2.number_input("Venta (€)", value=vt_f, format="%.2f")
                
                if st.form_submit_button("🚀 GUARDAR REGISTRO"):
                    with st.spinner("Subiendo..."):
                        res_c = cloudinary.uploader.upload(archivo_foto.getvalue(), folder="inventario", public_id=f"foto_{f_id}")
                        nueva = pd.DataFrame([{"ID": f_id, "Categoria": f_cat, "Fecha": datetime.now().strftime('%Y-%m-%d'), "Talla": f_talla, "Color": f_col, "Compra": f_compra, "Venta": f_venta, "Stock": f_stock, "Image_Ref": res_c['secure_url']}])
                        df_f = pd.concat([df_inventario[df_inventario["ID"].astype(str) != str(f_id)], nueva], ignore_index=True)
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_f)
                        st.session_state.modo_registro = None
                        st.rerun()

    elif st.session_state.modo_registro == "manual":
        with st.form("form_manual"):
            f_id = st.text_input("ID", value=str(nuevo_id_sug))
            c_1, c_2 = st.columns(2)
            f_cat = c_1.text_input("Categoría"); f_col = c_2.text_input("Color")
            f_talla = c_1.text_input("Talla"); f_stock = c_2.number_input("Stock", min_value=1)
            f_compra = c_1.number_input("Compra (€)"); f_venta = c_2.number_input("Venta (€)")
            if st.form_submit_button("💾 GUARDAR MANUAL"):
                nueva = pd.DataFrame([{"ID": f_id, "Categoria": f_cat, "Fecha": datetime.now().strftime('%Y-%m-%d'), "Talla": f_talla, "Color": f_col, "Compra": f_compra, "Venta": f_venta, "Stock": f_stock, "Image_Ref": URL_SIN_IMAGEN}])
                df_f = pd.concat([df_inventario[df_inventario["ID"].astype(str) != str(f_id)], nueva], ignore_index=True)
                conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_f)
                st.session_state.modo_registro = None
                st.rerun()

# --- TAB 2: INVENTARIO (REESTRUCTURADO) ---
with tab2:
    # --- 1. DATOS Y FILTRADO (Necesario al inicio para evitar errores de variables) ---
    df_ver = df_inventario.copy()
    
    # --- 2. FILA SUPERIOR: TÍTULO Y GESTIÓN ---
    col_tit, col_gest = st.columns([3, 1])
    with col_tit:
        st.subheader("📋 Control de Stock Visual")
    with col_gest:
        exp_gest = st.expander("🛠️ Gestionar Fichas", expanded=False)
        with exp_gest:
            sel_id = st.selectbox("ID a editar:", ["-- Elegir --"] + df_ver["ID"].astype(str).tolist(), key="editor_id")
            if sel_id != "-- Elegir --":
                # (Aquí iría tu formulario de edición que ya tienes configurado)
                st.info(f"Editando ID: {sel_id}")
                # [Inserta aquí tu bloque st.form de edición anterior si lo deseas]

    # --- 3. FILA DE CONTROLES: BUSCADOR Y MOSTRAR ---
    col_bus, col_pag_limit = st.columns([4, 1])
    with col_bus:
        bus = st.text_input("🔍 Buscar por ID, Categoría o Color", key="bus_tab2_final").lower()
    with col_pag_limit:
        items_por_pag = st.selectbox("Mostrar:", [20, 50, 100], index=0, key="limite_vista")

    # Aplicar filtro de búsqueda
    if bus:
        df_ver = df_ver[df_ver.apply(lambda r: bus in str(r.values).lower(), axis=1)]
    
    total_items = len(df_ver)

    # --- 4. LÓGICA DE PAGINACIÓN ---
    num_paginas = (total_items // items_por_pag) + (1 if total_items % items_por_pag > 0 else 0)
    
    if 'pag_actual' not in st.session_state:
        st.session_state.pag_actual = 1
    
    # Reset de página si el filtro reduce los resultados
    if st.session_state.pag_actual > num_paginas:
        st.session_state.pag_actual = max(1, num_paginas)

    inicio = (st.session_state.pag_actual - 1) * items_por_pag
    df_pagina = df_ver.iloc[inicio : inicio + items_por_pag]

    # --- 5. RENDERIZADO DE LA TABLA ---
    df_html = df_pagina.copy()
    # Formateo visual (Imagen y Moneda)
    df_html['Vista'] = df_html['Image_Ref'].apply(lambda x: f'<a href="{x}" target="_blank"><img src="{x}" height="50px" style="border-radius:5px; cursor:zoom-in;"></a>')
    df_html['Compra'] = df_html['Compra'].apply(lambda x: f"{x:,.2f} €")
    df_html['Venta'] = df_html['Venta'].apply(lambda x: f"{x:,.2f} €")

    # CSS de la tabla
    st.markdown("""<style>
        table {width: 100%; border-collapse: collapse;}
        th {background-color: #d1d5db !important; color: #1f2937 !important; padding: 12px; border: 1px solid #9ca3af;text-align: center !important; /* CENTRADO DE TÍTULOS */}
        td {text-align: center !important; vertical-align: middle !important; padding: 8px; border-bottom: 1px solid #e5e7eb;}
        tr:hover {background-color: rgba(156, 163, 175, 0.3) !important; transition: 0.2s;}
    </style>""", unsafe_allow_html=True)

    cols_tab = ['Vista', 'ID', 'Categoria', 'Color', 'Talla', 'Stock', 'Compra', 'Venta', 'Fecha']
    st.markdown(df_html[cols_tab].to_html(escape=False, index=False), unsafe_allow_html=True)

    # --- 6. NAVEGACIÓN INTELIGENTE (Solo se muestra si hay más de 1 página) ---
    if num_paginas > 1:
        st.write("")
        c_prev, c_nums, c_next = st.columns([1, 3, 1])
        
        with c_prev:
            if st.button("⬅️ Anterior", disabled=(st.session_state.pag_actual <= 1), use_container_width=True):
                st.session_state.pag_actual -= 1
                st.rerun()

        with c_nums:
            # Creamos botones con los números de las páginas
            cols_n = st.columns(num_paginas)
            for i in range(num_paginas):
                p_num = i + 1
                # Resaltamos el número de la página actual
                label = f"**{p_num}**" if p_num == st.session_state.pag_actual else str(p_num)
                if cols_n[i].button(label, key=f"btn_p_{p_num}", use_container_width=True):
                    st.session_state.pag_actual = p_num
                    st.rerun()

        with c_next:
            if st.button("Siguiente ➡️", disabled=(st.session_state.pag_actual >= num_paginas), use_container_width=True):
                st.session_state.pag_actual += 1
                st.rerun()

# --- TAB 3: ANÁLISIS Y GRÁFICOS ---
with tab3:
    st.header("📊 Análisis Estadístico del Inventario")
    
    if df_inventario.empty:
        st.info("No hay datos suficientes para generar gráficos. Registra algunas prendas primero.")
    else:
        # --- FILA DE MÉTRICAS RÁPIDAS ---
        # Calculamos datos clave para la pestaña de análisis
        total_prendas = df_inventario["Stock"].sum()
        inversion_total = (df_inventario["Stock"] * df_inventario["Compra"]).sum()
        precio_medio_venta = df_inventario["Venta"].mean()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Unidades Totales", f"{total_prendas} uds")
        m2.metric("Inversión en Stock", f"{inversion_total:,.2f} €")
        m3.metric("Promedio Venta", f"{precio_medio_venta:,.2f} €")
        
        st.write("---")
        
        # --- ZONA DE GRÁFICAS ---
        col_chart1, col_chart2 = st.columns([2, 1])
        
        with col_chart1:
            st.subheader("💰 Distribución de la Inversión")
            # Preparación de datos
            df_inv = df_inventario.copy()
            df_inv["Inversion"] = df_inv["Compra"] * df_inv["Stock"]
            
            fig_pie = px.pie(
                df_inv, 
                values='Inversion', 
                names='Categoria', 
                hole=.4,
                color_discrete_sequence=px.colors.qualitative.Bold,
                template="plotly_white"
            )
            
            fig_pie.update_layout(
                margin=dict(t=30, b=30, l=30, r=30),
                legend=dict(
                    bgcolor="rgba(255, 255, 255, 0.7)",
                    bordercolor="#9ca3af",
                    borderwidth=1
                )
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_chart2:
            st.subheader("📦 Stock por Categoría")
            # Gráfico de barras simple para ver cantidades
            df_stock_cat = df_inventario.groupby("Categoria")["Stock"].sum().reset_index()
            fig_bar = px.bar(
                df_stock_cat, 
                x="Categoria", 
                y="Stock",
                color="Categoria",
                text_auto=True,
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        # --- TABLA RESUMEN DE RENDIMIENTO ---
        st.write("---")
        st.subheader("📈 Resumen de Valor por Categoría")
        
        # Agrupamos datos para mostrar una tabla informativa
        resumen_cat = df_inventario.groupby("Categoria").agg({
            "Stock": "sum",
            "Compra": "mean",
            "Venta": "mean"
        }).reset_index()
        
        resumen_cat.columns = ["Categoría", "Stock Total", "Precio Compra Medio", "Precio Venta Medio"]
        
        # Aplicamos formato de moneda para que sea profesional
        resumen_cat["Precio Compra Medio"] = resumen_cat["Precio Compra Medio"].map("{:,.2f} €".format)
        resumen_cat["Precio Venta Medio"] = resumen_cat["Precio Venta Medio"].map("{:,.2f} €".format)
        
        st.table(resumen_cat)
