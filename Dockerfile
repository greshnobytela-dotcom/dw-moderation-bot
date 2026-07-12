FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ticket_bot.py report_bot.py salary_bot.py channel_styling.py ./
RUN mkdir -p /app/data

CMD ["python", "-u", "ticket_bot.py"]
