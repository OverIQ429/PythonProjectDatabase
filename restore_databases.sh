#!/bin/bash
echo "🚀 Запуск всех сервисов..."
docker compose up -d --build

echo "⏳ Ждем запуска PostgreSQL..."
sleep 10

echo "📦 Копируем дампы в контейнеры..."
docker cp dumps/cafe_common cafe_postgres_common:/tmp/
docker cp dumps/cafe_branch_1 cafe_postgres_branch:/tmp/

echo "🔄 Восстанавливаем базы данных..."
docker exec cafe_postgres_common psql -U postgres -d cafe_common -f /tmp/cafe_common
docker exec cafe_postgres_branch psql -U postgres -d cafe_branch_1 -f /tmp/cafe_branch_1

echo "🐍 Запускаем приложение..."
python3 main.py