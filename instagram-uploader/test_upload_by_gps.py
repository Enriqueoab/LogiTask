#!/usr/bin/env python3
"""Offline tests for discovery, grouping, captions, and flags (no Instagram login)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from country_flags import country_flag, country_title
from upload_by_gps import (
    MediaItem,
    build_batches,
    build_caption,
    discover_media,
    parse_coords_from_name,
)


class FlagTests(unittest.TestCase):
    def test_spain_flag(self):
        self.assertEqual(country_flag("Spain"), "🇪🇸")
        self.assertIn("Spain", country_title("Spain"))
        self.assertTrue(country_title("Spain").startswith("🇪🇸"))


class CoordsTests(unittest.TestCase):
    def test_parse_plain(self):
        lat, lon, label = parse_coords_from_name("36.318189,-5.245317")
        self.assertAlmostEqual(lat, 36.318189)
        self.assertAlmostEqual(lon, -5.245317)
        self.assertEqual(label, "36.318189, -5.245317")

    def test_parse_collision_suffix(self):
        lat, lon, label = parse_coords_from_name("36.318189,-5.245317 (2)")
        self.assertAlmostEqual(lat, 36.318189)
        self.assertAlmostEqual(lon, -5.245317)
        self.assertEqual(label, "36.318189, -5.245317")


class DiscoverTests(unittest.TestCase):
    def test_country_state_city_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "Spain" / "Andalucia" / "Manilva"
            target.mkdir(parents=True)
            photo = target / "36.318189,-5.245317.JPG"
            photo.write_bytes(b"fake")

            items = discover_media(root, [".jpg", ".jpeg"], include_videos=False)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].country, "Spain")
            self.assertEqual(items[0].state, "Andalucia")
            self.assertEqual(items[0].city, "Manilva")
            self.assertAlmostEqual(items[0].lat, 36.318189)
            self.assertAlmostEqual(items[0].lon, -5.245317)


class CaptionBatchTests(unittest.TestCase):
    def test_per_city_batches_and_caption(self):
        items = [
            MediaItem(Path("a.jpg"), "Spain", "Andalucia", "Manilva", 36.3, -5.2),
            MediaItem(Path("b.jpg"), "Spain", "Andalucia", "Manilva", 36.4, -5.1),
            MediaItem(Path("c.jpg"), "France", "Provence", "Nice", 43.7, 7.2),
        ]
        batches = build_batches(items, "per-city", max_album_size=10)
        self.assertEqual(len(batches), 2)

        spain = next(b for b in batches if b.country == "Spain")
        caption = build_caption(spain, include_hashtags=True)
        self.assertIn("🇪🇸", caption)
        self.assertIn("Spain — Manilva", caption)
        self.assertIn("📍 Manilva · Andalucia · Spain", caption)
        self.assertIn("36.3, -5.2", caption)
        self.assertIn("#Spain", caption)

    def test_album_chunking(self):
        items = [
            MediaItem(Path(f"{i}.jpg"), "Spain", "Andalucia", "Manilva", 36.0 + i, -5.0)
            for i in range(12)
        ]
        batches = build_batches(items, "per-city", max_album_size=10)
        self.assertEqual(len(batches), 2)
        self.assertEqual(len(batches[0].items), 10)
        self.assertEqual(len(batches[1].items), 2)


if __name__ == "__main__":
    unittest.main()
