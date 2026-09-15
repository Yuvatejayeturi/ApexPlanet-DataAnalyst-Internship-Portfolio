import os
from pathlib import Path
import hashlib
import sqlite3

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Netflix Data Explorer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# TMDB CONFIG
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN", "").strip()
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def tmdb_request(endpoint, params=None):
    """Call TMDB using either an API Read Access Token or a v3 API key."""
    params = dict(params or {})
    headers = {"accept": "application/json"}

    if TMDB_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {TMDB_ACCESS_TOKEN}"
    elif TMDB_API_KEY:
        params["api_key"] = TMDB_API_KEY
    else:
        return None

    try:
        return requests.get(endpoint, params=params, headers=headers, timeout=10)
    except requests.RequestException:
        return None


# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
.stApp { background:#0b0b0f; color:#f5f5f5; }
[data-testid="stSidebar"] { background:#101014; border-right:1px solid #25252d; }
[data-testid="stSidebar"] * { color:#f5f5f5; }

.brand-netflix { color:#e50914; font-size:30px; font-weight:900; letter-spacing:1px; }
.brand-explorer { color:#f5f5f5; font-size:23px; font-weight:800; }

.hero {
    padding:48px;
    border-radius:20px;
    background:linear-gradient(135deg,#1d1d27 0%,#101014 65%,#160b0d 100%);
    border:1px solid #292932;
    margin-bottom:25px;
}
.hero h1 { font-size:48px; margin:0; }
.hero p { color:#b8b8c3; font-size:18px; max-width:800px; }

.stat {
    background:#15151c;
    border:1px solid #2a2a34;
    border-radius:14px;
    padding:18px;
    text-align:center;
}
.stat-number { font-size:30px; font-weight:800; }
.stat-label { color:#a8a8b3; font-size:13px; }

.section-title { font-size:27px; font-weight:800; margin:28px 0 15px; }

.poster {
    min-height:360px;
    border-radius:12px;
    padding:18px;
    display:flex;
    flex-direction:column;
    justify-content:flex-end;
    border:1px solid #30303a;
    background-size:cover;
    background-position:center;
    margin-bottom:10px;
}
.poster-small {
    min-height:300px;
    border-radius:12px;
    padding:15px;
    display:flex;
    flex-direction:column;
    justify-content:flex-end;
    border:1px solid #30303a;
    background-size:cover;
    background-position:center;
    margin-bottom:10px;
}
.poster-type { font-size:11px; font-weight:800; letter-spacing:1px; color:#ff4b55; text-transform:uppercase; }
.poster-title { font-size:22px; font-weight:850; line-height:1.05; margin-top:7px; text-shadow:0 2px 8px #000; }
.poster-meta { color:#fff; font-size:12px; margin-top:7px; text-shadow:0 2px 8px #000; }

.info-box {
    background:#15151c;
    border:1px solid #292933;
    border-radius:14px;
    padding:22px;
}
.insight {
    background:#15151c;
    border-left:4px solid #e50914;
    border-radius:8px;
    padding:15px 18px;
    margin:10px 0;
}
.tag {
    display:inline-block;
    background:#292932;
    border-radius:15px;
    padding:4px 9px;
    margin:2px;
    font-size:12px;
}
.tmdb-note {
    color:#9f9faa;
    font-size:12px;
    padding:10px 0;
}

.cert-card {
    background:#15151c;
    border:1px solid #292933;
    border-radius:16px;
    padding:20px;
    height:100%;
}
.profile-card {
    background:linear-gradient(135deg,#15151c,#101014);
    border:1px solid #292933;
    border-radius:18px;
    padding:28px;
}
.skill {
    display:inline-block;
    background:#25252f;
    border:1px solid #343440;
    border-radius:18px;
    padding:7px 12px;
    margin:4px;
    font-size:13px;
}
@media (max-width: 768px) {
    .hero { padding:28px 22px; }
    .hero h1 { font-size:34px; }
    .hero p { font-size:15px; }
    .section-title { font-size:23px; }
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATA
# ============================================================
@st.cache_data
def load_data():
    conn = sqlite3.connect("netflix.db")
    data = pd.read_sql_query("SELECT * FROM titles", conn)
    conn.close()
    return data

df = load_data()

for col in [
    "title", "director", "cast", "country",
    "date_added", "rating", "duration",
    "listed_in", "description"
]:
    df[col] = df[col].fillna("Not available")

df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce")

# ============================================================
# TMDB SEARCH / POSTER
# ============================================================
@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 7)
def tmdb_search(title, content_type, year=None):
    if not TMDB_API_KEY and not TMDB_ACCESS_TOKEN:
        return None

    endpoint = "https://api.themoviedb.org/3/search/movie"
    if content_type == "TV Show":
        endpoint = "https://api.themoviedb.org/3/search/tv"

    params = {
        "query": title,
        "include_adult": "false",
        "language": "en-US",
    }

    if year:
        if content_type == "Movie":
            params["year"] = int(year)
        else:
            params["first_air_date_year"] = int(year)

    response = tmdb_request(endpoint, params)
    if response is None or response.status_code != 200:
        return None

    try:
        results = response.json().get("results", [])
        if not results:
            return None

        key = "title" if content_type == "Movie" else "name"
        exact = [r for r in results if str(r.get(key, "")).strip().lower() == str(title).strip().lower()]
        result = exact[0] if exact else results[0]

        poster_path = result.get("poster_path")
        backdrop_path = result.get("backdrop_path")

        return {
            "poster_url": f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None,
            "backdrop_url": f"https://image.tmdb.org/t/p/w1280{backdrop_path}" if backdrop_path else None,
            "tmdb_id": result.get("id"),
        }
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=300)
def tmdb_connection_status():
    if not TMDB_API_KEY and not TMDB_ACCESS_TOKEN:
        return False, "TMDB credentials not configured"

    response = tmdb_request("https://api.themoviedb.org/3/configuration")
    if response is None:
        return False, "TMDB connection failed"
    if response.status_code == 200:
        method = "access token" if TMDB_ACCESS_TOKEN else "API key"
        return True, f"TMDB connected ({method})"
    if response.status_code in (401, 403):
        method = "access token" if TMDB_ACCESS_TOKEN else "API key"
        return False, f"TMDB {method} rejected"
    return False, f"TMDB HTTP {response.status_code}"

def poster_info(row):
    year = int(row["release_year"]) if pd.notna(row["release_year"]) else None
    return tmdb_search(row["title"], row["type"], year)

def safe_year(value):
    return str(int(value)) if pd.notna(value) else "N/A"

def fallback_gradient(title):
    digest = hashlib.md5(str(title).encode("utf-8")).hexdigest()
    h1 = int(digest[:2], 16) % 360
    h2 = (h1 + 55) % 360
    return f"linear-gradient(145deg,hsl({h1},55%,18%),hsl({h2},50%,8%))"

@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 7)
def download_poster(url):
    if not url:
        return None
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception:
        return None

def _token_set(value):
    if value is None:
        return set()
    return {x.strip().lower() for x in str(value).split(",") if x.strip()}

@st.cache_data(show_spinner=False)
def build_recommendation_features(data):
    features = data[["title", "type", "release_year", "rating", "country", "listed_in"]].copy()
    features["genre_set"] = features["listed_in"].map(_token_set)
    features["country_set"] = features["country"].map(_token_set)
    return features

def recommend_titles(selected_row, data, n=6):
    """Recommend catalog titles using transparent, dataset-only similarity scoring."""
    features = build_recommendation_features(data)
    target_title = str(selected_row["title"])
    target_type = str(selected_row["type"])
    target_genres = _token_set(selected_row["listed_in"])
    target_countries = _token_set(selected_row["country"])
    target_rating = str(selected_row["rating"])
    target_year = selected_row["release_year"]

    candidates = features[features["title"] != target_title].copy()

    def similarity(row):
        score = 0.0
        genres = row["genre_set"]
        countries = row["country_set"]
        genre_union = target_genres | genres
        if target_genres and genres:
            score += 0.52 * len(target_genres & genres) / max(len(genre_union), 1)
        if target_type == row["type"]:
            score += 0.18
        if target_rating != "Not available" and target_rating == row["rating"]:
            score += 0.10
        if target_countries and countries and "not available" not in countries:
            score += 0.10 * len(target_countries & countries) / max(len(target_countries | countries), 1)
        if pd.notna(target_year) and pd.notna(row["release_year"]):
            distance = abs(float(target_year) - float(row["release_year"]))
            score += 0.10 * max(0.0, 1.0 - distance / 20.0)
        return score

    candidates["similarity"] = candidates.apply(similarity, axis=1)
    return data[data["title"].isin(
        candidates.sort_values(["similarity", "release_year"], ascending=[False, False]).head(n)["title"]
    )].copy()

def render_title_card(row, small=False):
    """Render a title card with the poster downloaded by Python."""
    info = poster_info(row)
    poster_bytes = download_poster(info["poster_url"]) if info else None

    if poster_bytes:
        st.image(poster_bytes, use_container_width=True)
    else:
        st.markdown(
            f"""
            <div class="poster{'-small' if small else ''}"
                 style="background:{fallback_gradient(row['title'])};">
                <div class="poster-type">{row['type']}</div>
                <div class="poster-title">{row['title']}</div>
                <div class="poster-meta">{safe_year(row['release_year'])} • {row['rating']} • {row['duration']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div style="margin-top:-4px; margin-bottom:16px;">
            <div style="font-size:18px;font-weight:800;">{row['title']}</div>
            <div style="color:#a8a8b3;font-size:12px;">
                {row['type']} • {safe_year(row['release_year'])} • {row['rating']} • {row['duration']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown('<div class="brand-netflix">NETFLIX</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-explorer">DATA EXPLORER</div>', unsafe_allow_html=True)
    st.caption("Your interactive Netflix analysis")
    st.divider()

    page = st.radio(
        "Navigation",
        ["🏠 Home", "🎬 Browse", "🔎 Title Details", "📊 Analytics", "💡 Insights", "🏆 Certifications", "👤 Portfolio", "ℹ️ About"],
        label_visibility="collapsed",
    )

    st.divider()
    tmdb_ok, tmdb_message = tmdb_connection_status()
    if tmdb_ok:
        st.success(tmdb_message)
    else:
        st.error(tmdb_message)
    st.caption("Python • Streamlit • Pandas • SQLite • Plotly")

# ============================================================
# HOME
# ============================================================
if page == "🏠 Home":
    st.markdown("""
    <div class="hero">
        <h1>Explore Netflix Content 🎬</h1>
        <p>
            Discover movies and TV shows, search the catalog, explore title
            details and understand Netflix content through interactive analytics.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    values = [
        (len(df), "Total Titles"),
        ((df["type"] == "Movie").sum(), "Movies"),
        ((df["type"] == "TV Show").sum(), "TV Shows"),
        (df["release_year"].nunique(), "Release Years"),
    ]
    for col, (number, label) in zip([c1, c2, c3, c4], values):
        with col:
            st.markdown(
                f'<div class="stat"><div class="stat-number">{number:,}</div>'
                f'<div class="stat-label">{label}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-title">Latest Releases in the Dataset</div>', unsafe_allow_html=True)

    latest = df.sort_values(["release_year", "title"], ascending=[False, True]).head(6)
    cols = st.columns(3)
    for i, (_, row) in enumerate(latest.iterrows()):
        with cols[i % 3]:
            render_title_card(row)
            st.caption(f"{row['listed_in']}")

    if TMDB_API_KEY:
        st.markdown(
            '<div class="tmdb-note">Poster artwork and metadata matching are powered by The Movie Database (TMDB).</div>',
            unsafe_allow_html=True
        )

# ============================================================
# BROWSE
# ============================================================
elif page == "🎬 Browse":
    st.title("🎬 Browse Netflix")
    st.caption("Search and filter the catalog.")

    with st.expander("🔎 Search & Filters", expanded=True):
        search = st.text_input("Search title", placeholder="Try Stranger Things...")

        f1, f2, f3 = st.columns(3)
        with f1:
            content_type = st.selectbox("Type", ["All", "Movie", "TV Show"])
        with f2:
            years = sorted(df["release_year"].dropna().astype(int).unique(), reverse=True)
            year = st.selectbox("Release Year", ["All"] + years)
        with f3:
            ratings = sorted(df.loc[df["rating"] != "Not available", "rating"].unique())
            rating = st.selectbox("Rating", ["All"] + ratings)

        genres = sorted(set(
            g.strip()
            for value in df["listed_in"]
            for g in str(value).split(",")
            if g.strip()
        ))
        genre = st.multiselect(
            "Genre",
            genres,
            placeholder="Choose one or more genres...",
        )

    filtered = df.copy()

    if search:
        filtered = filtered[filtered["title"].str.contains(search, case=False, na=False)]
    if content_type != "All":
        filtered = filtered[filtered["type"] == content_type]
    if year != "All":
        filtered = filtered[filtered["release_year"] == int(year)]
    if rating != "All":
        filtered = filtered[filtered["rating"] == rating]
    for selected_genre in genre:
        filtered = filtered[filtered["listed_in"].str.contains(selected_genre, case=False, na=False)]

    # Sorting keeps the browse experience predictable and useful.
    sort_col, sort_order, page_size = st.columns([1.4, 1.2, 1])
    with sort_col:
        sort_by = st.selectbox(
            "Sort by",
            ["Release Year", "Title"],
            key="browse_sort_by",
        )
    with sort_order:
        order = st.selectbox(
            "Order",
            ["Newest / A–Z", "Oldest / Z–A"],
            key="browse_sort_order",
        )
    with page_size:
        per_page = st.selectbox("Titles per page", [6, 12, 18, 24], index=2)

    if sort_by == "Release Year":
        filtered = filtered.sort_values(
            ["release_year", "title"],
            ascending=[order == "Oldest / Z–A", order == "Oldest / Z–A"],
            na_position="last",
        )
    else:
        filtered = filtered.sort_values(
            "title",
            ascending=order == "Newest / A–Z",
        )

    total_results = len(filtered)
    st.write(f"**{total_results:,} titles found**")

    if total_results == 0:
        st.warning("No titles match your filters. Try removing a filter or changing your search.")
    else:
        total_pages = max(1, (total_results + per_page - 1) // per_page)
        page_number = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key="browse_page",
        )
        start = (int(page_number) - 1) * per_page
        display = filtered.iloc[start:start + per_page]

        st.caption(f"Showing {start + 1:,}–{min(start + per_page, total_results):,} of {total_results:,} titles")

        for row_start in range(0, len(display), 3):
            cols = st.columns(3)
            for col, (_, row) in zip(cols, display.iloc[row_start:row_start + 3].iterrows()):
                with col:
                    render_title_card(row, small=True)
                    st.caption(
                        f"**{row['title']}**  \n"
                        f"{safe_year(row['release_year'])} • {row['rating']} • {row['duration']}"
                    )

        if total_pages > 1:
            st.progress(int(page_number) / total_pages)
            st.caption(f"Page {int(page_number)} of {total_pages}")

# ============================================================
# TITLE DETAILS 2.0
# ============================================================
elif page == "🔎 Title Details":
    st.title("🔎 Title Details")
    st.caption("Explore a title with richer metadata, TMDB artwork and dataset-based recommendations.")

    selected_title = st.selectbox("Choose a title", sorted(df["title"].tolist()))
    row = df[df["title"] == selected_title].iloc[0]
    info = poster_info(row)

    # Hero artwork from TMDB when available.
    backdrop_bytes = None
    if info and info.get("backdrop_url"):
        backdrop_bytes = download_poster(info["backdrop_url"])
    if backdrop_bytes:
        st.image(backdrop_bytes, use_container_width=True)

    left, right = st.columns([0.85, 1.7], gap="large")

    with left:
        render_title_card(row)

    with right:
        st.markdown(f"# {row['title']}")
        st.markdown(
            f"**{row['type']}** &nbsp;•&nbsp; **{safe_year(row['release_year'])}** &nbsp;•&nbsp; "
            f"**{row['rating']}** &nbsp;•&nbsp; **{row['duration']}**",
            unsafe_allow_html=True,
        )

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Type", row["type"])
        with m2:
            st.metric("Release Year", safe_year(row["release_year"]))
        with m3:
            st.metric("Rating", row["rating"])

        st.markdown("### 🎭 Genres")
        tags = "".join(
            f'<span class="tag">{g.strip()}</span>'
            for g in str(row["listed_in"]).split(",")
            if g.strip()
        )
        st.markdown(tags, unsafe_allow_html=True)

        st.markdown("### 📝 Description")
        st.write(row["description"])

        if info and info.get("tmdb_id"):
            st.caption(f"TMDB match ID: {info['tmdb_id']}")

    st.divider()

    st.markdown('<div class="section-title">👥 Cast & Crew</div>', unsafe_allow_html=True)
    crew1, crew2 = st.columns(2)
    with crew1:
        st.markdown("**Director**")
        st.write(row["director"])
        st.markdown("**Country**")
        st.write(row["country"])
    with crew2:
        st.markdown("**Cast**")
        st.write(row["cast"])
        st.markdown("**Date Added to Netflix Dataset**")
        st.write(row["date_added"])

    st.divider()

    st.markdown('<div class="section-title">🤖 Because you selected this title</div>', unsafe_allow_html=True)
    st.caption("Recommendations are calculated from the Netflix dataset using genre, type, rating, country and release-year similarity.")
    recommendations = recommend_titles(row, df, n=6)
    if recommendations.empty:
        st.info("No similar titles could be found in the dataset.")
    else:
        rec_cols = st.columns(3)
        for i, (_, rec_row) in enumerate(recommendations.iterrows()):
            with rec_cols[i % 3]:
                render_title_card(rec_row, small=True)
                st.caption(str(rec_row["listed_in"]))

    st.divider()
    st.markdown("### 📊 Dataset Snapshot")
    same_type = df[df["type"] == row["type"]]
    same_genre = df[df["listed_in"].astype(str).str.contains(str(row["listed_in"]).split(",")[0].strip(), case=False, na=False)]
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric("Titles in Dataset", f"{len(df):,}")
    with s2:
        st.metric(f"{row['type']} Titles", f"{len(same_type):,}")
    with s3:
        st.metric("Genre-Matched Titles", f"{len(same_genre):,}")
    with s4:
        st.metric("Genres", f"{len(str(row['listed_in']).split(','))}")

# ============================================================
# ANALYTICS
# ============================================================
elif page == "📊 Analytics":
    st.title("📊 Analytics Dashboard")
    st.caption("Explore Netflix catalog patterns with interactive, portfolio-ready analysis.")

    # Prepare analysis data
    analysis_df = df.copy()
    analysis_df["release_year"] = pd.to_numeric(analysis_df["release_year"], errors="coerce")
    analysis_df["date_added_dt"] = pd.to_datetime(analysis_df["date_added"], errors="coerce")
    analysis_df["added_year"] = analysis_df["date_added_dt"].dt.year
    analysis_df["added_month"] = analysis_df["date_added_dt"].dt.month_name()
    analysis_df["genre_primary"] = analysis_df["listed_in"].fillna("").str.split(",").str[0].str.strip()

    min_year = int(analysis_df["release_year"].dropna().min())
    max_year = int(analysis_df["release_year"].dropna().max())
    selected_years = st.slider(
        "Release year range",
        min_value=min_year,
        max_value=max_year,
        value=(max(min_year, 2000), max_year),
    )

    filtered = analysis_df[
        analysis_df["release_year"].between(selected_years[0], selected_years[1], inclusive="both")
    ].copy()

    total = len(filtered)
    movies = int((filtered["type"] == "Movie").sum())
    shows = int((filtered["type"] == "TV Show").sum())
    countries = int(filtered["country"].dropna().nunique())
    avg_year = filtered["release_year"].dropna().mean()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Titles in range", f"{total:,}")
    with k2:
        st.metric("Movies", f"{movies:,}")
    with k3:
        st.metric("TV Shows", f"{shows:,}")
    with k4:
        st.metric("Countries", f"{countries:,}")

    st.divider()

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.subheader("📈 Titles by Release Year")
        yearly = (
            filtered.dropna(subset=["release_year"])
            .groupby("release_year")
            .size()
            .reset_index(name="Titles")
            .sort_values("release_year")
        )
        fig = px.line(
            yearly,
            x="release_year",
            y="Titles",
            markers=True,
            labels={"release_year": "Release Year", "Titles": "Number of Titles"},
        )
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("🎬 Movies vs TV Shows")
        type_counts = filtered["type"].value_counts().rename_axis("Type").reset_index(name="Titles")
        fig = px.pie(
            type_counts,
            names="Type",
            values="Titles",
            hole=0.55,
        )
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2, gap="large")

    with c3:
        st.subheader("⭐ Rating Distribution")
        ratings = (
            filtered["rating"]
            .fillna("Unknown")
            .value_counts()
            .reset_index()
            .rename(columns={"rating": "Rating", "count": "Titles"})
        )
        fig = px.bar(
            ratings,
            x="Rating",
            y="Titles",
            text="Titles",
            labels={"Rating": "Rating", "Titles": "Titles"},
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        st.subheader("🎭 Top 10 Genres")
        genres = (
            filtered["listed_in"]
            .fillna("")
            .str.split(",")
            .explode()
            .str.strip()
        )
        genres = genres[genres.ne("")]
        genre_counts = genres.value_counts().head(10).sort_values().reset_index()
        genre_counts.columns = ["Genre", "Titles"]
        fig = px.bar(
            genre_counts,
            x="Titles",
            y="Genre",
            orientation="h",
            text="Titles",
            labels={"Titles": "Titles", "Genre": ""},
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    c5, c6 = st.columns(2, gap="large")

    with c5:
        st.subheader("🌎 Top 10 Countries")
        countries_series = (
            filtered["country"]
            .fillna("")
            .str.split(",")
            .explode()
            .str.strip()
        )
        countries_series = countries_series[countries_series.ne("")]
        country_counts = countries_series.value_counts().head(10).sort_values().reset_index()
        country_counts.columns = ["Country", "Titles"]
        fig = px.bar(
            country_counts,
            x="Titles",
            y="Country",
            orientation="h",
            text="Titles",
            labels={"Titles": "Titles", "Country": ""},
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c6:
        st.subheader("📅 Titles Added to Netflix")
        added = (
            filtered.dropna(subset=["date_added_dt"])
            .groupby("added_year")
            .size()
            .reset_index(name="Titles")
            .sort_values("added_year")
        )
        fig = px.area(
            added,
            x="added_year",
            y="Titles",
            labels={"added_year": "Year Added", "Titles": "Titles Added"},
        )
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("💡 Quick Data Summary")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.metric("Average release year", f"{avg_year:.0f}" if pd.notna(avg_year) else "N/A")
    with s2:
        movie_share = (movies / total * 100) if total else 0
        st.metric("Movie share", f"{movie_share:.1f}%")
    with s3:
        show_share = (shows / total * 100) if total else 0
        st.metric("TV Show share", f"{show_share:.1f}%")

    if total:
        top_genre = (
            filtered["listed_in"].fillna("").str.split(",").explode().str.strip()
        )
        top_genre = top_genre[top_genre.ne("")].value_counts()
        top_genre_name = top_genre.index[0] if len(top_genre) else "N/A"
        st.info(
            f"Within the selected release-year range, **{movies:,} movies** and "
            f"**{shows:,} TV shows** are represented. The most common listed genre is "
            f"**{top_genre_name}**."
        )

    csv_data = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Filtered Analytics Data (CSV)",
        data=csv_data,
        file_name=f"netflix_analytics_{selected_years[0]}_{selected_years[1]}.csv",
        mime="text/csv",
    )

# ============================================================
# INSIGHTS
# ============================================================
elif page == "💡 Insights":
    st.title("💡 Key Insights")
    st.caption("Automatically generated observations from the catalog.")

    movies = (df["type"] == "Movie").sum()
    shows = (df["type"] == "TV Show").sum()
    genre_series = df["listed_in"].str.split(",").explode().str.strip()
    top_genre = genre_series.value_counts().idxmax()
    country_series = df[df["country"] != "Not available"]["country"].str.split(",").explode().str.strip()
    top_country = country_series.value_counts().idxmax()
    latest_year = int(df["release_year"].max())

    insights = [
        f"🎬 **Movies dominate the catalog:** {movies:,} movies versus {shows:,} TV shows.",
        f"🎭 **Most frequently listed genre:** {top_genre}.",
        f"🌎 **Most represented country:** {top_country}.",
        f"📅 **Latest release year in this dataset:** {latest_year}.",
    ]

    for text in insights:
        st.markdown(f'<div class="insight">{text}</div>', unsafe_allow_html=True)

# ============================================================
# CERTIFICATIONS
# ============================================================
elif page == "🏆 Certifications":
    st.title("🏆 Certifications")
    st.caption("Professional learning and internship credentials.")

    cert_dir = BASE_DIR / "certificates"
    preview = cert_dir / "Certificate_yuva_preview.png"
    pdf_file = cert_dir / "Certificate_yuva.pdf"

    left, right = st.columns([1.25, 1], gap="large")

    with left:
        if preview.exists():
            st.image(str(preview), use_container_width=True)
        else:
            st.info("Certificate preview is not available.")

    with right:
        st.markdown('<div class="cert-card">', unsafe_allow_html=True)
        st.markdown("## ApexPlanet Data Analytics Internship")
        st.markdown("**ApexPlanet Software Pvt. Ltd.**")
        st.write("Successfully completed the Internship Program in the domain of **Data Analytics**.")
        st.markdown("**Duration:** 8 Weeks & 3 Days")
        st.markdown("**Dates:** 11 May 2026 – 09 July 2026")
        st.markdown("**Mode:** Virtual / Online")
        st.markdown("**Certificate ID:** APSPL2634197")
        st.markdown("</div>", unsafe_allow_html=True)

        if pdf_file.exists():
            st.download_button(
                "📄 Download Certificate PDF",
                data=pdf_file.read_bytes(),
                file_name="ApexPlanet_Data_Analytics_Internship_Certificate.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    st.divider()
    st.markdown("### 📌 Internship Highlights")
    h1, h2, h3 = st.columns(3)
    with h1:
        st.metric("Duration", "8 Weeks + 3 Days")
    with h2:
        st.metric("Domain", "Data Analytics")
    with h3:
        st.metric("Mode", "Online")

    st.info(
        "This certificate represents the internship credential used as part of "
        "this portfolio project."
    )

# ============================================================
# PORTFOLIO
# ============================================================
elif page == "👤 Portfolio":
    st.title("👤 My Portfolio")
    st.caption("A quick overview of my technical skills, project work and learning journey.")

    st.markdown("""
    <div class="profile-card">
        <h2 style="margin-top:0;">Yuva Teja Yeturi</h2>
        <p style="color:#b8b8c3;font-size:16px;">
            Data Analytics • Python • SQL • Machine Learning
        </p>
        <p style="color:#a8a8b3;">
            This portfolio section presents the skills and project work behind the
            Netflix Data Explorer.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">🛠️ Technical Skills</div>', unsafe_allow_html=True)
    skills = [
        "Python", "Pandas", "NumPy", "SQL", "Statistics",
        "Machine Learning", "Excel", "Power BI", "Matplotlib",
        "Seaborn", "Plotly", "SQLite", "Git & GitHub", "Streamlit"
    ]
    st.markdown(
        "".join(f'<span class="skill">{skill}</span>' for skill in skills),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">🚀 Featured Project</div>', unsafe_allow_html=True)
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("### 🎬 Netflix Data Explorer")
        st.write(
            "An interactive Netflix catalog and analytics application built with "
            "Python and Streamlit. It combines data exploration, visualization, "
            "dataset-based recommendations and TMDB poster artwork."
        )
        st.markdown("**Core stack:** Python • Streamlit • Pandas • SQLite • Plotly • TMDB API")

    with p2:
        st.markdown("### 📈 What the project demonstrates")
        st.write(
            "Data cleaning and exploration, filtering, descriptive analytics, "
            "interactive visualization, recommendation logic, API integration, "
            "and portfolio-ready presentation."
        )

    st.markdown('<div class="section-title">🔗 Professional Links</div>', unsafe_allow_html=True)
    st.write("Connect with me and explore my projects.")

    link1, link2 = st.columns(2)
    with link1:
        st.link_button(
            "💻 GitHub",
            "https://github.com/Yuvatejayeturi",
            use_container_width=True,
        )
    with link2:
        st.link_button(
            "🔗 LinkedIn",
            "https://www.linkedin.com/in/yuva-teja-yeturi-9b0311342/",
            use_container_width=True,
        )

# ============================================================
# ABOUT / ATTRIBUTION
# ============================================================
elif page == "ℹ️ About":
    st.title("ℹ️ About This Project")

    st.markdown("""
    ### Netflix Data Explorer

    This project turns a Netflix dataset into an interactive data-analysis
    website using **Python, Streamlit, Pandas, SQLite and Plotly**.

    It includes catalog search, filtering, title details, dataset-based recommendations,
TMDB poster matching, data visualization, automatically generated insights,
and a portfolio/certification section.
    """)

    st.divider()

    st.subheader("TMDB Attribution")
    st.markdown(
        "This product uses the **TMDB API** but is not endorsed or certified by TMDB."
    )
    st.markdown(
        "Poster artwork and selected metadata are provided by "
        "[The Movie Database (TMDB)](https://www.themoviedb.org/)."
    )

    st.subheader("Data Source")
    st.write(
        "The Netflix title catalog displayed here comes from the CSV dataset "
        "used for this data-analysis project."
    )
