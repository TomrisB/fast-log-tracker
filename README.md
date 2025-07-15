# fast-log-tracker

Mini log management system based on FastAPI + Jinja2 + Bootstrap.

## Features
- Logging to TXT or MySQL database
- Date/IP filtering
- Simple web interface (Bootstrap)
- JSON API endpoints

## Installation
````bash
git clone https://github.com/<username>/fast-log-tracker.git
cd fast-log-tracker
pip install -r requirements.txt
uvicorn main:app --reload
