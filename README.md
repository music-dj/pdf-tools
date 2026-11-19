# PDF Master Pro V3.2 📄✨

**PDF Master Pro** is a modern, powerful, and comprehensive all-in-one PDF manipulation desktop application built with Python and PyQt6. It provides advanced tools for organizing, converting, editing, rotating, and smartly compressing PDF files with zero hassle.

**برنامج PDF Master Pro V3.2** هو تطبيق مكتبي متكامل واحترافي للتعامل مع ملفات PDF، يتميز بواجهة داكنة أنيقة وعصرية (Catppuccin theme) وسرعة فائقة في معالجة المستندات بدون الحاجة للاتصال بالإنترنت.

---

## 🚀 Key Features | المميزات الرئيسية

### 1. 📑 Organize Pages | تنظيم الصفحات
- **Merge PDFs (دمج ملفات PDF):** Merge multiple PDF files into a single document with drag-and-drop file reordering and sorting.
- **Split PDF (تقسيم PDF):** Extract specific page ranges or selected pages with instant visual previews.
- **Reorder Pages (إعادة ترتيب الصفحات):** Interactive thumbnail and list view. Drag and drop pages freely or use quick movement controls (`Move Left`, `Move Right`, `To First`, `To Last`, `Reverse All`).

### 2. 🔄 Convert Hub | مركز التحويل
- **Images to PDF (صور إلى PDF):** Convert images into PDF documents. Supports `.png`, `.jpg`, `.jpeg`, `.jfif`, `.webp`, `.bmp`, `.tiff`, `.tif`, `.ico`, and `.gif`.
- **Word to PDF (وورد إلى PDF):** 100% native fidelity conversion using the Word engine.
- **PDF to Word (PDF إلى وورد):** Convert PDF pages into editable `.docx` documents.
- **PDF to Images (PDF إلى صور):** Extract pages as ultra-high-resolution 300 DPI PNG images.
- **Convert to Pages (تفكيك إلى صفحات منفردة):** Split a multi-page PDF into individual 1-page PDF documents with **100% lossless vector quality**.
- **Rotate PDF (تدوير الصفحات):** Fix misaligned or sideways scanned documents with a live preview window. Supports 90° clockwise, 90° counter-clockwise, and 180° flip (applicable to All Pages or Current Page only).

### 3. 🎨 Edit & Annotate | الرسم والتعديل
- **Draw & Edit:** Freehand drawing, highlights, annotations, and shapes directly on PDF or image pages.
- **Page Numbering (ترقيم الصفحات):** Add customizable sequential page numbers (Arabic / English, font size, color, positions, margins, and custom formats like `Page {n} of {total}`).

### 4. 🗜️ Smart Compress | الضغط الذكي
- **Custom DPI Slider (سلايدر الدقة التفاعلي):** Smooth interactive slider from 50 DPI to 300 DPI. Default is set to **100 DPI** (the optimal balance between lightweight file size and razor-sharp text clarity).
- **Quick Presets (أزرار الاختيار السريع):** Instant one-click presets for `72 DPI (Max Compression)`, `90 DPI`, `100 DPI (Default)`, `120 DPI (Sharp)`, `150 DPI`, `200 DPI`, `250 DPI`, and `300 DPI`.
- **Squeeze / Lossless (ضغط بدون فقدان):** Stream and object compression using `cpdf` without altering image pixels.
- **Additional Optimization:** Fast Web View (Linearization) and Grayscale conversion options.

---

## 📥 Download Standalone Executable | تحميل البرنامج الجاهز

You can download the pre-compiled, fully standalone portable executable (`PDF Master Pro V3.exe`) from the [**Releases Page**](https://github.com/music-dj/pdf-tools/releases/latest).

> **Note:** The standalone executable has all required engines (Ghostscript, cpdf, optipng, jpegoptim) bundled inside. It runs directly on any Windows 10/11 system without installing Python or any third-party dependencies!

---

## 🛠️ Running from Source | التشغيل من الكود المصدري

### Prerequisites
- Python 3.10+ (Tested up to Python 3.14)
- Windows 10 or 11

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/music-dj/pdf-tools.git
   cd pdf-tools
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python "PDF editor tool.py"
   ```

---

## 📦 Building Standalone Executable | بناء ملف التشغيل

To build the standalone `.exe` using PyInstaller:

```bash
pyinstaller "PDF Master Pro.spec" --noconfirm
```
The output file will be generated in `dist/PDF Master Pro V3.exe`.

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
