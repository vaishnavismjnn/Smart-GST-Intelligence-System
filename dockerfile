FROM python:3.11-slim

# Install tesseract
RUN apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-eng

WORKDIR /app

COPY requriments.txt .
RUN pip install -r requriments.txt

COPY . .

CMD ["uvicorn", "backend.mainn:app", "--host", "0.0.0.0", "--port", "10000"]