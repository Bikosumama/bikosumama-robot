import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import io
import json

# --- 1. AYARLAR VE GÜVENLİK ---
st.set_page_config(page_title="bikosumama ERP v2.8", page_icon="🐾", layout="wide")

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
        sifre = st.text_input("Şifre:", type="password")
        if st.button("Giriş Yap 🚀"):
            if sifre == GIZLI_SIFRE: st.session_state.giris_yapildi = True; st.rerun()
            else: st.error("❌ Hatalı Şifre")
    st.stop()

# --- 2. GOOGLE BAĞLANTISI ---
SHEET_ID = "1I_KpIeCTLWO0P_4ZLlMtUyoWtcIGvdT2p8GkjEnzN8M"

@st.cache_resource
def google_baglan():
    try:
        info = json.loads(st.secrets["google_credentials"])
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Bağlantı Hatası: {e}")
        return None

client = google_baglan()
if client:
    spreadsheet = client.open_by_key(SHEET_ID)
else:
    st.stop()

# VİRGÜL SORUNUNU ÇÖZEN YENİ VERİ ÇEKME FONKSİYONU
def veri_cek(sekme_adi):
    sheet = spreadsheet.worksheet(sekme_adi)
    data = sheet.get_all_values() # Sayıları değiştirmeden saf metin olarak alır
    
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
    elif len(data) == 1:
        df = pd.DataFrame(columns=data[0])
    else:
        df = pd.DataFrame()
        
    df.columns = df.columns.str.strip()
    return df, sheet

# Tüm Verileri Çekelim
urunler_df, urunler_sheet = veri_cek("Urunler")
kargo_df, _ = veri_cek("Kargo_Fiyatlari")
genel_df, _ = veri_cek("Pazaryeri_Kurallari")
ozel_df, _ = veri_cek("Ozel_Kurallar")
teklif_df, _ = veri_cek("Trendyol_Teklifler")

# Sabitler
try:
    sabitler_raw, _ = veri_cek("Sabitler")
    marka_listesi = sorted([m for m in sabitler_raw['Markalar'].unique() if str(m).strip() != ''])
    kategori_listesi = sorted([k for k in sabitler_raw['Kategoriler'].unique() if str(k).strip() != ''])
except:
    marka_listesi = ["Genel"]
    kategori_listesi = ["Genel"]

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
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.get('Max Desi', 99)):
            kargo_ucreti_desi = sayisal_yap(row.get('Kargo Ücreti', 0))
            break
    
    pz_genel = genel_df[genel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == pz_adi_temiz.lower()]
    if pz_genel.empty: return 0,0,0,0,0,0,0,0,0, "Hata", "Pazaryeri Kurallarda Yok"
    
    genel_k = pz_genel.iloc[0]
    komisyon = sayisal_yap(genel_k.get('Komisyon Oranı', 0))
    kaynak = "🌍 Genel"

    pz_ozel = ozel_df[ozel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == pz_adi_temiz.lower()]
    marka_o = pz_ozel[pz_ozel['Marka'].astype(str).str.strip().str.lower() == str(marka).lower()]
    if not marka_o.empty and str(marka_o.iloc[0]['Komisyon Oranı']).strip() != '':
        komisyon = sayisal_yap(marka_o.iloc[0]['Komisyon Oranı']); kaynak = "🌟 Marka"
    else:
        kat_o = pz_ozel[pz_ozel['Kategori'].astype(str).str.strip().str.lower() == str(kategori).lower()]
        if not kat_o.empty and str(kat_o.iloc[0]['Komisyon Oranı']).strip() != '':
            komisyon = sayisal_yap(kat_o.iloc[0]['Komisyon Oranı']); kaynak = "📁 Kategori"

    komisyon_oran, stopaj_oran = komisyon/100, sayisal_yap(genel_k.get('Stopaj Oranı', 0))/100
    hizmet, islem, diger = sayisal_yap(genel_k.get('Platform Hizmet Bedeli', 0)), sayisal_yap(genel_k.get('İşlem Gideri', 0)), sayisal_yap(genel_k.get('Diğer Giderler', 0))
    efektif_stopaj = stopaj_oran / (1 + (kdv / 100))
    bolen = 1 - komisyon_oran - efektif_stopaj
    
    if bolen <= 0: return 0,0,0,0,0,0,0,0,0, "Hata", f"Oran Çok Yüksek (Bölen: {round(bolen,2)})"

    def matematik(k_maliyet):
        toplam_sabit = alis + k_maliyet + islem + diger + hizmet
        h_kar = toplam_sabit * (kar_yuzdesi / 100)
        return (toplam_sabit + h_kar) / bolen, h_kar

    b1_s, b1_k = sayisal_yap(genel_k.get('Barem 1 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 1 Kargo (TL)', 0))
    b2_s, b2_k = sayisal_yap(genel_k.get('Barem 2 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 2 Kargo (TL)', 0))

    s1, k1 = matematik(b1_k)
    if b1_s > 0 and s1 <= b1_s: return s1, k1, b1_k, s1*komisyon_oran, s1*efektif_stopaj, hizmet, islem, diger, komisyon, "1. Barem", kaynak
    s2, k2 = matematik(b2_k)
    if b2_s > 0 and s2 <= b2_s: return s2, k2, b2_k, s2*komisyon_oran, s2*efektif_stopaj, hizmet, islem, diger, komisyon, "2. Barem", kaynak
    
    s_d, k_d = matematik(kargo_ucreti_desi)
    return s_d, k_d, kargo_ucreti_desi, s_d*komisyon_oran, s_d*efektif_stopaj, hizmet, islem, diger, komisyon, "Desi", kaynak

def kampanya_analiz_motoru(desi, alis, kdv, tf, tk):
    res = fiyat_hesapla_v6("Genel", "Genel", desi, alis, kdv, "Trendyol", 0)
    pz_genel = genel_df[genel_df['Pazaryeri Adı'].str.contains("Trendyol", case=False)].iloc[0]
    stp_o = sayisal_yap(pz_genel.get('Stopaj Oranı', 0))/100
    hiz, isl, dig = sayisal_yap(pz_genel.get('Platform Hizmet Bedeli', 0)), sayisal_yap(pz_genel.get('İşlem Gideri', 0)), sayisal_yap(pz_genel.get('Diğer Giderler', 0))
    kom_t = tf * (tk/100)
    stp_t = tf * (stp_o / (1 + (kdv/100)))
    maliyet = alis + res[2] + hiz + isl + dig + kom_t + stp_t
    nktl = tf - maliyet
    nky = (nktl / (maliyet - kom_t - stp_t)) * 100 if (maliyet-kom_t-stp_t) > 0 else 0
    return nktl, nky

# --- 4. ARAYÜZ ---
st.sidebar.title("🐾 bikosumama ERP v2.8")
menu = st.sidebar.radio("MENÜ", ["📊 Dashboard", "➕ Ürün Yönetimi", "🔍 Ürün Analiz", "📊 Toplu Liste", "🎯 Ty Kampanya", "⚙️ Veritabanı"])

if menu == "📊 Dashboard":
    st.subheader("📊 Operasyonel Genel Bakış")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Ürün Sayısı", len(urunler_df))
    c2.metric("🏪 Pazaryeri", len(genel_df))
    c3.metric("🚚 Kargo Baremi", len(kargo_df))
    c4.metric("🌟 Özel Kural", len(ozel_df))
    st.dataframe(urunler_df.tail(10), use_container_width=True)

elif menu == "➕ Ürün Yönetimi":
    st.subheader("🚀 Toplu Ürün Girişi")
    with st.expander("🛠️ Sabit Değerler", expanded=True):
        c1, c2, c3 = st.columns(3)
        sabit_marka = c1.selectbox("Marka", options=marka_listesi)
        sabit_kat = c2.selectbox("Kategori", options=kategori_listesi)
        sabit_kdv = c3.selectbox("KDV %", [20, 10, 1])
    yapistirilan_df = st.data_editor(pd.DataFrame(columns=["Stok Kodu", "Ürün Adı", "Desi", "Alış Fiyatı"]), num_rows="dynamic", use_container_width=True)
    if st.button("🔥 Kaydet"):
        hazir = [[str(r["Stok Kodu"]), sabit_marka, str(r["Ürün Adı"]), sabit_kat, sayisal_yap(r["Desi"]), sayisal_yap(r["Alış Fiyatı"]), sabit_kdv] for _, r in yapistirilan_df.dropna(subset=["Stok Kodu"]).iterrows()]
        if hazir:
            urunler_sheet.append_rows(hazir)
            st.success("Kaydedildi!"); st.cache_resource.clear()

elif menu == "🔍 Ürün Analiz":
    st.subheader("🔍 Ürün Analiz ve Hata Raporlama")
    arama = st.text_input("Ürün Ara...")
    if arama:
        filtrelenmis = urunler_df[urunler_df['Ürün Adı'].str.contains(arama, case=False) | urunler_df['Stok Kodu'].str.contains(arama, case=False)]
        event = st.dataframe(filtrelenmis[['Stok Kodu', 'Marka', 'Ürün Adı', 'Alış Fiyatı']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if len(event.selection.rows) > 0:
            u = filtrelenmis.iloc[event.selection.rows[0]]
            kar = st.number_input("Hedef Kar %", value=20.0)
            
            pazaryerleri = [str(p).strip() for p in genel_df['Pazaryeri Adı'].unique() if str(p).strip() != '']
            if not pazaryerleri:
                st.error("Google Tabloda 'Pazaryeri_Kurallari' sekmesinde hiç veri bulamadım!")
            
            analiz = []
            for pz in pazaryerleri:
                res = fiyat_hesapla_v6(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, kar)
                if res[0] > 0: 
                    analiz.append({"Pazaryeri": pz, "Fiyat": f"{round(res[0],2)} TL", "Kar": f"{round(res[1],2)} TL", "Kom %": f"%{res[8]}", "Kargo": f"{res[2]} TL", "Durum": "✅ Başarılı"})
                else:
                    analiz.append({"Pazaryeri": pz, "Fiyat": "HATA", "Kar": "-", "Kom %": "-", "Kargo": "-", "Durum": f"❌ {res[10]}"})
            
            st.table(pd.DataFrame(analiz))

elif menu == "📊 Toplu Liste":
    st.subheader("📋 Toplu Fiyat Listesi")
    kar_o = st.number_input("Genel Kar %", value=20.0)
    if st.button("🚀 Hesapla"):
        toplu = []
        for _, u in urunler_df.iterrows():
            if not str(u['Ürün Adı']): continue
            satir = {"SKU": u['Stok Kodu'], "Ürün": u['Ürün Adı']}
            for pz in genel_df['Pazaryeri Adı'].unique():
                if str(pz).strip() == '': continue
                res = fiyat_hesapla_v6(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, kar_o)
                satir[pz] = round(res[0], 2) if res[0] > 0 else "Hata"
            toplu.append(satir)
        st.dataframe(pd.DataFrame(toplu), use_container_width=True)

elif menu == "🎯 Ty Kampanya":
    st.subheader("🎯 Trendyol Süzgeci")
    minkar = st.number_input("Min Kar %", value=10.0)
    if st.button("🚀 Çalıştır"):
        results = []
        for _, t in teklif_df.iterrows():
            u = urunler_df[urunler_df['Stok Kodu'].astype(str) == str(t['Stok Kodu'])]
            if not u.empty:
                u = u.iloc[0]
                tf, tk = sayisal_yap(t.get('Teklif 1 Fiyat')), sayisal_yap(t.get('Teklif 1 Komisyon'))
                ktl, ky = kampanya_analiz_motoru(sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), tf, tk)
                results.append({"SKU": t['Stok Kodu'], "Ürün": u['Ürün Adı'], "Teklif Karı": f"%{round(ky,1)}", "Karar": "✅" if ky >= minkar else "❌"})
        st.dataframe(pd.DataFrame(results), use_container_width=True)

elif menu == "⚙️ Veritabanı":
    st.subheader("⚙️ Veritabanı")
    tabs = st.tabs(["Ürünler", "Genel", "Özel", "Kargo", "Teklifler"])
    tabs[0].dataframe(urunler_df); tabs[1].dataframe(genel_df); tabs[2].dataframe(ozel_df); tabs[3].dataframe(kargo_df); tabs[4].dataframe(teklif_df)
