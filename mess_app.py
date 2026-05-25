import sqlite3
from datetime import date

import pandas as pd
import streamlit as st


DB = "manage_mess.db"
MIN_MEALS = 40


conn = sqlite3.connect(DB, check_same_thread=False)
cur = conn.cursor()


cur.execute("""
CREATE TABLE IF NOT EXISTS members(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    deposit REAL,
    water_bill REAL,
    establishment REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS meals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_name TEXT,
    meal_date TEXT,
    lunch INTEGER,
    dinner INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS expenses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT,
    expense_date TEXT,
    amount REAL
)
""")

conn.commit()


def query(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


def run(sql, params=()):
    cur.execute(sql, params)
    conn.commit()


def names():
    df = query("SELECT name FROM members ORDER BY name")
    return df["name"].tolist()


st.set_page_config(page_title="Mess Management", layout="wide")

st.title("Mess Management")
st.caption("Members, meals, expenses, monthly report, and CSV export")

tab1, tab2, tab3, tab4 = st.tabs(["Members", "Meals", "Expenses", "Monthly Report"])


with tab1:
    st.subheader("Member Management")

    with st.form("member_form"):
        c1, c2, c3, c4 = st.columns(4)

        name = c1.text_input("Name")
        deposit = c2.number_input("Deposit", min_value=0.0)
        water = c3.number_input("Water Bill", min_value=0.0)
        establishment = c4.number_input("Establishment", min_value=0.0)

        add = st.form_submit_button("Add Member")

        if add:
            if name.strip():
                run(
                    "INSERT INTO members(name, deposit, water_bill, establishment) VALUES (?, ?, ?, ?)",
                    (name.strip(), deposit, water, establishment)
                )
                st.success("Member added successfully.")
            else:
                st.error("Enter member name.")

    members_df = query("SELECT * FROM members ORDER BY id DESC")
    st.dataframe(members_df, use_container_width=True)

    delete_id = st.number_input("Delete Member ID", min_value=0, step=1)

    if st.button("Delete Member"):
        run("DELETE FROM members WHERE id=?", (delete_id,))
        st.success("Member deleted. Refresh page if table does not update immediately.")


with tab2:
    st.subheader("Meal Entry")

    member_list = names()

    with st.form("meal_form"):
        c1, c2, c3, c4 = st.columns(4)

        member = c1.selectbox("Member", member_list)
        meal_date = c2.date_input("Date", value=date.today())
        lunch = c3.checkbox("Lunch")
        dinner = c4.checkbox("Dinner")

        add_meal = st.form_submit_button("Add Meal")

        if add_meal:
            if not member:
                st.error("Add member first.")
            elif not lunch and not dinner:
                st.error("Select lunch or dinner.")
            else:
                exists = query(
                    "SELECT id FROM meals WHERE member_name=? AND meal_date=?",
                    (member, str(meal_date))
                )

                if not exists.empty:
                    st.error("Meal already added for this member on this date.")
                else:
                    run(
                        "INSERT INTO meals(member_name, meal_date, lunch, dinner) VALUES (?, ?, ?, ?)",
                        (member, str(meal_date), int(lunch), int(dinner))
                    )
                    st.success("Meal added successfully.")

    meals_df = query("SELECT * FROM meals ORDER BY meal_date DESC, id DESC")
    st.dataframe(meals_df, use_container_width=True)

    delete_meal_id = st.number_input("Delete Meal ID", min_value=0, step=1)

    if st.button("Delete Meal"):
        run("DELETE FROM meals WHERE id=?", (delete_meal_id,))
        st.success("Meal deleted.")


with tab3:
    st.subheader("Expense Entry")

    with st.form("expense_form"):
        c1, c2, c3 = st.columns(3)

        item = c1.text_input("Expense Item")
        expense_date = c2.date_input("Expense Date", value=date.today())
        amount = c3.number_input("Amount", min_value=0.0)

        add_expense = st.form_submit_button("Add Expense")

        if add_expense:
            if item.strip() and amount > 0:
                run(
                    "INSERT INTO expenses(item, expense_date, amount) VALUES (?, ?, ?)",
                    (item.strip(), str(expense_date), amount)
                )
                st.success("Expense added successfully.")
            else:
                st.error("Enter item and valid amount.")

    expenses_df = query("SELECT * FROM expenses ORDER BY expense_date DESC, id DESC")
    st.dataframe(expenses_df, use_container_width=True)

    delete_expense_id = st.number_input("Delete Expense ID", min_value=0, step=1)

    if st.button("Delete Expense"):
        run("DELETE FROM expenses WHERE id=?", (delete_expense_id,))
        st.success("Expense deleted.")


with tab4:
    st.subheader("Monthly Final Report")

    c1, c2 = st.columns(2)
    month = c1.selectbox("Month", [f"{i:02d}" for i in range(1, 13)], index=date.today().month - 1)
    year = c2.text_input("Year", value=str(date.today().year))

    prefix = f"{year}-{month}"

    total_expense = query(
        "SELECT SUM(amount) AS total FROM expenses WHERE expense_date LIKE ?",
        (prefix + "%",)
    )["total"][0] or 0

    members = query("SELECT * FROM members ORDER BY name")

    report = []
    total_effective_meals = 0

    for _, m in members.iterrows():
        meals = query(
            "SELECT SUM(lunch + dinner) AS meals FROM meals WHERE member_name=? AND meal_date LIKE ?",
            (m["name"], prefix + "%")
        )["meals"][0] or 0

        effective = max(meals, MIN_MEALS)
        total_effective_meals += effective

        report.append({
            "Name": m["name"],
            "Deposit": m["deposit"],
            "Gross Meals": meals,
            "Effective Meals": effective,
            "Water Bill": m["water_bill"],
            "Establishment": m["establishment"]
        })

    meal_rate = total_expense / total_effective_meals if total_effective_meals else 0

    final_report = []

    for row in report:
        meal_expense = row["Effective Meals"] * meal_rate
        final_total = meal_expense + row["Water Bill"] + row["Establishment"]
        balance = row["Deposit"] - final_total

        if balance > 0:
            status = f"will receive Rs {balance:.2f}"
        elif balance < 0:
            status = f"will give Rs {abs(balance):.2f}"
        else:
            status = "Settled"

        final_report.append({
            **row,
            "Meal Expense": round(meal_expense, 2),
            "Final Total": round(final_total, 2),
            "Balance": round(balance, 2),
            "Status": status
        })

    st.metric("Total Expense", f"Rs {total_expense:.2f}")
    st.metric("Total Effective Meals", total_effective_meals)
    st.metric("Meal Rate", f"Rs {meal_rate:.2f}")

    report_df = pd.DataFrame(final_report)
    st.dataframe(report_df, use_container_width=True)

    csv = report_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download CSV Report",
        csv,
        file_name=f"Final_Mess_Report_{month}_{year}.csv",
        mime="text/csv"
    )
