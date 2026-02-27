# Arthadrishti

Industrial Identity Intelligence Dashboard (Streamlit).

## Local Run (macOS / Apple Silicon)

Recommended Python: **3.12.9**

```bash
pyenv install 3.12.9
pyenv local 3.12.9
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run dashboard/app.py
```

## Streamlit Community Cloud

- App file path: `dashboard/app.py`
- Requirements: `requirements.txt`

## Notes

- Data files are read from `tools/zone_dna/output/<tag>/chapter_summary.csv`.
