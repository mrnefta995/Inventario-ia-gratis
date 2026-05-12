import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime

# 1. Configuración de la IA (Usará la clave de los Secrets)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Falta la clave API en los Secrets.")

st.set_page_config(page_title="Inventario Ropa Gratis", layout="wide")
st.title("👕 Mi Almacén de Ropa IA (Gratis)")

# 2. Base de datos persistente (Simulada en la sesión)
if 'db' not in st.session_state:
    st.session_state.db = pd.DataFrame(columns=["ID", "Categoría", "Talla", "Color", "Compra", "Venta", "Stock"])

tab1, tab2 = st.tabs(["➕ Añadir Prenda", "📋 Ver / Editar Almacén"])

with tab1:
    foto = st.file_uploader("Saca o sube una foto de la prenda", type=['jpg', 'jpeg', 'png'])
    
    if foto:
        img = Image.open(foto)
        st.image(img, width=250, caption="Prenda detectada")
        
        if st.button("🤖 Analizar con IA"):
            with st.spinner("Leyendo prenda..."):
                # Prompt detallado para Gemini
                prompt = "Analiza esta prenda de ropa. Responde solo con texto separado por comas: Categoria, Color, Material."
                response = model.generate_content([prompt, img])
                detalles = response.text.split(',')
                
                # Guardar datos temporales para el formulario
                st.session_state.temp = {
                    "cat": detalles[0].strip() if len(detalles) > 0 else "",
                    "col": detalles[1].strip() if len(detalles) > 1 else "",
                    "id": f"REF-{datetime.now().strftime('%M%S')}"
                }

        if 'temp' in st.session_state:
            with st.form("registro"):
                col1, col2 = st.columns(2)
                with col1:
                    f_id = st.text_input("ID Producto (Puedes cambiarlo)", value=st.session_state.temp['id'])
                    f_cat = st.text_input("Categoría", value=st.session_state.temp['cat'])
                    f_talla = st.text_input("Talla (Obligatorio)")
                    f_col = st.text_input("Color", value=st.session_state.temp['col'])
                with col2:
                    f_compra = st.number_input("Precio Compra €", min_value=0.0, step=0.1)
                    f_venta = st.number_input("Precio Venta €", min_value=0.0, step=0.1)
                    f_stock = st.number_input("Cantidad", min_value=1, value=1)
                
                if st.form_submit_button("✅ Guardar en Inventario"):
                    if not f_talla:
                        st.warning("Escribe la talla antes de guardar.")
                    else:
                        nueva_prenda = pd.DataFrame([[f_id, f_cat, f_talla, f_col, f_compra, f_venta, f_stock]], 
                                                  columns=st.session_state.db.columns)
                        st.session_state.db = pd.concat([st.session_state.db, nueva_prenda], ignore_index=True)
                        st.success(f"¡Guardado! ID: {f_id}")

with tab2:
    st.subheader("Estado del Almacén")
    if not st.session_state.db.empty:
        # Buscador por ID
        busqueda = st.text_input("Buscar por ID para borrar o editar")
        if busqueda:
            resultado = st.session_state.db[st.session_state.db['ID'] == busqueda]
            if not resultado.empty:
                st.write(resultado)
                if st.button("🗑️ Borrar este ID"):
                    st.session_state.db = st.session_state.db[st.session_state.db['ID'] != busqueda]
                    st.rerun()
        
        st.divider()
        st.dataframe(st.session_state.db, use_container_width=True)
    else:
        st.info("El inventario está vacío.")
