# 계획 4 — 안드로이드 정식 빌드(서명·AAB)와 구글 플레이 등록 준비

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 서명된 릴리스 앱 번들(AAB)을 GitHub Actions 가 만들고, 사용자가 플레이 콘솔에서 비공개 테스트 → 정식 출시까지 진행할 수 있도록 신고 답안·등록 문구·그래픽·절차 문서를 저장소에 갖춘다.

**Architecture:** 업로드 키는 사용자가 로컬에서 만들어 GitHub Secrets 4개로 올리고, 새 워크플로 `release-android.yml` 이 키스토어를 복원해 `bundleRelease` 로 AAB 를 만든 뒤 bundletool·jarsigner 로 버전·권한·서명을 검사해 아티팩트로 올린다. Gradle 은 서명 환경변수가 모두 있을 때만 서명 설정을 붙이므로 기존 디버그 워크플로(`build-android.yml`)는 그대로 돈다. 플레이 콘솔 입력(개발자 계정·신고 양식·등록정보·테스트 트랙)은 사용자 몫이라 답안·문구·그래픽·스크린샷 규격을 `docs/app-release.md` 와 `app/store/` 에 둔다.

**Tech Stack:** Capacitor 8.5.3 안드로이드 프로젝트(AGP 8.13, JDK 21, compileSdk/targetSdk 36), GitHub Actions(ubuntu, Node 22), keytool·jarsigner(JDK), bundletool 1.18.3, Pillow(스토어 그래픽), Python unittest.

**Spec:** `docs/superpowers/specs/2026-10-20-mobile-app-reminders-design.md` — 6절 스토어 준비물, 9절 4단계(구글 플레이 비공개 테스트 → 정식 출시). iOS(9절 5단계)는 계획 5 로 뺀다.

## Global Constraints

- 앱 이름 "영양제.kr", 앱 ID `kr.yeongyangje.app`(스펙 7절) — 바꾸지 않는다.
- 1차 출시 앱은 쇼핑 버튼을 숨긴다: `assets/js/config.js` 의 `appShopping: false` 유지(쿠팡 최종승인 뒤 켬, 스펙 7절).
- 회원가입 없음(스펙 5-4) — 콘솔 '앱 액세스'는 "모든 기능 제한 없이 이용 가능", 데이터 안전 신고는 GA4 방문 통계만.
- 건강 정보 표현은 식약처 인정 범위("~에 도움을 줄 수 있음")로 쓰고 질병 치료·예방·완치 표현을 쓰지 않는다(CLAUDE.md).
- 서명 키·비밀번호는 GitHub Secrets 에만 둔다(스펙 6절 "키는 Secrets 에"). 값이 저장소·문서·채팅에 나타나지 않게 하고 `*.jks` 는 .gitignore 에 넣는다.
- 저장소는 공개 유지(스펙 6절). 안드로이드 먼저(스펙 7절): 이 계획은 안드로이드·플레이만 다룬다.
- 생성 파일은 손대지 않는다. `app/android/` 는 커밋된 생성물이지만 `AndroidManifest.xml`·`app/build.gradle` 은 `cap sync` 가 덮어쓰지 않으므로 직접 고친다.
- 알림은 모두 `isExactNotification: false`(`assets/js/reminders.js`)라 정확 알람 권한이 필요 없다 — 플러그인은 이 경우 `AlarmManager.setAndAllowWhileIdle` 을 쓴다(`@capacitor/local-notifications` `LocalNotificationManager.kt:369`). 그래서 플러그인이 넣는 `SCHEDULE_EXACT_ALARM` 을 병합 매니페스트에서 뺀다.
- 응답·커밋 메시지는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 피처 그래픽 PNG 에 알파 채널이 있으면 콘솔이 업로드를 거부한다 → RGB 로 저장 (Task 4 `test_feature_graphic_is_opaque_rgb`).
2. 요즘 폰 스크린샷(1080×2400, 20:9)은 긴 변이 짧은 변의 2배를 넘어 거부된다 → 9:16 캔버스에 여백을 채워 맞춤 (Task 4 `test_fit_screenshot_pads_tall_phone_to_9_16`).
3. 등록 문구에 치료·예방·완치·효능 같은 표현이 들어가면 심사 거부와 식약처 위반 → 금칙어·길이 검사 (Task 5 `test_listing_sections_within_limits_and_without_disease_claims`).
4. 한글 도메인 URL(`https://영양제.kr/privacy`)은 콘솔 입력란이 거부할 수 있다 → 문서·문구의 모든 URL 은 퓨니코드 (Task 5 `test_urls_are_ascii_punycode`).
5. 문서가 안내하는 Secrets 이름과 워크플로가 읽는 이름이 다르면 사용자가 등록해도 빌드가 실패한다 → 두 파일의 이름 일치 검사 (Task 5 `test_secret_names_match_workflow`).
6. 플러그인 업그레이드로 `USE_EXACT_ALARM` 이 추가되어도 번들에 남지 않아야 한다 → 매니페스트 remove 노드 두 개(Task 1 테스트) + CI 번들 검사(Task 3 '번들 검사' 단계가 `EXACT_ALARM` 을 찾으면 실패).

---

### Task 1: 정확 알람 권한을 병합 매니페스트에서 제거

**Files:**
- Modify: `app/android/app/src/main/AndroidManifest.xml:2,34`
- Test: `tests/test_android_manifest.py`

**Interfaces:**
- Consumes: 없음
- Produces: 병합 매니페스트에 `SCHEDULE_EXACT_ALARM`·`USE_EXACT_ALARM` 이 없음(Task 3 의 번들 검사가 전제).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_android_manifest -v`
Expected: FAIL — `test_exact_alarm_permissions_are_removed_from_merged_manifest` 에서 `'android.permission.SCHEDULE_EXACT_ALARM' not found`.

- [ ] **Step 3: 매니페스트 수정**

`<manifest>` 에 `xmlns:tools="http://schemas.android.com/tools"` 를 추가하고, `<!-- Permissions -->` 아래 INTERNET 다음에 두 줄을 넣는다(주석으로 이유: 알림이 모두 비정확 예약이라 플러그인의 정확 알람 권한을 뺌 — Play 의 제한 권한 심사 회피).

```xml
<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" tools:node="remove" />
<uses-permission android:name="android.permission.USE_EXACT_ALARM" tools:node="remove" />
```

- [ ] **Step 4: 통과 확인**

Run: `python -m unittest tests.test_android_manifest -v`
Expected: `Ran 2 tests` … `OK`

- [ ] **Step 5: 커밋**

```bash
git add tests/test_android_manifest.py app/android/app/src/main/AndroidManifest.xml
git commit -m "fix(app): 정확 알람 권한(SCHEDULE_EXACT_ALARM·USE_EXACT_ALARM)을 병합 매니페스트에서 제거 — 알림은 모두 비정확 예약"
```

---

### Task 2: 릴리스 서명·버전을 Gradle 에 환경변수·속성으로 연결

**Files:**
- Modify: `app/android/app/build.gradle:3-25`
- Modify: `app/package.json` (`"version": "1.0.0"` 추가 — versionName 의 단일 출처)
- Modify: `.gitignore` (`*.jks`, `*.keystore`, `*.b64`)
- Test: `tests/test_android_gradle.py`

**Interfaces:**
- Consumes: 없음
- Produces: 환경변수 `ANDROID_KEYSTORE_PATH`·`ANDROID_KEYSTORE_PASSWORD`·`ANDROID_KEY_ALIAS`·`ANDROID_KEY_PASSWORD`(넷 다 있을 때만 release 서명) / Gradle 속성 `-PversionCode=<정수>`(기본 1)·`-PversionName=<문자열>`(기본 "1.0.0") — Task 3 워크플로가 쓴다. `app/package.json` 의 `version` 이 versionName.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
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
        self.assertNotRegex(GRADLE, re.compile(r"^\s*versionCode\s+\d", re.M))

    def test_package_version_is_semver(self):
        v = json.loads((ROOT / "app/package.json").read_text(encoding="utf-8"))["version"]
        self.assertRegex(v, r"^\d+\.\d+\.\d+$")

    def test_keystores_are_gitignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for pat in ("*.jks", "*.keystore", "*.b64"):
            self.assertIn(pat, lines)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_android_gradle -v`
Expected: 4개 모두 FAIL(`System.getenv` 없음, `findProperty` 없음, `KeyError: 'version'`, `*.jks` 없음).

- [ ] **Step 3: `app/android/app/build.gradle` 수정**

파일 머리(`android {` 앞)에 정의를 두고 `defaultConfig`·`signingConfigs`·`buildTypes` 를 아래처럼 바꾼다(나머지 블록은 그대로).

```groovy
// 릴리스 서명은 GitHub Actions release-android.yml 이 환경변수로 넘긴다(docs/app-release.md). 넷 중 하나라도 없으면 서명 없이(debug 빌드) 돈다.
def releaseStore = System.getenv("ANDROID_KEYSTORE_PATH")
def releaseSigned = releaseStore && System.getenv("ANDROID_KEYSTORE_PASSWORD") && System.getenv("ANDROID_KEY_ALIAS") && System.getenv("ANDROID_KEY_PASSWORD")
// versionCode 는 워크플로 실행 번호(-PversionCode), versionName 은 app/package.json 의 version(-PversionName)
def appVersionCode = (project.findProperty("versionCode") ?: "1").toInteger()
def appVersionName = project.findProperty("versionName") ?: "1.0.0"
```

`defaultConfig` 안: `versionCode appVersionCode` / `versionName appVersionName`. `signingConfigs { release { if (releaseSigned) { storeFile file(releaseStore); storePassword System.getenv("ANDROID_KEYSTORE_PASSWORD"); keyAlias System.getenv("ANDROID_KEY_ALIAS"); keyPassword System.getenv("ANDROID_KEY_PASSWORD") } } }`. `buildTypes.release` 안에 `if (releaseSigned) signingConfig signingConfigs.release` 추가, `minifyEnabled false` 유지.

- [ ] **Step 4: `app/package.json` 에 `"version": "1.0.0"` 추가(`"private"` 다음 줄), `.gitignore` 에 `*.jks`·`*.keystore`·`*.b64` 추가(주석: 업로드 키스토어·base64 사본 — 절대 커밋 금지)**

- [ ] **Step 5: 통과 확인**

Run: `python -m unittest tests.test_android_gradle -v`
Expected: `Ran 4 tests` … `OK`

- [ ] **Step 6: 커밋·푸시 후 디버그 워크플로로 Gradle 문법 확인**

```bash
git add tests/test_android_gradle.py app/android/app/build.gradle app/package.json .gitignore
git commit -m "build(app): 릴리스 서명(환경변수)·versionCode/versionName(Gradle 속성) 연결, 키스토어 gitignore"
git push
gh run list --workflow=build-android.yml --limit 1
```

`app/**` push 로 `build-android.yml` 이 자동 실행된다. `gh run watch <run-id> --exit-status` 로 기다린다.
Expected: 성공(서명 환경변수가 없어도 debug 빌드가 그대로 됨). 실패하면 Gradle 문법 문제이므로 로그를 보고 고친다.

---

### Task 3: 서명된 AAB 워크플로 `release-android.yml`

**Files:**
- Create: `.github/workflows/release-android.yml`
- (참고) `.github/workflows/build-android.yml` 은 바꾸지 않는다.

**Interfaces:**
- Consumes: Task 2 의 환경변수 4개·Gradle 속성 2개, Task 1 의 매니페스트.
- Produces: GitHub Secrets 이름 `ANDROID_KEYSTORE_BASE64`·`ANDROID_KEYSTORE_PASSWORD`·`ANDROID_KEY_ALIAS`·`ANDROID_KEY_PASSWORD`(Task 5 문서가 같은 이름으로 안내), 아티팩트 `app-release-aab-<run_number>` 안의 `app-release.aab`.

- [ ] **Step 1: 워크플로 작성**

```yaml
# 서명된 안드로이드 앱 번들(AAB) 빌드 — 플레이 콘솔에 올릴 파일. 수동 실행만(Actions → release-android → Run workflow).
# 서명 키는 GitHub Secrets(ANDROID_KEYSTORE_BASE64·ANDROID_KEYSTORE_PASSWORD·ANDROID_KEY_ALIAS·ANDROID_KEY_PASSWORD) — 만드는 법은 docs/app-release.md 1·2절.
# versionCode = 이 워크플로의 실행 번호(run_number). 워크플로 파일명을 바꾸면 번호가 1부터 다시 시작해 플레이가 거부하므로 바꾸지 않는다.
name: release-android

on:
  workflow_dispatch:

jobs:
  aab:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      BUNDLETOOL_VERSION: "1.18.3"
    steps:
      - name: Secrets 확인
        env:
          KEYSTORE_B64: ${{ secrets.ANDROID_KEYSTORE_BASE64 }}
          KEYSTORE_PW: ${{ secrets.ANDROID_KEYSTORE_PASSWORD }}
          KEY_ALIAS: ${{ secrets.ANDROID_KEY_ALIAS }}
          KEY_PW: ${{ secrets.ANDROID_KEY_PASSWORD }}
        run: |
          missing=""
          [ -n "$KEYSTORE_B64" ] || missing="$missing ANDROID_KEYSTORE_BASE64"
          [ -n "$KEYSTORE_PW" ] || missing="$missing ANDROID_KEYSTORE_PASSWORD"
          [ -n "$KEY_ALIAS" ] || missing="$missing ANDROID_KEY_ALIAS"
          [ -n "$KEY_PW" ] || missing="$missing ANDROID_KEY_PASSWORD"
          if [ -n "$missing" ]; then echo "::error::GitHub Secrets 가 없음:$missing — docs/app-release.md 2절대로 등록한 뒤 다시 실행"; exit 1; fi

      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: app/package-lock.json }
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: 21 }
      - name: Android SDK 36 (러너에 없으면 설치)
        continue-on-error: true
        run: |
          yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses >/dev/null 2>&1 || true
          "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platforms;android-36" "build-tools;36.0.0" >/dev/null
      - name: Capacitor 동기화
        working-directory: app
        run: |
          npm ci
          npx cap sync android

      - name: 키스토어 복원
        env:
          KEYSTORE_B64: ${{ secrets.ANDROID_KEYSTORE_BASE64 }}
        run: echo "$KEYSTORE_B64" | base64 -d > "$RUNNER_TEMP/upload.jks"

      - name: Gradle 빌드 (release AAB)
        working-directory: app/android
        env:
          ANDROID_KEYSTORE_PATH: ${{ runner.temp }}/upload.jks
          ANDROID_KEYSTORE_PASSWORD: ${{ secrets.ANDROID_KEYSTORE_PASSWORD }}
          ANDROID_KEY_ALIAS: ${{ secrets.ANDROID_KEY_ALIAS }}
          ANDROID_KEY_PASSWORD: ${{ secrets.ANDROID_KEY_PASSWORD }}
        run: |
          chmod +x gradlew
          VERSION_NAME=$(node -p "require('../package.json').version")
          ./gradlew bundleRelease --no-daemon --stacktrace -PversionCode=${{ github.run_number }} -PversionName="$VERSION_NAME"

      - name: 번들 검사 (서명·버전·정확 알람 권한 없음·네이티브 라이브러리 없음)
        run: |
          AAB=app/android/app/build/outputs/bundle/release/app-release.aab
          curl -sSL -o bundletool.jar "https://github.com/google/bundletool/releases/download/${BUNDLETOOL_VERSION}/bundletool-all-${BUNDLETOOL_VERSION}.jar"
          jarsigner -verify "$AAB" | grep -q "jar verified"
          M=$(java -jar bundletool.jar dump manifest --bundle "$AAB")
          echo "$M" | grep -q 'versionCode="${{ github.run_number }}"'
          # `! grep` 은 bash -e 에서 실패해도 단계를 멈추지 않으므로 if 로 명시
          if echo "$M" | grep -q "EXACT_ALARM"; then echo "::error::정확 알람 권한이 번들에 남아 있음 — AndroidManifest.xml 의 tools:node=remove 확인"; exit 1; fi
          if unzip -l "$AAB" | grep -q '\.so$'; then echo "::error::네이티브 라이브러리(.so)가 들어 있음 — 16KB 페이지 크기 확인 필요"; exit 1; fi
          echo "$M" | grep -o 'versionCode="[0-9]*"\|versionName="[^"]*"'
          ls -l "$AAB"

      - name: 키스토어 삭제
        if: always()
        run: rm -f "$RUNNER_TEMP/upload.jks"

      - uses: actions/upload-artifact@v4
        with:
          name: app-release-aab-${{ github.run_number }}
          path: app/android/app/build/outputs/bundle/release/app-release.aab
          retention-days: 30
          if-no-files-found: error
```

- [ ] **Step 2: 커밋·푸시**

```bash
git add .github/workflows/release-android.yml
git commit -m "ci(android): 서명된 release AAB 워크플로 — Secrets 확인·키스토어 복원·bundleRelease·bundletool 검사·아티팩트"
git push
```

- [ ] **Step 3: Secrets 없이 실행해 사전 확인 단계를 검증**

Run: `gh secret list` 로 `ANDROID_*` 넷이 없는지 본 뒤 `gh workflow run release-android.yml && sleep 20 && gh run list --workflow=release-android.yml --limit 1`, 이어서 `gh run watch <run-id> --exit-status`.
Expected: 'Secrets 확인' 단계에서 실패하고 로그에 `GitHub Secrets 가 없음: ANDROID_KEYSTORE_BASE64 ANDROID_KEYSTORE_PASSWORD ANDROID_KEY_ALIAS ANDROID_KEY_PASSWORD` 가 보인다(Gradle 까지 가지 않음).
(사용자가 이미 Secrets 를 등록했다면 이 단계 대신 Step 4 의 결과가 나온다.)

- [ ] **Step 4: Secrets 등록 뒤 실행(사용자가 `docs/app-release.md` 1·2절을 마친 다음 — 등록 전이면 이 단계는 보류로 기록하고 Task 4 로 간다)**

Run: `gh workflow run release-android.yml` → `gh run watch <run-id> --exit-status` → `gh run download <run-id> -n app-release-aab-<run_number> -D "<scratchpad>/aab"`.
Expected: 성공. '번들 검사' 로그에 `versionCode="<run_number>"`·`versionName="1.0.0"`, 아티팩트에 `app-release.aab`(수 MB).

---

### Task 4: 스토어 그래픽 생성 `scripts/build_store_assets.py`

**Files:**
- Create: `scripts/build_store_assets.py`
- Create(생성물, 커밋): `app/store/feature-graphic.png`(1024×500 RGB), `app/store/play-icon-512.png`(512×512 불투명 정사각)
- Test: `tests/test_store_assets.py`

**Interfaces:**
- Consumes: `scripts/build_app_icons.py` 의 `BG`(색), `draw_icon(size, *, rounded, scale=1.0, opaque=False) -> Image`.
- Produces: `feature_graphic() -> Image`(1024×500, RGB, 배경 `BG`, 가운데 잎 아이콘 — 글자 없음, 폰트 의존 없음) / `play_icon() -> Image`(512×512, `draw_icon(512, rounded=False, opaque=True)`) / `fit_screenshot(im: Image, size=(1080, 1920)) -> Image`(RGB, 비율 유지로 `size` 안에 맞추고 남는 곳은 `BG`, 가운데 정렬) / `build(out_dir: Path, screens_dir: Path | None = None) -> list[Path]`(두 PNG + `screens_dir` 의 `*.png|*.jpg|*.jpeg` 를 이름순으로 `out_dir/screenshots/01.png, 02.png…`) / CLI `python scripts/build_store_assets.py [--screens 폴더]` → `app/store/`.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""스토어 그래픽 생성 스크립트(scripts/build_store_assets.py) 테스트. 실행: python -m unittest tests.test_store_assets -v"""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_app_icons as B  # noqa: E402
import build_store_assets as S  # noqa: E402


class StoreAssetTests(unittest.TestCase):
    def test_feature_graphic_is_opaque_rgb(self):
        im = S.feature_graphic()
        self.assertEqual((im.size, im.mode), ((1024, 500), "RGB"))
        self.assertEqual(im.getpixel((5, 5)), B.BG)
        self.assertEqual(im.getpixel((512, 250)), (255, 255, 255))   # 가운데는 흰 잎

    def test_play_icon_is_full_square_opaque(self):
        im = S.play_icon()
        self.assertEqual(im.size, (512, 512))
        self.assertEqual(im.getpixel((2, 2))[:3], B.BG)
        self.assertEqual(im.getpixel((2, 2))[3], 255)

    def test_fit_screenshot_pads_tall_phone_to_9_16(self):
        out = S.fit_screenshot(Image.new("RGB", (1080, 2400), (255, 0, 0)))
        self.assertEqual((out.size, out.mode), ((1080, 1920), "RGB"))
        self.assertEqual(out.getpixel((0, 0)), B.BG)          # 좌우 여백
        self.assertEqual(out.getpixel((540, 960)), (255, 0, 0))

    def test_fit_screenshot_scales_exact_ratio_without_padding(self):
        out = S.fit_screenshot(Image.new("RGBA", (720, 1280), (0, 0, 255, 255)))
        self.assertEqual((out.size, out.mode), ((1080, 1920), "RGB"))
        self.assertEqual(out.getpixel((0, 0)), (0, 0, 255))

    def test_build_writes_graphics_and_numbered_screenshots(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            Image.new("RGB", (1080, 2400)).save(src / "b.png")
            Image.new("RGB", (1080, 2400)).save(src / "a.jpg")
            files = sorted(p.relative_to(d).as_posix() for p in S.build(Path(d), src))
            self.assertEqual(files, ["feature-graphic.png", "play-icon-512.png", "screenshots/01.png", "screenshots/02.png"])
            self.assertEqual(Image.open(Path(d) / "screenshots/01.png").size, (1080, 1920))
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_store_assets -v`
Expected: `ModuleNotFoundError: No module named 'build_store_assets'`.

- [ ] **Step 3: `scripts/build_store_assets.py` 구현**

머리 주석에 용도(플레이 콘솔 그래픽: 피처 그래픽 1024×500 은 알파 없는 PNG 여야 하고, 스크린샷은 긴 변이 짧은 변의 2배를 넘으면 거부되므로 9:16 캔버스에 맞춤)와 실행법. `feature_graphic` 은 `Image.new("RGB", (1024, 500), B.BG)` 에 `B.draw_icon(360, rounded=False, opaque=True)` 를 가운데 붙인다(같은 배경색이라 이음새 없음). `fit_screenshot` 은 `thumbnail` 대신 `resize(LANCZOS)` 로 `min(W/w, H/h)` 배율. `build` 는 `out_dir/screenshots/` 를 비우고 다시 만든다. `main()` 은 argparse `--screens`, 출력 `ROOT/app/store`, 만든 파일 경로를 출력.

- [ ] **Step 4: 통과 확인**

Run: `python -m unittest tests.test_store_assets -v`
Expected: `Ran 5 tests` … `OK`

- [ ] **Step 5: 생성물 만들기·확인·커밋**

Run: `python scripts/build_store_assets.py && python -c "from PIL import Image; print(Image.open('app/store/feature-graphic.png').mode)"`
Expected: 두 파일 경로 출력, `RGB`.

```bash
git add scripts/build_store_assets.py tests/test_store_assets.py app/store/feature-graphic.png app/store/play-icon-512.png
git commit -m "feat(app): 플레이 콘솔 그래픽 생성 — 피처 그래픽·아이콘·스크린샷 9:16 맞춤(scripts/build_store_assets.py)"
```

---

### Task 5: 출시 절차 문서와 등록 문구

**Files:**
- Create: `docs/app-release.md`
- Create: `app/store/listing.ko.md`
- Test: `tests/test_store_listing.py`

**Interfaces:**
- Consumes: Task 3 의 Secrets 이름 4개·워크플로 이름 `release-android`, Task 4 의 `app/store/*` 와 CLI.
- Produces: 사용자가 그대로 따라 하는 절차와 복사해 붙이는 문구. `listing.ko.md` 의 절 제목은 정확히 `## 앱 이름`, `## 짧은 설명`, `## 전체 설명`, `## 출시 노트`(테스트가 이 제목으로 나눈다).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""플레이 등록 문구(app/store/listing.ko.md)·출시 문서(docs/app-release.md) 검사. 실행: python -m unittest tests.test_store_listing -v"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTING = ROOT / "app/store/listing.ko.md"
DOC = ROOT / "docs/app-release.md"
WORKFLOW = ROOT / ".github/workflows/release-android.yml"
LIMITS = {"앱 이름": 30, "짧은 설명": 80, "전체 설명": 4000, "출시 노트": 500}
BANNED = ("치료", "예방", "완치", "효능", "질병", "의학적")


def sections(text):
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


class ListingTests(unittest.TestCase):
    def test_listing_sections_within_limits_and_without_disease_claims(self):
        sec = sections(LISTING.read_text(encoding="utf-8"))
        self.assertEqual(set(LIMITS), set(sec))
        for name, limit in LIMITS.items():
            self.assertLessEqual(len(sec[name]), limit, name)
            for w in BANNED:
                self.assertNotIn(w, sec[name], "%s 에 금칙어 %s" % (name, w))
        self.assertEqual(sec["앱 이름"], "영양제.kr")

    def test_urls_are_ascii_punycode(self):
        for f in (LISTING, DOC):
            for url in re.findall(r"https?://\S+", f.read_text(encoding="utf-8")):
                self.assertTrue(url.isascii(), "%s: %s" % (f.name, url))

    def test_secret_names_match_workflow(self):
        names = set(re.findall(r"secrets\.(ANDROID_[A-Z_]+)", WORKFLOW.read_text(encoding="utf-8")))
        self.assertEqual(len(names), 4)
        doc = DOC.read_text(encoding="utf-8")
        for n in names:
            self.assertIn("gh secret set %s" % n, doc)

    def test_doc_names_privacy_url_and_workflow(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("https://xn--og5b1hx9c.kr/privacy", doc)
        self.assertIn("release-android", doc)
        self.assertIn("build_store_assets.py --screens", doc)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_store_listing -v`
Expected: 4개 모두 FAIL(`FileNotFoundError` — listing.ko.md, app-release.md 없음).

- [ ] **Step 3: `app/store/listing.ko.md` 작성**

네 절. 내용 규칙: 식약처 범위 표현("~에 도움을 줄 수 있음"), 금칙어(위 BANNED) 없음, 회원가입 없음·기기 내 저장·링크/QR 이동을 강조, 정보 출처 식약처(식품안전나라 공개 데이터).
- `## 앱 이름`: `영양제.kr`
- `## 짧은 설명`(80자 이내): `영양제 성분 정보와 궁합, 복용 시간표와 복용 알림까지 — 회원가입 없이`
- `## 전체 설명`(4000자 이내, 문단 5개): ① 무엇을 하는 앱인지(성분 사전 81종·궁합 체크·가이드·제품 찾기 — 수치는 빌드 시점 `data/meta.json` 과 맞춤) ② 앱 전용: 내 영양제·복용 시간표·복용 알림(시각·평일/주말 선택)·'먹었어요' 기록(선택 기능) ③ 회원가입 없음: 기기 안 저장, 링크·QR 로 다른 기기에 옮김, 백업은 휴대폰 설정 ④ 정보 출처와 한계: 식약처 공개 자료 기준, 기능성 표현은 식약처 인정 범위, 질환이 있거나 약을 먹는 경우 전문가와 상의 ⑤ 개인정보: 방문 통계(GA4) 외 수집 없음, 처리방침 `https://xn--og5b1hx9c.kr/privacy`
- `## 출시 노트`(500자 이내): 1.0.0 첫 출시 — 내 영양제·복용 알림·복용 기록·링크/QR 옮기기·오프라인 안내.

- [ ] **Step 4: `docs/app-release.md` 작성(절 번호를 워크플로 오류 메시지가 가리키므로 1·2절 순서 고정)**

1. **업로드 키 만들기(한 번만, 사용자)** — Play App Signing 을 쓰므로 이 키는 '업로드 키'이고 앱 서명 키는 구글이 보관한다(분실 시 콘솔에서 업로드 키 재설정 요청 가능). 명령(Git Bash, 비밀번호는 keytool 이 물음 — 비밀번호 관리자에 보관):
   ```bash
   keytool -genkeypair -v -keystore "$HOME/yeongyangje-upload.jks" -alias upload -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=yeongyangje.kr, O=yeongyangje.kr, C=KR"
   ```
   `.jks` 를 클라우드 드라이브 등 두 곳에 백업, 저장소에 넣지 않음(`.gitignore`).
2. **GitHub Secrets 4개 등록(사용자)** — 각각 한 블록:
   ```bash
   base64 -w0 "$HOME/yeongyangje-upload.jks" > "$HOME/yeongyangje-upload.jks.b64"
   ```
   ```bash
   gh secret set ANDROID_KEYSTORE_BASE64 < "$HOME/yeongyangje-upload.jks.b64"
   ```
   ```bash
   gh secret set ANDROID_KEYSTORE_PASSWORD
   ```
   ```bash
   gh secret set ANDROID_KEY_ALIAS --body upload
   ```
   ```bash
   gh secret set ANDROID_KEY_PASSWORD
   ```
   (값을 묻는 명령은 붙여 넣고 Enter. 등록 뒤 `gh secret list` 로 이름 4개 확인, `.b64` 파일 삭제.)
3. **AAB 만들기** — GitHub → Actions → `release-android` → Run workflow → 완료 후 아티팩트 `app-release-aab-<번호>` 내려받아 압축 해제 → `app-release.aab`. versionCode 는 실행 번호라 매번 커짐, versionName 은 `app/package.json` 의 `version`(앱 껍데기를 바꿀 때 올림).
4. **플레이 개발자 계정(사용자)** — play.google.com/console, 등록비 25달러 1회, 본인 확인(신분증). 2023-11 이후 만든 개인 계정은 비공개 테스트 '12명 이상·연속 14일' 뒤 프로덕션 액세스를 신청해야 한다(테스터는 15명 이상 모아 두면 이탈해도 안전).
5. **앱 만들기와 '앱 콘텐츠' 신고 답안** — 표로: 앱 이름 영양제.kr / 기본 언어 한국어 / 앱·무료 / 개인정보처리방침 `https://xn--og5b1hx9c.kr/privacy` / 광고 없음 / 앱 액세스 "모든 기능 제한 없이 이용 가능" / 콘텐츠 등급 설문: 카테고리 '참고 자료, 뉴스 또는 교육용', 폭력·성·언어·마약·도박·사용자 간 상호작용·위치 공유·구매 모두 '아니요' → 전체 이용가 / 타겟층 18세 이상(어린이 대상 아님, 어린이 관심 끌지 않음) / 뉴스 앱 아님 / 데이터 안전: 수집 '예'(GA4) — 유형 '앱 활동 › 앱 상호작용'·'기기 또는 기타 ID', 수집·공유 안 함·필수·용도 '분석', 전송 암호화 '예', 삭제 요청 '예'(처리방침 제8조 이메일 help@usdt.io.kr); 내 영양제 데이터는 기기 안에만 있어 수집 아님 / 정부 앱 아님 / 금융 기능 없음 / 광고 ID 사용 안 함 / 건강 앱 선언: '건강 및 피트니스 › 영양 및 체중 관리'(영양제 정보·복용 알림; '의료 › 약물 및 치료 관리'는 의약품용이라 선택하지 않음 — 양식의 설명문에 식이보충제가 '약물' 쪽에 적혀 있으면 그쪽으로 바꾸고 알려 주기).
6. **스토어 등록정보** — `app/store/listing.ko.md` 복사, 앱 카테고리 '건강/운동', 개발자 이메일(처리방침과 같은 주소 권장), 그래픽: 앱 아이콘 `app/store/play-icon-512.png`, 피처 그래픽 `app/store/feature-graphic.png`, 휴대전화 스크린샷 2~8장(권장 4장 이상, 각 변 320~3840px, 긴 변 ≤ 짧은 변×2). 촬영 목록(앱에서, 순서대로): ① 내 영양제 목록 ② 오늘 복용 시간표 ③ 알림 설정(시각·요일) ④ 복용 기록(연속 일수) ⑤ 링크·QR 로 옮기기 ⑥ 궁합 체크 결과 ⑦ 성분 상세. 폰 캡처(1080×2400)는 그대로 쓰면 거부되므로 폴더에 모아 `python scripts/build_store_assets.py --screens <폴더>` → `app/store/screenshots/01.png…` 를 올린다.
7. **비공개 테스트** — 테스트 → 비공개 테스트 → 트랙 만들기 → 테스터: 이메일 목록(Gmail 주소, 12명 이상) → 국가 대한민국 → AAB 업로드(첫 업로드 때 Play App Signing 동의) → 출시 노트(listing.ko.md) → 검토 후 출시. 테스터에게 참여 링크 전달, '테스터 되기' 수락 후 설치·유지(14일 동안 옵트인 12명 미만으로 떨어지면 기간이 다시 셈). 14일 뒤 대시보드 '프로덕션 액세스 신청' 설문(테스트 내용·피드백) 작성.
8. **정식 출시** — 프로덕션 → 새 버전 만들기 → 같은 AAB 또는 새 실행의 AAB → 심사 메모(아래 문구) → 검토 제출. 심사 메모 문구: 앱 전용 기능(내 영양제·복용 알림·복용 기록·오프라인 안내), 회원가입 없음(계정 불필요), 정보 출처(식품의약품안전처 공개 데이터), 알림은 비정확 예약(정확 알람 권한 없음), 사이트 콘텐츠는 WebView 로 라이브 사이트를 표시.
9. **이후 업데이트** — 사이트 변경은 앱에 바로 반영(라이브). 앱 껍데기(`app/`, 플러그인, 아이콘)를 바꾸면 `app/package.json` 의 `version` 을 올리고 `release-android` 를 다시 실행해 새 AAB 를 프로덕션에 올린다. 쿠팡 최종승인 뒤 `config.js` 의 `appShopping: true` 는 사이트 배포만으로 적용(앱 재출시 불필요).
10. **문제 해결** — 업로드 키 분실: 콘솔 → 설정 → 앱 서명 → 업로드 키 재설정 요청 / 워크플로 파일명 변경 금지(versionCode 초기화) / '16KB 페이지 크기' 경고: 네이티브 라이브러리가 없어 해당 없음(워크플로가 `.so` 없음을 확인) / 정확 알람 권한 심사 질문: 매니페스트에서 제거되어 번들에 없음.

- [ ] **Step 5: 통과 확인**

Run: `python -m unittest tests.test_store_listing -v`
Expected: `Ran 4 tests` … `OK`

- [ ] **Step 6: 커밋**

```bash
git add docs/app-release.md app/store/listing.ko.md tests/test_store_listing.py
git commit -m "docs(app): 플레이 출시 절차(업로드 키·Secrets·AAB·신고 답안·테스트 트랙)와 등록 문구"
```

---

### Task 6: 지침·현황 문서 갱신

**Files:**
- Modify: `CLAUDE.md` (자주 쓰는 명령에 `python scripts/build_store_assets.py [--screens 폴더]`·`gh workflow run release-android.yml`, 구조 요약 `app/` 항목에 `app/store/`·`docs/app-release.md`·Secrets 4개 이름·versionCode=run_number 설명, `python -m unittest discover -s tests` 설명에 매니페스트·Gradle·스토어 테스트 포함)
- Modify: `docs/PROJECT-STATUS.md` (작업 이력 10-20 행: 계획 4 코드 측 완료 — 매니페스트 권한 제거·서명/버전 Gradle·release 워크플로·그래픽 스크립트·출시 문서; 7절 A: 다음은 사용자 몫 1~2절(키·Secrets) → 워크플로 실행 → 콘솔 4~8절, 그 뒤 계획 5 iOS)

- [ ] **Step 1: 두 문서 수정**

- [ ] **Step 2: 전체 테스트·점검**

Run: `python -m unittest discover -s tests -v 2>&1 | tail -3 && node --test tests/sw.test.mjs tests/store.test.mjs tests/app.test.mjs tests/reminders.test.mjs 2>&1 | tail -5 && python scripts/check_site.py --quiet`
Expected: unittest `OK`(기존 13 + 새 15 = 28), node `fail 0`, check_site 실패 0.

- [ ] **Step 3: 커밋·푸시**

```bash
git add CLAUDE.md docs/PROJECT-STATUS.md
git commit -m "docs: 계획 4(플레이 출시 준비) 반영 — 명령·구조·다음 할 일"
git push
```
