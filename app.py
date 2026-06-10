from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime

app = Flask(__name__)
# Güvenlik için uygulamanın gizli anahtarı (session ve flash mesajları için gereklidir)
app.secret_key = 'super_secret_finance_key'
DATABASE = 'finance.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    # Satırlara sözlük gibi erişebilmek için
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    # Kullanıcı giriş yapmışsa dashboard'a yönlendir, yapmamışsa login'e yönlendir
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Filtre parametreleri
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category_filter = request.args.get('category')
    search_query = request.args.get('search')

    # İşlemleri ve kategori bilgilerini çekiyoruz
    query = '''
        SELECT t.id, t.amount, t.date, t.description, c.name as category_name, c.type 
        FROM Transactions t
        JOIN Categories c ON t.category_id = c.id
        WHERE t.user_id = ?
    '''
    params = [user_id]
    
    if start_date:
        query += " AND t.date >= ?"
        params.append(start_date + " 00:00:00")
    if end_date:
        query += " AND t.date <= ?"
        params.append(end_date + " 23:59:59")
        
    if category_filter:
        query += " AND c.name = ?"
        params.append(category_filter)
        
    if search_query:
        query += " AND (t.description LIKE ? OR c.name LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        
    query += " ORDER BY t.date DESC"
    
    transactions = conn.execute(query, tuple(params)).fetchall()
    
    # Tüm benzersiz kategorileri dropdown için çekiyoruz
    user_categories = conn.execute('''
        SELECT DISTINCT c.name 
        FROM Categories c
        JOIN Transactions t ON c.id = t.category_id
        WHERE t.user_id = ?
        ORDER BY c.name
    ''', (user_id,)).fetchall()
    conn.close()
    
    # Toplam gelir, gider ve bakiye hesaplama
    total_income = sum(t['amount'] for t in transactions if t['type'] == 'Gelir')
    total_expense = sum(t['amount'] for t in transactions if t['type'] == 'Gider')
    balance = total_income - total_expense
    
    # Grafikler için verileri hazırlama
    expense_categories = {}
    timeline_data = {}
    
    for t in transactions:
        # Pie Chart için kategori bazlı giderler
        if t['type'] == 'Gider':
            cat = t['category_name']
            expense_categories[cat] = expense_categories.get(cat, 0) + t['amount']
            
        # Line Chart için günlük gelir/gider
        date_str = t['date'][:10] # Sadece YYYY-MM-DD
        if date_str not in timeline_data:
            timeline_data[date_str] = {'Gelir': 0, 'Gider': 0}
        timeline_data[date_str][t['type']] += t['amount']
        
    import json
    pie_chart_data = {
        'labels': list(expense_categories.keys()),
        'values': list(expense_categories.values())
    }
    
    sorted_dates = sorted(timeline_data.keys())
    line_chart_data = {
        'labels': sorted_dates,
        'income': [timeline_data[d]['Gelir'] for d in sorted_dates],
        'expense': [timeline_data[d]['Gider'] for d in sorted_dates]
    }
    
    return render_template('dashboard.html', 
                           transactions=transactions, 
                           total_income=total_income, 
                           total_expense=total_expense, 
                           balance=balance,
                           pie_chart_data=json.dumps(pie_chart_data),
                           line_chart_data=json.dumps(line_chart_data),
                           start_date=start_date,
                           end_date=end_date,
                           category_filter=category_filter,
                           search_query=search_query,
                           user_categories=user_categories)

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    type_ = request.form['type']
    category_name = request.form['category_name']
    amount = float(request.form['amount'])
    description = request.form.get('description', '')
    date_ = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user_id = session['user_id']
    
    conn = get_db_connection()
    
    # Kategori veritabanında var mı kontrol et, yoksa oluştur
    category = conn.execute('SELECT id FROM Categories WHERE name = ? AND type = ?', (category_name, type_)).fetchone()
    if category:
        category_id = category['id']
    else:
        cursor = conn.execute('INSERT INTO Categories (name, type) VALUES (?, ?)', (category_name, type_))
        category_id = cursor.lastrowid
        
    # İşlemi kaydet
    conn.execute('INSERT INTO Transactions (user_id, category_id, amount, date, description) VALUES (?, ?, ?, ?, ?)',
                 (user_id, category_id, amount, date_, description))
    conn.commit()
    conn.close()
    
    flash('İşlem başarıyla eklendi.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_transaction/<int:id>', methods=['POST'])
def delete_transaction(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    conn.execute('DELETE FROM Transactions WHERE id = ? AND user_id = ?', (id, session['user_id']))
    conn.commit()
    conn.close()
    flash('İşlem başarıyla silindi.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/edit_transaction/<int:id>', methods=['GET', 'POST'])
def edit_transaction(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    if request.method == 'POST':
        type_ = request.form['type']
        category_name = request.form['category_name']
        amount = float(request.form['amount'])
        description = request.form.get('description', '')
        
        category = conn.execute('SELECT id FROM Categories WHERE name = ? AND type = ?', (category_name, type_)).fetchone()
        if category:
            category_id = category['id']
        else:
            cursor = conn.execute('INSERT INTO Categories (name, type) VALUES (?, ?)', (category_name, type_))
            category_id = cursor.lastrowid
            
        conn.execute('''
            UPDATE Transactions 
            SET category_id = ?, amount = ?, description = ? 
            WHERE id = ? AND user_id = ?
        ''', (category_id, amount, description, id, session['user_id']))
        conn.commit()
        conn.close()
        flash('İşlem başarıyla güncellendi.', 'success')
        return redirect(url_for('dashboard'))
        
    transaction = conn.execute('''
        SELECT t.*, c.name as category_name, c.type 
        FROM Transactions t
        JOIN Categories c ON t.category_id = c.id
        WHERE t.id = ? AND t.user_id = ?
    ''', (id, session['user_id'])).fetchone()
    conn.close()
    
    if not transaction:
        flash('İşlem bulunamadı.', 'error')
        return redirect(url_for('dashboard'))
        
    return render_template('edit_transaction.html', t=transaction)

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            flash('Kullanıcı adı ve şifre zorunludur.', 'error')
            return render_template('register.html')
        
        # Şifreyi güvenli bir şekilde hashliyoruz
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            # Kullanıcıyı veritabanına ekle
            conn.execute('INSERT INTO Users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            flash('Kayıt başarılı! Lütfen giriş yapın.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Bu kullanıcı adı zaten alınmış.', 'error')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM Users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        # Kullanıcı var mı ve şifresi doğru mu kontrol et
        if user and check_password_hash(user['password'], password):
            # Kullanıcı giriş oturumunu başlat
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('Geçersiz kullanıcı adı veya şifre.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Oturumu temizle ve giriş sayfasına yönlendir
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)