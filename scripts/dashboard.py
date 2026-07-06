import json
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Fintech AI Guard Dashboard", layout="wide")
st.title("Fintech AI Guard Metrics Dashboard")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "raw"

@st.cache_data
def load_data():
    data = []
    if not REPORTS_DIR.exists():
        return pd.DataFrame()
        
    for json_file in sorted(REPORTS_DIR.glob("*.json")):
        with open(json_file, "r") as f:
            try:
                run_data = json.load(f)
                stats = run_data.get("results", {}).get("stats", {})
                
                # Mock extraction - adapt based on real promptfoo output structure
                row = {
                    "Run ID": json_file.stem,
                    "Total Scenarios": stats.get("total", 0),
                    "Passes": stats.get("successes", 0),
                    "Failures": stats.get("failures", 0),
                    "Pass Rate (%)": (stats.get("successes", 0) / max(1, stats.get("total", 0))) * 100
                }
                data.append(row)
            except Exception as e:
                st.error(f"Error parsing {json_file.name}: {e}")
                
    return pd.DataFrame(data)

df = load_data()

if df.empty:
    st.warning("No evaluation data found in reports/raw/")
else:
    st.subheader("Historical Pass Rate")
    fig = px.line(df, x="Run ID", y="Pass Rate (%)", markers=True, title="Pass Rate Trend")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Latest Run Details")
    st.dataframe(df.tail(1))
    
    st.subheader("All Runs")
    st.dataframe(df)
