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
            nueva_fila = {"Fecha": datetime.strptime(r["fecha"], "%Y-%m-%d").date(), "Dia_Nombre": r["dia_nombre"]}
            nueva_fila.update(r["datos_habitos"])
            filas.append(nueva_fila)
        df = pd.DataFrame(filas)
        df.sort_values("Fecha", inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        # MEJORA PUNTO 1: Numeración de días reales y cálculo de bloques de 7 días vía operador módulo implícito
        df['Dia_Contador'] = df.index + 1
        df['Semana_Id'] = ((df['Dia_Contador'] - 1) // 7) + 1
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
# 5. INTERFAZ EN PESTAÑAS
# =====================================================================
menu = st.tabs(["📝 Registrar Día", "📈 Estadísticas", "🧠 Patrones"])

# PESTAÑA 1: REGISTRAR DÍA
with menu[0]:
    st.subheader("Registrar hábitos diarios")
    fecha_sel = st.date_input("Fecha del registro", value=datetime.now().date(), max_value=datetime.now().date())
    
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
        
        # Simulación temporal del bloque de 7 días para el payload inicial
        if df_habitos.empty:
            sim_semana_id = 1
        elif fecha_sel in df_habitos['Fecha'].values:
            sim_semana_id = int(df_habitos[df_habitos['Fecha'] == fecha_sel]['Semana_Id'].iloc[0])
        else:
            sim_semana_id = len(df_habitos) // 7 + 1
            
        payload = {"user_id": user_id, "fecha": str(fecha_sel), "dia_nombre": nombre_dia, "semana_id": sim_semana_id, "datos_habitos": datos_json}
        
        res_check = supabase.table("historial_habitos").select("id").eq("user_id", user_id).eq("fecha", str(fecha_sel)).execute()
        if res_check.data:
            supabase.table("historial_habitos").update(payload).eq("id", res_check.data[0]["id"]).execute()
        else:
            supabase.table("historial_habitos").insert(payload).execute()
            
        st.session_state[f"guardado_{fecha_sel}"] = True
        st.rerun()

    if st.session_state.get(f"guardado_{fecha_sel}", False):
        st.success("🚀 ¡Datos guardados exitosamente!")
        
        res_hoy = supabase.table("historial_habitos").select("datos_habitos").eq("user_id", user_id).eq("fecha", str(fecha_sel)).execute()
        if res_hoy.data:
            datos_hoy = res_hoy.data[0]["datos_habitos"]
            habitos_fallados = [h for h, completado in datos_hoy.items() if completado == 0]
            total_logrados_hoy = sum(datos_hoy.values())
            
            if habitos_fallados:
                st.markdown("---")
                st.warning("🕵️‍♂️ Detectamos baches en tus objetivos. Clasifica los motivos para guardar en tus patrones:")
                
                with st.form(key=f"form_obstaculos_{fecha_sel}"):
                    respuestas_obstaculos = {}
                    opciones_motivos = [
                        ('🏖️ Día de descanso', 'DESCANSO'),
                        ('⚡ Falta de energía / Cansancio', 'ENERGIA'),
                        ('⏰ Logística / Falta de tiempo', 'TIEMPO'),
                        ('🔗 Efecto dominó (Fallé uno anterior)', 'DOMINO'),
                        ('📦 Entorno inadecuado / Materiales', 'ENTORNO'),
                        ('📝 Otra razón particular', 'OTRA')
                    ]
                    
                    for h in habitos_fallados:
                        respuestas_obstaculos[h] = st.selectbox(
                            f"Razón para no hacer '{h}':", 
                            opciones_motivos, 
                            key=f"sel_motivo_{h}_{fecha_sel}"
                        )
                    
                    if st.form_submit_button("🧠 Guardar Motivos de Fallo"):
                        supabase.table("historial_obstaculos").delete().eq("user_id", user_id).eq("fecha", str(fecha_sel)).execute()
                        for h, motivo in respuestas_obstaculos.items():
                            supabase.table("historial_obstaculos").insert({
                                "user_id": user_id, "fecha": str(fecha_sel), "habito": h, "categoria_fallo": motivo[1], "detalle_flibre": ""
                            }).execute()
                        st.success("✅ ¡Patrones guardados! Datos listos para la pestaña de Inteligencia.")
                        st.rerun()

            res_obs = supabase.table("historial_obstaculos").select("habito", "categoria_fallo").eq("user_id", user_id).eq("fecha", str(fecha_sel)).execute()
            descansos_hoy = 0
            if res_obs.data:
                descansos_hoy = sum(1 for o in res_obs.data if o["categoria_fallo"] == 'DESCANSO')
            
            habitos_activos = len(habitos) - descansos_hoy
            
            st.markdown("### 🧠 Tu Feedback Diario:")
            if habitos_activos <= 0:
                st.info("🏖️ **Día de Descanso Total:** Hoy recargaste energías por completo. ¡Excelente planificación!")
            elif total_logrados_hoy == len(habitos):
                st.balloons()
                st.success("✨ **¡DÍA PERFECTO!** Has completado absolutamente todo. Estás construyendo una inercia imparable.")
            elif total_logrados_hoy == 0 and descansos_hoy == 0:
                st.error("📉 **Día de Cero Absoluto.** Hoy no se pudo cumplir nada, y *está bien*. Mañana la pizarra vuelve a estar en blanco. El verdadero peligro es fallar dos veces seguidas.")
            else:
                porcentaje_ajustado = (total_logrados_hoy / habitos_activos) * 100
                
                if porcentaje_ajustado >= 100:
                    st.balloons()
                    st.success(f"🔥 **¡Objetivo Ajustado Cumplido! ({porcentaje_ajustado:.0f}%)** Lograste todos tus hábitos activos ({total_logrados_hoy}/{habitos_activos}). ¡Los descansos se respetan!")
                elif porcentaje_ajustado >= 75:
                    st.success(f"⚡ **¡Casi Perfecto! ({porcentaje_ajustado:.0f}%)** Cumpliste {total_logrados_hoy} de {habitos_activos} hábitos activos. Rozaste la excelencia, gran progreso.")
                elif porcentaje_ajustado >= 40:
                    st.info(f"⚖️ **Progreso Equilibrado ({porcentaje_ajustado:.0f}%)**: Cumpliste {total_logrados_hoy} de {habitos_activos} hábitos activos. No fue perfecto, pero defendiste el día.")
                else:
                    st.warning(f"⚠️ **Fuerza de Resistencia ({porcentaje_ajustado:.0f}%)**: Hiciste {total_logrados_hoy} de {habitos_activos} hábitos activos. Aunque bajo, mantienes la identidad del hábito.")

# PESTAÑA 2: ESTADÍSTICAS Y CONTROLES
with menu[1]:
    if df_habitos.empty:
        st.warning("Registra tu primer día para calcular tus scores de rendimiento.")
    else:
        df_limpio = df_habitos.copy()
        if not df_obstaculos.empty:
            fechas_descanso = df_obstaculos[df_obstaculos['Categoria_Fallo'] == 'DESCANSO']['Fecha'].unique()
            df_limpio = df_limpio[~df_limpio['Fecha'].isin(fechas_descanso)]
            
        if df_limpio.empty:
            recovery_val, stability_val = "Invicto", "100%"
        else:
            rendimiento_diario = df_limpio[habitos].mean(axis=1) * 100
            
            # MEJORA PUNTO 3: Algoritmo de Recovery Score Estricto y Cronológico anti-bucles
            puntajes_rec = []
            i = 0
            n = len(rendimiento_diario)
            while i < n:
                if rendimiento_diario.iloc[i] < 50.0:
                    # Encontramos un bache. Busquemos cuándo se recupera de manera consecutiva
                    bache_inicio = i
                    i += 1
                    while i < n and rendimiento_diario.iloc[i] < 50.0:
                        i += 1
                    
                    if i < n: # Logró recuperarse en el índice i
                        dias_en_recuperarse = i - bache_inicio
                        if dias_en_recuperarse == 1:
                            puntajes_rec.append(100)
                        elif dias_en_recuperarse == 2:
                            puntajes_rec.append(50)
                        else:
                            puntajes_rec.append(0)
                    else:
                        # Terminó el historial en pleno bache y nunca rebotó
                        puntajes_rec.append(0)
                else:
                    i += 1
                
            recovery_val = "Invicta" if not puntajes_rec else f"{np.mean(puntajes_rec):.0f}%"
            
            # MEJORA PUNTO 3: Cálculo de Estabilidad Sensible a Volatilidad Extrema (Picos Caóticos)
            if len(rendimiento_diario) >= 2:
                desviacion = np.std(rendimiento_diario)
                diff_diarias = np.abs(np.diff(rendimiento_diario))
                promedio_saltos = np.mean(diff_diarias)
                # Penalizamos tanto la dispersión como los saltos violentos de un día al otro
                stability_score = max(0.0, 100.0 - (desviacion * 1.5 + promedio_saltos * 0.5))
            else:
                stability_score = 100.0
            stability_val = f"{stability_score:.0f}%"
            
        c1, c2, c3 = st.columns(3)
        c1.metric("📅 DÍAS GUARDADOS", f"{total_dias_sistema} días")
        c2.metric("🩹 RECOVERY SCORE", recovery_val)
        c3.metric("⚖️ STABILITY SCORE", stability_val)
        
        st.markdown("### 📑 Diagnóstico de tu Rendimiento General")
        
        if recovery_val == "Invicta":
            st.info("📌 **Mente Resiliente:** No registras caídas prolongadas. Cada tropiezo es corregido inmediatamente al día siguiente.")
        else:
            rec_num = float(recovery_val.replace('%',''))
            if rec_num >= 75:
                st.info("📌 **Mente Resiliente:** Alta velocidad de rebote ante tropiezos. Corriges el rumbo rápido.")
            elif rec_num >= 45:
                st.warning("⚠️ **Retorno Lento:** Cuando tienes un día malo, te toma entre 2 y 3 días reaccionar. Intenta forzar un 'mínimo ridículo' al día siguiente.")
            else:
                st.error("🚨 **Alerta de Inercia Negativa:** Tiendes a encadenar rachas largas de días fallados. Tu mayor peligro no es la primera caída, sino la segunda.")

        if len(df_limpio) >= 2:
            if stability_score >= 75:
                st.info("📌 **Consistencia de Roca:** Vives en niveles estables y predecibles de rendimiento. Muy bien.")
            elif stability_score >= 45:
                st.warning("⚠️ **Fluctuación Moderada:** Tu progreso muestra irregularidades. Intenta definir mejor tus bloques horarios.")
            else:
                st.error("🚨 **Montaña Rusa Absoluta:** Pasas del 100% al 0% drásticamente. Ese ritmo quema tu fuerza de voluntad. Es preferible un 60% constante que picos caóticos.")
        
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
        
        colores_barras = ['#2ECC71' if v >= 50 else '#E74C3C' for v in exito_absoluto.values()]
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
            
        # MEJORA PUNTO 4: Explicación didáctica y escáner automático de Hábitos Llave
        corr_matrix = df_habitos[habitos].astype(float).corr(method='pearson').fillna(0)
        st.markdown("### Mapa de Relaciones de Comportamiento")
        fig_corr, ax_corr = plt.subplots(figsize=(6, 4))
        sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="RdYlGn", vmin=-1, vmax=1, center=0, square=True, cbar=False)
        st.pyplot(fig_corr)
        
        st.markdown("""
        #### 📈 ¿Cómo interpretar este mapa?
        * **1.00 (Verde Intenso):** Relación perfecta directa.
        * **Valores > 0.40 (Verde):** Correlación positiva. Cuando haces un hábito, aumenta drásticamente la probabilidad de que cumplas el otro.
        * **Valores cercanos a 0.00 (Amarillo):** Comportamientos independientes. Hacer uno no afecta al otro.
        * **Valores < -0.30 (Rojo):** Correlación negativa o de exclusión. Hacer un hábito interfiere o destruye el tiempo del otro.
        """)
        
        st.markdown("### 🔑 Descubrimiento de tus Hábitos Llave")
        enlaces_fuertes = []
        for i in range(len(habitos)):
            for j in range(i+1, len(habitos)):
                val = corr_matrix.iloc[i, j]
                if val >= 0.40:
                    enlaces_fuertes.append((habitos[i], habitos[j], val))
                    
        if enlaces_fuertes:
            # Ordenamos de mayor a menor correlación
            enlaces_fuertes.sort(key=lambda x: x[2], reverse=True)
            for h1, h2, score in enlaces_fuertes:
                st.info(f"🎯 **Sinergia Detectada ({score:.2f}):** El hábito **'{h1}'** está amarrado fuertemente a **'{h2}'**. Si defiendes el primero a la mañana, arrastrarás al segundo casi sin esfuerzo por inercia cerebral.")
        else:
            st.write("🔍 El sistema aún no detecta dependencias cruzadas fuertes. Tus hábitos se comportan de manera independiente por ahora.")
