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

# 1. Define la URL de la imagen negra "Sin Imagen"
URL_SIN_IMAGEN = "https://res.cloudinary.com/daquubngv/image/upload/v1778660130/sin_imagen_zy2jcx.jpg"
# Función de lectura sin caché para no perder datos
def leer_datos():
    df = conn.read(spreadsheet=st.secrets["spreadsheet_url"], ttl=0)
    if df.empty:
        return pd.DataFrame(columns=["ID", "Categoria", "Fecha", "Talla", "Color", "Compra", "Venta", "Stock", "Image_Ref"])
    return df

tab1, tab2 = st.tabs(["➕ Registrar Prenda", "📋 Ver Inventario"])

# --- 2. SUSTITUYE TU TAB 1 ACTUAL (Desde la línea 60 aprox) POR ESTO ---
with tab1:
    st.header("Registrar Nueva Prenda")
    
    # El cargador de archivos ahora es opcional
    archivo_foto = st.file_uploader("Sube la foto de la prenda (Opcional)", type=["jpg", "png", "jpeg"])

    # Inicializamos las variables vacías
    e_cat = ""
    e_color = ""

    # LÓGICA INTELIGENTE:
    if archivo_foto is not None:
        # SI HAY FOTO -> PROCESA CON IA
        imagen_pil = Image.open(archivo_foto)
        st.image(imagen_pil, caption="Vista previa", width=200)
        
        with st.spinner("IA analizando la prenda..."):
            prompt = "Analiza esta prenda y devuelve únicamente: CATEGORIA / COLOR"
            # Asegúrate que el nombre de tu modelo sea el que configuraste arriba (model)
            respuesta = model.generate_content([prompt, imagen_pil])
            try:
                datos_ia = respuesta.text.split("/")
                e_cat = datos_ia[0].strip()
                e_color = datos_ia[1].strip()
            except:
                st.warning("No pude extraer datos automáticamente. Por favor, rellena los campos.")
    else:
        # SI NO HAY FOTO -> PERMITE ENTRADA MANUAL
        st.info("ℹ️ No se ha subido foto. Introduce los datos manualmente.")
    
    # CAMPOS DE ENTRADA (Se rellenan solos si hay IA, o los escribes tú si no la hay)
    col1, col2 = st.columns(2)
    with col1:
        e_cat = st.text_input("Categoría", value=e_cat)
    with col2:
        e_color = st.text_input("Color", value=e_color)

    # Resto de campos que ya tenías...
    e_fecha = st.date_input("Fecha", datetime.now())
    e_talla = st.selectbox("Talla", ["S", "M", "L", "XL", "Única"])
    e_compra = st.number_input("Precio Compra", min_value=0.0, step=0.1)
    e_venta = st.number_input("Precio Venta", min_value=0.0, step=0.1)
    e_stock = st.number_input("Stock Inicial", min_value=1, step=1)

    if st.button("💾 Guardar en Inventario"):
        with st.spinner("Registrando..."):
            # LÓGICA DE IMAGEN FINAL
            if archivo_foto is not None:
                # Subir a Cloudinary
                res_subida = cloudinary.uploader.upload(
                    archivo_foto.getvalue(), 
                    folder="inventario", 
                    public_id=f"foto_{nuevo_id}"
                )
                url_final_foto = res_subida['secure_url']
            else:
                # Usar la imagen negra por defecto
                url_final_foto = URL_SIN_IMAGEN

            # CREAR FILA Y SUBIR A GOOGLE SHEETS
            # (Ajusta los nombres de tus variables si cambian en tu archivo)
            nueva_fila = pd.DataFrame([{
                "ID": nuevo_id,
                "Categoria": e_cat,
                "Fecha": e_fecha.strftime('%Y-%m-%d'),
                "Talla": e_talla,
                "Color": e_color,
                "Compra": e_compra,
                "Venta": e_venta,
                "Stock": e_stock,
                "Image_Ref": url_final_foto
            }])
            
            # Unir con el dataframe actual y actualizar
            df_actualizado = pd.concat([df_inventario, nueva_fila], ignore_index=True)
            conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_actualizado)
            
            st.success(f"✅ Prenda {nuevo_id} guardada correctamente.")
            st.rerun()


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

        
        # 2. SELECTOR DE ID (Solo ID en la lista)
        st.subheader("🔍 Buscador y Editor de Productos")
        
        # Lista solo con IDs
        lista_ids = df_ver["ID"].astype(str).tolist()
        
        if "prenda_seleccionada" not in st.session_state:
            st.session_state.prenda_seleccionada = "-- Elige un ID --"

        # Controlamos que el ID guardado en sesión aún exista (por si se borró)
        if st.session_state.prenda_seleccionada not in (["-- Elige un ID --"] + lista_ids):
            st.session_state.prenda_seleccionada = "-- Elige un ID --"

        seleccion = st.selectbox(
            "Selecciona el ID de la prenda:", 
            ["-- Elige un ID --"] + lista_ids,
            index=(["-- Elige un ID --"] + lista_ids).index(st.session_state.prenda_seleccionada)
        )

        if seleccion != "-- Elige un ID --":
            st.session_state.prenda_seleccionada = seleccion
            
            # Localizar datos
            item_index = df_ver.index[df_ver['ID'].astype(str) == seleccion].tolist()
            datos = df_ver.loc[item_index]

            col_img, col_edit = st.columns([1, 2]) # Dando espacio

            with col_img:
                st.image(datos["Image_Ref"].values[0], caption="Foto Actual", use_container_width=True)
                
                # Inicializamos el estado para mostrar el cargador si no existe
                if "mostrar_cargador" not in st.session_state:
                    st.session_state.mostrar_cargador = False

                # BOTÓN SIMPLE PARA ACTIVAR LA SUBIDA
                if st.button("📷 Cambiar / Añadir Foto"):
                    st.session_state.mostrar_cargador = True

                nueva_foto_archivo = None
                if st.session_state.mostrar_cargador:
                    nueva_foto_archivo = st.file_uploader("Selecciona la nueva imagen", type=['jpg', 'jpeg', 'png'], key="update_uploader")
                    if st.button("❌ Cancelar cambio"):
                        st.session_state.mostrar_cargador = False
                        st.rerun()

            with col_edit:
                with st.form("editor_maestro_v4"):
                    st.write(f"📝 **Ficha:** {seleccion}")
                    
                    # Tus campos de texto (ID, Categoría, etc.)
                    nuevo_id = st.text_input("ID Producto", value=str(datos["ID"].values[0]))
                    e_cat = st.text_input("Categoría", value=str(datos["Categoria"].values[0]))
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        e_talla = st.text_input("Talla", value=str(datos["Talla"].values[0]))
                        e_compra = st.number_input("Compra (€)", value=float(datos["Compra"].values[0]), format="%.2f")
                        e_stock = st.number_input("Stock", value=int(datos["Stock"].values[0]), min_value=0)
                    with c2:
                        e_color = st.text_input("Color", value=str(datos["Color"].values[0]))
                        e_venta = st.number_input("Venta (€)", value=float(datos["Venta"].values[0]), format="%.2f")
                        e_fecha = st.text_input("Fecha", value=str(datos["Fecha"].values[0]))

                    st.write("---")
                    c_btn1, c_btn2 = st.columns(2)
                    guardar_seguir = c_btn1.form_submit_button("💾 Guardar y Seguir")
                    guardar_salir = c_btn2.form_submit_button("🚪 Guardar y Salir")

                # LÓGICA DE GUARDADO
                if guardar_seguir or guardar_salir:
                    try:
                        url_final_foto = datos["Image_Ref"].values[0]
                        
                        # Si hay un archivo en el cargador, lo subimos
                        if nueva_foto_archivo is not None:
                            with st.spinner("Subiendo nueva imagen..."):
                                res_subida = cloudinary.uploader.upload(
                                    nueva_foto_archivo.getvalue(), 
                                    folder="inventario",
                                    public_id=f"foto_{nuevo_id}"
                                )
                                url_final_foto = res_subida['secure_url']

                        # Actualización de datos
                        df_ver.loc[item_index, ["ID", "Categoria", "Talla", "Color", "Compra", "Venta", "Stock", "Fecha", "Image_Ref"]] = [
                            nuevo_id, e_cat, e_talla, e_color, e_compra, e_venta, e_stock, e_fecha, url_final_foto
                        ]
                        
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_ver)
                        st.success("✅ Cambios actualizados")
                        
                        # Resetear el estado del cargador
                        st.session_state.mostrar_cargador = False
                        
                        st.session_state.prenda_seleccionada = "-- Elige un ID --" if guardar_salir else nuevo_id
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")


                # BOTÓN ELIMINAR
                if st.button("🗑️ ELIMINAR PRENDA PERMANENTEMENTE", type="primary", use_container_width=True):
                    df_nuevo = df_ver.drop(item_index)
                    conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_nuevo)
                    st.session_state.prenda_seleccionada = "-- Elige un ID --"
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

        

