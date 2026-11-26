FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Full backend (RBAC, seed, ops, suggestions, …)
COPY *.py ./

ENV PORT=8026
ENV DB_PATH=./db/website.db
ENV RESET_STAFF_PASSWORDS=true
EXPOSE 8026

CMD ["python", "main.py"]
