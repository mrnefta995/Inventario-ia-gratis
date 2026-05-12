import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURACIÓN DEL MODELO CORRECTO ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
# Usamos el modelo preview que te funciona
model = genai.GenerativeModel('gemini-3-flash-preview') 
conn = st.connection("gsheets", type=GSheetsConnection)

st.set_page_config(page_title="Almacén IA Pro", layout="wide")
st.title("👕 Gestor de Inventario con Fecha")

# Función de lectura sin caché para no perder datos
def leer_datos():
    df = conn.read(spreadsheet=st.secrets["spreadsheet_url"], ttl=0)
    if df.empty:
        return pd.DataFrame(columns=["ID", "Categoria", "Fecha", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"])
    return df

tab1, tab2 = st.tabs(["➕ Registrar Prenda", "📋 Ver Inventario"])

with tab1:
    foto = st.file_uploader("Subir foto", type=['jpg', 'jpeg', 'png'])
    if foto:
        st.image(Image.open(foto), width=200)
        if st.button("🤖 Analizar con IA Preview"):
            with st.spinner("Analizando..."):
                try:
                    # Prompt para separar categoría y color
                    prompt = "Analiza esta prenda. Responde solo en este formato: CATEGORIA / COLOR"
                    response = model.generate_content([prompt, Image.open(foto)])
                    
                    texto = response.text.replace("Categoría:", "").replace("Color:", "").strip()
                    partes = texto.split("/") if "/" in texto else [texto, ""]
                    
                    st.session_state.temp = {
                        "id": f"REF-{datetime.now().strftime('%M%S')}",
                        "cat": partes[0].strip(),
                        "col": partes[1].strip() if len(partes) > 1 else ""
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Error IA: {e}")

    if 'temp' in st.session_state:
        with st.form("registro_con_fecha"):
            col1, col2 = st.columns(2)
            with col1:
                f_id = st.text_input("ID Producto", value=st.session_state.temp['id'])
                f_cat = st.text_input("Categoría", value=st.session_state.temp['cat'])
                # La fecha se genera automáticamente al guardar, no hace falta campo de texto
                f_talla = st.text_input("Talla")
            with col2:
                f_col = st.text_input("Color", value=st.session_state.temp['col'])
                f_compra = st.number_input("Precio Compra €", format="%.2f")
                f_venta = st.number_input("Precio Venta €", format="%.2f")
            
            f_stock = st.number_input("Stock", min_value=1, value=1)

            if st.form_submit_button("✅ Guardar en Almacén"):
                df_actual = leer_datos()
                
                if f_id in df_actual['ID'].astype(str).values:
                    st.error("⚠️ El ID ya existe.")
                elif not f_talla:
                    st.warning("⚠️ Introduce la talla.")
                else:
                    # NUEVA FILA con la FECHA en la 3ª posición
                    nueva_fila = {
                        "ID": str(f_id),
                        "Categoria": str(f_cat),
                        "Fecha": datetime.now().strftime("%d/%m/%Y"), # 3ª Columna
                        "Talla": str(f_talla),
                        "Color": str(f_col),
                        "Compra": float(f_compra),
                        "Venta": float(f_venta),
                        "Stock": int(f_stock),
                        "Image_Ref": "Pendiente"
                    }
                    
                    # Unimos y forzamos el orden de las columnas
                    df_final = pd.concat([df_actual, pd.DataFrame([nueva_fila])], ignore_index=True)
                    columnas_orden = ["ID", "Categoria", "Fecha", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"]
                    df_final = df_final[columnas_orden]
                    
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_final)
                    
                    st.success(f"¡Guardado con éxito el día {nueva_fila['Fecha']}!")
                    del st.session_state.temp
                    st.rerun()

with tab2:
    st.subheader("Control de Stock")
    df_ver = leer_datos()
    st.dataframe(df_ver, use_container_width=True)
