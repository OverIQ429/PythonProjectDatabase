FROM python:3.11-slim

# Установка рабочей директории
WORKDIR /app

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка зависимостей Python
RUN pip install --no-cache-dir -r requirements.txt

# Установка PostgreSQL клиентов (для pg_dump/pg_restore)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование исходного кода
COPY . .

# Создание директорий для бэкапов
RUN mkdir -p dumps backups

# Даем права на выполнение скриптов
RUN chmod +x restore_databases.sh

# Открываем порт (если нужно)
EXPOSE 8000