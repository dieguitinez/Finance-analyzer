---
name: pdf_layout_vision_parser
version: 1.0.0
description: "Perform spatial analysis on the document to isolate the transaction ledger (tables) and discard non-transactional visual noise."
---

# PDF LAYOUT VISION PARSER
**Objective:** Perform spatial analysis on the document to isolate the transaction ledger (tables) and discard non-transactional visual noise.

## Instructions
1. **Geometric Analysis:** Analyze the geometric layout of the PDF pages. Identify tabular structures based on column alignment and whitespace.
2. **Anchor Identification:** Locate the anchor header row. Look for column titles such as "Date", "Description", "Transaction", "Amount", "Debit", "Credit", "Balance".
3. **Bounding Box Protocol:** Establish a bounding box that starts immediately below the header row and ends where the tabular structure breaks (e.g., before summary charts, marketing messages, or page footers).
4. **Noise Filtering:** Ignore all visual noise outside this bounding box: promotional banners, bank logos, page numbers, and interest rate disclosures.
5. **Multi-page Continuity:** If the table breaks at the end of page 1 and continues on page 2, concatenate the data within the bounding boxes seamlessly.
6. **Data Extraction:** Extract and pass only the text contained within the isolated tabular bounding boxes.

## Constraints
- Precision in bounding box detection is critical to avoid missing rows.
- Only tabular data should be passed to the next agent node.
