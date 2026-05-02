import json
import os
from collections import Counter


ANALYTICS_DIR = "analytics"
PAGE_STATS_PATH = os.path.join(ANALYTICS_DIR, "page_stats.jsonl")
UNIQUE_URLS_PATH = os.path.join(ANALYTICS_DIR, "unique_urls.txt")
WORD_COUNTS_PATH = os.path.join(ANALYTICS_DIR, "word_counts.tsv")
SUBDOMAINS_PATH = os.path.join(ANALYTICS_DIR, "subdomains.tsv")


def load_pages():
    pages = {}
    if not os.path.exists(PAGE_STATS_PATH):
        return pages

    with open(PAGE_STATS_PATH, "r", encoding="utf-8") as page_stats:
        for line in page_stats:
            try:
                page = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = page.get("url")
            if not url:
                continue
            pages[url] = int(page.get("word_count", 0))
    return pages


def load_unique_urls(pages):
    if not os.path.exists(UNIQUE_URLS_PATH):
        return set(pages)

    with open(UNIQUE_URLS_PATH, "r", encoding="utf-8") as unique_urls_file:
        return {line.strip() for line in unique_urls_file if line.strip()}


def load_word_counts():
    counts = Counter()
    if not os.path.exists(WORD_COUNTS_PATH):
        return counts

    with open(WORD_COUNTS_PATH, "r", encoding="utf-8") as word_counts_file:
        for line in word_counts_file:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 2:
                continue
            word, count = parts
            try:
                counts[word] = int(count)
            except ValueError:
                continue
    return counts


def load_subdomains():
    subdomains = []
    if not os.path.exists(SUBDOMAINS_PATH):
        return subdomains

    with open(SUBDOMAINS_PATH, "r", encoding="utf-8") as subdomains_file:
        for line in subdomains_file:
            line = line.strip()
            if line:
                subdomains.append(line)
    return sorted(subdomains)


def main():
    pages = load_pages()
    unique_urls = load_unique_urls(pages)
    word_counts = load_word_counts()
    subdomains = load_subdomains()

    print("How many unique pages did you find?")
    print(len(unique_urls))
    print()

    print("What is the longest page in terms of the number of words?")
    if pages:
        url, count = max(pages.items(), key=lambda item: item[1])
        print(f"{url}, {count}")
    else:
        print("No pages recorded yet.")
    print()

    print("What are the 50 most common words?")
    for word, count in word_counts.most_common(50):
        print(f"{word}, {count}")
    print()

    print("How many subdomains did you find in the uci.edu domain?")
    print(len(subdomains))
    for line in subdomains:
        print(line)


if __name__ == "__main__":
    main()
