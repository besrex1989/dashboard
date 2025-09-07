@app.route("/dashboard")
def dashboard():
    import pandas as pd
    import calendar

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user = session.get("user")
    role = session.get("role")

    # -------------------- Filter/Zeitraum einlesen -------------------------
    filter_typ = request.args.get("filter") or "monat"
    jahr_str = request.args.get("jahr") or datetime.now().strftime("%Y")
    monat_str = request.args.get("monat") or datetime.now().strftime("%m")  # optionaler Monatswechsel via Query

    # Hilfsfunktion: letzten Tag eines Monats bestimmen
    def _last_day_of_month(year_int: int, month_int: int) -> int:
        return calendar.monthrange(year_int, month_int)[1]

    # Start/End als Strings im Format DD.MM.YYYY vorbereiten
    jahr_int = int(jahr_str)
    monat_int = int(monat_str)

    if filter_typ == "monat":
        last_day = _last_day_of_month(jahr_int, monat_int)
        start = f"01.{monat_int:02d}.{jahr_int}"
        end   = f"{last_day:02d}.{monat_int:02d}.{jahr_int}"
    elif filter_typ == "jahres":
        start, end = f"01.01.{jahr_int}", f"31.12.{jahr_int}"
    elif filter_typ == "quartal1":
        start, end = f"01.01.{jahr_int}", f"31.03.{jahr_int}"
    elif filter_typ == "quartal2":
        start, end = f"01.04.{jahr_int}", f"30.06.{jahr_int}"
    elif filter_typ == "quartal3":
        start, end = f"01.07.{jahr_int}", f"30.09.{jahr_int}"
    elif filter_typ == "quartal4":
        start, end = f"01.10.{jahr_int}", f"31.12.{jahr_int}"
    elif filter_typ == "custom":
        start = request.args.get("start") or datetime.now().strftime("%d.%m.%Y")
        end   = request.args.get("end")   or datetime.now().strftime("%d.%m.%Y")
    else:
        # Unbekannter Filter → sicherer Fallback auf aktuellen Monat
        last_day = _last_day_of_month(datetime.now().year, datetime.now().month)
        start = f"01.{datetime.now().month:02d}.{datetime.now().year}"
        end   = f"{last_day:02d}.{datetime.now().month:02d}.{datetime.now().year}"
        filter_typ = "monat"
        jahr_str = str(datetime.now().year)
        jahr_int = int(jahr_str)
        monat_str = f"{datetime.now().month:02d}"
        monat_int = int(monat_str)

    # -------------------- Daten laden & parsen -----------------------------
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM umsatz", conn)
    conn.close()

    # Datumsspalte robust parsen; ungültige Zeilen verwerfen
    df["Datum"] = pd.to_datetime(df["datum"], format="%d.%m.%Y", errors="coerce")
    df = df.dropna(subset=["Datum"])

    # Start/End einmalig parsen; Fallback auf Monatsrange bei Fehlern/Vertauschung
    start_dt = pd.to_datetime(start, dayfirst=True, errors="coerce")
    end_dt   = pd.to_datetime(end,   dayfirst=True, errors="coerce")
    if pd.isna(start_dt) or pd.isna(end_dt) or end_dt < start_dt:
        last_day = _last_day_of_month(jahr_int, monat_int)
        start_dt = pd.to_datetime(f"01.{monat_int:02d}.{jahr_int}", dayfirst=True)
        end_dt   = pd.to_datetime(f"{last_day:02d}.{monat_int:02d}.{jahr_int}", dayfirst=True)
        # Strings konsistent halten für Template
        start = start_dt.strftime("%d.%m.%Y")
        end   = end_dt.strftime("%d.%m.%Y")
        filter_typ = "monat"

    # -------------------- Auswertungen -------------------------------------
    stats = []
    last_entries = []
    monthly = {r: [0]*12 for r in RESTAURANTS}

    for r in RESTAURANTS:
        # Input-User sehen nur ihr Restaurant
        if role == "input" and session.get("restaurant") != r:
            continue

        df_r = df[df["restaurant"] == r]

        # Zeitraum-Summe (einheitliche, vorgeparste Grenzen)
        dfF = df_r[df_r["Datum"].between(start_dt, end_dt, inclusive="both")]
        total_summe = round(dfF["total"].sum(), 2) if not dfF.empty else 0.0
        stats.append([r, total_summe])

        # letztes Datum/Eintrag je Restaurant
        if not df_r.empty:
            l = df_r.sort_values("Datum", ascending=False).iloc[0]
            last_entries.append((r, l["datum"], l["total"]))
        else:
            last_entries.append((r, "-", 0.0))

        # Monatsentwicklung fürs ausgewählte Jahr
        for m in range(1, 13):
            last_day_m = _last_day_of_month(jahr_int, m)
            st = pd.to_datetime(f"01.{m:02d}.{jahr_int}", dayfirst=True)
            en = pd.to_datetime(f"{last_day_m:02d}.{m:02d}.{jahr_int}", dayfirst=True)
            sub = df_r[df_r["Datum"].between(st, en, inclusive="both")]
            monthly[r][m-1] = round(sub["total"].sum(), 2) if not sub.empty else 0.0

    gesamt = round(sum(row[1] for row in stats), 2)
    jahresliste = [str(y) for y in range(2023, 2031)]

    # -------------------- Render -------------------------------------------
    return render_template(
        "dashboard.html",
        stats=stats,
        gesamt=gesamt,
        year=jahr_str,
        filter=filter_typ,
        jahre=jahresliste,
        jahr_selected=jahr_str,
        start=start,
        end=end,
        user=user,
        last_entries=last_entries,
        monthly=monthly
    )
