FROM python:3.12-slim
WORKDIR /app
COPY hos/api/requirements.txt /app/hos/api/requirements.txt
RUN pip install --no-cache-dir -r /app/hos/api/requirements.txt
COPY hos /app/hos
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "hos.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
