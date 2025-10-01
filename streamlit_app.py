import streamlit as st
import pandas as pd
import re
from datetime import datetime
import time

# Configuration de la page pour mobile
st.set_page_config(
    page_title="Déménagement Logistique",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS pour mobile
st.markdown("""
    <style>
    .stApp { max-width: 100%; padding: 0; }
    .stButton > button {
        width: 100%;
        height: 60px;
        font-size: 18px !important;
        margin: 10px 0;
    }
    .stTextInput > div > div > input {
        font-size: 20px !important;
        height: 50px;
    }
    .status-card {
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        text-align: center;
        font-size: 20px;
    }
    .success { background-color: #4CAF50; color: white; }
    .error { background-color: #f44336; color: white; }
    .waiting { background-color: #2196F3; color: white; }
    .direction { background-color: #FF9800; color: white; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# Initialisation session state
if 'state' not in st.session_state:
    st.session_state.state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.session_state.processed = 0
    st.session_state.history = []

# Charger le CSV
@st.cache_data
def load_csv():
    try:
        df = pd.read_csv('emplacements.csv', sep=';', header=None, encoding='utf-8')
        if len(df.columns) >= 3:
            df = df.iloc[:, :3]
            df.columns = ['ancien', 'quantite', 'nouveau']
        df['ancien'] = df['ancien'].astype(str).str.strip()
        df['nouveau'] = df['nouveau'].astype(str).str.strip()
        df['quantite'] = pd.to_numeric(df['quantite'], errors='coerce').fillna(0).astype(int)
        df = df[df['ancien'] != '1']
        df = df[df['ancien'].str.len() > 0]
        return df
    except:
        return pd.DataFrame({
            'ancien': ['TEST001', 'TEST002'],
            'quantite': [10, 25],
            'nouveau': ['A-01-01', 'A-01-02']
        })

# Nettoyer les codes (enlever doubles lettres)
def clean_code(code):
    if code and not any(x in str(code).upper() for x in ['POUMON', 'DELTA', 'DEMENAGEMENT']):
        pattern = r'^([A-Z])\1(-\d)'
        if re.match(pattern, str(code)):
            return re.sub(pattern, r'\1\2', str(code))
    return str(code)

# Charger les données
df = load_csv()

# Header
st.markdown("<h1 style='text-align: center; color: #2196F3;'>📦 DÉMÉNAGEMENT LOGISTIQUE</h1>", unsafe_allow_html=True)

# Statistiques
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total", f"{len(df)}")
with col2:
    st.metric("Traités", f"{st.session_state.processed}")
with col3:
    pourcentage = (st.session_state.processed / len(df) * 100) if len(df) > 0 else 0
    st.metric("Progression", f"{pourcentage:.1f}%")

# Zone de statut
if st.session_state.state == 'WAITING_OLD':
    st.markdown("""
        <div class='status-card waiting'>
            📦 EN ATTENTE<br>
            <small>Entrez l'ancien emplacement</small>
        </div>
    """, unsafe_allow_html=True)
elif st.session_state.state == 'WAITING_NEW':
    st.markdown(f"""
        <div class='status-card direction'>
            ➡️ DIRECTION<br>
            <strong style='font-size: 24px;'>{st.session_state.new_location}</strong><br>
            <small>Quantité: {st.session_state.quantity} pièces</small>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# SIMPLE SAISIE MANUELLE
scan_input = st.text_input(
    "📝 Tapez ou scannez le code",
    placeholder="Ex: A-01-01-1",
    key="scanner_input",
    label_visibility="visible"
)

# Bouton valider
if st.button("✅ VALIDER", type="primary", use_container_width=True):
    if scan_input:
        scan_clean = clean_code(scan_input.strip().upper())
        
        if st.session_state.state == 'WAITING_OLD':
            # Chercher l'ancien emplacement
            df['ancien_upper'] = df['ancien'].str.upper()
            match = df[df['ancien_upper'] == scan_clean]
            
            if not match.empty:
                st.session_state.old_location = scan_clean
                st.session_state.new_location = match.iloc[0]['nouveau']
                st.session_state.quantity = match.iloc[0]['quantite']
                st.session_state.state = 'WAITING_NEW'
                st.success(f"✅ Trouvé! Allez à: **{st.session_state.new_location}**")
                st.rerun()
            else:
                st.error(f"❌ Code non trouvé: {scan_clean}")
        
        elif st.session_state.state == 'WAITING_NEW':
            # Vérifier le nouvel emplacement
            new_clean = clean_code(st.session_state.new_location.strip().upper())
            
            if scan_clean == new_clean:
                st.session_state.processed += 1
                st.session_state.history.append({
                    'ancien': st.session_state.old_location,
                    'nouveau': st.session_state.new_location,
                    'quantite': st.session_state.quantity,
                    'heure': datetime.now().strftime("%H:%M")
                })
                
                st.balloons()
                st.success(f"✅ SUCCÈS! {st.session_state.quantity} pièces déplacées")
                
                # Reset
                st.session_state.state = 'WAITING_OLD'
                st.session_state.old_location = None
                st.session_state.new_location = None
                st.session_state.quantity = None
                time.sleep(2)
                st.rerun()
            else:
                st.error(f"❌ Mauvais emplacement! Attendu: {st.session_state.new_location}")

# Info actuelle
if st.session_state.old_location:
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📍 De: **{st.session_state.old_location}**")
    with col2:
        st.info(f"📦 Vers: **{st.session_state.new_location}**")

# Bouton Reset
st.markdown("---")
if st.button("🔄 RESET", type="secondary", use_container_width=True):
    st.session_state.state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.rerun()

# Historique
with st.expander(f"📜 Historique ({len(st.session_state.history)})"):
    if st.session_state.history:
        for item in reversed(st.session_state.history[-5:]):
            st.text(f"{item['heure']} | {item['ancien']} → {item['nouveau']} ({item['quantite']})")
