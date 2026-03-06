import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import io
import json

# --- 1. AYARLAR VE GÜVENLİK ---
st.set_page_config(page_title="bikosumama ERP v3.0", page_icon="🐾", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e1e4e8; box-shadow: 0px 4px 6px rgba(0,0,0,0.02); }
    .main { background-color: #f8f9fa; }
    </style>
""", unsafe_allow_html=True)

GIZLI_SIFRE = "biko2026"
if "giris_yapildi" not in st.session_state: st.session_state.giris_yapildi = False

if not st.session_state.giris_yapildi:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 bikosumama ERP")
        st.info("Sadece Okuma Modu - Kararlı Sürüm")
        sifre = st.text_input("Şifre:", type="password")
        if st.button("Giriş Yap 🚀"):
            if sifre == GIZLI_SIFRE: st.session_state.giris_yapildi = True; st.rerun()
            else: st.error("❌ Hatalı Şifre")
    st.stop()

# --- 2. GOOGLE BAĞLANTISI (SADECE OKUMA) ---
SHEET_ID = "1I_KpIeCTLWO0P_4ZLlMtUyoWtcIGvdT2p8GkjEnzN8M"

@st.cache_resource
def google_baglan():
    try:
        info = json.loads(st.secrets["google_credentials"])
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Bağlantı Hatası: Lütfen Secrets alanını kontrol edin.")
        return None

client = google_baglan()
if client:
    spreadsheet = client.open_by_key(SHEET_ID)
else:
    st.stop()

# VİRGÜL SORUNUNU ÇÖZEN VERİ ÇEKME FONKSİYONU
def veri_cek(sekme_adi):
    sheet = spreadsheet.worksheet(sekme_adi)
    data = sheet.get_all_values() 
    
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
    elif len(data) == 1:
        df = pd.DataFrame(columns=data[0])
    else:
        df = pd.DataFrame()
        
    df.columns = df.columns.str.strip()
    return df, sheet

# Tüm Verileri Çekelim
urunler_df, _ = veri_cek("Urunler")
kargo_df, _ = veri_cek("Kargo_Fiyatlari")
genel_df, _ = veri_cek("Pazaryeri_Kurallari")
ozel_df, _ = veri_cek("Ozel_Kurallar")
teklif_df, _ = veri_cek("Trendyol_Teklifler")

# --- 3. HESAPLAMA MOTORU ---
def sayisal_yap(deger):
    if pd.isna(deger) or str(deger).strip() == '': return 0.0
    try: return float(str(deger).replace('%', '').replace(',', '.').replace(' ', ''))
    except: return 0.0

def fiyat_hesapla_v6(marka, kategori, desi, alis, kdv, pz_adi, kar_yuzdesi):
    pz_adi_temiz = str(pz_adi).strip()
    
    kargo_ucreti_desi = 0
    pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == pz_adi_temiz.lower()]
    if pz_kargo.empty: pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == 'Genel']
    for _, row in pz_kargo.iterrows():
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.
