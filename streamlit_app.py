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
# Ejecutamos la función para que 'df_inventario' exista
df_inventario = leer_datos()

tab1, tab2 = st.tabs(["➕ Registrar Prenda", "📋 Ver Inventario"])



# --- 2. SUSTITUYE TODO TU 'WITH TAB1:' POR ESTE BLOQUE ---
with tab1:
    st.header("Gestión de Inventario")
    
    # Inicializar el estado del modo si no existe
    if 'modo_registro' not in st.session_state:
        st.session_state.modo_registro = None

    # Botones principales ocupando el ancho
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("📸 Registrar por Imagen", use_container_width=True):
            st.session_state.modo_registro = "imagen"
    with col_btn2:
        if st.button("📝 Registrar Nuevo Artículo (Manual)", use_container_width=True):
            st.session_state.modo_registro = "manual"

    st.divider()

    # --- CÁLCULO DE NUEVO ID (Versión Robusta) ---
    try:
        # Intentamos obtener el máximo, eliminando nulos y asegurando que sea numérico
        ids_numericos = pd.to_numeric(df_inventario["ID"], errors='coerce').dropna()
        
        if not ids_numericos.empty:
            nuevo_id = int(ids_numericos.max()) + 1
        else:
            nuevo_id = 1
    except Exception:
        # Si todo falla (por ejemplo, si la columna no existe), empezamos en 1
        nuevo_id = 1

    

    # --- OPERATIVA A: REGISTRO POR IMAGEN ---
    if st.session_state.modo_registro == "imagen":
        st.subheader(f"Registro Inteligente")
        
        # Botón para volver atrás (Cancelar)
        if st.button("⬅️ Volver a selección"):
            st.session_state.modo_registro = None
            st.rerun()

        archivo_foto = st.file_uploader(
            "Requerimientos: Máx. 200MB. Formatos: JPG, PNG, JPEG", 
            type=["jpg", "png", "jpeg"]
        )

        if archivo_foto is not None:
            imagen_pil = Image.open(archivo_foto)
            st.image(imagen_pil, caption="Imagen detectada", width=260)
            
            # Solo analizamos si no tenemos ya los datos en el session_state (para evitar bucles)
            if 'datos_ia' not in st.session_state:
                with st.spinner("🤖 IA Analizando prenda..."):
                    prompt = "Analiza esta prenda y devuelve únicamente: CATEGORIA / COLOR"
                    respuesta = model.generate_content([prompt, imagen_pil])
                    try:
                        res_split = respuesta.text.split("/")
                        st.session_state.datos_ia = {
                            "cat": res_split[0].strip(),
                            "color": res_split[1].strip()
                        }
                    except:
                        st.session_state.datos_ia = {"cat": "", "color": ""}

            # Lógica de sugerencia de duplicados
            cat_detectada = st.session_state.datos_ia["cat"]
            col_detectado = st.session_state.datos_ia["color"]
            
            posible_duplicado = df_inventario[
                (df_inventario["Categoria"].str.lower() == cat_detectada.lower()) & 
                (df_inventario["Color"].str.lower() == col_detectado.lower())
            ]

            if not posible_duplicado.empty:
                st.warning(f"⚠️ Parece que ya tienes '{cat_detectada}' de color '{col_detectado}' en el inventario (ID: {posible_duplicado['ID'].values[0]}).")

            # Formulario de registro
            with st.form("form_registro_imagen"):
                col_id, col_fecha = st.columns(2)
                with col_id:
                    # Permitimos editar el ID sugerido
                    e_id_edit = st.number_input("ID del Artículo", value=int(nuevo_id), step=1)
                with col_fecha:
                    e_fecha = st.date_input("Fecha de Registro", datetime.now())

                c1, c2 = st.columns(2)
                with c1:
                    e_cat = st.text_input("Categoría", value=cat_detectada)
                    e_talla = st.text_input("Talla", placeholder="Ej: M, L, 42...")
                with c2:
                    e_color = st.text_input("Color", value=col_detectado)
                    e_stock = st.number_input("Stock Inicial", min_value=1, step=1)

                c3, c4 = st.columns(2)
                with c3: e_compra = st.number_input("Precio Compra (€)", min_value=0.0, step=0.01)
                with c4: e_venta = st.number_input("Precio Venta (€)", min_value=0.0, step=0.01)

                if st.form_submit_button("💾 CONFIRMAR Y GUARDAR", use_container_width=True):
                    if e_id_edit in df_inventario["ID"].values:
                        st.error(f"El ID {e_id_edit} ya existe. Elige otro o modifícalo.")
                    else:
                        with st.spinner("Subiendo y guardando..."):
                            res_subida = cloudinary.uploader.upload(
                                archivo_foto.getvalue(), 
                                folder="inventario", 
                                public_id=f"foto_{e_id_edit}"
                            )
                            
                            nueva_fila = pd.DataFrame([{
                                "ID": e_id_edit, "Categoria": e_cat, "Fecha": e_fecha.strftime('%Y-%m-%d'),
                                "Talla": e_talla, "Color": e_color, "Compra": e_compra,
                                "Venta": e_venta, "Stock": e_stock, "Image_Ref": res_subida['secure_url']
                            }])
                            
                            df_actualizado = pd.concat([df_inventario, nueva_fila], ignore_index=True)
                            conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_actualizado)
                            
                            # LIMPIEZA PARA EVITAR BUCLES
                            del st.session_state.datos_ia # Borramos los datos temporales
                            st.session_state.modo_registro = None # Volvemos al menú principal
                            st.success("¡Guardado correctamente!")
                            st.rerun() # Recarga limpia
        else:
            st.info("Esperando imagen...")

    # --- OPERATIVA B: REGISTRO MANUAL ---
    elif st.session_state.modo_registro == "manual":
        st.subheader(f"Entrada Manual (ID: {nuevo_id})")
        with st.form("form_registro_manual"):
            c1, c2 = st.columns(2)
            with c1:
                e_cat = st.text_input("Categoría")
                e_talla = st.text_input("Talla (Escribe la talla)", placeholder="Ej: Única, XL, 38...")
            with c2:
                e_color = st.text_input("Color")
                e_fecha = st.date_input("Fecha de Registro", datetime.now())

            c3, c4, c5 = st.columns(3)
            with c3: e_compra = st.number_input("Precio Compra (€)", min_value=0.0, step=0.01)
            with c4: e_venta = st.number_input("Precio Venta (€)", min_value=0.0, step=0.01)
            with c5: e_stock = st.number_input("Stock Inicial", min_value=1, step=1)

            if st.form_submit_button("💾 GUARDAR ARTÍCULO SIN FOTO", use_container_width=True):
                if not e_cat:
                    st.error("Por favor, indica al menos la categoría.")
                else:
                    with st.spinner("Registrando artículo..."):
                        nueva_fila = pd.DataFrame([{
                            "ID": nuevo_id, "Categoria": e_cat, "Fecha": e_fecha.strftime('%Y-%m-%d'),
                            "Talla": e_talla, "Color": e_color, "Compra": e_compra,
                            "Venta": e_venta, "Stock": e_stock, "Image_Ref": URL_SIN_IMAGEN
                        }])
                        df_actualizado = pd.concat([df_inventario, nueva_fila], ignore_index=True)
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], data=df_actualizado)
                        st.success(f"✅ Prenda {nuevo_id} registrada sin imagen.")
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

        

