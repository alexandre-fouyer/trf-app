import streamlit as st
import pandas as pd
import re
from datetime import datetime
import json

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
    .big-font { font-size: 24px !important; font-weight: bold; }
    .success-box { 
        padding: 20px; 
        background-color: #d4edda; 
        border-radius: 10px; 
        margin: 10px 0;
    }
    .error-box { 
        padding: 20px; 
        background-color: #f8d7da; 
        border-radius: 10px; 
        margin: 10px 0;
    }
    .direction-box { 
        padding: 20px; 
        background-color: #fff3cd; 
        border-radius: 10px; 
        margin: 10px 0;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
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
        # Données de test
        return pd.DataFrame({
            'ancien': ['TEST001', 'TEST002'],
            'quantite': [10, 25],
            'nouveau': ['A-01-01', 'A-01-02']
        })

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

# Interface HTML pour scanner natif
def barcode_scanner_component():
    scanner_html = """
    <div style="margin: 20px 0;">
        <input 
            type="text" 
            id="barcodeInput" 
            placeholder="Scanner ou taper le code..."
            style="
                width: 100%;
                padding: 15px;
                font-size: 20px;
                border: 2px solid #4CAF50;
                border-radius: 10px;
                text-align: center;
            "
            autofocus
            autocomplete="off"
            inputmode="none"
        />
        <script>
            // Focus automatique
            document.getElementById('barcodeInput').focus();
            
            // Capturer les scans
            document.getElementById('barcodeInput').addEventListener('input', function(e) {
                const value = e.target.value;
                // Les scanners ajoutent souvent un retour chariot
                if (value.includes('\\n') || value.includes('\\r') || value.length > 5) {
                    // Envoyer à Streamlit
                    const cleanValue = value.replace(/[\\n\\r]/g, '');
                    window.parent.postMessage({
                        type: 'BARCODE_SCAN',
                        code: cleanValue
                    }, '*');
                    // Clear input
                    setTimeout(() => {
                        e.target.value = '';
                    }, 100);
                }
            });
            
            // Enter key
            document.getElementById('barcodeInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && e.target.value) {
                    window.parent.postMessage({
                        type: 'BARCODE_SCAN',
                        code: e.target.value
                    }, '*');
                    e.target.value = '';
                }
            });
        </script>
    </div>
    """
    return scanner_html

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

# Scanner natif ou input
st.markdown("### Scanner")

# Component HTML pour scanner
st.components.v1.html(barcode_scanner_component(), height=100)

# Alternative : Input manuel
with st.form("manual_input", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        code_input = st.text_input("Ou tapez le code manuellement", label_visibility="collapsed", placeholder="Ex: A-01-01-1")
    with col2:
        submit = st.form_submit_button("✅ Valider", use_container_width=True, type="primary")
    
    if submit and code_input:
        cleaned = clean_code(code_input)
        
        if st.session_state.scan_state == 'WAITING_OLD':
            # Chercher ancien
            match = df[df['ancien'].str.upper() == cleaned]
            if not match.empty:
                st.session_state.old_location = cleaned
                st.session_state.new_location = match.iloc[0]['nouveau']
                st.session_state.quantity = match.iloc[0]['quantite']
                st.session_state.scan_state = 'WAITING_NEW'
                st.rerun()
            else:
                st.error(f"❌ Code non trouvé : {cleaned}")
        
        elif st.session_state.scan_state == 'WAITING_NEW':
            # Vérifier nouveau
            expected = clean_code(st.session_state.new_location)
            if cleaned == expected:
                st.session_state.processed += 1
                st.success(f"✅ **SUCCÈS!** {st.session_state.quantity} pièces déplacées")
                st.balloons()
                # Reset
                st.session_state.scan_state = 'WAITING_OLD'
                st.session_state.old_location = None
                st.session_state.new_location = None
                st.session_state.quantity = None
                st.rerun()
            else:
                st.error(f"❌ Mauvais emplacement! Attendu: {st.session_state.new_location}")

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
    st.rerun()

# Script pour recevoir messages du scanner HTML
st.components.v1.html("""
<script>
window.addEventListener('message', function(e) {
    if (e.data.type === 'BARCODE_SCAN') {
        // Simuler un submit du formulaire avec le code scanné
        const input = window.parent.document.querySelector('input[type="text"]');
        const button = window.parent.document.querySelector('button[type="submit"]');
        if (input && button) {
            input.value = e.data.code;
            button.click();
        }
    }
});
</script>
""", height=0)
