# EasyTableCopy - Kullanıcı Kılavuzu

**EasyTableCopy**, Web'den veya Windows listelerinden Word, Excel gibi uygulamalara veri aktarırken yaşanan format bozulmalarını, kaybolan kenarlıkları ve yapısal hataları çözmek için tasarlanmış bir NVDA eklentisidir.

---

## 1. Temel Özellikler

* **Çift Kopyalama Motoru:** Görsel kalite için "Standart" mod, yapısal garanti için "Yeniden Oluşturma" modu.
* **Web Listesi Desteği:** Web sayfalarındaki listeleri iki seçenekle kopyalayın — orijinal biçimlendirmeyi (yazı tipleri, renkler, bağlantılar) koruyarak veya temiz bir düz liste olarak (buton ve etkileşimli öğe metinleri dahil). Belirli öğeleri işaretleyerek yalnızca seçilenleri kopyalayın.
* **Akıllı Seçim:** Bitişik olmayan satırları, liste öğelerini veya sadece belirli sütunları kolayca seçip kopyalayın.
* **Masaüstü ve Gezgin Desteği:** Dosya Gezgini veya uygulama listelerini anında düzenli bir tabloya dönüştürerek kopyalayın. Belirli sütunları veya sütun kombinasyonlarını seçip kopyalayın.
* **Ağaç Görünümü (TreeView) Desteği:** Klasör ağaçları veya ayarlar (Girdi Hareketleri gibi) hiyerarşik yapılarını seviyeleri korunmuş olarak kopyalayın.
* **Hücre Düzeyinde Kopyalama:** Tek bir hücrenin içeriğini tablo yapısı olmadan hızlıca kopyalayın.
* **Tablo İstatistikleri:** Herhangi bir tablo veya listenin satır ve sütun sayısını anında öğrenin.
* **Sesli Geri Bildirim:** İşlem başladığında ve bittiğinde farklı seslerle sizi bilgilendirir.

---

## 2. Web Modu (Tarayıcılar)

Bu özellikler Chrome, Edge, Firefox gibi tarayıcılarda "Tarama Kipi" (Browse Mode) açıkken çalışır.

### A. Tablo Kopyalama Menüsü

Herhangi bir tablonun içindeyken `NVDA + Alt + T` tuşlarına basarak menüyü açabilirsiniz.

* **Tabloyu Kopyala (Standart):**
Tarayıcının kendi kopyalama yöntemini kullanır.
*Avantajı:* Yazı tiplerini, renkleri ve bağlantıları orijinal haliyle korur.
*Dezavantajı:* Tarayıcıya bağımlı olduğu için bazı boş hücreler Word'de kaybolabilir.
* **Tabloyu Kopyala (Yeniden Oluşturulan):**
"Güvenli Mod"dur. Eklenti tabloyu hücre hücre okur ve sıfırdan inşa eder.
*Avantajı:* **Boş hücrelerin korunmasını** ve kenarlıkların Word'de kesinlikle görünmesini garanti eder.
*Dezavantajı:* Çok karmaşık görsel stilleri (yuvarlak köşeler vb.) aktarmayabilir.
* **Geçerli Satırı Kopyala:** İmlecin bulunduğu satırı kopyalar.
* **Geçerli Sütunu Kopyala:** İmlecin bulunduğu dikey sütunu manuel olarak ayıklar ve kopyalar.

### B. Liste Kopyalama Menüsü

Herhangi bir web listesinin (madde işaretli veya numaralı) içindeyken `NVDA + Alt + T` tuşlarına basarak liste kopyalama menüsünü açabilirsiniz.

* **Listeyi Kopyala (Biçimli):**
Tarayıcının kendi kopyalama yöntemini kullanır.
*Avantajı:* Yazı tiplerini, renkleri, bağlantıları ve tüm orijinal biçimlendirmeyi korur.
*Dezavantajı:* Tarayıcıya bağımlıdır.
* **Listeyi Kopyala (Düz):**
Eklenti liste öğelerini okur ve temiz bir `<ul><li>` yapısı oluşturur. Buton metinleri ve etkileşimli öğe etiketleri (ör. "Manage cookies") artık düz metin çıktısına dahil edilmektedir.
*Avantajı:* Taşınabilir, temiz bir liste üretir. Düz metin olarak her öğe ayrı satırda gelir.
*Dezavantajı:* Orijinal görsel biçimlendirme (yazı tipleri, renkler) korunmaz.
* **İşaretlileri Kopyala (N öğe):** *(yalnızca işaretli öğe varken görünür)*
Tek tek işaretlediğiniz öğeleri kopyalar. Bkz. **Akıllı Seçim** bölümü.
* **Seçimleri Temizle:** *(yalnızca işaretli öğe varken görünür)*
Kopyalama yapmadan tüm işaretleri kaldırır.

### C. Akıllı Seçim (İşaretleme)

Tablonun tamamını değil, sadece istediğiniz kısımları alabilirsiniz. Bu özellik hem **tablo satırları** hem de **web listesi öğeleri** için çalışır. **Not:** Aynı anda hem satır/öğe hem sütun seçilemez.

#### Belirli Satır veya Liste Öğelerini Kopyalama:

1. İstediğiniz satıra veya liste öğesine gelin.
2. `Kontrol + Alt + Boşluk` tuşuna basın. Tablolarda "Satır İşaretlendi", listelerde "Öğe İşaretlendi" diyecektir.
3. Başka bir satır veya öğeye gidin ve tekrarlayın.
4. Menüyü açın (`NVDA + Alt + T`) ve **"İşaretlileri Kopyala"** seçeneğini seçin.

#### Belirli Sütunları Kopyalama:

1. İstediğiniz sütundaki bir hücreye gelin.
2. `Kontrol + Alt + Shift + Boşluk` tuşuna basın. NVDA "Sütun İşaretlendi" diyecektir.
3. Diğer sütunlar için tekrarlayın.
4. Menüyü açın ve **"İşaretlileri Kopyala"** seçeneğini seçin.

> **Not:** Seçimleri temizlemek için `Kontrol + Alt + Windows + Boşluk` tuşuna basabilir veya menüden "Seçimleri Temizle" seçeneğini kullanabilirsiniz (liste menüsünde de işaretli öğe varken görünür).

### D. Ek Web Özellikleri

* **İşaretli Satırları Metin Olarak Kopyala:** İşaretlediğiniz satırları tablo yapısı olmadan düz metin olarak kopyalayabilirsiniz (varsayılan tuş ataması yok, Girdi Hareketleri'nden atayabilirsiniz).
* **Geçerli Hücreyi Kopyala:** Bulunduğunuz hücrenin içeriğini hızlıca kopyalamak için `Geçerli Hücreyi Kopyala` komutunu kullanın.

---

## 3. Masaüstü, Gezgin ve Ağaç Görünümü Modu (Windows)

EasyTableCopy; Dosya Gezgini, standart liste görünümleri ve hiyerarşik ağaç yapılarında da çalışır.

### A. Hızlı Liste ve Ağaç Kopyalama

1. Bir listeye (klasör içi) veya ağaç öğesine (Girdi Hareketleri dalı gibi) odaklanın.
2. `NVDA + Alt + T` tuşuna basın.
3. **Listeler İçin Sonuç:** Listenin tamamı; "Ad", "Tarih", "Tür" gibi başlıkları olan düzenli bir tabloya dönüştürülür ve panoya kopyalanır.
4. **Ağaçlar İçin Sonuç:** Tüm ağaç yapısı en üst kökten başlayarak taranır ve girintili bir liste olarak kopyalanır.
* `[+]` işareti kapalı dalları, `[-]` işareti açık dalları temsil eder.

### B. Sütun Bazlı Kopyalama (Sadece Masaüstü ve Gezgin)

Herhangi bir masaüstü listesinden veya Gezgin penceresinden tek tek sütunları veya sütun kombinasyonlarını kopyalayabilirsiniz. Bu komutlar sadece masaüstü ortamında çalışır.

| Komut | Açıklama |
| --- | --- |
| 1. Sütunu Kopyala | İlk sütunu kopyalar (genellikle Ad sütunu) |
| 2. Sütunu Kopyala | İkinci sütunu kopyalar (genellikle Boyut veya Tür) |
| 3. Sütunu Kopyala | Üçüncü sütunu kopyalar (genellikle Değiştirilme Tarihi) |
| 1-2. Sütunları Kopyala | Birinci ve ikinci sütunları birlikte kopyalar |
| 1-3. Sütunları Kopyala | Birinci, ikinci ve üçüncü sütunları birlikte kopyalar |
| 1 ve 3. Sütunları Kopyala | Birinci ve üçüncü sütunları kopyalar (ikincisini atlar) |

**Nasıl kullanılır:**

1. Herhangi bir listeye veya Gezgin penceresine odaklanın.
2. İstediğiniz sütun komutuna atadığınız tuşa basın (varsayılan tuş yok — Girdi Hareketleri'nden atayın).
3. Seçtiğiniz sütunlar başlıklarıyla birlikte bir tablo olarak panoya kopyalanır.

### C. Masaüstü Modunda Tablo İstatistikleri

`Tablo İstatistikleri` komutunu kullanarak (varsayılan tuş yok):

* Klasördeki/listedeki öğe sayısını
* Görüntülenen sütun sayısını öğrenebilirsiniz.

---

## 4. Evrensel Özellikler (Her Yerde Çalışır)

### A. Tablo İstatistikleri

`Tablo İstatistikleri` komutunu her yerde (web, masaüstü, Gezgin) kullanarak geçerli tablo veya liste hakkında anında bilgi alabilirsiniz:

* Satır/öğe sayısı
* Sütun sayısı

Eklenti, büyük tablolarda performans sorunu yaşamamak için akıllı örnekleme yaparak hızlı ve doğru bilgi verir.

### B. Geçerli Hücreyi Kopyala

`Geçerli Hücreyi Kopyala` komutunu her yerde kullanarak bulunduğunuz hücrenin içeriğini tablo yapısı olmadan hızlıca kopyalayabilirsiniz.

---

## 5. Kısayol Listesi

*(Tüm kısayolları NVDA Menüsü → Tercihler → Girdi Hareketleri → EasyTableCopy kategorisinden özelleştirebilirsiniz)*

### Varsayılan Kısayollar

| Kısayol | İşlev | Bağlam |
| --- | --- | --- |
| `NVDA + Alt + T` | Tablo/Liste Menüsünü Aç (Web) / Liste veya Ağacı Kopyala (Masaüstü) | Her Yerde |
| `Ctrl + Alt + Boşluk` | Satır veya Liste Öğesini İşaretle/Kaldır | Sadece Web |
| `Ctrl + Alt + Shift + Boşluk` | Sütunu İşaretle/Kaldır | Sadece Web |
| `Ctrl + Alt + Win + Boşluk` | Seçimleri Temizle | Sadece Web |

### Varsayılan Tuşu Olmayan Komutlar (Kendiniz Atayın)

| Komut | Açıklama | Bağlam |
| --- | --- | --- |
| 1. Sütunu Kopyala | İlk sütunu kopyalar | Sadece Masaüstü/Gezgin |
| 2. Sütunu Kopyala | İkinci sütunu kopyalar | Sadece Masaüstü/Gezgin |
| 3. Sütunu Kopyala | Üçüncü sütunu kopyalar | Sadece Masaüstü/Gezgin |
| 1-2. Sütunları Kopyala | Birinci ve ikinci sütunları kopyalar | Sadece Masaüstü/Gezgin |
| 1-3. Sütunları Kopyala | İlk üç sütunu kopyalar | Sadece Masaüstü/Gezgin |
| 1 ve 3. Sütunları Kopyala | Birinci ve üçüncü sütunları kopyalar | Sadece Masaüstü/Gezgin |
| Tablo İstatistikleri | Tablo boyutlarını söyler | Her Yerde |
| Geçerli Hücreyi Kopyala | Bulunulan hücrenin içeriğini kopyalar | Her Yerde |
| İşaretli Satırları Metin Olarak Kopyala | İşaretli satırları düz metin olarak kopyalar | Sadece Web |

---

## 6. Önemli Notlar

* **Excel/Calc Koruması:** Eklenti, Excel ve benzeri uygulamalarda otomatik olarak devre dışı kalır.
* **Seçim Sınırlamaları:** Satır ve sütun seçimlerini karıştıramazsınız. Satır ya da sütun — ikisini birden seçemezsiniz.
* **Büyük Tablolar:** Çok büyük web tablolarında istatistikler, performans için örnekleme yöntemiyle hesaplanır.
* **Web vs Masaüstü:** Bazı komutlar bağlama özgüdür. Geçerli olmayan bağlamdaki komutlar yok sayılır.
* **Ağaç Yükleme:** Bazı Windows ağaç görünümlerinde, daha önce hiç açılmamış dallar NVDA tarafından görülmeyebilir.

---

## 7. Geri Bildirim ve Katkı

Herhangi bir sorunla karşılaşırsanız veya iyileştirme önerileriniz varsa, lütfen eklentinin deposunu ziyaret edin veya yazarla iletişime geçin.