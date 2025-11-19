# recession_model.py
import math
import time
import pandas as pd
import numpy as np
from pandas_datareader import data as web
import requests
from requests.adapters import HTTPAdapter, Retry

# ============================================================
# Global FRED session (retries + backoff)
# ============================================================

session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)


# -----------------------------------------------------------
# FRED fetch util
# -----------------------------------------------------------

def fred(series, start="1990-01-01"):
    """Robust FRED fetcher with:
    - automatic retry
    - HTML error detection
    - silent failure handling
    - clean warning messages
    """
    url = f"https://fred.stlouisfed.org/series/{series}"

    for attempt in range(1, 4):
        try:
            # Attempt fetch
            df = web.DataReader(series, "fred", start, session=session)

            # If FRED returned nothing, check if we got an HTML page
            if df is None or df.empty:
                raise ValueError("Empty response")

            return df.dropna()

        except Exception as e:
            # Now check if FRED returned HTML instead of CSV
            try:
                response = session.get(url, timeout=5)
                content_type = response.headers.get("Content-Type", "")

                if "text/html" in content_type.lower():
                    print(f"[FRED WARNING] {series}: HTML error page received (likely 404 or rate-limit).")
                else:
                    print(f"[FRED WARNING] {series}: fetch failed ({str(e)})")

            except Exception:
                print(f"[FRED WARNING] {series}: network error.")

            if attempt < 3:
                wait = 2 ** (attempt - 1)
                print(f"[Retrying {series} in {wait}s]...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"[FRED ERROR] {series} failed after 3 attempts.")


# -----------------------------------------------------------
# CAPE fallback
# -----------------------------------------------------------

def fetch_cape(start="1990-01-01"):
    try:
        return fred("CAPE", start)
    except:
        print("[WARN] CAPE unavailable — using fallback")
        cape_vals = pd.Series([22, 25, 30, 35, 38, 40],
                              index=pd.date_range("2019-01-01", periods=6, freq="YS"))
        return pd.DataFrame(cape_vals, columns=["CAPE"])


# -----------------------------------------------------------
# Z-score
# -----------------------------------------------------------

def zscore(series, current):
    return (current - series.mean()) / series.std()


# -----------------------------------------------------------
# Recession Model class
# -----------------------------------------------------------

class RecessionRiskModel2026:
    beta0 = -1.0
    beta_yc = -0.45
    beta_hy = 0.35
    beta_u = 0.30
    beta_cape = 0.25
    beta_struct = 0.20
    beta_ret = 0.20

    @staticmethod
    def logistic(x):
        return 1 / (1 + math.exp(-x))

    def predict(self, z_yc, z_hy, z_u, z_cape, z_struct, z_ret):
        x = (
            self.beta0
            + self.beta_yc * z_yc
            + self.beta_hy * z_hy
            + self.beta_u * z_u
            + self.beta_cape * z_cape
            + self.beta_struct * z_struct
            + self.beta_ret * z_ret
        )
        return self.logistic(x)


# -----------------------------------------------------------
# Compute full recession probability + signals
# -----------------------------------------------------------
def compute_recession_probability():
    # Yield curve (2Y - 3M)
    df2 = fred("DGS2")
    df3m = fred("DGS3MO")

    yc = pd.concat([df2, df3m], axis=1).dropna()
    yc["spread"] = yc["DGS2"] - yc["DGS3MO"]

    # HY Spread
    hy = fred("BAMLH0A0HYM2")

    # Unemployment
    un = fred("UNRATE")
    delta_u = un["UNRATE"].iloc[-1] - un["UNRATE"].iloc[-13]

    # CAPE (fallback)
    cape = fetch_cape()

    # Z-scores
    z_yc = zscore(yc["spread"], yc["spread"].iloc[-1])
    z_hy = zscore(hy["BAMLH0A0HYM2"], hy["BAMLH0A0HYM2"].iloc[-1])
    z_u = zscore(un["UNRATE"].diff(12).dropna(), delta_u)
    z_cape = zscore(cape["CAPE"], cape["CAPE"].iloc[-1])

    # Structural + retiree wealth placeholders
    z_struct = 1.0
    z_ret = 1.0

    model = RecessionRiskModel2026()
    p = model.predict(z_yc, z_hy, z_u, z_cape, z_struct, z_ret)

    # ✅ RETURN DICT (not float)
    return {
        "probability": float(p),
        "z": {
            "Yield Curve": float(z_yc),
            "HY Spread": float(z_hy),
            "Unemployment Δ12M": float(z_u),
            "CAPE": float(z_cape),
            "Structural": z_struct,
            "Retiree Wealth": z_ret,
        },
        "raw": {
            "spread": yc["spread"],
            "hy": hy["BAMLH0A0HYM2"],
            "unrate": un["UNRATE"],
            "cape": cape["CAPE"]
        }
    }
