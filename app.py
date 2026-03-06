import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="bikosumama Fiyat Robotu", page_icon="🐾", layout="wide")

# --- 🔒 ŞİFRE KORUMA ---
GIZLI_SIFRE = "biko2026"
if "giris_yapildi" not in st.session_state: st.session_state.giris_yapildi = False
if not st.session_state.giris_yapildi:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 Güvenli Giriş")
        girilen_sifre = st.text_input("Yönetici Şifresi:", type="password")
        if st.button("Giriş Yap 🚀"):
            if girilen_sifre == GIZLI_SIFRE: st.session_state.giris_yapildi = True; st.rerun()
            else: st.error("❌ Hatalı şifre!")
    st.stop()

st.title("🤖 bikosumama | Gelişmiş Fiyatlandırma Paneli")
st.markdown("---")

SHEET_ID = "1I_KpIeCTLWO0P_4ZLlMtUyoWtcIGvdT2p8GkjEnzN8M"

def sayisal_yap(deger):
    if pd.isna(deger) or str(deger).strip() == '': return 0.0
    deger = str(deger).replace('%', '').replace(',', '.').replace(' ', '')
    try: return float(deger)
    except: return 0.0

@st.cache_data(ttl=30)
def veri_getir():
    try:
        base_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet="
        urunler = pd.read_csv(base_url + "Urunler")
        kargo = pd.read_csv(base_url + "Kargo_Fiyatlari")
        genel_kurallar = pd.read_csv(base_url + "Pazaryeri_Kurallari")
        ozel_kurallar = pd.read_csv(base_url + "Ozel_Kurallar")
        
        # Teklifler Sekmesini Çek
        try: teklifler = pd.read_csv(base_url + "Trendyol_Teklifler")
        except: teklifler = pd.DataFrame(columns=['Stok Kodu', 'Teklif 1 Fiyat', 'Teklif 1 Komisyon', 'Teklif 2 Fiyat', 'Teklif 2 Komisyon', 'Teklif 3 Fiyat', 'Teklif 3 Komisyon'])

        for df in [urunler, kargo, genel_kurallar, ozel_kurallar, teklifler]:
            df.columns = df.columns.str.strip()
            df.fillna('', inplace=True)
            
        return urunler, kargo, genel_kurallar, ozel_kurallar, teklifler
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return None, None, None, None, None

urunler_df, kargo_df, genel_df, ozel_df, teklif_df = veri_getir()

def fiyat_hesapla_v4(marka, kategori, desi, alis, kdv, pz_adi, kar_yuzdesi):
    kargo_ucreti_desi = 0
    pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == str(pz_adi).strip().lower()]
    if pz_kargo.empty: pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == 'Genel']
    for _, row in pz_kargo.iterrows():
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.get('Max Desi', 99)):
            kargo_ucreti_desi = sayisal_yap(row.get('Kargo Ücreti', 0))
            break
    
    pz_genel = genel_df[genel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == str(pz_adi).strip().lower()]
    if pz_genel.empty: return 0,0,0,0,0,0,0,0,0, "Hata", "Yok"
    genel_k = pz_genel.iloc[0]
    komisyon = sayisal_yap(genel_k.get('Komisyon Oranı', 0)); kaynak = "🌍 Genel"

    pz_ozel = ozel_df[ozel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == str(pz_adi).strip().lower()]
    marka_o = pz_ozel[pz_ozel['Marka'].astype(str).str.strip().str.lower() == str(marka).strip().lower()]
    if not marka_o.empty and str(marka_o.iloc[0]['Komisyon Oranı']).strip() != '':
        komisyon = sayisal_yap(marka_o.iloc[0]['Komisyon Oranı']); kaynak = "🌟 Marka"
    else:
        kat_o = pz_ozel[pz_ozel['Kategori'].astype(str).str.strip().str.lower() == str(kategori).strip().lower()]
        if not kat_o.empty and str(kat_o.iloc[0]['Komisyon Oranı']).strip() != '':
            komisyon = sayisal_yap(kat_o.iloc[0]['Komisyon Oranı']); kaynak = "📁 Kategori"

    komisyon_oran, stopaj_oran = komisyon/100, sayisal_yap(genel_k.get('Stopaj Oranı', 0))/100
    hizmet, islem, diger = sayisal_yap(genel_k.get('Platform Hizmet Bedeli', 0)), sayisal_yap(genel_k.get('İşlem Gideri', 0)), sayisal_yap(genel_k.get('Diğer Giderler', 0))
    efektif_stopaj = stopaj_oran / (1 + (kdv / 100))
    bolen = 1 - komisyon_oran - efektif_stopaj
    if bolen <= 0: return 0,0,0,0,0,0,0,0,0, "Hata", "Oran Hatası"

    def matematik(k_maliyet):
        toplam_sabit = alis + k_maliyet + islem + diger + hizmet
        h_kar = toplam_sabit * (kar_yuzdesi / 100)
        return (toplam_sabit + h_kar) / bolen, h_kar

    b1_s, b1_k = sayisal_yap(genel_k.get('Barem 1 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 1 Kargo (TL)', 0))
    b2_s, b2_k = sayisal_yap(genel_k.get('Barem 2 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 2 Kargo (TL)', 0))
    u_sinir = sayisal_yap(genel_k.get('Ücretsiz Kargo Sınırı (TL)', 0))

    s1, k1 = matematik(b1_k)
    if b1_s > 0 and s1 <= b1_s: return s1, k1, b1_k, s1*komisyon_oran, s1*efektif_stopaj, hizmet, islem, diger, komisyon, "1. Barem", kaynak
    s2, k2 = matematik(b2_k)
    if b2_s > 0 and s2 <= b2_s: return s2, k2, b2_k, s2*komisyon_oran, s2*efektif_stopaj, hizmet, islem, diger, komisyon, "2. Barem", kaynak
    if u_sinir > 0
