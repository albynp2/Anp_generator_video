# ANP Video Generator — Perubahan Template Builder & Kualitas

- Menambahkan dropdown Auto Template / Manual Template.
- Auto mode menghitung video area di tengah, text area di atas video, dan title area di bawah video; kontrol area manual disembunyikan.
- Manual mode menampilkan pilihan Video Area, Text Area, dan Title Area untuk drag-resize pada gambar.
- Menambahkan font themes Cinematic, Bold Impact, Modern, Elegant, dan Playful. Font preview memakai file font yang sama dari assets/fonts.
- Menambahkan tipe gaya Normal, Bold, Outline, Shadow, Glow, dan Fire.
- Menambahkan konfigurasi background teks: warna, transparansi, padding, dan radius. Renderer backend menerapkan background tersebut pada hasil render.
- Menjaga gambar template asli saat disimpan; koordinat konfigurasi memakai resolusi asli.
- Mempertahankan FFmpeg pad guard untuk fit Contain/Cover.
- Menaikkan default kualitas encode ke CRF 17 / preset medium. Pengaturan .env lokal tetap perlu diperiksa karena nilainya mengalahkan default compose.
- Menggenerikkan prompt caption dan label template bawaan.

Validasi yang dilakukan: Python compileall, render teks Pillow dengan background aktif, dan FFmpeg smoke test untuk Contain serta Cover. Build Vite belum dapat dijalankan karena dependency npm tidak tersedia dan instalasi npm timeout.
