---
name: parsing-pdf-layout
description: Extracts text from specific layout structures in PDFs. Use for table bounding box extraction.
---
# PDF Layout Vision Parser
## Cuándo usar este skill
- Extracción de tablas financieras ignorando ruido.
## Instrucciones
Usa pdfplumber para detectar bounding boxes de tablas.
```python
import pdfplumber
def extract_table_text(pdf_data: bytes) -> str:
    # Logic to extract only from table zones
    return "Extracted table content"
```
