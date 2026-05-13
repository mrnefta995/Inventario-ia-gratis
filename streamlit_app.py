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

st.title("👕 Gestor de Inventario con Fecha")

URL_SIN_IMAGEN = "https://res.cloudinary.com/daquubngv/image/upload/v1778660130/sin_imagen_zy2jcx.jpg"

def leer_datos():
    df = conn.read(spreadsheet=st.secrets["spreadsheet_url"], ttl=0)
    if df.empty:
        return pd.DataFrame(columns=["ID", "Categoria", "Fecha", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"])
    df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
    df['Compra'] = pd.to_numeric(df['Compra'], errors='coerce').fillna(0.0)
    df['Venta'] = pd.to_numeric(df['Venta'], errors='coerce').fillna(0.0)
    return df

df_inventario = leer_datos()

# --- CÁLCULO DE NUEVO ID ---
try:
    ids_num = pd.to_numeric(df_inventario["ID"], errors='coerce').dropna()
    nuevo_id_sug = int(ids_num.max()) + 1 if not ids_num.empty else 1
except:
    nuevo_id_sug = 1

tab1, tab2 = st.tabs(["➕ Registrar Prenda", "📋 Ver e Interactuar"])

# --- TAB 1: REGISTRO (Sin cambios) ---
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
    
    if st.session_state.modo_registro == "imagen":
        archivo_foto = st.file_uploader("Sube la foto", type=["jpg", "png", "jpeg"])
        if archivo_foto:
            if 'datos_ia' not in st.session_state:
                with st.spinner("🤖 Analizando..."):
                    img_pil = Image.open(archivo_foto)
                    prompt = "Analiza la prenda. Responde ESTRICTAMENTE: CATEGORIA / COLOR."
                    resp = model.generate_content([prompt, img_pil])
                    try:
                        p = resp.text.split("/")
                        st.session_state.datos_ia = {"cat": p[0].strip(), "color": p[1].strip()}
                    except:
                        st.session_state.datos_ia = {"cat": "Revisar", "color": "Revisar"}
            
            c_ia, cl_ia = st.session_state.datos_ia["cat"], st.session_state.datos_ia["color"]
            match = df_inventario[(df_inventario["Categoria"].str.lower() == c_ia.lower()) & (df_inventario["Color"].str.lower() == cl_ia.lower())]
            id_f, t_f, cp_f, vt_f = str(nuevo_id_sug), "", 0.0, 0.0
            if not match.empty:
                art = match.iloc[0]
                id_f, t_f, cp_f, vt_f = str(art['ID']), str(art['Talla']), float(art['Compra']), float(art['Venta'])

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
                    res_c = cloudinary.uploader.upload(archivo_foto.getvalue(), folder="inventario", public_id=f"foto_{f_id}")
                    nueva = pd.DataFrame([{"ID": f_id, "Categoria": f_cat, "Fecha": datetime.now().strftime('%Y-%m-%d'), "Talla": f_talla, "Color": f_col, "Compra": f_compra, "Venta": f_venta, "Stock": f_stock, "Image_Ref": res_c['secure_url']}])
                    df_f = pd.concat([df_inventario[df_inventario["ID"].astype(str) != str(f_id)], nueva], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_f)
                    st.session_state.modo_registro = None
                    st.rerun()

    elif st.session_state.modo_registro == "manual":
        with st.form("form_manual"):
            f_id = st.text_input("ID", value=str(nuevo_id_sug))
            f_cat = st.text_input("Categoría"); f_col = st.text_input("Color")
            f_talla = st.text_input("Talla"); f_stock = st.number_input("Stock", min_value=1)
            f_compra = st.number_input("Compra (€)"); f_venta = st.number_input("Venta (€)")
            if st.form_submit_button("💾 GUARDAR MANUAL"):
                nueva = pd.DataFrame([{"ID": f_id, "Categoria": f_cat, "Fecha": datetime.now().strftime('%Y-%m-%d'), "Talla": f_talla, "Color": f_col, "Compra": f_compra, "Venta": f_venta, "Stock": f_stock, "Image_Ref": URL_SIN_IMAGEN}])
                df_f = pd.concat([df_inventario[df_inventario["ID"].astype(str) != str(f_id)], nueva], ignore_index=True)
                conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_f)
                st.session_state.modo_registro = None
                st.rerun()

# --- TAB 2: INVENTARIO ---
with tab2:
    st.subheader("📋 Control de Stock Visual")
    
    bus = st.text_input("🔍 Buscar por ID, Categoría o Color").lower()
    df_ver = df_inventario.copy()
    if bus:
        df_ver = df_ver[df_ver.apply(lambda r: bus in str(r.values).lower(), axis=1)]

    # --- MEJORAS DE FORMATO Y CLIC EN IMAGEN ---
    df_html = df_ver.copy()
    
    # 1. Imagen ampliable (Click para abrir en pestaña nueva)
    df_html['Vista'] = df_html['Image_Ref'].apply(
        lambda x: f'<a href="{x}" target="_blank"><img src="{x}" height="50px" style="border-radius:5px; cursor:zoom-in;" title="Click para ampliar"></a>'
    )
    
    # 2. Formateo de moneda (Compra y Venta)
    df_html['Compra'] = df_html['Compra'].apply(lambda x: f"{x:,.2f} €")
    df_html['Venta'] = df_html['Venta'].apply(lambda x: f"{x:,.2f} €")
    
    cols_tab = ['Vista', 'ID', 'Categoria', 'Color', 'Talla', 'Stock', 'Compra', 'Venta', 'Fecha']
    
    st.markdown("""<style>
        table {width: 100%; border-collapse: collapse; font-family: sans-serif;}
        th {background-color: #f0f2f6 !important; color: #31333f !important; padding: 12px !important;}
        td {text-align: center !important; vertical-align: middle !important; padding: 8px !important; border-bottom: 1px solid #e6e9ef;}
        tr:hover {background-color: #f8f9fb;}
    </style>""", unsafe_allow_html=True)
    
    st.markdown(df_html[cols_tab].to_html(escape=False, index=False), unsafe_allow_html=True)

    # --- EDITOR Y ELIMINACIÓN (Sin cambios) ---
    st.divider()
    st.subheader("🛠️ Gestión de Fichas")
    sel_id = st.selectbox("ID para editar:", ["-- Elegir --"] + df_ver["ID"].astype(str).tolist())

    if sel_id != "-- Elegir --":
        idx_match = df_inventario.index[df_inventario['ID'].astype(str) == sel_id].tolist()[0]
        datos_p = df_inventario.loc[idx_match]
        col_f, col_d = st.columns([1, 2])
        with col_f:
            st.image(datos_p["Image_Ref"], use_container_width=True)
            nueva_f = st.file_uploader("Actualizar foto", type=['jpg','png'])
        with col_d:
            with st.form("edit_master"):
                ed_id = st.text_input("ID", value=str(datos_p["ID"]))
                ed_cat = st.text_input("Categoría", value=str(datos_p["Categoria"]))
                cx1, cx2 = st.columns(2)
                ed_talla = cx1.text_input("Talla", value=str(datos_p["Talla"]))
                ed_color = cx2.text_input("Color", value=str(datos_p["Color"]))
                ed_stock = cx1.number_input("Stock", value=int(datos_p["Stock"]))
                ed_compra = cx2.number_input("Compra", value=float(datos_p["Compra"]))
                ed_venta = cx1.number_input("Venta", value=float(datos_p["Venta"]))
                ed_fecha = cx2.text_input("Fecha", value=str(datos_p["Fecha"]))
                if st.form_submit_button("💾 APLICAR CAMBIOS"):
                    url_dest = datos_p["Image_Ref"]
                    if nueva_f:
                        res = cloudinary.uploader.upload(nueva_f.getvalue(), folder="inventario", public_id=f"foto_{ed_id}")
                        url_dest = res['secure_url']
                    df_inventario.loc[idx_match] = [ed_id, ed_cat, ed_fecha, ed_talla, ed_color, ed_compra, ed_venta, ed_stock, url_dest]
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_inventario)
                    st.rerun()
        if st.button("🗑️ ELIMINAR ARTÍCULO", type="primary", use_container_width=True):
            df_del = df_inventario.drop(idx_match)
            conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_del)
            st.rerun()

    # --- GRÁFICO CON LEYENDA ENMARCADA ---
    st.divider()
    if not df_inventario.empty:
        df_inv = df_inventario.copy()
        df_inv["Inversion"] = df_inv["Compra"] * df_inv["Stock"]
        fig = px.pie(df_inv, values='Inversion', names='Categoria', hole=.4, 
                     title="Distribución de la Inversión (€)",
                     color_discrete_sequence=px.colors.qualitative.Safe)
        
        # Mejora visual de la leyenda (Recuadro y borde)
        fig.update_layout(
            legend=dict(
                bgcolor="rgba(255, 255, 255, 0.8)", # Fondo blanco semitransparente
                bordercolor="Black",                # Borde negro
                borderwidth=1,                      # Grosor del borde
                title_font_family="sans-serif",
                font=dict(size=12, color="black")
            )
        )
        st.plotly_chart(fig, use_container_width=True)
