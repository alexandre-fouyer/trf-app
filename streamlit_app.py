import streamlit as st
import pandas as pd
import re
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase
import av
import cv2
import numpy as np
from pyzbar import pyzbar
import time

# Configuration page mobile
st.set_page_config(
    page_title="Déménagement Logistique",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS
st.markdown("""
    <style>
    .stApp { padding: 10px; }
    .direction-box { 
        padding: 20px; 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 15px; 
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        margin: 20px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Session state
if 'scan_state' not in st.session_state:
    st.session_state.scan_state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.session_state.processed = 0
    st.session_state.last_code = None
    st.session_state.code_detected = False

# Charger CSV
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
            return df
    except:
        return pd.DataFrame({
            'ancien': ['L-10-06-5', 'TEST001', 'TEST002'],
            'quantite': [10, 25, 5],
            'nouveau': ['A-01-01', 'A-01-02', 'B-01-01']
        })

# Processeur vidéo pour detection en temps réel
class BarcodeScanner(VideoProcessorBase):
    def __init__(self):
        self.last_detected = None
        self.detection_time = 0
        
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        
        # Détecter les codes-barres
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        barcodes = pyzbar.decode(gray)
        
        for barcode in barcodes:
            # Décoder
            barcode_data = barcode.data.decode('utf-8')
            
            # Éviter détections répétées
            current_time = time.time()
            if barcode_data != self.last_detected or (current_time - self.detection_time) > 2:
                self.last_detected = barcode_data
                self.detection_time = current_time
                
                # Sauvegarder dans session state
                st.session_state.last_code = barcode_data
                st.session_state.code_detected = True
            
            # Dessiner rectangle vert autour du code détecté
            points = barcode.polygon
            if len(points) == 4:
                pts = np.array(points, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(img, [pts], True, (0, 255, 0), 3)
            
            # Afficher le code
            x = barcode.rect[0]
            y = barcode.rect[1]
            cv2.putText(img, barcode_data, (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# Nettoyer codes (pas de double lettre au début)
def clean_code(code):
    if not code:
        return ''
    code = str(code).strip().upper()
    # Pour vos codes comme L-10-06-5, pas besoin de nettoyer
    return code

# Charger données
df = load_csv()

# Header
st.markdown("# 📦 Déménagement Logistique")

# Stats
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total", len(df))
with col2:
    st.metric("Traités", st.session_state.processed)
with col3:
    pct = (st.session_state.processed / len(df) * 100) if len(df) > 0 else 0
    st.metric("Progression", f"{pct:.0f}%")

# État actuel
if st.session_state.scan_state == 'WAITING_OLD':
    st.info("🔍 **Pointez la caméra vers l'ANCIEN emplacement**")
elif st.session_state.scan_state == 'WAITING_NEW':
    st.markdown(f"""
    <div class="direction-box">
        ➡️ ALLEZ À<br>
        <span style="font-size: 36px;">{st.session_state.new_location}</span><br>
        <span style="font-size: 18px;">Quantité: {st.session_state.quantity} pièces</span>
    </div>
    """, unsafe_allow_html=True)
    st.warning("🎯 **Scannez le NOUVEAU emplacement**")

# Scanner en temps réel
st.markdown("### 📷 Scanner Automatique")

# Streamer vidéo avec détection
ctx = webrtc_streamer(
    key="barcode-scanner",
    video_processor_factory=BarcodeScanner,
    rtc_configuration={
        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    },
    media_stream_constraints={
        "video": {"facingMode": "environment"},  # Caméra arrière
        "audio": False
    }
)

# Traiter la détection
if st.session_state.code_detected:
    code = st.session_state.last_code
    cleaned = clean_code(code)
    
    if st.session_state.scan_state == 'WAITING_OLD':
        match = df[df['ancien'].str.upper() == cleaned]
        if not match.empty:
            st.session_state.old_location = cleaned
            st.session_state.new_location = match.iloc[0]['nouveau']
            st.session_state.quantity = match.iloc[0]['quantite']
            st.session_state.scan_state = 'WAITING_NEW'
            st.success(f"✅ Trouvé! Direction: {st.session_state.new_location}")
            st.session_state.code_detected = False
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"❌ Code non trouvé: {cleaned}")
            st.session_state.code_detected = False
    
    elif st.session_state.scan_state == 'WAITING_NEW':
        expected = clean_code(st.session_state.new_location)
        if cleaned == expected:
            st.session_state.processed += 1
            st.balloons()
            st.success(f"✅ SUCCÈS! {st.session_state.quantity} pièces déplacées")
            # Reset
            st.session_state.scan_state = 'WAITING_OLD'
            st.session_state.old_location = None
            st.session_state.new_location = None
            st.session_state.quantity = None
            st.session_state.code_detected = False
            time.sleep(2)
            st.rerun()
        else:
            st.error(f"❌ Mauvais emplacement!")
            st.session_state.code_detected = False

# Alternative manuelle
with st.expander("⌨️ Saisie Manuelle"):
    with st.form("manual", clear_on_submit=True):
        code = st.text_input("Code", placeholder="L-10-06-5")
        if st.form_submit_button("Valider", use_container_width=True):
            st.session_state.last_code = code
            st.session_state.code_detected = True
            st.rerun()

# Reset
if st.button("🔄 RESET", use_container_width=True):
    st.session_state.scan_state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.session_state.code_detected = False
    st.rerun()
