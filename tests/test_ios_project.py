"""iOS 프로젝트(app/ios) 설정 검사. 실행: python -m unittest tests.test_ios_project -v"""
import json
import plistlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "app/ios/App"
PBX = IOS / "App.xcodeproj/project.pbxproj"


class IosProjectTests(unittest.TestCase):
    def test_package_has_ios_platform_and_assets_flag(self):
        pkg = json.loads((ROOT / "app/package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["dependencies"]["@capacitor/ios"], pkg["dependencies"]["@capacitor/core"])
        self.assertIn("--ios", pkg["scripts"]["assets"])

    def test_info_plist_name_and_export_compliance(self):
        with open(IOS / "App/Info.plist", "rb") as f:
            info = plistlib.load(f)
        self.assertEqual(info["CFBundleDisplayName"], "영양제.kr")
        self.assertIs(info["ITSAppUsesNonExemptEncryption"], False)   # HTTPS 만 써 수출 규정 질문 생략
        self.assertEqual(info["CFBundleShortVersionString"], "$(MARKETING_VERSION)")
        self.assertEqual(info["CFBundleVersion"], "$(CURRENT_PROJECT_VERSION)")

    def test_project_bundle_id_and_device_family(self):
        pbx = PBX.read_text(encoding="utf-8")
        self.assertIn("PRODUCT_BUNDLE_IDENTIFIER = kr.yeongyangje.app;", pbx)
        self.assertRegex(pbx, r'TARGETED_DEVICE_FAMILY = "1,2";')   # 아이폰 + 아이패드

    def test_privacy_manifest_is_in_project(self):
        with open(IOS / "App/PrivacyInfo.xcprivacy", "rb") as f:
            pm = plistlib.load(f)
        self.assertIs(pm["NSPrivacyTracking"], False)
        cats = {a["NSPrivacyAccessedAPIType"]: a["NSPrivacyAccessedAPITypeReasons"] for a in pm["NSPrivacyAccessedAPITypes"]}
        self.assertEqual(cats["NSPrivacyAccessedAPICategoryUserDefaults"], ["CA92.1"])
        pbx = PBX.read_text(encoding="utf-8")
        self.assertTrue("PrivacyInfo.xcprivacy" in pbx or "PBXFileSystemSynchronizedRootGroup" in pbx)   # 프로젝트에 등록돼야 번들에 실림

    def test_app_icon_source_exists(self):
        icons = list((IOS / "App/Assets.xcassets/AppIcon.appiconset").glob("*.png"))
        self.assertTrue(icons)

    def test_app_bound_domains_enable_service_worker(self):
        # WKWebView 는 App-Bound Domains 를 선언한 앱에서만 서비스워커를 허용한다(오프라인 '최근 본 페이지'·offline.html). localhost 는 errorPath(capacitor://localhost)용
        with open(IOS / "App/Info.plist", "rb") as f:
            info = plistlib.load(f)
        self.assertEqual(info["WKAppBoundDomains"], ["xn--og5b1hx9c.kr", "localhost"])
        cfg = json.loads((ROOT / "app/capacitor.config.json").read_text(encoding="utf-8"))
        self.assertIs(cfg["ios"]["limitsNavigationsToAppBoundDomains"], True)
