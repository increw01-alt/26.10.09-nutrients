"""릴리스 서명·버전 설정 검사(app/android/app/build.gradle, app/package.json, .gitignore). 실행: python -m unittest tests.test_android_gradle -v"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADLE = (ROOT / "app/android/app/build.gradle").read_text(encoding="utf-8")
ENV_VARS = ("ANDROID_KEYSTORE_PATH", "ANDROID_KEYSTORE_PASSWORD", "ANDROID_KEY_ALIAS", "ANDROID_KEY_PASSWORD")


class GradleTests(unittest.TestCase):
    def test_signing_reads_env_only_and_has_no_literal_secret(self):
        for var in ENV_VARS:
            self.assertIn('System.getenv("%s")' % var, GRADLE)
        self.assertIn("signingConfigs.release", GRADLE)
        self.assertNotRegex(GRADLE, re.compile(r'(storePassword|keyPassword)\s+"'))

    def test_version_comes_from_gradle_properties_with_defaults(self):
        self.assertIn('findProperty("versionCode")', GRADLE)
        self.assertIn('findProperty("versionName")', GRADLE)
        self.assertNotRegex(GRADLE, re.compile(r"^\s*versionCode\s+\d", re.M))   # 숫자 하드코딩 금지

    def test_package_version_is_semver(self):
        v = json.loads((ROOT / "app/package.json").read_text(encoding="utf-8"))["version"]
        self.assertRegex(v, r"^\d+\.\d+\.\d+$")

    def test_keystores_are_gitignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for pat in ("*.jks", "*.keystore", "*.b64"):
            self.assertIn(pat, lines)
