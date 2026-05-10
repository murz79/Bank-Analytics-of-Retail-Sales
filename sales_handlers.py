import pandas as pd
from datetime import date
from database import get_connection
from calendar import monthrange
import re

def add_sale(manager_id, product_id, quantity, sale_date=None):
    if sale_date is None:
        sale_date = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT base_price FROM products WHERE id=?", (product_id,))
    price = c.fetchone()[0]
    revenue = price * quantity
    c.execute('''
        INSERT INTO sales (sale_date, product_id, manager_id, quantity, revenue)
        VALUES (?,?,?,?,?)
    ''', (sale_date, product_id, manager_id, quantity, revenue))
    conn.commit()
    conn.close()

def add_sale_with_request(manager_id, product_id, quantity, sale_date, request_id=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT base_price FROM products WHERE id=?", (product_id,))
    price = c.fetchone()[0]
    revenue = price * quantity
    c.execute('''
        INSERT INTO sales (sale_date, product_id, manager_id, quantity, revenue, request_id)
        VALUES (?,?,?,?,?,?)
    ''', (sale_date, product_id, manager_id, quantity, revenue, request_id))
    if request_id:
        c.execute('''
            UPDATE requests SET status = 'success', completion_date = ? WHERE id = ?
        ''', (sale_date, request_id))
    conn.commit()
    conn.close()

def get_manager_sales(manager_id, start_date=None, end_date=None):
    conn = get_connection()
    query = """
        SELECT s.id, s.sale_date, p.name as product, s.quantity, s.revenue
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.manager_id = ?
    """
    params = [manager_id]
    if start_date:
        query += " AND s.sale_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND s.sale_date <= ?"
        params.append(end_date)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_supervisor_group_sales(supervisor_id, start_date=None, end_date=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE role='manager' AND supervisor_id=?", (supervisor_id,))
    manager_ids = [row[0] for row in c.fetchall()]
    if not manager_ids:
        conn.close()
        return pd.DataFrame()
    placeholders = ','.join(['?']*len(manager_ids))
    query = f"""
        SELECT s.sale_date, u.full_name as manager, p.name as product, s.quantity, s.revenue
        FROM sales s
        JOIN users u ON s.manager_id = u.id
        JOIN products p ON s.product_id = p.id
        WHERE s.manager_id IN ({placeholders})
    """
    params = manager_ids
    if start_date:
        query += " AND s.sale_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND s.sale_date <= ?"
        params.append(end_date)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_sales_report(start_date, end_date):
    conn = get_connection()
    query = """
        SELECT s.sale_date, u.full_name as manager, p.name as product, s.quantity, s.revenue
        FROM sales s
        JOIN users u ON s.manager_id = u.id
        JOIN products p ON s.product_id = p.id
        WHERE s.sale_date BETWEEN ? AND ?
        ORDER BY s.sale_date
    """
    df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    conn.close()
    return df

# ---------- Заявки клиентов ----------
def create_request(manager_id, client_surname, client_status, product_id):
    conn = get_connection()
    c = conn.cursor()
    request_date = date.today().isoformat()
    c.execute('''
        INSERT INTO requests (client_surname, client_status, product_id, manager_id, request_date, status)
        VALUES (?,?,?,?,?,?)
    ''', (client_surname, client_status, product_id, manager_id, request_date, 'active'))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    return request_id

def get_active_requests(manager_id):
    conn = get_connection()
    query = '''
        SELECT r.id, r.client_surname, 
               CASE r.client_status WHEN 'new' THEN 'Новый' WHEN 'existing' THEN 'Действующий' END as status,
               p.name as product,
               r.request_date
        FROM requests r
        JOIN products p ON r.product_id = p.id
        WHERE r.manager_id = ? AND r.status = 'active'
        ORDER BY r.request_date DESC
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id,))
    conn.close()
    return df

def get_closed_requests(manager_id):
    conn = get_connection()
    query = '''
        SELECT r.id, r.client_surname,
               CASE r.client_status WHEN 'new' THEN 'Новый' WHEN 'existing' THEN 'Действующий' END as client_status,
               p.name as product,
               r.status,
               r.completion_date,
               r.cancellation_reason
        FROM requests r
        JOIN products p ON r.product_id = p.id
        WHERE r.manager_id = ? AND r.status IN ('success', 'cancelled')
        ORDER BY r.completion_date DESC
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id,))
    conn.close()
    return df

def cancel_request(request_id, reason):
    conn = get_connection()
    c = conn.cursor()
    completion_date = date.today().isoformat()
    c.execute('''
        UPDATE requests
        SET status = 'cancelled', completion_date = ?, cancellation_reason = ?
        WHERE id = ?
    ''', (completion_date, reason, request_id))
    conn.commit()
    conn.close()

def complete_request_with_sale(request_id, manager_id, product_id, quantity, sale_date):
    add_sale_with_request(manager_id, product_id, quantity, sale_date, request_id)

# ---------- Отчёты для менеджера ----------
def get_today_sales_with_points(manager_id, sale_date):
    conn = get_connection()
    query = '''
        SELECT s.sale_date, p.name as product, s.quantity, s.revenue
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.manager_id = ? AND s.sale_date = ?
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id, sale_date))
    conn.close()
    points_map = {
        "Дебетовая карта (ДК)": 35,
        "Кредит наличными (КН)": 135,
        "Кредитная карта (КК)": 65,
        "Стикер": 35,
        "Страхование от мошенничества (СОМ)": 30,
        "Страхование кредитной карты (СКК)": 45,
        "Коробочный страховой продукт (КСП)": 100,
        "Накопительный счет (НС)": 150,
        "Программа долгосрочных сбережений (ПДС)": 250,
        "Зарплатный проект (ЗП)": 150,
        "Пенсия": 150,
        "Автоплатеж на мобильную связь (АПМОБ)": 45,
        "Автоплатеж за ЖКУ (АПЖКУ)": 45,
        "Подписка": 50,
        "Паевый инвестиционный фонд (ПИФ)": 200,
        "Вклад": 150
    }

    df['points'] = df['product'].map(points_map).fillna(0) * df['quantity']
    return df

def get_today_successful_clients(manager_id, request_date):
    conn = get_connection()
    query = '''
        SELECT client_surname
        FROM requests
        WHERE manager_id = ? AND request_date = ? AND status = 'success'
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id, request_date))
    conn.close()
    return df['client_surname'].tolist()

def get_today_cancelled_clients(manager_id, request_date):
    conn = get_connection()
    query = '''
        SELECT client_surname, cancellation_reason
        FROM requests
        WHERE manager_id = ? AND request_date = ? AND status = 'cancelled'
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id, request_date))
    conn.close()
    return list(zip(df['client_surname'], df['cancellation_reason']))

def get_today_requests_count(manager_id, request_date):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM requests WHERE manager_id = ? AND request_date = ?', (manager_id, request_date))
    total = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM requests WHERE manager_id = ? AND request_date = ? AND status = "success"', (manager_id, request_date))
    success = c.fetchone()[0]
    conn.close()
    return total, success

def get_today_cross_sales(manager_id, sale_date):
    conn = get_connection()
    query = '''
        SELECT p.name as product, SUM(s.quantity) as total_quantity
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.manager_id = ? AND s.sale_date = ?
        GROUP BY p.name
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id, sale_date))
    conn.close()
    def extract_abbr(name):
        match = re.search(r'\(([^)]+)\)', name)
        return match.group(1) if match else name[:3].upper()
    df['abbr'] = df['product'].apply(extract_abbr)
    return df[['abbr', 'total_quantity']].to_dict('records')

# ---------- Планы продаж (баллы на одного сотрудника) ----------
def get_product_points(product_name):
    points_map = {
        "Дебетовая карта (ДК)": 35,
        "Кредит наличными (КН)": 135,
        "Кредитная карта (КК)": 65,
        "Стикер": 35,
        "Страхование от мошенничества (СОМ)": 30,
        "Страхование кредитной карты (СКК)": 45,
        "Коробочный страховой продукт (КСП)": 100,
        "Накопительный счет (НС)": 150,
        "Программа долгосрочных сбережений (ПДС)": 250,
        "Зарплатный проект (ЗП)": 150,
        "Пенсия": 150,
        "Автоплатеж на мобильную связь (АПМОБ)": 45,
        "Автоплатеж за ЖКУ (АПЖКУ)": 45,
        "Подписка": 50,
        "Паевый инвестиционный фонд (ПИФ)": 200,
        "Вклад": 150
    }
    return points_map.get(product_name, 0)

def set_monthly_plan_per_employee(supervisor_id, year_month, target_points_per_employee):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM sales_plans WHERE supervisor_id=? AND year_month=?", (supervisor_id, year_month))
    c.execute("INSERT INTO sales_plans (supervisor_id, year_month, target_revenue) VALUES (?,?,?)",
              (supervisor_id, year_month, target_points_per_employee))
    conn.commit()
    conn.close()

def get_monthly_plan_per_employee(supervisor_id, year_month):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT target_revenue FROM sales_plans WHERE supervisor_id=? AND year_month=?", (supervisor_id, year_month))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_employee_count_in_group(supervisor_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE role='manager' AND supervisor_id=?", (supervisor_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_group_plan_points(supervisor_id, year_month):
    per_employee = get_monthly_plan_per_employee(supervisor_id, year_month)
    if per_employee is None:
        return None
    emp_count = get_employee_count_in_group(supervisor_id)
    return per_employee * emp_count if emp_count > 0 else 0

def get_employee_actual_points(manager_id, year_month):
    start_date = f"{year_month}-01"
    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    end_date = f"{year_month}-{last_day}"
    conn = get_connection()
    query = '''
        SELECT s.quantity, p.name as product_name
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.manager_id = ? AND s.sale_date BETWEEN ? AND ?
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id, start_date, end_date))
    if df.empty:
        return 0
    df['points'] = df.apply(lambda row: get_product_points(row['product_name']) * row['quantity'], axis=1)
    conn.close()
    return df['points'].sum()

def get_group_actual_points(supervisor_id, year_month):
    start_date = f"{year_month}-01"
    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    end_date = f"{year_month}-{last_day}"
    conn = get_connection()
    query = '''
        SELECT s.quantity, p.name as product_name
        FROM sales s
        JOIN products p ON s.product_id = p.id
        JOIN users u ON s.manager_id = u.id
        WHERE u.supervisor_id = ? AND s.sale_date BETWEEN ? AND ?
    '''
    df = pd.read_sql_query(query, conn, params=(supervisor_id, start_date, end_date))
    conn.close()
    if df.empty:
        return 0
    df['points'] = df.apply(lambda row: get_product_points(row['product_name']) * row['quantity'], axis=1)
    return df['points'].sum()


def get_employees_with_points(supervisor_id, year_month):
    """Возвращает список сотрудников группы с их баллами и процентом выполнения плана"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, full_name, username FROM users WHERE role='manager' AND supervisor_id=?", (supervisor_id,))
    employees = c.fetchall()
    conn.close()
    if not employees:
        return pd.DataFrame()

    plan_per_employee = get_monthly_plan_per_employee(supervisor_id, year_month)
    if plan_per_employee is None or plan_per_employee == 0:
        # Если план не установлен, показываем прочерки
        data = []
        for emp_id, full_name, username in employees:
            actual = get_employee_actual_points(emp_id, year_month)
            data.append({
                'id': emp_id,
                'ФИО': full_name,
                'Логин': username,
                'План (баллы)': 'не установлен',
                'Факт (баллы)': actual,
                'Выполнение %': '—'
            })
        return pd.DataFrame(data)
    else:
        data = []
        for emp_id, full_name, username in employees:
            actual = get_employee_actual_points(emp_id, year_month)
            percent = (actual / plan_per_employee) * 100 if plan_per_employee > 0 else 0
            data.append({
                'id': emp_id,
                'ФИО': full_name,
                'Логин': username,
                'План (баллы)': round(plan_per_employee, 0),
                'Факт (баллы)': round(actual, 0),
                'Выполнение %': round(percent, 1)
            })
        return pd.DataFrame(data)

def get_all_managers_with_supervisors():
    """Возвращает df с id, full_name менеджера, supervisor_id, full_name руководителя"""
    conn = get_connection()
    query = '''
        SELECT m.id as manager_id, m.full_name as manager_name,
               m.supervisor_id, s.full_name as supervisor_name
        FROM users m
        LEFT JOIN users s ON m.supervisor_id = s.id
        WHERE m.role = 'manager'
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_all_supervisors():
    """Возвращает список всех руководителей (id, full_name)."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, full_name FROM users WHERE role='supervisor'", conn)
    conn.close()
    return df


def get_manager_conversion(manager_id, year_month):
    """Конверсия = успешные заявки / все заявки * 100 за месяц."""
    start_date = f"{year_month}-01"
    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    end_date = f"{year_month}-{last_day}"
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) FROM requests 
        WHERE manager_id = ? AND request_date BETWEEN ? AND ? AND status = 'success'
    ''', (manager_id, start_date, end_date))
    success = c.fetchone()[0]
    c.execute('''
        SELECT COUNT(*) FROM requests 
        WHERE manager_id = ? AND request_date BETWEEN ? AND ?
    ''', (manager_id, start_date, end_date))
    total = c.fetchone()[0]
    conn.close()
    if total == 0:
        return 0.0
    return (success / total) * 100


def get_manager_cross_sales_count(manager_id, year_month):
    """Количество клиентов (уникальных фамилий) у менеджера, купивших более одного продукта за месяц."""
    start_date = f"{year_month}-01"
    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    end_date = f"{year_month}-{last_day}"
    conn = get_connection()
    query = '''
        SELECT r.client_surname, COUNT(DISTINCT s.product_id) as product_count
        FROM sales s
        JOIN requests r ON s.request_id = r.id
        WHERE s.manager_id = ? AND s.sale_date BETWEEN ? AND ?
          AND r.client_surname IS NOT NULL AND r.client_surname != ''
        GROUP BY r.client_surname
        HAVING product_count > 1
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id, start_date, end_date))
    conn.close()
    return len(df)

def get_manager_high_value_conversion(manager_id, year_month, high_value_keywords=None):
    """
    Конверсия по доходным продуктам с учётом продаж (не только заказанных).
    Показывает, в какой доле успешных заявок (встреч) менеджер продал хотя бы один доходный продукт.
    """
    if high_value_keywords is None:
        high_value_keywords = ['ПИФ', 'ПДС', 'Вклад', 'Кредит наличными', 'СОМ', 'КСП', 'Подписка']

    # Определяем границы месяца
    start_date = f"{year_month}-01"
    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    end_date = f"{year_month}-{last_day}"

    conn = get_connection()

    # 1. Получаем все заявки менеджера за месяц
    query_requests = '''
        SELECT id, status
        FROM requests
        WHERE manager_id = ? AND request_date BETWEEN ? AND ?
    '''
    df_requests = pd.read_sql_query(query_requests, conn, params=(manager_id, start_date, end_date))
    if df_requests.empty:
        conn.close()
        return 0.0

    # 2. Отбираем только успешные заявки (status = 'success')
    success_requests = df_requests[df_requests['status'] == 'success']
    if success_requests.empty:
        conn.close()
        return 0.0

    # 3. Для каждой успешной заявки получаем все проданные продукты (из sales)
    success_ids = success_requests['id'].tolist()
    placeholders = ','.join(['?'] * len(success_ids))
    query_sales = f'''
        SELECT s.request_id, p.name as product_name
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.request_id IN ({placeholders})
    '''
    df_sales = pd.read_sql_query(query_sales, conn, params=success_ids)
    conn.close()

    if df_sales.empty:
        return 0.0

    # 4. Определяем, какие из успешных заявок содержат хотя бы один доходный продукт
    mask = df_sales['product_name'].str.contains('|'.join(high_value_keywords), case=False, na=False)
    high_value_sales = df_sales[mask]
    requests_with_hv = set(high_value_sales['request_id'].tolist())

    total_success = len(success_ids)
    hv_success_count = len(requests_with_hv)

    # 5. Конверсия = (число успешных заявок с доходным продуктом) / (все успешные заявки) * 100
    return (hv_success_count / total_success) * 100

def get_all_managers_rating(year_month):
    """Возвращает DataFrame со всеми менеджерами, их руководителями и метриками за месяц."""
    conn = get_connection()
    query_managers = '''
        SELECT u.id as manager_id, u.full_name as manager_name, 
               u2.id as supervisor_id, u2.full_name as supervisor_name
        FROM users u
        JOIN users u2 ON u.supervisor_id = u2.id
        WHERE u.role = 'manager'
    '''
    managers_df = pd.read_sql_query(query_managers, conn)
    conn.close()

    if managers_df.empty:
        return pd.DataFrame()

    results = []
    for _, row in managers_df.iterrows():
        manager_id = row['manager_id']
        supervisor_id = row['supervisor_id']

        # План и факт баллов
        plan = get_monthly_plan_per_employee(supervisor_id, year_month)
        actual = get_employee_actual_points(manager_id, year_month)
        if plan and plan > 0:
            percent = (actual / plan) * 100
        else:
            percent = 0.0
            plan = 0

        # Конверсия
        conversion = get_manager_conversion(manager_id, year_month)
        # Кросс-продажи
        cross_sales = get_manager_cross_sales_count(manager_id, year_month)
        # Конверсия доходных продуктов
        hv_conversion = get_manager_high_value_conversion(manager_id, year_month)
        # Общее количество заявок
        total_requests = get_manager_total_requests(manager_id, year_month)

        results.append({
            'Менеджер': row['manager_name'],
            'Руководитель': row['supervisor_name'],
            'Баллы (факт)': actual,
            'План (баллы)': plan,
            'Выполнение плана (%)': round(percent, 1),
            'Конверсия (%)': round(conversion, 1),
            'Кросс-продажи (клиенты)': cross_sales,
            'Конверсия доходных продуктов (%)': round(hv_conversion, 1),
            'Всего заявок': total_requests
        })

    return pd.DataFrame(results)

def create_request_with_client(manager_id, client_surname, client_status, product_id, client_id):
    conn = get_connection()
    c = conn.cursor()
    request_date = date.today().isoformat()
    c.execute('''
        INSERT INTO requests (client_surname, client_status, product_id, manager_id, request_date, status, client_id)
        VALUES (?,?,?,?,?,?,?)
    ''', (client_surname, client_status, product_id, manager_id, request_date, 'active', client_id))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    return request_id

def get_products_by_ids(product_ids):
    """Возвращает продукты с указанными id."""
    if not product_ids:
        return pd.DataFrame()
    placeholders = ','.join('?' * len(product_ids))
    conn = get_connection()
    query = f"SELECT id, name, category, base_price FROM products WHERE id IN ({placeholders})"
    df = pd.read_sql_query(query, conn, params=product_ids)
    conn.close()
    return df


# ========== ABC-анализ продуктов ==========
def abc_analysis(year_month):
    """
    Возвращает DataFrame с ABC-анализом продуктов за указанный месяц.
    Группа A: до 80% выручки, B: 80-95%, C: >95%.
    """
    start_date = f"{year_month}-01"
    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    end_date = f"{year_month}-{last_day}"

    conn = get_connection()
    query = '''
        SELECT p.name, SUM(s.revenue) as revenue
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.sale_date BETWEEN ? AND ?
        GROUP BY p.id
        ORDER BY revenue DESC
    '''
    df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    conn.close()

    if df.empty:
        return pd.DataFrame(columns=['product', 'revenue', 'cum_percent', 'group'])

    total = df['revenue'].sum()
    df['cum_percent'] = df['revenue'].cumsum() / total * 100
    df['group'] = df['cum_percent'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))
    df = df.rename(columns={'name': 'product', 'revenue': 'revenue'})
    return df


# ========== Прогнозирование выполнения плана (экстраполяция) ==========
def forecast_plan_completion(manager_id, year_month, supervisor_id=None):
    if supervisor_id is None:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT supervisor_id FROM users WHERE id=?", (manager_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0] is not None:
            supervisor_id = int(row[0])  # принудительно преобразуем в int
        else:
            return None

    plan = get_monthly_plan_per_employee(supervisor_id, year_month)
    if plan is None or plan == 0:
        # Если план всё равно не найден – возможно, проблема в типе данных в БД
        # Попробуем найти план без приведения (для отладки)
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT target_revenue, typeof(supervisor_id), typeof(year_month) FROM sales_plans WHERE supervisor_id=? AND year_month=?",
                  (supervisor_id, year_month))
        debug = c.fetchone()
        conn.close()
        return None

    actual_now = get_employee_actual_points(manager_id, year_month)

    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    today = date.today()

    if today.year < year or (today.year == year and today.month < month):
        return None

    days_passed = min(today.day, last_day)
    if days_passed == 0:
        return None

    projected = actual_now / days_passed * last_day
    projected_percent = (projected / plan) * 100
    actual_percent = (actual_now / plan) * 100

    return {
        'plan': plan,
        'actual_now': actual_now,
        'actual_percent': actual_percent,
        'projected': projected,
        'projected_percent': projected_percent,
        'days_passed': days_passed,
        'last_day': last_day
    }

def get_today_requests_with_client(manager_id):
    """Возвращает активные заявки менеджера за сегодня с полными данными клиента из client_profile."""
    today_str = date.today().isoformat()
    conn = get_connection()
    query = '''
        SELECT r.id, r.client_surname, r.client_status, r.product_id, p.name as product_name,
               cp.id as client_id, cp.birth_date, cp.gender, cp.family_status, cp.children_count,
               cp.monthly_income, cp.employment_type, cp.current_balance, cp.total_assets, cp.credit_score
        FROM requests r
        JOIN products p ON r.product_id = p.id
        LEFT JOIN client_profile cp ON r.client_id = cp.id
        WHERE r.manager_id = ? AND DATE(r.request_date) = ? AND r.status = 'active'
        ORDER BY r.client_surname
    '''
    df = pd.read_sql_query(query, conn, params=(manager_id, today_str))
    conn.close()
    return df


def get_product_pairs_analysis(start_date=None, end_date=None, min_support=0.01):
    """
    Анализ парности продуктов (Market Basket Analysis).
    Возвращает DataFrame с парами продуктов, support, confidence, lift.
    Транзакция = все продукты, проданные по одному request_id.
    """
    conn = get_connection()
    # Получаем продукты для каждой транзакции
    query = '''
        SELECT s.request_id, p.name as product_name
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.request_id IS NOT NULL
    '''
    params = []
    if start_date:
        query += " AND s.sale_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND s.sale_date <= ?"
        params.append(end_date)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return pd.DataFrame(columns=['product_A', 'product_B', 'support', 'confidence_A_B', 'confidence_B_A', 'lift'])

    # Группируем товары по транзакции (request_id)
    basket = df.groupby('request_id')['product_name'].apply(list).reset_index()
    basket.columns = ['request_id', 'products']

    # Количество транзакций
    total_trans = len(basket)

    # Словарь: товар -> список транзакций, где он встречается
    from collections import defaultdict
    product_to_trans = defaultdict(set)
    for idx, row in basket.iterrows():
        for prod in row['products']:
            product_to_trans[prod].add(row['request_id'])

    products = list(product_to_trans.keys())
    pairs = []

    # Перебираем все комбинации пар (чтобы не дублировать, идём по индексам)
    for i in range(len(products)):
        for j in range(i + 1, len(products)):
            A = products[i]
            B = products[j]
            trans_A = product_to_trans[A]
            trans_B = product_to_trans[B]

            # support = |A ∩ B| / total_trans
            inter = len(trans_A.intersection(trans_B))
            support = inter / total_trans if total_trans > 0 else 0
            if support < min_support:
                continue

            # confidence A → B = |A ∩ B| / |A|
            conf_AB = inter / len(trans_A) if len(trans_A) > 0 else 0
            # confidence B → A = |A ∩ B| / |B|
            conf_BA = inter / len(trans_B) if len(trans_B) > 0 else 0
            # lift = (support) / (support(A) * support(B))
            support_A = len(trans_A) / total_trans
            support_B = len(trans_B) / total_trans
            lift = support / (support_A * support_B) if support_A * support_B > 0 else 0

            pairs.append({
                'product_A': A,
                'product_B': B,
                'support': round(support, 4),
                'confidence_A_B': round(conf_AB, 4),
                'confidence_B_A': round(conf_BA, 4),
                'lift': round(lift, 2)
            })

    result_df = pd.DataFrame(pairs)
    # Отсортируем по убыванию lift или confidence
    if not result_df.empty:
        result_df = result_df.sort_values('lift', ascending=False)
    return result_df

def get_manager_total_requests(manager_id, year_month):
    """Возвращает общее количество заявок менеджера за месяц (все статусы)."""
    start_date = f"{year_month}-01"
    year, month = map(int, year_month.split('-'))
    last_day = monthrange(year, month)[1]
    end_date = f"{year_month}-{last_day}"
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) FROM requests
        WHERE manager_id = ? AND request_date BETWEEN ? AND ?
    ''', (manager_id, start_date, end_date))
    total = c.fetchone()[0]
    conn.close()
    return total