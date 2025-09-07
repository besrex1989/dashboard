from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "geheim123"

DB_FILE = "umsatz.db"

# ================= DB Initialisierung ======================================

def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE umsatz (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant TEXT,
                datum TEXT,
                total REAL,
                bar REAL,
                kartenterminal REAL,
                twint REAL,
                amex REAL,
                debitoren REAL,
                eatch REAL,
                reka REAL,
                sonstige REAL,
                user TEXT
            )
        """)
        conn.commit()
        conn.close()

init_db()

# ================= Benutzer ===============================================

USERS = {
    "admin_sebastiano": {"password": "admin!2025", "role": "super", "restaurant": None},
    "La_Vita": {"password": "1234", "role": "input", "restaurant": "Restaurant La Vita"},
    "La_Gioia": {"password": "1234", "role": "input", "restaurant": "Restaurant La Gioia"},
    "Celina": {"password": "1234", "role": "input", "restaurant": "Restaurant Celina"},
    "Lido": {"password": "1234", "role": "input", "restaurant": "Restaurant Lido"},
    "Da_Vito": {"password": "1234", "role": "input", "restaurant": "Restaurant da Vito"},
}

RESTAURANTS = [
    "Restaurant La Vita",
    "Restaurant La Gioia",
    "Restaurant Celina",
    "Restaurant Lido",
    "Restaurant da Vito"
]


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        if u in USERS and USERS[u]["password"] == p:
            session["logged_in"] = True
            session["user"] = u
            session["role"] = USERS[u]["role"]
            session["restaurant"] = USERS[u]["restaurant"]
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Falscher Login")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ====================== Formular ==========================================

@app.route("/form", methods=["GET", "POST"])
def form():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    role = session.get("role")
    user = session.get("user")
    rfix = session.get("restaurant")

    restaurants = RESTAURANTS if role == "super" else [rfix]

    if request.method == "POST":
        rest = request.form["restaurant"]
        now = datetime.now()
        datum = now.strftime("%d.%m.%Y")

        # Umsatzfelder
        total = float(request.form.get("total") or 0)
        bar = float(request.form.get("bar") or 0)
        kart = float(request.form.get("kartenterminal") or 0)
        twint = float(request.form.get("twint") or 0)
        amex = float(request.form.get("amex") or 0)
        deb = float(request.form.get("debitoren") or 0)
        eatch = float(request.form.get("eatch") or 0)
        reka = float(request.form.get("reka") or 0)
        sonst = float(request.form.get("sonstige") or 0)

        if round(bar+kart+twint+amex+deb+eatch+reka+sonst,2) != round(total,2):
            return "Fehler bei Zahlungsarten"

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
         INSERT INTO umsatz (restaurant, datum, total, bar, kartenterminal, twint, amex, debitoren, eatch, reka, sonstige, user)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (rest, datum, total, bar, kart, twint, amex, deb, eatch, reka, sonst, user))
        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("form.html", restaurants=restaurants, user=user)


# ======================= Dashboard =========================================

@app.route("/dashboard")
def dashboard():
    import pandas as pd
    import calendar

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user = session.get("user")
    role = session.get("role")

    # Filter
    filter = request.args.get("filter") or "monat"
    jahr = request.args.get("jahr") or datetime.now().strftime("%Y")
    monat = datetime.now().strftime("%m")

    if filter == "monat":
        start = f"01.{monat}.{jahr}"
        end = f"31.{monat}.{jahr}"
    elif filter == "jahres":
        start, end = f"01.01.{jahr}", f"31.12.{jahr}"
    elif filter == "quartal1":
        start, end = f"01.01.{jahr}", f"31.03.{jahr}"
    elif filter == "quartal2":
        start, end = f"01.04.{jahr}", f"30.06.{jahr}"
    elif filter == "quartal3":
        start, end = f"01.07.{jahr}", f"30.09.{jahr}"
    elif filter == "quartal4":
        start, end = f"01.10.{jahr}", f"31.12.{jahr}"
    elif filter == "custom":
        start = request.args.get("start") or datetime.now().strftime("%d.%m.%Y")
        end = request.args.get("end") or datetime.now().strftime("%d.%m.%Y")

    # Daten laden
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM umsatz", conn)
    conn.close()

    df["Datum"] = pd.to_datetime(df["datum"], format="%d.%m.%Y")

    stats = []
    last_entries = []
    monthly = {r: [0]*12 for r in RESTAURANTS}

    for r in RESTAURANTS:
        if role == "input" and session.get("restaurant") != r:
            continue

        df_r = df[df["restaurant"] == r]

        # Zeitraum-Summe
        mask = (df_r["Datum"] >= pd.to_datetime(start, dayfirst=True)) & (df_r["Datum"] <= pd.to_datetime(end, dayfirst=True))
        dfF = df_r[mask]
        total_summe = round(dfF["total"].sum(), 2) if not dfF.empty else 0
        stats.append([r, total_summe])

        # letztes Datum
        if not df_r.empty:
            l = df_r.sort_values("Datum", ascending=False).iloc[0]
            last_entries.append((r, l["datum"], l["total"]))
        else:
            last_entries.append((r, "-", 0))

        # Monatsentwicklung
        for m in range(1, 12+1):
            st = f"01.{m:02d}.{jahr}"
            ld = calendar.monthrange(int(jahr), m)[1]
            en = f"{ld:02d}.{m:02d}.{jahr}"
            sub = df_r[(df_r["Datum"] >= pd.to_datetime(st, dayfirst=True)) & (df_r["Datum"] <= pd.to_datetime(en, dayfirst=True))]
            monthly[r][m-1] = round(sub["total"].sum(), 2) if not sub.empty else 0

    gesamt = sum([row[1] for row in stats])
    jahresliste = [str(y) for y in range(2023, 2031)]

    return render_template("dashboard.html", stats=stats, gesamt=gesamt,
                           year=jahr, filter=filter, jahre=jahresliste,
                           jahr_selected=jahr, start=start, end=end,
                           user=user, last_entries=last_entries, monthly=monthly)

# ================= MAIN ====================================================

if __name__ == "__main__":
    app.run(debug=True)
