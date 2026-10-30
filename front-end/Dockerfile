FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY front-end/ .

EXPOSE 8501

CMD ["streamlit", "run", "display.py", "--server.address=0.0.0.0", "--server.port=8501"]