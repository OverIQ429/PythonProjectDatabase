import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from datetime import datetime


class CafeDatabaseManager:
    def __init__(self):
        # Подключение к общей базе (порт 5432)
        self.common_conn = psycopg2.connect(
            host="localhost",
            port="5432",
            database="cafe_common",
            user="postgres",
            password="postgres"
        )

        # Подключение к базе филиала (порт 5433)
        self.branch_conn = psycopg2.connect(
            host="localhost",
            port="5433",
            database="cafe_branch_1",
            user="postgres",
            password="postgres"
        )

    def close_connections(self):
        self.common_conn.close()
        self.branch_conn.close()


    def create_dish(self, name, description, price, category_id):
        """CREATE: Добавить новое блюдо в общую базу"""
        with self.common_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO dishes (name, description, base_price, category_id)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (name, description, price, category_id))
            dish_id = cursor.fetchone()[0]
            self.common_conn.commit()
            print(f" Блюдо '{name}' создано с ID: {dish_id}")
            return dish_id

    def read_dishes(self, category_id=None):
        """READ: Получить блюда из общей базы"""
        with self.common_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            if category_id:
                cursor.execute("""
                    SELECT d.*, dc.name as category_name 
                    FROM dishes d 
                    LEFT JOIN dishcategories dc ON d.category_id = dc.id
                    WHERE d.category_id = %s AND d.is_active = true
                """, (category_id,))
            else:
                cursor.execute("""
                    SELECT d.*, dc.name as category_name 
                    FROM dishes d 
                    LEFT JOIN dishcategories dc ON d.category_id = dc.id
                    WHERE d.is_active = true
                """)

            dishes = cursor.fetchall()
            print("🍽️  Список блюд:")
            for dish in dishes:
                print(f"  {dish['id']}: {dish['name']} - {dish['base_price']} руб. ({dish['category_name']})")
            return dishes

    def update_dish_price(self, dish_id, new_price):
        """UPDATE: Обновить цену блюда в общей базе"""
        with self.common_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE dishes SET base_price = %s WHERE id = %s
            """, (new_price, dish_id))
            self.common_conn.commit()
            print(f" Цена блюда ID {dish_id} обновлена: {new_price} руб.")

    def deactivate_dish(self, dish_id):
        """DELETE: Деактивировать блюдо в общей базе"""
        with self.common_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE dishes SET is_active = false WHERE id = %s
            """, (dish_id,))
            self.common_conn.commit()
            print(f"🚫 Блюдо ID {dish_id} деактивировано")

    # === CRUD для КЛИЕНТОВ (cafe_branch_1 - порт 5433) ===

    def create_customer(self, first_name, last_name, phone, email=None):
        """CREATE: Добавить нового клиента в базу филиала"""
        with self.branch_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO customers (first_name, last_name, phone, email)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (first_name, last_name, phone, email))
            customer_id = cursor.fetchone()[0]
            self.branch_conn.commit()
            print(f"👤 Клиент '{first_name} {last_name}' создан с ID: {customer_id}")
            return customer_id

    def read_customers(self):
        """READ: Получить клиентов из базы филиала"""
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM customers 
                ORDER BY registration_date DESC
            """)
            customers = cursor.fetchall()
            print("👥 Список клиентов:")
            for customer in customers:
                points = f", {customer['loyalty_points']} баллов" if customer['loyalty_points'] else ""
                print(
                    f"  {customer['id']}: {customer['first_name']} {customer['last_name']} - {customer['phone']}{points}")
            return customers

    def update_customer_loyalty(self, customer_id, points):
        """UPDATE: Обновить бонусные баллы клиента"""
        with self.branch_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE customers SET loyalty_points = %s WHERE id = %s
            """, (points, customer_id))
            self.branch_conn.commit()
            print(f"⭐ Клиенту ID {customer_id} начислено {points} баллов")

    # === CRUD для ЗАКАЗОВ (cafe_branch_1 - порт 5433) ===

    def create_order(self, employee_id, table_id, customer_id=None):
        """CREATE: Создать новый заказ в базе филиала"""
        with self.branch_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO orders (employee_id, table_id, customer_id)
                VALUES (%s, %s, %s) RETURNING id
            """, (employee_id, table_id, customer_id))
            order_id = cursor.fetchone()[0]
            self.branch_conn.commit()
            print(f"📝 Заказ создан с ID: {order_id}")
            return order_id

    def add_dish_to_order(self, order_id, dish_id, quantity):
        """CREATE: Добавить блюдо в заказ (межбазовая операция)"""
        try:
            # Шаг 1: Получить цену блюда из ОБЩЕЙ базы (порт 5432)
            with self.common_conn.cursor() as cursor:
                cursor.execute("SELECT name, base_price FROM dishes WHERE id = %s AND is_active = true", (dish_id,))
                result = cursor.fetchone()
                if not result:
                    print(f"❌ Блюдо ID {dish_id} не найдено или неактивно")
                    return False

                dish_name, price = result

            # Шаг 2: Добавить в заказ в базе ФИЛИАЛА (порт 5433)
            with self.branch_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO orderitems (order_id, dish_id, quantity, price_at_time)
                    VALUES (%s, %s, %s, %s)
                """, (order_id, dish_id, quantity, price))

                # Обновить общую сумму заказа
                cursor.execute("""
                    UPDATE orders SET total_amount = (
                        SELECT SUM(quantity * price_at_time) 
                        FROM orderitems 
                        WHERE order_id = %s
                    ) WHERE id = %s
                """, (order_id, order_id))

                self.branch_conn.commit()

            print(f"🍕 '{dish_name}' добавлено в заказ {order_id} ({quantity} x {price} руб.)")
            return True

        except Exception as e:
            print(f"❌ Ошибка при добавлении блюда: {e}")
            return False

    def read_orders(self, status=None):
        """READ: Получить заказы из базы филиала"""
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            if status:
                cursor.execute("""
                    SELECT o.*, e.first_name, e.last_name, t.table_number,
                           c.first_name as customer_name, c.last_name as customer_last_name
                    FROM orders o
                    LEFT JOIN employees e ON o.employee_id = e.id
                    LEFT JOIN tables t ON o.table_id = t.id
                    LEFT JOIN customers c ON o.customer_id = c.id
                    WHERE o.status = %s
                    ORDER BY o.order_date DESC
                """, (status,))
            else:
                cursor.execute("""
                    SELECT o.*, e.first_name, e.last_name, t.table_number,
                           c.first_name as customer_name, c.last_name as customer_last_name
                    FROM orders o
                    LEFT JOIN employees e ON o.employee_id = e.id
                    LEFT JOIN tables t ON o.table_id = t.id
                    LEFT JOIN customers c ON o.customer_id = c.id
                    ORDER BY o.order_date DESC
                """)

            orders = cursor.fetchall()
            print("📋 Список заказов:")
            for order in orders:
                status_emoji = {
                    'Новый': '🟡',
                    'Готов': '🟢',
                    'Оплачен': '🔵',
                    'Отменен': '🔴'
                }.get(order['status'], '⚪')

                customer = f"{order['customer_name']} {order['customer_last_name']}" if order[
                    'customer_name'] else "Гость"
                print(f"  {status_emoji} Заказ {order['id']}: Стол {order['table_number']}, "
                      f"Клиент: {customer}, Сумма: {order['total_amount']} руб.")
            return orders

    def update_order_status(self, order_id, new_status):
        """UPDATE: Обновить статус заказа в базе филиала"""
        valid_statuses = ['Новый', 'Готов', 'Оплачен', 'Отменен']
        if new_status not in valid_statuses:
            print(f"❌ Неверный статус. Допустимые: {', '.join(valid_statuses)}")
            return

        with self.branch_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE orders SET status = %s WHERE id = %s
            """, (new_status, order_id))
            self.branch_conn.commit()
            print(f"🔄 Статус заказа {order_id} изменен на: {new_status}")

    def read_order_details(self, order_id):
        """READ: Детали заказа с информацией из обеих баз"""
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Информация о заказе из базы филиала
            cursor.execute("""
                SELECT o.*, e.first_name, e.last_name, t.table_number,
                       c.first_name as customer_name, c.last_name as customer_last_name
                FROM orders o
                LEFT JOIN employees e ON o.employee_id = e.id
                LEFT JOIN tables t ON o.table_id = t.id
                LEFT JOIN customers c ON o.customer_id = c.id
                WHERE o.id = %s
            """, (order_id,))
            order = cursor.fetchone()

            if not order:
                print(f"❌ Заказ {order_id} не найден")
                return None, None

            # Позиции заказа с названиями блюд из общей базы
            cursor.execute("""
                SELECT oi.* 
                FROM orderitems oi
                WHERE oi.order_id = %s
            """, (order_id,))
            items = cursor.fetchall()

        # Получаем названия блюд из ОБЩЕЙ базы
        dish_names = {}
        if items:
            dish_ids = [item['dish_id'] for item in items]
            placeholders = ','.join(['%s'] * len(dish_ids))

            with self.common_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(f"""
                    SELECT id, name FROM dishes 
                    WHERE id IN ({placeholders})
                """, dish_ids)
                for dish in cursor.fetchall():
                    dish_names[dish['id']] = dish['name']

        print(f"\n📦 Детали заказа {order_id}:")
        print(f"  Стол: {order['table_number']}")
        print(f"  Официант: {order['first_name']} {order['last_name']}")
        print(f"  Клиент: {order['customer_name']} {order['customer_last_name']}")
        print(f"  Статус: {order['status']}")
        print(f"  Общая сумма: {order['total_amount']} руб.")
        print(f"  Позиции:")

        for item in items:
            dish_name = dish_names.get(item['dish_id'], f"Блюдо #{item['dish_id']}")
            total = item['quantity'] * item['price_at_time']
            print(f"    - {dish_name}: {item['quantity']} x {item['price_at_time']} руб. = {total} руб.")

        return order, items

    def get_employee_info(self, employee_id):
        """READ: Получить информацию о сотруднике"""
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM employees WHERE id = %s
            """, (employee_id,))
            employee = cursor.fetchone()
            return employee

    def get_table_info(self, table_id):
        """READ: Получить информацию о столике"""
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM tables WHERE id = %s
            """, (table_id,))
            table = cursor.fetchone()
            return table


def main():
    manager = CafeDatabaseManager()

    try:
        print("=" * 60)
        print("🏪 ДЕМОНСТРАЦИЯ CRUD ОПЕРАЦИЙ ДЛЯ КАФЕ")
        print("   (2 базы данных на разных портах)")
        print("=" * 60)

        # Демонстрация операций
        print("\n1. 📊 ТЕКУЩИЕ ДАННЫЕ:")
        print("\nИз ОБЩЕЙ базы (порт 5432):")
        manager.read_dishes()

        print("\nИз базы ФИЛИАЛА (порт 5433):")
        manager.read_customers()
        manager.read_orders()

        print("\n2. 🆕 CREATE ОПЕРАЦИИ:")
        # Создаем нового клиента в базе филиала
        customer_id = manager.create_customer("Анна", "Демо", "+78005553535", "anna@demo.ru")

        # Создаем новый заказ в базе филиала
        order_id = manager.create_order(employee_id=1, table_id=2, customer_id=customer_id)

        # Добавляем блюда в заказ (межбазовая операция!)
        print("\n3. 🔗 МЕЖБАЗОВЫЕ ОПЕРАЦИИ:")
        manager.add_dish_to_order(order_id, 1, 2)  # Блюдо из общей базы
        manager.add_dish_to_order(order_id, 3, 1)  # Блюдо из общей базы
        manager.add_dish_to_order(order_id, 5, 1)  # Блюдо из общей базы

        print("\n4. 📖 READ ОПЕРАЦИИ:")
        manager.read_order_details(order_id)

        print("\n5. ✏️ UPDATE ОПЕРАЦИИ:")
        manager.update_order_status(order_id, "Готов")
        manager.update_customer_loyalty(customer_id, 50)  # Начисляем баллы
        manager.update_dish_price(1, 480.00)  # Обновляем цену в общей базе

        print("\n6. 🗑️ DELETE ОПЕРАЦИИ:")
        manager.deactivate_dish(7)  # Деактивируем блюдо в общей базе

        print("\n7. 📊 ФИНАЛЬНЫЕ ДАННЫЕ:")
        print("\nОбщая база (порт 5432):")
        manager.read_dishes()

        print("\nБаза филиала (порт 5433):")
        manager.read_orders()
        manager.read_customers()

        print("\n" + "=" * 60)
        print("✅ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("   cafe_common: localhost:5432")
        print("   cafe_branch_1: localhost:5433")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        manager.close_connections()


if __name__ == "__main__":
    main()