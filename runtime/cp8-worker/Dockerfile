FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin worker
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt
COPY --chown=1000:1000 cp8_agent.py /app/cp8_agent.py
USER 1000:1000
ENTRYPOINT ["python", "/app/cp8_agent.py"]
