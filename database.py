import sqlite3
from datetime import date, timedelta
import bcrypt

def get_connection():
    return sqlite3.connect('bank_sales.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # --- Таблицы ядра системы ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            hashed_password TEXT,
            full_name TEXT,
            role TEXT,
            supervisor_id INTEGER,
            branch_id INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
            base_price REAL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date TEXT,
            product_id INTEGER,
            manager_id INTEGER,
            quantity INTEGER,
            revenue REAL,
            request_id INTEGER,
            client_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (manager_id) REFERENCES users(id),
            FOREIGN KEY (request_id) REFERENCES requests(id),
            FOREIGN KEY (client_id) REFERENCES client_profile(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS sales_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supervisor_id INTEGER,
            year_month TEXT,
            target_revenue REAL,
            FOREIGN KEY (supervisor_id) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_surname TEXT NOT NULL,
            client_status TEXT CHECK(client_status IN ('new', 'existing')),
            product_id INTEGER,
            manager_id INTEGER,
            request_date TEXT,
            status TEXT CHECK(status IN ('active', 'success', 'cancelled')),
            completion_date TEXT,
            cancellation_reason TEXT,
            client_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (manager_id) REFERENCES users(id),
            FOREIGN KEY (client_id) REFERENCES client_profile(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS client_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            surname TEXT NOT NULL,
            first_name TEXT,
            middle_name TEXT,
            birth_date TEXT,
            gender TEXT CHECK(gender IN ('М','Ж')),
            family_status TEXT,
            children_count INTEGER DEFAULT 0,
            monthly_income REAL,
            employment_type TEXT,
            current_balance REAL,
            total_assets REAL,
            credit_score INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            cluster INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            manager_id INTEGER NOT NULL,
            interaction_date TEXT NOT NULL,
            channel TEXT,
            duration_minutes INTEGER,
            result TEXT,
            notes TEXT,
            FOREIGN KEY (client_id) REFERENCES client_profile(id),
            FOREIGN KEY (manager_id) REFERENCES users(id)
        )
    ''')

    # Убедимся, что колонки client_id добавлены (старая БД)
    try:
        c.execute("ALTER TABLE sales ADD COLUMN request_id INTEGER REFERENCES requests(id)")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE sales ADD COLUMN client_id INTEGER REFERENCES client_profile(id)")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE requests ADD COLUMN client_id INTEGER REFERENCES client_profile(id)")
    except sqlite3.OperationalError:
        pass

    conn.commit()

    # Заполнение тестовыми данными, если таблицы пусты
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        _create_test_data(conn)

    conn.close()

def _create_test_data(conn):
    c = conn.cursor()

    # --- Пользователи ---
    admin_hash = bcrypt.hashpw("123".encode(), bcrypt.gensalt()).decode()
    sup_hash = bcrypt.hashpw("123".encode(), bcrypt.gensalt()).decode()
    man_hash = bcrypt.hashpw("123".encode(), bcrypt.gensalt()).decode()

    c.execute("INSERT INTO users (username, hashed_password, full_name, role, supervisor_id) VALUES (?,?,?,?,?)",
              ("admin", admin_hash, "Главный администратор", "admin", None))
    c.execute("INSERT INTO users (username, hashed_password, full_name, role, supervisor_id) VALUES (?,?,?,?,?)",
              ("supervisor1", sup_hash, "Иванов Иван Иванович", "supervisor", None))
    supervisor_id = c.lastrowid
    c.execute("INSERT INTO users (username, hashed_password, full_name, role, supervisor_id) VALUES (?,?,?,?,?)",
              ("manager1", man_hash, "Петров Петр Петрович", "manager", supervisor_id))
    manager_id = c.lastrowid

    # --- Продукты ---
    products = [
        ("Дебетовая карта (ДК)", "Карты", 35),
        ("Кредит наличными (КН)", "Кредиты", 135),
        ("Кредитная карта (КК)", "Карты", 65),
        ("Стикер", "Другое", 35),
        ("Страхование от мошенничества (СОМ)", "Страхование", 30),
        ("Страхование кредитной карты (СКК)", "Страхование", 45),
        ("Коробочный страховой продукт (КСП)", "Страхование", 100),
        ("Накопительный счет (НС)", "Сбережения", 150),
        ("Программа долгосрочных сбережений (ПДС)", "Инвестиции", 250),
        ("Зарплатный проект (ЗП)", "Бизнес", 150),
        ("Пенсия", "Соцпакет", 150),
        ("Автоплатеж на мобильную связь (АПМОБ)", "Услуги", 45),
        ("Автоплатеж за ЖКУ (АПЖКУ)", "Услуги", 45),
        ("Подписка", "Услуги", 50),
        ("Паевый инвестиционный фонд (ПИФ)", "Инвестиции", 200)
    ]
    for p in products:
        c.execute("INSERT INTO products (name, category, base_price) VALUES (?,?,?)", p)

    # Словарь product_id по названию
    c.execute("SELECT id, name FROM products")
    prod_rows = c.fetchall()
    product_ids = {name: pid for pid, name in prod_rows}

    # --- Клиенты (client_profile) ---
    clients_data = [
        ("Иванов", "Сергей", "Петрович", "1985-03-12", "М", "женат", 2, 120000, "наёмный", 45000, 1500000, 720),
        ("Петрова", "Анна", "Ивановна", "1990-07-23", "Ж", "замужем", 1, 85000, "наёмный", 12500, 500000, 650),
        ("Сидоров", "Алексей", "Владимирович", "1978-11-05", "М", "разведён", 0, 200000, "предприниматель", 50000, 3000000, 800),
        ("Козлова", "Елена", "Дмитриевна", "1965-02-18", "Ж", "вдова", 2, 55000, "пенсионер", 15000, 800000, 700),
        ("Смирнов", "Дмитрий", "Александрович", "1995-09-30", "М", "холост", 0, 70000, "наёмный", 5000, 100000, 600),
        ("Новикова", "Ольга", "Витальевна", "1982-04-17", "Ж", "замужем", 2, 150000, "наёмный", 30000, 1800000, 750),
        ("Васильев", "Игорь", "Андреевич", "1970-12-01", "М", "женат", 2, 180000, "предприниматель", 25000, 2500000, 680),
    ]
    for cdata in clients_data:
        c.execute('''INSERT INTO client_profile 
            (surname, first_name, middle_name, birth_date, gender, family_status, children_count, monthly_income, employment_type, current_balance, total_assets, credit_score, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (cdata[0], cdata[1], cdata[2], cdata[3], cdata[4], cdata[5], cdata[6], cdata[7], cdata[8], cdata[9], cdata[10], cdata[11], date.today().isoformat()))

    # Получим id клиентов по фамилии
    c.execute("SELECT id, surname FROM client_profile")
    clients = {surname: cid for cid, surname in c.fetchall()}

    # --- Заявки (requests) ---
    # Формат: (клиент_surname, client_status, product_name, request_date, status, completion_date, cancellation_reason)
    # --- Заявки (requests) ---
    requests_data = [
        ("Иванов", "new", "Кредитная карта (КК)", "2026-04-01", "success", "2026-04-05", None),
        ("Иванов", "existing", "Паевый инвестиционный фонд (ПИФ)", "2026-04-15", "cancelled", "2026-04-16",
         "Неактуально"),
        ("Петрова", "new", "Кредит наличными (КН)", "2026-04-02", "success", "2026-04-07", None),
        ("Петрова", "existing", "Стикер", "2026-04-20", "cancelled", "2026-04-21", "Недозвон"),
        ("Сидоров", "new", "Программа долгосрочных сбережений (ПДС)", "2026-04-03", "success", "2026-04-10", None),
        ("Сидоров", "existing", "Кредитная карта (КК)", "2026-04-18", "active", None, None),
        ("Козлова", "existing", "Пенсия", "2026-04-05", "success", "2026-04-12", None),
        ("Козлова", "new", "Дебетовая карта (ДК)", "2026-04-22", "cancelled", "2026-04-23", "Не успеваю к клиенту"),
        ("Смирнов", "new", "Кредитная карта (КК)", "2026-04-07", "success", "2026-04-14", None),
        ("Смирнов", "existing", "Стикер", "2026-04-25", "active", None, None),
        ("Новикова", "new", "Кредит наличными (КН)", "2026-04-09", "success", "2026-04-17", None),
        ("Новикова", "existing", "Паевый инвестиционный фонд (ПИФ)", "2026-04-28", "cancelled", "2026-04-29",
         "Другое: не подходит"),
        ("Васильев", "new", "Программа долгосрочных сбережений (ПДС)", "2026-04-12", "success", "2026-04-19", None),
        ("Васильев", "existing", "Кредит наличными (КН)", "2026-05-01", "active", None, None),
    ]
    for (surname, status, prod_name, req_date, req_status, comp_date, cancel_reason) in requests_data:
        client_id = clients[surname]
        prod_id = product_ids[prod_name]
        c.execute('''INSERT INTO requests 
            (client_surname, client_status, product_id, manager_id, request_date, status, completion_date, cancellation_reason, client_id)
            VALUES (?,?,?,?,?,?,?,?,?)''',
                  (surname, status, prod_id, manager_id, req_date, req_status, comp_date, cancel_reason, client_id))
    # Получим все заявки для связывания с продажами
    c.execute("SELECT id, client_id, product_id, status FROM requests WHERE manager_id=?", (manager_id,))
    requests_all = c.fetchall()  # (request_id, client_id, product_id, status)

    # --- Продажи (sales) ---
    # 1) Продажи, связанные с успешными заявками
    for req_id, client_id, prod_id, status in requests_all:
        if status == "success":
            c.execute("SELECT request_date, completion_date FROM requests WHERE id=?", (req_id,))
            row = c.fetchone()
            sale_date = row[1] if row[1] else row[0]
            c.execute("SELECT base_price FROM products WHERE id=?", (prod_id,))
            price = c.fetchone()[0]
            quantity = 1
            revenue = price * quantity
            c.execute('''INSERT INTO sales 
                (sale_date, product_id, manager_id, quantity, revenue, request_id, client_id)
                VALUES (?,?,?,?,?,?,?)''',
                (sale_date, prod_id, manager_id, quantity, revenue, req_id, client_id))

    # 2) Прямые продажи без привязки к заявке
    direct_sales = [
        ("Иванов", "Дебетовая карта (ДК)", 1, "2026-04-14"),
        ("Петрова", "Стикер", 2, "2026-04-18"),
        ("Сидоров", "Кредитная карта (КК)", 1, "2026-04-22"),
        ("Козлова", "Пенсия", 1, "2026-04-25"),
    ]
    for surname, prod_name, qty, sdate in direct_sales:
        client_id = clients[surname]
        prod_id = product_ids[prod_name]
        c.execute("SELECT base_price FROM products WHERE id=?", (prod_id,))
        price = c.fetchone()[0]
        revenue = price * qty
        c.execute('''INSERT INTO sales 
            (sale_date, product_id, manager_id, quantity, revenue, client_id)
            VALUES (?,?,?,?,?,?)''',
            (sdate, prod_id, manager_id, qty, revenue, client_id))

    # --- Взаимодействия (interactions) ---
    interactions_data = [
        ("Иванов", "2026-04-01", "office", 15, "request_created", "Первичная консультация по кредитной карте"),
        ("Иванов", "2026-04-05", "phone", 10, "sale_made", "Оформление кредитной карты"),
        ("Петрова", "2026-04-02", "office", 20, "request_created", "Консультация по кредиту наличными"),
        ("Петрова", "2026-04-07", "phone", 12, "sale_made", "Оформление кредита наличными"),
        ("Сидоров", "2026-04-03", "office", 25, "request_created", "Интерес к ПДС"),
        ("Сидоров", "2026-04-10", "phone", 8, "sale_made", "Оформление ПДС"),
        ("Козлова", "2026-04-05", "office", 30, "request_created", "Вопросы по пенсионному продукту"),
        ("Козлова", "2026-04-12", "phone", 15, "sale_made", "Оформление пенсии"),
        ("Смирнов", "2026-04-07", "chat", 5, "request_created", "Заявка на кредитную карту онлайн"),
        ("Смирнов", "2026-04-14", "phone", 7, "sale_made", "Одобрение и выдача карты"),
        ("Новикова", "2026-04-09", "office", 18, "request_created", "Консультация по кредиту наличными"),
        ("Новикова", "2026-04-17", "email", 2, "sale_made", "Одобрение кредита"),
        ("Васильев", "2026-04-12", "office", 22, "request_created", "Интерес к ПДС"),
        ("Васильев", "2026-04-19", "phone", 10, "sale_made", "Оформление ПДС"),
    ]
    for surname, i_date, channel, dur, result, notes in interactions_data:
        client_id = clients[surname]
        c.execute('''INSERT INTO interactions 
            (client_id, manager_id, interaction_date, channel, duration_minutes, result, notes)
            VALUES (?,?,?,?,?,?,?)''',
            (client_id, manager_id, i_date, channel, dur, result, notes))

    # --- Планы продаж на месяц ---
    supervisor_id = 2  # ID руководителя (убедитесь, что он существует)
    today = date.today()
    current_month = today.strftime("%Y-%m")
    next_month = (today.replace(day=1) + timedelta(days=32)).strftime("%Y-%m")
    c.execute("DELETE FROM sales_plans WHERE supervisor_id=? AND year_month=?", (supervisor_id, current_month))
    c.execute("INSERT INTO sales_plans (supervisor_id, year_month, target_revenue) VALUES (?,?,?)",
              (supervisor_id, current_month, 5000))
    c.execute("DELETE FROM sales_plans WHERE supervisor_id=? AND year_month=?", (supervisor_id, next_month))
    c.execute("INSERT INTO sales_plans (supervisor_id, year_month, target_revenue) VALUES (?,?,?)",
              (supervisor_id, next_month, 5000))
    conn.commit()