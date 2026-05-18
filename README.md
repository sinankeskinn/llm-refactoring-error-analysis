# Büyük Dil Modellerinin Yazılım Geliştirme Süreçlerindeki Güvenilirliğinin İncelenmesi
## Investigating the Reliability of Large Language Models in Software Development Processes

Bu depo (repository), Büyük Dil Modellerinin (LLM) yazılım refaktörizasyon süreçlerindeki performanslarını, mimari olgunluklarını ve halüsinasyon eğilimlerini niteliksel ve niceliksel yöntemlerle inceleyen akademik tez çalışmasının açık erişimli veri havuzudur ve tekrarlanabilirlik paketidir (replication package).

---

## 🇹🇷 TÜRKÇE İÇERİK

### 📌 Proje Hakkında
Bu çalışmada, güncel büyük dil modellerinin (Claude 3.5 Sonnet, Gemini 1.5 Flash ve GPT-4o) Python ve SQL katmanlarındaki karmaşık kod senaryoları üzerindeki refaktör çıktıları sistematik olarak analiz edilmiştir. Araştırma, küresel nicel yazılım metrikleri (Pylint ve Radon) ile desteklenmiş niteliksel bir karşılaştırmalı vaka analizi tasarımıdır.

### 🔬 Metodoloji ve Değerlendirme Kriterleri
Modellerin ürettiği çözümler, araştırmacı tarafından geliştirilen ve uzman görüşüyle doğrulanan **"Hata İzleme ve Karşılaştırma Matrisi"** temelinde 4 ana boyutta (1-4 arası puanlama skalasıyla) değerlendirilmiştir:
1. **Fonksiyonel Doğruluk:** Kodun beklenen çıktıyı ve katmanlı mimari yapıyı tam olarak sağlayıp sağlamadığı.
2. **Kod Kalitesi:** PEP 8 standartlarına uyum (Pylint) ve yazılım karmaşıklığı (Radon - Cyclomatic Complexity & Maintainability Index).
3. **Halüsinasyon Yoğunluğu:** Yapısal/mantıksal sapmalar ve literatürde tanımlanan *semantic breaking* (orijinal işlevselliğin bozulması) bulguları.
4. **Güvenlik Uyumu:** CWE kategorilerine ve güvenli tasarım kalıplarına uygunluk (örn: Few-Shot senaryosunda kurulan çift katmanlı güvenlik mimarisi).

### 📂 Depo Klasör Yapısı
* `/dataset`: Modellere yönlendirilen ham kod senaryoları ve Few-Shot/Zero-Shot prompt şablonları.
* `/outputs`: Modellerin ürettiği ham kaynak kod çıktıları.
* `/metrics`: Çıktılara ait Pylint skorları ve Radon statik analiz raporları.
* `/evaluation`: Uzman doğrulamasından geçmiş 1-4 arası puanlama matrisleri.

---

## 🇬🇧 ENGLISH CONTENT

### 📌 About the Project
This repository contains the experimental datasets, source codes, and static analysis reports for evaluating the structural maturity, functional correctness, and hallucination tendencies of state-of-the-art LLMs (Claude 3.5 Sonnet, Gemini 1.5 Flash, and GPT-4o) during software refactoring tasks.

### 🔬 Methodology & Evaluation Framework
The generated source codes were evaluated using a hybrid framework combining qualitative expert analysis and quantitative software engineering metrics (evaluated on a 1-4 scale):
* **Functional Correctness:** Multi-layer architectural consistency and exact output validation.
* **Code Quality:** PEP 8 compliance via Pylint and structural density via Radon (Cyclomatic Complexity & Maintainability Index).
* **Hallucination Density:** Logical anomalies, non-existent API dependencies, and *semantic breaking* indicators.
* **Security Compliance:** Evaluation against CWE categories and robust architectural definitions.

---

## 📑 Atıf / Citation
Bu veri setini veya metodolojik altyapıyı çalışmalarınızda kullanırsanız, lütfen ana teze atıfta bulunun:

> Sinan KESKİN, "Büyük Dil Modellerinin (LLM) Yazılım Geliştirme Süreçlerindeki Güvenilirliğini Niteliksel Hata Analizi Yöntemiyle İncelemek", Yüksek Lisans Tezi, 2026.
