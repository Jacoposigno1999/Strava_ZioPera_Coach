import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
import numpy as np

load_dotenv()


# -----------------------------------
# DB CONNECTION 
# -----------------------------------
def get_engine():
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")

    # postgresql+psycopg2://user:password@host:port/dbname
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)

# -----------------------------------
# QUERY: daily running distance
# -----------------------------------
def load_daily_running_distance():
    """
    Returns a DataFrame with:
      - day: date of the activity
      - km: total distance run that day (in kilometers)
    """
    sql = text("""
        SELECT
            DATE(start_date_local) AS day,
            SUM(distance_m) / 1000.0 AS km
        FROM activities
        WHERE LOWER(type) LIKE :pattern
        GROUP BY day
        ORDER BY day;
    """)
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql_query(sql, conn, params={"pattern": "%run%"})
    return df


# -----------------------------------
# PLOT FUNCTION
# -----------------------------------
def plot_daily_running_distance(df, cumulative: bool = False):
    """
    Plots the evolution of running distance over time.
    x-axis: date
    y-axis: km (daily or cumulative)
    """
    if df.empty:
        print("No data to plot.")
        return

    plot_df = df.copy()

    if cumulative:
        plot_df["km"] = plot_df["km"].cumsum()

 # --- FIGURE STYLE ---
    plt.style.use("ggplot")  # clean baseline

    fig, ax = plt.subplots(figsize=(12, 6), dpi=120)

    # Strava-like orange
    color = "#FC4C02"

    # Smoother line via interpolation (optional)
    x = plot_df["day"]
    y = plot_df["km"]

    # Convert dates to numeric for interpolation
    x_num = mdates.date2num(x)

    ax.plot(
        x,
        y,
        color=color,
        linewidth=2.4,
        marker="o",
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=1.5,
        markeredgecolor=color,
    )

    # --- TITLES AND LABELS ---
    title = "Cumulative Running Distance" if cumulative else "Daily Running Distance"
    ax.set_title(
        title,
        fontsize=20,
        fontweight="bold",
        pad=20
    )

    ax.set_xlabel("Date", fontsize=14)
    ax.set_ylabel("Kilometers", fontsize=14)

    # --- GRID & AXES ---
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)

    # Dynamic date formatting
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    plt.xticks(rotation=45, fontsize=10)
    plt.yticks(fontsize=12)

    # Add padding
    plt.tight_layout()

    # Show final plot
    plt.show()

    
    
# -----------------------------------
# MAIN
# -----------------------------------
if __name__ == "__main__":
    df = load_daily_running_distance()

    # 1) Daily distance
    plot_daily_running_distance(df, cumulative=False)