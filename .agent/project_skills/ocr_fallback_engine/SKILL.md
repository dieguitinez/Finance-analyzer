---
name: ocr_fallback_engine
version: 1.0.0
description: "Detect if a PDF is a flat image and apply High-Fidelity OCR while strictly preserving spatial layout."
---

# OCR FALLBACK ENGINE
**Objective:** Act as a pre-processing safeguard. Detect if a PDF is a flat image (scanned document) and apply High-Fidelity Optical Character Recognition (OCR) while strictly preserving spatial layout.

## Instructions
1. **Input Analysis:** Receive the raw PDF document. Scan metadata and structure for a selectable digital text layer.
2. **Decision Gate:**
   - **Text Exists:** If digital text exists in the tabular areas, bypass OCR and return the original document to the pipeline.
   - **Flat Image:** If the document is a flat image or lacks selectable text, activate the OCR engine.
3. **Spatial OCR Execution:** Perform full-page text extraction. Preserve exact X and Y coordinate bounding boxes of every recognized word. Map text precisely to original visual layout.
4. **Noise Reduction:** Ignore background watermarks or physical bank stamps. Focus on machine-printed alphanumeric characters.
5. **Output:** Return digitally reconstructed document payload (selectable text with preserved geometry).

## Constraints
- Spatial geometry preservation is mandatory for downstream parsing.
- Accuracy in "Flat Image" detection avoids redundant processing costs.
