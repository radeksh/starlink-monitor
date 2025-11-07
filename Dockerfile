FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY starlink_client.py .
COPY pingmon.py .

RUN chmod +x pingmon.py

EXPOSE 9877

ENV DISH_IP=192.168.100.1
ENV DISH_PORT=9200
ENV POLL_INTERVAL=2
ENV ALERT_THRESHOLD=0.1
ENV HTTP_PORT=9877
ENV LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9877/health').read()"

CMD ["python", "-u", "pingmon.py"]
