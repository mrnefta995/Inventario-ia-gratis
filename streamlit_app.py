import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-3-flash-preview') # Modelo estable
conn = st.connection("gsheets", type=GSheetsConnection)

st.set_page_config(page_title="Almacén IA", layout="wide")
st.title("👕 Gestor de Inventario")

def read_data():
    df = conn.read(spreadsheet=st.secrets["spreadsheet_url"])
    if df.empty:
        return pd.DataFrame(columns=["ID", "Categoria", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"])
    return df

tab1, tab2 = st.tabs(["➕ Registrar", "📋 Inventario"])

with tab1:
    foto = st.file_uploader("Subir foto", type=['jpg', 'jpeg', 'png'])
    if foto:
        st.image(Image.open(foto), width=250)
        
        if st.button("🤖 Analizar Prenda"):
            with st.spinner("Analizando..."):
                try:
                    # PROMPT MEJORADO: Pedimos un formato muy específico
                    prompt = "Analiza esta prenda. Responde exclusivamente en este formato, sin añadir etiquetas: Categoria / Color. Ejemplo: Suéter / Rojo y beige"
                    response = model.generate_content([prompt, Image.open(foto)])
                    
                    # SEPARACIÓN SEGURA DE DATOS
                    texto_ia = response.text.replace("Categoría:", "").replace("Color:", "").strip()
                    if "/" in texto_ia:
                        partes = texto_ia.split("/")
                        cat_ia = partes[0].strip()
                        col_ia = partes[1].strip()
                    else:
                        cat_ia = texto_ia
                        col_ia = ""

                    st.session_state.temp = {
                        "id": f"REF-{datetime.now().strftime('%M%S')}",
                        "cat": cat_ia,
                        "col": col_ia
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Error IA: {e}")

        if 'temp' in st.session_state:
            with st.form("form_registro"):
                col1, col2 = st.columns(2)
                with col1:
                    f_id = st.text_input("ID Producto", value=st.session_state.temp['id'])
                    f_cat = st.text_input("Categoría", value=st.session_state.temp['cat'])
                    f_talla = st.text_input("Talla (Obligatorio)")
                with col2:
                    f_col = st.text_input("Color", value=st.session_state.temp['col'])
                    f_compra = st.number_input("Precio Compra €", min_value=0.0, step=0.01)
                    f_venta = st.number_input("Precio Venta €", min_value=0.0, step=0.01)
                
                f_stock = st.number_input("Cantidad", min_value=1, value=1)

                if st.form_submit_button("✅ Guardar"):
                    df_actual = read_data()
                    if f_id in df_actual['ID'].astype(str).values:
                        st.error("El ID ya existe.")
                    elif not f_talla:
                        st.warning("Falta la talla.")
                    else:
                        nueva_fila = pd.DataFrame([{
                            "ID": str(f_id), "Categoria": str(f_cat), "Talla": str(f_talla),
                            "Color": str(f_col), "Compra": float(f_compra), "Venta": float(f_venta),
                            "Stock": int(f_stock), "Image_Ref": "Pendiente"
                        }])
                        df_final = pd.concat([df_actual, nueva_fila], ignore_index=True)
                        df_final = df_final[["ID", "Categoria", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"]]
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_final)
                        st.success("¡Guardado!")
                        del st.session_state.temp
                        st.rerun()

with tab2:
    df_ver = read_data()
    st.dataframe(df_ver, use_container_width=True)
