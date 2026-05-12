import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Configuración IA
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("👕 Almacén Inteligente con Referencia Visual")

# --- FUNCIONES CLAVE ---
def leer_datos():
    return conn.read(spreadsheet=st.secrets["spreadsheet_url"])

# --- PESTAÑAS ---
tab1, tab2 = st.tabs(["➕ Registro", "📋 Inventario"])

with tab1:
    foto = st.file_uploader("Foto de la prenda", type=['jpg', 'png', 'jpeg'])
    if foto:
        st.image(foto, width=200)
        if st.button("🤖 Analizar"):
            # (Mantener lógica de análisis anterior para llenar st.session_state.temp)
            response = model.generate_content(["Responde solo: Categoria, Color", Image.open(foto)])
            detalles = response.text.split(',')
            st.session_state.temp = {"id": f"REF-{datetime.now().strftime('%M%S')}", "cat": detalles[0], "col": detalles[1] if len(detalles)>1 else ""}

        if 'temp' in st.session_state:
            with st.form("registro"):
                f_id = st.text_input("ID Producto", value=st.session_state.temp['id'])
                f_cat = st.text_input("Categoría", value=st.session_state.temp['cat'])
                f_talla = st.text_input("Talla")
                f_compra = st.number_input("Compra €", step=0.01)
                f_venta = st.number_input("Venta €", step=0.01)
                f_stock = st.number_input("Stock", min_value=1)
                
                if st.form_submit_button("✅ Guardar"):
                    df = leer_datos()
                    
                    # EVITAR SOBREESCRIBIR: Verificar si el ID ya existe
                    if f_id in df['ID'].astype(str).values:
                        st.error(f"El ID {f_id} ya existe. Usa otro o edita en la pestaña Inventario.")
                    else:
                        nueva_fila = {
                            "ID": f_id, "Categoria": f_cat, "Talla": f_talla, 
                            "Color": st.session_state.temp['col'], "Compra": f_compra, 
                            "Venta": f_venta, "Stock": f_stock, "Imagen_Ref": "Ver en App"
                        }
                        df_final = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
                        # Forzar orden de columnas para evitar duplicados
                        df_final = df_final[["ID", "Categoria", "Talla", "Color", "Compra", "Venta", "Stock", "Imagen_Ref"]]
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_final)
                        st.success("Guardado correctamente")

with tab2:
    st.subheader("Buscador de Referencia")
    df_ver = leer_datos()
    id_buscar = st.text_input("Introduce ID para ver detalles")
    
    if id_buscar:
        item = df_ver[df_ver['ID'].astype(str) == id_buscar]
        if not item.empty:
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(item)
            with col_b:
                st.info("Nota: Para ver la imagen real aquí, necesitaríamos guardar la foto en un servidor como Google Drive o Imgur.")
        else:
            st.warning("ID no encontrado.")
    
    st.divider()
    st.dataframe(df_ver)
