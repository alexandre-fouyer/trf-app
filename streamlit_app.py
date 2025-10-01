import streamlit as st
import pandas as pd
import re
from datetime import datetime
import cv2
import numpy as np
from pyzbar import pyzbar
from PIL import Image

# Configuration page mobile
st.set_page_config(
    page_title="Déménagement Logistique",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS pour mobile
st.markdown("""
    <style>
    .stApp { padding: 10px; }
    .direction-box { 
        padding: 20px; 
        background-color: #fff3cd; 
        border-radius: 10px; 
        margin: 10px 0;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
    }
    div[data-testid="stCameraInput"] {
        margin: 10px 0;
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
    st.session_state.last_processed_code = None

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
            'ancien': ['TEST001', 'TEST002'],
            'quantite': [10, 25],
            'nouveau': ['A-01-01', 'A-01-02']
        })

# Détecter code-barres dans image
def detect_barcode(image):
    try:
        img_array = np.array(image)
        
        # Essayer détection directe
        barcodes = pyzbar.decode(img_array)
        
        if not barcodes and len(img_array.shape) == 3:
            # Convertir en gris et améliorer
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # Améliorer contraste
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            barcodes = pyzbar.decode(enhanced)
        
        if barcodes:
            return barcodes[0].data.decode('utf-8')
        return None
    except:
        return None

# Nettoyer codes
def clean_code(code):
    if not code:
        return ''
    code = str(code).strip().upper()
    if any(x in code for x in ['POUMON', 'DELTA', 'DEMENAGEMENT']):
        return code
    pattern = r'^([A-Z])\1(-\d)'
    if re.match(pattern, code):
        return re.sub(pattern, r'\1\2', code)
    return code

# Traiter un scan
def process_scan(code, df):
    cleaned = clean_code(code)
    
    if st.session_state.scan_state == 'WAITING_OLD':
        match = df[df['ancien'].str.upper() == cleaned]
        if not match.empty:
            st.session_state.old_location = cleaned
            st.session_state.new_location = match.iloc[0]['nouveau']
            st.session_state.quantity = match.iloc[0]['quantite']
            st.session_state.scan_state = 'WAITING_NEW'
            st.session_state.last_processed_code = cleaned
            return True, f"✅ Direction: {st.session_state.new_location}"
        else:
            return False, f"❌ Code non trouvé: {cleaned}"
    
    elif st.session_state.scan_state == 'WAITING_NEW':
        expected = clean_code(st.session_state.new_location)
        if cleaned == expected:
            st.session_state.processed += 1
            st.session_state.scan_state = 'WAITING_OLD'
            qty = st.session_state.quantity
            st.session_state.old_location = None
            st.session_state.new_location = None
            st.session_state.quantity = None
            st.session_state.last_processed_code = cleaned
            return True, f"✅ SUCCÈS! {qty} pièces déplacées"
        else:
            return False, f"❌ Mauvais emplacement!"

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
    st.info("🔍 **Scannez l'ANCIEN emplacement**")
elif st.session_state.scan_state == 'WAITING_NEW':
    st.markdown(f"""
    <div class="direction-box">
        ➡️ ALLEZ À<br>
        <span style="font-size: 30px;">{st.session_state.new_location}</span><br>
        Quantité: {st.session_state.quantity} pièces
    </div>
    """, unsafe_allow_html=True)
    st.warning("🎯 **Scannez le NOUVEAU emplacement pour confirmer**")

# Tabs pour scanner
tab1, tab2, tab3 = st.tabs(["📷 Caméra", "⌨️ Manuel", "🔫 Scanner USB"])

with tab1:
    st.info("Prenez une photo nette du code-barres")
    
    # Camera input
    camera_photo = st.camera_input("Scanner", key="camera_scanner")
    
    if camera_photo is not None:
        # Détecter le code
        image = Image.open(camera_photo)
        code = detect_barcode(image)
        
        if code and code != st.session_state.last_processed_code:
            success, message = process_scan(code, df)
            if success:
                st.success(message)
                st.balloons() if "SUCCÈS" in message else None
                st.rerun()
            else:
                st.error(message)
        elif not code:
            st.warning("Aucun code détecté. Réessayez avec une photo plus nette.")

with tab2:
    # Input manuel
    with st.form("manual_form", clear_on_submit=True):
        code_input = st.text_input("Code-barres", placeholder="Ex: A-01-01-1")
        submit = st.form_submit_button("✅ Valider", use_container_width=True, type="primary")
        
        if submit and code_input:
            success, message = process_scan(code_input, df)
            if success:
                st.success(message)
                st.balloons() if "SUCCÈS" in message else None
                st.rerun()
            else:
                st.error(message)

with tab3:
    st.info("Pour scanner USB/Bluetooth")
    
    # Input pour scanner qui émule clavier (sans limite de caractères)
    usb_code = st.text_input(
        "Le scanner enverra le code ici",
        placeholder="Attendez le scan...",
        key="usb_scanner"
    )
    
    if usb_code:
        success, message = process_scan(usb_code, df)
        if success:
            st.success(message)
            st.balloons() if "SUCCÈS" in message else None
            # Clear et rerun
            st.session_state.usb_scanner = ""
            st.rerun()
        else:
            st.error(message)

# Infos actuelles
if st.session_state.old_location:
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📍 **Ancien:** {st.session_state.old_location}")
    with col2:
        st.info(f"📦 **Nouveau:** {st.session_state.new_location}")

# Reset
st.markdown("---")
if st.button("🔄 RESET", use_container_width=True):
    st.session_state.scan_state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.session_state.last_processed_code = None
    st.rerun()
