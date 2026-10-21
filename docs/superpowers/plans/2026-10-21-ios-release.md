# 계획 5 — iOS 앱: Capacitor iOS 프로젝트, GitHub Actions macOS 빌드·서명·TestFlight 업로드, App Store 등록 준비

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mac 없이 iOS 앱을 만든다 — Capacitor iOS 프로젝트를 저장소에 넣고, GitHub Actions macOS 러너가 (서명 없이) 컴파일을 검증하며, App Store Connect API 키가 등록되면 같은 러너가 서명·IPA 생성·TestFlight 업로드까지 하고, 사용자가 App Store Connect 에서 심사를 제출할 수 있는 문서·문구·스크린샷 규격을 갖춘다.

**Architecture:** `npx cap add ios --packagemanager SPM` 으로 만든 `app/ios/` 를 커밋한다(CocoaPods 없음 → 러너 준비가 단순). 워크플로 둘: `build-ios.yml` 은 서명 없는 아카이브로 컴파일·번들 내용(Info.plist·PrivacyInfo)을 검사하고 지금 바로 돌 수 있다. `release-ios.yml` 은 Secrets 4개(App Store Connect API 키·팀 ID)가 있을 때만 `xcodebuild -allowProvisioningUpdates` 자동 서명(클라우드 관리 배포 인증서 — 로컬 인증서·Mac 불필요)으로 아카이브 → IPA 내보내기 → `xcrun altool --upload-app` 으로 TestFlight 업로드. 버전은 `MARKETING_VERSION` = `app/package.json` version, `CURRENT_PROJECT_VERSION` = 워크플로 실행 번호. 스토어 그래픽 스크립트에 아이폰·아이패드 규격을 더하고, 절차 문서·문구는 안드로이드와 같은 틀로 둔다.

**Tech Stack:** Capacitor 8.5.3(`@capacitor/ios`), SPM 템플릿(`capacitor-swift-pm` 8, iOS 15+), GitHub Actions `macos-latest`(macOS 26·Xcode 26.x — Capacitor 8 은 Xcode 26 이상 필요), xcodebuild 자동 서명(API 키), altool, @capacitor/assets(`--ios`), Pillow, Python unittest.

**Spec:** `docs/superpowers/specs/2026-10-20-mobile-app-reminders-design.md` — 3절 제약(Mac 없음, 아이폰·아이패드, macOS 러너), 6절(iOS 빌드 = GitHub Actions macOS 러너 + App Store Connect API 키 → TestFlight; 애플 개발자 프로그램은 사용자), 8절(iOS 반복 알림 64개 상한), 9절 5단계.

## Global Constraints

- 앱 이름 "영양제.kr", 번들 ID `kr.yeongyangje.app`(안드로이드와 동일, 스펙 7절). 아이폰·아이패드 모두 지원(`TARGETED_DEVICE_FAMILY` 1,2 유지 — 스펙 "아이폰·아이패드로 테스트").
- Mac 없음: iOS 프로젝트 생성은 윈도우에서(`cap add ios` 는 템플릿 복사), 컴파일·서명·업로드는 GitHub Actions macOS 러너에서만. 공개 저장소라 macOS 러너 무료(스펙 6절).
- API 키·팀 ID 는 GitHub Secrets 에만: `ASC_KEY_ID`·`ASC_ISSUER_ID`·`ASC_PRIVATE_KEY_BASE64`(.p8 내용 base64)·`APPLE_TEAM_ID`. 값은 저장소·문서·채팅에 나타나지 않는다. 키 역할은 **Admin**(App Manager 는 클라우드 서명 권한 오류 — 애플 포럼 다수 보고).
- 1차 iOS 앱도 쇼핑 버튼 숨김(`appShopping: false`), 회원가입 없음, 건강 표현은 식약처 범위(CLAUDE.md).
- 생성 파일은 손대지 않는다. `app/ios/` 는 생성물이지만 커밋하며, `Info.plist`·`project.pbxproj`·`PrivacyInfo.xcprivacy` 는 `cap sync` 가 덮어쓰지 않으므로 직접 고친다. `app/ios/App/App/public/`·`capacitor.config.json` 은 `cap sync` 산출물이라 커밋하지 않는다(템플릿 .gitignore).
- iOS 알림: 플러그인은 iOS 에서 `allowWhileIdle`·`smallIcon`·정확 알람 설정을 무시하고 캘린더 트리거로 반복한다. 예약 수는 6 시간대 × 최대 7(매일 1 또는 평일 5) + 30분 뒤 6 ≤ 42 로 iOS 상한 64 안(스펙 8절). JS 변경 없음.
- 수출 규정: HTTPS 만 쓰므로 `ITSAppUsesNonExemptEncryption` = false 를 Info.plist 에 둬 TestFlight 빌드마다 묻는 질문을 없앤다.
- 응답·커밋 메시지는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. API 키 역할이 Admin 이 아니면 서명 단계가 "Cloud signing permission error" 로 실패한다 → 문서가 Admin 을 명시 (Task 5 `test_doc_requires_admin_key_role`).
2. `PrivacyInfo.xcprivacy` 를 만들어도 Xcode 프로젝트(pbxproj)에 등록되지 않으면 번들에 실리지 않아 심사에서 경고 → pbxproj 참조 검사(Task 1 `test_privacy_manifest_is_in_project`) + 서명 없는 아카이브의 번들 안에 파일이 있는지 CI 검사(Task 2 '번들 검사').
3. 아이폰 캡처(1170×2532 등)를 그대로 올리면 App Store Connect 가 크기 오류로 거부 → 6.5형 1284×2778·아이패드 13형 2064×2752 로 맞춤 (Task 4 `test_ios_phone_and_pad_screens_fit`).
4. 매 TestFlight 빌드마다 '수출 규정 준수' 질문이 떠 테스터 배포가 막힌다 → Info.plist 키 (Task 1 `test_info_plist_name_and_export_compliance`).
5. 문서의 Secrets 이름과 워크플로가 읽는 이름이 다르면 등록해도 실패 → 대조 (Task 5 `test_secret_names_match_workflow`).
6. `altool` 은 `--apiKey` 를 받아도 키 파일을 `~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8` 에서 찾으므로 다른 경로에 두면 "key not found" → 워크플로가 그 경로에 둔다(Task 3 Step 1 에 고정, 실제 실행은 API 키 등록 뒤).

---

### Task 1: iOS 플랫폼 추가와 앱 설정(표시 이름·수출 규정·프라이버시 매니페스트·아이콘)

**Files:**
- Modify: `app/package.json` (`dependencies` 에 `"@capacitor/ios": "8.5.3"`, `assets` 스크립트에 `--ios` 추가, `sync` 를 `cap sync` 로)
- Create(생성·커밋): `app/ios/**` (`npx cap add ios --packagemanager SPM`), `app/ios/App/App/Assets.xcassets/**`(@capacitor/assets)
- Modify: `app/ios/App/App/Info.plist` (`CFBundleDisplayName` 영양제.kr, `ITSAppUsesNonExemptEncryption` false)
- Create: `app/ios/App/App/PrivacyInfo.xcprivacy` + `app/ios/App/App.xcodeproj/project.pbxproj` 에 참조(동기화 그룹이면 불필요)
- Test: `tests/test_ios_project.py`

**Interfaces:**
- Consumes: 없음
- Produces: Xcode 프로젝트 `app/ios/App/App.xcodeproj`, 스킴 `App`, 번들 ID `kr.yeongyangje.app`, 빌드 설정 `MARKETING_VERSION`·`CURRENT_PROJECT_VERSION`(Info.plist 가 참조) — Task 2·3 의 xcodebuild 가 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""iOS 프로젝트(app/ios) 설정 검사. 실행: python -m unittest tests.test_ios_project -v"""
import json
import plistlib
import re
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
        self.assertIs(info["ITSAppUsesNonExemptEncryption"], False)
        self.assertEqual(info["CFBundleShortVersionString"], "$(MARKETING_VERSION)")
        self.assertEqual(info["CFBundleVersion"], "$(CURRENT_PROJECT_VERSION)")

    def test_project_bundle_id_and_device_family(self):
        pbx = PBX.read_text(encoding="utf-8")
        self.assertIn("PRODUCT_BUNDLE_IDENTIFIER = kr.yeongyangje.app;", pbx)
        self.assertRegex(pbx, r'TARGETED_DEVICE_FAMILY = "1,2";')

    def test_privacy_manifest_is_in_project(self):
        with open(IOS / "App/PrivacyInfo.xcprivacy", "rb") as f:
            pm = plistlib.load(f)
        self.assertIs(pm["NSPrivacyTracking"], False)
        cats = {a["NSPrivacyAccessedAPIType"]: a["NSPrivacyAccessedAPITypeReasons"] for a in pm["NSPrivacyAccessedAPITypes"]}
        self.assertEqual(cats["NSPrivacyAccessedAPICategoryUserDefaults"], ["CA92.1"])
        pbx = PBX.read_text(encoding="utf-8")
        self.assertTrue("PrivacyInfo.xcprivacy" in pbx or "PBXFileSystemSynchronizedRootGroup" in pbx)

    def test_app_icon_source_exists(self):
        icons = list((IOS / "App/Assets.xcassets/AppIcon.appiconset").glob("*.png"))
        self.assertTrue(icons)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_ios_project -v`
Expected: 5개 모두 FAIL/ERROR(`@capacitor/ios` KeyError, `app/ios` 없음).

- [ ] **Step 3: iOS 플랫폼 추가**

Run(저장소 루트에서): `cd app && npm install @capacitor/ios@8.5.3 --save-exact && npx cap add ios --packagemanager SPM`
Expected: `app/ios/App/App.xcodeproj`, `app/ios/App/CapApp-SPM/Package.swift`(platforms iOS 15, capacitor-swift-pm 8) 생성. 윈도우에서 pod·xcodebuild 관련 경고는 무시. 실패하면(윈도우 거부) Ruling 으로 기록하고 템플릿 `app/node_modules/@capacitor/cli/assets/ios-spm-template.tar.gz` 를 풀어 `cap add` 가 하는 치환(앱 이름·번들 ID)을 직접 한다.

- [ ] **Step 4: 설정 수정**

- `app/package.json`: `assets` 스크립트에 `--ios` 추가(안드로이드 옵션 유지), `sync` 스크립트를 `cap sync` 로.
- `Info.plist`: `CFBundleDisplayName` 을 `영양제.kr` 로, `<key>ITSAppUsesNonExemptEncryption</key><false/>` 추가.
- `PrivacyInfo.xcprivacy` 생성(plist): `NSPrivacyTracking` false, `NSPrivacyTrackingDomains` 빈 배열, `NSPrivacyCollectedDataTypes` 빈 배열(방문 통계는 WebView 의 GA 로 App Store Connect 의 앱 개인정보 설문에서 답함), `NSPrivacyAccessedAPITypes` = [{UserDefaults, [CA92.1]}](Preferences 플러그인의 내 영양제 복제본).
- pbxproj: `PBXFileSystemSynchronizedRootGroup` 이 있으면 `App/App` 폴더의 파일이 자동 포함이므로 그대로. 없으면 `Info.plist`/`AppDelegate.swift` 항목을 본떠 `PBXFileReference`(lastKnownFileType text.plist.xml) + `PBXBuildFile` + 리소스 빌드 단계(`PBXResourcesBuildPhase` files)에 추가(UUID 24자리 16진, 기존과 겹치지 않게).
- Run: `cd app && npm run assets` → `app/ios/App/App/Assets.xcassets/AppIcon.appiconset/*.png`·`Splash.imageset` 생성(배경색 #3a7d44 유지).
- Run: `cd app && npx cap sync ios` → 윈도우에서는 `public/`·`capacitor.config.json` 복사까지만 되고 패키지 해석 경고가 날 수 있음(무시, CI 가 한다).

- [ ] **Step 5: 통과 확인**

Run: `python -m unittest tests.test_ios_project -v`
Expected: `Ran 5 tests` … `OK`

- [ ] **Step 6: 커밋**

`git status` 로 `app/ios/App/App/public/`·`app/ios/App/App/capacitor.config.json`·`DerivedData` 가 추적되지 않는지 확인(템플릿 .gitignore; 빠져 있으면 `app/.gitignore` 에 추가).

```bash
git add app/package.json app/package-lock.json app/ios tests/test_ios_project.py app/.gitignore
git commit -m "feat(app): Capacitor iOS 프로젝트 추가(SPM) — 표시 이름·수출 규정·프라이버시 매니페스트·아이콘"
```

---

### Task 2: 서명 없는 iOS 빌드 워크플로 `build-ios.yml` (컴파일·번들 검사, 지금 실행 가능)

**Files:**
- Create: `.github/workflows/build-ios.yml`

**Interfaces:**
- Consumes: Task 1 의 프로젝트·스킴·빌드 설정.
- Produces: macOS 러너에서 `cap sync ios` + `xcodebuild archive` 가 통과한다는 사실(Task 3 의 전제). 아티팩트 없음(서명 없는 아카이브는 설치 불가).

- [ ] **Step 1: 워크플로 작성**

```yaml
# iOS 컴파일 검증 — macOS 러너에서 서명 없이 아카이브를 만들어 Capacitor iOS 프로젝트가 빌드되는지, 번들에 Info.plist 값·PrivacyInfo 가 실리는지 본다.
# 서명·TestFlight 업로드는 release-ios.yml. Capacitor 8 은 Xcode 26 이상이 필요해 macos-latest(macOS 26)를 쓴다.
name: build-ios

on:
  workflow_dispatch:
  push:
    paths:
      - "app/ios/**"
      - "app/capacitor.config.json"
      - "app/package.json"
      - ".github/workflows/build-ios.yml"

jobs:
  ios:
    runs-on: macos-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: app/package-lock.json }
      - name: Capacitor 동기화
        working-directory: app
        run: |
          npm ci
          npx cap sync ios
          xcodebuild -version
      - name: 아카이브 (서명 없음)
        working-directory: app/ios/App
        run: |
          VERSION_NAME=$(node -p "require('../../package.json').version")
          xcodebuild archive -project App.xcodeproj -scheme App -configuration Release -destination "generic/platform=iOS" \
            -archivePath "$RUNNER_TEMP/App.xcarchive" -skipMacroValidation \
            CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
            MARKETING_VERSION="$VERSION_NAME" CURRENT_PROJECT_VERSION=${{ github.run_number }} | tail -40
      - name: 번들 검사
        run: |
          APP="$RUNNER_TEMP/App.xcarchive/Products/Applications/App.app"
          test -f "$APP/PrivacyInfo.xcprivacy"
          plutil -extract CFBundleIdentifier raw "$APP/Info.plist" | grep -qx "kr.yeongyangje.app"
          plutil -extract CFBundleDisplayName raw "$APP/Info.plist"
          plutil -extract ITSAppUsesNonExemptEncryption raw "$APP/Info.plist" | grep -qx "false"
          plutil -extract CFBundleShortVersionString raw "$APP/Info.plist"
          plutil -extract CFBundleVersion raw "$APP/Info.plist" | grep -qx "${{ github.run_number }}"
```

- [ ] **Step 2: 커밋·푸시 후 실행 확인**

```bash
git add .github/workflows/build-ios.yml
git commit -m "ci(ios): macOS 러너 서명 없는 아카이브로 iOS 프로젝트 컴파일·번들 검사"
git push
```

Run: `gh run list --workflow=build-ios.yml --limit 1` → `gh run watch <id> --exit-status`(15분 안팎).
Expected: 성공. '번들 검사' 로그에 표시 이름 `영양제.kr`, 버전 `1.0.0`, 빌드 번호 = 실행 번호. 실패하면 로그의 xcodebuild 오류(SPM 해석·Swift 버전·매니페스트 참조)를 고쳐 다시 푸시 — 한 번에 안 될 가능성이 가장 큰 작업이므로 수정 내용을 장부에 적는다.

---

### Task 3: 서명·TestFlight 업로드 워크플로 `release-ios.yml`

**Files:**
- Create: `.github/workflows/release-ios.yml`

**Interfaces:**
- Consumes: Task 1 프로젝트, Task 2 의 아카이브 명령.
- Produces: Secrets 이름 `ASC_KEY_ID`·`ASC_ISSUER_ID`·`ASC_PRIVATE_KEY_BASE64`·`APPLE_TEAM_ID`(Task 5 문서가 같은 이름으로 안내), 아티팩트 `app-ios-ipa-<run_number>`(App.ipa), TestFlight 에 올라간 빌드(버전 1.0.0, 빌드 번호 = 실행 번호).

- [ ] **Step 1: 워크플로 작성**

```yaml
# iOS 서명 빌드 + TestFlight 업로드 — 수동 실행만. Mac 없이 xcodebuild 자동 서명(App Store Connect API 키, 클라우드 관리 배포 인증서)으로
# 아카이브 → IPA → altool 업로드. Secrets: ASC_KEY_ID·ASC_ISSUER_ID·ASC_PRIVATE_KEY_BASE64(.p8 base64)·APPLE_TEAM_ID — docs/app-release-ios.md 2·3절.
# 빌드 번호(CFBundleVersion) = 실행 번호(run_number). 파일명을 바꾸면 1부터 다시 시작해 App Store Connect 가 거부하므로 바꾸지 않는다.
name: release-ios

on:
  workflow_dispatch:

jobs:
  ipa:
    runs-on: macos-latest
    timeout-minutes: 60
    steps:
      - name: Secrets 확인
        env:
          KEY_ID: ${{ secrets.ASC_KEY_ID }}
          ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          KEY_B64: ${{ secrets.ASC_PRIVATE_KEY_BASE64 }}
          TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
        run: |
          missing=""
          [ -n "$KEY_ID" ] || missing="$missing ASC_KEY_ID"
          [ -n "$ISSUER_ID" ] || missing="$missing ASC_ISSUER_ID"
          [ -n "$KEY_B64" ] || missing="$missing ASC_PRIVATE_KEY_BASE64"
          [ -n "$TEAM_ID" ] || missing="$missing APPLE_TEAM_ID"
          if [ -n "$missing" ]; then
            echo "::error::GitHub Secrets 가 없음:$missing — docs/app-release-ios.md 2·3절대로 등록한 뒤 다시 실행"
            exit 1
          fi

      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: app/package-lock.json }
      - name: Capacitor 동기화
        working-directory: app
        run: |
          npm ci
          npx cap sync ios

      - name: API 키 파일 준비
        env:
          KEY_ID: ${{ secrets.ASC_KEY_ID }}
          KEY_B64: ${{ secrets.ASC_PRIVATE_KEY_BASE64 }}
        run: |
          mkdir -p "$HOME/.appstoreconnect/private_keys"
          echo "$KEY_B64" | base64 -d > "$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8"
          chmod 600 "$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8"

      - name: 아카이브 (자동 서명)
        working-directory: app/ios/App
        env:
          KEY_ID: ${{ secrets.ASC_KEY_ID }}
          ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
        run: |
          VERSION_NAME=$(node -p "require('../../package.json').version")
          xcodebuild archive -project App.xcodeproj -scheme App -configuration Release -destination "generic/platform=iOS" \
            -archivePath "$RUNNER_TEMP/App.xcarchive" -skipMacroValidation -allowProvisioningUpdates \
            -authenticationKeyPath "$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8" \
            -authenticationKeyID "$KEY_ID" -authenticationKeyIssuerID "$ISSUER_ID" \
            DEVELOPMENT_TEAM="$TEAM_ID" CODE_SIGN_STYLE=Automatic \
            MARKETING_VERSION="$VERSION_NAME" CURRENT_PROJECT_VERSION=${{ github.run_number }} | tail -40

      - name: IPA 내보내기
        env:
          KEY_ID: ${{ secrets.ASC_KEY_ID }}
          ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
        run: |
          cat > "$RUNNER_TEMP/ExportOptions.plist" <<EOF
          <?xml version="1.0" encoding="UTF-8"?>
          <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
          <plist version="1.0"><dict>
            <key>method</key><string>app-store-connect</string>
            <key>destination</key><string>export</string>
            <key>signingStyle</key><string>automatic</string>
            <key>teamID</key><string>$TEAM_ID</string>
            <key>uploadSymbols</key><true/>
          </dict></plist>
          EOF
          xcodebuild -exportArchive -archivePath "$RUNNER_TEMP/App.xcarchive" -exportPath "$RUNNER_TEMP/export" \
            -exportOptionsPlist "$RUNNER_TEMP/ExportOptions.plist" -allowProvisioningUpdates \
            -authenticationKeyPath "$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8" \
            -authenticationKeyID "$KEY_ID" -authenticationKeyIssuerID "$ISSUER_ID" | tail -20
          ls -l "$RUNNER_TEMP/export"
          test -f "$RUNNER_TEMP/export/App.ipa"

      - name: TestFlight 업로드
        env:
          KEY_ID: ${{ secrets.ASC_KEY_ID }}
          ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
        run: xcrun altool --upload-app -f "$RUNNER_TEMP/export/App.ipa" -t ios --apiKey "$KEY_ID" --apiIssuer "$ISSUER_ID"

      - name: API 키 삭제
        if: always()
        run: rm -rf "$HOME/.appstoreconnect/private_keys"

      - uses: actions/upload-artifact@v4
        with:
          name: app-ios-ipa-${{ github.run_number }}
          path: ${{ runner.temp }}/export/App.ipa
          retention-days: 30
          if-no-files-found: error
```

- [ ] **Step 2: 커밋·푸시, Secrets 없이 실행해 사전 확인 단계 검증**

```bash
git add .github/workflows/release-ios.yml
git commit -m "ci(ios): API 키 자동 서명 → IPA → TestFlight 업로드 워크플로(Secrets 4개, 빌드 번호 = 실행 번호)"
git push
```

Run: `gh workflow run release-ios.yml` → `gh run watch <id> --exit-status`.
Expected: 'Secrets 확인' 에서 네 이름을 모두 적고 멈춤. (Secrets 등록 뒤의 실제 실행은 사용자가 `docs/app-release-ios.md` 1~4절을 마친 다음 — 그때 TestFlight 처리 메일·App Store Connect 빌드 목록으로 확인하고 결과를 `PROJECT-STATUS.md` 에 적는다. 첫 실제 실행에서 생길 수 있는 오류와 대응은 Task 5 문서 10절.)

---

### Task 4: App Store 스크린샷 규격을 그래픽 스크립트에 추가

**Files:**
- Modify: `scripts/build_store_assets.py`
- Test: `tests/test_store_assets.py` (추가)

**Interfaces:**
- Consumes: 기존 `fit_screenshot(im, size)`, `build(out_dir, screens_dir)`.
- Produces: `IOS_PHONE_SIZE = (1284, 2778)`(아이폰 6.5형 — 6.9형 칸에도 허용), `IOS_PAD_SIZE = (2064, 2752)`(아이패드 13형), `build_screens(src_dir: Path, out_dir: Path, size: tuple[int, int]) -> list[Path]`(이름순 `01.png…`, 기존 `build` 의 스크린샷 부분을 이 함수로 추출), CLI `--ios-phone 폴더`(→ `app/store/ios/iphone/`)·`--ios-pad 폴더`(→ `app/store/ios/ipad/`). 안드로이드 `--screens` 동작은 그대로.

- [ ] **Step 1: 실패하는 테스트 추가(`tests/test_store_assets.py` 끝에)**

```python
    def test_ios_phone_and_pad_screens_fit(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            Image.new("RGB", (1170, 2532), (255, 0, 0)).save(src / "a.png")     # 아이폰 6.1형 캡처
            Image.new("RGB", (2048, 2732), (0, 0, 255)).save(src / "b.png")     # 아이패드 12.9형 캡처
            phone = S.build_screens(src, Path(d) / "iphone", S.IOS_PHONE_SIZE)
            pad = S.build_screens(src, Path(d) / "ipad", S.IOS_PAD_SIZE)
            self.assertEqual([p.name for p in phone], ["01.png", "02.png"])
            self.assertEqual(Image.open(phone[0]).size, (1284, 2778))
            self.assertEqual(Image.open(pad[1]).size, (2064, 2752))
            self.assertEqual(Image.open(phone[0]).getpixel((642, 1389)), (255, 0, 0))

    def test_build_keeps_android_output_names(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            Image.new("RGB", (1080, 2400)).save(src / "a.png")
            files = [p.relative_to(d).as_posix() for p in S.build(Path(d), src)]
            self.assertIn("screenshots/01.png", files)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_store_assets -v`
Expected: `test_ios_phone_and_pad_screens_fit` ERROR(`build_screens` 없음), 나머지 OK.

- [ ] **Step 3: 구현** — `build_screens` 추출(기존 `build` 가 이를 호출), 상수 두 개, argparse `--ios-phone`·`--ios-pad`(둘 다 선택, 출력 폴더는 비우고 다시 만듦), 머리 주석에 App Store 규격(아이폰 6.5형 1284×2778 — 6.9형 칸 허용·아이패드 13형 2064×2752, 기기당 최대 10장) 추가.

- [ ] **Step 4: 통과 확인**

Run: `python -m unittest tests.test_store_assets -v`
Expected: `Ran 7 tests` … `OK`

- [ ] **Step 5: 커밋**

```bash
git add scripts/build_store_assets.py tests/test_store_assets.py
git commit -m "feat(app): App Store 스크린샷 규격(아이폰 6.5형·아이패드 13형) 변환 추가"
```

---

### Task 5: iOS 출시 절차 문서와 App Store 문구

**Files:**
- Create: `docs/app-release-ios.md`
- Create: `app/store/listing.ios.ko.md`
- Test: `tests/test_store_listing_ios.py`

**Interfaces:**
- Consumes: Task 3 Secrets 이름 4개·워크플로 이름 `release-ios`, Task 4 CLI 플래그.
- Produces: 절 제목 정확히 `## 이름`(30)·`## 부제`(30)·`## 프로모션 텍스트`(170)·`## 설명`(4000)·`## 키워드`(100, 쉼표 구분)·`## 새로운 기능`(4000).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""App Store 문구(app/store/listing.ios.ko.md)·iOS 출시 문서(docs/app-release-ios.md) 검사. 실행: python -m unittest tests.test_store_listing_ios -v"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTING = ROOT / "app/store/listing.ios.ko.md"
DOC = ROOT / "docs/app-release-ios.md"
WORKFLOW = ROOT / ".github/workflows/release-ios.yml"
LIMITS = {"이름": 30, "부제": 30, "프로모션 텍스트": 170, "설명": 4000, "키워드": 100, "새로운 기능": 4000}
BANNED = ("치료", "예방", "완치", "효능", "질병", "의학적")


def sections(text):
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


class IosListingTests(unittest.TestCase):
    def test_sections_within_limits_and_without_disease_claims(self):
        sec = sections(LISTING.read_text(encoding="utf-8"))
        self.assertEqual(set(LIMITS), set(sec))
        for name, limit in LIMITS.items():
            self.assertLessEqual(len(sec[name]), limit, name)
            for w in BANNED:
                self.assertNotIn(w, sec[name], "%s 에 금칙어 %s" % (name, w))
        self.assertEqual(sec["이름"], "영양제.kr")
        self.assertNotIn(" ", sec["키워드"])   # 쉼표만, 공백 없음(공백도 글자 수에 들어감)

    def test_urls_are_ascii_punycode(self):
        for f in (LISTING, DOC):
            for host in re.findall(r"https?://([^/\s)`\]]+)", f.read_text(encoding="utf-8")):
                self.assertTrue(host.isascii(), "%s: %s" % (f.name, host))

    def test_secret_names_match_workflow(self):
        names = set(re.findall(r"secrets\.([A-Z_]+)", WORKFLOW.read_text(encoding="utf-8")))
        self.assertEqual(names, {"ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_PRIVATE_KEY_BASE64", "APPLE_TEAM_ID"})
        doc = DOC.read_text(encoding="utf-8")
        for n in names:
            self.assertIn("gh secret set %s" % n, doc)

    def test_doc_requires_admin_key_role(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("Admin", doc)
        self.assertIn("release-ios", doc)
        self.assertIn("build_store_assets.py --ios-phone", doc)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_store_listing_ios -v`
Expected: 4개 모두 ERROR(`FileNotFoundError`).

- [ ] **Step 3: `app/store/listing.ios.ko.md` 작성** — 안드로이드 `listing.ko.md` 의 전체 설명을 바탕으로(식약처 범위·금칙어 없음·수치 81/710/87): `## 이름` 영양제.kr / `## 부제` `영양제 궁합과 복용 알림` / `## 프로모션 텍스트`(170자 이내, 회원가입 없이 바로·복용 알림 강조) / `## 설명`(■ 성분 정보와 궁합, ■ 앱 전용: 내 영양제·복용 알림·'먹었어요' 기록, ■ 회원가입 없음·링크/QR, ■ 정보 출처와 한계, ■ 개인정보 — 처리방침 URL 퓨니코드) / `## 키워드` `영양제,궁합,복용알림,비타민,오메가3,유산균,마그네슘,영양제추천,건강기능식품,복용시간` / `## 새로운 기능` 1.0.0 첫 출시 항목.

- [ ] **Step 4: `docs/app-release-ios.md` 작성(절 번호 고정 — 워크플로 오류가 2·3절을 가리킴)**

1. **애플 개발자 프로그램 승인 확인** — 승인 메일 뒤 [developer.apple.com/account](https://developer.apple.com/account) 로그인, Membership details 의 **Team ID**(10자) 메모. 아이폰·아이패드에 App Store 에서 **TestFlight** 앱 설치.
2. **App Store Connect API 키 발급(사용자)** — [appstoreconnect.apple.com](https://appstoreconnect.apple.com) → 사용자 및 액세스 → 통합(Integrations) → App Store Connect API → 팀 키 → + 생성: 이름 `github-actions`, 액세스 **Admin**(App Manager 는 xcodebuild 클라우드 서명이 "Cloud signing permission error" 로 실패). 생성 뒤 **Issuer ID**·**Key ID** 를 메모하고 `.p8` 파일을 **한 번만** 내려받아(다시 못 받음) `C:\Users\OK\AuthKey.p8` 처럼 저장소 밖에 둔다.
3. **GitHub Secrets 4개 등록(사용자)** — 한 블록씩(PowerShell·Git Bash 공통):
   ```bash
   gh secret set ASC_KEY_ID
   ```
   ```bash
   gh secret set ASC_ISSUER_ID
   ```
   ```bash
   python -c "import base64,pathlib,subprocess;subprocess.run(['gh','secret','set','ASC_PRIVATE_KEY_BASE64'],input=base64.b64encode((pathlib.Path.home()/'AuthKey.p8').read_bytes()),check=True)"
   ```
   ```bash
   gh secret set APPLE_TEAM_ID
   ```
   (값을 묻는 명령은 붙여 넣고 Enter. 세 번째 명령은 `gh secret set ASC_PRIVATE_KEY_BASE64` 에 `.p8` 의 base64 텍스트를 넘기는 것과 같다 — 테스트가 이 문구로 이름을 대조한다. `gh secret list` 로 4개 확인. `.p8` 은 백업 뒤 보관, 저장소에 넣지 않음 — `.gitignore` 에 `*.p8` 추가.)
4. **번들 ID 등록과 앱 만들기(사용자)** — developer.apple.com → Certificates, Identifiers & Profiles → Identifiers → + → App IDs → App → Description `yeongyangje kr`, Bundle ID **Explicit** `kr.yeongyangje.app`, Capabilities 는 아무것도 켜지 않음 → Register. 이어서 App Store Connect → 나의 앱 → + → 신규 앱: 플랫폼 iOS, 이름 `영양제.kr`, 기본 언어 한국어, 번들 ID 방금 등록한 것, SKU `yeongyangje-kr`, 사용자 액세스 전체.
5. **첫 빌드·TestFlight 업로드** — GitHub → Actions → `release-ios` → Run workflow(15~25분). 자동 서명이 인증서·프로파일을 만들고 `altool` 이 올리면 App Store Connect → TestFlight 탭에 빌드가 '처리 중'(10~30분) → 완료 메일. 명령: `gh workflow run release-ios.yml`.
6. **TestFlight 로 기기 확인(사용자)** — TestFlight 탭 → 내부 테스트 → + 그룹 `내부 테스터` → 테스터에 본인(App Store Connect 사용자) 추가 → 빌드 선택. 아이폰·아이패드의 TestFlight 앱에 나타나면 설치 → 내 영양제 → 알림 권한 허용 → 시각을 몇 분 뒤로 바꿔 알림·'먹었어요'·'30분 뒤' 확인, 비행기 모드로 오프라인 안내 확인.
7. **앱 정보·심사 준비(사용자, 문구는 `app/store/listing.ios.ko.md`)** — ① 앱 정보: 이름·부제·카테고리 '건강 및 피트니스', 개인정보처리방침 URL `https://xn--og5b1hx9c.kr/privacy` ② 가격 무료, 이용 가능 국가 전체(또는 대한민국) ③ **앱 개인정보(App Privacy)**: 데이터 수집 '예' → 유형 '사용 데이터 › 제품 상호 작용'과 '식별자 › 기기 ID'(각각 분석 목적, 사용자에게 연결되지 않음, 추적에 사용 안 함); 그 밖 수집 없음 ④ 연령 등급 설문: 모두 '없음/아니요' → 4+ ⑤ 버전 정보: 프로모션 텍스트·설명·키워드·지원 URL `https://xn--og5b1hx9c.kr/about`·마케팅 URL 사이트 ⑥ 스크린샷: 아이폰 6.9형 칸(1284×2778 허용)·아이패드 13형 칸(2064×2752). 촬영 목록은 안드로이드와 같은 7장(`docs/app-release.md` 6절)을 아이폰과 아이패드에서 각각 캡처해 폴더에 모은 뒤:
   ```bash
   python scripts/build_store_assets.py --ios-phone "C:/Users/OK/Pictures/ios-phone" --ios-pad "C:/Users/OK/Pictures/ios-pad"
   ```
   → `app/store/ios/iphone/01.png…`·`app/store/ios/ipad/01.png…` 업로드 ⑦ 빌드: 5절의 TestFlight 빌드 선택 ⑧ 심사 정보: 로그인 불필요(데모 계정 없음), 연락처, 메모(아래) ⑨ 수출 규정: Info.plist 로 '해당 없음' 처리되어 질문이 뜨지 않음.
   심사 메모 문구: 영양제.kr 은 식품의약품안전처 공개 자료 기반 영양제 성분 정보·궁합 앱. 앱 전용 기능은 '내 영양제'(복용 시간표), 로컬 복용 알림(평일/주말 선택, '먹었어요' 기록), 오프라인 안내 — 웹사이트를 그대로 감싼 것이 아니라 알림·기기 내 저장이 핵심 기능(지침 4.2 대응). 회원가입·로그인 없음. 콘텐츠는 개발자가 직접 운영하는 사이트(https://xn--og5b1hx9c.kr)를 표시. 건강 기능성 표현은 식약처 인정 범위만, 쇼핑 링크 없음.
8. **심사 제출** — 버전 페이지 '심사를 위해 추가' → '심사 제출'. 보통 1~3일. 승인 뒤 '출시'(수동 출시를 골랐으면 버튼으로).
9. **이후 업데이트** — 사이트 변경은 즉시 반영. 앱 껍데기를 바꾸면 `app/package.json` version 을 올리고 `release-ios` 재실행 → TestFlight → App Store Connect 에서 새 버전 만들어 그 빌드로 제출.
10. **문제 해결** — "Cloud signing permission error" → 키 역할 Admin 으로 재발급 후 Secrets 갱신 / "No profiles for 'kr.yeongyangje.app'" 또는 "Provisioning profile … doesn't include signing certificate" → 4절 App ID 등록 확인, 실행 다시 / altool "no suitable application records" → 4절의 App Store Connect 앱 레코드 생성 / "ITMS-90xxx … Missing Privacy Manifest" → `build-ios.yml` 의 번들 검사로 매니페스트 포함 여부 확인 / 지침 4.2(최소 기능) 거절 → 7절 메모 보강: 알림·기록·오프라인 화면 캡처 첨부, 회신 / 같은 빌드 번호 거부 → 실행을 Re-run 하지 말고 새로 Run workflow / Xcode 26 요구 → `macos-latest` 가 macOS 26 이상인지 러너 이미지 확인.

- [ ] **Step 5: `.gitignore` 에 `*.p8` 추가, 통과 확인**

Run: `python -m unittest tests.test_store_listing_ios -v`
Expected: `Ran 4 tests` … `OK`

- [ ] **Step 6: 커밋**

```bash
git add docs/app-release-ios.md app/store/listing.ios.ko.md tests/test_store_listing_ios.py .gitignore
git commit -m "docs(app): iOS 출시 절차(API 키·Secrets·TestFlight·App Store 심사)와 App Store 문구"
```

---

### Task 6: 지침·현황 문서 갱신

**Files:**
- Modify: `CLAUDE.md` (명령: `gh workflow run build-ios.yml`·`release-ios.yml`·`build_store_assets.py --ios-phone/--ios-pad`, `cd app && npm ci && npx cap sync`(ios 포함); 구조 `app/` 에 `ios/`(SPM, macOS 러너에서만 빌드), Secrets 4개 이름, 빌드 번호 = 실행 번호, `docs/app-release-ios.md`·`listing.ios.ko.md`)
- Modify: `docs/PROJECT-STATUS.md` (작업 이력 10-21 행; 7절 A: 계획 5 코드 측 완료, 사용자 몫 = 애플 승인 → `app-release-ios.md` 1~8절; 플레이 쪽은 신원 확인 대기)

- [ ] **Step 1: 두 문서 수정**

- [ ] **Step 2: 전체 테스트·점검**

Run: `python -m unittest discover -s tests 2>&1 | tail -3 && node --test --test-reporter=tap tests/sw.test.mjs tests/store.test.mjs tests/app.test.mjs tests/reminders.test.mjs 2>&1 | grep -E "^# (pass|fail)" && python scripts/check_site.py --quiet`
Expected: unittest `OK`(29 + 새 11 = 40), node `fail 0`, check_site 실패 0.

- [ ] **Step 3: 커밋·푸시**

```bash
git add CLAUDE.md docs/PROJECT-STATUS.md
git commit -m "docs: 계획 5(iOS) 반영 — 명령·구조·다음 할 일"
git push
```
