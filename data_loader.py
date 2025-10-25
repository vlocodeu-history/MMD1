# data_loader.py
from __future__ import annotations
import pandas as pd
import streamlit as st
from pathlib import Path

DATA_DIR = Path("data")

@st.cache_data(show_spinner=False)
def load_b1634():
    df = pd.read_csv(DATA_DIR / "b1634_pressures.csv", comment="#")
    # Ensure numeric columns
    for col in ["DN_mm","150","300","400","600","900","1500","2500","4500"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

@st.cache_data(show_spinner=False)
def load_materials():
    df = pd.read_csv(DATA_DIR / "dc009_materials.csv", comment="#")
    df["yield_mpa"] = pd.to_numeric(df["yield_mpa"], errors="coerce")
    # Fast lookups
    by_name = {str(r["material"]).strip(): float(r["yield_mpa"]) for _, r in df.iterrows()}
    return df, by_name

@st.cache_data(show_spinner=False)
def load_dati():
    # This file has two sections; pandas will read all rows then we split by header presence
    df = pd.read_csv(DATA_DIR / "dati_master.csv", comment="#")
    # Normalize column names if both sections were concatenated
    df_cols = {c.lower(): c for c in df.columns}
    # Extract class pressure table
    if {"class","Pa","Pe","P_psig","P_kgmm2"}.issubset(set(df.columns)):
        classes = df[["class","Pa","Pe","P_psig","P_kgmm2"]].dropna(how="all")
    else:
        # If your editor removed case—fall back by lower() names
        classes = df.rename(columns=str.lower)[["class","pa","pe","p_psig","p_kgmm2"]].dropna(how="all")
        classes.columns = ["class","Pa","Pe","P_psig","P_kgmm2"]

    # Extract bolt areas
    if {"bolt_thread","area_mm2"}.issubset(set(df.columns)):
        bolt = df[["bolt_thread","area_mm2"]].dropna(how="all").drop_duplicates()
    else:
        bolt = df.rename(columns=str.lower)[["bolt_thread","area_mm2"]].dropna(how="all").drop_duplicates()

    # Normalize
    classes["class"] = pd.to_numeric(classes["class"], errors="coerce").astype("Int64")
    classes = classes.dropna(subset=["class"])
    bolt["area_mm2"] = pd.to_numeric(bolt["area_mm2"], errors="coerce")

    bolt_map = {str(r["bolt_thread"]).strip(): float(r["area_mm2"]) for _, r in bolt.iterrows()}
    class_map = {int(r["class"]): dict(Pa=float(r["Pa"]), Pe=float(r["Pe"]),
                                       P_psig=float(r["P_psig"]), P_kgmm2=float(r["P_kgmm2"]))
                 for _, r in classes.iterrows()}

    return classes, bolt, class_map, bolt_map

# ---------- High-level helpers (call from pages) ----------

def pressure_for_dn_class(dn_mm: float, asme_class: int) -> float | None:
    """
    Return recommended pressure (MPa) for a DN & Class. You can choose which column to use
    (often 'Pa' from DATI class table or the B16.34 per-size table). Here we use B16.34 DF.
    """
    b = load_b1634()
    # nearest DN row
    row = b.iloc[(b["DN_mm"] - float(dn_mm)).abs().argsort()].head(1)
    if row.empty:
        return None
    col = str(asme_class)
    return float(row.iloc[0][col]) if col in b.columns else None

def class_pressures(asme_class: int) -> dict | None:
    """Return Pa/Pe/P_psig/P_kgmm2 for a class from DATI."""
    _, _, class_map, _ = load_dati()
    return class_map.get(int(asme_class))

def bolt_area_mm2(thread: str) -> float | None:
    """Return tensile area for a bolt thread string (e.g., 'M12 x 1.75' or '1/2\" UNC')."""
    _, _, _, bolt_map = load_dati()
    return bolt_map.get(thread.strip())

def material_yield_mpa(material_name: str) -> float | None:
    """Yield stress lookup from DC009 materials."""
    _, by_name = load_materials()
    return by_name.get(material_name.strip())

def list_materials() -> list[str]:
    df, _ = load_materials()
    return df["material"].dropna().astype(str).tolist()

def list_bolt_threads() -> list[str]:
    _, bolt, _, _ = load_dati()
    return bolt["bolt_thread"].dropna().astype(str).tolist()
