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

        # 2. SELECTOR MAESTRO
        opciones_id = df_ver.apply(lambda x: f"{x['ID']} - {x['Categoria']}", axis=1).tolist()
        
        # Usamos session_state para mantener la selección después del guardado
        # Si no existe en sesión, ponemos el valor por defecto
        if "prenda_seleccionada" not in st.session_state:
            st.session_state.prenda_seleccionada = "-- Elige una prenda --"

        seleccion = st.selectbox(
            "Selecciona una prenda:", 
            ["-- Elige una prenda --"] + opciones_id,
            index=(["-- Elige una prenda --"] + opciones_id).index(st.session_state.prenda_seleccionada)
        )

        if seleccion != "-- Elige una prenda --":
            st.session_state.prenda_seleccionada = seleccion # Actualizamos la sesión
            
            id_original = seleccion.split(" - ")[0]
            item_index = df_ver.index[df_ver['ID'].astype(str) == id_original].tolist()
            datos = df_ver.loc[item_index]

            col_img, col_edit = st.columns([1, 2])

            with col_img:
                st.image(datos["Image_Ref"].values[0], caption=f"ID: {id_original}", use_container_width=True)

            with col_edit:
                # CREAMOS DOS BOTONES DE GUARDADO DIFERENTES
                with st.form("editor_maestro_continuo"):
                    # ... (Todos tus campos text_input y number_input aquí igual que antes) ...
                    nuevo_id = st.text_input("ID Producto", value=str(datos["ID"].values[0]))
                    e_cat = st.text_input("Categoría", value=str(datos["Categoria"].values[0]))
                    # (Añade el resto de campos: talla, color, compra, venta, stock, fecha...)
                    
                    st.write("---")
                    c_btn1, c_btn2 = st.columns(2)
                    guardar_continuar = c_btn1.form_submit_button("💾 Guardar y Seguir")
                    guardar_salir = c_btn2.form_submit_button("🚪 Guardar y Salir")

                # LÓGICA DE GUARDADO
                if guardar_continuar or guardar_salir:
                    # Actualizamos el DataFrame (igual que antes)
                    df_ver.loc[item_index, "ID"] = nuevo_id
                    # ... (Actualiza todos los campos e_cat, e_talla, etc.) ...
                    
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_ver)
                    st.success("✅ ¡Cambios guardados!")
                    
                    if guardar_salir:
                        st.session_state.prenda_seleccionada = "-- Elige una prenda --"
                    else:
                        # Si continuamos, actualizamos la etiqueta del selector por si cambió el ID o Categoría
                        st.session_state.prenda_seleccionada = f"{nuevo_id} - {e_cat}"
                    
                    st.rerun()

                # BOTÓN ELIMINAR (Siempre sale del editor al borrar)
                if st.button("🗑️ ELIMINAR PRENDA", type="primary", use_container_width=True):
                    df_nuevo = df_ver.drop(item_index)
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_nuevo)
                    st.session_state.prenda_seleccionada = "-- Elige una prenda --"
                    st.warning("Prenda eliminada.")
                    st.rerun()


        # Botón opcional para refrescar si haces cambios manuales en el Sheets
        if st.button("🔄 Actualizar lista"):
            st.rerun()
        
        # 2. SECCIÓN VISUAL (Aquí es donde calculamos sin guardar en el inventario)
        st.divider()
        st.subheader("📊 Análisis de Inversión por Categoría")
        
        # Creamos una copia temporal solo para el gráfico
        df_calculo = df_ver.copy()
        df_calculo["Inversion_Temp"] = df_calculo["Compra"] * df_calculo["Stock"]
        
        # Agrupamos usando la columna temporal
        df_gastos = df_calculo.groupby("Categoria")["Inversion_Temp"].sum().reset_index()
        
        # Fila de TOTAL
        total_suma = df_gastos["Inversion_Temp"].sum()
        fila_total = pd.DataFrame([{"Categoria": "TOTAL INVERTIDO EN ALMACÉN", "Inversion_Temp": total_suma}])
        
        # Tabla resumen final para mostrar
        df_resumen_final = pd.concat([df_gastos.sort_values(by="Inversion_Temp", ascending=False), fila_total], ignore_index=True)

        col_graf, col_tabla = st.columns([1.2, 1])

        with col_graf:
            import plotly.express as px
            fig = px.pie(
                df_gastos, 
                values='Inversion_Temp', 
                names='Categoria',
                hole=0.5,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_traces(textinfo='percent', hovertemplate="%{label}<br>%{value:.2f} €")
            st.plotly_chart(fig, use_container_width=True)

        with col_tabla:
            st.write("💰 **Desglose de gastos:**")
            st.dataframe(
                df_resumen_final,
                column_config={
                    "Categoria": st.column_config.TextColumn("Categoría / Concepto"),
                    "Inversion_Temp": st.column_config.NumberColumn("Inversión", format="%.2f €")
                },
                hide_index=True,
                use_container_width=True
            )


        # --- Cálculo rápido de inversión ---
        total_inv = (df_ver["Compra"] * df_ver["Stock"]).sum()
        st.divider()
        st.metric("Inversión Total en Almacén", f"{total_inv:,.2f} €")

      
        # 3. BOTÓN DE DESCARGA (Exportar)
        st.divider()
        csv = df_ver.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Inventario completo (CSV)", data=csv, file_name="inventario_real.csv", mime="text/csv")
      
    else:
        st.info("El inventario está vacío. Registra tu primera prenda.")
        st.info("Aún no hay prendas registradas.")

        

