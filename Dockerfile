FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Credentials must be provided via environment variables at runtime.
# Never bake credentials into the image.
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.main"]
