"""안드로이드 매니페스트(app/android/app/src/main/AndroidManifest.xml) 검사. 실행: python -m unittest tests.test_android_manifest -v"""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = "{http://schemas.android.com/apk/res/android}"
TOOLS = "{http://schemas.android.com/tools}"


class ManifestTests(unittest.TestCase):
    def setUp(self):
        root = ET.parse(ROOT / "app/android/app/src/main/AndroidManifest.xml").getroot()
        self.perms = {p.get(ANDROID + "name"): p for p in root.findall("uses-permission")}

    def test_exact_alarm_permissions_are_removed_from_merged_manifest(self):
        for name in ("android.permission.SCHEDULE_EXACT_ALARM", "android.permission.USE_EXACT_ALARM"):
            self.assertIn(name, self.perms)
            self.assertEqual(self.perms[name].get(TOOLS + "node"), "remove")

    def test_internet_permission_kept(self):
        self.assertIn("android.permission.INTERNET", self.perms)
        self.assertIsNone(self.perms["android.permission.INTERNET"].get(TOOLS + "node"))
