FROM python:3.10-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Команда для запуска приложения
# Здесь мы используем Uvicorn напрямую, как в примере для разработки.
# Для продакшена обычно используется Gunicorn, запускающий Uvicorn worker'ы.
# Пример команды для продакшена с Gunicorn:
# CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "reports_service:app", "--bind", "0.0.0.0:8000"]
# Для простоты пока используем Uvicorn напрямую
CMD ["uvicorn", "reports_service:app", "--host", "0.0.0.0", "--port", "8000"]