import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from supabase import create_client, Client

# =====================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y CONEXIÓN SEGURA
# =====================================================================
st.set_page_config(page_title="Tracker de Hábitos Pro", page_icon="🚀", layout="centered")

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

@st.cache_resource
def inicializar_conexion():
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = inicializar_conexion()
except Exception as e:
    st.error("⚠️ Error de conexión con la base de datos. Verifica tus credenciales secretas.")
    st.stop()

# =====================================================================
# 2. SISTEMA DE USUARIOS (LOGIN / REGISTRO)
# =====================================================================
st.title("🌟 Tracker de Hábitos")

if "usuario" not in st.session_state:
    st.session_state.usuario = None

if st.session_state.usuario is None:
    pestana_auth = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with pestana_auth[0]:
        correo_login = st.text_input("Correo electrónico", key="login_email")
        pass_login = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar", type="primary"):
            try:
                res = supabase.auth.sign_in_with_password({"email": correo_login, "password": pass_login})
                st.session_state.usuario = res.user
                st.rerun()
            except Exception as e:
                st.error("❌ Correo o contraseña incorrectos.")
                
    with pestana_auth[1]:
        correo_reg = st.text_input("Elige un correo electrónico", key="reg_email")
        pass_reg = st.text_input("Elige una contraseña (mín. 6 caracteres)", type="password", key="reg_pass")
        if st.button("Crear Cuenta Segura"):
            try:
                res = supabase.auth.sign_up({"email": correo_reg, "password": pass_reg})
                st.success("🎉 ¡Cuenta creada con éxito! Ya puedes iniciar sesión en la pestaña de al lado.")
            except Exception as e:
                st.error(f"❌ No se pudo crear la cuenta: {e}")
    st.stop()

user_id = st.session_state.usuario.id

if st.sidebar.button("🚪 Cerrar Sesión"):
    supabase.auth.sign_out()
    st.session_state.usuario = None
    st.rerun()

# =====================================================================
# 3. FUNCIONES DE CARGA DESDE SUPABASE
# =====================================================================
def cargar_configuracion():
    res = supabase.table("config_habitos").select("*").eq("user_id", user_id).execute()
    if res.data:
        dicc_habitos = {}
        for fila in res.data:
            dicc_habitos[fila["habito_nombre"]] = {"minimo": fila["minimo"], "frecuencia": fila["frecuencia"]}
        return dicc_habitos
    return {}

def cargar_historial():
    res = supabase.table("historial_habitos").select("*").eq("user_id", user_id).execute()
    if res.data:
        filas = []
        for r in res.data:
            nueva_fila = {"Fecha": datetime.strptime(r["fecha"], "%Y-%m-%d").date(), "Dia_Nombre": r["dia_nombre"], "Semana_Id": r["semana_id"]}
            nueva_fila.update(r["datos_habitos"])
            filas.append(nueva_fila)
        df = pd.DataFrame(filas)
        df.sort_values("Fecha", inplace=True)
        df.reset_index(drop=True, inplace=True)
        df['Semana_Id'] = df.index // 7 + 1
        return df
    return pd.DataFrame()

def cargar_obstaculos():
    res = supabase.table("historial_obstaculos").select("*").eq("user_id", user_id).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
        df.rename(columns={"fecha": "Fecha", "habito": "Habito", "categoria_fallo": "Categoria_Fallo", "detalle_flibre": "Detalle_Flibre"}, inplace=True)
        return df
    return pd.DataFrame(columns=['Fecha', 'Habito', 'Categoria_Fallo', 'Detalle_Flibre'])

mis_habitos = cargar_configuracion()
df_habitos = cargar_historial()
df_obstaculos = cargar_obstaculos()

# =====================================================================
# 4. FORMULARIO DE CONFIGURACIÓN INICIAL
# =====================================================================
if not mis_habitos:
    st.info("👋 ¡Bienvenido! Configura tus hábitos para empezar.")
    nombre_usuario = st.text_input("¿Cómo te llamas?")
    num_habitos = st.slider("¿Cuántos hábitos quieres trackear?", 3, 6, 4)
    
    dict_nuevos = {}
    for i in range(num_habitos):
        st.markdown(f"### Hábito {i+1}")
        col1, col2, col3 = st.columns(3)
        with col1: h_nom = st.text_input(f"Nombre Hábito {i+1}", key=f"h_n_{i}")
        with col2: h_min = st.text_input(f"Mínimo diario", key=f"h_m_{i}", placeholder="Ej: 30 min")
        with col3: h_frec = st.selectbox(f"Días x Semana", list(range(1, 8)), index=4, key=f"h_f_{i}")
        if h_nom:
            dict_nuevos[h_nom] = {"minimo": h_min, "frecuencia": h_frec}
            
    if st.button("🚀 Guardar configuración y empezar"):
        if not nombre_usuario or len(dict_nuevos) < num_habitos:
            st.error("Por favor completa todos los campos.")
        else:
            for h, info in dict_nuevos.items():
                supabase.table("config_habitos").insert({
                    "user_id": user_id, "habito_nombre": h, "minimo": info["minimo"], "frecuencia": info["frecuencia"]
                }).execute()
            st.success("¡Configuración guardada de forma segura!")
            st.rerun()
    st.stop()

habitos = list(mis_habitos.keys())
total_dias_sistema = len(df_habitos)

# =====================================================================
# 5. INTERFAZ EN PESTAÑAS (OPTIMIZADA PARA CELULAR)
# =====================================================================
menu = st.tabs(["📝 Registrar Día", "📈 Estadísticas", "🧠 Patrones"])

# PESTAÑA 1: REGISTRAR DÍA
with menu[0]:
    st.subheader("Registrar hábitos diarios")
    fecha_sel = st.date_input("Fecha del registro", value=datetime.now().date())
    
    valores_previos = {}
    if not df_habitos.empty and fecha_sel in df_habitos['Fecha'].values:
        fila_prev = df_habitos[df_habitos['Fecha'] == fecha_sel].iloc[0]
        for h in habitos:
            valores_previos[h] = True if fila_prev.get(h, 0) == 1 else False

    chks = {}
    for h, info in mis_habitos.items():
        chks[h] = st.checkbox(f"{h} (Mínimo: {info['minimo']})", value=valores_previos.get(h, False), key=f"chk_run_{h}")
        
    if st.button("💾 Guardar Registro Diario", type="primary"):
        dias_espanol = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
        nombre_dia = dias_espanol[fecha_sel.strftime('%A')]
        
        datos_json = {h: (1 if chks[h] else 0) for h in habitos}
        total_logrados_hoy = sum(datos_json.values())
        
        # Guardar o actualizar registro en Supabase
        res_check = supabase.table("historial_habitos").select("id").eq("user_id", user_id).eq("fecha", str(fecha_sel)).execute()
        
        if df_habitos.empty:
            sim_semana_id = 1
        elif fecha_sel in df_habitos['Fecha'].values:
            sim_semana_id = int(df_habitos[df_habitos['Fecha'] == fecha_sel]['Semana_Id'].iloc[0])
        else:
            sim_semana_id = len(df_habitos) // 7 + 1
            
        payload = {"user_id": user_id, "fecha": str(fecha_sel), "dia_nombre": nombre_dia, "semana_id": sim_semana_id, "datos_habitos": datos_json}
        
        if res_check.data:
            supabase.table("historial_habitos").update(payload).eq("id", res_check.data[0]["id"]).execute()
        else:
            supabase.table("historial_habitos").insert(payload).execute()
            
        # Eliminar obstáculos antiguos de este día para evitar duplicados
        supabase.table("historial_obstaculos").delete().eq("user_id", user_id).eq("fecha", str(fecha_sel)).execute()
        
        habitos_fallados = [h for h, completado in datos_json.items() if completado == 0]
        if habitos_fallados:
            st.warning("Detectamos baches en tus objetivos. Clasifica los motivos de forma honesta:")
            for h in habitos_fallados:
                motivo = st.selectbox(f"Razón para '{h}':", [
                    ('🏖️ Día de descanso', 'DESCANSO'),
                    ('⚡ Falta de energía / Cansancio ', 'ENERGIA'),
                    ('⏰ Logística / Falta de tiempo', 'TIEMPO'),
                    ('🔗 Efecto dominó (Fallé un hábito anterior)', 'DOMINO'),
                    ('📦 Entorno inadecuado / Falta de materiales', 'ENTORNO'),
                    ('📝 Otra razón particular', 'OTRA')
                ], key=f"motivo_{h}")
                
                supabase.table("historial_obstaculos").insert({
                    "user_id": user_id, "fecha": str(fecha_sel), "habito": h, "categoria_fallo": motivo[1], "detalle_flibre": ""
                }).execute()
        
        # --- 🟢 AQUÍ RECUPERAMOS TUS INSIGHTS DIARIOS ORIGINALES ---
        st.success("🚀 ¡Datos guardados exitosamente!")
        st.markdown("### 🧠 Tu Feedback Diario:")
        
        if total_logrados_hoy == len(habitos):
            st.balloons()
            st.success("✨ **¡DÍA PERFECTO!** Has completado absolutamente todo. Estás construyendo una inercia imparable. Camina con orgullo hoy.")
        elif total_logrados_hoy == 0:
            st.error("📉 **Día de Cero Absoluto.** Hoy no se pudo cumplir nada, y *está bien*. Mañana la pizarra vuelve a estar en blanco. El verdadero peligro no es fallar un día, sino fallar dos seguidos. Mañana recuperamos.")
        else:
            porcentaje = (total_logrados_hoy / len(habitos)) * 100
            st.info(f"⚖️ **Progreso Equilibrado ({porcentaje:.0f}%):** Cumpliste {total_logrados_hoy} de {len(habitos)} hábitos. No fue perfecto, pero defendiste el día. Mantuviste la consistencia.")

# PESTAÑA 2: ESTADÍSTICAS Y CONTROLES
with menu[1]:
    if df_habitos.empty:
        st.warning("Registra tu primer día para calcular tus scores de rendimiento.")
    else:
        df_limpio = df_habitos.copy()
        if not df_obstaculos.empty:
            fechas_descanso = df_obstaculos[df_obstaculos['Categoria_Fallo'] == 'DESCANSO']['Fecha'].unique()
            df_limpio = df_limpio[~df_limpio['Fecha'].isin(fechas_descanso)]
            
        # Rendimiento de Scores
        if df_limpio.empty:
            recovery_val, stability_val = "Invicto", "100%"
        else:
            rendimiento_diario = df_limpio[habitos].mean(axis=1) * 100
            
            dias_malos = rendimiento_diario[rendimiento_diario < 50.0].index
            puntajes_rec = []
            for idx in dias_malos:
                siguientes = rendimiento_diario.loc[idx + 1:]
                dias_en_volver = 0
                recuperado = False
                for rend in siguientes:
                    dias_en_volver += 1
                    if rend >= 50.0:
                        recuperado = True
                        break
                if recuperado:
                    if dias_en_volver == 1: puntajes_rec.append(100)
                    elif dias_en_volver == 2: puntajes_rec.append(50)
                    else: puntajes_rec.append(0)
                else: puntajes_rec.append(0)
                
            recovery_val = "Invicto" if not puntajes_rec else f"{np.mean(puntajes_rec):.0f}%"
            stability_score = max(0.0, 100.0 - (np.std(rendimiento_diario) * 2.0)) if len(rendimiento_diario) >= 2 else 100.0
            stability_val = f"{stability_score:.0f}%"
            
        c1, c2, c3 = st.columns(3)
        c1.metric("📅 DÍAS GUARDADOS", f"{total_dias_sistema} días")
        c2.metric("🩹 RECOVERY SCORE", recovery_val)
        c3.metric("⚖️ STABILITY SCORE", stability_val)
        
        # --- 🟢 RECUPERAMOS LOS INSIGHTS EXTRAS DE LOS SCORES ---
        st.markdown("### 📑 Diagnóstico de tu Rendimiento General")
        
        # Insight de Recovery
        if recovery_val == "Invicto":
            st.info("📌 **Mente Resiliente:** Te recuperas al instante de tus fallos. ¡No dejas que la culpa te paralice!")
        else:
            rec_num = float(recovery_val.replace('%',''))
            if rec_num >= 70:
                st.info("📌 **Mente Resiliente:** Alta velocidad de rebote ante tropiezos. Corriges el rumbo rápido.")
            else:
                st.warning("⚠️ **Alerta de Inercia Negativa:** Te cuesta retomar tus rutinas después de romperlas. Intenta que un día malo nunca se transforme en una racha.")

        # Insight de Stability
        if len(df_limpio) >= 2:
            if stability_score >= 75:
                st.info("📌 **Consistencia de Roca:** Vives en niveles estables y predecibles de rendimiento. Muy bien.")
            else:
                st.warning("⚠️ **Montaña Rusa:** Tu nivel es caótico; pasas de 100% a 0% drásticamente de un día para el otro. Busca un mínimo sostenible.")
        
        # Gráficas por bloques de 7 días reales
        st.markdown("### Tu Progreso Real por Etapas de 7 Días")
        df_semanal = df_habitos.copy()
        semanas_registradas = sorted(df_semanal['Semana_Id'].unique())
        
        rendimientos_bloques = []
        nombres_bloques = []
        exito_absoluto = {}
        
        for s in semanas_registradas:
            df_s = df_semanal[df_semanal['Semana_Id'] == s]
            dias_s = len(df_s)
            valores_s = []
            for h in habitos:
                logrados_s = df_s[h].sum()
                target_s = max(1, round((mis_habitos[h]['frecuencia'] / 7.0) * dias_s))
                valores_s.append(min((logrados_s / target_s) * 100, 100.0))
            rendimientos_bloques.append(np.mean(valores_s))
            nombres_bloques.append(f"Bloque {s}")
            
        for h in habitos:
            total_logrado = df_habitos[h].sum()
            meta_esperada = max(1.0, min((mis_habitos[h]['frecuencia'] / 7.0) * total_dias_sistema, total_dias_sistema))
            exito_absoluto[h] = min((total_logrado / meta_esperada) * 100, 100.0)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        ax1.plot(nombres_bloques, rendimientos_bloques, marker='o', linewidth=3, color='#2ECC71')
        ax1.fill_between(nombres_bloques, rendimientos_bloques, alpha=0.1, color='#2ECC71')
        ax1.set_title('Evolución por Bloques de 7 Días Reales', fontweight='bold')
        ax1.set_ylim(0, 110)
        
        colores_barras = ['#2ECC71' if v >= 40 else '#E74C3C' for v in exito_absoluto.values()]
        ax2.barh(list(exito_absoluto.keys()), list(exito_absoluto.values()), color=colores_barras, edgecolor='black')
        ax2.set_title('% de Éxito Absoluto por Hábito', fontweight='bold')
        ax2.set_xlim(0, 105)
        
        st.pyplot(fig)

# PESTAÑA 3: PATRONES
with menu[2]:
    if total_dias_sistema < 7:
        st.info("💡 Necesitas registrar al menos 7 días para que la Inteligencia de la App empiece a cruzar patrones.")
    else:
        st.subheader("Análisis Inteligente de Obstáculos")
        df_fallos_reales = df_obstaculos[df_obstaculos['Categoria_Fallo'] != 'DESCANSO']
        
        if not df_fallos_reales.empty:
            conteos_fallos = df_fallos_reales['Categoria_Fallo'].value_counts()
            mapeo_nombres = {'ENERGIA': '⚡ Energía / Cansancio', 'TIEMPO': '⏰ Logística / Tiempos', 'DOMINO': '🔗 Efecto Dominó', 'ENTORNO': '📦 Entorno', 'OTRA': '📝 Razones Varias'}
            
            principal_criptonita = conteos_fallos.index[0]
            st.error(f"🚨 Problema Principal: Tu mayor freno actual es '{mapeo_nombres.get(principal_criptonita, principal_criptonita)}'.")
        else:
            st.success("💪 ¡Increíble! No registras baches reales de motivación u organización todavía.")
            
        corr_matrix = df_habitos[habitos].astype(float).corr(method='pearson').fillna(0)
        st.markdown("### Mapa de Relaciones de Comportamiento")
        fig_corr, ax_corr = plt.subplots(figsize=(6, 4))
        sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="RdYlGn", vmin=-1, vmax=1, center=0, square=True, cbar=False)
        st.pyplot(fig_corr)
