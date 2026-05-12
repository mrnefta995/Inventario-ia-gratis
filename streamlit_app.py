import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE IA ---
# Forzamos la configuración de la API
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Usamos el nombre de modelo más estable para la API gratuita
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    st.error("⚠️ No se encontró la GEMINI_API_KEY en los Secrets de Streamlit.")

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Error de conexión a Sheets: {e}")

st.set_page_config(page_title="Inventario IA Pro", layout="wide")
st.title("👕 Gestor de Inventario Inteligente (Gratis)")

# Función para leer datos de Google Sheets
def leer_datos():
    return conn.read(spreadsheet=st.secrets["spreadsheet_url"])

# --- PESTAÑAS ---
tab1, tab2 = st.tabs(["➕ Añadir Prenda", "📋 Almacén Real"])

with tab1:
    foto = st.file_uploader("Saca una foto o sube imagen", type=['jpg', 'jpeg', 'png'])
    
    if foto:
        img_pil = Image.open(foto)
        st.image(img_pil, width=250, caption="Imagen cargada")
        
        if st.button("🤖 Analizar con IA"):
            with st.spinner("La IA está clasificando la prenda..."):
                try:
                    # Prompt optimizado para evitar errores de lectura
                    prompt = "Analiza esta prenda. Responde solo con este formato: CATEGORIA, COLOR. Ejemplo: Camiseta, Rojo"
                    response = model.generate_content([prompt, img_pil])
                    
                    # Procesar respuesta
                    resultado = response.text.split(',')
                    categoria_ia = resultado[0].strip() if len(resultado) > 0 else ""
                    color_ia = resultado[1].strip() if len(resultado) > 1 else ""
                    
                    # Generar ID automático sugerido
                    id_sugerido = f"REF-{datetime.now().strftime('%M%S')}"
                    
                    st.session_state.temp = {
                        "id": id_sugerido,
                        "cat": categoria_ia,
                        "col": color_ia
                    }
                except Exception as e:
                    st.error(f"Hubo un problema con la IA: {e}")
                    st.info("Revisa si tu API Key de Google AI Studio es correcta.")

        # Formulario de Registro
        if 'temp' in st.session_state:
            with st.form("form_registro"):
                st.subheader("Confirmar Datos")
                col1, col2 = st.columns(2)
                with col1:
                    f_id = st.text_input("ID Producto (Editable)", value=st.session_state.temp['id'])
                    f_cat = st.text_input("Categoría", value=st.session_state.temp['cat'])
                    f_talla = st.text_input("Talla (Escríbela aquí)")
                with col2:
                    f_col = st.text_input("Color", value=st.session_state.temp['col'])
                    f_compra = st.number_input("Precio Compra (€)", min_value=0.0, step=0.01)
                    f_venta = st.number_input("Precio Venta (€)", min_value=0.0, step=0.01)
                    f_stock = st.number_input("Stock inicial", min_value=1, value=1)
                
                if st.form_submit_button("✅ Guardar en Google Sheets"):
                    if not f_talla:
                        st.warning("⚠️ Debes introducir una talla.")
                    else:
                        try:
                            # Preparar nueva fila
                            nueva_fila = pd.DataFrame([[f_id, f_cat, f_talla, f_col, f_compra, f_venta, f_stock]], 
                                                    columns=["ID", "Categoria", "Talla", "Color", "Compra", "Venta", "Stock"])
                            
                            # Leer datos actuales, añadir y subir
                            df_actual = leer_datos()
                            df_final = pd.concat([df_actual, nueva_fila], ignore_index=True)
                            conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_final)
                            
                            st.success(f"¡Guardado con éxito! ID: {f_id}")
                            del st.session_state.temp # Limpiar formulario
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

with tab2:
    st.subheader("Inventario en Google Sheets")
    try:
        df = leer_datos()
        # Buscador básico
        buscar = st.text_input("Buscar por ID")
        if buscar:
            df = df[df['ID'].str.contains(buscar, case=False, na=False)]
        
        st.dataframe(df, use_container_width=True)
        
        if st.button("🔄 Refrescar Inventario"):
            st.rerun()
    except:
        st.info("Aún no hay datos. Registra tu primera prenda.")
