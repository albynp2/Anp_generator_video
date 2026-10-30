# ANP Video Generator

Local-first AI Video Generator and Clipper.

## Technology Stack

- Python Backend
- FFmpeg
- Docker & Docker Compose
- Frontend Web Application

## Development

Development and testing are performed locally
before changes are merged into the stable branch.


### Template area boundary handling
Template Builder rounds image canvas dimensions down to even pixels for H.264 compatibility. Auto and manual areas are now constrained to that final canvas. Existing template areas that exceed the right or bottom edge are clipped safely during loading and normalized permanently when saved again.


## Layout video output v4.2
Pada dashboard, pilih:
- **Template Background** untuk menempatkan video pada `video_area` yang disimpan di Template Builder.
- **Full Screen Video** untuk memenuhi seluruh canvas output. Default `Contain` memakai background blur yang diambil dari video yang sama, sehingga konten landscape tetap terlihat utuh dan tidak meninggalkan bidang hitam besar. `Cover` tetap tersedia untuk crop-to-fill.

Resolusi output yang dipilih pada dashboard dikirim langsung ke backend (`output_width` dan `output_height`). Preset Full HD Portrait adalah 1080x1920.


----
