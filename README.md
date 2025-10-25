# Streamlit Frontend — Valve Data Sheet

This single-page Streamlit app reproduces your first Excel sheet:
- **Green cells** are **inputs**.
- Non-green values are shown as **computed** (read-only).

It includes placeholder calculations for Operating Pressure (by ASME class),
Bore Diameter (by NPS), Face-to-Face (for 2"/Class 600), and a **demo** body wall
thickness formula. Replace with backend calls to your FastAPI compute service.

## Run
```bash
pip install streamlit
streamlit run app.py
```
