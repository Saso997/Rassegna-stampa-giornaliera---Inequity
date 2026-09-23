"""
RASSEGNA STAMPA AUTOMATICA - Notizie da Europa e Mondo
========================================================
Legge le notizie da feed RSS di testate autorevoli (gratuiti, nessuna
chiave API richiesta), seleziona le 30 più importanti e salva il
risultato in un file Markdown (rassegna_stampa.md) leggibile da chiunque,
anche solo aprendo il file su GitHub.

USO IN LOCALE:
    pip install feedparser
    python top_news.py

USO AUTOMATICO:
    Pensato per girare ogni giorno tramite GitHub Actions (vedi il file
    .github/workflows/daily-news.yml che accompagna questo script).
"""

import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import feedparser

# -----------------------------------------------------------------------
# 1) FONTI: puoi aggiungere o togliere feed RSS a piacere.
#    Sono tutti gratuiti e pubblici, non serve nessuna registrazione.
# -----------------------------------------------------------------------
FEEDS = {
    "ANSA": "https://www.ansa.it/sito/ansait_rss.xml",
    "Corriere della Sera": "https://xml2.corriere.it/rss/homepage.xml",
    "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "The Guardian World": "https://www.theguardian.com/world/rss",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "DW (Deutsche Welle)": "https://rss.dw.com/rdf/rss-en-all",
    "France24": "https://www.france24.com/en/rss",
    "Euronews": "https://www.euronews.com/rss?level=theme&name=news",
    "Politico Europe": "https://www.politico.eu/feed/",
    "New York Times World": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
}

MAX_AGE_HOURS = 36          # considera solo notizie nelle ultime N ore
SIMILARITY_THRESHOLD = 0.5  # quanto devono essere simili due titoli per essere la stessa notizia
TOP_N = 30                  # quante notizie finali vuoi in output
OUTPUT_FILE = "rassegna_stampa.md"


def clean_title(title):
    return re.sub(r"\s+", " ", title or "").strip()


def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def fetch_all_entries():
    entries = []
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                print(f"  [!] Attenzione: non sono riuscito a leggere {source}")
                continue
            for e in feed.entries:
                title = clean_title(e.get("title", ""))
                link = e.get("link", "")
                published = e.get("published_parsed") or e.get("updated_parsed")
                if not title or not link:
                    continue
                entries.append(
                    {"source": source, "title": title, "link": link, "published": published}
                )
            print(f"  [OK] {source}: {len(feed.entries)} notizie lette")
        except Exception as ex:
            print(f"  [!] Errore leggendo {source}: {ex}")
    return entries


def filter_recent(entries):
    now = datetime.now(timezone.utc)
    recent = []
    for e in entries:
        if e["published"]:
            pub_dt = datetime(*e["published"][:6], tzinfo=timezone.utc)
            if now - pub_dt <= timedelta(hours=MAX_AGE_HOURS):
                e["published_dt"] = pub_dt
                recent.append(e)
        else:
            e["published_dt"] = now
            recent.append(e)
    return recent


def cluster_entries(entries):
    clusters = []
    for e in entries:
        placed = False
        for cluster in clusters:
            if similar(e["title"], cluster[0]["title"]) > SIMILARITY_THRESHOLD:
                cluster.append(e)
                placed = True
                break
        if not placed:
            clusters.append([e])
    return clusters


def rank_clusters(clusters):
    def score(cluster):
        n_sources = len(set(e["source"] for e in cluster))
        most_recent = max(e["published_dt"] for e in cluster)
        hours_ago = (datetime.now(timezone.utc) - most_recent).total_seconds() / 3600
        recency_score = max(0.0, (MAX_AGE_HOURS - hours_ago) / MAX_AGE_HOURS)
        return n_sources * 2 + recency_score

    return sorted(clusters, key=score, reverse=True)


def write_markdown(top, path=OUTPUT_FILE):
    """Salva il risultato in un file Markdown leggibile (anche da GitHub)."""
    now = datetime.now(timezone.utc)
    lines = [
        "# Rassegna stampa - Europa e Mondo",
        "",
        f"_Generata automaticamente il {now.strftime('%d/%m/%Y')} alle {now.strftime('%H:%M')} UTC_",
        "",
        "---",
        "",
    ]
    for i, cluster in enumerate(top, 1):
        main_entry = max(cluster, key=lambda e: len(e["title"]))
        sources = ", ".join(sorted(set(e["source"] for e in cluster)))
        lines.append(f"### {i}. {main_entry['title']}")
        lines.append(f"- **Fonti che ne parlano:** {sources}")
        lines.append(f"- **Link:** [{main_entry['source']}]({main_entry['link']})")
        lines.append("")
    if not top:
        lines.append("Nessuna notizia trovata in questo aggiornamento.")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("Scarico le notizie dai feed RSS...\n")
    entries = fetch_all_entries()
    print(f"\nTotale notizie scaricate: {len(entries)}")

    recent = filter_recent(entries)
    print(f"Notizie nelle ultime {MAX_AGE_HOURS} ore: {len(recent)}")

    clusters = cluster_entries(recent)
    ranked = rank_clusters(clusters)
    top = ranked[:TOP_N]

    write_markdown(top)
    print(f"\nFatto! Risultato salvato in '{OUTPUT_FILE}' ({len(top)} notizie).")


if __name__ == "__main__":
    main()
