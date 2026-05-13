import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import cloudinary
import cloudinary.uploader
import plotly.express as px

# --- CONFIGURACIÓN DE SEGURIDAD Y PÁGINA ---
st.set_option('deprecation.showPyplotGlobalUse', False)
st.set_page_config(page_title="Almacén IA Pro", layout="wide")

# --- CONFIG CLOUDINARY ---
cloudinary.config( 
  cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"], 
  api_key = st.secrets["CLOUDINARY_API_KEY"], 
  api_secret = st.secrets["CLOUDINARY_API_SECRET"] 
)

# --- CONFIGURACIÓN DEL MODELO IA ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash') # Actualizado a la versión estable
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("👕 Gestor de Inventario Inteligente")

# 1. URL de imagen por defecto
URL_SIN_IMAGEN = "https://res.cloudinary.com/daquubngv/image/upload/v1778660130/sin_imagen_zy2jcx.jpg"

# --- FUNCIONES DE DATOS ---
def leer_datos():
    df = conn.read(spreadsheet=st.secrets["spreadsheet_url"], ttl=0)
    if df.empty:
        return pd.DataFrame(columns=["ID", "Categoria", "Fecha", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"])
    # Aseguramos tipos de datos para evitar errores de cálculo
    df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
    df['Compra'] = pd.to_numeric(df['Compra'], errors='coerce').fillna(0.0)
    df['Venta'] = pd.to_numeric(df['Venta'], errors='coerce').fillna(0.0)
    return df

df_inventario = leer_datos()

# --- CÁLCULO DE NUEVO ID SUGERIDO ---
try:
    ids_numericos = pd.to_numeric(df_inventario["ID"], errors='coerce').dropna()
    nuevo_id_sug = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
except:
    nuevo_id_sug = 1

# --- DASHBOARD SUPERIOR ---
st.markdown("### 📊 Estado del Almacén")
c_m1, c_m2, c_m3 = st.columns(3)
total_stock = df_inventario["Stock"].sum()
inv_total = (df_inventario["Stock"] * df_inventario["Compra"]).sum()
with c_m1: st.metric("Total Prendas", f"{total_stock} uds")
with c_m2: st.metric("Inversión Total", f"{inv_total:,.2f} €")
with c_m3: st.metric("Categorías", len(df_inventario["Categoria"].unique()))
st.divider()

tab1, tab2 = st.tabs(["➕ Registrar Prenda", "📋 Ver e Interactuar"])

# --- TAB 1: REGISTRO ---
with tab1:
    if 'modo_registro' not in st.session_state: st.session_state.modo_registro = None

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("📸 Registrar por Imagen", use_container_width=True):
            st.session_state.modo_registro = "imagen"
            if 'datos_ia' in st.session_state: del st.session_state.datos_ia
    with col_btn2:
        if st.button("📝 Registro Manual", use_container_width=True):
            st.session_state.modo_registro = "manual"

    # OPERATIVA IMAGEN
    if st.session_state.modo_registro == "imagen":
        archivo_foto = st.file_uploader("Sube la foto", type=["jpg", "png", "jpeg"])
        if archivo_foto:
            if 'datos_ia' not in st.session_state:
                with st.spinner("🤖 Analizando..."):
                    img = Image.open(archivo_foto)
                    res = model.generate_content(["Analiza: CATEGORIA / COLOR. Solo texto.", img])
                    try:
                        p = res.text.split("/")
                        st.session_state.datos_ia = {"cat": p[0].strip(), "color": p[1].strip()}
                    except:
                        st.session_state.datos_ia = {"cat": "", "color": ""}
            
            # Lógica de autocompletado
            cat_ia = st.session_state.datos_ia["cat"]
            col_ia = st.session_state.datos_ia["color"]
            
            # Buscar si ya existe algo igual
            match = df_inventario[(df_inventario["Categoria"].str.lower() == cat_ia.lower()) & (df_inventario["Color"].str.lower() == col_ia.lower())]
            
            id_f, t_f, c_f, v_f = str(nuevo_id_sug), "", 0.0, 0.0
            if not match.empty:
                art = match.iloc[0]
                id_f, t_f, c_f, v_f = str(art['ID']), str(art['Talla']), float(art['Compra']), float(art['Venta'])
                st.info(f"💡 Se encontró una coincidencia (ID: {id_f}). Datos cargados.")

            with st.form("form_ia"):
                e_id = st.text_input("ID (Alfanumérico)", value=id_f)
                c1, c2 = st.columns(2)
                e_cat = c1.text_input("Categoría", value=cat_ia)
                e_col = c2.text_input("Color", value=col_ia)
                e_talla = c1.text_input("Talla", value=t_f)
                e_stock = c2.number_input("Cantidad", min_value=1)
                e_compra = c1.number_input("Compra (€)", value=c_f)
                e_venta = c2.number_input("Venta (€)", value=v_f)
                
                if st.form_submit_button("GUARDAR"):
                    with st.spinner("Subiendo..."):
                        res_c = cloudinary.uploader.upload(archivo_foto.getvalue(), folder="inventario", public_id=f"foto_{e_id}")
                        nueva = pd.DataFrame([{"ID": e_id, "Categoria": e_cat, "Fecha": datetime.now().strftime('%Y-%m-%d'), "Talla": e_talla, "Color": e_col, "Compra": e_compra, "Venta": e_venta, "Stock": e_stock, "Image_Ref": res_c['secure_url']}])
                        df_f = pd.concat([df_inventario[df_inventario["ID"].astype(str) != str(e_id)], nueva], ignore_index=True)
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_f)
                        st.session_state.modo_registro = None
                        st.rerun()

    # OPERATIVA MANUAL
    elif st.session_state.modo_registro == "manual":
        with st.form("form_man"):
            e_id = st.text_input("ID", value=str(nuevo_id_sug))
            e_cat = st.text_input("Categoría")
            e_col = st.text_input("Color")
            e_talla = st.text_input("Talla")
            e_stock = st.number_input("Stock", min_value=1)
            e_compra = st.number_input("Compra (€)")
            e_venta = st.number_input("Venta (€)")
            if st.form_submit_button("GUARDAR MANUAL"):
                nueva = pd.DataFrame([{"ID": e_id, "Categoria": e_cat, "Fecha": datetime.now().strftime('%Y-%m-%d'), "Talla": e_talla, "Color": e_col, "Compra": e_compra, "Venta": e_venta, "Stock": e_stock, "Image_Ref": URL_SIN_IMAGEN}])
                df_f = pd.concat([df_inventario[df_inventario["ID"].astype(str) != str(e_id)], nueva], ignore_index=True)
                conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_f)
                st.session_state.modo_registro = None
                st.rerun()

# --- TAB 2: INVENTARIO ---
with tab2:
    st.subheader("📋 Tabla de Control")
    
    # Buscador
    bus = st.text_input("🔍 Buscar por ID, Categoría o Color").lower()
    df_ver = df_inventario.copy()
    if bus:
        df_ver = df_ver[df_ver.apply(lambda r: bus in str(r.values).lower(), axis=1)]

    # --- MINIATURAS HTML ---
    df_tab = df_ver.copy()
    df_tab['Vista'] = df_tab['Image_Ref'].apply(lambda x: f'<img src="{x}" height="50px" style="border-radius:5px">')
    
    # Reordenar para que la imagen sea lo primero
    cols = ['Vista', 'ID', 'Categoria', 'Color', 'Talla', 'Stock', 'Compra', 'Venta', 'Fecha']
    
    st.markdown("""<style>
        table {width: 100%; border-collapse: collapse;}
        th {background-color: #f0f2f6 !important; color: black !important;}
        td {text-align: center !important; vertical-align: middle !important;}
    </style>""", unsafe_allow_html=True)
    
    st.markdown(df_tab[cols].to_html(escape=False, index=False), unsafe_allow_html=True)

    st.divider()

    # --- EDITOR Y ELIMINACIÓN ---
    st.subheader("🛠️ Editor Maestro")
    ids_list = ["-- Seleccionar --"] + df_ver["ID"].astype(str).tolist()
    sel = st.selectbox("Elegir ID para editar o borrar", ids_list)

    if sel != "-- Seleccionar --":
        idx = df_inventario.index[df_inventario['ID'].astype(str) == sel].tolist()[0]
        dat = df_inventario.loc[idx]
        
        c_i, c_e = st.columns([1, 2])
        with c_i:
            st.image(dat["Image_Ref"], use_container_width=True)
            new_photo = st.file_uploader("Cambiar foto", type=['jpg','png'])
        
        with c_e:
            with st.form("edit_form"):
                ed_id = st.text_input("ID", value=str(dat["ID"]))
                ed_cat = st.text_input("Categoría", value=str(dat["Categoria"]))
                col1, col2 = st.columns(2)
                ed_talla = col1.text_input("Talla", value=str(dat["Talla"]))
                ed_color = col2.text_input("Color", value=str(dat["Color"]))
                ed_stock = col1.number_input("Stock", value=int(dat["Stock"]))
                ed_compra = col2.number_input("Compra", value=float(dat["Compra"]))
                ed_venta = col1.number_input("Venta", value=float(dat["Venta"]))
                ed_fecha = col2.text_input("Fecha", value=str(dat["Fecha"]))
                
                if st.form_submit_button("💾 ACTUALIZAR"):
                    url_f = dat["Image_Ref"]
                    if new_photo:
                        res = cloudinary.uploader.upload(new_photo.getvalue(), folder="inventario", public_id=f"foto_{ed_id}")
                        url_f = res['secure_url']
                    
                    df_inventario.loc[idx] = [ed_id, ed_cat, ed_fecha, ed_talla, ed_color, ed_compra, ed_venta, ed_stock, url_f]
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_inventario)
                    st.success("¡Actualizado!")
                    st.rerun()

        if st.button("🗑️ ELIMINAR ESTE PRODUCTO", type="primary"):
            df_new = df_inventario.drop(idx)
            conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_new)
            st.rerun()

    # --- ANÁLISIS ---
    st.divider()
    st.subheader("📈 Análisis de Gastos")
    if not df_inventario.empty:
        df_inv = df_inventario.copy()
        df_inv["Total_Inv"] = df_inv["Compra"] * df_inv["Stock"]
        fig = px.pie(df_inv, values='Total_Inv', names='Categoria', hole=.4, title="Inversión por Categoría")
        st.plotly_chart(fig, use_container_width=True)
        

