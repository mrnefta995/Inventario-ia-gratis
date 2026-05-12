import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. Configuración de IA y Base de Datos
# Configuración ultra-compatible
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
# Probamos con el nombre que Google está forzando ahora
model = genai.GenerativeModel('gemini-1.5-flash-latest') 

# Conexión a Google Sheets (Usará la URL de los Secrets)
conn = st.connection("gsheets", type=GSheetsConnection)

st.set_page_config(page_title="Inventario IA Real", layout="wide")
st.title("👕 Mi Almacén Permanente")

# Función para leer datos actuales
def leer_inventario():
    return conn.read(spreadsheet=st.secrets["spreadsheet_url"], usecols=[0,1,2,3,4,5,6])

# --- PESTAÑAS ---
tab1, tab2 = st.tabs(["➕ Añadir Prenda", "📋 Ver Almacén"])

with tab1:
    foto = st.file_uploader("Subir foto", type=['jpg', 'jpeg', 'png'])
    if foto:
        img = Image.open(foto)
        st.image(img, width=200)
        
        if st.button("🤖 Analizar Prenda"):
            with st.spinner("Leyendo prenda..."):
                try:
                    # Usamos el nombre directo del modelo
                    model_fast = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = "Analiza esta prenda. Responde solo: Categoria, Color."
                    
                    # Mandamos la imagen directamente
                    response = model_fast.generate_content([prompt, Image.open(foto)])
                    
                    if response.text:
                        st.session_state.temp = {
                            "detalles": response.text,
                            "id": f"REF-{datetime.now().strftime('%M%S')}"
                        }
                        st.rerun()
                except Exception as e:
                    st.error(f"Nota: Si sale error 404, prueba a cambiar el nombre del modelo a 'gemini-1.5-pro'. Error actual: {e}")

        if 'temp' in st.session_state:
            with st.form("registro"):
                f_id = st.text_input("ID (Editable)", value=st.session_state.temp['id'])
                f_cat = st.text_input("Categoría", value=st.session_state.temp['detalles'][0])
                f_talla = st.text_input("Talla")
                f_c = st.number_input("Precio Compra €")
                f_v = st.number_input("Precio Venta €")
                f_s = st.number_input("Cantidad", min_value=1)

                if st.form_submit_button("✅ Guardar"):
                    # Crear nueva fila
                    nueva_fila = pd.DataFrame([[f_id, f_cat, f_talla, "Color", f_c, f_v, f_s]], 
                                            columns=["ID", "Categoria", "Talla", "Color", "Compra", "Venta", "Stock"])
                    # Leer datos viejos, añadir nueva y actualizar
                    df_actual = leer_inventario()
                    df_final = pd.concat([df_actual, nueva_fila], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_final)
                    st.success("Guardado en Google Sheets")

with tab2:
    st.subheader("Datos en tiempo real")
    try:
        df = leer_inventario()
        st.dataframe(df)
    except:
        st.info("Todavía no hay datos o la URL es incorrecta.")
