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
        with col1: h_nom = st.text_input(f"Hábito {i+1}", key=f"h_n_{i}")
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

# State para controlar cuándo mostrar los festejos/feedback reales (Punto 3)
if "mostrar_feedback" not in st.session_state:
    st.session_state.mostrar_feedback = False

# =====================================================================
# 5. INTERFAZ EN PESTAÑAS
# =====================================================================
menu = st.tabs(["📝 Registrar Día", "📈 Estadísticas", "🧠 Patrones"])

# PESTAÑA 1: REGISTRAR DÍA
with menu[0]:
    st.subheader("Registrar hábitos diarios")
    fecha_sel = st.date_input("Fecha", value=datetime.now().date(), max_value=datetime.now().date())
    
    # Si cambia la fecha del calendario, reseteamos el estado del feedback para que no salte viejo contenido
    if "ultima_fecha_vista" not in st.session_state or st.session_state.ultima_fecha_vista != fecha_sel:
        st.session_state.ultima_fecha_vista = fecha_sel
        st.session_state.mostrar_feedback = False

    valores_previos = {}
    if not df_habitos.empty and fecha_sel in df_habitos['Fecha'].values:
        fila_prev = df_habitos[df_habitos['Fecha'] == fecha_sel].iloc[0]
        for h in habitos:
            valores_previos[h] = True if fila_prev.get(h, 0) == 1 else False

    chks = {}
    for h, info in mis_habitos.items():
        chks[h] = st.checkbox(f"{h} (Mínimo: {info['minimo']})", value=valores_previos.get(h, False), key=f"chk_run_{h}")
        
    habitos_fallados_vivos = [h for h, cumplido in chks.items() if not cumplido]

    # PUNTO 3: Si hay fallos, los motivos se eligen ANTES de procesar el éxito del día
    respuestas_obstaculos = {}
    if habitos_fallados_vivos:
        st.markdown("---")
        st.warning("🕵️‍♂️ Dejaste baches sin marcar. Clasificá los motivos reales antes de guardar:")
        opciones_motivos = [
            ('⚡ Falta de energía / Cansancio', 'ENERGIA'),
            ('⏰ Logística / Falta de tiempo', 'TIEMPO'),
            ('🔗 Efecto dominó (Fallé uno anterior)', 'DOMINO'),
            ('📦 Entorno inadecuado / Materiales', 'ENTORNO'),
            ('🏖️ Día de descanso planificado', 'DESCANSO'),
            ('📝 Otra razón particular', 'OTRA')
        ]
        for h in habitos_fallados_vivos:
            respuestas_obstaculos[h] = st.selectbox(f"Motivo para no hacer '{h}':", opciones_motivos, key=f"live_motivo_{h}_{fecha_sel}")

    # UN SOLO BOTÓN DE GUARDADO: Evita ejecuciones intermedias y globos locos
    if st.button("💾 Confirmar y Guardar Todo el Día", type="primary"):
        dias_espanol = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
        nombre_dia = dias_espanol[fecha_sel.strftime('%A')]
        datos_json = {h: (1 if chks[h] else 0) for h in habitos}
        
        sim_semana_id = 1 if df_habitos.empty else (len(df_habitos) // 7 + 1)
        if not df_habitos.empty and fecha_sel in df_habitos['Fecha'].values:
            sim_semana_id = int(df_habitos[df_habitos['Fecha'] == fecha_sel]['Semana_Id'].iloc[0])
            
        payload = {"user_id": user_id, "fecha": str(fecha_sel), "dia_nombre": nombre_dia, "semana_id": sim_semana_id, "datos_habitos": datos_json}
        
        res_check = supabase.table("historial_habitos").select("id").eq("user_id", user_id).eq("fecha", str(fecha_sel)).execute()
        if res_check.data:
            supabase.table("historial_habitos").update(payload).eq("id", res_check.data[0]["id"]).execute()
        else:
            supabase.table("historial_habitos").insert(payload).execute()
            
        # Guardamos los obstáculos asociados de inmediato
        supabase.table("historial_obstaculos").delete().eq("user_id", user_id).eq("fecha", str(fecha_sel)).execute()
        for h, motivo in respuestas_obstaculos.items():
            supabase.table("historial_obstaculos").insert({
                "user_id": user_id, "fecha": str(fecha_sel), "habito": h, "categoria_fallo": motivo[1], "detalle_flibre": ""
            }).execute()
            
        st.session_state.mostrar_feedback = True
        st.rerun()

    # BLOQUE DE RENDIMIENTO DEFINITIVO: Solo se dibuja si el usuario hizo clic en Guardar
    if st.session_state.mostrar_feedback:
        st.success("✅ ¡Historial y motivos de baches actualizados correctamente en el sistema!")
        
        total_logrados_hoy = sum(chks.values())
        descansos_hoy = sum(1 for m in respuestas_obstaculos.values() if m[1] == 'DESCANSO')
        habitos_activos = len(habitos) - descansos_hoy
        
        st.markdown("### 🧠 Tu Feedback de Jornada:")
        if habitos_activos <= 0:
            st.info("🏖️ **Día de Descanso Absoluto:** Hoy cargaste baterías de manera consciente.")
        elif total_logrados_hoy == len(habitos):
            st.balloons()
            st.success("✨ **¡DÍA PERFECTO!** Completaste el 100% real de tus metas. ¡Inercia pura!")
        elif total_logrados_hoy == 0 and descansos_hoy == 0:
            st.error("📉 **Día de Cero Absoluto.** No defendiste ni un solo hábito hoy. Mañana tenés la oportunidad obligatoria de romper esta inercia antes de que se vuelva racha.")
        else:
            porcentaje_ajustado = (total_logrados_hoy / habitos_activos) * 100
            if porcentaje_ajustado >= 100:
                st.balloons()
                st.success(f"🔥 **¡Meta Ajustada Lograda! ({porcentaje_ajustado:.0f}%)** Cumpliste todo lo activo ({total_logrados_hoy}/{habitos_activos}).")
            elif porcentaje_ajustado >= 75:
                st.success(f"⚡ **¡Excelente Esfuerzo! ({porcentaje_ajustado:.0f}%)** Te faltó una sola pieza para el día perfecto.")
            elif porcentaje_ajustado >= 40:
                st.info(f"⚖️ **Rendimiento Regular ({porcentaje_ajustado:.0f}%)**: Cumpliste {total_logrados_hoy} hábitos. Salvaste el día del cero.")
            else:
                st.warning(f"⚠️ **Zona de Peligro ({porcentaje_ajustado:.0f}%)**: Nivel muy bajo ({total_logrados_hoy}/{habitos_activos}). Necesitás reajustar tus prioridades mañana.")

# PESTAÑA 2: ESTADÍSTICAS Y CONTROLES
with menu[1]:
    if df_habitos.empty:
        st.warning("Registra tu primer día para calcular tus scores de rendimiento.")
    else:
        df_limpio = df_habitos.copy()
        
        # Filtrar días que fueron declarados puramente como DESCANSO (Mejora 6)
        fechas_descanso = []
        if not df_obstaculos.empty:
            df_solo_descansos = df_obstaculos[df_obstaculos['Categoria_Fallo'] == 'DESCANSO']
            # Agrupamos por fecha para ver si todos los fallos de ese día fueron descanso
            for f, subdf in df_solo_descansos.groupby('Fecha'):
                fallos_totales_dia = len(df_habitos[df_habitos['Fecha'] == f]) - int(df_habitos[df_habitos['Fecha'] == f][habitos].sum(axis=1).iloc[0])
                if len(subdf) >= fallos_totales_dia:
                    fechas_descanso.append(f)
                    
        df_limpio = df_limpio[~df_limpio['Fecha'].isin(fechas_descanso)]
        
        if df_limpio.empty:
            recovery_val, stability_val = "100%", "100%"
            rendimiento_diario = pd.Series([100.0])
        else:
            rendimiento_diario = df_limpio[habitos].mean(axis=1) * 100
            
            # PUNTO 2: Algoritmo Estricto de Recovery Score (Castiga severamente las rachas largas de fallos)
            puntajes_rec = []
            i = 0
            n = len(rendimiento_diario)
            while i < n:
                if rendimiento_diario.iloc[i] < 50.0:
                    bache_inicio = i
                    while i < n and rendimiento_diario.iloc[i] < 50.0:
                        i += 1
                    
                    if i < n: # Salió del bache
                        dias_caido = i - bache_inicio
                        if dias_caido == 1:
                            puntajes_rec.append(100) # Rebote perfecto al día siguiente
                        elif dias_caido == 2:
                            puntajes_rec.append(40)  # Tardó dos días
                        else:
                            puntajes_rec.append(0)   # Racha larga de abandono
                    else:
                        # Se quedó en el bache y nunca se recuperó
                        puntajes_rec.append(0)
                else:
                    i += 1
            
            recovery_val = "100%" if not puntajes_rec else f"{np.mean(puntajes_rec):.0f}%"
            
            # PUNTO 2: Algoritmo de Estabilidad Ultra Sensible a Volatilidad y Variaciones Drásticas
            if len(rendimiento_diario) >= 2:
                desviacion_estandar = np.std(rendimiento_diario)
                diferencias_consecutivas = np.abs(np.diff(rendimiento_diario))
                promedio_saltos = np.mean(diferencias_consecutivas)
                
                # Multiplicamos penalizaciones para que la inestabilidad de picos quiebre el score alto
                stability_score = max(0.0, 100.0 - (desviacion_estandar * 1.6 + promedio_saltos * 0.9))
            else:
                stability_score = 100.0
            stability_val = f"{stability_score:.0f}%"
            
        c1, c2, c3 = st.columns(3)
        c1.metric("📅 DÍAS GUARDADOS", f"{total_dias_sistema} días")
        c2.metric("🩹 RECOVERY SCORE", recovery_val)
        c3.metric("⚖️ STABILITY SCORE", stability_val)
        
        st.markdown("### 📑 Diagnóstico Real de tu Consistencia")
        
        rec_num = float(recovery_val.replace('%','')) if "%" in recovery_val else 100
        stab_num = float(stability_val.replace('%','')) if "%" in stability_val else 100
        
        # Lógica de mensajes realista basada en los nuevos scores ajustados
        if rec_num >= 80:
            st.info("📌 **Capacidad de Rebote:** Excelente. No permitís que un troiezo se convierta en una racha de abandono.")
        elif rec_num >= 50:
            st.warning("⚠️ **Retorno Demorado:** Te toma un par de días reaccionar tras una caída. Rompé la inercia antes usando objetivos mínimos.")
        else:
            st.error("🚨 **Alerta de Abandono Prolongado:** Cuando fallás un día, tendés a encadenar baches largos. Tu problema no es caerte, es la parálisis posterior.")

        if stab_num >= 75:
            st.info("📌 **Consistencia de Roca:** Tus días son sumamente predecibles y estables. Mantienes el control.")
        elif stab_num >= 45:
            st.warning("⚠️ **Fluctuación de Energía:** Tenés altibajos marcados. Buscá regularizar tus horarios semanales.")
        else:
            st.error("🚨 **Montaña Rusa Absoluta:** Pasás del 100% al 0% con facilidad. Este patrón destruye tu fuerza de voluntad. Estabilizá el ritmo aunque signifique bajar tus metas.")
        
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

# PESTAÑA 3: PATRONES Y MOTIVOS DE FALLO
with menu[2]:
    if total_dias_sistema < 5:
        st.info("💡 Necesitás registrar un par de días más para que los cruces estadísticos de patrones sean significativos.")
    else:
        st.subheader("Análisis Inteligente de Obstáculos")
        
        # PUNTO 1: Mostrar detalladamente las razones de fallo guardadas
        if not df_obstaculos.empty:
            mapeo_nombres = {
                'ENERGIA': '⚡ Energía / Cansancio', 
                'TIEMPO': '⏰ Logística / Tiempos', 
                'DOMINO': '🔗 Efecto Dominó', 
                'ENTORNO': '📦 Entorno Inadecuado', 
                'DESCANSO': '🏖️ Descanso Planificado',
                'OTRA': '📝 Razones Varias'
            }
            
            df_plot_obs = df_obstaculos.copy()
            df_plot_obs['Motivo_Visual'] = df_plot_obs['Categoria_Fallo'].map(mapeo_nombres)
            conteos = df_plot_obs['Motivo_Visual'].value_counts()
            
            st.markdown("#### 📊 Distribución de tus Causas de Incumplimiento")
            fig_obs, ax_obs = plt.subplots(figsize=(8, 4))
            sns.barplot(x=conteos.values, y=conteos.index, palette="Oranges_r", ax=ax_obs, edgecolor="black")
            ax_obs.set_xlabel("Cantidad de veces reportado")
            st.pyplot(fig_obs)
            
            # Criptonita real sin contar los descansos
            df_fallos_reales = df_obstaculos[df_obstaculos['Categoria_Fallo'] != 'DESCANSO']
            if not df_fallos_reales.empty:
                crit = df_fallos_reales['Categoria_Fallo'].value_counts().index[0]
                st.error(f"🚨 **Tu verdadera Criptonita:** El motivo principal por el que rompés tus rutinas es: **{mapeo_nombres[crit]}**.")
        else:
            st.success("💪 ¡Excelente! No se registran motivos de baches en el historial actual.")
            
        corr_matrix = df_habitos[habitos].astype(float).corr(method='pearson').fillna(0)
        st.markdown("### Mapa de Relaciones de Comportamiento (Pearson)")
        fig_corr, ax_corr = plt.subplots(figsize=(6, 4))
        sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="RdYlGn", vmin=-1, vmax=1, center=0, square=True, cbar=False)
        st.pyplot(fig_corr)
        
        st.markdown("### 🔑 Descubrimiento de tus Hábitos Llave")
        enlaces_fuertes = []
        for i in range(len(habitos)):
            for j in range(i+1, len(habitos)):
                val = corr_matrix.iloc[i, j]
                if val >= 0.40:
                    enlaces_fuertes.append((habitos[i], habitos[j], val))
                    
        if enlaces_fuertes:
            enlaces_fuertes.sort(key=lambda x: x[2], reverse=True)
            for h1, h2, score in enlaces_fuertes:
                st.info(f"🎯 **Sinergia ({score:.2f}):** El hábito **'{h1}'** está amarrado fuertemente a **'{h2}'**. Si defendés el primero, arrastrás al segundo por inercia.")
        else:
            st.write("🔍 Tus hábitos se comportan de manera independiente por ahora.")
