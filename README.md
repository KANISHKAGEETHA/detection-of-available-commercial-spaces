# Detection of Available Commercial Spaces

I built this prototype to help surface potential commercial rental spaces from real world video. It samples video frames, reads visible text with OCR, and stores the resulting leads with a location label and optional coordinates so they can be reviewed later.

## Run

Requires Python 3.10+, OpenCV, and Tesseract OCR installed on the machine.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Upload a video, enter a location label and optional latitude/longitude, and review the extracted text. Tesseract must be installed and available on PATH. The SQLite database is created locally as `spaces.db`.

## Scope

- I sample frames at a configurable interval and use Tesseract OCR to surface text that may indicate availability.
- I save the location label, optional GPS coordinates, video filename, and extracted text in SQLite.
- The resume mentions Firebase and REST APIs, but does not provide credentials, an API contract, or a database schema. I have kept this MVP local instead of inventing service configuration.
- OCR output is a lead for human review, not verified property information.
