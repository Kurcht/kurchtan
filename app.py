from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secret"
DB = "database.db"


# =========================
# DATABASE INIT
# =========================
def init_db():
    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            password TEXT,
            balance REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS loan_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client TEXT,
            loan_id INTEGER,
            month INTEGER,
            payment REAL,
            principal REAL,
            interest REAL,
            paid INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            receiver TEXT,
            amount REAL,
            fee REAL,
            time TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client TEXT,
            amount REAL,
            months INTEGER,
            status TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL
        )
    """)

    cur.execute("SELECT COUNT(*) FROM clients")

    if cur.fetchone()[0] == 0:
        users = [
            ("Ali", "admin", 20),
            ("Aika", "admin", 20),
            ("Nurs", "admin", 20),
            ("Dana", "admin", 20),
            ("Erik", "admin", 20),
            ("Mira", "admin", 20),
            ("Samat", "admin", 20),
            ("Lina", "admin", 20),
            ("Azamat", "admin", 20),
            ("Aruzhan", "admin", 20),
        ]

        cur.executemany(
            "INSERT INTO clients (name,password,balance) VALUES (?,?,?)",
            users
        )

    conn.commit()
    conn.close()


# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]

        conn = sqlite3.connect(DB, timeout=10)
        cur = conn.cursor()

        cur.execute(
            "SELECT name FROM clients WHERE name=? AND password=?",
            (name, password)
        )

        user = cur.fetchone()

        conn.close()

        if user:
            session["user"] = user[0]
            return redirect("/client")

    return render_template("login.html")


# =========================
# CLIENT PAGE
# =========================
@app.route("/client")
def client():
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute(
        "SELECT name, balance FROM clients WHERE name=?",
        (session["user"],)
    )
    user = cur.fetchone()

    cur.execute(
        "SELECT name FROM clients WHERE name != ?",
        (session["user"],)
    )
    others = [x[0] for x in cur.fetchall()]

    cur.execute("""
        SELECT sender, receiver, amount, fee, time
        FROM transactions
        WHERE sender=? OR receiver=?
        ORDER BY id DESC
    """, (session["user"], session["user"]))

    history = cur.fetchall()

    cur.execute("""
        SELECT id, amount, status
        FROM loans
        WHERE client=?
    """, (session["user"],))

    loans = cur.fetchall()

    cur.execute("""
        SELECT loan_id, month, payment, principal, interest, paid
        FROM loan_schedule
        WHERE client=?
        ORDER BY loan_id, month
    """, (session["user"],))

    schedule = cur.fetchall()

    conn.close()

    return render_template(
        "client.html",
        user=user,
        others=others,
        history=history,
        loans=loans,
        schedule=schedule
    )


# =========================
# TRANSFER
# =========================
@app.route("/transfer", methods=["POST"])
def transfer():
    sender = session["user"]
    receiver = request.form["receiver"]
    amount = float(request.form["amount"])

    fee = amount * 0.001
    total = amount + fee

    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute("SELECT balance FROM clients WHERE name=?", (sender,))
    bal = cur.fetchone()[0]

    if bal >= total:
        cur.execute(
            "UPDATE clients SET balance = balance - ? WHERE name=?",
            (total, sender)
        )

        cur.execute(
            "UPDATE clients SET balance = balance + ? WHERE name=?",
            (amount, receiver)
        )

        cur.execute("""
            INSERT INTO transactions (sender, receiver, amount, fee, time)
            VALUES (?,?,?,?,datetime('now'))
        """, (sender, receiver, amount, fee))

        cur.execute(
            "INSERT INTO fees (amount) VALUES (?)",
            (fee,)
        )

    conn.commit()
    conn.close()

    return redirect("/client")


# =========================
# LOAN REQUEST
# =========================
@app.route("/loan_request", methods=["POST"])
def loan_request():
    user = session["user"]
    amount = float(request.form["amount"])
    months = int(request.form["months"])

    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE sender=?
    """, (user,))

    count = cur.fetchone()[0]

    if count > 3:
        status = "active"

        cur.execute(
            "UPDATE clients SET balance = balance + ? WHERE name=?",
            (amount, user)
        )
    else:
        status = "rejected"

    cur.execute("""
        INSERT INTO loans (client, amount, months, status)
        VALUES (?,?,?,?)
    """, (user, amount, months, status))

    conn.commit()
    conn.close()

    return redirect("/client")


# =========================
# PAY LOAN
# =========================
@app.route("/pay_loan", methods=["POST"])
def pay_loan():
    user = session["user"]
    loan_id = request.form["loan_id"]

    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute("""
        SELECT amount, status
        FROM loans
        WHERE id=? AND client=?
    """, (loan_id, user))

    loan = cur.fetchone()

    if loan:
        amount, status = loan

        if status == "active":

            cur.execute("""
                SELECT balance
                FROM clients
                WHERE name=?
            """, (user,))

            balance = cur.fetchone()[0]

            if balance >= amount:

                cur.execute("""
                    UPDATE clients
                    SET balance = balance - ?
                    WHERE name=?
                """, (amount, user))

                cur.execute("""
                    UPDATE loans
                    SET status='closed'
                    WHERE id=?
                """, (loan_id,))

                cur.execute("""
                    UPDATE loan_schedule
                    SET paid=1
                    WHERE loan_id=?
                """, (loan_id,))

    conn.commit()
    conn.close()

    return redirect("/client")


# =========================
# LOAN DETAIL
# =========================
@app.route("/loan/<int:loan_id>")
def loan_detail(loan_id):
    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, amount, months, status
        FROM loans
        WHERE id=?
    """, (loan_id,))

    loan = cur.fetchone()

    monthly_payment = round(loan[1] / loan[2], 2)

    conn.close()

    return render_template(
        "loan_detail.html",
        loan=loan,
        monthly_payment=monthly_payment
    )


# =========================
# PAY MONTH
# =========================
@app.route("/pay_month", methods=["POST"])
def pay_month():
    user = session["user"]
    loan_id = request.form["loan_id"]

    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT amount, months
            FROM loans
            WHERE id=?
        """, (loan_id,))

        loan = cur.fetchone()

        if loan:
            amount, months = loan
            monthly_payment = amount / months

            cur.execute("""
                SELECT balance
                FROM clients
                WHERE name=?
            """, (user,))

            balance = cur.fetchone()[0]

            if balance >= monthly_payment:

                cur.execute("""
                    UPDATE clients
                    SET balance = balance - ?
                    WHERE name=?
                """, (monthly_payment, user))

                cur.execute("""
                    UPDATE loan_schedule
                    SET paid=1
                    WHERE loan_id=?
                    AND paid=0
                """, (loan_id,))

        conn.commit()

    finally:
        conn.close()

    return redirect("/client")


# =========================
# CLOSE LOAN
# =========================
@app.route("/close_loan", methods=["POST"])
def close_loan():
    user = session["user"]
    loan_id = request.form["loan_id"]

    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT amount
            FROM loans
            WHERE id=?
        """, (loan_id,))

        loan = cur.fetchone()

        if loan:
            amount = loan[0]

            cur.execute("""
                SELECT balance
                FROM clients
                WHERE name=?
            """, (user,))

            balance = cur.fetchone()[0]

            if balance >= amount:

                cur.execute("""
                    UPDATE clients
                    SET balance = balance - ?
                    WHERE name=?
                """, (amount, user))

                cur.execute("""
                    UPDATE loans
                    SET status='closed'
                    WHERE id=?
                """, (loan_id,))

                cur.execute("""
                    UPDATE loan_schedule
                    SET paid=1
                    WHERE loan_id=?
                """, (loan_id,))

        conn.commit()

    finally:
        conn.close()

    return redirect("/client")


# =========================
# ADMIN
# =========================
@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute("SELECT * FROM clients")
    clients = cur.fetchall()

    cur.execute("SELECT * FROM transactions ORDER BY id DESC")
    transactions = cur.fetchall()

    cur.execute("SELECT * FROM loans")
    loans = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM transactions")
    total_transfers = cur.fetchone()[0] or 0

    cur.execute("SELECT COALESCE(SUM(amount),0) FROM transactions")
    volume = cur.fetchone()[0] or 0

    cur.execute("SELECT COALESCE(AVG(balance),0) FROM clients")
    avg_balance = cur.fetchone()[0] or 0

    cur.execute("SELECT COALESCE(SUM(amount),0) FROM fees")
    fee_income = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT sender, COUNT(*)
        FROM transactions
        GROUP BY sender
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """)

    top_client = cur.fetchone()

    cur.execute("""
        SELECT sender, COUNT(*)
        FROM transactions
        GROUP BY sender
        HAVING COUNT(*) > 3
    """)

    risk_clients = cur.fetchall()

    cur.execute("""
        SELECT sender, COUNT(*)
        FROM transactions
        GROUP BY sender
    """)

    tx = cur.fetchall() or []

    tx_labels, tx_values = [], []

    for x in tx:
        if x and x[0] is not None:
            tx_labels.append(str(x[0]))
            tx_values.append(int(x[1]) if x[1] else 0)

    cur.execute("""
        SELECT name, balance
        FROM clients
    """)

    bal = cur.fetchall() or []

    bal_labels, bal_values = [], []

    for x in bal:
        if x and x[0] is not None:
            bal_labels.append(str(x[0]))
            bal_values.append(float(x[1]) if x[1] else 0)

    cur.execute("""
        SELECT time, SUM(fee)
        FROM transactions
        GROUP BY time
    """)

    fee = cur.fetchall() or []

    fee_labels, fee_values = [], []

    for x in fee:
        if x and x[0] is not None:
            fee_labels.append(str(x[0]))
            fee_values.append(float(x[1]) if x[1] else 0)

    conn.close()

    return render_template(
        "admin.html",
        clients=clients,
        transactions=transactions,
        loans=loans,
        total_transfers=total_transfers,
        volume=volume,
        avg_balance=avg_balance,
        fee_income=fee_income,
        top_client=top_client,
        risk_clients=risk_clients,
        tx_labels=tx_labels,
        tx_values=tx_values,
        bal_labels=bal_labels,
        bal_values=bal_values,
        fee_labels=fee_labels,
        fee_values=fee_values
    )


# =========================
# CLIENT DETAIL (ADMIN)
# =========================
@app.route("/client_detail/<name>")
def client_detail(name):
    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute(
        "SELECT name, balance FROM clients WHERE name=?",
        (name,)
    )
    user = cur.fetchone()

    cur.execute("""
        SELECT sender, receiver, amount, fee, time
        FROM transactions
        WHERE sender=? OR receiver=?
        ORDER BY id DESC
    """, (name, name))

    history = cur.fetchall()

    cur.execute("""
        SELECT id, amount, status
        FROM loans
        WHERE client=?
    """, (name,))

    loans = cur.fetchall()

    conn.close()

    return render_template(
        "client_detail.html",
        user=user,
        history=history,
        loans=loans
    )


# =========================
# SUSPICIOUS
# =========================
@app.route("/suspicious")
def suspicious():
    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()

    cur.execute("""
        SELECT sender, receiver, amount, fee, time
        FROM transactions
        WHERE amount >= 15
        ORDER BY id DESC
    """)

    data = cur.fetchall()

    conn.close()

    return render_template(
        "suspicious.html",
        transfers=data
    )


# =========================
# RUN
# =========================
if __name__ == "__main__":
    init_db()
    app.run(debug=True, threaded=False)