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
tab1, tab2 = st.tabs(["➕ Registrar Prenda", "📋 Ver e Interactuar"])

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
    # --- 1. FILA DE CONTROLES (Buscador a la izquierda, Mostrar a la derecha) ---
    col_bus, col_pag = st.columns([4, 1])

    with col_bus:
        bus = st.text_input("🔍 Filtrar inventario por ID, Categoría o Color", key="buscador_principal_tab2").lower()

    with col_pag:
        # He cambiado la key a "pag_limit_final" para evitar el error de duplicado
        items_pag = st.selectbox("Mostrar:", [20, 50, 100], index=0, key="pag_limit_final")

    # --- 2. PREPARACIÓN DE DATOS FILTRADOS ---
    df_ver = df_inventario.copy()
    if bus:
        df_ver = df_ver[df_ver.apply(lambda r: bus in str(r.values).lower(), axis=1)]
    
    total_items = len(df_ver)

    # 3. Cabecera Simétrica (Título y Gestión)
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader("📋 Control de Stock Visual")
    with col_t2:
        gestion_abierta = st.expander("🛠️ Gestionar Fichas", expanded=False)

    with gestion_abierta:
        st.markdown("### Editar o Eliminar Artículos")
        sel_id = st.selectbox("Selecciona el ID a modificar:", ["-- Elegir --"] + df_ver["ID"].astype(str).tolist(), key="sel_gest")

        if sel_id != "-- Elegir --":
            idx_match = df_inventario.index[df_inventario['ID'].astype(str) == sel_id].tolist()[0]
            datos_p = df_inventario.loc[idx_match]
            
            with st.form("form_edicion_rapida"):
                c_ed1, c_ed2 = st.columns([1, 2])
                with c_ed1:
                    st.image(datos_p["Image_Ref"], use_container_width=True)
                    nueva_f = st.file_uploader("Cambiar foto", type=['jpg','png'])
                with c_ed2:
                    ed_id = st.text_input("ID", value=str(datos_p["ID"]))
                    ed_cat = st.text_input("Categoría", value=str(datos_p["Categoria"]))
                    cx1, cx2 = st.columns(2)
                    ed_talla = cx1.text_input("Talla", value=str(datos_p["Talla"]))
                    ed_color = cx2.text_input("Color", value=str(datos_p["Color"]))
                    ed_stock = cx1.number_input("Stock", value=int(datos_p["Stock"]))
                    ed_compra = cx2.number_input("Compra", value=float(datos_p["Compra"]))
                    ed_venta = cx1.number_input("Venta", value=float(datos_p["Venta"]))
                    ed_fecha = cx2.text_input("Fecha", value=str(datos_p["Fecha"]))

                b_ed1, b_ed2, b_ed3 = st.columns(3)
                if b_ed1.form_submit_button("♻️ Sobreescribir"):
                    url_f = datos_p["Image_Ref"]
                    if nueva_f:
                        res = cloudinary.uploader.upload(nueva_f.getvalue(), folder="inventario", public_id=f"foto_{ed_id}")
                        url_f = res['secure_url']
                    df_inventario.loc[idx_match] = [ed_id, ed_cat, ed_fecha, ed_talla, ed_color, ed_compra, ed_venta, ed_stock, url_f]
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_inventario)
                    st.rerun()
                
                if b_ed2.form_submit_button("📑 Copia v1"):
                    nueva_id = f"{ed_id}_v1"
                    n_fila = pd.DataFrame([{"ID": nueva_id, "Categoria": ed_cat, "Fecha": ed_fecha, "Talla": ed_talla, "Color": ed_color, "Compra": ed_compra, "Venta": ed_venta, "Stock": ed_stock, "Image_Ref": datos_p["Image_Ref"]}])
                    df_final = pd.concat([df_inventario, n_fila], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_final)
                    st.rerun()

                if b_ed3.form_submit_button("🗑️ Eliminar", type="primary"):
                    df_del = df_inventario.drop(idx_match)
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_del)
                    st.rerun()

    # 4. Configuración de Paginación
    st.write("---")
    col_v1, col_v2 = st.columns([3, 1])
    with col_v2:
        items_pag = st.selectbox("Mostrar:", [20, 50, 100], index=0, key="pag_limit")

    num_pags = (total_items // items_pag) + (1 if total_items % items_pag > 0 else 0)
    if 'pag_act' not in st.session_state: st.session_state.pag_act = 1
    if st.session_state.pag_act > num_pags: st.session_state.pag_act = max(1, num_pags)

    inicio = (st.session_state.pag_act - 1) * items_pag
    df_pagina = df_ver.iloc[inicio:inicio + items_pag]

    # 5. Tabla HTML con Estilos
    df_html = df_pagina.copy()
    df_html['Vista'] = df_html['Image_Ref'].apply(lambda x: f'<a href="{x}" target="_blank"><img src="{x}" height="50px" style="border-radius:5px; cursor:zoom-in;"></a>')
    df_html['Compra'] = df_html['Compra'].apply(lambda x: f"{x:,.2f} €")
    df_html['Venta'] = df_html['Venta'].apply(lambda x: f"{x:,.2f} €")

    st.markdown("""<style>
        table {width: 100%; border-collapse: collapse; font-family: sans-serif;}
        th {background-color: #d1d5db !important; color: #1f2937 !important; padding: 12px !important; border: 1px solid #9ca3af;}
        td {text-align: center !important; vertical-align: middle !important; padding: 8px !important; border-bottom: 1px solid #e5e7eb;}
        tr:hover {background-color: rgba(156, 163, 175, 0.3) !important; transition: 0.2s;}
    </style>""", unsafe_allow_html=True)

    cols_ver = ['Vista', 'ID', 'Categoria', 'Color', 'Talla', 'Stock', 'Compra', 'Venta', 'Fecha']
    st.markdown(df_html[cols_ver].to_html(escape=False, index=False), unsafe_allow_html=True)

    # 6. Navegación
    st.write("")
    cp, cn, cx = st.columns([1, 2, 1])
    if cp.button("⬅️ Anterior", disabled=(st.session_state.pag_act <= 1), use_container_width=True):
        st.session_state.pag_act -= 1
        st.rerun()
    cn.markdown(f"<p style='text-align: center;'>Página <b>{st.session_state.pag_act}</b> de {max(1, num_pags)}</p>", unsafe_allow_html=True)
    if cx.button("Siguiente ➡️", disabled=(st.session_state.pag_act >= num_pags), use_container_width=True):
        st.session_state.pag_act += 1
        st.rerun()

    # 7. Gráfica de Análisis
    st.divider()
    if not df_inventario.empty:
        st.markdown("### 📈 Análisis de Inversión por Categoría")
        with st.container(border=True):
            df_inv = df_inventario.copy()
            df_inv["Inversion"] = df_inv["Compra"] * df_inv["Stock"]
            fig = px.pie(df_inv, values='Inversion', names='Categoria', hole=.4, color_discrete_sequence=px.colors.qualitative.Bold)
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), legend=dict(bgcolor="rgba(240, 242, 246, 0.9)", bordercolor="#9ca3af", borderwidth=1))
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
