#!/bin/bash

echo "🔄 Восстановление баз данных..."

# Восстановление cafe_common
echo "📦 Восстанавливаю cafe_common..."
docker exec cafe_postgres_common psql -U postgres -d cafe_common -f /dumps/cafe_common.txt

# Восстановление cafe_branch_1
echo "📦 Восстанавливаю cafe_branch_1..."
docker exec cafe_postgres_branch psql -U postgres -d cafe_branch_1 -f /dumps/cafe_branch_1.txt

echo "✅ Базы данных восстановлены!"