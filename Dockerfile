FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py predictor.py scraper.py crex_functions.py ./
COPY model ./model
COPY templates ./templates
COPY static ./static
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/healthz'%os.getenv('PORT','8000'))"
CMD ["sh","-c","gunicorn app:app --workers 2 --threads 4 --timeout 60 --bind 0.0.0.0:${PORT:-8000} --access-logfile -"]
