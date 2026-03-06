import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import io
import json

# --- 1. AYARLAR VE GÜVENLİK ---
st.set_page_config(page_title="bikosumama ERP v2.5", page_icon="🐾", layout="wide")

# Şık Tasarım İçin CSS
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
        sifre = st.text_input("Yönetici Şifresi:", type="password")
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

def veri_cek(sekme_adi):
    sheet = spreadsheet.worksheet(sekme_adi)
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip()
    return df, sheet

# Tüm Verileri Çekelim
urunler_df, urunler_sheet = veri_cek("Urunler")
kargo_df, _ = veri_cek("Kargo_Fiyatlari")
genel_df, _ = veri_cek("Pazaryeri_Kurallari")
ozel_df, _ = veri_cek("Ozel_Kurallar")
teklif_df, _ = veri_cek("Trendyol_Teklifler")

# Sabitleri Çekelim (Marka ve Kategori Listesi İçin)
try:
    sabitler_raw, _ = veri_cek("Sabitler")
    marka_listesi = sorted([m for m in sabitler_raw['Markalar'].unique() if str(m).strip() != ''])
    kategori_listesi = sorted([k for k in sabitler_raw['Kategoriler'].unique() if str(k).strip() != ''])
except:
    marka_listesi = ["Lütfen Sabitler Sekmesini Oluşturun"]
    kategori_listesi = ["Lütfen Sabitler Sekmesini Oluşturun"]

# --- 3. HESAPLAMA MOTORLARI ---
def sayisal_yap(deger):
    if pd.isna(deger) or str(deger).strip() == '': return 0.0
    try: return float(str(deger).replace('%', '').replace(',', '.').replace(' ', ''))
    except: return 0.0

def fiyat_hesapla_v6(marka, kategori, desi, alis, kdv, pz_adi, kar_yuzdesi):
    # İsim eşleşme hatasını önlemek için pz_adi'ni temizleyelim
    pz_adi_temiz = str(pz_adi).strip()
    
    # 1. KARGO HESAPLAMA
    kargo_ucreti_desi = 0
    # Pazaryerine özel kargo ayarı var mı bak, yoksa 'Genel'i kullan
    pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == pz_adi_temiz.lower()]
    if pz_kargo.empty: 
        pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == 'Genel']
    
    for _, row in pz_kargo.iterrows():
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.get('Max Desi', 99)):
            kargo_ucreti_desi = sayisal_yap(row.get('Kargo Ücreti', 0))
            break
    
    # 2. KOMİSYON VE GİDERLERİ BULMA
    # Pazaryeri kurallarını küçük/büyük harf duyarsız ara
    pz_genel_mask = genel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == pz_adi_temiz.lower()
    pz_genel = genel_df[pz_genel_mask]
    
    if pz_genel.empty: 
        return 0,0,0,0,0,0,0,0,0, "Veri Yok", "Pazaryeri Bulunamadı"
        
    genel_k = pz_genel.iloc[0]
    komisyon = sayisal_yap(genel_k.get('Komisyon Oranı', 0))
    kaynak = "🌍 Genel"

    # 3. ÖZEL KURALLAR (Marka veya Kategori Bazlı)
    pz_ozel = ozel_df[ozel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == pz_adi_temiz.lower()]
    
    # Marka kontrolü
    marka_o = pz_ozel[pz_ozel['Marka'].astype(str).str.strip().str.lower() == str(marka).lower()]
    if not marka_o.empty and str(marka_o.iloc[0]['Komisyon Oranı']).strip() != '':
        komisyon = sayisal_yap(marka_o.iloc[0]['Komisyon Oranı'])
        kaynak = "🌟 Marka"
    else:
        # Kategori kontrolü
        kat_o = pz_ozel[pz_ozel['Kategori'].astype(str).str.strip().str.lower() == str(kategori).lower()]
        if not kat_o.empty and str(kat_o.iloc[0]['Komisyon Oranı']).strip() != '':
            komisyon = sayisal_yap(kat_o.iloc[0]['Komisyon Oranı'])
            kaynak = "📁 Kategori"

    # 4. MATEMATİKSEL HESAPLAMA (Ters Matris)
    komisyon_oran = komisyon / 100
    stopaj_oran = sayisal_yap(genel_k.get('Stopaj Oranı', 0)) / 100
    hizmet = sayisal_yap(genel_k.get('Platform Hizmet Bedeli', 0))
    islem = sayisal_yap(genel_k.get('İşlem Gideri', 0))
    diger = sayisal_yap(genel_k.get('Diğer Giderler', 0))
    
    efektif_stopaj = stopaj_oran / (1 + (kdv / 100))
    bolen = 1 - komisyon_oran - efektif_stopaj
    
    if bolen <= 0: return 0,0,0,0,0,0,0,0,0, "Hata", "Oran Hatası"

    def matematik(k_maliyet):
        toplam_sabit = alis + k_maliyet + islem + diger + hizmet
        h_kar = toplam_sabit * (kar_yuzdesi / 100)
        satis_fiyati = (toplam_sabit + h_kar) / bolen
        return satis_fiyati, h_kar

    # Barem Kontrolleri
    b1_s = sayisal_yap(genel_k.get('Barem 1 Sınırı (TL)', 0))
    b1_k = sayisal_yap(genel_k.get('Barem 1 Kargo (TL)', 0))
    b2_s = sayisal_yap(genel_k.get('Barem 2 Sınırı (TL)', 0))
    b2_k = sayisal_yap(genel_k.get('Barem 2 Kargo (TL)', 0))

    # 1. Barem Testi
    s1, k1 = matematik(b1_k)
    if b1_s > 0 and s1 <= b1_s:
        return s1, k1, b1_k, s1*komisyon_oran, s1*efektif_stopaj, hizmet, islem, diger, komisyon, "1. Barem", kaynak

    # 2. Barem Testi
    s2, k2 = matematik(b2_k)
    if b2_s > 0 and s2 <= b2_s:
        return s2, k2, b2_k, s2*komisyon_oran, s2*efektif_stopaj, hizmet, islem, diger, komisyon, "2. Barem", kaynak

    # Desi Bazlı Test
    s_d, k_d = matematik(kargo_ucreti_desi)
    return s_d, k_d, kargo_ucreti_desi, s_d*komisyon_oran, s_d*efektif_stopaj, hizmet, islem, diger, komisyon, "Desi", kaynak
def kampanya_analiz_motoru(desi, alis, kdv, tf, tk):
    pz_adi = "Trendyol"
    kargo_ucreti = 0
    pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == pz_adi]
    if pz_kargo.empty: pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == 'Genel']
    for _, row in pz_kargo.iterrows():
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.get('Max Desi', 99)):
            kargo_ucreti = sayisal_yap(row.get('Kargo Ücreti', 0)); break
    pz_genel = genel_df[genel_df['Pazaryeri Adı'] == pz_adi].iloc[0]
    stopaj_oran = sayisal_yap(pz_genel.get('Stopaj Oranı', 0)) / 100
    hizmet, islem, diger = sayisal_yap(pz_genel.get('Platform Hizmet Bedeli', 0)), sayisal_yap(pz_genel.get('İşlem Gideri', 0)), sayisal_yap(pz_genel.get('Diğer Giderler', 0))
    b1_s, b1_k = sayisal_yap(pz_genel.get('Barem 1 Sınırı (TL)', 0)), sayisal_yap(pz_genel.get('Barem 1 Kargo (TL)', 0))
    b2_s, b2_k = sayisal_yap(pz_genel.get('Barem 2 Sınırı (TL)', 0)), sayisal_yap(pz_genel.get('Barem 2 Kargo (TL)', 0))
    uk = b1_k if tf <= b1_s else (b2_k if tf <= b2_s else kargo_ucreti)
    kom_t = tf * (tk / 100)
    ef_stp = stopaj_oran / (1 + (kdv / 100))
    stp_t = tf * ef_stp
    maliyet = alis + uk + islem + diger + hizmet + kom_t + stp_t
    nktl = tf - maliyet
    nky = (nktl / (alis + uk + islem + diger + hizmet)) * 100 if (alis + uk + islem + diger + hizmet) > 0 else 0
    return nktl, nky

# --- 4. ARAYÜZ MODÜLLERİ ---
st.sidebar.title("🐾 bikosumama ERP v2.5")
menu = st.sidebar.radio("MENÜ", ["📊 Dashboard", "➕ Ürün Yönetimi", "🔍 Ürün Analiz", "📊 Toplu Liste", "🎯 Ty Kampanya", "⚙️ Veritabanı"])
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Güvenli Çıkış"):
    st.session_state.giris_yapildi = False; st.rerun()

if menu == "📊 Dashboard":
    st.subheader("📊 Operasyonel Genel Bakış")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Kayıtlı Ürün", len(urunler_df))
    c2.metric("🏪 Pazaryeri", len(genel_df))
    c3.metric("🚚 Kargo Baremi", len(kargo_df))
    c4.metric("🌟 Özel Kural", len(ozel_df))
    st.markdown("---")
    st.write("### 🕒 Son Kayıtlar")
    st.dataframe(urunler_df.tail(10), use_container_width=True, hide_index=True)

elif menu == "➕ Ürün Yönetimi":
    st.subheader("🚀 Profesyonel Toplu Ürün Girişi")
    with st.expander("🛠️ 1. Sabit Değerleri Seçin (Açılır Menü)", expanded=True):
        c1, c2, c3 = st.columns(3)
        sabit_marka = c1.selectbox("Marka Seçiniz", options=marka_listesi)
        sabit_kat = c2.selectbox("Kategori Seçiniz", options=kategori_listesi)
        sabit_kdv = c3.selectbox("KDV Oranı (%)", [20, 10, 1], index=0)
    st.markdown("---")
    st.write("### 📋 2. Excel Verisini Yapıştırın")
    st.info("Excel'den Başlıklar (Stok Kodu, Ürün Adı, Desi, Alış Fiyatı) dahil şekilde kopyalayıp aşağıdaki tabloya yapıştırın.")
    yapistirilan_df = st.data_editor(
        pd.DataFrame(columns=["Stok Kodu", "Ürün Adı", "Desi", "Alış Fiyatı"]),
        num_rows="dynamic", use_container_width=True, key="toplu_editor"
    )
    if st.button("🔥 Doğrula ve Google Tablo'ya Gönder"):
        temiz_df = yapistirilan_df.dropna(subset=["Stok Kodu", "Ürün Adı"])
        if temiz_df.empty: st.warning("⚠️ Lütfen veri girin!")
        else:
            try:
                with st.spinner("İşleniyor..."):
                    hazir = [[str(r["Stok Kodu"]), sabit_marka, str(r["Ürün Adı"]), sabit_kat, sayisal_yap(r["Desi"]), sayisal_yap(r["Alış Fiyatı"]), sabit_kdv] for _, r in temiz_df.iterrows()]
                    urunler_sheet.append_rows(hazir)
                    st.success(f"✅ {len(hazir)} Ürün Başarıyla Eklendi!")
                    st.cache_resource.clear()
            except Exception as e: st.error(f"Hata: {e}")

elif menu == "🔍 Ürün Analiz":
    st.subheader("🔍 Detaylı Ürün Analizi")
    arama = st.text_input("Ürün veya Stok Kodu Ara...")
    if arama:
        filtrelenmis = urunler_df[urunler_df['Ürün Adı'].str.contains(arama, case=False) | urunler_df['Stok Kodu'].str.contains(arama, case=False)]
        event = st.dataframe(filtrelenmis[['Stok Kodu', 'Marka', 'Ürün Adı', 'Alış Fiyatı']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if len(event.selection.rows) > 0:
            u = filtrelenmis.iloc[event.selection.rows[0]]
            kar = st.number_input("Hedef Kar (%)", value=20.0)
            analiz = []
            for pz in genel_df['Pazaryeri Adı'].unique():
                res = fiyat_hesapla_v5(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, kar)
                if res[0] > 0: analiz.append({"Pazaryeri": pz, "SATIŞ": f"{round(res[0],2)} TL", "KAR": f"{round(res[1],2)} TL", "Kom %": f"%{res[8]}", "Kargo": f"{round(res[2],2)}", "Kaynak": res[10]})
            st.table(pd.DataFrame(analiz))

elif menu == "📊 Toplu Liste":
    st.subheader("📋 Kategori Bazlı Kar Listesi")
    kar_modu = st.radio("Mod:", ["Global", "Kategori Bazlı"])
    if kar_modu == "Global":
        gkar = st.number_input("Kar (%)", value=20.0)
        karlar = {k: gkar for k in urunler_df['Kategori'].unique()}
    else:
        karlar = {}; cats = [k for k in urunler_df['Kategori'].unique() if str(k).strip() != '']
        cols = st.columns(4)
        for i, c in enumerate(cats): karlar[c] = cols[i%4].number_input(f"{c} %", value=20.0)
    if st.button("🚀 Tümünü Hesapla"):
        toplu = []
        for _, u in urunler_df.iterrows():
            if str(u['Ürün Adı']).strip() == '': continue
            k_o = karlar.get(u['Kategori'], 20.0)
            satir = {"SKU": u['Stok Kodu'], "Ürün": u['Ürün Adı']}
            for pz in genel_df['Pazaryeri Adı'].unique():
                res = fiyat_hesapla_v5(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, k_o)
                satir[pz] = round(res[0], 2) if res[0] > 0 else "Hata"
            toplu.append(satir)
        st.dataframe(pd.DataFrame(toplu), use_container_width=True)

elif menu == "🎯 Ty Kampanya":
    st.subheader("🎯 Trendyol Kampanya Süzgeci")
    minkar = st.number_input("Min Kar (%)", value=10.0)
    if st.button("🚀 Süzgeçten Geçir"):
        results = []
        for _, t in teklif_df.iterrows():
            u = urunler_df[urunler_df['Stok Kodu'].astype(str) == str(t['Stok Kodu'])]
            if not u.empty:
                u = u.iloc[0]; s = {"SKU": t['Stok Kodu'], "Ürün": u['Ürün Adı']}
                for i in range(1, 4):
                    tf, tk = sayisal_yap(t.get(f'Teklif {i} Fiyat')), sayisal_yap(t.get(f'Teklif {i} Komisyon'))
                    if tf > 0:
                        ktl, ky = kampanya_analiz_motoru(sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), tf, tk)
                        s[f"Teklif {i}"] = f"✅ %{round(ky,1)}" if ky >= minkar else f"❌ %{round(ky,1)}"
                    else: s[f"Teklif {i}"] = "-"
                results.append(s)
        st.dataframe(pd.DataFrame(results), use_container_width=True)

elif menu == "⚙️ Veritabanı":
    st.subheader("⚙️ Veritabanı")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Ürünler", "Genel Kurallar", "Özel Kurallar", "Kargo", "🎯 Teklifler"])
    with tab1: st.dataframe(urunler_df)
    with tab2: st.dataframe(genel_df)
    with tab3: st.dataframe(ozel_df)
    with tab4: st.dataframe(kargo_df)
    with tab5: st.dataframe(teklif_df)

