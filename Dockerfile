# Development environment: Python 3.12
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Google Chrome (stable) + the matching ChromeDriver
RUN apt-get update \
 && apt-get install -y --no-install-recommends wget unzip ca-certificates \
 && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
 && apt-get install -y --no-install-recommends ./google-chrome-stable_current_amd64.deb \
 && rm google-chrome-stable_current_amd64.deb \
 && CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+(\.[0-9]+){3}') \
 && echo "Installed Chrome $CHROME_VERSION" \
 && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" \
 && unzip -q chromedriver-linux64.zip \
 && mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
 && chmod +x /usr/local/bin/chromedriver \
 && rm -rf chromedriver-linux64 chromedriver-linux64.zip /var/lib/apt/lists/*

WORKDIR /app

# Python libraries: Selenium, Flask, Gunicorn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Selenium automation + summarizer + REST API
COPY app.py .

EXPOSE 7000

# Start the API automatically when the container runs
CMD ["gunicorn", "--bind", "0.0.0.0:7000", "--workers", "1", "--threads", "4", "--timeout", "180", "app:app"]
