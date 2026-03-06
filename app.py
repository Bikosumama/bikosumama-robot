import streamlit as st
import pandas as pd
import numpy as np
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
    except:
        return None, None, None, None, None

urunler_df, kargo_df, genel_df, ozel_df, teklif_df = veri_getir()

def fiyat_hesapla_v4(marka, kategori, desi, alis, kdv, pz_adi, kar_yuzdesi):
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

if urunler_df is not None:
    menu = st.sidebar.radio("MENÜ", ["🔍 Ürün Arama & Analiz", "📊 Toplu Liste", "🎯 Ty Kampanya Simülatörü", "⚙️ Veritabanı"])
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Sistemden Çıkış Yap"):
        st.session_state.giris_yapildi = False; st.rerun()

    # İŞTE GERİ DÖNEN EFSANE DETAYLI ARAMA EKRANI!
    if menu == "🔍 Ürün Arama & Analiz":
        st.subheader("🔍 Hızlı Ürün Arama & Detaylı Analiz")
        arama_metni = st.text_input("Aramak için yazın...", placeholder="Örn: Pro Plan, 101...")
        mask = (urunler_df['Ürün Adı'].astype(str).str.contains(arama_metni, case=False) | urunler_df['Stok Kodu'].astype(str).str.contains(arama_metni, case=False))
        filtrelenmis_df = urunler_df[mask]
        if arama_metni != "":
            event = st.dataframe(filtrelenmis_df[['Stok Kodu', 'Marka', 'Ürün Adı', 'Alış Fiyatı']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if len(event.selection.rows) > 0:
                u = filtrelenmis_df.iloc[event.selection.rows[0]]
                kar = st.number_input("Hedef Net Kar Marjı (%)", min_value=0.0, value=20.0, step=0.5)
                analiz_data = []
                for pz in genel_df['Pazaryeri Adı'].unique():
                    res = fiyat_hesapla_v4(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, kar)
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
        else: st.info("👆 Başlamak için ürün adı veya stok kodu yazın.")

    elif menu == "📊 Toplu Liste":
        st.subheader("📋 Dinamik Toplu Fiyat Listesi")
        kar_modu = st.radio("Kar Marjı Belirleme Yöntemi:", ["🌍 Tüm Ürünlere Aynı Kar Marjını Uygula", "📁 Kategori Bazlı Kar Marjı Uygula"])
        
        kategori_karlari = {}
        global_kar = 20.0
        varsayilan_kar = 20.0
        
        if kar_modu == "🌍 Tüm Ürünlere Aynı Kar Marjını Uygula":
            global_kar = st.number_input("Global Hedef Kar Marjı (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
        else:
            st.markdown("**Aşağıdan kategorilerinize özel kâr marjlarını belirleyin:**")
            kategoriler = [k for k in urunler_df['Kategori'].unique() if str(k).strip() != '']
            for i in range(0, len(kategoriler), 4):
                cols = st.columns(4)
                for j in range(4):
                    if i + j < len(kategoriler):
                        kat = kategoriler[i + j]
                        with cols[j]:
                            kategori_karlari[kat] = st.number_input(f"{kat} (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5, key=f"kar_{kat}")
            varsayilan_kar = st.number_input("Kategorisi Boş Olanlar İçin Kar (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
        
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

                    satir = {"Stok Kodu": urun['Stok Kodu'], "Ürün": urun['Ürün Adı'], "Kategori": urun['Kategori'], "Uygulanan Kar": f"%{aktif_kar}", "Maliyet": urun['Alış Fiyatı']}
                    for pz in p_yerleri:
                        res_t = fiyat_hesapla_v4(urun['Marka'], urun['Kategori'], sayisal_yap(urun['Desi']), sayisal_yap(urun['Alış Fiyatı']), sayisal_yap(urun['KDV Oranı']), pz, aktif_kar)
                        satir[pz] = round(res_t[0], 2) if res_t[0] > 0 else "Hata"
                    toplu_data.append(satir)
                
                df_toplu = pd.DataFrame(toplu_data)
                st.dataframe(df_toplu, use_container_width=True)
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: df_toplu.to_excel(wr, index=False, sheet_name='Toplu_Fiyatlar')
                st.download_button("📥 Sonuçları Excel Olarak İndir", data=buf.getvalue(), file_name="bikosumama_fiyatlar.xlsx", mime="application/vnd.ms-excel")

    def kampanya_analiz_motoru(desi, alis, kdv, teklif_fiyat, teklif_komisyon):
    pz_adi = "Trendyol"
    kargo_ucreti = 0
    
    # Hata 2 Çözümü: Pazaryeri isimlerindeki boşluk ve harf büyüklüğü toleransı artırıldı (.str.strip().str.lower() eklendi)
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

if urunler_df is not None:
    menu = st.sidebar.radio("MENÜ", ["🔍 Ürün Arama & Analiz", "📊 Toplu Liste", "🎯 Ty Kampanya Simülatörü", "⚙️ Veritabanı"])
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Sistemden Çıkış Yap"):
        st.session_state.giris_yapildi = False; st.rerun()

    if menu == "🔍 Ürün Arama & Analiz":
        st.subheader("🔍 Hızlı Ürün Arama & Detaylı Analiz")
        arama_metni = st.text_input("Aramak için yazın...", placeholder="Örn: Pro Plan, 101...")
        mask = (urunler_df['Ürün Adı'].astype(str).str.contains(arama_metni, case=False) | urunler_df['Stok Kodu'].astype(str).str.contains(arama_metni, case=False))
        filtrelenmis_df = urunler_df[mask]
        if arama_metni != "":
            event = st.dataframe(filtrelenmis_df[['Stok Kodu', 'Marka', 'Ürün Adı', 'Alış Fiyatı']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if len(event.selection.rows) > 0:
                u = filtrelenmis_df.iloc[event.selection.rows[0]]
                kar = st.number_input("Hedef Net Kar Marjı (%)", min_value=0.0, value=20.0, step=0.5)
                analiz_data = []
                for pz in genel_df['Pazaryeri Adı'].unique():
                    res = fiyat_hesapla_v4(u['Marka'], u['Kategori'], sayisal_yap(u['Desi']), sayisal_yap(u['Alış Fiyatı']), sayisal_yap(u['KDV Oranı']), pz, kar)
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
        else: st.info("👆 Başlamak için ürün adı veya stok kodu yazın.")

    elif menu == "📊 Toplu Liste":
        st.subheader("📋 Dinamik Toplu Fiyat Listesi")
        kar_modu = st.radio("Kar Marjı Belirleme Yöntemi:", ["🌍 Tüm Ürünlere Aynı Kar Marjını Uygula", "📁 Kategori Bazlı Kar Marjı Uygula"])
        
        kategori_karlari = {}
        global_kar = 20.0
        varsayilan_kar = 20.0
        
        if kar_modu == "🌍 Tüm Ürünlere Aynı Kar Marjını Uygula":
            global_kar = st.number_input("Global Hedef Kar Marjı (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
        else:
            st.markdown("**Aşağıdan kategorilerinize özel kâr marjlarını belirleyin:**")
            kategoriler = [k for k in urunler_df['Kategori'].unique() if str(k).strip() != '']
            for i in range(0, len(kategoriler), 4):
                cols = st.columns(4)
                for j in range(4):
                    if i + j < len(kategoriler):
                        kat = kategoriler[i + j]
                        with cols[j]:
                            kategori_karlari[kat] = st.number_input(f"{kat} (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5, key=f"kar_{kat}")
            varsayilan_kar = st.number_input("Kategorisi Boş Olanlar İçin Kar (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
        
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

                    satir = {"Stok Kodu": urun['Stok Kodu'], "Ürün": urun['Ürün Adı'], "Kategori": urun['Kategori'], "Uygulanan Kar": f"%{aktif_kar}", "Maliyet": urun['Alış Fiyatı']}
                    for pz in p_yerleri:
                        res_t = fiyat_hesapla_v4(urun['Marka'], urun['Kategori'], sayisal_yap(urun['Desi']), sayisal_yap(urun['Alış Fiyatı']), sayisal_yap(urun['KDV Oranı']), pz, aktif_kar)
                        satir[pz] = round(res_t[0], 2) if res_t[0] > 0 else "Hata"
                    toplu_data.append(satir)
                
                df_toplu = pd.DataFrame(toplu_data)
                st.dataframe(df_toplu, use_container_width=True)
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: df_toplu.to_excel(wr, index=False, sheet_name='Toplu_Fiyatlar')
                st.download_button("📥 Sonuçları Excel Olarak İndir", data=buf.getvalue(), file_name="bikosumama_fiyatlar.xlsx", mime="application/vnd.ms-excel")

    elif menu == "🎯 Ty Kampanya Simülatörü":
        st.subheader("🎯 Trendyol Fırsat Merkezi Süzgeci")
        st.markdown("Google Tablodaki `Trendyol_Teklifler` sekmesine yapıştırdığınız kademeli fiyat/komisyon tekliflerini analiz eder. **Sadece belirlediğiniz kâr marjının üstünde kalan teklifleri onaylar.**")
        min_kar_hedefi = st.number_input("Süzgeç: Kabul Edilebilir Minimum Kâr Marjı (%)", min_value=0.0, value=10.0, step=0.5)
        
        if st.button("🚀 Teklifleri Analiz Et"):
            if teklif_df.empty or len(teklif_df) == 0:
                st.warning("⚠️ Trendyol_Teklifler sekmesinde veri bulunamadı.")
            else:
                with st.spinner('Teklifler Süzgeçten Geçiriliyor...'):
                    analiz_sonuclari = []
                    
                    # Hata 1 Çözümü: Urunler tablosundaki stok kodlarını güvenli formata çevirip (örn: 101.0 -> 101) sabitleyelim
                    urunler_stok_temiz = urunler_df['Stok Kodu'].astype(str).str.replace('.0', '', regex=False).str.strip()
                    
                    for _, teklif in teklif_df.iterrows():
                        # Teklifler tablosundaki stok kodunu da aynı şekilde temizle
                        stok_kodu = str(teklif.get('Stok Kodu', '')).replace('.0', '', 1).strip()
                        if not stok_kodu or stok_kodu == 'nan': continue
                        
                        # Artık temizlenmiş kodlar üzerinden eşleşme arıyoruz
                        eslesen_urun = urunler_df[urunler_stok_temiz == stok_kodu]
                        if eslesen_urun.empty: continue
                        
                        u = eslesen_urun.iloc[0]
                        desi = sayisal_yap(u.get('Desi', 0))
                        alis = sayisal_yap(u.get('Alış Fiyatı', 0))
                        kdv = sayisal_yap(u.get('KDV Oranı', 20))
                        
                        satir = {"Stok Kodu": stok_kodu, "Ürün Adı": u['Ürün Adı']}
                        teklif_gecerli_mi = False
                        
                        for i in range(1, 4):
                            t_fiyat = sayisal_yap(teklif.get(f'Teklif {i} Fiyat', 0))
                            t_komisyon = sayisal_yap(teklif.get(f'Teklif {i} Komisyon', 0))
                            
                            if t_fiyat > 0:
                                teklif_gecerli_mi = True
                                kar_tl, kar_yuzde = kampanya_analiz_motoru(desi, alis, kdv, t_fiyat, t_komisyon)
                                if kar_yuzde >= min_kar_hedefi: 
                                    satir[f"Teklif {i} Kararı"] = f"✅ KABUL (Kar: %{round(kar_yuzde, 1)} | {round(kar_tl, 2)} TL)"
                                else: 
                                    satir[f"Teklif {i} Kararı"] = f"❌ RED (Kar: %{round(kar_yuzde, 1)} | {round(kar_tl, 2)} TL)"
                            else: 
                                satir[f"Teklif {i} Kararı"] = "-"
                        
                        if teklif_gecerli_mi:
                            analiz_sonuclari.append(satir)
                    
                    # Eğer liste boş dönmüşse (hiçbir ürün eşleşmemişse) ekrana hata bas ki nerede tıkandığımızı görelim
                    if len(analiz_sonuclari) > 0:
                        df_analiz = pd.DataFrame(analiz_sonuclari)
                        st.dataframe(df_analiz, use_container_width=True)
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: df_analiz.to_excel(wr, index=False, sheet_name='Kampanya_Karari')
                        st.download_button("📥 Onay/Red Listesini Excel İndir", data=buf.getvalue(), file_name="Trendyol_Kampanya_Kararlari.xlsx")
                    else:
                        st.error("❌ Eşleşen ürün veya fiyatı 0'dan büyük teklif bulunamadı! Lütfen iki sekmedeki 'Stok Kodu' değerlerinin tam olarak aynı yazıldığından emin ol.")

    elif menu == "⚙️ Veritabanı":
        st.subheader("⚙️ Veritabanı Görüntüleyici")
        t1, t2, t3, t4, t5 = st.tabs(["Ürünler", "Genel Kurallar", "Özel Kurallar", "Kargo", "🎯 Ty Teklifler"])
        with t1: st.dataframe(urunler_df)
        with t2: st.dataframe(genel_df)
        with t3: st.dataframe(ozel_df)
        with t4: st.dataframe(kargo_df)
        with t5: 
            st.info("Bu tablo 'Trendyol_Teklifler' sekmesinden çekilen dinamik kampanya verilerini gösterir.")
            st.dataframe(teklif_df)
