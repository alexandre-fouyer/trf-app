import streamlit as st
import pandas as pd
import re
from datetime import datetime
import time
import cv2
import numpy as np
from pyzbar import pyzbar
from PIL import Image
import streamlit_webrtc as webrtc
import av

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
    st.session_state.last_scan = ""
    st.session_state.scan_detected = False

# Charger le CSV
@st.cache_data
def load_csv():
    try:
        df = pd.read_csv('emplacements.csv', sep=';', header=None, encoding='utf-8')
        
        if len(df.columns) >= 3:
            df = df.iloc[:, :3]
            df.columns = ['ancien', 'quantite', 'nouveau']
        else:
            st.error("Format CSV incorrect")
            return pd.DataFrame()
        
        df['ancien'] = df['ancien'].astype(str).str.strip()
        df['nouveau'] = df['nouveau'].astype(str).str.strip()
        df['quantite'] = pd.to_numeric(df['quantite'], errors='coerce').fillna(0).astype(int)
        
        df = df[df['ancien'] != '1']
        df = df[df['ancien'].str.len() > 0]
        df = df[~df['ancien'].str.contains('ancien', case=False, na=False)]
        
        st.success(f"✅ CSV chargé: {len(df)} emplacements")
        return df
        
    except Exception as e:
        st.error(f"Erreur chargement CSV: {e}")
        return pd.DataFrame({
            'ancien': ['TEST001', 'TEST002', 'TEST003'],
            'quantite': [10, 25, 5],
            'nouveau': ['A-01-01', 'A-01-02', 'B-01-01']
        })

# Classe pour traiter les frames vidéo
class VideoProcessor:
    def __init__(self):
        self.result = None
        
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        
        # Détecter les codes-barres
        barcodes = pyzbar.decode(img)
        
        for barcode in barcodes:
            # Décoder les données
            barcode_data = barcode.data.decode('utf-8')
            
            # Dessiner un rectangle autour du code-barres détecté
            points = barcode.polygon
            if len(points) > 4:
                hull = cv2.convexHull(np.array([point for point in points], dtype=np.float32))
                points = hull
            
            n = len(points)
            for j in range(0, n):
                cv2.line(img, tuple(points[j]), tuple(points[(j+1) % n]), (0, 255, 0), 3)
            
            # Afficher le texte
            x = barcode.rect[0]
            y = barcode.rect[1]
            cv2.putText(img, barcode_data, (x, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Stocker le résultat
            if barcode_data and not st.session_state.scan_detected:
                st.session_state.last_scan = barcode_data
                st.session_state.scan_detected = True
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# Fonction pour nettoyer les codes
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
    # Scanner en temps réel avec webrtc
    ctx = webrtc.webrtc_streamer(
        key="barcode-scanner",
        video_processor_factory=VideoProcessor,
        rtc_configuration={
            "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
        },
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True
    )
    
    # Si un code a été détecté
    if st.session_state.scan_detected:
        st.session_state.scan_detected = False
        st.rerun()

with tab2:
    manual_input = st.text_input(
        "Code-barres",
        placeholder="Entrez le code...",
        label_visibility="collapsed",
        key="manual_input"
    )
    
    if st.button("✅ VALIDER", type="primary", use_container_width=True):
        if manual_input:
            st.session_state.last_scan = manual_input
            st.rerun()

# Traitement du scan
if st.session_state.last_scan:
    scan_clean = clean_code(st.session_state.last_scan.strip().upper())
    
    if st.session_state.state == 'WAITING_OLD':
        df['ancien_upper'] = df['ancien'].str.upper()
        match = df[df['ancien_upper'] == scan_clean]
        
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
        new_location_clean = clean_code(st.session_state.new_location.strip().upper())
        
        if scan_clean == new_location_clean:
            st.session_state.processed += 1
            st.session_state.history.append({
                'ancien': st.session_state.old_location,
                'nouveau': st.session_state.new_location,
                'quantite': st.session_state.quantity,
                'heure': datetime.now().strftime("%H:%M:%S")
            })
            
            st.balloons()
            st.success(f"✅ SUCCÈS! {st.session_state.quantity} pièces déplacées")
            
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
if st.button("🔄 RESET", type="secondary", use_container_width=True):
    st.session_state.state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.session_state.last_scan = ""
    st.rerun()

with st.expander(f"📜 Historique ({len(st.session_state.history)})"):
    if st.session_state.history:
        for item in reversed(st.session_state.history[-5:]):
            st.text(f"{item['heure']} | {item['ancien']} → {item['nouveau']}")
