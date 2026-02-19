# EasyTableCopy - Kullanıcı Kılavuzu

**EasyTableCopy**, Web'den veya Windows listelerinden Word, Excel gibi uygulamalara veri aktarırken yaşanan format bozulmalarını, kaybolan kenarlıkları ve yapısal hataları çözmek için tasarlanmış bir NVDA eklentisidir.

## 1. Temel Özellikler

* **Çift Kopyalama Motoru:** Görsel kalite için "Standart" mod, yapısal garanti için "Yeniden Oluşturma" modu.
* **Akıllı Seçim:** Bitişik olmayan satırları veya sadece belirli sütunları kolayca seçip kopyalayın.
* **Masaüstü ve Gezgin Desteği:** Dosya Gezgini veya uygulama listelerini anında düzenli bir tabloya dönüştürerek kopyalayın. Belirli sütunları veya sütun kombinasyonlarını seçip kopyalayın.
* **Hücre Düzeyinde Kopyalama:** Tek bir hücrenin içeriğini tablo yapısı olmadan hızlıca kopyalayın.
* **Tablo İstatistikleri:** Herhangi bir tablo veya listenin satır ve sütun sayısını anında öğrenin.
* **Sesli Geri Bildirim:** İşlem başladığında ve bittiğinde farklı seslerle sizi bilgilendirir.

## 2. Web Modu (Tarayıcılar)

Bu özellikler Chrome, Edge, Firefox gibi tarayıcılarda "Tarama Kipi" (Browse Mode) açıkken çalışır.

### A. Kopyalama Menüsü

Herhangi bir tablonun içindeyken `NVDA + Alt + T` tuşlarına basarak menüyü açabilirsiniz.

* **Tabloyu Kopyala (Standart):**
Tarayıcının kendi kopyalama yöntemini kullanır.
*Avantajı:* Yazı tiplerini, renkleri ve linkleri orijinal haliyle korur.
*Dezavantajı:* Tarayıcıya bağımlı olduğu için bazı boş hücreler Word'de kaybolabilir.

* **Tabloyu Kopyala (Yeniden Oluşturulan):**
"Güvenli Mod"dur. Eklenti tabloyu hücre hücre okur ve sıfırdan inşa eder.
*Avantajı:* **Boş hücrelerin korunmasını** ve kenarlıkların (border) Word'de kesinlikle görünmesini garanti eder.
*Dezavantajı:* Çok karmaşık görsel stilleri (yuvarlak köşeler vb.) aktarmayabilir.

* **Geçerli Satırı Kopyala:** İmlecin bulunduğu satırı kopyalar.
* **Geçerli Sütunu Kopyala:** İmlecin bulunduğu dikey sütunu manuel olarak ayıklar ve kopyalar.

### B. Akıllı Seçim (İşaretleme)

Tablonun tamamını değil, sadece istediğiniz kısımları alabilirsiniz. **Not:** Aynı anda hem satır hem sütun seçilemez.

#### Belirli Satırları Kopyalama:

1. İstediğiniz satıra gelin.
2. `Kontrol + Alt + Boşluk` tuşuna basın. NVDA "Satır İşaretlendi" diyecektir.
3. Başka bir satıra gidin ve tekrarlayın.
4. Menüyü açın (`NVDA + Alt + T`) ve **"İşaretlileri Kopyala"** seçeneğine tıklayın.

#### Belirli Sütunları Kopyalama:

1. İstediğiniz sütundaki bir hücreye gelin.
2. `Kontrol + Alt + Shift + Boşluk` tuşuna basın. NVDA "Sütun İşaretlendi" diyecektir.
3. Diğer sütunlar için tekrarlayın.
4. Menüyü açın ve **"İşaretlileri Kopyala"** deyin.

> **Not:** Seçimleri temizlemek için `Kontrol + Alt + Windows + Boşluk` tuşuna basabilir veya menüden "Seçimleri Temizle" diyebilirsiniz.

### C. Ek Web Özellikleri

* **İşaretli Satırları Metin Olarak Kopyala:** İşaretlediğiniz satırları tablo yapısı olmadan düz metin olarak kopyalayabilirsiniz. Bu komut için `İşaretli Satırları Metin Olarak Kopyala` komutunu kullanın (varsayılan tuş ataması yok, Girdi Hareketleri'nden atayabilirsiniz).
* **Geçerli Hücreyi Kopyala:** Bulunduğunuz hücrenin içeriğini hızlıca kopyalamak için `Geçerli Hücreyi Kopyala` komutunu kullanın.

## 3. Masaüstü ve Gezgin Modu (Windows)

EasyTableCopy, Dosya Gezgini ve standart liste görünümlerinde de çalışır.

### A. Hızlı Liste Kopyalama

1. Bir listeye odaklanın (Örneğin bir klasörün içine girin).
2. `NVDA + Alt + T` tuşuna basın.
3. **Sonuç:** Listenin tamamı; "Ad", "Tarih", "Tür" gibi başlıkları olan düzenli bir tabloya dönüştürülür ve panoya kopyalanır.

### B. Sütun Bazlı Kopyalama (Sadece Masaüstü ve Gezgin)

Herhangi bir masaüstü listesinden veya Gezgin penceresinden tek tek sütunları veya sütun kombinasyonlarını kopyalayabilirsiniz. Bu komutlar sadece masaüstü ortamında çalışır (web tarayıcılarında çalışmaz).

| Komut | Açıklama |
| --- | --- |
| 1. Sütunu Kopyala | İlk sütunu kopyalar (genellikle Ad sütunu) |
| 2. Sütunu Kopyala | İkinci sütunu kopyalar (genellikle Boyut veya Tür) |
| 3. Sütunu Kopyala | Üçüncü sütunu kopyalar (genellikle Değiştirilme Tarihi) |
| 1-2. Sütunları Kopyala | Birinci ve ikinci sütunları birlikte kopyalar |
| 1-3. Sütunları Kopyala | Birinci, ikinci ve üçüncü sütunları birlikte kopyalar |
| 1 ve 3. Sütunları Kopyala | Birinci ve üçüncü sütunları kopyalar (ikinci sütunu atlar) |

**Nasıl kullanılır:**
1. Herhangi bir listeye veya Gezgin penceresine odaklanın.
2. İstediğiniz sütun komutuna atadığınız tuşa basın (varsayılan tuş yok - Girdi Hareketleri'nden atayın).
3. Seçtiğiniz sütunlar başlıklarıyla birlikte bir tablo olarak panoya kopyalanır.

### C. Masaüstü Modunda Tablo İstatistikleri

`Tablo İstatistikleri` komutunu kullanarak (varsayılan tuş yok):
- Klasördeki/listelerdeki öğe sayısını
- Görüntülenen sütun sayısını öğrenebilirsiniz

## 4. Evrensel Özellikler (Her Yerde Çalışır)

### A. Tablo İstatistikleri

`Tablo İstatistikleri` komutunu her yerde (web, masaüstü, Gezgin) kullanarak geçerli tablo veya liste hakkında anında bilgi alabilirsiniz:
- Satır/öğe sayısı
- Sütun sayısı

Eklenti, büyük tablolarda performans sorunu yaşamamak için akıllı örnekleme yaparak hızlı ve doğru bilgi verir.

### B. Geçerli Hücreyi Kopyala

`Geçerli Hücreyi Kopyala` komutunu her yerde kullanarak bulunduğunuz hücrenin içeriğini tablo yapısı olmadan hızlıca kopyalayabilirsiniz. Şunlar için idealdir:
- Web tablolarından belirli değerleri almak
- Listelerden tek bir öğeyi çıkarmak
- Hızlı veri girişi işlemleri

## 5. Kısayol Listesi

*(Tüm kısayolları NVDA Menüsü -> Tercihler -> Girdi Hareketleri -> EasyTableCopy kategorisinden özelleştirebilirsiniz)*

### Varsayılan Kısayollar

| Kısayol | İşlev | Bağlam |
| --- | --- | --- |
| `NVDA + Alt + T` | Menüyü Aç (Web) / Listeyi Kopyala (Masaüstü) | Her Yerde |
| `Ctrl + Alt + Boşluk` | Satırı İşaretle/Kaldır | Sadece Web |
| `Ctrl + Alt + Shift + Boşluk` | Sütunu İşaretle/Kaldır | Sadece Web |
| `Ctrl + Alt + Win + Boşluk` | Seçimleri Temizle | Sadece Web |

### Varsayılan Tuşu Olmayan Komutlar (Kendiniz Atayın)

Bu komutların varsayılan tuş atamaları yoktur. Kullanmak için NVDA'nın Girdi Hareketleri diyaloğundan kendi kısayollarınızı atayın:

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

## 6. Önemli Notlar

* **Excel/Calc Koruması:** Eklenti, Excel ve benzeri uygulamalarda otomatik olarak devre dışı kalır. Bu, orijinal kopyalama işlevleriyle çakışmayı önler.
* **Seçim Sınırlamaları:** Satır ve sütun seçimlerini karıştıramazsınız. Ya sadece satırları ya da sadece sütunları işaretleyin.
* **Büyük Tablolar:** Eklenti büyük tabloları verimli bir şekilde işler. Çok büyük web tablolarında istatistikler, optimum performans için örnekleme yöntemiyle hesaplanır.
* **Web vs Masaüstü:** Bazı komutlar bağlama özgüdür (sadece web veya sadece masaüstü). Bu, güvenilir çalışmayı sağlamak içindir. Geçerli olmayan bağlamdaki komutlar basitçe yok sayılır.

## 7. Geri Bildirim ve Katkı

Herhangi bir sorunla karşılaşırsanız veya iyileştirme önerileriniz varsa, lütfen eklentinin deposunu ziyaret edin veya yazarla iletişime geçin.