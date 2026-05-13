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
    
        # 2. SELECTOR PARA GESTIÓN TOTAL Edicion (CRUD)
        st.divider()

        
        st.subheader("🛠️ Editor Maestro de Producto")
        id_seleccionado = st.selectbox("Selecciona el ID que deseas modificar:", ["-- Seleccionar --"] + df_ver["ID"].tolist())

        if id_seleccionado != "-- Seleccionar --":
            # Extraemos el índice y los datos actuales
            item_index = df_ver.index[df_ver['ID'] == id_seleccionado].tolist()[0]
            datos = df_ver.loc[item_index]

            col_img, col_edit = st.columns([1, 2])

            with col_img:
                st.image(datos["Image_Ref"], caption=f"Referencia actual: {id_seleccionado}", width=250)
                st.caption(f"Registrado el: {datos['Fecha']}")

            with col_edit:
                with st.form("editor_completo"):
                    st.write(f"📝 Editando: **{id_seleccionado}**")
                    
                    e_cat = st.text_input("Categoría", value=str(datos["Categoria"]))
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        e_talla = st.text_input("Talla", value=str(datos["Talla"]))
                        e_compra = st.number_input("Precio Compra (€)", value=float(datos["Compra"]), step=0.01, format="%.2f")
                        e_stock = st.number_input("Unidades en Stock", value=int(datos["Stock"]), min_value=0)
                    with c2:
                        e_color = st.text_input("Color", value=str(datos["Color"]))
                        e_venta = st.number_input("Precio Venta (€)", value=float(datos["Venta"]), step=0.01, format="%.2f")
                        e_fecha = st.text_input("Fecha (dd/mm/aaaa)", value=str(datos["Fecha"]))

                    # BOTONES DENTRO DEL FORMULARIO
                    submit_edit = st.form_submit_button("💾 Guardar todos los cambios", use_container_width=True)
                
                # Botón de borrar fuera del formulario de edición por seguridad
                if st.button("🗑️ ELIMINAR PRODUCTO PERMANENTEMENTE", type="primary", use_container_width=True):
                    df_nuevo = df_ver.drop(item_index)
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_nuevo)
                    st.warning(f"Producto {id_seleccionado} eliminado.")
                    st.rerun()

                if submit_edit:
                    # Actualizamos todos los valores en el DataFrame
                    df_ver.at[item_index, "Categoria"] = e_cat
                    df_ver.at[item_index, "Talla"] = e_talla
                    df_ver.at[item_index, "Color"] = e_color
                    df_ver.at[item_index, "Compra"] = e_compra
                    df_ver.at[item_index, "Venta"] = e_venta
                    df_ver.at[item_index, "Stock"] = e_stock
                    df_ver.at[item_index, "Fecha"] = e_fecha
                    
                    # Subimos a Google Sheets
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_ver)
                    st.success(f"¡{id_seleccionado} actualizado correctamente!")
                    st.rerun()

        # Botón opcional para refrescar si haces cambios manuales en el Sheets
        if st.button("🔄 Actualizar lista"):
            st.rerun()
        
        
          # 3. SECCIÓN VISUAL: GRÁFICO Y TABLA RESUMEN CON TOTAL
        st.divider()
        st.subheader("📊 Análisis de Inversión por Categoría")
        
        # Agrupamos por categoría y sumamos el gasto
        df_gastos = df_ver.groupby("Categoria")["Total_Invertido"].sum().reset_index()
        
        # --- CÁLCULO DE LA FILA TOTAL ---
        total_suma = df_gastos["Total_Invertido"].sum()
        fila_total = pd.DataFrame([{"Categoria": "TOTAL INVERTIDO EN ALMACÉN", "Total_Invertido": total_suma}])
        
        # Unimos la tabla de categorías con la fila del total
        df_resumen_final = pd.concat([df_gastos.sort_values(by="Total_Invertido", ascending=False), fila_total], ignore_index=True)

        col_graf, col_tabla = st.columns([1.2, 1]) # El gráfico un poco más ancho que la tabla

        with col_graf:
            import plotly.express as px
            fig = px.pie(
                df_gastos, 
                values='Total_Invertido', 
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
                    "Total_Invertido": st.column_config.NumberColumn("Inversión", format="%.2f €")
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

        

