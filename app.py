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

# --- YARDIMCI FONKSİYONLAR ---
def sayisal_yap(deger):
    if pd.isna(deger) or str(deger).strip() == '': return 0.0
    deger = str(deger).replace('%', '').replace(',', '.').replace(' ', '')
    try: return float(deger)
    except: return 0.0

def temiz_kod(deger):
    d = str(deger).strip()
    if d.endswith('.0'): return d[:-2]
    if d.lower() == 'nan': return ''
    return d

@st.cache_data(ttl=300)
def excel_oku(file):
    xls = pd.read_excel(file, sheet_name=None)
    
    def sekme_getir(isim, default_cols):
        if isim in xls:
            df = xls[isim]
            df.columns = df.columns.astype(str).str.strip()
            df.fillna('', inplace=True)
            return df
        else:
            return pd.DataFrame(columns=default_cols)

    # Urunler sekmesine 'Min Satış Fiyatı' eklendi!
    urunler = sekme_getir("Urunler", ["Stok Kodu", "Barkod", "Marka", "Ürün Adı", "Alış Fiyatı", "KDV Oranı", "Desi", "Kategori", "Rakip Fiyatı", "Min Satış Fiyatı"])
    kargo = sekme_getir("Kargo_Fiyatlari", ["Pazaryeri Adı", "Min Desi", "Max Desi", "Kargo Ücreti"])
    genel_kurallar = sekme_getir("Pazaryeri_Kurallari", ["Pazaryeri Adı", "Komisyon Oranı", "Stopaj Oranı", "Platform Hizmet Bedeli", "İşlem Gideri", "Diğer Giderler", "Barem 1 Sınırı (TL)", "Barem 1 Kargo (TL)", "Barem 2 Sınırı (TL)", "Barem 2 Kargo (TL)", "Ücretsiz Kargo Sınırı (TL)"])
    ozel_kurallar = sekme_getir("Ozel_Kurallar", ["Pazaryeri Adı", "Marka", "Kategori", "Komisyon Oranı"])
    teklifler = sekme_getir("Trendyol_Teklifler", ['Barkod', 'Stok Kodu', 'Teklif 1 Fiyat', 'Teklif 1 Komisyon', 'Teklif 2 Fiyat', 'Teklif 2 Komisyon', 'Teklif 3 Fiyat', 'Teklif 3 Komisyon'])

    return urunler, kargo, genel_kurallar, ozel_kurallar, teklifler

# --- YAN MENÜ VE DOSYA YÜKLEME ---
st.sidebar.title("🐾 bikosumama ERP")
st.sidebar.markdown("Sürüm 6.0 (Firma Taban Fiyat Koruması)")

uploaded_file = st.sidebar.file_uploader("📂 Veritabanı Excel'ini Yükle", type=["xlsx", "xls"])

if uploaded_file is None:
    st.title("🤖 bikosumama | Gelişmiş Fiyatlandırma Paneli")
    st.info("👈 Lütfen sol menüden Excel dosyanızı yükleyin. (Not: Urunler sekmenize 'Min Satış Fiyatı' sütunu eklemeyi unutmayın!)")
    st.stop()

# Dosya yüklendiyse verileri oku
try:
    urunler_df, kargo_df, genel_df, ozel_df, teklif_df = excel_oku(uploaded_file)
except Exception as e:
    st.error(f"Excel okunurken bir hata oluştu: {e}")
    st.stop()

# --- HESAPLAMA MOTORLARI ---
def fiyat_hesapla_v5(marka, kategori, desi, alis, kdv, pz_adi, kar_yuzdesi, min_fiyat=0.0):
    kargo_ucreti_desi = 0
    pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == str(pz_adi).strip().lower()]
    if pz_kargo.empty: pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == 'Genel']
    for _, row in pz_kargo.iterrows():
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.get('Max Desi', 99)):
            kargo_ucreti_desi = sayisal_yap(row.get('Kargo Ücreti', 0))
            break
    
    pz_genel = genel_df[genel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == str(pz_adi).strip().lower()]
    if pz_genel.empty: return 0,0,0,0,0,0,0,0,0, "Hata", "Yok", 0
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
    if bolen <= 0: return 0,0,0,0,0,0,0,0,0, "Hata", "Oran Hatası", 0

    def matematik(k_maliyet):
        toplam_sabit = alis + k_maliyet + islem + diger + hizmet
        h_kar = toplam_sabit * (kar_yuzdesi / 100)
        return (toplam_sabit + h_kar) / bolen, h_kar

    b1_s, b1_k = sayisal_yap(genel_k.get('Barem 1 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 1 Kargo (TL)', 0))
    b2_s, b2_k = sayisal_yap(genel_k.get('Barem 2 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 2 Kargo (TL)', 0))
    u_sinir = sayisal_yap(genel_k.get('Ücretsiz Kargo Sınırı (TL)', 0))

    def bul_hedef():
        s1, k1 = matematik(b1_k)
        if b1_s > 0 and s1 <= b1_s: return s1, k1, b1_k, "1. Barem"
        s2, k2 = matematik(b2_k)
        if b2_s > 0 and s2 <= b2_s: return s2, k2, b2_k, "2. Barem"
        if u_sinir > 0:
            s_u, k_u = matematik(0)
            if s_u < u_sinir: return s_u, k_u, 0, "Alıcı Öder"
        s_d, k_d = matematik(kargo_ucreti_desi)
        return s_d, k_d, kargo_ucreti_desi, "Desi"

    s_hedef, k_hedef, kg_hedef, b_isim = bul_hedef()
    gerceklesecek_kar_yuzdesi = kar_yuzdesi

    # 🛑 FİRMA TABAN FİYAT KURALI KONTROLÜ
    if min_fiyat > 0 and s_hedef < min_fiyat:
        s_hedef = min_fiyat
        b_isim = "Desi"
        kg_hedef = kargo_ucreti_desi
        
        # Taban fiyata çıkınca kargo baremi değişiyor mu kontrol edelim
        if b1_s > 0 and s_hedef <= b1_s: 
            kg_hedef = b1_k; b_isim = "1. Barem"
        elif b2_s > 0 and s_hedef <= b2_s: 
            kg_hedef = b2_k; b_isim = "2. Barem"
        elif u_sinir > 0 and s_hedef < u_sinir: 
            kg_hedef = 0; b_isim = "Alıcı Öder"
            
        kom_t = s_hedef * komisyon_oran
        stp_t = s_hedef * efektif_stopaj
        tm = alis + kg_hedef + islem + diger + hizmet + kom_t + stp_t
        k_hedef = s_hedef - tm
        
        taban = alis + kg_hedef + islem + diger + hizmet
        gerceklesecek_kar_yuzdesi = (k_hedef / taban) * 100 if taban > 0 else 0
        kaynak = "🚨 Firm. Min. Fiyat Kuralı"

    kom_tutar = s_hedef * komisyon_oran
    stp_tutar = s_hedef * efektif_stopaj

    return s_hedef, k_hedef, kg_hedef, kom_tutar, stp_tutar, hizmet, islem, diger, komisyon, b_isim, kaynak, gerceklesecek_kar_yuzdesi

def kampanya_analiz_motoru(desi, alis, kdv, teklif_fiyat, teklif_komisyon, pz_adi="Trendyol"):
    kargo_ucreti = 0
    pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == pz_adi.lower()]
    if pz_kargo.empty: pz_kargo = kargo_df[kargo_df['Pazaryeri Adı'].astype(str).str.strip() == 'Genel']
    for _, row in pz_kargo.iterrows():
        if sayisal_yap(row.get('Min Desi', 0)) <= desi <= sayisal_yap(row.get('Max Desi', 99)):
            kargo_ucreti = sayisal_yap(row.get('Kargo Ücreti', 0)); break
            
    pz_genel = genel_df[genel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == pz_adi.lower()]
    if pz_genel.empty: return 0, 0
    genel_k = pz_genel.iloc[0]
    
    stopaj_oran = sayisal_yap(genel_k.get('Stopaj Oranı', 0)) / 100
    hizmet = sayisal_yap(genel_k.get('Platform Hizmet Bedeli', 0))
    islem = sayisal_yap(genel_k.get('İşlem Gideri', 0))
    diger = sayisal_yap(genel_k.get('Diğer Giderler', 0))
    
    b1_s, b1_k = sayisal_yap(genel_k.get('Barem 1 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 1 Kargo (TL)', 0))
    b2_s, b2_k = sayisal_yap(genel_k.get('Barem 2 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 2 Kargo (TL)', 0))
    u_sinir = sayisal_yap(genel_k.get('Ücretsiz Kargo Sınırı (TL)', 0))
    
    uygulanan_kargo = kargo_ucreti
    if b1_s > 0 and teklif_fiyat <= b1_s: uygulanan_kargo = b1_k
    elif b2_s > 0 and teklif_fiyat <= b2_s: uygulanan_kargo = b2_k
    elif u_sinir > 0 and teklif_fiyat >= u_sinir: uygulanan_kargo = 0

    komisyon_tutari = teklif_fiyat * (teklif_komisyon / 100)
    efektif_stopaj = stopaj_oran / (1 + (kdv / 100))
    stopaj_tutari = teklif_fiyat * efektif_stopaj
    
    toplam_maliyet = alis + uygulanan_kargo + islem + diger + hizmet + komisyon_tutari + stopaj_tutari
    net_kar_tl = teklif_fiyat - toplam_maliyet
    
    sabit_maliyet_tabani = alis + uygulanan_kargo + islem + diger + hizmet
    if sabit_maliyet_tabani > 0: net_kar_yuzde = (net_kar_tl / sabit_maliyet_tabani) * 100
    else: net_kar_yuzde = 0
    
    return net_kar_tl, net_kar_yuzde

def renk_karari(val):
    if isinstance(val, str):
        if '✅ KABUL' in val: return 'background-color: #d4edda; color: #155724; font-weight: bold;'
        elif '❌ RED' in val: return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
    return ''

# --- ARAYÜZ ---
menu = st.sidebar.radio("MENÜ", ["📈 Dashboard", "🔍 Ürün Arama & Analiz", "📊 Toplu Liste", "🎯 Ty Kampanya Simülatörü", "⚙️ Veritabanı"])
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sistemden Çıkış Yap"):
    st.session_state.giris_yapildi = False; st.rerun()

st.title("🤖 bikosumama | Gelişmiş Fiyatlandırma Paneli")
st.markdown("---")

if menu == "📈 Dashboard":
    st.subheader("📊 Operasyonel Genel Bakış")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Toplam Ürün Sayısı", len(urunler_df[urunler_df['Stok Kodu'] != '']))
    col2.metric("🏪 Aktif Pazaryeri", len(genel_df[genel_df['Pazaryeri Adı'] != '']))
    
    kategoriler = urunler_df[urunler_df['Kategori'] != '']['Kategori'].nunique()
    markalar = urunler_df[urunler_df['Marka'] != '']['Marka'].nunique()
    col3.metric("📁 Kategori Sayısı", kategoriler)
    col4.metric("🌟 Marka Sayısı", markalar)
    
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**📁 Kategorilere Göre Ürün Dağılımı**")
        kat_dagilim = urunler_df[urunler_df['Kategori'] != '']['Kategori'].value_counts()
        if not kat_dagilim.empty: st.bar_chart(kat_dagilim, color="#ffaa00")
        else: st.info("Kategori verisi bulunamadı.")
            
    with c2:
        st.markdown("**🌟 Markalara Göre Ürün Dağılımı**")
        marka_dagilim = urunler_df[urunler_df['Marka'] != '']['Marka'].value_counts().head(10)
        if not marka_dagilim.empty: st.bar_chart(marka_dagilim, color="#00aaff")
        else: st.info("Marka verisi bulunamadı.")

elif menu == "🔍 Ürün Arama & Analiz":
    st.subheader("🔍 Hızlı Ürün Arama & Detaylı Analiz")
    arama_metni = st.text_input("Aramak için yazın...", placeholder="Örn: Pro Plan, 101...")
    
    if 'Barkod' in urunler_df.columns:
        mask = (urunler_df['Ürün Adı'].astype(str).str.contains(arama_metni, case=False) | 
                urunler_df['Stok Kodu'].astype(str).str.contains(arama_metni, case=False) |
                urunler_df['Barkod'].astype(str).str.contains(arama_metni, case=False))
    else:
        mask = (urunler_df['Ürün Adı'].astype(str).str.contains(arama_metni, case=False) | 
                urunler_df['Stok Kodu'].astype(str).str.contains(arama_metni, case=False))
        
    filtrelenmis_df = urunler_df[mask]
    
    if arama_metni != "":
        gosterim_sutunlari = ['Stok Kodu', 'Marka', 'Ürün Adı', 'Alış Fiyatı']
        if 'Barkod' in urunler_df.columns: gosterim_sutunlari.insert(1, 'Barkod')
        if 'Min Satış Fiyatı' in urunler_df.columns: gosterim_sutunlari.append('Min Satış Fiyatı')

        event = st.dataframe(filtrelenmis_df[gosterim_sutunlari], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        if len(event.selection.rows) > 0:
            u = filtrelenmis_df.iloc[event.selection.rows[0]]
            
            st.markdown("### 💰 Kâr Marjı Hedefi ile Satış Fiyatı Bulma")
            if "arama_hedef_kar" not in st.session_state: st.session_state.arama_hedef_kar = 20.0
            kar = st.number_input("Hedef Net Kar Marjı (%)", min_value=0.0, step=0.5, key="arama_hedef_kar")
            
            firma_min_fiyat = sayisal_yap(u.get('Min Satış Fiyatı', 0))
            if firma_min_fiyat > 0:
                st.warning(f"⚠️ **DİKKAT:** Bu ürün için firma taban fiyatı **{firma_min_fiyat} TL** olarak belirlenmiş. Sistem fiyatın bu rakamın altına düşmesine izin vermeyecektir.")

            analiz_data = []
            for pz in genel_df['Pazaryeri Adı'].unique():
                res = fiyat_hesapla_v5(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, kar, firma_min_fiyat)
                s, k, kg, km_t, stp, hiz, isl, dgr, km_y, b_isim, kay, gercek_kar = res
                
                if s > 0:
                    analiz_data.append({
                        "Pazaryeri": pz, 
                        "SATIŞ FİYATI": f"{round(s, 2)} TL", 
                        "NET KAR (TL)": f"{round(k, 2)} TL", 
                        "Gerçekleşen Kâr (%)": f"%{round(gercek_kar, 1)}",
                        "Komisyon Oranı": f"%{km_y}",
                        "Kargo Gideri": f"{round(kg, 2)} TL", 
                        "Kural Kaynağı": kay
                    })
            
            # Tabloyu renklendir (Firm taban fiyatı devreye girdiyse kaynağı kırmızı/kalın yap)
            def kural_renk(val):
                if isinstance(val, str) and '🚨 Firm.' in val: return 'color: red; font-weight: bold;'
                return ''
                
            st.dataframe(pd.DataFrame(analiz_data).style.map(kural_renk, subset=['Kural Kaynağı']), use_container_width=True)
            
            st.markdown("---")
            st.markdown("### ⚔️ Rekabet Analizi (Rakip Fiyatına İnersem Ne Olur?)")
            
            varsayilan_rakip_fiyati = 0.0
            if 'Rakip Fiyatı' in u and sayisal_yap(u['Rakip Fiyatı']) > 0:
                varsayilan_rakip_fiyati = sayisal_yap(u['Rakip Fiyatı'])
                st.info(f"Excel'den çekilen Rakip Fiyatı: **{varsayilan_rakip_fiyati} TL**")
                
            rakip_fiyati = st.number_input("Piyasa / Rakip Satış Fiyatı (TL)", min_value=0.0, value=varsayilan_rakip_fiyati, step=1.0)
            
            if rakip_fiyati > 0:
                rekabet_data = []
                for pz in genel_df['Pazaryeri Adı'].unique():
                    if str(pz).strip() == '': continue
                    komisyon = 0
                    pz_genel = genel_df[genel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == str(pz).strip().lower()]
                    if not pz_genel.empty: komisyon = sayisal_yap(pz_genel.iloc[0].get('Komisyon Oranı', 0))
                        
                    pz_ozel = ozel_df[ozel_df['Pazaryeri Adı'].astype(str).str.strip().str.lower() == str(pz).strip().lower()]
                    marka_o = pz_ozel[pz_ozel['Marka'].astype(str).str.strip().str.lower() == str(u['Marka']).strip().lower()]
                    if not marka_o.empty and str(marka_o.iloc[0]['Komisyon Oranı']).strip() != '':
                        komisyon = sayisal_yap(marka_o.iloc[0]['Komisyon Oranı'])
                    else:
                        kat_o = pz_ozel[pz_ozel['Kategori'].astype(str).str.strip().str.lower() == str(u['Kategori']).strip().lower()]
                        if not kat_o.empty and str(kat_o.iloc[0]['Komisyon Oranı']).strip() != '':
                            komisyon = sayisal_yap(kat_o.iloc[0]['Komisyon Oranı'])
                    
                    r_kar_tl, r_kar_yuzde = kampanya_analiz_motoru(sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), rakip_fiyati, komisyon, pz)
                    
                    durum = "🟢 KÂRLI" if r_kar_yuzde >= kar else ("🔴 ZARAR / ÇOK DÜŞÜK" if r_kar_yuzde < 5 else "🟠 RİSKLİ")
                    rekabet_data.append({
                        "Pazaryeri": pz,
                        "Satış Fiyatı": f"{rakip_fiyati} TL",
                        "Gerçekleşen Net Kâr (%)": f"%{round(r_kar_yuzde, 2)}",
                        "Gerçekleşen Net Kâr (TL)": f"{round(r_kar_tl, 2)} TL",
                        "Durum": durum
                    })
                
                def rekabet_renk(val):
                    if isinstance(val, str):
                        if '🟢' in val: return 'background-color: #d4edda; color: green; font-weight: bold;'
                        elif '🔴' in val: return 'background-color: #f8d7da; color: red; font-weight: bold;'
                        elif '🟠' in val: return 'background-color: #fff3cd; color: orange; font-weight: bold;'
                    return ''
                    
                df_rekabet = pd.DataFrame(rekabet_data)
                st.dataframe(df_rekabet.style.map(rekabet_renk, subset=['Durum']), use_container_width=True)

    else: st.info("👆 Başlamak için ürün adı, stok kodu veya barkod yazın.")

elif menu == "📊 Toplu Liste":
    st.subheader("📋 Dinamik Toplu Fiyat Listesi")
    kar_modu = st.radio("Kar Marjı Belirleme Yöntemi:", ["🌍 Tüm Ürünlere Aynı Kar Marjını Uygula", "📁 Kategori Bazlı Kar Marjı Uygula"])
    
    kategori_karlari = {}
    
    if "global_kar_hafiza" not in st.session_state: st.session_state.global_kar_hafiza = 20.0
    if "varsayilan_kar_hafiza" not in st.session_state: st.session_state.varsayilan_kar_hafiza = 20.0
    
    if kar_modu == "🌍 Tüm Ürünlere Aynı Kar Marjını Uygula":
        global_kar = st.number_input("Global Hedef Kar Marjı (%)", min_value=0.0, max_value=100.0, step=0.5, key="global_kar_hafiza")
    else:
        st.markdown("**Aşağıdan kategorilerinize özel kâr marjlarını belirleyin:**")
        kategoriler = [k for k in urunler_df['Kategori'].unique() if str(k).strip() != '']
        for i in range(0, len(kategoriler), 4):
            cols = st.columns(4)
            for j in range(4):
                if i + j < len(kategoriler):
                    kat = kategoriler[i + j]
                    key_ismi = f"hafiza_kar_{kat}"
                    if key_ismi not in st.session_state: st.session_state[key_ismi] = 20.0
                    with cols[j]:
                        kategori_karlari[kat] = st.number_input(f"{kat} (%)", min_value=0.0, max_value=100.0, step=0.5, key=key_ismi)
        varsayilan_kar = st.number_input("Kategorisi Boş Olanlar İçin Kar (%)", min_value=0.0, max_value=100.0, step=0.5, key="varsayilan_kar_hafiza")
    
    st.markdown("---")

    if st.button("🚀 Tümünü Hesapla"):
        with st.spinner('Tüm ürünler hesaplanıyor, lütfen bekleyin...'):
            p_yerleri = genel_df['Pazaryeri Adı'].unique()
            toplu_data = []
            for _, urun in urunler_df.iterrows():
                if str(urun['Ürün Adı']).strip() == '': continue
                if kar_modu == "🌍 Tüm Ürünlere Aynı Kar Marjını Uygula": aktif_kar = global_kar
                else:
                    kat_ismi = str(urun.get('Kategori', '')).strip()
                    aktif_kar = kategori_karlari.get(kat_ismi, varsayilan_kar)

                barkod_metni = urun.get('Barkod', '') if 'Barkod' in urun else ''
                firma_min_fiyat = sayisal_yap(urun.get('Min Satış Fiyatı', 0))
                
                satir = {
                    "Barkod": barkod_metni,
                    "Stok Kodu": urun['Stok Kodu'], 
                    "Ürün": urun['Ürün Adı'], 
                    "Hedef Kar": f"%{aktif_kar}"
                }
                
                for pz in p_yerleri:
                    res_t = fiyat_hesapla_v5(urun['Marka'], urun['Kategori'], sayisal_yap(urun['Desi']), sayisal_yap(urun['Alış Fiyatı']), sayisal_yap(urun['KDV Oranı']), pz, aktif_kar, firma_min_fiyat)
                    satir[pz] = round(res_t[0], 2) if res_t[0] > 0 else "HATA"
                toplu_data.append(satir)
            
            df_toplu = pd.DataFrame(toplu_data)
            
            def hata_boya(val):
                if val == 'HATA': return 'color: red; font-weight: bold; background-color: #ffe6e6;'
                return ''
                
            st.dataframe(df_toplu.style.map(hata_boya), use_container_width=True)
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: df_toplu.to_excel(wr, index=False, sheet_name='Toplu_Fiyatlar')
            st.download_button("📥 Sonuçları Excel Olarak İndir", data=buf.getvalue(), file_name="bikosumama_fiyatlar.xlsx", mime="application/vnd.ms-excel")

elif menu == "🎯 Ty Kampanya Simülatörü":
    st.subheader("🎯 Trendyol Fırsat Merkezi Süzgeci")
    
    if "kampanya_min_kar_hafiza" not in st.session_state: st.session_state.kampanya_min_kar_hafiza = 10.0
    min_kar_hedefi = st.number_input("Süzgeç: Kabul Edilebilir Minimum Kâr Marjı (%)", min_value=0.0, step=0.5, key="kampanya_min_kar_hafiza")
    
    if st.button("🚀 Teklifleri Analiz Et"):
        if teklif_df.empty or len(teklif_df) == 0:
            st.warning("⚠️ Trendyol_Teklifler sekmesinde veri bulunamadı.")
        else:
            with st.spinner('Teklifler Süzgeçten Geçiriliyor... Akıllı Eşleştirme Aktif!'):
                analiz_sonuclari = []
                
                urunler_stok_temiz = urunler_df['Stok Kodu'].apply(temiz_kod)
                if 'Barkod' in urunler_df.columns: urunler_barkod_temiz = urunler_df['Barkod'].apply(temiz_kod)
                else: urunler_barkod_temiz = pd.Series([''] * len(urunler_df), index=urunler_df.index)
                
                for _, teklif in teklif_df.iterrows():
                    stok_kodu = temiz_kod(teklif.get('Stok Kodu', ''))
                    barkod_teklif = temiz_kod(teklif.get('Barkod', ''))
                    
                    if not stok_kodu and not barkod_teklif: continue
                    eslesen_urun = pd.DataFrame()
                    
                    if stok_kodu: eslesen_urun = urunler_df[urunler_stok_temiz == stok_kodu]
                    if eslesen_urun.empty and barkod_teklif: eslesen_urun = urunler_df[urunler_barkod_temiz == barkod_teklif]
                    if eslesen_urun.empty: continue
                    
                    u = eslesen_urun.iloc[0]
                    desi = sayisal_yap(u.get('Desi', 0))
                    alis = sayisal_yap(u.get('Alış Fiyatı', 0))
                    kdv = sayisal_yap(u.get('KDV Oranı', 20))
                    firma_min_fiyat = sayisal_yap(u.get('Min Satış Fiyatı', 0))
                    
                    satir = {
                        "Barkod": barkod_teklif if barkod_teklif else u.get('Barkod', ''),
                        "Stok Kodu": stok_kodu if stok_kodu else u.get('Stok Kodu', ''), 
                        "Ürün Adı": u['Ürün Adı']
                    }
                    teklif_gecerli_mi = False
                    
                    for i in range(1, 4):
                        t_fiyat = sayisal_yap(teklif.get(f'Teklif {i} Fiyat', 0))
                        t_komisyon = sayisal_yap(teklif.get(f'Teklif {i} Komisyon', 0))
                        
                        if t_fiyat > 0:
                            teklif_gecerli_mi = True
                            kar_tl, kar_yuzde = kampanya_analiz_motoru(desi, alis, kdv, t_fiyat, t_komisyon)
                            
                            # EĞER FİRMA TABAN FİYATI VARSA VE KAMPANYA FİYATI BUNUN ALTINDAYSA DİREKT REDDET
                            if firma_min_fiyat > 0 and t_fiyat < firma_min_fiyat:
                                satir[f"Teklif {i}"] = f"❌ RED (FİRMA KURALI İHLALİ)"
                            elif kar_yuzde >= min_kar_hedefi: 
                                satir[f"Teklif {i}"] = f"✅ KABUL (Kar: %{round(kar_yuzde, 1)})"
                            else: 
                                satir[f"Teklif {i}"] = f"❌ RED (Kar: %{round(kar_yuzde, 1)})"
                        else: satir[f"Teklif {i}"] = "-"
                    
                    if teklif_gecerli_mi: analiz_sonuclari.append(satir)
                
                if len(analiz_sonuclari) > 0:
                    df_analiz = pd.DataFrame(analiz_sonuclari)
                    st.dataframe(df_analiz.style.map(renk_karari, subset=['Teklif 1', 'Teklif 2', 'Teklif 3']), use_container_width=True)
                    
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: df_analiz.to_excel(wr, index=False, sheet_name='Kampanya_Karari')
                    st.download_button("📥 Onay/Red Listesini Excel İndir", data=buf.getvalue(), file_name="Trendyol_Kampanya_Kararlari.xlsx")
                else: st.error("❌ Eşleşen ürün bulunamadı!")

elif menu == "⚙️ Veritabanı":
    st.subheader("⚙️ Veritabanı Görüntüleyici")
    t1, t2, t3, t4, t5 = st.tabs(["Ürünler", "Genel Kurallar", "Özel Kurallar", "Kargo", "🎯 Ty Teklifler"])
    with t1: st.dataframe(urunler_df)
    with t2: st.dataframe(genel_df)
    with t3: st.dataframe(ozel_df)
    with t4: st.dataframe(kargo_df)
    with t5: st.dataframe(teklif_df)
