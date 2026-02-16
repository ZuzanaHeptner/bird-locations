# streamlit_app.py
import streamlit as st
import pandas as pd
import folium
from branca.colormap import LinearColormap
from streamlit_folium import st_folium
import json
from pathlib import Path

st.set_page_config(layout="wide")

# ---- Load historic data ----
dfs = []
files = list(Path("ebird_IS_historic").rglob("*.json"))
for file in files:
    data = json.loads(file.read_text())
    if data:
        df = pd.DataFrame(data)
        df["source_file"] = file.name
        dfs.append(df)

df_is_all = pd.concat(dfs, ignore_index=True)

# ---- Wishlist of species ----
wishlist = [
    'Common Eider', 'White-winged Scoter', 'Long-tailed Duck', 'Iceland Gull',
    'Ruddy Turnstone', 'Red-breasted Merganser', 'Common Redshank', 'Purple Sandpiper',
    'Common Loon', 'Harlequin Duck', 'Black Guillemot', 'Glaucous Gull', 'Black-legged Kittiwake',
    'Merlin', 'Rock Ptarmigan', 'European Golden-Plover', 'Red Knot', 'Red-throated Loon',
    'Barnacle Goose', 'Black-tailed Godwit', 'Greater White-fronted Goose', 'Short-eared Owl',
    'King Eider', 'Northern Gannet', 'Ruff', 'American Wigeon', 'Common Goldeneye',
    "Barrow's Goldeneye", 'Razorbill', 'White-tailed Eagle', 'Surf Scoter', 'Velvet Scoter',
    'Bar-tailed Godwit', 'Dunlin', 'Parasitic Jaeger', 'Common Murre', 'Manx Shearwater',
    'Brant', 'Thick-billed Murre', 'Black Scoter', 'Atlantic Puffin'
]

# ---- Keep only wishlist species ----
df_wishlist = df_is_all[df_is_all["comName"].isin(wishlist)].copy()

# ---- Rank locations ----
rank_df = (
    df_wishlist.groupby(['locName', 'comName'])
    .count()[['sciName']]
    .reset_index()
)
rank_df['rank'] = rank_df.groupby('comName')['sciName'].rank(
    method='dense', ascending=False
)
df_wishlist = df_wishlist.merge(
    rank_df[['locName', 'comName', 'rank']],
    on=['locName', 'comName'],
    how='left'
)

# ---- Safe datetime conversion ----
df_wishlist["obsDt"] = pd.to_datetime(df_wishlist["obsDt"], errors="coerce")

# ---- Sidebar: select species ----
all_species = sorted(df_wishlist["comName"].dropna().unique())
selected_species = st.sidebar.selectbox("Select species to show", ["All"] + all_species)

# ---- Filter dataframe if a species is selected ----
if selected_species != "All":
    df_filtered = df_wishlist[df_wishlist["comName"] == selected_species].copy()
else:
    df_filtered = df_wishlist.copy()

# ---- Aggregate per location ----
def aggregate_records(g):
    g = g.sort_values(["comName", "obsDt"])
    return pd.Series({
        "species_list": g["comName"].tolist(),
        "dates": [d.strftime("%Y-%m-%d %H:%M") if pd.notnull(d) else "" for d in g["obsDt"]],
        "counts": g["howMany"].tolist(),
        "avg_rank": g["rank"].mean(),
        "n_species": g["comName"].nunique()
    })

agg = (
    df_filtered
    .groupby(["locName","lat","lng"], group_keys=False)
    .apply(aggregate_records, include_groups=False)
    .reset_index()
)

# ---- Create Folium map ----
center_lat = agg["lat"].mean() if not agg.empty else 0
center_lng = agg["lng"].mean() if not agg.empty else 0

m = folium.Map(location=[center_lat, center_lng], zoom_start=6)

#if not agg.empty:
#    bounds = [[agg['lat'].min(), agg['lng'].min()], [agg['lat'].max(), agg['lng'].max()]]
#    m.fit_bounds(bounds)


# ---- Color scale ----
if not agg.empty and agg["avg_rank"].notna().any():
    min_rank = agg["avg_rank"].min()
    max_rank = agg["avg_rank"].max()
    if min_rank > max_rank:
        min_rank, max_rank = max_rank, min_rank
    colormap = LinearColormap(
        colors=["green","yellow","red"],
        vmin=min_rank,
        vmax=max_rank
    )
    colormap.caption = "Average Rank (Green = Best)"
    # colormap.add_to(m)
else:
    colormap = None

# ---- Add markers ----
for _, row in agg.iterrows():
    species_html = ""
    for sp, dt, ct in zip(row["species_list"], row["dates"], row["counts"]):
        species_html += f"{sp} — {dt} — {ct}<br>"

    popup_html = f"""
    <b>{row['locName']}</b><br>
    <b>Species count:</b> {row['n_species']}<br>
    <b>Average rank:</b> {row['avg_rank']:.2f}<br><br>
    {species_html}
    """

    color_val = colormap(row["avg_rank"]) if colormap and pd.notna(row["avg_rank"]) else "blue"

    folium.CircleMarker(
        location=[row["lat"], row["lng"]],
        radius=5 + row["n_species"]*1.5,
        color=color_val,
        fill=True,
        fill_opacity=0.85,
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(m)

# ---- Display map ----
st.subheader("Iceland trip March 2026")
st_folium(m, width=1200, height=800)
