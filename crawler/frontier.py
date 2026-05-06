"""
Thread-safe Frontier with per-domain politeness enforcement.

Key design decisions
--------------------
* A single RLock guards all mutations to self.save (shelve) and
  self.to_be_downloaded (deque).
* Per-domain last-access times are stored in self._domain_last_access,
  also protected by the same lock.
* get_tbd_url() will block (with a short sleep) until it either finds
  a URL whose domain is ready (i.e. last access was >= POLITENESS_DELAY
  ago), or the frontier is empty.
* POLITENESS_DELAY matches the assignment spec: 500 ms for multi-thread.
"""

import os
import shelve
import time
from collections import deque
from threading import RLock

from utils import get_logger, get_urlhash, normalize
from scraper import is_valid

# 500 ms between requests to the same domain (multi-thread politeness)
POLITENESS_DELAY = 0.5          # seconds
IDLE_SLEEP      = 0.05          # seconds to sleep when no URL is ready


def _domain_of(url: str) -> str:
    """Return the host (domain) of a URL, lower-cased."""
    from urllib.parse import urlparse
    return urlparse(url).netloc.lower().split(":")[0]


class Frontier:
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config

        self._lock = RLock()
        self.to_be_downloaded = deque()     # thread-safe append/popleft
        self._domain_last_access: dict[str, float] = {}   # domain -> timestamp

        if not os.path.exists(self.config.save_file) and not restart:
            self.logger.info(
                f"Did not find save file {self.config.save_file}, "
                f"starting from seed.")
        elif os.path.exists(self.config.save_file) and restart:
            self.logger.info(
                f"Found save file {self.config.save_file}, deleting it.")
            os.remove(self.config.save_file)

        self.save = shelve.open(self.config.save_file)

        with self._lock:
            if restart:
                for url in self.config.seed_urls:
                    self._add_url_locked(url)
            else:
                self._parse_save_file()
                if not self.save:
                    for url in self.config.seed_urls:
                        self._add_url_locked(url)

    # ------------------------------------------------------------------
    # Internal helpers (must be called with self._lock held)
    # ------------------------------------------------------------------

    def _parse_save_file(self):
        total_count = len(self.save)
        tbd_count = 0
        for url, completed in self.save.values():
            if not completed and is_valid(url):
                self.to_be_downloaded.append(url)
                tbd_count += 1
        self.logger.info(
            f"Found {tbd_count} urls to be downloaded from {total_count} "
            f"total urls discovered.")

    def _add_url_locked(self, url):
        """Add url without acquiring the lock (caller must hold it)."""
        url = normalize(url)
        urlhash = get_urlhash(url)
        if urlhash not in self.save:
            self.save[urlhash] = (url, False)
            self.save.sync()
            self.to_be_downloaded.append(url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tbd_url(self):
        """
        Return the next URL that is ready to be fetched (respecting
        per-domain politeness), or None when the frontier is empty.

        Blocks briefly (IDLE_SLEEP) when URLs exist but none are ready yet.
        """
        while True:
            with self._lock:
                if not self.to_be_downloaded:
                    return None     # truly empty

                now = time.time()
                # Scan for a URL whose domain is ready
                for _ in range(len(self.to_be_downloaded)):
                    url = self.to_be_downloaded[0]
                    domain = _domain_of(url)
                    last = self._domain_last_access.get(domain, 0.0)
                    if now - last >= POLITENESS_DELAY:
                        self.to_be_downloaded.popleft()
                        self._domain_last_access[domain] = now
                        return url
                    else:
                        # Move to end and try next
                        self.to_be_downloaded.rotate(-1)

                # All URLs are in cooldown — fall through to sleep
                # (lock released before sleeping)

            # Brief pause before re-checking
            time.sleep(IDLE_SLEEP)

    def add_url(self, url):
        with self._lock:
            self._add_url_locked(url)

    def mark_url_complete(self, url):
        with self._lock:
            urlhash = get_urlhash(url)
            if urlhash not in self.save:
                self.logger.error(
                    f"Completed url {url}, but have not seen it before.")
            self.save[urlhash] = (url, True)
            self.save.sync()