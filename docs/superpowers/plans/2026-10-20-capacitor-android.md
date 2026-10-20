# Capacitor 안드로이드 앱 + 복용 알림(앱 3단계) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 영양제.kr 사이트를 그대로 여는 안드로이드 앱(Capacitor)을 만들고, 내 영양제의 알림 설정대로 휴대폰이 스스로 복용 알림을 울리게 한다. 앱 안에서는 쇼핑 버튼을 숨기고 첫 화면·홈 탭을 내 영양제로 바꾼다. 빌드는 GitHub Actions 가 하고, 결과 APK 를 사용자의 안드로이드 폰에 설치해 확인한다.

**Architecture:** 앱은 번들 대신 라이브 사이트(`https://xn--og5b1hx9c.kr/my`)를 웹뷰로 연다(설계 4절). 사이트 JS 에 작은 "앱 브리지" 모듈을 더해 네이티브 여부를 감지하고, 네이티브일 때만 Capacitor 런타임(전역 빌드 `capacitor.js`)과 플러그인 UMD 파일을 저장소에 복사해 둔 것에서 동적으로 싣는다(번들러 없음). 알림 예약은 순수 "계획" 함수(상태·시간표 → 알림 목록)와 얇은 "동기화" 함수(취소 후 다시 예약)로 나눠 Node 에서 계획을 테스트하고, 브라우저에서는 가짜 플러그인으로 동기화 호출을 검증한다. 네이티브 프로젝트는 `app/` 폴더(Capacitor 설정·`android/`)에 두고 CI 가 디버그 APK 를 만든다.

**Tech Stack:** Capacitor 8.5(core·cli·android), `@capacitor/local-notifications` 8.3, `@capacitor/preferences` 8, `@capacitor/assets`(아이콘·스플래시 생성), JDK 21 + Android SDK(compileSdk 36, minSdk 24)는 GitHub Actions `ubuntu-latest`, Node 24. 사이트 쪽은 Vanilla JS + `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-20-mobile-app-reminders-design.md` 4절(구조 1~5항), 5-2(알림), 5-5(Preferences 복제), 7절 결정(앱 ID `kr.yeongyangje.app`, 앱 이름 "영양제.kr", 홈 탭→내 영양제, 쇼핑 버튼 숨김, GA `platform=app`), 9절 3단계

## Global Constraints

- 사이트 규칙은 CLAUDE.md 그대로(런타임 CDN·번들러 금지, `defer`, 빌드로 해시, 점검 실패 0, 한국어). Capacitor 런타임·플러그인은 npm 에서 **복사한 파일**(`assets/js/vendor/capacitor/*.js`)이며 앱 모드에서만 동적으로 싣는다. 웹 방문자에게는 바이트가 늘지 않아야 한다(`app.js` 한 파일 추가만 허용, 2KB 이내).
- 앱 ID `kr.yeongyangje.app`, 앱 이름 `영양제.kr`, `server.url` = `https://xn--og5b1hx9c.kr/my`, `server.androidScheme` = `https`, `server.cleartext` = false, `android.allowMixedContent` = false. Capacitor 문서는 `server.url` 을 운영용으로 권하지 않으나 설계 4절의 결정(심사 거절 시 번들 방식으로 전환 가능하도록 사이트 JS 는 origin 에 의존하지 않게)을 따른다.
- 알림 문구: 제목 `{시간대} 영양제 시간이에요`, 본문은 `showNames` 면 성분 짧은 이름을 ` · ` 로 이은 것, 아니면 `지금 챙겨 드세요`. 효능 표현 없음. 동작 버튼 `먹었어요` / `30분 뒤 다시`.
- 알림 id: 시간대 순서 `SLOT_ORDER` 인덱스 `i`(0~5), 매일 반복 `1000 + i*10`, 평일만(주말 끄기) `1000 + i*10 + weekday`(weekday 2~6, Capacitor `Weekday` 는 일요일=1), 30분 뒤 다시 `9000 + i`. 우리 id 범위는 1000~1059, 9000~9005 로 고정하며 동기화는 이 범위만 취소한다.
- `isExactNotification: false`(정확 알람 권한을 요구하지 않음; 몇 분 늦을 수 있음), `allowWhileIdle: true`.
- 저장 스키마는 바꾸지 않는다(`yj.my.v1`). Preferences 복제 키도 `yj.my.v1`.
- 비밀값 없음(디버그 APK). 서명·Play 제출은 계획 4.
- 각 작업 끝에 테스트·빌드·점검 뒤 커밋, 푸시는 Task 6 에서. `.claude/launch.json` 삭제, 모바일 확인 뒤 데스크톱 복귀, 로컬 SW 는 켜지 않음.

## Review Focus

1. 알림 권한을 거부하면 토글이 켜진 채 남거나 오류로 멈추면 안 된다. 거부 시 토글을 끄고 설정 안내를 보여 준다. → Task 4 브라우저(가짜 플러그인이 `denied` 반환).
2. 항목·시각·토글을 바꿀 때마다 옛 예약이 남지 않고 전부 새로 잡혀야 한다. 다른 앱 알림을 건드리면 안 된다. → Task 3 `plan 은 같은 입력에 같은 id`, Task 4 브라우저(가짜 플러그인 기록: 우리 범위만 cancel 뒤 schedule).
3. 앱이 꺼진 상태에서 알림의 '먹었어요'를 눌러도 기록이 남아야 한다(콜드 스타트 때 리스너가 늦게 붙으면 유실). → Task 3 `applyAction` 순수 함수 테스트 + Task 6 사용자 기기 확인 항목.
4. '주말에도 알림'을 끄면 토·일에는 울리지 않아야 한다. → Task 3 `weekends=false 면 월~금 5건`.
5. 웹(앱 아님)에서는 Capacitor 파일을 싣거나 플러그인을 부르면 안 되고, 알림 토글은 비활성이어야 한다. → Task 1 브라우저(웹에서 vendor 스크립트 없음), Task 4 브라우저(웹에서 토글 disabled).

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `assets/js/app.js` (신규, 모든 페이지) | 앱 모드 감지(`window.Capacitor` 네이티브 또는 로컬 개발 스위치), `body.is-app`, 네이티브일 때 vendor 런타임·플러그인 동적 로드, `AppBridge.ready()/plugin()/mirror()/restore()` |
| `assets/js/vendor/capacitor/capacitor.js`, `local-notifications.js`, `preferences.js` (복사본) | Capacitor 전역 런타임과 플러그인 UMD 빌드 |
| `assets/js/reminders.js` (신규, my.html) | 알림 계획(순수)·동기화·동작 처리 |
| `assets/js/layout.js`, `assets/js/affiliate.js`, `assets/js/pages/my.js` (수정) | 앱 모드 분기: 탭 바·배너·GA / 쇼핑 버튼·고지 숨김 / 알림 토글·권한·동기화·Preferences 복제 |
| `scripts/build_site.py`, 정적 HTML 14개 (수정) | head 에 `app.js` 추가(패치 스크립트) |
| `scripts/build_app_icons.py` (수정) | 적응형 아이콘 전경/배경·스플래시·상태바용 흰 잎 생성 |
| `app/` (신규) | `package.json`, `capacitor.config.json`, `www/index.html`, `assets/`(아이콘 원본), `android/`(생성, 커밋) |
| `.github/workflows/build-android.yml` (신규) | 디버그 APK 빌드·아티팩트 |
| `package.json` (수정) | `vendor:cap` 스크립트 |
| `tests/app.test.mjs`, `tests/reminders.test.mjs` (신규) | Node 테스트 |
| `CLAUDE.md`, `docs/PROJECT-STATUS.md` (수정) | 구조·명령·이력 |

---

### Task 1: 앱 모드 감지와 사이트 분기

**Files:**
- Create: `assets/js/app.js`, `tests/app.test.mjs`
- Modify: `assets/js/layout.js`(탭 바·배너·GA), `assets/js/affiliate.js`(`buttonsHtml`·`disclosure`), `scripts/build_site.py`(성분 템플릿·`head_html` 의 `config.js` 다음 줄), 정적 HTML 14개(`config.js` 다음 줄 — 패치 스크립트로)

**Interfaces:**
- Produces (`window.AppBridge`, `module.exports` 겸용):
  - `detect(win) -> "native" | "dev" | null` — 순수. `win.Capacitor && typeof win.Capacitor.isNativePlatform === "function" && win.Capacitor.isNativePlatform()` 이면 `"native"`; 아니면 `win.location.hostname` 이 `localhost`/`127.0.0.1` 이고 `win.localStorage.getItem("appDev") === "1"` 이면 `"dev"`; 그 밖 `null`. (`?app=1`/`?app=0` 은 `init` 에서 `appDev` 를 세팅.)
  - `mode() -> string|null`, `isNative() -> boolean`(mode 가 native 또는 dev), `isReal() -> boolean`(native 만).
  - `init()` — 로드 즉시 실행: `?app=` 처리, `document.documentElement.classList.add("is-app")`(DOMContentLoaded 전이라 html 요소에; body 에는 DOMContentLoaded 때 추가), 네이티브면 vendor 세 파일을 순서대로 `<script>` 로 삽입하고 `ready()` 가 그 완료를 기다리는 Promise 를 만든다. dev 모드에서는 vendor 를 싣지 않고 `ready()` 가 바로 resolve.
  - `ready() -> Promise<void>`
  - `plugin(name) -> object|null` — `win.__devPlugins && win.__devPlugins[name]`(브라우저 검증용 가짜)가 있으면 그것, 아니면 `win.Capacitor && win.Capacitor.Plugins && win.Capacitor.Plugins[name]`, 없으면 `null`.
- Produces (`layout.js`): `renderTabbar` 는 `AppBridge.isNative()` 면 첫 탭을 `{ key: "my", label: "내 영양제", href: "my.html", icon: "pill" }` 로 바꾼다(나머지 4개 동일). `initInstallBanner` 는 앱 모드면 아무것도 안 함. GA 블록은 `gtag("config", …)` 뒤에 앱 모드면 `gtag("set", "user_properties", { platform: "app" })`. 푸터의 '제휴 고지' 문단은 앱 모드면 생략.
- Produces (`affiliate.js`): `buttonsHtml()` 은 앱 모드면 `""`, `disclosure()` 는 `""`.
- 스크립트 위치: 모든 페이지 head 의 `config.js` 바로 다음(`data.js` 앞). `defer`. `app.js` 는 `D` 를 쓰지 않는다(`data-root` 는 직접 읽음).

- [ ] **Step 1: 실패하는 테스트** — `tests/app.test.mjs`

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const A = createRequire(import.meta.url)("../assets/js/app.js");
const win = (o) => Object.assign({ location: { hostname: "xn--og5b1hx9c.kr", search: "" }, localStorage: { getItem: () => null } }, o);

test("detect: Capacitor 네이티브면 native", () => assert.equal(A.detect(win({ Capacitor: { isNativePlatform: () => true } })), "native"));
test("detect: Capacitor 객체가 있어도 웹이면 null", () => assert.equal(A.detect(win({ Capacitor: { isNativePlatform: () => false } })), null));
test("detect: localhost + appDev=1 이면 dev", () => assert.equal(A.detect(win({ location: { hostname: "localhost" }, localStorage: { getItem: (k) => (k === "appDev" ? "1" : null) } })), "dev"));
test("detect: 운영 도메인에서는 appDev 를 무시", () => assert.equal(A.detect(win({ localStorage: { getItem: () => "1" } })), null));
test("detect: 저장소가 throw 해도 null", () => assert.equal(A.detect(win({ location: { hostname: "localhost" }, localStorage: { getItem() { throw new Error("x"); } } })), null));
```

- [ ] **Step 2: 실패 확인** — `node --test tests/app.test.mjs` → `Cannot find module '../assets/js/app.js'`
- [ ] **Step 3: `app.js` 구현** — IIFE, 끝에 `window.AppBridge`/`module.exports`. Node 에서 `window` 가 없을 때 `init()` 을 건너뛴다.
- [ ] **Step 4: 통과 확인** — `pass 5`
- [ ] **Step 5: 스크립트 삽입 패치** — 스크래치에 파이썬 패치: 루트 `*.html`(offline.html·naver 확인 파일 제외)과 `scripts/build_site.py` 의 두 템플릿에서 `assets/js/config.js` 스크립트 줄 바로 뒤에 같은 접두(`./`·`../`·`{root}`)의 `app.js` 줄을 넣는다(멱등). `layout.js`·`affiliate.js` 분기 구현.
- [ ] **Step 6: 빌드·점검** — `python scripts/build_site.py && python scripts/check_site.py --quiet && grep -L "assets/js/app.js" *.html i/zinc.html guide/diet.html` → `실패 0`, grep 출력은 `offline.html`·`naver…html` 만.
- [ ] **Step 7: 브라우저 검증** — 로컬 서버에서 `products.html?app=0` 열고: `document.documentElement.classList.contains("is-app") === false`, 탭 바 첫 탭 "홈", `document.querySelector('script[src*="vendor/capacitor"]') === null`, 쇼핑 버튼 존재. 이어 `products.html?app=1`: `is-app` true, 첫 탭 "내 영양제", 쇼핑 버튼 없음, 푸터에 "제휴 고지" 없음, `AppBridge.mode() === "dev"`, vendor 스크립트 없음(dev 는 싣지 않음), 콘솔 오류 없음. 끝에 `?app=0` 으로 되돌림.
- [ ] **Step 8: 커밋** — `git add assets/js/app.js tests/app.test.mjs assets/js/layout.js assets/js/affiliate.js scripts/build_site.py *.html sw.js i guide data/meta.json && git commit -m "feat(app): 앱 모드 감지(app.js) — 앱에서는 홈 탭을 내 영양제로, 쇼핑 버튼·제휴 고지·설치 배너 숨김, GA platform=app"`

---

### Task 2: Capacitor 프로젝트와 런타임 복사본

**Files:**
- Create: `app/package.json`, `app/capacitor.config.json`, `app/www/index.html`, `app/assets/icon-only.png`·`icon-foreground.png`·`icon-background.png`·`splash.png`, `app/android/**`(생성), `app/.gitignore`(`node_modules/`, `android/app/build/`, `android/.gradle/`, `android/build/`, `android/local.properties`)
- Create(복사): `assets/js/vendor/capacitor/capacitor.js`, `local-notifications.js`, `preferences.js`
- Modify: `package.json`(루트, `"vendor:cap"` 스크립트), `scripts/build_app_icons.py`, `assets/js/app.js`(ready 가 싣는 파일 경로 확정)

**Interfaces:**
- `app/package.json`: `"private": true`, dependencies `@capacitor/core` `8.5.3`, `@capacitor/android` `8.5.3`, `@capacitor/local-notifications` `8.3.1`, `@capacitor/preferences` `^8`; devDependencies `@capacitor/cli` `8.5.3`, `@capacitor/assets` 최신; scripts `"sync": "cap sync android"`, `"assets": "capacitor-assets generate --android --iconBackgroundColor '#3a7d44' --iconBackgroundColorDark '#3a7d44' --splashBackgroundColor '#3a7d44' --splashBackgroundColorDark '#3a7d44'"`.
- `app/capacitor.config.json`: `{ "appId": "kr.yeongyangje.app", "appName": "영양제.kr", "webDir": "www", "server": { "url": "https://xn--og5b1hx9c.kr/my", "androidScheme": "https", "cleartext": false }, "android": { "allowMixedContent": false }, "plugins": { "LocalNotifications": { "smallIcon": "ic_stat_leaf", "iconColor": "#246d4b" } } }`
- `app/www/index.html`: 오프라인·첫 로드 실패 때만 보이는 최소 페이지(인라인 스타일, "영양제.kr 을 여는 중… 인터넷 연결을 확인해 주세요", 다시 시도 버튼은 `location.href = "https://xn--og5b1hx9c.kr/my"`).
- 루트 `package.json`: `"vendor:cap": "node -e \"const f=require('fs');f.mkdirSync('assets/js/vendor/capacitor',{recursive:true});[['core/dist/capacitor.js','capacitor.js'],['local-notifications/dist/plugin.js','local-notifications.js'],['preferences/dist/plugin.js','preferences.js']].forEach(([s,d])=>f.copyFileSync('app/node_modules/@capacitor/'+s,'assets/js/vendor/capacitor/'+d))\""`.
- `scripts/build_app_icons.py` 에 `build_app_sources(out_dir: Path) -> list[Path]` 추가: `icon-only.png`(1024, 둥근 모서리 없는 꽉 찬 배경 = 기존 `icon-1024.png` 와 동일), `icon-foreground.png`(1024, 투명 배경에 잎·잎맥만, 잎을 중심 기준 0.66 배 — 적응형 아이콘 안전 영역), `icon-background.png`(1024, `#3a7d44` 단색), `splash.png`(2732, `#3a7d44` 배경 중앙에 흰 잎 600px 폭), 상태바용 `ic_stat_leaf.png`(흰 잎 실루엣, 투명 배경, 24dp 기준으로 mdpi 24·hdpi 36·xhdpi 48·xxhdpi 72·xxxhdpi 96 — `app/android/app/src/main/res/drawable-{dpi}/ic_stat_leaf.png`). `main()` 은 `app/assets/` 와 res 폴더에 쓴다(폴더 없으면 만든다).
- `app.js` `ready()` 가 싣는 순서: `vendor/capacitor/capacitor.js` → `local-notifications.js` → `preferences.js`(`data-root` 접두).

- [ ] **Step 1: 테스트 추가** — `tests/test_app_icons.py` 에:

```python
    def test_app_sources_sizes_and_transparency(self):
        with tempfile.TemporaryDirectory() as d:
            files = {p.name: p for p in B.build_app_sources(Path(d))}
            from PIL import Image
            self.assertEqual(Image.open(files["icon-foreground.png"]).size, (1024, 1024))
            self.assertEqual(Image.open(files["icon-foreground.png"]).getpixel((2, 2))[3], 0)      # 투명 배경
            self.assertEqual(Image.open(files["icon-background.png"]).getpixel((10, 10))[:3], (58, 125, 68))
            self.assertEqual(Image.open(files["splash.png"]).size, (2732, 2732))
            self.assertEqual(Image.open(files["ic_stat_leaf-xxxhdpi.png"]).size, (96, 96))
            self.assertEqual(Image.open(files["ic_stat_leaf-xxxhdpi.png"]).getpixel((48, 40))[:3], (255, 255, 255))   # 잎 중앙은 흰색
```
(`build_app_sources` 는 `ic_stat_leaf-{dpi}.png` 로 돌려주고, `main()` 이 res 폴더 이름으로 옮겨 쓴다.)

- [ ] **Step 2: 실패 확인** — `python -m unittest tests.test_app_icons -v` → `AttributeError: … build_app_sources`
- [ ] **Step 3: 구현·통과** — `OK` (5 tests)
- [ ] **Step 4: 프로젝트 생성** — Run: `mkdir app && cd app && npm init -y` 뒤 위 `package.json` 내용으로 정리, `npm install` (dependencies·devDependencies), `capacitor.config.json`·`www/index.html` 작성, `npx cap add android`, `python ../scripts/build_app_icons.py`(루트에서 실행해도 되게 경로는 ROOT 기준), `npm run assets`(아이콘·스플래시 생성), `npx cap sync android`. Expected: `app/android/app/src/main/res/mipmap-*` 에 아이콘, `drawable-*/ic_stat_leaf.png`, `app/android/app/src/main/assets/capacitor.config.json` 에 `server.url` 반영.
- [ ] **Step 5: AndroidManifest 확인** — Run: `grep -n "POST_NOTIFICATIONS\|SCHEDULE_EXACT_ALARM\|usesCleartextTraffic" app/android/app/src/main/AndroidManifest.xml app/node_modules/@capacitor/local-notifications/android/src/main/AndroidManifest.xml` → 플러그인 매니페스트에 두 권한이 있음(병합됨), 앱 매니페스트에 cleartext 없음.
- [ ] **Step 6: 런타임 복사** — Run: `npm run vendor:cap && ls -la assets/js/vendor/capacitor && head -c 60 assets/js/vendor/capacitor/capacitor.js && tail -c 60 assets/js/vendor/capacitor/local-notifications.js` → 세 파일, `var capacitorExports=`, `})({}, capacitorExports);`.
- [ ] **Step 7: 빌드·점검·커밋** — `python scripts/build_site.py && python scripts/check_site.py --quiet` → `실패 0`. 커밋: `git add app package.json scripts/build_app_icons.py tests/test_app_icons.py assets/js/vendor/capacitor assets/js/app.js sw.js i guide *.html data/meta.json && git commit -m "feat(app): Capacitor 안드로이드 프로젝트(app/, kr.yeongyangje.app, 라이브 사이트 로드), 아이콘·스플래시·상태바 아이콘, 런타임·플러그인 복사본"` (`app/node_modules` 는 .gitignore).

---

### Task 3: 알림 계획·동작 처리(순수 함수)

**Files:**
- Create: `assets/js/reminders.js`, `tests/reminders.test.mjs`

**Interfaces:**
- Consumes: `Store`(SLOT_ORDER·SLOT_LABEL·markDue·toggleDone·dateKey), `Data.shortName`(이름 짧게 — Node 에서는 `opts.shortName` 주입).
- Produces (`window.Reminders`, `module.exports`):
  - `ID_BASE = 1000`, `ID_SNOOZE = 9000`, `ACTION_TYPE = "DOSE"`.
  - `plan(state, sched, opts) -> Notification[]` — `opts.shortName(it) -> string`. `state.settings.remindersOn` 이 false 면 `[]`. `sched.slots` 중 `settings.slotOn[slot]` 인 것만. `times[slot]` 을 `HH:MM` 으로 파싱. `weekends` 면 1건 `{ id: 1000 + i*10, title, body, schedule: { on: { hour, minute }, allowWhileIdle: true }, actionTypeId: "DOSE", extra: { slot }, isExactNotification: false }`, 아니면 weekday 2~6 으로 5건(`schedule.on` 에 `weekday` 추가, id `1000 + i*10 + weekday`). 결과는 id 오름차순.
  - `ourIds(pending: {id}[]) -> number[]` — 1000~1059, 9000~9005 범위만.
  - `snoozeNotification(slot, nowMs, opts, names) -> Notification` — `{ id: 9000 + i, title: "{시간대} 영양제, 30분 뒤예요", body, schedule: { at: new Date(nowMs + 30*60000) }, actionTypeId: "DOSE", extra: { slot } }`.
  - `applyAction(state, action, dueSlots, todayKey) -> { state, snooze: string|null, open: boolean }` — `action = { actionId, notification: { extra: { slot } } }`. `"done"` → `markDue(todayKey, dueSlots)` 뒤 `toggleDone(slot, true)`, `open: false`; `"snooze"` → 상태 그대로, `snooze: slot`; `"tap"`(알림 본체) → `open: true`. 모르는 actionId 는 그대로.
  - `actionTypes() -> { types: [{ id: "DOSE", actions: [{ id: "done", title: "먹었어요" }, { id: "snooze", title: "30분 뒤 다시" }] }] }`.
  - `sync(LN, state, sched, opts) -> Promise<{ cancelled: number, scheduled: number }>` — `LN.getPending()` → `ourIds` 만 `LN.cancel({ notifications: ids.map(id => ({ id })) })`(0건이면 호출 안 함) → `plan(...)` 이 있으면 `LN.schedule({ notifications })`.

- [ ] **Step 1: 실패하는 테스트** — `tests/reminders.test.mjs`

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const S = req("../assets/js/store.js"), R = req("../assets/js/reminders.js");
const sn = (it) => it.name.replace(/\s*\(.*$/, "");
const core = { byId: { magnesium: { id: "magnesium", name: "마그네슘" }, "vitamin-d": { id: "vitamin-d", name: "비타민 D" } } };
const sched = { slots: [{ key: "morning_after", items: [core.byId["vitamin-d"]] }, { key: "bedtime", items: [core.byId.magnesium] }] };
function on() { return S.setSetting(S.addItems(S.empty(), ["vitamin-d", "magnesium"]).state, "remindersOn", true); }

test("plan: 꺼져 있으면 없음", () => assert.deepEqual(R.plan(S.empty(), sched, { shortName: sn }), []));
test("plan: 매일 반복 — 시간대마다 1건, 시각·이름·id", () => {
  const p = R.plan(on(), sched, { shortName: sn });
  assert.deepEqual(p.map(n => n.id), [1010, 1050]);
  assert.deepEqual(p[0].schedule.on, { hour: 8, minute: 0 }); assert.equal(p[0].title, "아침 식후 영양제 시간이에요"); assert.equal(p[0].body, "비타민 D");
  assert.equal(p[1].schedule.on.hour, 22); assert.equal(p[1].schedule.on.minute, 30); assert.equal(p[1].actionTypeId, "DOSE"); assert.equal(p[1].extra.slot, "bedtime");
  assert.equal(p[0].isExactNotification, false); assert.equal(p[0].schedule.allowWhileIdle, true);
});
test("plan: 주말 끄면 월~금 5건씩, 토·일 없음", () => {
  const p = R.plan(S.setSetting(on(), "weekends", false), { slots: [sched.slots[0]] }, { shortName: sn });
  assert.deepEqual(p.map(n => n.schedule.on.weekday), [2, 3, 4, 5, 6]); assert.deepEqual(p.map(n => n.id), [1012, 1013, 1014, 1015, 1016]);
});
test("plan: 시간대 토글이 꺼진 시간대·이름 숨김", () => {
  let s = S.setSlotOn(on(), "bedtime", false); s = S.setSetting(s, "showNames", false);
  const p = R.plan(s, sched, { shortName: sn });
  assert.equal(p.length, 1); assert.equal(p[0].body, "지금 챙겨 드세요");
});
test("plan: 같은 입력이면 같은 결과(동기화가 멱등)", () => assert.deepEqual(R.plan(on(), sched, { shortName: sn }), R.plan(on(), sched, { shortName: sn })));
test("ourIds: 우리 범위만", () => assert.deepEqual(R.ourIds([{ id: 1 }, { id: 1010 }, { id: 1059 }, { id: 1060 }, { id: 9003 }, { id: 9006 }]), [1010, 1059, 9003]));
test("snoozeNotification: 30분 뒤 1회", () => {
  const n = R.snoozeNotification("bedtime", 0, { shortName: sn }, "마그네슘");
  assert.equal(n.id, 9005); assert.equal(n.schedule.at.getTime(), 30 * 60000); assert.equal(n.title, "취침 전 영양제, 30분 뒤예요");
});
test("applyAction: done 은 오늘 due 를 먼저 기록하고 체크", () => {
  const r = R.applyAction(on(), { actionId: "done", notification: { extra: { slot: "bedtime" } } }, ["morning_after", "bedtime"], "2026-10-20");
  assert.deepEqual(S.dayStats(r.state, "2026-10-20"), { due: 2, done: 1, complete: false }); assert.equal(r.open, false); assert.equal(r.snooze, null);
});
test("applyAction: snooze·tap·모르는 동작", () => {
  assert.equal(R.applyAction(on(), { actionId: "snooze", notification: { extra: { slot: "bedtime" } } }, [], "2026-10-20").snooze, "bedtime");
  assert.equal(R.applyAction(on(), { actionId: "tap", notification: { extra: { slot: "bedtime" } } }, [], "2026-10-20").open, true);
  const s = on(); assert.equal(R.applyAction(s, { actionId: "x", notification: {} }, [], "2026-10-20").state, s);
});
test("sync: 우리 id 만 취소하고 계획을 예약한다", async () => {
  const calls = [];
  const LN = { getPending: async () => ({ notifications: [{ id: 1010 }, { id: 42 }] }), cancel: async (o) => calls.push(["cancel", o.notifications.map(n => n.id)]), schedule: async (o) => calls.push(["schedule", o.notifications.map(n => n.id)]) };
  const r = await R.sync(LN, on(), sched, { shortName: sn });
  assert.deepEqual(calls, [["cancel", [1010]], ["schedule", [1010, 1050]]]); assert.deepEqual(r, { cancelled: 1, scheduled: 2 });
  calls.length = 0; await R.sync(LN, S.empty(), sched, { shortName: sn }); assert.deepEqual(calls, [["cancel", [1010]]]);
});
```

- [ ] **Step 2: 실패 확인** — `node --test tests/reminders.test.mjs` → `Cannot find module '../assets/js/reminders.js'`
- [ ] **Step 3: 구현** — IIFE + `module.exports`; Node 에서 `Store` 는 `require("./store.js")` 로, 브라우저에서는 `window.Store`.
- [ ] **Step 4: 통과 확인** — `pass 10`
- [ ] **Step 5: 커밋** — `git add assets/js/reminders.js tests/reminders.test.mjs && git commit -m "feat(app): 복용 알림 계획·동기화·동작 처리(reminders.js) — 매일/평일 반복 id 규칙, 30분 뒤 다시, 먹었어요 기록"`

---

### Task 4: 내 영양제 페이지의 앱 연동(알림 토글·동기화·동작·Preferences 복제)

**Files:**
- Modify: `assets/js/pages/my.js`, `my.html`(`reminders.js` 스크립트 추가, `store.js` 다음), `assets/js/app.js`(`mirror`/`restore`)

**Interfaces:**
- Consumes: Task 1 `AppBridge.isNative()/isReal()/ready()/plugin()`, Task 3 `Reminders.*`.
- Produces (`app.js`): `mirror(stateJson: string) -> Promise<void>`(`Preferences.set({ key: "yj.my.v1", value })`, 플러그인 없으면 no-op), `restore() -> Promise<string|null>`(`Preferences.get` 의 `value`).
- Produces (`my.js`):
  - 로드 흐름: `D.core()` 뒤 `AppBridge.ready()` 를 기다린 다음, `localStorage` 가 비어 있고(`state.items.length === 0 && !localStorage.getItem(S.KEY)`) 앱 모드면 `AppBridge.restore()` 로 받은 JSON 을 `S.load({ getItem: () => json })` 로 읽어 복원.
  - 앱 모드면 알림 섹션: '휴대폰 알림 받기' 토글 활성, 안내 문구 "알림은 이 휴대폰에서 울려요. 시각을 바꾸면 바로 다시 예약돼요."; 웹이면 지금처럼 비활성 + "앱에서 받을 수 있어요".
  - 토글 켤 때: `LN.requestPermissions()` → `display === "granted"` 면 `setSetting(remindersOn, true)` + 동기화, 아니면 토글을 되돌리고 `ui.notice = "알림 권한이 꺼져 있어요. 휴대폰 설정 → 앱 → 영양제.kr → 알림에서 켜 주세요."`.
  - `commit()` 뒤 앱 모드이고 `remindersOn` 이면 `Reminders.sync(LN, state, schedule(), { shortName: D.shortName })` 를 300ms 디바운스로 호출(끄면 한 번 더 호출해 취소만). 앱 모드면 `commit()` 때 `AppBridge.mirror(JSON.stringify(state))` 도 호출.
  - 시작 때(앱 모드): `LN.registerActionTypes(Reminders.actionTypes())`, `LN.addListener("localNotificationActionPerformed", handler)`; `handler` 는 `Reminders.applyAction(state, ev, dueSlots(schedule()), today())` 로 상태를 바꿔 `commit`, `snooze` 면 `LN.schedule({ notifications: [Reminders.snoozeNotification(...)] })`, `open` 이면 `window.scrollTo(0, 0)`(이미 my.html). 그리고 `remindersOn` 이면 `Reminders.sync` 한 번(시간표가 바뀌어 있을 수 있음).
- 브라우저 검증용 가짜: `window.__devPlugins = { LocalNotifications: {...calls 기록, requestPermissions 는 설정 가능}, Preferences: { 메모리 Map } }` 를 `?app=1` 상태에서 페이지 로드 전에 넣기 위해 `my.js` 는 `AppBridge.ready()` 뒤에 플러그인을 찾는다(가짜는 `javascript_tool` 로 `document.addEventListener("DOMContentLoaded")` 이전에 못 넣으므로 `AppBridge.plugin()` 호출 시점에만 있으면 된다 — 동기화·토글은 사용자 동작 뒤이므로 충분).

- [ ] **Step 1: 구현**
- [ ] **Step 2: 빌드·점검·테스트** — `node --test tests/store.test.mjs tests/sw.test.mjs tests/app.test.mjs tests/reminders.test.mjs && python scripts/build_site.py && python scripts/check_site.py --quiet`
- [ ] **Step 3: 브라우저 검증(웹)** — `my.html?app=0`: 토글 `disabled`, `window.Capacitor` 없음, vendor 스크립트 없음(Review Focus 5).
- [ ] **Step 4: 브라우저 검증(앱 흉내)** — `my.html?app=1` 로드 후 `javascript_tool` 로 `window.__devPlugins` 설정(기록용 LN: `getPending`→`{notifications:[{id:1010},{id:7}]}`, `cancel`·`schedule`·`registerActionTypes`·`addListener` 기록, `requestPermissions`→`{display:"granted"}`; Preferences 메모리). 토글 클릭 → `remindersOn === true`, 기록에 `cancel [1010]` 뒤 `schedule` 의 id 가 `Reminders.plan` 과 같음. 시각 변경 → 300ms 뒤 다시 `schedule`. `requestPermissions` 를 `denied` 로 바꾸고 토글 끄고 다시 켜기 → 토글 꺼진 채 유지 + 안내 문구(Review Focus 1). `Preferences` 메모리에 `yj.my.v1` 이 저장됨. 콘솔 오류 없음. 끝에 `?app=0`.
- [ ] **Step 5: 커밋** — `git add assets/js/pages/my.js my.html assets/js/app.js sw.js i guide *.html data/meta.json && git commit -m "feat(app): 내 영양제 알림 연동 — 권한 요청·토글·설정 변경 시 재예약·알림 동작(먹었어요/30분 뒤)·Preferences 복제"`

---

### Task 5: GitHub Actions 안드로이드 빌드

**Files:**
- Create: `.github/workflows/build-android.yml`

**Interfaces:**
- 트리거: `workflow_dispatch`, `push` with `paths: ["app/**", ".github/workflows/build-android.yml"]`.
- job `android`(`ubuntu-latest`): `actions/checkout@v4` → `actions/setup-node@v4`(node 20, `cache: npm`, `cache-dependency-path: app/package-lock.json`) → `actions/setup-java@v4`(`distribution: temurin`, `java-version: 21`) → `cd app && npm ci` → `npx cap sync android` → `cd android && chmod +x gradlew && ./gradlew assembleDebug --no-daemon --stacktrace` → `actions/upload-artifact@v4`(name `app-debug-apk`, path `app/android/app/build/outputs/apk/debug/app-debug.apk`, retention 14일). SDK 36 이 없으면 Gradle 이 내려받도록 `ANDROID_HOME` 의 `cmdline-tools/latest/bin/sdkmanager "platforms;android-36" "build-tools;36.0.0"` 를 앞 단계에 넣는다(실패해도 계속).
- `app/android/gradle.properties` 에 `org.gradle.jvmargs=-Xmx3g`(기본값 유지 가능).

- [ ] **Step 1: 워크플로 작성·푸시** — 이 작업만 예외로 바로 푸시한다(CI 는 원격에서만 돈다). `git add .github/workflows/build-android.yml && git commit -m "ci(android): Capacitor 디버그 APK 빌드 워크플로(workflow_dispatch·app/** push)" && git push origin HEAD`
- [ ] **Step 2: 실행·확인** — Run: `gh workflow run build-android.yml --ref claude/supplement-info-compatibility-site-1o2qrj && sleep 60 && gh run list --workflow build-android.yml --limit 1` → 완료까지 `gh run watch <id> --exit-status`(약 5~8분). Expected: `success`, 아티팩트 `app-debug-apk`.
- [ ] **Step 3: 아티팩트 내려받기** — Run: `gh run download <id> -n app-debug-apk -D "$SCRATCHPAD/apk" && ls -la "$SCRATCHPAD/apk"` → `app-debug.apk`(약 3~6MB). 실패하면 로그(`gh run view <id> --log-failed`)로 원인을 고친 뒤 재실행(SDK 버전·JDK·Gradle 메모리가 흔한 원인).
- [ ] **Step 4: 사용자에게 전달** — `SendUserFile` 로 APK 를 보내고 설치 절차(출처를 알 수 없는 앱 허용 → 설치 → 앱 열기 → 내 영양제 → 알림 토글 → 권한 허용 → 시각을 2~3분 뒤로 바꿔 알림 확인 → 알림의 '먹었어요' → 기록 반영 확인)를 안내한다. 이 확인은 사용자 몫이며 결과를 문서에 적는다.

---

### Task 6: 문서·푸시

**Files:**
- Modify: `CLAUDE.md`(구조: `app.js`·`reminders.js`·`vendor/capacitor`·`app/`·CI 워크플로, 명령: `npm run vendor:cap`, `cd app && npx cap sync android`, 테스트 명령에 두 파일, 작업 요령: 로컬 앱 흉내 `?app=1`/`?app=0`, 플러그인 버전 올릴 때 `vendor:cap` 재실행), `docs/PROJECT-STATUS.md`(이력 10-20/21, 7절 A: 3단계 완료 → 계획 4, 사용자 확인 항목·결과 칸), `.github/workflows/build-assets.yml`(paths 에 `scripts/sw_template.js`, `assets/js/vendor/**` 추가 — 지난 검토 보류 항목)

- [ ] **Step 1: 전체 테스트·빌드·점검** — `node --test tests/store.test.mjs tests/sw.test.mjs tests/app.test.mjs tests/reminders.test.mjs && python -m unittest discover -s tests && npm run assets && python scripts/build_site.py && python scripts/check_site.py --quiet && test ! -e .claude/launch.json`
- [ ] **Step 2: 커밋·푸시·배포 확인** — `git add -A && git commit -m "docs: Capacitor 안드로이드 앱(3단계) 기록, 앱 모드·알림 모듈·CI 안내" && git push origin HEAD`; 2~3분 뒤 `curl -s https://xn--og5b1hx9c.kr/my | grep -c "assets/js/app.js"` → `1`, 운영 `my` 페이지를 앱 안 브라우저로 열어 토글이 여전히 비활성(웹)인지 확인.

---

## 자가 점검 기록

- 사양 대조: 4절 2항(라이브 사이트 로드·`window.Capacitor` 감지) → Task 1·2; 4절 3항(알림만 네이티브) → Task 3·4; 4절 4항(안드로이드 Capacitor) → Task 2·5; 4절 5항(쇼핑 버튼 숨김·플래그) → Task 1(앱 모드 분기; 최종승인 뒤 켜는 플래그는 계획 4 에서 `config.js` 에); 5-2(설정·문구·버튼·재예약·권한·웹 안내) → Task 3·4; 5-5(Preferences 복제·OS 백업) → Task 4; 7절(앱 ID·이름·홈 탭·GA platform) → Task 1·2. 아이콘은 1단계 아이콘을 원본으로 Task 2.
- 이름 일치: `AppBridge.detect/mode/isNative/isReal/init/ready/plugin/mirror/restore`, `Reminders.plan/ourIds/snoozeNotification/applyAction/actionTypes/sync`, 상수 `ID_BASE/ID_SNOOZE/ACTION_TYPE` 이 테스트·단계에서 같은 이름.
- Review Focus 5건: 1→Task 4 Step 4, 2→Task 3(멱등·ourIds·sync)+Task 4, 3→Task 3(applyAction)+Task 5 사용자 확인, 4→Task 3(주말), 5→Task 1 Step 7·Task 4 Step 3.
- 알려진 위험: Capacitor 문서가 `server.url` 을 운영용으로 권하지 않음(설계 4절 결정, 심사·동작 문제 시 번들 방식으로 전환); iOS 는 이 계획 범위 밖(계획 4).
