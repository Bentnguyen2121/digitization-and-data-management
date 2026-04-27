from flask import Flask, render_template, request, redirect, session, flash, url_for, send_file
import mysql.connector
from functools import wraps
import pandas as pd  
import io

app = Flask(__name__)
app.secret_key = "nganhangso_2026"

# 1. Cấu hình tài khoản
USERS = {
    "admin": {"password": "123", "role": "admin"},
    "staff": {"password": "456", "role": "staff"}
}

# --- HÀM BỔ TRỢ ---
def get_tier(balance):
    """Phân hạng khách hàng dựa trên số dư"""
    val = float(balance) if balance is not None else 0
    if val >= 50000:
        return {"label": "Diamond", "color": "info", "icon": "fa-gem"}
    elif val >= 10000:
        return {"label": "Gold", "color": "warning", "icon": "fa-crown"}
    elif val >= 5000:
        return {"label": "Silver", "color": "secondary", "icon": "fa-medal"}
    else:
        return {"label": "Standard", "color": "success", "icon": "fa-user"}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("Bạn không có quyền thực hiện hành động này!", "danger")
            return redirect(url_for('customers_page'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Ben2005abcd.t", 
        database="bank_db"
    )

# --- ROUTES ---

@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Phân tích Nghề nghiệp
        cursor.execute("SELECT job, COUNT(*) as count FROM customers GROUP BY job ORDER BY count DESC LIMIT 5")
        job_data = cursor.fetchall()
        
        # Phân tích Hôn nhân
        cursor.execute("SELECT marital, COUNT(*) as count FROM customers GROUP BY marital")
        marital_data = cursor.fetchall()
        
        # Phân tích Vay nhà - LẤY SỐ DƯ TRUNG BÌNH VÀ LÀM TRÒN
        cursor.execute("SELECT housing, AVG(balance) as avg_balance FROM customers GROUP BY housing")
        housing_balance_data = cursor.fetchall()
        
        # Thống kê tổng quan
        cursor.execute("SELECT COUNT(*) as total_users, SUM(balance) as total_balance, AVG(age) as avg_age FROM customers")
        summary = cursor.fetchone()
        
        # Top khách hàng VIP
        cursor.execute("SELECT id, age, job, balance, housing FROM customers ORDER BY balance DESC LIMIT 5")
        top_customers = cursor.fetchall()
        for cust in top_customers:
            cust['tier'] = get_tier(cust['balance'])
            
    finally:
        cursor.close()
        conn.close()
    
    # CHUẨN BỊ DỮ LIỆU BIỂU ĐỒ (Làm tròn số để biểu đồ mượt hơn)
    return render_template('dashboard.html', 
                           labels_job=[row['job'] for row in job_data], 
                           values_job=[row['count'] for row in job_data], 
                           labels_marital=[row['marital'] for row in marital_data], 
                           values_marital=[row['count'] for row in marital_data],
                           labels_housing=["Có vay" if row['housing'] == 'yes' else "Không" for row in housing_balance_data],
                           values_housing=[round(float(row['avg_balance']), 2) if row['avg_balance'] else 0 for row in housing_balance_data],
                           top_customers=top_customers, summary=summary)

@app.route('/customers')
@login_required
def customers_page():
    job = request.args.get('job', '')
    min_bal = request.args.get('min_bal', '')
    max_bal = request.args.get('max_bal', '')
    marital = request.args.get('marital', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM customers WHERE 1=1"
    params = []
    if job: query += " AND job LIKE %s"; params.append(f"%{job}%")
    if min_bal: query += " AND balance >= %s"; params.append(min_bal)
    if max_bal: query += " AND balance <= %s"; params.append(max_bal)
    if marital: query += " AND marital = %s"; params.append(marital)

    query += " ORDER BY id DESC LIMIT 100"
    cursor.execute(query, params)
    customers = cursor.fetchall()
    for cust in customers:
        cust['tier'] = get_tier(cust['balance'])
    cursor.close()
    conn.close()
    return render_template('customers.html', customers=customers, search_job=job, min_bal=min_bal, max_bal=max_bal, selected_marital=marital)

@app.route('/quick-search')
@login_required
def quick_search():
    customer_id = request.args.get('customer_id')
    if not customer_id or not customer_id.isdigit():
        flash("Vui lòng nhập ID hợp lệ!", "warning")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM customers WHERE id = %s", (customer_id,))
    customer = cursor.fetchone()
    cursor.close()
    conn.close()

    if customer:
        return redirect(url_for('edit_customer', id=customer_id))
    flash(f"Không tìm thấy khách hàng ID: {customer_id}", "danger")
    return redirect(url_for('dashboard'))

@app.route('/add_customer', methods=['POST'])
@login_required
def add_customer():
    try:
        age = request.form.get('age')
        job = request.form.get('job')
        marital = request.form.get('marital')
        balance = request.form.get('balance', 0)
        housing = request.form.get('housing', 'no')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customers (age, job, marital, balance, housing) 
            VALUES (%s, %s, %s, %s, %s)
        """, (age, job, marital, balance, housing))
        conn.commit()
        flash("Thêm khách hàng thành công!", "success")
    except Exception as e:
        flash(f"Lỗi khi thêm: {str(e)}", "danger")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
    return redirect(url_for('customers_page'))

@app.route('/export')
@login_required
def export_excel():
    try:
        conn = get_db_connection()
        query = "SELECT id, age, job, marital, balance, housing FROM customers"
        df = pd.read_sql(query, conn)
        conn.close()
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Customers')
        output.seek(0)
        
        return send_file(output, 
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, 
                         download_name='Danh_sach_khach_hang.xlsx')
    except Exception as e:
        flash(f"Lỗi xuất file: {str(e)}", "danger")
        return redirect(url_for('customers_page'))

@app.route('/delete/<int:id>')
@login_required
@admin_required
def delete_customer(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM customers WHERE id = %s", (id,))
        conn.commit()
        flash(f"Đã xóa khách hàng #{id}", "info")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('customers_page'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_customer(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        age = request.form.get('age')
        job = request.form.get('job')
        marital = request.form.get('marital') # Bổ sung marital để đồng bộ
        balance = float(request.form.get('balance', 0))
        cursor.execute("UPDATE customers SET age=%s, job=%s, marital=%s, balance=%s WHERE id=%s", 
                       (age, job, marital, balance, id))
        conn.commit()
        flash("Cập nhật thành công!", "success")
        return redirect(url_for('customers_page'))
        
    cursor.execute("SELECT * FROM customers WHERE id = %s", (id,))
    customer = cursor.fetchone()
    conn.close()
    if not customer:
        flash("Khách hàng không tồn tại!", "danger")
        return redirect(url_for('customers_page'))
    return render_template('edit_customer.html', customer=customer)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = USERS.get(username)
        if user and user['password'] == password:
            session.update({'logged_in': True, 'username': username, 'role': user['role']})
            return redirect(url_for('dashboard'))
        flash("Sai tài khoản hoặc mật khẩu!", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)