"""CLI tool for agents to fetch URL content with tiered fallback.

Usage:
    python -m multi_agent_flow.fetch_source "https://example.com/article" /path/to/sources/source-001.md
    python -m multi_agent_flow.fetch_source "https://example.com/article" /path/to/sources/source-001.md --snippet "fallback text"
    python -m multi_agent_flow.fetch_source --prefetch-site "https://docs.example.com" /path/to/prefetched-sites/

Tiered fallback chain (first success wins):
  1. Direct HTTP (urllib)
  2. wget
  3. Jina Reader (r.jina.ai)
  4. Google Cache
  5. Wayback Machine
  6. Snippet fallback (--snippet)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote as urlquote
from urllib.request import Request, urlopen

_MAX_RESPONSE_BYTES = 1_048_576  # 1 MB
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ── HTML-to-text converter ───────────────────────────────────────────

_SKIP_TAGS = frozenset({"script", "style", "noscript", "svg", "head"})
_BLOCK_TAGS = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "br", "tr", "blockquote", "pre", "section",
    "article", "header", "footer", "nav", "main",
})


class _HTMLToText(HTMLParser):
    """Minimal HTML→plain-text converter using only stdlib."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and tag_lower in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth == 0 and tag_lower in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)


def _html_to_text(html: str) -> str:
    parser = _HTMLToText()
    parser.feed(html)
    text = "".join(parser._parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Fetch tiers ──────────────────────────────────────────────────────


def _read_response(resp: object, max_bytes: int = _MAX_RESPONSE_BYTES) -> bytes:
    """Read up to max_bytes from an HTTP response."""
    return resp.read(max_bytes)  # type: ignore[union-attr]


def _fetch_direct(url: str) -> str | None:
    """Tier 1: Direct HTTP via urllib."""
    try:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            raw = _read_response(resp)
        return _html_to_text(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


def _fetch_wget(url: str) -> str | None:
    """Tier 2: wget — handles redirects, cookies, challenge-response better."""
    try:
        result = subprocess.run(
            ["wget", "-q", "-O", "-", f"--user-agent={_USER_AGENT}", url],
            capture_output=True,
            timeout=20,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        raw = result.stdout[:_MAX_RESPONSE_BYTES]
        return _html_to_text(raw.decode("utf-8", errors="replace"))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _fetch_jina(url: str) -> str | None:
    """Tier 3: Jina Reader — returns markdown directly."""
    try:
        jina_url = f"https://r.jina.ai/{url}"
        req = Request(jina_url, headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/markdown",
        })
        with urlopen(req, timeout=30) as resp:
            raw = _read_response(resp)
        return raw.decode("utf-8", errors="replace").strip()
    except Exception:
        return None


def _fetch_google_cache(url: str) -> str | None:
    """Tier 4: Google Cache."""
    try:
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{urlquote(url, safe='')}"
        req = Request(cache_url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            raw = _read_response(resp)
        return _html_to_text(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


def _fetch_wayback(url: str) -> str | None:
    """Tier 5: Wayback Machine."""
    try:
        wayback_url = f"https://web.archive.org/web/{url}"
        req = Request(wayback_url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            raw = _read_response(resp)
        return _html_to_text(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


# ── Tier names for metadata ──────────────────────────────────────────

_TIERS: list[tuple[str, object]] = [
    ("direct", _fetch_direct),
    ("wget", _fetch_wget),
    ("jina", _fetch_jina),
    ("google_cache", _fetch_google_cache),
    ("wayback", _fetch_wayback),
]


def fetch_with_fallback(url: str, snippet: str | None = None) -> tuple[str, str]:
    """Try each fetch tier in order. Returns (content, tier_name)."""
    for tier_name, fetch_fn in _TIERS:
        content = fetch_fn(url)
        if content and len(content.strip()) > 50:
            return content, tier_name

    if snippet and snippet.strip():
        return snippet.strip(), "snippet"

    return f"[Failed to fetch: {url}]", "failed"


# ── Site pre-fetch for deep research ─────────────────────────────────


def prefetch_site(url: str, dest_dir: str) -> str:
    """Download an entire site recursively via wget for local access.

    Returns the domain-specific subdirectory path.
    """
    from urllib.parse import urlparse

    domain = urlparse(url).netloc or "site"
    site_dir = Path(dest_dir) / domain
    site_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "wget", "-r", "-p", "-k",
                "-l", "3",
                "-e", "robots=off",
                "--convert-links",
                "-U", _USER_AGENT,
                "-P", str(site_dir),
                "--no-verbose",
                url,
            ],
            capture_output=True,
            timeout=300,  # 5 min max for recursive crawl
        )
        # Count downloaded files
        count = sum(1 for _ in site_dir.rglob("*") if _.is_file())
        print(f"Pre-fetched {count} files from {domain} into {site_dir}")
    except subprocess.TimeoutExpired:
        count = sum(1 for _ in site_dir.rglob("*") if _.is_file())
        print(f"Pre-fetch timed out after 5 min. Captured {count} files from {domain}.")
    except FileNotFoundError:
        print("Warning: wget not found. Skipping site pre-fetch.", file=sys.stderr)

    return str(site_dir)


# ── Path validation ──────────────────────────────────────────────────


def _validate_path(dest: Path) -> bool:
    """Validate output path is within a .maf/tasks directory."""
    parts = dest.parts
    if ".maf" not in parts or "tasks" not in parts:
        print(
            f"Error: path must be within a .maf/tasks directory: {dest}",
            file=sys.stderr,
        )
        return False
    if ".." in parts:
        print("Error: path must not contain '..'", file=sys.stderr)
        return False
    return True


# ── CLI entry point ──────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch URL content with tiered fallback.",
    )
    parser.add_argument("url", nargs="?", help="URL to fetch")
    parser.add_argument("path", nargs="?", help="Destination file path for fetched content")
    parser.add_argument(
        "--snippet",
        help="Fallback search snippet if all fetch tiers fail",
    )
    parser.add_argument(
        "--prefetch-site",
        metavar="URL",
        help="Recursively download an entire site for local access",
    )
    parser.add_argument(
        "--prefetch-dest",
        metavar="DIR",
        help="Destination directory for --prefetch-site",
    )
    args = parser.parse_args()

    # ── prefetch-site mode ──
    if args.prefetch_site:
        dest = args.prefetch_dest or args.path
        if not dest:
            print("Error: --prefetch-site requires a destination directory (positional or --prefetch-dest)", file=sys.stderr)
            return 1
        dest_path = Path(dest).resolve()
        if not _validate_path(dest_path):
            return 1
        site_path = prefetch_site(args.prefetch_site, dest)
        print(site_path)
        return 0

    # ── single-URL mode ──
    if not args.url or not args.path:
        parser.print_help()
        return 1

    dest = Path(args.path).resolve()
    if not _validate_path(dest):
        return 1

    content, tier = fetch_with_fallback(args.url, args.snippet)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")

    meta = {
        "url": args.url,
        "fetch_tier": tier,
        "size_bytes": len(content.encode("utf-8")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = dest.with_name(dest.stem + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Fetched ({tier}): {dest} ({meta['size_bytes']} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
