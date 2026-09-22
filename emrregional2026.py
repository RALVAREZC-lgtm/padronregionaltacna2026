import hashlib
import io
import time
import unicodedata
from typing import Dict, Optional

import folium
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit_folium import st_folium
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS ADAPTATIVOS
# ==============================================================================
st.set_page_config(
    page_title="Padrón Unificado Tacna EMR 2026",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #F8FAFC;
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    }
    .app-header {
        background: linear-gradient(135deg, #1B3B6F 0%, #0F172A 100%);
        color: white;
        padding: 20px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(27, 59, 111, 0.15);
    }
    .app-header h1 {
        font-size: 24px;
        font-weight: 700;
        margin: 0;
    }
    .app-header p {
        font-size: 13px;
        margin-top: 4px;
        opacity: 0.9;
    }
    .elector-card {
        background-color: #FFFFFF;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    }
    .dni-badge {
        background-color: #E0F2FE;
        color: #0369A1;
        font-weight: 700;
        font-size: 13px;
        padding: 3px 8px;
        border-radius: 8px;
        display: inline-block;
    }
    .dis-badge {
        background-color: #DCFCE7;
        color: #15803D;
        font-size: 12px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 8px;
        display: inline-block;
        margin-left: 6px;
    }
    .pro-badge {
        background-color: #FEF3C7;
        color: #B45309;
        font-size: 12px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 8px;
        display: inline-block;
        margin-left: 6px;
    }
    .elector-name {
        font-size: 16px;
        font-weight: 700;
        color: #1E293B;
        margin: 8px 0;
        text-transform: uppercase;
    }
    .elector-detail {
        font-size: 12px;
        color: #475569;
        margin-top: 4px;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""",
    unsafe_allow_html=True,
)


# ==============================================================================
# 2. AUTENTICACIÓN Y CONTROL DE ACCESO BASADO EN ROLES (RBAC)
# ==============================================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

PERMISOS_SISTEMA = {
    "consultar_padron": "🪪 Búsqueda & Fichas",
    "ver_dashboard": "📊 Dashboard Estadístico",
    "ver_mapas": "🗺️ Geolocalización / Mapas",
    "exportar_reportes": "📥 Exportar Reportes",
    "gestionar_usuarios": "⚙️ Gestión de Usuarios & Perfiles",
}

if "db_usuarios" not in st.session_state:
    st.session_state.db_usuarios = {
        "admin": {
            "password_hash": hash_password("admin123"),
            "nombre": "Administrador General",
            "rol": "Administrador",
            "permisos": list(PERMISOS_SISTEMA.keys()),
        },
        "analista": {
            "password_hash": hash_password("analista123"),
            "nombre": "Analista de Datos",
            "rol": "Analista",
            "permisos": ["consultar_padron", "ver_dashboard", "ver_mapas", "exportar_reportes"],
        },
        "operador": {
            "password_hash": hash_password("campo123"),
            "nombre": "Operador de Campo",
            "rol": "Operador",
            "permisos": ["consultar_padron"],
        },
    }

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None


def login_form():
    st.markdown(
        """
        <div class="app-header">
            <h1>🔒 CONTROL DE ACCESO REGIONAL EMR TACNA 2026</h1>
            <p>Sistema Unificado: Tacna, Tarata, Candarave y Jorge Basadre</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("form_login"):
            st.subheader("Iniciar Sesión")
            usuario_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")
            btn_ingresar = st.form_submit_button("Ingresar al Sistema", use_container_width=True)

            if btn_ingresar:
                usr = usuario_input.strip().lower()
                if usr in st.session_state.db_usuarios:
                    pass_hash = hash_password(password_input)
                    if st.session_state.db_usuarios[usr]["password_hash"] == pass_hash:
                        st.session_state.logged_in = True
                        st.session_state.user_info = {
                            "username": usr,
                            "nombre": st.session_state.db_usuarios[usr]["nombre"],
                            "rol": st.session_state.db_usuarios[usr]["rol"],
                            "permisos": st.session_state.db_usuarios[usr].get("permisos", []),
                        }
                        st.success(f"Bienvenido {st.session_state.user_info['nombre']}!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta.")
                else:
                    st.error("El usuario ingresado no existe.")

        st.info(
            """
            **Credenciales de Demostración:**
            * **Admin:** `admin` / `admin123` *(Acceso Total + Gestión)*
            * **Analista:** `analista` / `analista123` *(Dashboard + Reportes + Mapas)*
            * **Operador:** `operador` / `campo123` *(Búsqueda y Fichas)*
            """
        )


def logout():
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.rerun()


if not st.session_state.logged_in:
    login_form()
    st.stop()


# ==============================================================================
# 3. BASE GEOESPACIAL Y CLIENTE RENIEC/ONPE
# ==============================================================================
LOCALES_GEO = {
    "TACNA": [
        {"nombre": "I.E. Coronel Bolognesi", "lat": -18.0135, "lon": -70.2512, "capacidad": 4500, "distrito": "TACNA"},
        {"nombre": "I.E. Modesto Basadre", "lat": -18.0108, "lon": -70.2465, "capacidad": 3800, "distrito": "TACNA"},
        {"nombre": "UNJBG - Ciudad Universitaria", "lat": -18.0261, "lon": -70.2501, "capacidad": 8000, "distrito": "TACNA"},
        {"nombre": "I.E. Lastenia Rejas de Castañón", "lat": -18.0322, "lon": -70.2589, "capacidad": 3200, "distrito": "ALBARRACIN"},
    ],
    "TARATA": [
        {"nombre": "I.E. Ramón Copaja", "lat": -17.4744, "lon": -70.0331, "capacidad": 1200, "distrito": "TARATA"},
        {"nombre": "I.E. Manuel A. Odría", "lat": -17.4721, "lon": -70.0315, "capacidad": 900, "distrito": "TARATA"},
        {"nombre": "I.E. Ticaco", "lat": -17.4423, "lon": -70.0542, "capacidad": 600, "distrito": "TICACO"},
    ],
    "CANDARAVE": [
        {"nombre": "I.E. Fortunato Zora Carvajal", "lat": -17.2681, "lon": -70.2486, "capacidad": 1100, "distrito": "CANDARAVE"},
        {"nombre": "I.E. 42023 Cairani", "lat": -17.3012, "lon": -70.3210, "capacidad": 500, "distrito": "CAIRANI"},
        {"nombre": "I.E. Huanuara", "lat": -17.2845, "lon": -70.3521, "capacidad": 450, "distrito": "HUANUARA"},
    ],
    "JORGE BASADRE": [
        {"nombre": "I.E. José Carlos Mariátegui", "lat": -17.5951, "lon": -70.6120, "capacidad": 1500, "distrito": "LOCUMBA"},
        {"nombre": "I.E. Nuestro Señor de Locumba", "lat": -17.6110, "lon": -70.7420, "capacidad": 800, "distrito": "ITE"},
        {"nombre": "I.E. Juvenal Ubaldo Ordóñez Salazar", "lat": -17.5210, "lon": -70.8210, "capacidad": 1000, "distrito": "ILABAYA"},
    ],
}


class ClienteReniecOnpeAPI:

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or "DEMO_TOKEN_REGIONAL_2026"

    def obtener_datos_adicionales(self, dni: str, provincia: str) -> Dict[str, str]:
        dni_formatted = str(dni).strip().zfill(8)
        locales = LOCALES_GEO.get(provincia.upper(), LOCALES_GEO["TACNA"])
        idx = int(dni_formatted) % len(locales)
        local_obj = locales[idx]
        mesa = f"0{int(dni_formatted) % 900 + 1000}"
        aula = f"Aula {int(dni_formatted) % 20 + 101}"
        return {
            "dni": dni_formatted,
            "direccion": f"Calle Principal #{int(dni_formatted) % 300 + 10}, {local_obj['distrito']}",
            "local_votacion": local_obj["nombre"],
            "mesa_votacion": mesa,
            "aula": aula,
        }


# ==============================================================================
# 4. CARGA Y HOMOLOGACIÓN DE DATOS UNIFICADA (TACNA, TARATA, CANDARAVE, JORGE BASADRE)
# ==============================================================================
COLUMN_MAPPING = {
    "REGION": "NOMDPT",
    "PROVINCIA": "NOMPRO",
    "DISTRITO": "NOMDIS",
    "DNI": "NUMDLE",
    "APELLIDO PATERNO": "APEPAT",
    "APELLIDO MATERNO": "APEMAT",
    "NOMBRES": "NOMBRE",
}


@st.cache_data
def cargar_padron_unificado() -> pd.DataFrame:
    archivos = [
        ("emr2026tacna.xlsx", "TACNA"),
        ("emr2026tarata.xlsx", "TARATA"),
        ("emr2026basadre.xlsx", "JORGE BASADRE"),
        ("emr2026candarave.xlsx", "CANDARAVE"),
    ]
    dfs = []
    for archivo, prov_default in archivos:
        try:
            df_temp = pd.read_excel(archivo, sheet_name=0)
            df_temp.columns = df_temp.columns.str.strip().str.upper()
            df_temp.rename(columns=COLUMN_MAPPING, inplace=True)

            if "NOMPRO" not in df_temp.columns or df_temp["NOMPRO"].isnull().all():
                df_temp["NOMPRO"] = prov_default
            if "NOMDPT" not in df_temp.columns or df_temp["NOMDPT"].isnull().all():
                df_temp["NOMDPT"] = "TACNA"

            dfs.append(df_temp)
        except Exception:
            pass

    if dfs:
        df_concat = pd.concat(dfs, ignore_index=True)
    else:
        df_concat = pd.DataFrame(columns=["NOMDPT", "NOMPRO", "NOMDIS", "NUMDLE", "APEPAT", "APEMAT", "NOMBRE"])

    df_concat.drop_duplicates(subset=["NUMDLE"], inplace=True)
    df_concat["DNI"] = df_concat["NUMDLE"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(8)
    df_concat["APEPAT"] = df_concat["APEPAT"].fillna("").astype(str).str.strip()
    df_concat["APEMAT"] = df_concat["APEMAT"].fillna("").astype(str).str.strip()
    df_concat["NOMBRE"] = df_concat["NOMBRE"].fillna("").astype(str).str.strip()
    df_concat["NOMBRE_COMPLETO"] = (df_concat["APEPAT"] + " " + df_concat["APEMAT"] + " " + df_concat["NOMBRE"]).str.upper()

    return df_concat


class FiltroPadron:

    @staticmethod
    def normalizar_texto(texto: str) -> str:
        if not texto or not isinstance(texto, str):
            return ""
        nfkd = unicodedata.normalize("NFKD", texto)
        return "".join([c for c in nfkd if not unicodedata.combining(c)]).upper().strip()

    @classmethod
    def aplicar_filtros(
        cls,
        df: pd.DataFrame,
        provincia: str = "TODOS",
        distrito: str = "TODOS",
        busqueda_general: str = "",
    ) -> pd.DataFrame:
        df_res = df.copy()

        if provincia and provincia.upper() != "TODOS":
            df_res = df_res[df_res["NOMPRO"].str.upper() == provincia.upper()]

        if distrito and distrito.upper() != "TODOS":
            df_res = df_res[df_res["NOMDIS"].str.upper() == distrito.upper()]

        if busqueda_general.strip():
            query_norm = cls.normalizar_texto(busqueda_general)
            df_res["SEARCH_FIELD"] = (df_res["DNI"] + " " + df_res["NOMBRE_COMPLETO"]).apply(cls.normalizar_texto)
            df_res = df_res[df_res["SEARCH_FIELD"].str.contains(query_norm, regex=False)]

        return df_res


# ==============================================================================
# 5. GENERADOR DE REPORTES (EXCEL Y PDF)
# ==============================================================================
class GeneradorReportes:

    @staticmethod
    def exportar_excel(df: pd.DataFrame) -> bytes:
        output = io.BytesIO()
        cols = ["DNI", "APEPAT", "APEMAT", "NOMBRE", "NOMDIS", "NOMPRO", "NOMDPT"]
        df_export = df[[c for c in cols if c in df.columns]].copy()
        df_export.columns = ["DNI", "A. PATERNO", "A. MATERNO", "NOMBRES", "DISTRITO", "PROVINCIA", "REGIÓN"]

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, sheet_name="Padron_Regional_2026", index=False)
            ws = writer.sheets["Padron_Regional_2026"]
            header_fill = PatternFill(start_color="1B3B6F", end_color="1B3B6F", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

            for col_num in range(1, len(df_export.columns) + 1):
                cell = ws.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = col[0].column_letter
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        return output.getvalue()

    @staticmethod
    def exportar_pdf(df: pd.DataFrame, titulo: str = "REPORTE UNIFICADO REGIONAL TACNA 2026") -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#1B3B6F"),
            alignment=1,
        )
        subtitle_style = ParagraphStyle(
            "SubTitle", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#666666"), alignment=1
        )

        story.append(Paragraph(titulo, title_style))
        story.append(Paragraph("Gobierno Regional de Tacna - Padrón Electoral Consolidado", subtitle_style))
        story.append(Spacer(1, 12))

        data = [["DNI", "APELLIDOS Y NOMBRES", "DISTRITO", "PROVINCIA"]]
        for _, row in df.head(80).iterrows():
            nombre_full = f"{row.get('APEPAT', '')} {row.get('APEMAT', '')}, {row.get('NOMBRE', '')}"
            data.append([row.get("DNI", ""), nombre_full[:35], row.get("NOMDIS", ""), row.get("NOMPRO", "")])

        table = Table(data, colWidths=[65, 240, 110, 100])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B3B6F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ])
        )

        story.append(table)
        doc.build(story)
        return buffer.getvalue()


# ==============================================================================
# 6. NAVEGACIÓN Y MENÚ SEGÚN ROLES / PERMISOS
# ==============================================================================
user = st.session_state.user_info

st.sidebar.markdown(f"### 👤 {user['nombre']}")
st.sidebar.caption(f"Rol asignado: **{user['rol']}**")
st.sidebar.divider()

user_permisos = user.get("permisos", list(PERMISOS_SISTEMA.keys()))
opciones_menu = [lbl for clave, lbl in PERMISOS_SISTEMA.items() if clave in user_permisos]

if not opciones_menu:
    st.error("No tienes permisos asignados. Contacta al administrador.")
    st.stop()

seccion_activa = st.sidebar.radio("Navegación Principal:", opciones_menu)

st.sidebar.divider()
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    logout()


# ==============================================================================
# 7. EJECUCIÓN MÓDULOS DE LA APLICACIÓN
# ==============================================================================
st.markdown(
    """
    <div class="app-header">
        <h1>📍 PADRÓN REGIONAL TACNA EMR 2026</h1>
        <p>Sistema Unificado: Tacna, Tarata, Candarave y Jorge Basadre</p>
    </div>
""",
    unsafe_allow_html=True,
)

try:
    df_base = cargar_padron_unificado()
    cliente_reniec = ClienteReniecOnpeAPI()

    # MÓDULO 1: BÚSQUEDA Y FICHAS DE ELECTORES
    if seccion_activa == "🪪 Búsqueda & Fichas":
        st.subheader("🔍 Consulta e Identificación Ciudadana Regional")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            txt_busqueda = st.text_input("Buscar", placeholder="DNI o Apellidos...", label_visibility="collapsed")
        with c2:
            provincias = ["TODOS"] + sorted(list(df_base["NOMPRO"].dropna().unique()))
            prov_sel = st.selectbox("Provincia", provincias, label_visibility="collapsed")
        with c3:
            df_dis_scope = df_base if prov_sel == "TODOS" else df_base[df_base["NOMPRO"] == prov_sel]
            distritos = ["TODOS"] + sorted(list(df_dis_scope["NOMDIS"].dropna().unique()))
            dist_sel = st.selectbox("Distrito", distritos, label_visibility="collapsed")

        df_filtrado = FiltroPadron.aplicar_filtros(df_base, provincia=prov_sel, distrito=dist_sel, busqueda_general=txt_busqueda)

        st.caption(f"Se encontraron **{len(df_filtrado):,}** registros. Mostrando primeros 30:")
        if not df_filtrado.empty:
            for _, row in df_filtrado.head(30).iterrows():
                datos_reniec = cliente_reniec.obtener_datos_adicionales(row["DNI"], row["NOMPRO"])
                st.markdown(
                    f"""
                    <div class="elector-card">
                        <div>
                            <span class="dni-badge">🪪 DNI: {row['DNI']}</span>
                            <span class="pro-badge">🏛️ {row['NOMPRO']}</span>
                            <span class="dis-badge">📍 {row['NOMDIS']}</span>
                        </div>
                        <div class="elector-name">{row['APEPAT']} {row['APEMAT']} {row['NOMBRE']}</div>
                        <div class="elector-detail">🏠 <b>Dirección RENIEC:</b> {datos_reniec['direccion']}</div>
                        <div class="elector-detail">🏫 <b>Local Votación ONPE:</b> {datos_reniec['local_votacion']}</div>
                        <div class="elector-detail">🗳️ <b>Mesa:</b> {datos_reniec['mesa_votacion']} | 🚪 <b>Aula:</b> {datos_reniec['aula']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.warning("No se encontraron registros coincidentes.")

    # MÓDULO 2: DASHBOARD ESTADÍSTICO
    elif seccion_activa == "📊 Dashboard Estadístico":
        st.subheader("📊 Indicadores y Análisis Consolidado Regional")

        c1, c2 = st.columns(2)
        with c1:
            prov_dash = st.selectbox("Provincia Filtro", ["TODOS"] + sorted(list(df_base["NOMPRO"].dropna().unique())))
        with c2:
            df_prov_scope = df_base if prov_dash == "TODOS" else df_base[df_base["NOMPRO"] == prov_dash]
            dist_dash = st.selectbox("Distrito Filtro", ["TODOS"] + sorted(list(df_prov_scope["NOMDIS"].dropna().unique())))

        df_dash = FiltroPadron.aplicar_filtros(df_base, provincia=prov_dash, distrito=dist_dash, busqueda_general="")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Electores", f"{len(df_dash):,}")
        m2.metric("Provincias", f"{df_dash['NOMPRO'].nunique()}")
        m3.metric("Distritos", f"{df_dash['NOMDIS'].nunique()}")
        m4.metric("DNIs Válidos", f"{df_dash['DNI'].str.len().eq(8).sum():,}")

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_prov = px.bar(
                df_dash["NOMPRO"].value_counts().reset_index(name="Electores"),
                x="NOMPRO",
                y="Electores",
                text="Electores",
                title="Electores por Provincia",
                color_discrete_sequence=["#1B3B6F"],
            )
            fig_prov.update_traces(textposition="outside")
            fig_prov.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_prov, use_container_width=True)

        with col_g2:
            fig_ape = px.pie(
                df_dash["APEPAT"].value_counts().head(10).reset_index(name="Cantidad"),
                names="APEPAT",
                values="Cantidad",
                title="Top 10 Apellidos Paternos Frecuentes",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Prism,
            )
            fig_ape.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_ape, use_container_width=True)

    # MÓDULO 3: GEOLOCALIZACIÓN Y MAPAS (FOLIUM)
    elif seccion_activa == "🗺️ Geolocalización / Mapas":
        st.subheader("🗺️ Ubicación de Locales de Votación por Provincia")

        prov_mapa = st.selectbox("Filtrar provincia en mapa", ["TODAS"] + list(LOCALES_GEO.keys()))

        mapa_tacna = folium.Map(location=[-17.8000, -70.1000], zoom_start=9, tiles="OpenStreetMap")

        for prov, locales in LOCALES_GEO.items():
            if prov_mapa in ["TODAS", prov]:
                for loc in locales:
                    popup_content = f"""
                    <div style="font-family: Arial; width: 180px;">
                        <b>{loc['nombre']}</b><br>
                        <b>Provincia:</b> {prov}<br>
                        <b>Distrito:</b> {loc['distrito']}<br>
                        <b>Capacidad Aprox:</b> {loc['capacidad']} electores
                    </div>
                    """
                    folium.Marker(
                        location=[loc["lat"], loc["lon"]],
                        popup=folium.Popup(popup_content, max_width=220),
                        tooltip=f"{loc['nombre']} ({prov})",
                        icon=folium.Icon(color="red" if prov == "TACNA" else "blue", icon="info-sign"),
                    ).add_to(mapa_tacna)

        st_folium(mapa_tacna, width=1200, height=500)

    # MÓDULO 4: EXPORTACIÓN DE REPORTES
    elif seccion_activa == "📥 Exportar Reportes":
        st.subheader("📥 Generar y Descargar Reportes Unificados")

        c1, c2 = st.columns(2)
        with c1:
            prov_exp = st.selectbox("Provincia Exportación", ["TODOS"] + sorted(list(df_base["NOMPRO"].dropna().unique())))
        with c2:
            df_p_exp = df_base if prov_exp == "TODOS" else df_base[df_base["NOMPRO"] == prov_exp]
            dist_exp = st.selectbox("Distrito Exportación", ["TODOS"] + sorted(list(df_p_exp["NOMDIS"].dropna().unique())))

        df_exp = FiltroPadron.aplicar_filtros(df_base, provincia=prov_exp, distrito=dist_exp, busqueda_general="")

        st.info(f"Se exportará el listado con **{len(df_exp):,}** registros.")

        exp1, exp2 = st.columns(2)
        with exp1:
            st.download_button(
                "📊 Descargar Reporte Excel (.xlsx)",
                data=GeneradorReportes.exportar_excel(df_exp),
                file_name=f"Reporte_Padron_Tacna_{prov_exp}_{dist_exp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with exp2:
            st.download_button(
                "📄 Descargar Reporte PDF (.pdf)",
                data=GeneradorReportes.exportar_pdf(df_exp),
                file_name=f"Reporte_Padron_Tacna_{prov_exp}_{dist_exp}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    # MÓDULO 5: GESTIÓN DE USUARIOS Y PERMISOS
    elif seccion_activa == "⚙️ Gestión de Usuarios & Perfiles":
        st.subheader("⚙️ Panel de Control de Usuarios, Roles y Permisos Granulares")

        tab_list, tab_add = st.tabs(["📋 Usuarios Registrados", "➕ Registrar Nuevo Usuario"])

        with tab_list:
            users_data = []
            for u, d in st.session_state.db_usuarios.items():
                p_labels = [PERMISOS_SISTEMA[p] for p in d.get("permisos", []) if p in PERMISOS_SISTEMA]
                users_data.append({"Usuario": u, "Nombre": d["nombre"], "Rol": d["rol"], "Permisos Asignados": ", ".join(p_labels)})

            st.dataframe(pd.DataFrame(users_data), use_container_width=True)

            st.divider()
            st.markdown("#### Editar Usuario y Configurar Permisos")
            usr_mod = st.selectbox("Seleccionar Usuario", list(st.session_state.db_usuarios.keys()))

            u_curr = st.session_state.db_usuarios[usr_mod]
            c_p, c_r = st.columns(2)
            with c_p:
                pass_mod = st.text_input("Nueva Contraseña (dejar en blanco para mantener)", type="password")
            with c_r:
                rol_mod = st.selectbox("Rol Principal", ["Administrador", "Analista", "Operador"], index=["Administrador", "Analista", "Operador"].index(u_curr["rol"]))

            st.write("**Permisos Granulares:**")
            permisos_sel = []
            cols_perm = st.columns(2)
            for idx, (clave, desc) in enumerate(PERMISOS_SISTEMA.items()):
                col = cols_perm[idx % 2]
                default_val = clave in u_curr.get("permisos", [])
                if col.checkbox(f"{desc} (`{clave}`)", value=default_val, key=f"perm_{usr_mod}_{clave}"):
                    permisos_sel.append(clave)

            if st.button("Guardar Cambios de Usuario", use_container_width=True):
                if pass_mod.strip():
                    st.session_state.db_usuarios[usr_mod]["password_hash"] = hash_password(pass_mod.strip())
                st.session_state.db_usuarios[usr_mod]["rol"] = rol_mod
                st.session_state.db_usuarios[usr_mod]["permisos"] = permisos_sel
                st.success(f"Usuario '{usr_mod}' actualizado correctamente.")
                time.sleep(0.5)
                st.rerun()

        with tab_add:
            with st.form("form_add"):
                u_new = st.text_input("Nombre de Usuario (ID)")
                n_new = st.text_input("Nombre Completo")
                p_new = st.text_input("Contraseña", type="password")
                r_new = st.selectbox("Rol Principal", ["Administrador", "Analista", "Operador"])

                st.write("**Asignar Permisos:**")
                perm_nuevos = []
                for clave, desc in PERMISOS_SISTEMA.items():
                    if st.checkbox(desc, value=True if r_new == "Administrador" else False, key=f"new_{clave}"):
                        perm_nuevos.append(clave)

                if st.form_submit_button("Crear Usuario"):
                    u_clean = u_new.strip().lower()
                    if u_clean and p_new.strip() and u_clean not in st.session_state.db_usuarios:
                        st.session_state.db_usuarios[u_clean] = {
                            "password_hash": hash_password(p_new.strip()),
                            "nombre": n_new.strip() or u_clean.capitalize(),
                            "rol": r_new,
                            "permisos": perm_nuevos,
                        }
                        st.success(f"Usuario {u_clean} creado exitosamente.")
                        time.sleep(0.5)
                        st.rerun()
                    elif u_clean in st.session_state.db_usuarios:
                        st.error("El nombre de usuario ya existe.")
                    else:
                        st.error("Por favor completa los campos requeridos.")

except Exception as e:
    st.error(f"Error general en la aplicación unificada: {e}")