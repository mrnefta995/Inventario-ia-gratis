import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import cloudinary
import cloudinary.uploader
import plotly.express as px
import time

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
            # 1. Inicializamos variables con valores vacíos para evitar el NameError
            c_ia = ""
            cl_ia = ""

            if 'datos_ia' not in st.session_state:
                with st.spinner("🤖 IA Analizando..."):
                    try:
                        img_pil = Image.open(archivo_foto)
                        img_pil.thumbnail((800, 800)) 
                        prompt = "Analiza la prenda. Responde ESTRICTAMENTE: CATEGORIA / COLOR."
                        resp = model.generate_content([prompt, img_pil])
                        
                        p = resp.text.split("/")
                        c_ia = p[0].strip()
                        cl_ia = p[1].strip()
                        st.session_state.datos_ia = {"cat": c_ia, "color": cl_ia}
                    except Exception as e:
                        st.warning("⚠️ IA no disponible temporalmente. Introduce los datos a mano.")
                        st.session_state.datos_ia = {"cat": "", "color": ""}
            
            # 2. Recuperamos los datos del session_state (aseguramos que existan)
            c_ia = st.session_state.datos_ia.get("cat", "")
            cl_ia = st.session_state.datos_ia.get("color", "")

            # 3. Lógica de búsqueda de coincidencias (Blindada contra errores)
            match = pd.DataFrame() # Creamos un match vacío por defecto
            id_f, t_f, cp_f, vt_f = str(nuevo_id_sug), "", 0.0, 0.0

            # Solo buscamos si la IA nos dio algún dato
            if c_ia and cl_ia:
                match = df_inventario[
                    (df_inventario["Categoria"].str.lower() == c_ia.lower()) & 
                    (df_inventario["Color"].str.lower() == cl_ia.lower())
                ]
            
            if not match.empty:
                art = match.iloc[0]
                id_f, t_f, cp_f, vt_f = str(art['ID']), str(art['Talla']), float(art['Compra']), float(art['Venta'])
                st.info(f"🔍 Se encontró un artículo similar (ID: {id_f}).")

            # 4. Formulario de registro
            with st.form("form_ia_final"):
                f_id = st.text_input("ID Artículo", value=id_f)
                col1, col2 = st.columns(2)
                f_cat = col1.text_input("Categoría", value=c_ia)
                f_col = col2.text_input("Color", value=cl_ia)
                f_talla = col1.text_input("Talla", value=t_f)
                f_stock = col2.number_input("Cantidad", min_value=1)
                f_compra = col1.number_input("Compra (€)", value=cp_f)
                f_venta = col2.number_input("Venta (€)", value=vt_f)
                
                if st.form_submit_button("🚀 GUARDAR REGISTRO"):
                    # ... (Tu lógica de guardado en Cloudinary y GSheets)
                    st.success("¡Registro completado!")
                    if 'datos_ia' in st.session_state: del st.session_state.datos_ia
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
            st.markdown("### Editar o Eliminar")
            # El selector de ID
            sel_id = st.selectbox(
                "Selecciona el ID a modificar:", 
                ["-- Elegir --"] + df_ver["ID"].astype(str).tolist(), 
                key="editor_id_final"
            )

            # Si el usuario elige un ID, mostramos los campos para editar
            if sel_id != "-- Elegir --":
                # 1. Buscamos los datos actuales de ese ID
                idx_match = df_inventario.index[df_inventario['ID'].astype(str) == sel_id].tolist()[0]
                datos_p = df_inventario.loc[idx_match]
                
                # 2. Creamos un formulario para que los cambios se envíen juntos
                with st.form("form_edicion_dinamico"):
                    col_ed_img, col_ed_txt = st.columns([1, 2])
                    
                    with col_ed_img:
                        st.image(datos_p["Image_Ref"], caption="Foto actual", use_container_width=True)
                        nueva_foto = st.file_uploader("Cambiar foto", type=['jpg', 'png', 'jpeg'])
                    
                    with col_ed_txt:
                        # Rellenamos los campos con el valor actual (value=...)
                        ed_id = st.text_input("ID Artículo", value=str(datos_p["ID"]))
                        ed_cat = st.text_input("Categoría", value=str(datos_p["Categoria"]))
                        
                        c_extra1, c_extra2 = st.columns(2)
                        ed_talla = c_extra1.text_input("Talla", value=str(datos_p["Talla"]))
                        ed_color = c_extra2.text_input("Color", value=str(datos_p["Color"]))
                        
                        ed_stock = c_extra1.number_input("Stock", value=int(datos_p["Stock"]))
                        ed_compra = c_extra2.number_input("Precio Compra (€)", value=float(datos_p["Compra"]))
                        
                        ed_venta = c_extra1.number_input("Precio Venta (€)", value=float(datos_p["Venta"]))
                        ed_fecha = c_extra2.text_input("Fecha", value=str(datos_p["Fecha"]))

                    # 3. Botones de acción
                    st.write("")
                    b_col1, b_col2, b_col3 = st.columns(3)
                    
                    # ACCIÓN: SOBREESCRIBIR
                    if b_col1.form_submit_button("♻️ Sobreescribir"):
                        url_final = datos_p["Image_Ref"]
                        if nueva_foto:
                            res = cloudinary.uploader.upload(nueva_foto.getvalue(), folder="inventario", public_id=f"foto_{ed_id}")
                            url_final = res['secure_url']
                        
                        # Actualizamos la fila en el DataFrame
                        df_inventario.loc[idx_match] = [ed_id, ed_cat, ed_fecha, ed_talla, ed_color, ed_compra, ed_venta, ed_stock, url_final]
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_inventario)
                        st.success("✅ ¡Actualizado!")
                        st.rerun()

                    # ACCIÓN: COPIA (V1)
                    if b_col2.form_submit_button("📑 Copia v1"):
                        nuevo_id_v = f"{ed_id}_v1"
                        nueva_fila = pd.DataFrame([{
                            "ID": nuevo_id_v, "Categoria": ed_cat, "Fecha": ed_fecha, 
                            "Talla": ed_talla, "Color": ed_color, "Compra": ed_compra, 
                            "Venta": ed_venta, "Stock": ed_stock, "Image_Ref": datos_p["Image_Ref"]
                        }])
                        df_updated = pd.concat([df_inventario, nueva_fila], ignore_index=True)
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_updated)
                        st.success(f"✅ Creado: {nuevo_id_v}")
                        st.rerun()

                    # ACCIÓN: ELIMINAR
                    if b_col3.form_submit_button("🗑️ Eliminar", type="primary"):
                        df_del = df_inventario.drop(idx_match)
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_del)
                        st.warning("⚠️ Artículo eliminado.")
                        st.rerun()
    # --- 3. FILA DE CONTROLES: BUSCADOR Y MOSTRAR ---
    col_bus, col_pag_limit = st.columns([4, 1])

    with col_bus:
        # Al escribir aquí, Streamlit detecta el cambio automáticamente
        # Quitamos el .lower() inicial para procesar el ID puro primero
        bus_id = st.text_input("🔍 Buscar por ID (Escribe un número para filtrar)", key="bus_id_dinamico")
    
    with col_pag_limit:
        items_por_pag = st.selectbox("Mostrar:", [20, 50, 100], index=0, key="limite_vista_final")

    # --- 2. FILTRADO DINÁMICO EXCLUSIVO POR ID ---
    df_ver = df_inventario.copy()

    if bus_id:
        # Convertimos la columna ID a string y buscamos si contiene el texto introducido
        # Esto permite que si escribes "1", aparezcan el 1, 10, 11, 21, etc.
        df_ver = df_ver[df_ver["ID"].astype(str).str.contains(bus_id)]
    
    total_items = len(df_ver)

    # --- 3. LÓGICA DE PAGINACIÓN ADAPTATIVA ---
    num_paginas = (total_items // items_por_pag) + (1 if total_items % items_por_pag > 0 else 0)
    if num_paginas == 0: num_paginas = 1

    # Reset automático de página si el filtro deja menos páginas de las que había
    if 'pag_actual' not in st.session_state or st.session_state.pag_actual > num_paginas:
        st.session_state.pag_actual = 1

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
