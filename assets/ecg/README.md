# ECG learning case assets

Place locally sourced ECG image files in this directory. Reference each file in `data/cases.json` with a relative `image_path`, for example `assets/ecg/case_001.png`.

When adding an image, also provide its `source_name`, `source_url`, `license`, and `source_record`. Do not add images without verified provenance. Until a source image is available, keep `image_path` and provenance fields null; the app will show a placeholder and the reasoning workflow remains usable.
