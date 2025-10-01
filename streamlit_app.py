import streamlit as st
import pandas as pd
import cv2
import numpy as np
from pyzbar import pyzbar
from PIL import Image

# Configuration
st.set_page_config(
    page_title="Déménagement Logistique",
    page_icon="📦",
    layout="wide"
)

# CSS
st.markdown("""
    <style>
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

def detect_barcode_enhanced(image):
    """Détection améliorée avec plusieurs méthodes"""
    try:
        img_array = np.array(image)
        results = []
        
        # Méthode 1: Image originale
        decoded = pyzbar.decode(img_array)
        if decoded:
            return decoded[0].data.decode('utf-8')
        
        # Méthode 2: Niveaux de gris
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
            
        decoded = pyzbar.decode(gray)
        if decoded:
            return decoded[0].data.decode('utf-8')
        
        # Méthode 3: Amélioration du contraste
        enhanced = cv2.equalizeHist(gray)
        decoded = pyzbar.decode(enhanced)
        if decoded:
            return decoded[0].data.decode('utf-8')
        
        # Méthode 4: Seuillage adaptatif
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)
        decoded = pyzbar.decode(thresh)
        if decoded:
            return decoded[0].data.decode('utf-8')
        
        # Méthode 5: Flou + seuillage
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        decoded = pyzbar.decode(binary)
        if decoded:
            return decoded[0].data.decode('utf-8')
            
        return None
        
    except Exception as e:
        st.error(f"Erreur détection: {e}")
        return None

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

# État
if st.session_state.scan_state == 'WAITING_OLD':
    st.info("🔍 **Scannez l'ANCIEN emplacement**")
elif st.session_state.scan_state == 'WAITING_NEW':
    st.markdown(f"""
    <div class="direction-box">
        ➡️ ALLEZ À<br>
        <span style="font-size: 36px;">{st.session_state.new_location}</span><br>
        <span style="font-size: 18px;">Quantité: {st.session_state.quantity} pièces</span>
    </div>
    """, unsafe_allow_html=True)

# Tabs
tab1, tab2 = st.tabs(["📷 Scanner Photo", "⌨️ Saisie Manuelle"])

with tab1:
    st.info("📸 Prenez une photo NETTE du code-barres (pas trop proche)")
    
    # Bouton caméra
    photo = st.camera_input("Scanner", key=f"cam_{st.session_state.scan_state}")
    
    if photo:
        # Analyser
        image = Image.open(photo)
        
        # Afficher l'image pour debug
        with st.expander("Image capturée (debug)"):
            st.image(image, width=300)
        
        # Détecter
        with st.spinner("Analyse en cours..."):
            code = detect_barcode_enhanced(image)
        
        if code:
            st.success(f"✅ Code détecté: **{code}**")
            
            # Traiter selon l'état
            if st.session_state.scan_state == 'WAITING_OLD':
                match = df[df['ancien'].str.upper() == code.upper()]
                if not match.empty:
                    st.session_state.old_location = code
                    st.session_state.new_location = match.iloc[0]['nouveau']
                    st.session_state.quantity = match.iloc[0]['quantite']
                    st.session_state.scan_state = 'WAITING_NEW'
                    st.rerun()
                else:
                    st.error(f"❌ Code non trouvé dans la base")
            
            elif st.session_state.scan_state == 'WAITING_NEW':
                if code.upper() == st.session_state.new_location.upper():
                    st.session_state.processed += 1
                    st.balloons()
                    st.success(f"✅ SUCCÈS! {st.session_state.quantity} pièces déplacées")
                    st.session_state.scan_state = 'WAITING_OLD'
                    st.session_state.old_location = None
                    st.session_state.new_location = None
                    st.session_state.quantity = None
                    st.rerun()
                else:
                    st.error(f"❌ Mauvais emplacement!")
        else:
            st.warning("""
            ⚠️ Aucun code détecté. Conseils :
            - Assurez-vous que le code est bien visible
            - Ne prenez pas la photo trop près
            - Évitez les reflets
            - Centrez bien le code
            - Utilisez la saisie manuelle si besoin
            """)

with tab2:
    with st.form("manual", clear_on_submit=True):
        code_input = st.text_input("Code-barres", placeholder="Ex: L-10-06-5")
        submit = st.form_submit_button("✅ Valider", use_container_width=True)
        
        if submit and code_input:
            code = code_input.strip().upper()
            
            if st.session_state.scan_state == 'WAITING_OLD':
                match = df[df['ancien'].str.upper() == code]
                if not match.empty:
                    st.session_state.old_location = code
                    st.session_state.new_location = match.iloc[0]['nouveau']
                    st.session_state.quantity = match.iloc[0]['quantite']
                    st.session_state.scan_state = 'WAITING_NEW'
                    st.rerun()
                else:
                    st.error(f"❌ Code non trouvé")
            
            elif st.session_state.scan_state == 'WAITING_NEW':
                if code == st.session_state.new_location.upper():
                    st.session_state.processed += 1
                    st.balloons()
                    st.session_state.scan_state = 'WAITING_OLD'
                    st.session_state.old_location = None
                    st.session_state.new_location = None
                    st.session_state.quantity = None
                    st.rerun()
                else:
                    st.error(f"❌ Mauvais emplacement!")

# Afficher quelques codes pour test
with st.expander("🧪 Codes de test"):
    st.write("Voici quelques codes de votre base:")
    st.dataframe(df.head(5))

# Reset
if st.button("🔄 RESET", use_container_width=True):
    st.session_state.scan_state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.rerun()
