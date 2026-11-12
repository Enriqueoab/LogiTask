#!/usr/bin/env python3
"""
Upload photos/videos organized by Rename-ByGPS.ps1 to a personal Instagram account.

Expected folder layout (from Rename-ByGPS.ps1):
    <Folder>\\Spain\\Andalucia\\Manilva\\36.318189,-5.245317.JPG

Instagram has no real folders, so this script organizes the feed by:
  - grouping posts by country / city
  - putting a country flag + title in every caption
  - listing town / state and exact GPS coordinates
  - optionally tagging the Instagram place nearest to those coordinates

Modes:
  per-photo  one Instagram post per media file
  per-city   album posts grouped by Country/State/City (recommended)
  per-country album posts grouped by country (split into chunks of max_album_size)

Safe by default: dry_run=true until you flip it in config / CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from country_flags import country_title

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".mov"}
COORDS_RE = re.compile(
    r"^(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lon>-?\d+(?:\.\d+)?)"
    r"(?:\s*\(\d+\))?$",
    re.IGNORECASE,
)


@dataclass
class MediaItem:
    path: Path
    country: str
    state: str
    city: str
    lat: Optional[float]
    lon: Optional[float]
    coords_label: str = ""  # exact "lat,lon" text from the filename when present

    @property
    def place_label(self) -> str:
        bits = [p for p in (self.city, self.state) if p]
        return ", ".join(bits) if bits else self.country or "Unknown Location"

    @property
    def group_key_city(self) -> tuple[str, str, str]:
        return (self.country, self.state, self.city)

    @property
    def group_key_country(self) -> tuple[str]:
        return (self.country,)

    @property
    def coords_display(self) -> str:
        if self.coords_label:
            return self.coords_label
        if self.lat is None or self.lon is None:
            return ""
        return f"{self.lat}, {self.lon}"


@dataclass
class UploadBatch:
    key: tuple[str, ...]
    items: list[MediaItem] = field(default_factory=list)

    @property
    def country(self) -> str:
        return self.key[0] if self.key else "Unknown Location"

    @property
    def state(self) -> str:
        return self.key[1] if len(self.key) > 1 else ""

    @property
    def city(self) -> str:
        return self.key[2] if len(self.key) > 2 else ""


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def parse_coords_from_name(
    stem: str,
) -> tuple[Optional[float], Optional[float], str]:
    """
    Returns (lat, lon, label). label keeps the filename's exact coordinate text
    (without a collision suffix like ' (2)').
    """
    raw = stem.strip()
    match = COORDS_RE.match(raw)
    if not match:
        return None, None, ""
    lat = float(match.group("lat"))
    lon = float(match.group("lon"))
    label = f"{match.group('lat')}, {match.group('lon')}"
    return lat, lon, label


def discover_media(
    root: Path,
    extensions: Iterable[str],
    include_videos: bool,
) -> list[MediaItem]:
    """
    Walk Country[/State[/City]] trees produced by Rename-ByGPS.ps1.
    Depth can vary when a geocode level was missing.
    """
    wanted = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    if not include_videos:
        wanted -= VIDEO_EXTS

    items: list[MediaItem] = []
    root = root.resolve()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in wanted:
            continue

        rel = path.relative_to(root)
        parts = rel.parts
        if len(parts) < 2:
            # File still sitting in the root (not organized) — skip.
            continue

        folders = parts[:-1]

        # Rename-ByGPS uses country / state / city when all present.
        # With 1 folder: country only
        # With 2 folders: country / city (or country / state) — treat last as place
        # With 3+ folders: country / state / city [/...]
        if len(folders) == 1:
            country, state, city = folders[0], "", ""
        elif len(folders) == 2:
            country, state, city = folders[0], "", folders[1]
        else:
            country, state, city = folders[0], folders[1], folders[2]

        lat, lon, coords_label = parse_coords_from_name(path.stem)
        items.append(
            MediaItem(
                path=path,
                country=country,
                state=state,
                city=city,
                lat=lat,
                lon=lon,
                coords_label=coords_label,
            )
        )

    return items


def filter_items(
    items: list[MediaItem],
    only_countries: list[str],
    skip_countries: list[str],
    already: set[str],
) -> list[MediaItem]:
    only = {c.lower() for c in only_countries if c}
    skip = {c.lower() for c in skip_countries if c}
    out: list[MediaItem] = []
    for item in items:
        key = str(item.path.resolve())
        if key in already:
            continue
        c = item.country.lower()
        if only and c not in only:
            continue
        if c in skip:
            continue
        out.append(item)
    return out


def chunked(seq: list[MediaItem], size: int) -> list[list[MediaItem]]:
    if size <= 0:
        size = 10
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def build_batches(
    items: list[MediaItem],
    mode: str,
    max_album_size: int,
) -> list[UploadBatch]:
    mode = mode.lower().strip()
    batches: list[UploadBatch] = []

    if mode == "per-photo":
        for item in items:
            key = (item.country, item.state, item.city, item.path.name)
            batches.append(UploadBatch(key=key, items=[item]))
        return batches

    groups: dict[tuple[str, ...], list[MediaItem]] = {}
    for item in items:
        key = item.group_key_country if mode == "per-country" else item.group_key_city
        groups.setdefault(key, []).append(item)

    for key in sorted(groups.keys(), key=lambda k: tuple(x.lower() for x in k)):
        for part in chunked(groups[key], max_album_size):
            batches.append(UploadBatch(key=key, items=part))
    return batches


def hashtagize(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", text)
    return f"#{cleaned}" if cleaned else ""


def build_caption(
    batch: UploadBatch,
    include_hashtags: bool,
) -> str:
    country = batch.country
    title = country_title(country)

    # Title line: flag + country (or "Spain — Manilva" when city mode)
    if batch.city:
        headline = f"{title} — {batch.city}"
    elif batch.state:
        headline = f"{title} — {batch.state}"
    else:
        headline = title

    lines = [headline, ""]

    place_bits = [p for p in (batch.city, batch.state, country) if p]
    if place_bits:
        lines.append(f"📍 {' · '.join(place_bits)}")

    # Exact coordinates for every media in the batch (filename text preferred)
    coord_lines: list[str] = []
    for item in batch.items:
        display = item.coords_display
        if not display:
            continue
        coord_lines.append(f"🗺️ {display}")
    # Deduplicate identical coords while preserving order
    seen: set[str] = set()
    unique_coords: list[str] = []
    for line in coord_lines:
        if line not in seen:
            seen.add(line)
            unique_coords.append(line)

    if unique_coords:
        lines.append("")
        # Keep captions readable: show up to 5 exact points, then a count.
        if len(unique_coords) <= 5:
            lines.extend(unique_coords)
        else:
            lines.extend(unique_coords[:5])
            lines.append(f"… +{len(unique_coords) - 5} more locations")

    if include_hashtags:
        tags = []
        for part in (country, batch.state, batch.city, "Travel", "Drone", "Photography"):
            tag = hashtagize(part)
            if tag and tag not in tags:
                tags.append(tag)
        if tags:
            lines.append("")
            lines.append(" ".join(tags))

    caption = "\n".join(lines).strip()
    # Instagram caption hard limit is ~2200 chars
    return caption[:2200]


def resolve_location(client: Any, item: MediaItem):
    """Best-effort Instagram place nearest to the photo's GPS."""
    if item.lat is None or item.lon is None:
        return None
    try:
        from instagrapi.types import Location

        results = client.location_search(item.lat, item.lon)
        if results:
            return results[0]
        return Location(
            name=item.place_label,
            lat=item.lat,
            lng=item.lon,
        )
    except Exception as exc:  # noqa: BLE001 - network / API quirks
        print(f"  ! location lookup failed for {item.path.name}: {exc}")
        return None


def login_client(username: str, password: str, session_file: Path):
    from instagrapi import Client
    from instagrapi.exceptions import LoginRequired

    cl = Client()
    cl.delay_range = [1, 3]

    if session_file.exists():
        try:
            cl.load_settings(str(session_file))
        except Exception as exc:  # noqa: BLE001
            print(f"Could not load session ({exc}); logging in fresh.")

    try:
        cl.login(username, password)
    except LoginRequired:
        print("Saved session expired; logging in again…")
        if session_file.exists():
            session_file.unlink()
        cl = Client()
        cl.delay_range = [1, 3]
        cl.login(username, password)

    cl.dump_settings(str(session_file))
    return cl


def upload_batch(
    client: Any,
    batch: UploadBatch,
    tag_location: bool,
    include_hashtags: bool = True,
) -> Any:
    paths = [item.path for item in batch.items]
    caption = build_caption(batch, include_hashtags=include_hashtags)
    location = None
    if tag_location:
        location = resolve_location(client, batch.items[0])

    if len(paths) == 1:
        path = paths[0]
        ext = path.suffix.lower()
        if ext in VIDEO_EXTS:
            return client.video_upload(path, caption=caption, location=location)
        return client.photo_upload(path, caption=caption, location=location)

    return client.album_upload(paths, caption=caption, location=location)


def print_batch_plan(batch: UploadBatch, caption: str) -> None:
    print("-" * 60)
    print(f"Country : {country_title(batch.country)}")
    if batch.state:
        print(f"State   : {batch.state}")
    if batch.city:
        print(f"City    : {batch.city}")
    print(f"Files   : {len(batch.items)}")
    for item in batch.items:
        coords = item.coords_display or "no-coords"
        print(f"  - {item.path}  ({coords})")
    print("Caption preview:")
    for line in caption.splitlines():
        print(f"  | {line}")


def merge_config(defaults: dict[str, Any], file_cfg: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    cfg = dict(defaults)
    cfg.update({k: v for k, v in file_cfg.items() if v is not None})

    cli_map = {
        "folder": args.folder,
        "username": args.username,
        "password": args.password,
        "session_file": args.session_file,
        "state_file": args.state_file,
        "mode": args.mode,
        "delay_seconds": args.delay_seconds,
        "max_album_size": args.max_album_size,
        "limit": args.limit,
    }
    for key, value in cli_map.items():
        if value is not None:
            cfg[key] = value

    if args.dry_run:
        cfg["dry_run"] = True
    if args.upload:
        cfg["dry_run"] = False
    if args.no_location:
        cfg["tag_location"] = False
    if args.only_country:
        cfg["only_countries"] = list(args.only_country)
    if args.skip_country:
        cfg["skip_countries"] = list(args.skip_country)

    return cfg


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Upload Rename-ByGPS organized media to Instagram, grouped by country/city."
    )
    p.add_argument("--config", default="config.json", help="Path to config JSON")
    p.add_argument("--folder", help="Root folder with Country\\State\\City layout")
    p.add_argument("--username", help="Instagram username (or set IG_USERNAME)")
    p.add_argument("--password", help="Instagram password (or set IG_PASSWORD)")
    p.add_argument("--session-file", help="Path to session settings JSON")
    p.add_argument("--state-file", help="Path to upload state JSON")
    p.add_argument(
        "--mode",
        choices=["per-photo", "per-city", "per-country"],
        help="How to group posts",
    )
    p.add_argument("--dry-run", action="store_true", help="Plan only; do not upload")
    p.add_argument("--upload", action="store_true", help="Actually upload (overrides dry_run)")
    p.add_argument("--delay-seconds", type=int, help="Pause between posts")
    p.add_argument("--max-album-size", type=int, help="Max media per album (Instagram max 10)")
    p.add_argument("--limit", type=int, help="Upload at most N batches this run (0 = all)")
    p.add_argument("--only-country", action="append", help="Only this country (repeatable)")
    p.add_argument("--skip-country", action="append", help="Skip this country (repeatable)")
    p.add_argument("--no-location", action="store_true", help="Do not tag Instagram locations")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config_path = Path(args.config)
    file_cfg = load_json(config_path, {}) if config_path.exists() else {}

    defaults = {
        "folder": "",
        "username": os.environ.get("IG_USERNAME", ""),
        "password": os.environ.get("IG_PASSWORD", ""),
        "session_file": "instagram_session.json",
        "state_file": "upload_state.json",
        "mode": "per-city",
        "dry_run": True,
        "delay_seconds": 90,
        "max_album_size": 10,
        "include_videos": True,
        "extensions": [".jpg", ".jpeg", ".png", ".mp4", ".mov"],
        "caption_hashtags": True,
        "tag_location": True,
        "only_countries": [],
        "skip_countries": [],
        "limit": 0,
    }
    cfg = merge_config(defaults, file_cfg, args)

    folder = Path(cfg["folder"]) if cfg.get("folder") else None
    if not folder or not folder.exists():
        print(
            "ERROR: Set 'folder' in config.json or pass --folder to your "
            "Rename-ByGPS output directory.",
            file=sys.stderr,
        )
        return 1

    max_album = min(int(cfg.get("max_album_size") or 10), 10)
    state_path = Path(cfg["state_file"])
    state = load_json(state_path, {"uploaded": {}, "history": []})
    already = set(state.get("uploaded", {}).keys())

    items = discover_media(folder, cfg.get("extensions", []), bool(cfg.get("include_videos", True)))
    items = filter_items(
        items,
        list(cfg.get("only_countries") or []),
        list(cfg.get("skip_countries") or []),
        already,
    )
    batches = build_batches(items, str(cfg.get("mode") or "per-city"), max_album)

    limit = int(cfg.get("limit") or 0)
    if limit > 0:
        batches = batches[:limit]

    print(f"Root folder : {folder}")
    print(f"Mode        : {cfg.get('mode')}")
    print(f"Dry run     : {cfg.get('dry_run')}")
    print(f"Pending media files : {sum(len(b.items) for b in batches)}")
    print(f"Pending posts/batches: {len(batches)}")
    if not batches:
        print("Nothing to upload.")
        return 0

    # Always show the plan first
    for batch in batches:
        caption = build_caption(batch, include_hashtags=bool(cfg.get("caption_hashtags", True)))
        print_batch_plan(batch, caption)

    if cfg.get("dry_run", True):
        print("\nDry run only. Re-run with --upload (or set dry_run=false) to publish.")
        return 0

    username = cfg.get("username") or os.environ.get("IG_USERNAME", "")
    password = cfg.get("password") or os.environ.get("IG_PASSWORD", "")
    if not username or not password:
        print(
            "ERROR: Instagram username/password required via config, "
            "--username/--password, or IG_USERNAME / IG_PASSWORD.",
            file=sys.stderr,
        )
        return 1

    try:
        client = login_client(username, password, Path(cfg["session_file"]))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Instagram login failed: {exc}", file=sys.stderr)
        print(
            "Tip: complete any Instagram security challenge in the official app, "
            "then retry. Prefer session reuse via session_file.",
            file=sys.stderr,
        )
        return 1

    delay = max(0, int(cfg.get("delay_seconds") or 0))
    tag_location = bool(cfg.get("tag_location", True))
    include_hashtags = bool(cfg.get("caption_hashtags", True))

    for index, batch in enumerate(batches, start=1):
        print(f"\n[{index}/{len(batches)}] Uploading {country_title(batch.country)} "
              f"({len(batch.items)} file(s))…")
        try:
            media = upload_batch(
                client,
                batch,
                tag_location=tag_location,
                include_hashtags=include_hashtags,
            )
            code = getattr(media, "code", None)
            pk = getattr(media, "pk", None)
            print(f"  OK → https://www.instagram.com/p/{code}/" if code else f"  OK → pk={pk}")

            now = datetime.now(timezone.utc).isoformat()
            for item in batch.items:
                key = str(item.path.resolve())
                state.setdefault("uploaded", {})[key] = {
                    "media_pk": str(pk) if pk is not None else None,
                    "code": code,
                    "country": item.country,
                    "city": item.city,
                    "uploaded_at": now,
                }
            state.setdefault("history", []).append(
                {
                    "uploaded_at": now,
                    "country": batch.country,
                    "state": batch.state,
                    "city": batch.city,
                    "files": [str(i.path) for i in batch.items],
                    "code": code,
                }
            )
            save_json(state_path, state)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}", file=sys.stderr)
            save_json(state_path, state)
            print("Stopping so you can fix the issue and resume safely.")
            return 2

        if index < len(batches) and delay:
            print(f"  Waiting {delay}s before next post (rate-limit friendly)…")
            time.sleep(delay)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
