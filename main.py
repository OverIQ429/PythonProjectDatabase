import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from datetime import datetime
import random

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
        with self.common_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO dishes (name, description, base_price, category_id)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (name, description, price, category_id))
            dish_id = cursor.fetchone()[0]
            self.common_conn.commit()
            print(f" Dish '{name}' created with ID: {dish_id}")
            return dish_id

    def read_dishes(self, category_id=None):
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
            print("  Menu:")
            for dish in dishes:
                print(f"  {dish['id']}: {dish['name']} - {dish['base_price']} RUB ({dish['category_name']})")
            return dishes

    def update_dish_price(self, dish_id, new_price):
        with self.common_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE dishes SET base_price = %s WHERE id = %s
            """, (new_price, dish_id))
            self.common_conn.commit()
            print(f" Dish ID {dish_id} price updated: {new_price} RUB")

    def deactivate_dish(self, dish_id):
        with self.common_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE dishes SET is_active = false WHERE id = %s
            """, (dish_id,))
            self.common_conn.commit()
            print(f" Dish ID {dish_id} deactivated")


    def generate_phone(self):
        operators = ['901', '902', '903', '904', '905', '906', '908', '909',
                     '910', '911', '912', '913', '914', '915', '916', '917']
        operator = random.choice(operators)
        number = ''.join([str(random.randint(0, 9)) for _ in range(7)])
        return f"+7{operator}{number}"

    def create_customer(self, first_name, last_name, email=None):
        phone = self.generate_phone()
        with self.branch_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO customers (first_name, last_name, phone, email)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (first_name, last_name, phone, email))
            customer_id = cursor.fetchone()[0]
            self.branch_conn.commit()
            print(f" Customer '{first_name} {last_name}' created with ID: {customer_id}")
            return customer_id

    def read_customers(self):
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM customers 
                ORDER BY registration_date DESC
            """)
            customers = cursor.fetchall()
            print(" Customers list:")
            for customer in customers:
                print(f"  {customer['id']}: {customer['first_name']} {customer['last_name']} - {customer['phone']}")
            return customers


    def create_order(self, employee_id, table_id, customer_id=None):
        with self.branch_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO orders (employee_id, table_id, customer_id, status, order_date)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (employee_id, table_id, customer_id, 'accepted', datetime.now()))
            order_id = cursor.fetchone()[0]
            self.branch_conn.commit()
            print(f" Order created with ID: {order_id}")
            return order_id

    def add_dish_to_order(self, order_id, dish_id, quantity):
        try:
            with self.common_conn.cursor() as cursor:
                cursor.execute("SELECT name, base_price FROM dishes WHERE id = %s AND is_active = true", (dish_id,))
                result = cursor.fetchone()
                if not result:
                    print(f" Dish ID {dish_id} not found or inactive")
                    return False

                dish_name, price = result

            with self.branch_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO orderitems (order_id, dish_id, quantity, price_at_time)
                    VALUES (%s, %s, %s, %s)
                """, (order_id, dish_id, quantity, price))

                cursor.execute("""
                    UPDATE orders SET total_amount = (
                        SELECT SUM(quantity * price_at_time) 
                        FROM orderitems 
                        WHERE order_id = %s
                    ) WHERE id = %s
                """, (order_id, order_id))

                self.branch_conn.commit()

            print(f" '{dish_name}' added to order {order_id} ({quantity} x {price} RUB)")
            return True

        except Exception as e:
            print(f" Error adding dish: {e}")
            return False

    def read_orders(self, status=None):
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
            print("Orders list:")
            for order in orders:
                customer = f"{order['customer_name']} {order['customer_last_name']}" if order[
                    'customer_name'] else "Guest"
                print(f"  Order {order['id']}: Table {order['table_number']}, "
                      f"Customer: {customer}, Status: {order['status']}, Amount: {order['total_amount']} RUB")
            return orders

    def update_order_status(self, order_id, new_status):
        valid_statuses = ['accepted', 'cooking', 'ready', 'completed', 'canceled']
        if new_status not in valid_statuses:
            print(f" Invalid status. Allowed: {', '.join(valid_statuses)}")
            return

        with self.branch_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE orders SET status = %s WHERE id = %s
            """, (new_status, order_id))
            self.branch_conn.commit()
            print(f"Order {order_id} status changed to: {new_status}")

    def read_order_details(self, order_id):
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
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
                print(f" Order {order_id} not found")
                return None, None

            cursor.execute("""
                SELECT oi.* 
                FROM orderitems oi
                WHERE oi.order_id = %s
            """, (order_id,))
            items = cursor.fetchall()

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

        print(f"\n📦 Order {order_id} details:")
        print(f"  Table: {order['table_number']}")
        print(f"  Waiter: {order['first_name']} {order['last_name']}")
        print(f"  Customer: {order['customer_name']} {order['customer_last_name']}")
        print(f"  Status: {order['status']}")
        print(f"  Total amount: {order['total_amount']} RUB")
        print(f"  Items:")

        for item in items:
            dish_name = dish_names.get(item['dish_id'], f"Dish #{item['dish_id']}")
            total = item['quantity'] * item['price_at_time']
            print(f"    - {dish_name}: {item['quantity']} x {item['price_at_time']} RUB = {total} RUB")

        return order, items

    def get_employee_info(self, employee_id):
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM employees WHERE id = %s
            """, (employee_id,))
            employee = cursor.fetchone()
            return employee

    def get_table_info(self, table_id):
        with self.branch_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM tables WHERE id = %s
            """, (table_id,))
            table = cursor.fetchone()
            return table


def main():
    manager = CafeDatabaseManager()

    try:

        # Demonstration operations
        manager.read_dishes()

        manager.read_customers()
        manager.read_orders()

        print("\nCREATE OPERATIONS:")
        # Create new customer in branch database
        customer_id = manager.create_customer("John", "Smith", "john.smith@email.com")

        # Create new order in branch database
        order_id = manager.create_order(employee_id=1, table_id=2, customer_id=customer_id)

        # Add dishes to order (cross-database operation!)
        print("\nCROSS-DATABASE OPERATIONS:")
        manager.add_dish_to_order(order_id, 1, 2)  # Dish from common database
        manager.add_dish_to_order(order_id, 3, 1)  # Dish from common database
        manager.add_dish_to_order(order_id, 5, 1)  # Dish from common database

        print("\nREAD OPERATIONS:")
        manager.read_order_details(order_id)

        print("\nUPDATE OPERATIONS:")
        manager.update_order_status(order_id, "ready")
        manager.update_dish_price(1, 500.00)  # Update price in common database

        print("\nDELETE OPERATIONS:")
        manager.deactivate_dish(7)  # Deactivate dish in common database

        print("\nFINAL DATA:")
        manager.read_dishes()

        manager.read_orders()
        manager.read_customers()

    except Exception as e:
        print(f" Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        manager.close_connections()


if __name__ == "__main__":
    main()