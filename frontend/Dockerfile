FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY templates/ templates/
COPY static/ static/

ENV PORT=8027
ENV API_BASE_URL=http://backend:8026
EXPOSE 8027

CMD ["python", "main.py"]
