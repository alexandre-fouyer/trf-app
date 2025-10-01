import streamlit as st
import pandas as pd
import re
from datetime import datetime
import time
import base64

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
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# JavaScript pour scanner en continu
SCANNER_HTML = """
<div id="scanner-container" style="position: relative; width: 100%; max-width: 500px; margin: auto;">
    <video id="video" style="width: 100%; height: auto;"></video>
    <canvas id="canvas" style="display: none;"></canvas>
    <div id="result" style="margin-top: 20px; padding: 10px; background: #f0f0f0; border-radius: 5px; min-height: 50px;"></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/quagga@0.12.1/dist/quagga.min.js"></script>

<script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const resultDiv = document.getElementById('result');
    let scanning = true;
    
    // Accéder à la caméra arrière
    navigator.mediaDevices.getUserMedia({ 
        video: { 
            facingMode: 'environment',
            width: { ideal: 1280 },
            height: { ideal: 720 }
        } 
    })
    .then(function(stream) {
        video.srcObject = stream;
        video.play();
        requestAnimationFrame(scan);
    })
    .catch(function(err) {
        console.error('Erreur caméra:', err);
        resultDiv.innerHTML = 'Erreur: Impossible d\'accéder à la caméra';
    });
    
    function scan() {
        if (video.readyState === video.HAVE_ENOUGH_DATA && scanning) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            
            // Essayer de détecter un QR code
            const code = jsQR(imageData.data, imageData.width, imageData.height, {
                inversionAttempts: "dontInvert"
            });
            
            if (code) {
                scanning = false;
                resultDiv.innerHTML = 'Code détecté: ' + code.data;
                
                // Envoyer le résultat à Streamlit
                window.parent.postMessage({
                    type: 'barcode_detected',
                    data: code.data
                }, '*');
                
                // Recommencer le scan après 2 secondes
                setTimeout(() => {
                    scanning = true;
                    resultDiv.innerHTML = 'Recherche...';
                }, 2000);
            } else {
                // Essayer avec Quagga pour les codes-barres 1D
                Quagga.decodeSingle({
                    decoder: {
                        readers: ["ean_reader", "ean_8_reader", "code_128_reader", "code_39_reader"]
                    },
                    locate: true,
                    src: canvas.toDataURL()
                }, function(result) {
                    if(result && result.codeResult) {
                        scanning = false;
                        resultDiv.innerHTML = 'Code détecté: ' + result.codeResult.code;
                        
                        // Envoyer le résultat à Streamlit
                        window.parent.postMessage({
                            type: 'barcode_detected',
                            data: result.codeResult.code
                        }, '*');
                        
                        setTimeout(() => {
                            scanning = true;
                            resultDiv.innerHTML = 'Recherche...';
                        }, 2000);
                    }
                });
            }
        }
        requestAnimationFrame(scan);
    }
</script>
"""

# Initialisation session state
if 'state' not in st.session_state:
    st.session_state.state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.session_state.processed = 0
    st.session_state.history = []
    st.session_state.last_scan = ""

# Charger le CSV
@st.cache_data
def load_csv():
    try:
        df = pd.read_csv('emplacements.csv', sep=';', header=None, encoding='utf-8')
        
        if len(df.columns) >= 3:
            df = df.iloc[:, :3]
            df.columns = ['ancien', 'quantite', 'nouveau']
        else:
            return pd.DataFrame()
        
        df['ancien'] = df['ancien'].astype(str).str.strip()
        df['nouveau'] = df['nouveau'].astype(str).str.strip()
        df['quantite'] = pd.to_numeric(df['quantite'], errors='coerce').fillna(0).astype(int)
        
        df = df[df['ancien'] != '1']
        df = df[df['ancien'].str.len() > 0]
        df = df[~df['ancien'].str.contains('ancien', case=False, na=False)]
        
        return df
        
    except Exception as e:
        st.error(f"Erreur CSV: {e}")
        return pd.DataFrame({
            'ancien': ['TEST001', 'TEST002'],
            'quantite': [10, 25],
            'nouveau': ['A-01-01', 'A-01-02']
        })

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
tab1, tab2 = st.tabs(["📷 Scanner Auto", "⌨️ Saisie Manuelle"])

with tab1:
    # Scanner JavaScript en continu
    st.components.v1.html(SCANNER_HTML, height=600)
    
    # Champ caché pour recevoir le résultat du JavaScript
    result_container = st.container()
    with result_container:
        scan_result = st.text_input("Résultat du scan", key="scan_result", label_visibility="collapsed")
        if scan_result:
            st.session_state.last_scan = scan_result
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
            time.sleep(2)
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
            st.session_state.last_scan = ""

# Boutons d'action
st.markdown("---")
if st.button("🔄 RESET", type="secondary", use_container_width=True):
    st.session_state.state = 'WAITING_OLD'
    st.session_state.old_location = None
    st.session_state.new_location = None
    st.session_state.quantity = None
    st.session_state.last_scan = ""
    st.rerun()
