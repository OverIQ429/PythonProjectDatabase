#!/bin/bash

echo "Ожидание запуска PostgreSQL..."
sleep 10

# Восстановление cafe_common (порт 5432)
echo "Восстанавливаю cafe_common на порту 5432..."
docker exec -i cafe_postgres_common psql -U postgres -d cafe_common -f /dumps/cafe_common.txt

# Восстановление cafe_branch_1 (порт 5433)
echo "Восстанавливаю cafe_branch_1 на порту 5433..."
docker exec -i cafe_postgres_branch psql -U postgres -d cafe_branch_1 -f /dumps/cafe_branch_1.txt

echo "✅ Обе базы данных восстановлены!"
echo "   cafe_common доступна на localhost:5432"
echo "   cafe_branch_1 доступна на localhost:5433"