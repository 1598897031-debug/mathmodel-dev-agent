"""
Paper Generation Pipeline

IR → Markdown → Pandoc → docx

Architecture:
    paper_ir.json  (single source of truth)
        ↓
    paper_renderer.py  (IR → Markdown)
        ↓
    pandoc_builder.py  (Markdown → docx via Pandoc)
        ↓
    final_paper.docx
"""
