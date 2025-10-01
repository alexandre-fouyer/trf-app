import streamlit as st
import pandas as pd
import re
from datetime import datetime
import time
import cv2
import numpy as np
from pyzbar import pyzbar
from PIL import Image
import streamlit_camera_input_live

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
    st.session_state.last_detected = None
    st.session_state.detection_count = 0

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

# Détecter code-barres dans l'image
def detect_barcode(image):
    try:
        # Convertir PIL en numpy array
        img_array = np.array(image)
        
        # Essayer la détection directe
        barcodes = pyzbar.decode(img_array)
        
        if not barcodes and len(img_array.shape) == 3:
            # Convertir en niveaux de gris
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # Améliorer le contraste
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Réessayer
            barcodes = pyzbar.decode(enhanced)
            
            if not barcodes:
                # Essayer avec flou pour réduire le bruit
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                barcodes = pyzbar.decode(blurred)
        
        if barcodes:
            return barcodes[0].data.decode('utf-8')
        return None
        
    except Exception as e:
        return None

# Nettoyer les codes
def clean_code(code):
    if code and not any(x in str(code).upper() for x in ['POUMON', 'DELTA', 'DEMENAGEMENT']):
        pattern = r'^([A-Z])\1(-\d)'
        if re.match(pattern, str(code)):
            return re.sub(pattern, r'\1\2', str(code))
    return str(code)

# Traiter le code détecté
def process_scan(code, df):
    scan_clean = clean_code(code.strip().upper())
    
    if st.session_state.state == 'WAITING_OLD':
        df['ancien_upper'] = df['ancien'].str.upper()
        match = df[df['ancien_upper'] == scan_clean]
        
        if not match.empty:
            st.session_state.old_location = scan_clean
            st.session_state.new_location = match.iloc[0]['nouveau']
            st.session_state.quantity = match.iloc[0]['quantite']
            st.session_state.state = 'WAITING_NEW'
            return f"✅ Trouvé! Direction: {st.session_state.new_location}"
        else:
            return f"❌ Code non trouvé: {scan_clean}"
    
    elif st.session_state.state == 'WAITING_NEW':
        new_clean = clean_code(st.session_state.new_location.strip().upper())
        
        if scan_clean == new_clean:
            st.session_state.processed += 1
            st.session_state.history.append({
                'ancien': st.session_state.old_location,
                'nouveau': st.session_state.new_location,
                'quantite': st.session_state.quantity,
                'heure': datetime.now().strftime("%H:%M")
            })
            
            st.session_state.state = 'WAITING_OLD'
            st.session_state.old_location = None
            st.session_state.new_location = None
            st.session_state.quantity = None
            return f"✅ SUCCÈS! {st.session_state.quantity} pièces déplacées"
        else:
            return f"❌ Mauvais emplacement! Attendu: {st.session_state.new_location}"

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
tab1, tab2 = st.tabs(["📷 Scanner", "⌨️ Manuel"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎯 ACTIVER CAMÉRA", type="primary", use_container_width=True):
            st.session_state.camera_active = True
    with col2:
        if st.button("⏹️ ARRÊTER", type="secondary", use_container_width=True):
            st.session_state.camera_active = False
            st.rerun()
    
    if st.session_state.camera_active:
        # Scanner en continu
        image = streamlit_camera_input_live.camera_input_live(
            key="camera_scanner",
            height=400,
            debounce=500  # Capture toutes les 500ms
        )
        
        if image is not None:
            # Détecter le code-barres
            detected_code = detect_barcode(image)
            
            if detected_code:
                # Éviter les détections multiples du même code
                if detected_code != st.session_state.last_detected:
                    st.session_state.last_detected = detected_code
                    st.session_state.detection_count = 0
                    
                    # Traiter le scan
                    result = process_scan(detected_code, df)
                    st.info(result)
                    
                    if "SUCCÈS" in result or "Direction" in result:
                        time.sleep(2)
                        st.rerun()
                else:
                    st.session_state.detection_count += 1
                    if st.session_state.detection_count > 5:
                        st.session_state.last_detected = None
            else:
                st.info("📷 Pointez vers le code-barres...")

with tab2:
    manual_input = st.text_input("Code-barres", placeholder="Ex: A-01-01-1")
    
    if st.button("✅ VALIDER", type="primary", use_container_width=True):
        if manual_input:
            result = process_scan(manual_input, df)
            st.info(result)
            time.sleep(2)
            st.rerun()

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
if st.button("🔄 RESET", use_container_width=True):
    st.session_state.state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.session_state.camera_active = False
    st.rerun()
