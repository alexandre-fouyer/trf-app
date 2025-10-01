import streamlit as st
import pandas as pd
import re
from datetime import datetime
import cv2
import numpy as np
from pyzbar import pyzbar
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
    .stApp {
        max-width: 100%;
        padding: 0;
    }
    
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
    
    /* Cache le menu Streamlit */
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
    st.session_state.camera_active = False
    st.session_state.last_scan = ""

# Charger le CSV depuis GitHub
@st.cache_data
def load_csv():
    try:
        # Charger depuis le fichier dans le repo
        df = pd.read_csv('emplacements.csv', sep=';', header=None, names=['ancien', 'quantite', 'nouveau'])
        
        # Nettoyer les données
        df['ancien'] = df['ancien'].str.strip()
        df['nouveau'] = df['nouveau'].str.strip()
        df['quantite'] = pd.to_numeric(df['quantite'], errors='coerce').fillna(0).astype(int)
        
        # Enlever les lignes avec header si présentes
        df = df[~df['ancien'].str.contains('ancien', case=False, na=False)]
        
        return df
    except Exception as e:
        st.error(f"Erreur chargement CSV: {e}")
        # Données de test si erreur
        return pd.DataFrame({
            'ancien': ['TEST001', 'TEST002', 'TEST003'],
            'quantite': [10, 25, 5],
            'nouveau': ['A-01-01', 'A-01-02', 'B-01-01']
        })

# Fonction pour scanner avec la caméra
def scan_barcode_camera():
    """Scanner de code-barres utilisant la caméra"""
    camera_placeholder = st.empty()
    
    # Utiliser camera_input de Streamlit (méthode simple)
    img_file = camera_placeholder.camera_input("Pointez vers le code-barres", key="camera")
    
    if img_file is not None:
        # Lire l'image
        bytes_data = img_file.getvalue()
        nparr = np.frombuffer(bytes_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Détecter les codes-barres
        barcodes = pyzbar.decode(img)
        
        if barcodes:
            # Prendre le premier code détecté
            barcode_data = barcodes[0].data.decode('utf-8')
            camera_placeholder.empty()  # Fermer la caméra
            return barcode_data
    
    return None

# Fonction pour nettoyer les codes
def clean_code(code):
    if code and not any(x in code for x in ['POUMON', 'DELTA', 'DEMENAGEMENT']):
        pattern = r'^([A-Z])\1(-\d)'
        if re.match(pattern, code):
            return re.sub(pattern, r'\1\2', code)
    return code

# Charger les données
df = load_csv()

# Header
st.markdown("<h1 style='text-align: center; color: #2196F3;'>📦 DÉMÉNAGEMENT LOGISTIQUE</h1>", unsafe_allow_html=True)

# Statistiques en haut
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
            <small>Scannez l'ancien emplacement</small>
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

# Zone de scan
tab1, tab2 = st.tabs(["📷 Scanner Caméra", "⌨️ Saisie Manuelle"])

with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🎯 ACTIVER SCANNER", type="primary", use_container_width=True):
            st.session_state.camera_active = True
    
    with col2:
        if st.button("❌ FERMER", type="secondary", use_container_width=True):
            st.session_state.camera_active = False
            st.rerun()
    
    if st.session_state.camera_active:
        scanned_code = scan_barcode_camera()
        if scanned_code:
            st.session_state.camera_active = False
            st.session_state.last_scan = scanned_code
            st.rerun()

with tab2:
    manual_input = st.text_input(
        "Code-barres",
        placeholder="Entrez le code manuellement...",
        label_visibility="collapsed"
    )
    
    if st.button("✅ VALIDER", type="primary", use_container_width=True):
        if manual_input:
            st.session_state.last_scan = manual_input
            st.rerun()

# Traitement du scan
if st.session_state.last_scan:
    scan_clean = clean_code(st.session_state.last_scan.strip().upper())
    
    if st.session_state.state == 'WAITING_OLD':
        # Chercher dans le CSV
        match = df[df['ancien'].str.upper() == scan_clean]
        
        if not match.empty:
            st.session_state.old_location = scan_clean
            st.session_state.new_location = match.iloc[0]['nouveau']
            st.session_state.quantity = match.iloc[0]['quantite']
            st.session_state.state = 'WAITING_NEW'
            st.session_state.last_scan = ""
            
            st.success(f"✅ Trouvé! Direction: {st.session_state.new_location}")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"❌ Code non trouvé: {scan_clean}")
            st.session_state.last_scan = ""
    
    elif st.session_state.state == 'WAITING_NEW':
        if scan_clean == st.session_state.new_location.upper():
            st.session_state.processed += 1
            st.session_state.history.append({
                'ancien': st.session_state.old_location,
                'nouveau': st.session_state.new_location,
                'quantite': st.session_state.quantity,
                'heure': datetime.now().strftime("%H:%M:%S")
            })
            
            st.balloons()
            st.success(f"✅ SUCCÈS! {st.session_state.quantity} pièces déplacées")
            
            # Reset
            time.sleep(2)
            st.session_state.state = 'WAITING_OLD'
            st.session_state.old_location = None
            st.session_state.new_location = None
            st.session_state.quantity = None
            st.session_state.last_scan = ""
            st.rerun()
        else:
            st.error(f"❌ Mauvais emplacement!")
            st.warning(f"Attendu: {st.session_state.new_location}")
            st.session_state.last_scan = ""

# Informations actuelles
if st.session_state.old_location:
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📍 Ancien: **{st.session_state.old_location}**")
    with col2:
        st.info(f"📦 Nouveau: **{st.session_state.new_location or '-'}**")

# Boutons d'action
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 RESET", type="secondary", use_container_width=True):
        st.session_state.state = 'WAITING_OLD'
        st.session_state.old_location = None
        st.session_state.new_location = None
        st.session_state.quantity = None
        st.session_state.last_scan = ""
        st.rerun()

with col2:
    with st.expander(f"📜 Historique ({len(st.session_state.history)})"):
        if st.session_state.history:
            for item in reversed(st.session_state.history[-5:]):
                st.text(f"{item['heure']} | {item['ancien']} → {item['nouveau']}")