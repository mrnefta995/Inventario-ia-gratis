import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import cloudinary
import cloudinary.uploader

# --- CONFIG CLOUDINARY ---
cloudinary.config( 
  cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"], 
  api_key = st.secrets["CLOUDINARY_API_KEY"], 
  api_secret = st.secrets["CLOUDINARY_API_SECRET"] 
)

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
                f_compra = st.number_input("Precio Compra €", format="%.2f", min_value=0.0)
                f_venta = st.number_input("Precio Venta €", format="%.2f", min_value=0.0)
            
            f_stock = st.number_input("Stock", min_value=1, value=1)

            if st.form_submit_button("✅ Guardar en Almacén"):
                df_actual = leer_datos()
                
                # 1. Validaciones previas
                if f_id in df_actual['ID'].astype(str).values:
                    st.error("⚠️ El ID ya existe.")
                elif not f_talla:
                    st.warning("⚠️ Introduce la talla.")
                else:
                    try:
                        with st.spinner("Subiendo imagen y guardando datos..."):
                            # 2. Subida a Cloudinary
                            resultado_subida = cloudinary.uploader.upload(
                                foto.getvalue(), 
                                folder="inventario_ropa"
                            )
                            url_foto = resultado_subida['secure_url'] 
                
                            # 3. Preparar la nueva fila con el orden correcto de columnas
                            nueva_fila = {
                                "ID": str(f_id),
                                "Categoria": str(f_cat),
                                "Fecha": datetime.now().strftime("%d/%m/%Y"),
                                "Talla": str(f_talla),
                                "Color": str(f_col),
                                "Compra": float(f_compra),
                                "Venta": float(f_venta),
                                "Stock": int(f_stock),
                                "Image_Ref": url_foto 
                            }

                            # 4. Unir datos y asegurar orden de columnas (evita duplicados)
                            df_final = pd.concat([df_actual, pd.DataFrame([nueva_fila])], ignore_index=True)
                            columnas_orden = ["ID", "Categoria", "Fecha", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"]
                            df_final = df_final[columnas_orden]

                            # 5. Actualizar Google Sheets
                            conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_final)
                            
                            st.success(f"¡Guardado con éxito! ID: {f_id}")
                            st.balloons()
                            
                            # Limpiar y recargar
                            if 'temp' in st.session_state:
                                del st.session_state.temp
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error crítico al guardar: {e}")


with tab2:
    st.subheader("📋 Control de Stock y Finanzas")
    df_ver = leer_datos()
    
    if not df_ver.empty:
      # TRUCO: Limpiamos posibles espacios en los links que impiden que se vea la imagen
        if "Image_Ref" in df_ver.columns:
            df_ver["Image_Ref"] = df_ver["Image_Ref"].astype(str).str.strip()

        # Mostramos la tabla con configuración de columnas para los Euros
        st.dataframe(
            df_ver,
            column_config={
                "ID": st.column_config.TextColumn("ID"),
                "Categoria": st.column_config.TextColumn("Categoría"),
                "Fecha": st.column_config.TextColumn("Fecha Registro"),
                "Talla": st.column_config.TextColumn("Talla"),
                "Color": st.column_config.TextColumn("Color"),
                "Compra": st.column_config.NumberColumn(
                    "Precio Compra",
                    format="%.2f €"  # <--- Esto añade el formato Euro
                ),
                "Venta": st.column_config.NumberColumn(
                    "Precio Venta",
                    format="%.2f €"  # <--- Esto añade el formato Euro
                ),
                "Stock": st.column_config.NumberColumn("Unidades", format="%d uds"),
                "Image_Ref": st.column_config.TextColumn("Vista Previa",
                help="Foto de la prenda",
                width="medium" # Le damos un tamaño medio para que se vea mejor
                )                                               
            },
            use_container_width=True,
            hide_index=True
          )
        st.divider()
        buscar_id = st.text_input("🔍 Buscar ID para ver foto grande")
        if buscar_id:
            res = df_ver[df_ver['ID'].astype(str) == buscar_id]
            if not res.empty:
                url = res['Image_Ref'].values[0]
                st.image(url, width=350, caption=f"ID: {buscar_id}")
            else:
                st.error("No se encontró el ID.")

        else:
            st.info("Aún no hay prendas registradas.")
        # Botón opcional para refrescar si haces cambios manuales en el Sheets
        if st.button("🔄 Actualizar lista"):
            st.rerun()
        # --- Cálculo rápido de inversión ---
        total_inv = (df_ver["Compra"] * df_ver["Stock"]).sum()
        st.divider()
        st.metric("Inversión Total en Almacén", f"{total_inv:,.2f} €")
        
    else:
        st.info("El inventario está vacío. Registra tu primera prenda.")
        st.info("Aún no hay prendas registradas.")

        st.divider()

        # 2. SELECTOR PARA EDITAR O BORRAR
        st.subheader("🛠️ Acciones sobre Producto")
        id_seleccionado = st.selectbox("Selecciona un ID para gestionar:", ["-- Seleccionar --"] + df_ver["ID"].tolist())

        if id_seleccionado != "-- Seleccionar --":
            # Extraemos los datos actuales de ese producto
            item_index = df_ver.index[df_ver['ID'] == id_seleccionado].tolist()[0]
            datos_item = df_ver.iloc[item_index]

            col_img, col_form = st.columns([1, 2])

            with col_img:
                st.image(datos_item["Image_Ref"], caption=f"ID: {id_seleccionado}", width=200)

            with col_form:
                with st.expander(f"Editar / Borrar {id_seleccionado}", expanded=True):
                    # Campos de edición
                    new_stock = st.number_input("Actualizar Stock", value=int(datos_item["Stock"]), min_value=0)
                    new_venta = st.number_input("Actualizar Precio Venta (€)", value=float(datos_item["Venta"]), step=0.01)
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    # BOTÓN ACTUALIZAR (Update)
                    if col_btn1.button("💾 Guardar Cambios"):
                        df_ver.at[item_index, "Stock"] = new_stock
                        df_ver.at[item_index, "Venta"] = new_venta
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_ver)
                        st.success("¡Datos actualizados!")
                        st.rerun()

                    # BOTÓN BORRAR (Delete)
                    if col_btn2.button("🗑️ Eliminar Producto", type="primary"):
                        df_nuevo = df_ver.drop(item_index)
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_nuevo)
                        st.warning(f"Producto {id_seleccionado} eliminado.")
                        st.rerun()

        # 3. BOTÓN DE DESCARGA (Exportar)
        st.divider()
        csv = df_ver.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Inventario completo (CSV)", data=csv, file_name="inventario_real.csv", mime="text/csv")

