FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data
ENV CAMPUSFLOW_DB_URL=sqlite:////app/data/campusflow.db
EXPOSE 8000
CMD ["python", "run.py"]
