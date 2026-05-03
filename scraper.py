import json
import os
import re
from collections import Counter
from html import unescape
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


ALLOWED_DOMAINS = (
    "ics.uci.edu",
    "cs.uci.edu",
    "informatics.uci.edu",
    "stat.uci.edu",
)
BLOCKED_HOSTS = {
    "checkin.ics.uci.edu",
    "dale-cooper-v0.ics.uci.edu",
    "e2.ics.uci.edu",
    "elms.ics.uci.edu",
    "helpdesk.ics.uci.edu",
    "intranet.ics.uci.edu",
    "julia-hub.ics.uci.edu",
    "netreg.ics.uci.edu",
    "onboarding.ics.uci.edu",
    "signage.ics.uci.edu",
    "speedtest.ics.uci.edu",
    "staging-hub.ics.uci.edu",
    "support.ics.uci.edu",
}

ANALYTICS_DIR = "analytics"
PAGE_STATS_PATH = os.path.join(ANALYTICS_DIR, "page_stats.jsonl")
UNIQUE_URLS_PATH = os.path.join(ANALYTICS_DIR, "unique_urls.txt")
WORD_COUNTS_PATH = os.path.join(ANALYTICS_DIR, "word_counts.tsv")
SUBDOMAINS_PATH = os.path.join(ANALYTICS_DIR, "subdomains.tsv")
LONGEST_PAGE_PATH = os.path.join(ANALYTICS_DIR, "longest_page.txt")

MAX_QUERY_PARAMS = 6
MAX_PATH_SEGMENTS = 14
MAX_REPEATED_PATH_SEGMENT = 3
MIN_TEXT_WORDS_FOR_COUNTS = 5
PREFIX_SOFT_LIMIT = 80
TEMPLATE_TOKEN_RATIO_LIMIT = 0.28
LINK_HEAVY_WORD_LIMIT = 120
MIN_MEANINGFUL_WORDS_TO_EXPAND = 50
LINK_FARM_MIN_LINKS = 80
LINK_FARM_WORD_LIMIT = 250
LINK_FARM_RATIO_LIMIT = 3.0
DOMINANT_TEMPLATE_MIN_LINKS = 25
DOMINANT_TEMPLATE_RATIO_LIMIT = 0.65
URL_TEMPLATE_SOFT_LIMIT = 80
EVENT_DETAIL_TEMPLATE_LIMIT = 50
EVENT_ARCHIVE_TEMPLATE_LIMIT = 5
WIKI_NAMESPACE_TEMPLATE_LIMIT = 40
QUERY_TEMPLATE_LIMIT = 20

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can't",
    "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "let's", "me", "more",
    "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd",
    "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd",
    "they'll", "they're", "they've", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd",
    "we'll", "we're", "we've", "were", "weren't", "what", "what's",
    "when", "when's", "where", "where's", "which", "while", "who",
    "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves",
}

DISALLOWED_EXTENSIONS = re.compile(
    r".*\.(css|js|bmp|gif|jpe?g|ico"
    + r"|png|tiff?|mid|mp2|mp3|mp4"
    + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
    + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
    + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
    + r"|epub|dll|cnf|tgz|sha1"
    + r"|thmx|mso|arff|rtf|jar|csv"
    + r"|rm|smil|wmv|swf|wma|zip|rar|gz"
    + r"|apk|war|img|sqlite|db|log|xml|json|rss|atom|sql"
    + r"|woff2?|ttf|eot|webm|opus|aac|flac|flv|txt|ff"
    + r"|ipynb|rdata|rds|mat|nb)$"
)

WORD_RE = re.compile(r"[a-zA-Z]+(?:'[a-zA-Z]+)?")
BAD_QUERY_KEYS = {
    "share",
    "replytocom",
    "ical",
    "calendar",
    "action",
    "print",
    "format",
    "output",
    "download",
    "eventdisplay",
    "ical",
    "outlook-ical",
    "tab_details",
    "tab_files",
    "author",
    "attachment_id",
    "idx",
    "next",
    "oldid",
    "rev",
    "revision",
    "skin",
    "style",
    "theme",
    "tok",
    "tribe-bar-date",
    "version",
}
BAD_PATH_PARTS = {
    "admin",
    "calendar",
    "events-calendar",
    "wp-json",
    "xmlrpc.php",
    "feed",
    "login",
    "rss",
    "atom",
    "wp-login.php",
}
WORDPRESS_ARCHIVE_PARTS = {
    "author",
    "tag",
    "tags",
}
DOKUWIKI_ACTIONS = {
    "admin",
    "backlink",
    "diff",
    "edit",
    "export",
    "export_pdf",
    "index",
    "login",
    "media",
    "recent",
    "revisions",
    "subscribe",
    "export_code",
}

_seen_pages = set()
_word_counts = Counter()
_subdomains = Counter()
_longest_page = ("", 0)
_analytics_loaded = False
_accepted_prefix_counts = Counter()
_accepted_template_counts = Counter()


def scraper(url, resp):
    page_url = canonicalize_url(getattr(resp, "url", url)) or canonicalize_url(url)
    words = extract_page_words(resp)
    if page_url and is_valid(page_url) and words:
        record_page(page_url, words)

    links = extract_next_links(url, resp)
    valid_links = [link for link in links if is_valid(link)]
    if not should_expand_page(page_url, words, valid_links):
        return []
    return [
        link for link in valid_links
        if accept_crawl_link(link)
    ]


def extract_next_links(url, resp):
    if not is_successful_html_response(resp):
        return []

    raw_response = getattr(resp, "raw_response", None)
    content = getattr(raw_response, "content", None)
    if not content:
        return []

    base_url = getattr(raw_response, "url", None) or getattr(resp, "url", None) or url
    try:
        soup = BeautifulSoup(content, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(content, "html.parser")
        except Exception:
            return []

    links = set()
    for anchor in soup.find_all("a", href=True):
        normalized = canonicalize_url(urljoin(base_url, anchor.get("href")))
        if normalized:
            links.add(normalized)
    return sorted(links)


def is_valid(url):
    try:
        normalized = canonicalize_url(url)
        if not normalized:
            return False

        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc.lower().split(":")[0] in BLOCKED_HOSTS:
            return False
        if not is_allowed_domain(parsed.netloc):
            return False
        if DISALLOWED_EXTENSIONS.match(parsed.path.lower()):
            return False
        if has_trap_pattern(parsed):
            return False
        if exceeds_prefix_budget(parsed):
            return False
        return True

    except TypeError:
        print("TypeError for ", url)
        raise


def canonicalize_url(url):
    if not url:
        return None

    url, _ = urldefrag(url.strip())
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parsed.path or "/"
    query = normalize_query(parsed.query)
    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_query(query):
    if not query:
        return ""

    params = parse_qsl(query, keep_blank_values=False)
    kept = []
    for key, value in params:
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in {"fbclid", "gclid"}:
            continue
        kept.append((key, value))
    return urlencode(sorted(kept), doseq=True)


def is_allowed_domain(netloc):
    host = netloc.split("@")[-1].split(":")[0].lower()
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)


def has_trap_pattern(parsed):
    path = parsed.path.lower()
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) > MAX_PATH_SEGMENTS:
        return True

    counts = Counter(segments)
    if counts and counts.most_common(1)[0][1] > MAX_REPEATED_PATH_SEGMENT:
        return True

    if any(part in BAD_PATH_PARTS for part in segments):
        return True

    if is_wordpress_archive_path(segments):
        return True

    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    if len(query_params) > MAX_QUERY_PARAMS:
        return True
    if any(key.lower() in BAD_QUERY_KEYS for key, _ in query_params):
        return True
    if is_apache_directory_sort(query_params):
        return True
    if is_dokuwiki_action_path(path, query_params):
        return True
    if is_dokuwiki_low_value_namespace(path):
        return True
    if is_status_dashboard_path(parsed, segments, query_params):
        return True
    if is_event_archive_path(segments, query_params):
        return True

    return False


def is_wordpress_archive_path(segments):
    if not segments:
        return False
    if segments[0] in WORDPRESS_ARCHIVE_PARTS:
        return True
    if "category" in segments:
        return True
    for index, segment in enumerate(segments[:-1]):
        if segment == "page" and segments[index + 1].isdigit():
            return True
    return False


def is_event_archive_path(segments, query_params):
    if not segments:
        return False

    query_keys = {key.lower() for key, _ in query_params}
    if any(key.startswith("tribe") for key in query_keys):
        return True

    if "outlook-ical" in query_keys:
        return True

    if segments[0] == "events":
        if len(segments) == 1:
            return False
        if segments[1] in {"list", "month", "week", "today", "tag", "category"}:
            return True
        if is_date_segment(segments[1]):
            return True

    return False


def is_date_segment(segment):
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", segment))


def is_dokuwiki_action_path(path, query_params):
    if "doku.php" not in path:
        return False
    for key, value in query_params:
        key_lower = key.lower()
        value_lower = value.lower()
        if key_lower in {"codeblock", "rev", "revision", "version"}:
            return True
        if key_lower == "do" and value_lower in DOKUWIKI_ACTIONS:
            return True
        if key_lower in {"image", "ns", "sectok"}:
            return True
    return False


def is_dokuwiki_low_value_namespace(path):
    page_id = dokuwiki_page_id(path)
    if not page_id:
        return False

    parts = [part for part in page_id.split(":") if part]
    if not parts:
        return False

    first = parts[0]
    if first in {"group", "wiki", "some", "playground"}:
        return True

    if parts[-1] in {"sidebar", "start"} and len(parts) > 1:
        return True

    if "old" in parts:
        return True

    return False


def dokuwiki_page_id(path):
    path = path.lower()
    marker = "/doku.php/"
    if marker not in path:
        return ""
    return path.split(marker, 1)[1].strip("/")


def is_apache_directory_sort(query_params):
    for key, value in query_params:
        key_lower = key.lower()
        value_lower = value.lower()
        if key_lower == "c":
            return True
        if key_lower == "o" and value_lower in {"a", "d"}:
            return True
    return False


def is_status_dashboard_path(parsed, segments, query_params):
    host = parsed.netloc.lower().split(":")[0]
    if not segments:
        return False

    first_segment = segments[0]
    query_keys = {key.lower() for key, _ in query_params}
    if first_segment in {"status", "phpfpm.php"}:
        return True

    if first_segment == "hub" and host != "hub.ics.uci.edu":
        return True

    dashboard_hosts = {"grafana.ics.uci.edu", "observium.ics.uci.edu"}
    if host in dashboard_hosts:
        return True

    if "skin" in query_keys and ("status" in segments or host.endswith(".ics.uci.edu")):
        return True

    return False


def exceeds_prefix_budget(parsed):
    prefix = prefix_key(parsed)
    if not prefix:
        return False
    return _accepted_prefix_counts[prefix] >= PREFIX_SOFT_LIMIT


def consume_prefix_budget(parsed):
    prefix = prefix_key(parsed)
    if prefix:
        _accepted_prefix_counts[prefix] += 1


def should_expand_page(url, words, links):
    if not url:
        return False

    normalized = canonicalize_url(url)
    if not normalized:
        return False

    if is_root_or_seed_page(normalized):
        return True

    meaningful = [word for word in words if word not in STOP_WORDS and len(word) > 1]
    if len(meaningful) < MIN_MEANINGFUL_WORDS_TO_EXPAND:
        return False

    if is_template_heavy(words):
        return False

    if is_link_farm(words, links):
        return False

    if has_dominant_link_template(links):
        return False

    return True


def is_root_or_seed_page(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    path = parsed.path.rstrip("/") or "/"
    return (
        path == "/"
        and not parsed.query
        and host in {
            "www.ics.uci.edu",
            "www.cs.uci.edu",
            "www.informatics.uci.edu",
            "www.stat.uci.edu",
            "cs.ics.uci.edu",
            "informatics.ics.uci.edu",
            "www.informatics.ics.uci.edu",
            "stat.ics.uci.edu",
            "ics.uci.edu",
            "cs.uci.edu",
            "informatics.uci.edu",
            "stat.uci.edu",
        }
    )


def is_template_heavy(words):
    if not words:
        return True

    template_tokens = template_noise_tokens()
    template_count = sum(1 for word in words if word in template_tokens)
    if len(words) <= LINK_HEAVY_WORD_LIMIT and template_count:
        return True
    return template_count / max(len(words), 1) > TEMPLATE_TOKEN_RATIO_LIMIT


def is_link_farm(words, links):
    if len(links) < LINK_FARM_MIN_LINKS:
        return False
    if len(words) <= LINK_HEAVY_WORD_LIMIT:
        return True
    return len(words) <= LINK_FARM_WORD_LIMIT and len(links) / max(len(words), 1) > LINK_FARM_RATIO_LIMIT


def has_dominant_link_template(links):
    if len(links) < DOMINANT_TEMPLATE_MIN_LINKS:
        return False

    templates = [url_template(link) for link in links]
    templates = [template for template in templates if template]
    if len(templates) < DOMINANT_TEMPLATE_MIN_LINKS:
        return False

    _, count = Counter(templates).most_common(1)[0]
    return count / len(templates) >= DOMINANT_TEMPLATE_RATIO_LIMIT


def exceeds_template_budget(url):
    template = url_template(url)
    if not template:
        return False
    return _accepted_template_counts[template] >= template_limit(template)


def consume_template_budget(url):
    template = url_template(url)
    if not template:
        return
    _accepted_template_counts[template] += 1


def accept_crawl_link(url):
    parsed = urlparse(url)
    if exceeds_prefix_budget(parsed) or exceeds_template_budget(url):
        return False

    consume_prefix_budget(parsed)
    consume_template_budget(url)
    return True


def template_limit(template):
    if "/event/*?" in template:
        return EVENT_DETAIL_TEMPLATE_LIMIT
    if "/events/" in template:
        return EVENT_ARCHIVE_TEMPLATE_LIMIT
    if "/doku.php/" in template:
        return WIKI_NAMESPACE_TEMPLATE_LIMIT
    if "?" in template and not template.endswith("?"):
        return QUERY_TEMPLATE_LIMIT
    return URL_TEMPLATE_SOFT_LIMIT


def url_template(url):
    normalized = canonicalize_url(url)
    if not normalized:
        return ""

    parsed = urlparse(normalized)
    host = parsed.netloc.lower().split(":")[0]
    raw_path = parsed.path.lower().strip("/")
    raw_parts = [part for part in re.split(r"[/:\s]+", raw_path) if part]
    path_parts = template_path_parts(host, raw_parts)
    if len(path_parts) > 5:
        path_parts = path_parts[:5]

    query_keys = sorted(key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True))
    return host + "/" + "/".join(path_parts) + "?" + "&".join(query_keys)


def template_path_parts(host, raw_parts):
    if not raw_parts:
        return []

    if raw_parts[0] == "event" and len(raw_parts) > 1:
        return ["event", "*"]

    if raw_parts[0] == "events":
        if len(raw_parts) > 1:
            if is_date_segment(raw_parts[1]):
                return ["events", "#date"]
            return ["events", raw_parts[1], "*"]
        return ["events"]

    if raw_parts[0] == "doku.php" and len(raw_parts) > 1:
        namespace_parts = [part for part in re.split(r":+", raw_parts[1]) if part]
        if namespace_parts:
            return ["doku.php", namespace_parts[0], "*"]
        return ["doku.php"]

    if raw_parts[0].startswith("~") and len(raw_parts) > 1:
        return [raw_parts[0], "*"]

    return [normalize_template_piece(part) for part in raw_parts]


def normalize_template_piece(piece):
    if piece.isdigit():
        return "#"
    if re.fullmatch(r"\d+\.[a-z0-9]+", piece):
        return "#." + piece.rsplit(".", 1)[1]
    if re.fullmatch(r"[0-9a-f]{8,}", piece):
        return "#"
    if re.fullmatch(r"[a-z]+[-_]?\d+", piece):
        return re.sub(r"\d+", "#", piece)
    if re.fullmatch(r".*\d{3,}.*", piece):
        return re.sub(r"\d+", "#", piece)
    return piece


def prefix_key(parsed):
    host = parsed.netloc.lower().split(":")[0]
    path = parsed.path.lower().strip("/")
    if not path:
        return host + "/"

    parts = [part for part in re.split(r"[/:\s]+", path) if part]
    if not parts:
        return host + "/"

    if parts[0] == "doku.php":
        return "/".join([host] + parts[:4])

    if parts[0].startswith("~") and len(parts) > 1:
        return "/".join([host] + parts[:3])

    return "/".join([host] + parts[:3])


def is_successful_html_response(resp):
    if getattr(resp, "status", None) != 200:
        return False

    raw_response = getattr(resp, "raw_response", None)
    if raw_response is None:
        return False

    headers = getattr(raw_response, "headers", {}) or {}
    content_type = headers.get("content-type", headers.get("Content-Type", "")).lower()
    if content_type and "html" not in content_type and "text/plain" not in content_type:
        return False

    return True


def extract_page_words(resp):
    if not is_successful_html_response(resp):
        return []

    raw_response = getattr(resp, "raw_response", None)
    content = getattr(raw_response, "content", None)
    if not content:
        return []
    if is_word_exported_html(content):
        return []

    try:
        soup = BeautifulSoup(content, "lxml")
    except Exception:
        soup = BeautifulSoup(content, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas", "code", "pre"]):
        tag.decompose()

    text = unescape(soup.get_text(" "))
    words = [word.lower() for word in WORD_RE.findall(text)]
    return words


def is_word_exported_html(content):
    sample = content[:20000]
    text_samples = []
    for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text_samples.append(sample.decode(encoding, errors="ignore").lower())
        except LookupError:
            continue

    byte_sample = sample.lower().replace(b"\x00", b"")
    byte_markers = (
        b"microsoft word",
        b"word.document",
        b"urn:schemas-microsoft-com:office:word",
        b"schemas-microsoft-com:vml",
        b"mso-",
        b"<w:worddocument",
        b"<o:documentproperties",
    )
    text_markers = tuple(marker.decode("ascii") for marker in byte_markers)
    return (
        any(marker in byte_sample for marker in byte_markers)
        or any(
            marker in text_sample
            for text_sample in text_samples
            for marker in text_markers
        )
    )


def record_page(url, words):
    global _longest_page

    load_existing_analytics()
    if url in _seen_pages:
        return

    _seen_pages.add(url)
    word_count = len(words)
    filtered_words = [word for word in words if word not in STOP_WORDS and len(word) > 1]

    subdomain = urlparse(url).netloc.lower().split(":")[0]
    _subdomains[subdomain] += 1
    if word_count > _longest_page[1]:
        _longest_page = (url, word_count)

    if should_count_words(url, words):
        _word_counts.update(filtered_words)

    os.makedirs(ANALYTICS_DIR, exist_ok=True)
    with open(PAGE_STATS_PATH, "a", encoding="utf-8") as page_stats:
        page_stats.write(json.dumps({"url": url, "word_count": word_count}) + "\n")
    write_summary_files()


def should_count_words(url, words):
    if len(words) < MIN_TEXT_WORDS_FOR_COUNTS:
        return False

    host = urlparse(url).netloc.lower().split(":")[0]
    if host in BLOCKED_HOSTS:
        return False

    template_count = sum(1 for word in words if word in template_noise_tokens())
    if len(words) <= LINK_HEAVY_WORD_LIMIT and template_count:
        return False
    return template_count / max(len(words), 1) <= TEMPLATE_TOKEN_RATIO_LIMIT


def template_noise_tokens():
    return {
        "backlinks",
        "credentials",
        "details",
        "doku",
        "export",
        "history",
        "log",
        "login",
        "manager",
        "media",
        "recent",
        "remember",
        "restricted",
        "revisions",
        "skin",
        "sitemap",
        "tools",
        "username",
        "wiki",
    }


def load_existing_analytics():
    global _analytics_loaded, _longest_page

    if _analytics_loaded:
        return
    _analytics_loaded = True

    if os.path.exists(WORD_COUNTS_PATH):
        with open(WORD_COUNTS_PATH, "r", encoding="utf-8") as word_counts_file:
            for line in word_counts_file:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 2:
                    continue
                word, count = parts
                try:
                    _word_counts[word] = int(count)
                except ValueError:
                    continue

    if not os.path.exists(PAGE_STATS_PATH):
        return

    with open(PAGE_STATS_PATH, "r", encoding="utf-8") as page_stats:
        for line in page_stats:
            try:
                page = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = page.get("url")
            word_count = page.get("word_count", 0)
            if not url or url in _seen_pages:
                continue
            _seen_pages.add(url)
            _subdomains[urlparse(url).netloc.lower().split(":")[0]] += 1
            if word_count > _longest_page[1]:
                _longest_page = (url, word_count)


def write_summary_files():
    with open(UNIQUE_URLS_PATH, "w", encoding="utf-8") as unique_urls_file:
        for url in sorted(_seen_pages):
            unique_urls_file.write(f"{url}\n")

    with open(WORD_COUNTS_PATH, "w", encoding="utf-8") as word_counts_file:
        for word, count in _word_counts.most_common():
            word_counts_file.write(f"{word}\t{count}\n")

    with open(SUBDOMAINS_PATH, "w", encoding="utf-8") as subdomains_file:
        for subdomain in sorted(_subdomains):
            subdomains_file.write(f"{subdomain}, {_subdomains[subdomain]}\n")

    with open(LONGEST_PAGE_PATH, "w", encoding="utf-8") as longest_page_file:
        longest_page_file.write(f"{_longest_page[0]}\t{_longest_page[1]}\n")
