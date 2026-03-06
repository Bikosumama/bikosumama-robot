import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import io
import json

# --- 1. AYARLAR VE GÜVENLİK ---
st.set_page_config(page_title="bikosumama ERP v2", page_icon="🐾", layout="wide")

# Şık Tasarım İçin CSS Dokunuşları
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e1e4e8; box-shadow: 0px 4px 6px rgba(0,0,0,0.02); }
    .main { background-color: #f8f9fa; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    </style>
""", unsafe_allow_html=True)

GIZLI_SIFRE = "biko2026"
if "giris_yapildi" not in st.session_state: st.session_state.giris_yapildi = False

if not st.session_state.giris_yapildi:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 bikosumama ERP")
        st.info("Güvenli erişim için lütfen yönetici şifresini giriniz.")
        sifre = st.text_input("Şifre:", type="password")
        if st.button("Sisteme Giriş Yap 🚀"):
            if sifre == GIZLI_SIFRE: st.session_state.giris_yapildi = True; st.rerun()
            else: st.error("❌ Hatalı Şifre")
    st.stop()

# --- 2. GOOGLE SHEETS YAZMA/OKUMA BAĞLANTISI ---
SHEET_ID = "1I_KpIeCTLWO0P_4ZLlMtUyoWtcIGvdT2p8GkjEnzN8M"

@st.cache_resource
def google_baglan():
    # Streamlit Secrets'tan (google_credentials) JSON verisini alıyoruz
    try:
        info = json.loads(st.secrets["google_credentials"])
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ Bağlantı Hatası: Lütfen Secrets kısmındaki JSON formatını kontrol edin. Hata: {e}")
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

# Verileri Anlık Çekelim
urunler_df, urunler_sheet = veri_cek("Urunler")
kargo_df, _ = veri_cek("Kargo_Fiyatlari")
genel_df, _ = veri_cek("Pazaryeri_Kurallari")
ozel_df, _ = veri_cek("Ozel_Kurallar")
teklif_df, teklif_sheet = veri_cek("Trendyol_Teklifler")

# --- 3. MATEMATİKSEL HESAPLAMA MOTORU ---
def sayisal_yap(deger):
    if pd.isna(deger) or str(deger).strip() == '': return 0.0
    try: return float(str(deger).replace('%', '').replace(',', '.').replace(' ', ''))
    except: return 0.0

def fiyat_hesapla_v5(marka, kategori, desi, alis, kdv, pz_adi, kar_yuzdesi):
    kargo_ucreti_desi = 0
    pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == pz_adi]
    if pz_kargo.empty: pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == 'Genel']
    for _, row in pz_kargo.iterrows():
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.get('Max Desi', 99)):
            kargo_ucreti_desi = sayisal_yap(row.get('Kargo Ücreti', 0))
            break
    
    pz_genel = genel_df[genel_df['Pazaryeri Adı'] == pz_adi]
    if pz_genel.empty: return 0,0,0,0,0,0,0,0,0, "Hata", "Yok"
    genel_k = pz_genel.iloc[0]
    komisyon = sayisal_yap(genel_k.get('Komisyon Oranı', 0)); kaynak = "🌍 Genel"

    pz_ozel = ozel_df[ozel_df['Pazaryeri Adı'] == pz_adi]
    marka_o = pz_ozel[pz_ozel['Marka'].astype(str).str.strip() == marka]
    if not marka_o.empty and str(marka_o.iloc[0]['Komisyon Oranı']).strip() != '':
        komisyon = sayisal_yap(marka_o.iloc[0]['Komisyon Oranı']); kaynak = "🌟 Marka"
    else:
        kat_o = pz_ozel[pz_ozel['Kategori'].astype(str).str.strip() == kategori]
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
    if u_sinir > 0:
        s_u, k_u = matematik(0)
        if s_u < u_sinir: return s_u, k_u, 0, s_u*komisyon_oran, s_u*efektif_stopaj, hizmet, islem, diger, komisyon, "Alıcı Öder", kaynak
    s_d, k_d = matematik(kargo_ucreti_desi)
    return s_d, k_d, kargo_ucreti_desi, s_d*komisyon_oran, s_d*efektif_stopaj, hizmet, islem, diger, komisyon, "Desi", kaynak

def kampanya_analiz_motoru(desi, alis, kdv, teklif_fiyat, teklif_komisyon):
    pz_adi = "Trendyol"
    kargo_ucreti = 0
    pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == pz_adi]
    if pz_kargo.empty: pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == 'Genel']
    for _, row in pz_kargo.iterrows():
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.get('Max Desi', 99)):
            kargo_ucreti = sayisal_yap(row.get('Kargo Ücreti', 0)); break
            
    pz_genel = genel_df[genel_df['Pazaryeri Adı'] == pz_adi]
    if pz_genel.empty: return 0, 0
    genel_k = pz_genel.iloc[0]
    
    stopaj_oran = sayisal_yap(genel_k.get('Stopaj Oranı', 0)) / 100
    hizmet = sayisal_yap(genel_k.get('Platform Hizmet Bedeli', 0))
    islem = sayisal_yap(genel_k.get('İşlem Gideri', 0))
    diger = sayisal_yap(genel_k.get('Diğer Giderler', 0))
    
    b1_s, b1_k = sayisal_yap(genel_k.get('Barem 1 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 1 Kargo (TL)', 0))
    b2_s, b2_k = sayisal_yap(genel_k.get('Barem 2 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 2 Kargo (TL)', 0))
    if b1_s > 0 and teklif_fiyat <= b1_s: uygulanan_kargo = b1_k
    elif b2_s > 0 and teklif_fiyat <= b2_s: uygulanan_kargo = b2_k
    else: uygulanan_kargo = kargo_ucreti

    komisyon_tutari = teklif_fiyat * (teklif_komisyon / 100)
    efektif_stopaj = stopaj_oran / (1 + (kdv / 100))
    stopaj_tutari = teklif_fiyat * efektif_stopaj
    
    toplam_maliyet = alis + uygulanan_kargo + islem + diger + hizmet + komisyon_tutari + stopaj_tutari
    net_kar_tl = teklif_fiyat - toplam_maliyet
    
    sabit_maliyet_tabani = alis + uygulanan_kargo + islem + diger + hizmet
    if sabit_maliyet_tabani > 0: net_kar_yuzde = (net_kar_tl / sabit_maliyet_tabani) * 100
    else: net_kar_yuzde = 0
    
    return net_kar_tl, net_kar_yuzde

# --- 4. ARAYÜZ MODÜLLERİ ---
st.sidebar.title("🐾 bikosumama ERP v2")
menu = st.sidebar.radio("MENÜ", ["📊 Dashboard", "➕ Ürün Yönetimi", "🔍 Ürün Analiz", "📊 Toplu Liste", "🎯 Ty Kampanya", "⚙️ Veritabanı"])
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Güvenli Çıkış"):
    st.session_state.giris_yapildi = False; st.rerun()

if menu == "📊 Dashboard":
    st.subheader("📊 Operasyonel Genel Bakış")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Kayıtlı Ürün", len(urunler_df))
    c2.metric("🏪 Pazaryeri Sayısı", len(genel_df))
    c3.metric("🚚 Kargo Baremi", len(kargo_df))
    c4.metric("🌟 Özel Kural", len(ozel_df))
    
    st.markdown("---")
    st.write("### 🕒 Son Eklenen Ürünler")
    st.dataframe(urunler_df.tail(10), use_container_width=True, hide_index=True)

elif menu == "➕ Ürün Yönetimi":
    st.subheader("➕ Yeni Ürün Kayıt Formu")
    st.info("Buradan eklediğiniz ürünler anında Google E-Tablo'ya yazılır.")
    
    with st.form("yeni_urun_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            stok = st.text_input("Stok Kodu (SKU)*", placeholder="Örn: BIKO-101")
            ad = st.text_input("Ürün Adı*", placeholder="Örn: Pro Plan Somonlu 12kg")
            marka = st.text_input("Marka", placeholder="Örn: Pro Plan")
        with col2:
            kat = st.selectbox("Kategori", ["Kuru Mama", "Yaş Mama", "Ödül Maması", "Kum", "Aksesuar", "Ek Takviye"])
            alis = st.number_input("Alış Fiyatı (KDV Dahil)", min_value=0.0, step=0.01)
            desi = st.number_input("Desi Değeri", min_value=0.0, step=0.1)
            kdv_orani = st.selectbox("KDV Oranı (%)", [20, 10, 1], index=0)
        
        submit = st.form_submit_button("Ürünü Kaydet ve Google Tablo'ya Yaz 🚀")
        
        if submit:
            if not stok or not ad:
                st.warning("⚠️ Lütfen Stok Kodu ve Ürün Adı alanlarını doldurun.")
            else:
                try:
                    yeni_satir = [stok, marka, ad, kat, desi, alis, kdv_orani]
                    urunler_sheet.append_row(yeni_satir)
                    st.success(f"✅ Başarılı: '{ad}' ürünü Google E-Tablolar'a eklendi!")
                    st.cache_resource.clear() # Veriyi yenilemek için cache temizle
                except Exception as e:
                    st.error(f"❌ Kayıt Hatası: {e}")

elif menu == "🔍 Ürün Analiz":
    st.subheader("🔍 Detaylı Ürün Kar Analizi")
    arama = st.text_input("Aramak için yazın (Stok Kodu veya İsim)...")
    if arama:
        mask = (urunler_df['Ürün Adı'].astype(str).str.contains(arama, case=False) | urunler_df['Stok Kodu'].astype(str).str.contains(arama, case=False))
        filtrelenmis = urunler_df[mask]
        event = st.dataframe(filtrelenmis[['Stok Kodu', 'Marka', 'Ürün Adı', 'Alış Fiyatı']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        if len(event.selection.rows) > 0:
            u = filtrelenmis.iloc[event.selection.rows[0]]
            st.markdown(f"#### 📊 **Seçilen Ürün:** {u['Ürün Adı']}")
            kar = st.number_input("Hedef Net Kar Marjı (%)", min_value=0.0, value=20.0, step=0.5)
            
            analiz_data = []
            for pz in genel_df['Pazaryeri Adı'].unique():
                res = fiyat_hesapla_v5(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, kar)
                s, k, kg, km_t, stp, hiz, isl, dgr, km_y, ntu, kay = res
                if s > 0:
                    analiz_data.append({
                        "Pazaryeri": pz, 
                        "SATIŞ FİYATI": f"{round(s, 2)} TL", 
                        "NET KAR (TL)": f"{round(k, 2)} TL", 
                        "Komisyon (%)": f"%{km_y}",
                        "Kargo Gideri": f"{round(kg, 2)} ({ntu})", 
                        "Komisyon (TL)": f"{round(km_t, 2)} TL", 
                        "Kural Kaynağı": kay
                    })
            st.table(pd.DataFrame(analiz_data))

elif menu == "📊 Toplu Liste":
    st.subheader("📋 Kategori Bazlı Toplu Fiyat Listesi")
    kar_modu = st.radio("Kar Modu:", ["Global (Tüm Mağaza)", "Kategori Bazlı"])
    
    if kar_modu == "Global (Tüm Mağaza)":
        g_kar = st.number_input("Genel Kar Marjı (%)", value=20.0)
        aktif_karlar = {k: g_kar for k in urunler_df['Kategori'].unique()}
    else:
        st.write("Her kategori için kâr oranını girin:")
        aktif_karlar = {}
        kategoriler = [k for k in urunler_df['Kategori'].unique() if str(k).strip() != '']
        cols = st.columns(4)
        for i, kat in enumerate(kategoriler):
            aktif_karlar[kat] = cols[i % 4].number_input(f"{kat} (%)", value=20.0, key=f"kat_{kat}")
    
    if st.button("🚀 Tüm Listeyi Hesapla"):
        toplu = []
        for _, u in urunler_df.iterrows():
            if str(u['Ürün Adı']).strip() == '': continue
            kar_o = aktif_karlar.get(u['Kategori'], 20.0)
            satir = {"SKU": u['Stok Kodu'], "Ürün": u['Ürün Adı'], "Kategori": u['Kategori'], "Alış": u['Alış Fiyatı']}
            for pz in genel_df['Pazaryeri Adı'].unique():
                res = fiyat_hesapla_v5(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, kar_o)
                satir[pz] = round(res[0], 2) if res[0] > 0 else "Hata"
            toplu.append(satir)
        df_toplu = pd.DataFrame(toplu)
        st.dataframe(df_toplu, use_container_width=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: df_toplu.to_excel(wr, index=False)
        st.download_button("📥 Excel Olarak İndir", buf.getvalue(), file_name="bikosumama_fiyatlar.xlsx")

elif menu == "🎯 Ty Kampanya":
    st.subheader("🎯 Trendyol Kampanya Analiz Süzgeci")
    min_kar = st.number_input("Minimum Kabul Edilebilir Kar (%)", value=10.0)
    if st.button("🚀 Teklifleri Süzgeçten Geçir"):
        sonuclar = []
        for _, t in teklif_df.iterrows():
            stok = str(t.get('Stok Kodu', '')).strip()
            eslesen = urunler_df[urunler_df['Stok Kodu'].astype(str).str.strip() == stok]
            if not eslesen.empty:
                u = eslesen.iloc[0]
                satir = {"SKU": stok, "Ürün": u['Ürün Adı']}
                for i in range(1, 4):
                    tf, tk = sayisal_yap(t.get(f'Teklif {i} Fiyat')), sayisal_yap(t.get(f'Teklif {i} Komisyon'))
                    if tf > 0:
                        ktl, ky = kampanya_analiz_motoru(sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), tf, tk)
                        satir[f"Teklif {i}"] = f"✅ KABUL (%{round(ky,1)})" if ky >= min_kar else f"❌ RED (%{round(ky,1)})"
                    else: satir[f"Teklif {i}"] = "-"
                sonuclar.append(satir)
        st.dataframe(pd.DataFrame(sonuclar), use_container_width=True)

elif menu == "⚙️ Veritabanı":
    st.subheader("⚙️ Ham Veri Görüntüleyici")
    tab1, tab2, tab3 = st.tabs(["Ürünler", "Kurallar", "Kampanya Teklifleri"])
    with tab1: st.dataframe(urunler_df)
    with tab2: st.write("Pazaryeri Kuralları"); st.dataframe(genel_df)
    with tab3: st.dataframe(teklif_df)
