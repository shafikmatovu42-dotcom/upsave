import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta

import sys
from pathlib import Path

def _app_data_dir():
    env = os.environ.get("AGALI_AWAMU_DATA_DIR")
    if env:
        d = Path(env)
    else:
        if getattr(sys, "frozen", False):
            d = Path(sys.executable).parent
        else:
            d = Path(__file__).parent
        if not os.access(d, os.W_OK):
            d = Path.home() / ".agali_awamu"
    d.mkdir(parents=True, exist_ok=True)
    return d

DB_PATH = str(_app_data_dir() / "savings_group.db")

def _hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


def _generate_product_key():
    return secrets.token_urlsafe(24)


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_user(username, password, role='user', company_name='', motto=''):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, company_name, motto, product_key_verified, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username, _hash_password(password), role, company_name, motto, 0, _now_str())
    )
    conn.commit()
    conn.close()


def authenticate_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return None
    if user['password_hash'] != _hash_password(password):
        return None
    return user


def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, created_at FROM users ORDER BY username")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_user(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


def mark_product_key_verified(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET product_key_verified = 1 WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def is_product_key_verified(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_key_verified FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)['product_key_verified'] if row else False


def clear_member_transaction_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM savings")
    cursor.execute("DELETE FROM loans")
    cursor.execute("DELETE FROM repayments")
    cursor.execute("DELETE FROM withdraws")
    conn.commit()
    conn.close()


def delete_all_members_and_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM savings")
    cursor.execute("DELETE FROM loans")
    cursor.execute("DELETE FROM repayments")
    cursor.execute("DELETE FROM withdraws")
    cursor.execute("DELETE FROM deleted_members")
    cursor.execute("DELETE FROM members")
    conn.commit()
    conn.close()


def get_active_product_key():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM product_keys WHERE active = 1 ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def is_product_key_valid(key_value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM product_keys WHERE key = ? AND active = 1", (key_value,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    if row['expires_at']:
        try:
            expires = datetime.strptime(row['expires_at'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return False
        return datetime.now() <= expires
    return True


def create_product_key(permanent=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE product_keys SET active = 0 WHERE active = 1")
    new_key = _generate_product_key()
    expires_at = None if permanent else (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO product_keys (key, created_at, expires_at, active) VALUES (?, ?, ?, 1)",
        (new_key, _now_str(), expires_at)
    )
    conn.commit()
    conn.close()
    return new_key

def get_connection():
    """Returns a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys for this connection
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes the database schema if tables do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Create members table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        join_date TEXT NOT NULL,
        status TEXT DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive'))
    )
    """)
    
    # Create savings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS savings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        date TEXT NOT NULL,
        saving_type TEXT DEFAULT 'Regular' CHECK(saving_type IN ('Regular', 'Welfare', 'Share Purchase', 'Share Purchases', 'Special')),
        FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
    )
    """)


    cursor.execute("""CREATE TABLE IF NOT EXISTS active_week (
    id INTEGER PRIMARY KEY,
    week_name TEXT NOT NULL
)""")
   
   
    # Create loans table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        interest_rate REAL NOT NULL CHECK(interest_rate >= 0),
        term_months INTEGER NOT NULL CHECK(term_months > 0),
        start_date TEXT NOT NULL,
        status TEXT DEFAULT 'Active' CHECK(status IN ('Pending', 'Active', 'Fully Paid', 'Defaulted')),
        FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
    )
    """)
    
    # Create repayments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS repayments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        date TEXT NOT NULL,
        FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE CASCADE
    )
    """)

    # Create deleted_members table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deleted_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_member_id INTEGER,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        deleted_at TEXT NOT NULL
    )
    """)

    # Create withdraws table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS withdraws (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        date TEXT NOT NULL,
        note TEXT,
        FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
    )
    """)

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('developer', 'user')),
        company_name TEXT,
        motto TEXT,
        product_key_verified INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)
    
    # Migration: add new columns if they don't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN company_name TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN motto TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN product_key_verified INTEGER DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE savings ADD COLUMN week_name TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE loans ADD COLUMN week_name TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE withdraws ADD COLUMN week_name TEXT")
    except:
        pass

    # Create product_keys table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        expires_at TEXT,
        active INTEGER NOT NULL DEFAULT 1
    )
    """)
    
    conn.commit()
    conn.close()

def _ensure_default_developer():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'fikmen'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            ('fikmen', _hash_password('matovu)fik12'), 'developer', _now_str())
        )
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'member'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            ('member', _hash_password('member123'), 'user', _now_str())
        )
    cursor.execute("SELECT COUNT(*) FROM product_keys WHERE active = 1")
    if cursor.fetchone()[0] == 0:
        creator = _generate_product_key()
        expires_at = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO product_keys (key, created_at, expires_at, active) VALUES (?, ?, ?, 1)",
            (creator, _now_str(), expires_at)
        )
    conn.commit()
    conn.close()


def ensure_default_developer():
    _ensure_default_developer()


def seed_dummy_data():
    """Seeds the database with some realistic initial data if it's empty."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Ensure developer account and initial product key
    _ensure_default_developer()
    
    # Check if we already have members
    cursor.execute("SELECT COUNT(*) FROM members")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return  # Already seeded
    
    # Sample members
    members_data = [
        ("Alice Nambooze", "+256 701 123456", "alice@example.com", "2026-01-15", "Active"),
        ("Bob Okello", "+256 772 654321", "bob@example.com", "2026-01-20", "Active"),
        ("Charlie Mukasa", "+256 752 987654", "charlie@example.com", "2026-02-10", "Active"),
        ("Diana Kamusiime", "+256 781 112233", "diana@example.com", "2026-02-15", "Active"),
        ("Ethan Ssewankambo", "+256 703 445566", "ethan@example.com", "2026-03-01", "Active")
    ]
    
    cursor.executemany("""
    INSERT INTO members (name, phone, email, join_date, status)
    VALUES (?, ?, ?, ?, ?)
    """, members_data)
    
    # Retrieve member ids
    cursor.execute("SELECT id FROM members")
    member_ids = [row['id'] for row in cursor.fetchall()]
    
    # Sample savings (spanning Jan to June 2026)
    start_date = datetime(2026, 1, 1)
    savings_data = []
    
    # Let's add monthly regular savings of 50,000 UGX (or simply units) for each member
    # Plus some share purchases
    for member_id in member_ids:
        # Save every month
        for month in range(1, 6): # Jan to May
            save_date = (start_date + timedelta(days=30 * (month - 1) + 20)).strftime("%Y-%m-%d")
            savings_data.append((member_id, 100000.0, save_date, "Regular"))
            
        # Add a one-time welfare fee
        savings_data.append((member_id, 250000.0, "2026-02-15", "Welfare"))
        
    cursor.executemany("""
    INSERT INTO savings (member_id, amount, date, saving_type)
    VALUES (?, ?, ?, ?)
    """, savings_data)
    
    # Sample loans
    # Loan for Alice: 500,000, 10% interest, 4 months term, started 2026-02-01
    cursor.execute("""
    INSERT INTO loans (member_id, amount, interest_rate, term_months, start_date, status)
    VALUES (?, 500000.0, 10.0, 4, '2026-02-01', 'Active')
    """, (member_ids[0],))
    alice_loan_id = cursor.lastrowid
    
    # Loan for Bob: 800,000, 12% interest, 6 months term, started 2026-03-10
    cursor.execute("""
    INSERT INTO loans (member_id, amount, interest_rate, term_months, start_date, status)
    VALUES (?, 800000.0, 12.0, 6, '2026-03-10', 'Active')
    """, (member_ids[1],))
    bob_loan_id = cursor.lastrowid
    
    # Sample repayments
    # Alice made repayments in March, April, May
    repayments_data = [
        (alice_loan_id, 137500.0, "2026-03-01"), # Principal + Interest split approx
        (alice_loan_id, 137500.0, "2026-04-01"),
        (alice_loan_id, 137500.0, "2026-05-01"),
        (bob_loan_id, 149333.3, "2026-04-10"),
        (bob_loan_id, 149333.3, "2026-05-10")
    ]
    cursor.executemany("""
    INSERT INTO repayments (loan_id, amount, date)
    VALUES (?, ?, ?)
    """, repayments_data)
    
    conn.commit()
    conn.close()

def get_dashboard_kpis():
    """Retrieves high-level summary KPIs for the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total Savings should be regular savings only, not welfare fees
    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) FROM savings WHERE saving_type = 'Regular'")
    total_regular_savings = cursor.fetchone()[0] or 0.0
    total_withdrawals = get_total_withdraws()
    total_savings = total_regular_savings - total_withdrawals
    
    # Total Active Membersg
    cursor.execute("SELECT COUNT(*) FROM members WHERE status = 'Active'")
    total_members = cursor.fetchone()[0] or 0
    
    # Total Active/Pending Loans (Disbursed principal)
    cursor.execute("SELECT SUM(amount) FROM loans WHERE status = 'Active'")
    active_loans_principal = cursor.fetchone()[0] or 0.0
    
    # Total Repayments collected
    cursor.execute("SELECT SUM(amount) FROM repayments")
    total_repayments = cursor.fetchone()[0] or 0.0
    
    conn.close()
    return {
        "total_savings": total_savings,
        "total_members": total_members,
        "active_loans_principal": active_loans_principal,
        "total_repayments": total_repayments
    }

def get_monthly_savings_data():
    """Retrieves aggregated monthly savings for plotting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%Y-%m', date) as month, SUM(amount) as monthly_total
        FROM savings
        GROUP BY month
        ORDER BY month ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{"month": row["month"], "total": row["monthly_total"]} for row in rows]

def get_savings_by_type():
    """Retrieves savings distribution by type."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT saving_type, SUM(amount) as total
        FROM savings
        GROUP BY saving_type
    """)
    rows = cursor.fetchall()
    conn.close()

    # Normalize legacy/variant names into a single 'Welfare Fees' bucket
    type_totals = {}
    for row in rows:
        stype = row["saving_type"]
        total = row["total"]
        if stype in ("Share Purchase", "Share Purchases", "Welfare"):
            key = "Welfare Fees"
        else:
            key = stype
        type_totals[key] = type_totals.get(key, 0.0) + (total or 0.0)

    return [{"type": k, "total": v} for k, v in type_totals.items()]

def reset_db():
    """Drops all tables to clear the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF;")
    cursor.execute("DROP TABLE IF EXISTS repayments;")
    cursor.execute("DROP TABLE IF EXISTS loans;")
    cursor.execute("DROP TABLE IF EXISTS withdraws;")
    cursor.execute("DROP TABLE IF EXISTS savings;")
    cursor.execute("DROP TABLE IF EXISTS members;")
    cursor.execute("DROP TABLE IF EXISTS users;")
    cursor.execute("DROP TABLE IF EXISTS product_keys;")
    cursor.execute("DROP TABLE IF EXISTS deleted_members;")
    conn.commit()
    conn.close()

def add_member(name, phone, email, join_date, status='Active'):
    """Adds a new member to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO members (name, phone, email, join_date, status)
        VALUES (?, ?, ?, ?, ?)
    """, (name, phone, email, join_date, status))
    conn.commit()
    conn.close()

def get_all_members(search_query=None):
    """Retrieves all members, optionally filtered by a search query on name, phone, or email."""
    conn = get_connection()
    cursor = conn.cursor()
    if search_query:
        cursor.execute("""
            SELECT * FROM members 
            WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
            ORDER BY id ASC
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT * FROM members ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_member(member_id, name, phone, email, status):
    """Updates an existing member's details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE members 
        SET name = ?, phone = ?, email = ?, status = ?
        WHERE id = ?
    """, (name, phone, email, status, member_id))
    conn.commit()
    conn.close()

def add_saving(member_id, amount, date, saving_type='Regular'):
    week_name = get_active_week()
    """Adds a new savings record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO savings (member_id, amount, date, saving_type,week_name)
        VALUES (?, ?, ?, ?,?)
    """, (member_id, amount, date, saving_type,week_name))
    conn.commit()
    conn.close()
 
def get_regular_savings_balance(member_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(
                (SELECT SUM(amount)
                 FROM savings
                 WHERE member_id = ?
                 AND saving_type = 'Regular'),
                0
            )
            -
            COALESCE(
                (SELECT SUM(amount)
                 FROM withdraws
                 WHERE member_id = ?),
                0
            ) AS balance
    """, (member_id, member_id))

    balance = cursor.fetchone()[0]
    conn.close()

    return balance


def add_withdraw(member_id, amount, date, note=None):
    """Records a withdrawal for a member."""
    week_name = get_active_week()
    
    current_balance = get_regular_savings_balance(member_id)
    if amount > current_balance:
        return False, f"Insufficient balance. Available balance is UGX {current_balance:,.0f}"
    else:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO withdraws (member_id, amount, date, note, week_name)
            VALUES (?, ?, ?, ?, ?)
        """, (member_id, amount, date, note, week_name))
        conn.commit()
        conn.close()
        return True, "Withdrawal recorded successfully."
    


def get_all_withdraws(member_id=None):
    """Retrieves all withdrawals, optionally filtered by member."""
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT w.*, m.name as member_name FROM withdraws w JOIN members m ON w.member_id = m.id"
    params = []
    if member_id:
        query += " WHERE w.member_id = ?"
        params.append(member_id)
    query += " ORDER BY w.date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_total_withdraws():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as total FROM withdraws")
    total = cursor.fetchone()[0] or 0.0
    conn.close()
    return total

def get_all_savings(member_id=None, saving_type=None,week_name=None):
    """Retrieves all savings entries, optionally filtered by member_id or saving_type."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT s.*, m.name as member_name 
        FROM savings s
        JOIN members m ON s.member_id = m.id
    """
    params = []
    conditions = []
    if member_id:
        conditions.append("s.member_id = ?")
        params.append(member_id)
    if saving_type:
        # Allow 'Welfare' to match historical 'Share Purchase' variants 
        if saving_type == 'Welfare':
            conditions.append("(s.saving_type = 'Welfare' OR s.saving_type = 'Share Purchase' OR s.saving_type = 'Share Purchases')")
        else:
            conditions.append("s.saving_type = ?")
            params.append(saving_type)

    if week_name:
        conditions.append("s.week_name = ?")
        params.append(week_name)
        
    if conditions: 
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY s.date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_savings_summary_by_member():
    """Retrieves total savings grouped by member."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.id, m.name,
               COALESCE((SELECT SUM(amount) FROM savings WHERE member_id = m.id), 0.0) - COALESCE((SELECT SUM(amount) FROM withdraws WHERE member_id = m.id), 0.0) as total_savings,
               COALESCE((SELECT SUM(amount) FROM savings WHERE member_id = m.id AND saving_type = 'Regular'), 0.0) - COALESCE((SELECT SUM(amount) FROM withdraws WHERE member_id = m.id), 0.0) as regular_savings,
               COALESCE((SELECT SUM(amount) FROM savings WHERE member_id = m.id AND (saving_type = 'Welfare' OR saving_type = 'Share Purchase' OR saving_type = 'Share Purchases')), 0.0) as welfare_fees,
               COALESCE((SELECT SUM(amount) FROM withdraws WHERE member_id = m.id), 0.0) as total_withdrawals
        
        FROM members m
        ORDER BY m.name ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_loan(member_id, amount, interest_rate, term_months, start_date, status='Active'):
    """Adds a new loan record."""
    week_name = get_active_week()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO loans (member_id, amount, interest_rate, term_months, start_date, status, week_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (member_id, amount, interest_rate, term_months, start_date, status, week_name))
    conn.commit()
    conn.close()

def get_all_loans(status=None):
    """Retrieves all loans, optionally filtered by status, and calculates basic repayment statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT l.*, m.name as member_name,
               COALESCE(SUM(r.amount), 0.0) as total_repaid
        FROM loans l
        JOIN members m ON l.member_id = m.id
        LEFT JOIN repayments r ON l.id = r.loan_id
    """
    params = []
    if status:
        query += " WHERE l.status = ?"
        params.append(status)
    
    query += " GROUP BY l.id ORDER BY l.start_date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    loans_list = []
    for row in rows:
        loan = dict(row)
        principal = loan['amount']
        rate = loan['interest_rate']
        total_repayable = principal + (principal * (rate / 100.0))
        loan['total_repayable'] = total_repayable
        loan['remaining_balance'] = max(0.0, total_repayable - loan['total_repaid'])
        loans_list.append(loan)
        
    return loans_list

def add_repayment(loan_id, amount, date):
    """Adds a new repayment record. Automatically marks loan as Fully Paid if balance is cleared."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Insert repayment
    cursor.execute("""
        INSERT INTO repayments (loan_id, amount, date)
        VALUES (?, ?, ?)
    """, (loan_id, amount, date))
    
    # Calculate outstanding balance to see if it's fully paid
    cursor.execute("""
        SELECT amount, interest_rate, 
               (SELECT COALESCE(SUM(amount), 0.0) FROM repayments WHERE loan_id = ?) as total_repaid
        FROM loans WHERE id = ?
    """, (loan_id, loan_id))
    loan_row = cursor.fetchone()
    
    if loan_row:
        principal = loan_row['amount']
        rate = loan_row['interest_rate']
        total_repaid = loan_row['total_repaid']
        total_repayable = principal + (principal * (rate / 100.0))
        
        # If total repaid is >= total repayable, update status to Fully Paid
        if total_repaid >= total_repayable:
            cursor.execute("UPDATE loans SET status = 'Fully Paid' WHERE id = ?", (loan_id,))
            
    conn.commit()
    conn.close()

def get_loan_choices_for_repayment():
    """Returns a list of active/pending loans with member names for a dropdown selection."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.id, l.amount, l.start_date, m.name as member_name
        FROM loans l
        JOIN members m ON l.member_id = m.id
        WHERE l.status IN ('Active', 'Pending', 'Defaulted')
        ORDER BY m.name ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_loan_details(loan_id):
    """Retrieves full details of a specific loan, including its repayment history."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.*, m.name as member_name, m.phone as member_phone, m.email as member_email
        FROM loans l
        JOIN members m ON l.member_id = m.id
        WHERE l.id = ?
    """, (loan_id,))
    loan_row = cursor.fetchone()
    if not loan_row:
        conn.close()
        return None
        
    loan = dict(loan_row)
    
    # Fetch repayments
    cursor.execute("SELECT * FROM repayments WHERE loan_id = ? ORDER BY date DESC", (loan_id,))
    repayments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    principal = loan['amount']
    rate = loan['interest_rate']
    total_repayable = principal + (principal * (rate / 100.0))
    total_repaid = sum(r['amount'] for r in repayments)
    
    loan['repayments'] = repayments
    loan['total_repayable'] = total_repayable
    loan['total_repaid'] = total_repaid
    loan['remaining_balance'] = max(0.0, total_repayable - total_repaid)
    
    return loan

def get_system_reports_data():
    """Generates a summary of all financial stats for every member."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # First, list all members
    cursor.execute("SELECT id, name, status FROM members ORDER BY id ASC")
    members = [dict(row) for row in cursor.fetchall()]
    
    reports_data = []
    for m in members:
        member_id = m['id']
        
        # Total savings
        cursor.execute("SELECT COALESCE(SUM(amount), 0.0) FROM savings WHERE member_id = ?", (member_id,))
        total_savings = cursor.fetchone()[0] or 0.0
        
        # Total loans principal
        cursor.execute("SELECT COALESCE(SUM(amount), 0.0) FROM loans WHERE member_id = ?", (member_id,))
        total_loans_principal = cursor.fetchone()[0] or 0.0
        
        # Total loans repayable & repayments
        cursor.execute("SELECT id, amount, interest_rate FROM loans WHERE member_id = ?", (member_id,))
        loans = cursor.fetchall()
        total_repayable = 0.0
        total_repaid = 0.0
        for loan in loans:
            l_id = loan['id']
            principal = loan['amount']
            rate = loan['interest_rate']
            total_repayable += principal + (principal * (rate / 100.0))
            
            cursor.execute("SELECT COALESCE(SUM(amount), 0.0) FROM repayments WHERE loan_id = ?", (l_id,))
            total_repaid += cursor.fetchone()[0] or 0.0
            
        reports_data.append({
            "member_id": member_id,
            "name": m['name'],
            "status": m['status'],
            "total_savings": total_savings,
            "loans_principal": total_loans_principal,
            "total_repayable": total_repayable,
            "total_repaid": total_repaid,
            "outstanding_balance": max(0.0, total_repayable - total_repaid)
        })
        
    conn.close()
    return reports_data

def delete_member(member_id):
    """Deletes a member from the database, first archiving them to deleted_members, and wipes their data."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Fetch member details
    cursor.execute("SELECT * FROM members WHERE id = ?", (member_id,))
    member = cursor.fetchone()
    if not member:
        conn.close()
        return False
        
    # 2. Archive to deleted_members
    cursor.execute("""
        INSERT INTO deleted_members (original_member_id, name, phone, email, deleted_at)
        VALUES (?, ?, ?, ?, ?)
    """, (member['id'], member['name'], member['phone'], member['email'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    # 3. Delete from members (with cascading deletes enabled via PRAGMA foreign_keys = ON)
    cursor.execute("DELETE FROM members WHERE id = ?", (member_id,))
    
    conn.commit()
    conn.commit()
    conn.close()
    # After deletion, resequence member ids so they remain contiguous
    resequence_member_ids()
    return True

def get_deleted_members():
    """Retrieves all deleted members log."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deleted_members ORDER BY deleted_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def resequence_member_ids():
    """Resequence member IDs to be contiguous starting at 1.
    Updates all child tables that reference member_id accordingly.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # temporarily disable foreign key checks while we remap ids
    cursor.execute("PRAGMA foreign_keys = OFF")

    cursor.execute("SELECT id FROM members ORDER BY id ASC")
    rows = [r['id'] for r in cursor.fetchall()]
    if not rows:
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.close()
        return

    mapping = {}
    for new_idx, old_id in enumerate(rows, start=1):
        mapping[old_id] = new_idx

    # Step 1: set member ids to negative new ids to avoid UNIQUE conflicts
    for old_id, new_id in mapping.items():
        if old_id != new_id:
            cursor.execute("UPDATE members SET id = ? WHERE id = ?", (-new_id, old_id))

    # Step 2: update child tables to use negative new ids where they referenced old ids
    for old_id, new_id in mapping.items():
        if old_id != new_id:
            neg_new = -new_id
            cursor.execute("UPDATE savings SET member_id = ? WHERE member_id = ?", (neg_new, old_id))
            cursor.execute("UPDATE loans SET member_id = ? WHERE member_id = ?", (neg_new, old_id))
            cursor.execute("UPDATE withdraws SET member_id = ? WHERE member_id = ?", (neg_new, old_id))
            cursor.execute("UPDATE deleted_members SET original_member_id = ? WHERE original_member_id = ?", (neg_new, old_id))

    # Step 3: flip negative member ids back to positive
    cursor.execute("UPDATE members SET id = -id WHERE id < 0")
    # Step 4: flip child tables member_id back to positive
    cursor.execute("UPDATE savings SET member_id = -member_id WHERE member_id < 0")
    cursor.execute("UPDATE loans SET member_id = -member_id WHERE member_id < 0")
    cursor.execute("UPDATE withdraws SET member_id = -member_id WHERE member_id < 0")
    cursor.execute("UPDATE deleted_members SET original_member_id = -original_member_id WHERE original_member_id < 0")

    # Reset sqlite_sequence for members to max(id)
    try:
        cursor.execute("SELECT MAX(id) FROM members")
        max_id = cursor.fetchone()[0] or 0
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'members'")
        cursor.execute("INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)", ('members', max_id))
    except Exception:
        pass

    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()

def get_member_activity_timeline(member_id, week_name=None):
    """Retrieves a unified chronological timeline of all activities for a given member."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # We query:
    # 1. Member registration
    # 2. Savings contributions
    # 3. Loans disbursed
    # 4. Loan repayments
    query = """
        SELECT type, date, details, amount, week_name FROM (
            SELECT 'Registration' AS type, join_date AS date, 'Joined Agali Awamu Savings Group' AS details, NULL AS amount, NULL AS week_name, id AS member_id
            FROM members
            UNION ALL
            SELECT 'Saving' AS type, date, 'Contribution Type: ' || saving_type AS details, amount, week_name, member_id
            FROM savings
            UNION ALL
            SELECT 'Loan Disbursed' AS type, start_date AS date, 'Principal amount disbursed at ' || interest_rate || '% interest for ' || term_months || ' months' AS details, amount, week_name, member_id
            FROM loans
            UNION ALL
            SELECT 'Repayment' AS type, r.date AS date, 'Paid towards Loan ID: ' || l.id AS details, r.amount, NULL AS week_name, l.member_id
            FROM repayments r
            JOIN loans l ON r.loan_id = l.id
        )
        WHERE member_id = ?
    """
    params = [member_id]
    if week_name:
        query += " AND week_name = ?"
        params.append(week_name)
        
    query += " ORDER BY date DESC, type ASC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_weeks():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT week_name
        FROM (
            SELECT week_name FROM savings
            UNION
            SELECT week_name FROM withdraws
            UNION
            SELECT week_name FROM loans
        )
        WHERE week_name IS NOT NULL
        ORDER BY week_name
    """)

    weeks = [row["week_name"] for row in cursor.fetchall()]

    conn.close()

    return weeks

def set_active_week(week_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE active_week
        SET week_name = ?
        WHERE id = 1
    """, (week_name,))

    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO active_week (id, week_name)
            VALUES (1, ?)
        """, (week_name,))

    conn.commit()
    conn.close()

def increment_week():
    current = get_active_week()  # e.g. "Week 12"

    week_num = int(current.split()[-1])

    set_active_week(f"Week {week_num + 1}")

def get_active_week():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT week_name
        FROM active_week
        WHERE id = 1
    """)

    row = cursor.fetchone()

    conn.close()

    if row:
        return row["week_name"]
    return "Week 1"

def get_savings_by_week(week_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.name,
               COALESCE((SELECT SUM(amount) FROM savings WHERE member_id = m.id AND week_name = ?), 0.0) AS total_savings,
               COALESCE((SELECT SUM(amount) FROM savings WHERE member_id = m.id AND saving_type = 'Welfare' AND week_name = ?), 0.0) AS welfare_savings,
               COALESCE((SELECT SUM(amount) FROM savings WHERE member_id = m.id AND saving_type = 'Share Purchase' AND week_name = ?), 0.0) AS share_purchase_savings,
               COALESCE((SELECT SUM(amount) FROM savings WHERE member_id = m.id AND saving_type = 'Share Purchases' AND week_name = ?), 0.0) AS share_purchases_savings
        FROM members m
        ORDER BY m.name
    """, (week_name, week_name, week_name, week_name))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


