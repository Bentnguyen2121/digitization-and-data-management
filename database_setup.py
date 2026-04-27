import pandas as pd
import mysql.connector

# 1. Kết nối đến MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Ben2005abcd.t" 
)
cursor = db.cursor()

# 2. Tạo Database
cursor.execute("CREATE DATABASE IF NOT EXISTS bank_db")
cursor.execute("USE bank_db")

# 3. Tạo bảng customers dựa trên các cột của file bank.csv
cursor.execute("DROP TABLE IF EXISTS customers")
create_table_query = """
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    age INT,
    job VARCHAR(100),
    marital VARCHAR(50),
    education VARCHAR(100),
    is_default VARCHAR(10),
    balance INT,
    housing VARCHAR(10),
    loan VARCHAR(10),
    contact VARCHAR(50),
    day INT,
    month VARCHAR(20),
    duration INT,
    campaign INT,
    pdays INT,
    previous INT,
    poutcome VARCHAR(50),
    deposit VARCHAR(10)
)
"""
cursor.execute(create_table_query)

# 4. Đọc file CSV và chèn dữ liệu vào MySQL
df = pd.read_csv('bank.csv')
# Chuyển đổi dữ liệu để phù hợp với kiểu SQL (nếu cần)
for i, row in df.iterrows():
    sql = """INSERT INTO customers (age, job, marital, education, is_default, balance, 
             housing, loan, contact, day, month, duration, campaign, pdays, 
             previous, poutcome, deposit) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    cursor.execute(sql, tuple(row))

db.commit()
print(f"Đã số hóa thành công {cursor.rowcount} dòng dữ liệu vào MySQL.")
cursor.close()
db.close()