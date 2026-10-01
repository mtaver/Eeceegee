# ECG learning case assets

Place original, locally sourced ECG image files in `assets/ecg/source/` and processed learner-safe copies in `assets/ecg/learner/`. Reference originals in `data/cases.json` with a relative `image_path`, for example `assets/ecg/source/NSR_001.jpg`. The learner UI displays only the corresponding processed file from the learner directory.

When adding an image, also provide its `source_name`, `source_url`, `license`, and `source_record`. Do not add images without verified provenance. Until a source image is available, keep `image_path` and provenance fields null; the app will show a placeholder and the reasoning workflow remains usable. Never overwrite an original with its learner-safe copy.
