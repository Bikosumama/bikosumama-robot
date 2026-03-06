import streamlit as st
import pandas as pd
import numpy as np
import io

# --- 1. SAYFA AYARLARI ---
st.set_page_config(page_title="bikosumama Fiyat Robotu", page_icon="🐾", layout="wide")
st.title("🤖 bikosumama | Gelişmiş Fiyatlandırma Paneli")
st.markdown("---")

SHEET_ID = "1I_KpIeCTLWO0P_4ZLlMtUyoWtcIGvdT2p8GkjEnzN8M"

# --- 2. YARDIMCI FONKSİYONLAR ---
def sayisal_yap(deger):
    if pd.isna(deger) or deger == '': return 0.0
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
        for df in [urunler, kargo, genel_kurallar, ozel_kurallar]:
            df.columns = df.columns.str.strip()
            df.fillna('', inplace=True)
        return urunler, kargo, genel_kurallar, ozel_kurallar
    except:
        return None, None, None, None

urunler_df, kargo_df, genel_df, ozel_df = veri_getir()

# --- 3. HESAPLAMA MOTORU ---
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
    komisyon = sayisal_yap(genel_k.get('Komisyon Oranı', 0))
    kaynak = "🌍 Genel"

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
        satis = (toplam_sabit + h_kar) / bolen
        return satis, h_kar

    b1_s, b1_k = sayisal_yap(genel_k.get('Barem 1 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 1 Kargo (TL)', 0))
    b2_s, b2_k = sayisal_yap(genel_k.get('Barem 2 Sınırı (TL)', 0)), sayisal_yap(genel_k.get('Barem 2 Kargo (TL)', 0))
    u_sinir = sayisal_yap(genel_k.get('Ücretsiz Kargo Sınırı (TL)', 0))

    s1, k1 = matematik(b1_k)
    if b1_s > 0 and s1 <= b1_s: 
        return s1, k1, b1_k, s1*komisyon_oran, s1*efektif_stopaj, hizmet, islem, diger, komisyon, "1. Barem", kaynak
    s2, k2 = matematik(b2_k)
    if b2_s > 0 and s2 <= b2_s: 
        return s2, k2, b2_k, s2*komisyon_oran, s2*efektif_stopaj, hizmet, islem, diger, komisyon, "2. Barem", kaynak
    if u_sinir > 0:
        s_u, k_u = matematik(0)
        if s_u < u_sinir: 
            return s_u, k_u, 0, s_u*komisyon_oran, s_u*efektif_stopaj, hizmet, islem, diger, komisyon, "Alıcı Öder", kaynak
    s_d, k_d = matematik(kargo_ucreti_desi)
    return s_d, k_d, kargo_ucreti_desi, s_d*komisyon_oran, s_d*efektif_stopaj, hizmet, islem, diger, komisyon, "Desi", kaynak

# --- 4. KULLANICI ARAYÜZÜ ---
if urunler_df is not None:
    menu = st.sidebar.radio("MENÜ", ["🔍 Ürün Arama & Analiz", "📊 Toplu Liste", "⚙️ Veritabanı"])

    if menu == "🔍 Ürün Arama & Analiz":
        st.subheader("🔍 Hızlı Ürün Arama & Detaylı Analiz")
        arama_metni = st.text_input("Aramak için yazın...", placeholder="Örn: Pro Plan, 101, Felix...")
        
        mask = (
            urunler_df['Ürün Adı'].astype(str).str.contains(arama_metni, case=False) |
            urunler_df['Stok Kodu'].astype(str).str.contains(arama_metni, case=False) |
            urunler_df['Marka'].astype(str).str.contains(arama_metni, case=False)
        )
        filtrelenmis_df = urunler_df[mask]

        if arama_metni != "":
            st.write(f"✅ **{len(filtrelenmis_df)}** sonuç listelendi. Analiz için bir satıra tıklayın:")
            event = st.dataframe(
                filtrelenmis_df[['Stok Kodu', 'Marka', 'Ürün Adı', 'Alış Fiyatı']],
                use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
            )

            if len(event.selection.rows) > 0:
                secili_index = event.selection.rows[0]
                u = filtrelenmis_df.iloc[secili_index]
                
                st.markdown("---")
                st.success(f"📊 **Seçilen Ürün:** {u['Ürün Adı']}")
                
                kar = st.number_input("Hedef Net Kar Marjı (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
                
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
                            "Kural Kaynağı": kay
                        })
                st.table(pd.DataFrame(analiz_data))
        else:
            st.info("👆 Başlamak için yukarıdaki arama kutusuna bir kelime yazın.")

    elif menu == "📊 Toplu Liste":
        st.subheader("📋 Dinamik Toplu Fiyat Listesi")
        
        # --- YENİ EKLENEN KATEGORİ BAZLI KAR MODÜLÜ ---
        kar_modu = st.radio("Kar Marjı Belirleme Yöntemi:", ["🌍 Tüm Ürünlere Aynı Kar Marjını Uygula", "📁 Kategori Bazlı Kar Marjı Uygula"])
        
        kategori_karlari = {}
        global_kar = 20.0
        varsayilan_kar = 20.0
        
        if kar_modu == "🌍 Tüm Ürünlere Aynı Kar Marjını Uygula":
            global_kar = st.number_input("Global Hedef Kar Marjı (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
        else:
            st.markdown("**Aşağıdan kategorilerinize özel kâr marjlarını belirleyin:**")
            # Excel'deki benzersiz kategorileri bul
            kategoriler = [k for k in urunler_df['Kategori'].unique() if str(k).strip() != '']
            
            # Kategorileri 4'lü sütunlar halinde ekrana diz
            for i in range(0, len(kategoriler), 4):
                cols = st.columns(4)
                for j in range(4):
                    if i + j < len(kategoriler):
                        kat = kategoriler[i + j]
                        with cols[j]:
                            kategori_karlari[kat] = st.number_input(f"{kat} (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5, key=f"kar_{kat}")
            
            # Eğer Excel'de kategorisi boş bırakılmış bir ürün varsa onun kârını da buradan alalım
            varsayilan_kar = st.number_input("Kategorisi Boş Olanlar İçin Kar (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
        
        st.markdown("---")

        if st.button("🚀 Tümünü Hesapla"):
            with st.spinner('Tüm ürünler hesaplanıyor, lütfen bekleyin...'):
                p_yerleri = genel_df['Pazaryeri Adı'].unique()
                toplu_data = []
                for _, urun in urunler_df.iterrows():
                    if str(urun['Ürün Adı']).strip() == '': continue
                    
                    # --- ÜRÜNE UYGULANACAK KARI BELİRLE ---
                    if kar_modu == "🌍 Tüm Ürünlere Aynı Kar Marjını Uygula":
                        aktif_kar = global_kar
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
                
                st.markdown("<br>", unsafe_allow_html=True)
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                    df_toplu.to_excel(wr, index=False, sheet_name='Toplu_Fiyatlar')
                
                st.download_button(
                    label="📥 Sonuçları Excel Olarak İndir",
                    data=buf.getvalue(),
                    file_name="bikosumama_kategori_bazli_fiyatlar.xlsx",
                    mime="application/vnd.ms-excel"
                )

    elif menu == "⚙️ Veritabanı":
        t1, t2, t3, t4 = st.tabs(["Ürünler", "Genel Kurallar", "Özel Kurallar", "Kargo"])
        with t1: st.dataframe(urunler_df)
        with t2: st.dataframe(genel_df)
        with t3: st.dataframe(ozel_df)
        with t4: st.dataframe(kargo_df)