# iOS 앱 출시 절차 (App Store)

영양제.kr iOS 앱(`app/ios`, 번들 ID `kr.yeongyangje.app`)을 Mac 없이 GitHub Actions macOS 러너에서 서명·빌드해 TestFlight 에 올리고, App Store Connect 에서 심사를 제출하는 순서다. 코드·워크플로·그래픽·문구는 저장소에 있고, 키 발급·App Store Connect 입력은 사용자가 한다. 절 번호는 워크플로 오류 메시지가 가리키므로 바꾸지 않는다. 안드로이드는 `docs/app-release.md`.

설계 문서: `docs/superpowers/specs/2026-10-20-mobile-app-reminders-design.md` 6절 · 계획: `docs/superpowers/plans/2026-10-21-ios-release.md`

워크플로 둘: `build-ios`(서명 없이 컴파일만 검증, `app/ios/**` 변경 push 때 자동) · `release-ios`(수동 실행, 서명 → IPA → TestFlight 업로드).

## 1. 애플 개발자 프로그램 승인 확인 (사용자)

- 가입 승인 메일이 오면 [developer.apple.com/account](https://developer.apple.com/account) 에 로그인한다. 승인 전에는 2절부터 아무것도 할 수 없다.
- Membership details 에서 **Team ID**(영문·숫자 10자)를 메모한다. 3절에서 쓴다.
- 아이폰·아이패드에 App Store 에서 **TestFlight** 앱을 설치해 둔다(6절).

## 2. App Store Connect API 키 발급 (사용자)

[appstoreconnect.apple.com](https://appstoreconnect.apple.com) → 사용자 및 액세스 → 통합(Integrations) → App Store Connect API → **팀 키** 탭 → +(생성). 처음 들어가면 + 대신 **'액세스 요청'** 버튼과 약관 동의만 보이는데, 계정 소유자가 동의하면 바로 + 가 나타난다.

- 이름 `github-actions`, 액세스 **Admin**. App Manager 로 만들면 서명 단계가 "Cloud signing permission error" 로 실패한다(클라우드 관리 배포 인증서를 만들 권한이 Admin 에만 있다).
- 생성 뒤 화면의 **Issuer ID**(긴 UUID)와 키의 **Key ID**(10자)를 메모한다.
- **API 키 다운로드**는 한 번만 된다. 내려받은 `AuthKey_XXXXXXXXXX.p8` 을 `C:\Users\OK\AuthKey.p8` 로 이름을 바꿔 둔다(저장소 폴더 밖, 백업 한 곳 더). `.gitignore` 의 `*.p8` 이 실수 커밋을 막는다.

## 3. GitHub Secrets 4개 등록 (사용자)

워크플로가 읽는 이름은 정확히 `ASC_KEY_ID`·`ASC_ISSUER_ID`·`ASC_PRIVATE_KEY_BASE64`·`APPLE_TEAM_ID` 다(`tests/test_store_listing_ios.py` 가 워크플로와 이 문서의 이름을 대조한다). 저장소 폴더에서 한 블록씩 실행한다(PowerShell·Git Bash 공통). 값을 묻는 명령은 붙여 넣고 Enter.

Key ID(2절).

```bash
gh secret set ASC_KEY_ID
```

Issuer ID(2절).

```bash
gh secret set ASC_ISSUER_ID
```

키 파일을 base64 로 바꿔 올린다(묻는 것 없음). 이 명령은 `gh secret set ASC_PRIVATE_KEY_BASE64` 에 `.p8` 의 base64 텍스트를 넘기는 것과 같다.

```bash
python -c "import base64,pathlib,subprocess;subprocess.run(['gh','secret','set','ASC_PRIVATE_KEY_BASE64'],input=base64.b64encode((pathlib.Path.home()/'AuthKey.p8').read_bytes()),check=True)"
```

Team ID(1절).

```bash
gh secret set APPLE_TEAM_ID
```

확인 — `ASC_`·`APPLE_` 로 시작하는 이름 4개가 보이면 된다(안드로이드의 `ANDROID_*` 4개와 별개).

```bash
gh secret list
```

## 4. 번들 ID 등록과 앱 만들기 (사용자)

1. [developer.apple.com/account](https://developer.apple.com/account) → Certificates, Identifiers & Profiles → Identifiers → + → App IDs → App → Description `yeongyangje kr`, Bundle ID **Explicit** `kr.yeongyangje.app`, Capabilities 는 아무것도 켜지 않음(푸시 알림 안 씀, 로컬 알림은 권한 불필요) → Continue → Register.
2. [appstoreconnect.apple.com](https://appstoreconnect.apple.com) → 나의 앱 → + → 신규 앱: 플랫폼 **iOS**, 이름 `영양제.kr`, 기본 언어 **한국어**, 번들 ID 방금 등록한 `kr.yeongyangje.app`, SKU `yeongyangje-kr`, 사용자 액세스 **전체 액세스** → 생성.

앱 레코드가 있어야 5절의 업로드가 들어간다.

## 5. 첫 빌드·TestFlight 업로드

GitHub 저장소 → Actions → `release-ios` → Run workflow(15~25분). 명령으로는 `gh workflow run release-ios.yml`.

- 자동 서명이 인증서·프로비저닝 프로파일을 만들고, IPA 를 내보낸 뒤 `altool` 이 App Store Connect 에 올린다. 완료 뒤 App Store Connect → 앱 → TestFlight 탭에 빌드가 '처리 중'으로 보이고 10~30분 뒤 '테스트 준비 완료' 메일이 온다.
- 버전은 `app/package.json` 의 `version`(1.0.0), 빌드 번호는 워크플로 실행 번호라 실행할 때마다 커진다.
- Secrets 가 빠져 있으면 첫 단계에서 `GitHub Secrets 가 없음: …` 으로 멈춘다 → 3절. 그 밖의 오류는 10절.

## 6. TestFlight 로 기기 확인 (사용자)

App Store Connect → 앱 → TestFlight → 내부 테스트 → + → 그룹 이름 `내부 테스터` → 테스터 추가에서 본인(App Store Connect 사용자) 선택 → 빌드 선택. 몇 분 뒤 아이폰·아이패드의 TestFlight 앱에 영양제.kr 이 나타난다 → 설치.

확인 목록: 내 영양제 → 알림 권한 허용 → 알림 시각을 2~3분 뒤로 바꿔 알림 수신 → '먹었어요' 버튼(오늘 기록에 반영) → 앱을 완전히 닫은 뒤 알림의 '30분 뒤 다시' → 앱이 열리고 정확히 30분 뒤 다시 수신 → 성분 페이지를 몇 개 본 뒤 비행기 모드로 그 페이지 다시 열기(최근 본 페이지가 나와야 함, 처음 보는 페이지는 오프라인 안내) → 링크·QR 로 아이폰 ↔ 아이패드 옮기기. 문제가 있으면 화면 캡처를 보낸다.

## 7. 앱 정보·심사 준비 (사용자, 문구는 `app/store/listing.ios.ko.md`)

App Store Connect → 앱 → 왼쪽 메뉴에서:

1. **앱 정보**: 이름·부제(문구 파일), 카테고리 기본 '건강 및 피트니스', 콘텐츠 권한 '제3자 콘텐츠 없음', 개인정보처리방침 URL `https://xn--og5b1hx9c.kr/privacy`.
2. **가격 및 사용 가능 여부**: 무료, 사용 가능 국가 전체(또는 대한민국만).
3. **앱 개인정보(App Privacy)**: 데이터 수집 '예, 데이터를 수집합니다' → 유형 **사용 데이터 › 제품 상호 작용**과 **식별자 › 기기 ID**(각각: 분석 목적, 사용자 신원과 연결되지 않음, 추적에 사용하지 않음). 그 밖의 유형은 '수집 안 함'. 내 영양제·알림 설정은 기기 안에만 있어 수집이 아니다(개인정보처리방침 제5조).
4. **연령 등급**: 설문에서 '의료/치료 정보'는 **드묾/경미**(의약품 정보 페이지와 영양제–약 조합 주의를 보여 주므로), 나머지 항목은 '없음/아니요'. 12+ 로 산정되어도 그대로 둔다(정확한 신고가 우선, 지침 2.3).
5. **버전 정보(1.0.0)**: 프로모션 텍스트·설명·키워드(문구 파일), 지원 URL `https://xn--og5b1hx9c.kr/about`, 마케팅 URL `https://xn--og5b1hx9c.kr`, 저작권 `© 2026 영양제.kr`.
6. **스크린샷**: 아이폰 6.9형 칸에 1320×2868, 아이패드 13형 칸에 2064×2752(작은 기기 칸은 애플이 자동으로 줄여 씀). 촬영 목록은 안드로이드와 같은 7장(`docs/app-release.md` 6절)을 TestFlight 앱에서 아이폰과 아이패드로 각각 캡처해 폴더 두 개에 모은 뒤:

```bash
python scripts/build_store_assets.py --ios-phone "C:/Users/OK/Pictures/ios-phone" --ios-pad "C:/Users/OK/Pictures/ios-pad"
```

→ `app/store/ios/iphone/01.png…` 와 `app/store/ios/ipad/01.png…` 를 올린다(기기당 최대 10장).

7. **빌드**: 5절에서 올라온 TestFlight 빌드를 선택.
8. **앱 심사 정보**: 로그인 필요 '아니요'(데모 계정 없음), 연락처(이름·전화·이메일), 메모에 아래 문구.
9. **수출 규정 준수**: Info.plist 의 `ITSAppUsesNonExemptEncryption` = false 로 '해당 없음'이 자동 처리되어 질문이 뜨지 않는다.

심사 메모 문구:

> 영양제.kr 은 식품의약품안전처 공개 자료를 바탕으로 한 영양제 성분 정보·궁합 안내 앱입니다. 앱 전용 기능은 로컬 복용 알림(평일/주말 선택, 알림의 '먹었어요'·'30분 뒤 다시' 버튼, 버튼만으로 복용 기록)과 내 영양제의 iCloud 백업 저장이며, 성분 정보·내 영양제·복용 시간표·오프라인 안내 화면은 웹과 공통입니다(지침 4.2 참고). 회원가입·로그인이 없어 계정 없이 모든 기능을 쓸 수 있습니다. 콘텐츠는 개발자가 직접 운영하는 사이트(https://xn--og5b1hx9c.kr)를 표시합니다. 건강 기능성 표현은 식약처 인정 범위만 쓰며, 쇼핑 링크가 없습니다. 테스트: 내 영양제 → 성분 추가 → 휴대폰 알림 받기 → 시각을 몇 분 뒤로 → 알림 수신 → '먹었어요'.

## 8. 심사 제출

버전 페이지 오른쪽 위 '심사를 위해 추가' → '심사 제출'. 보통 1~3일. 승인 메일이 오면 자동 출시(또는 '수동 출시'를 골랐으면 버튼으로 출시).

## 9. 이후 업데이트

- 사이트 변경은 앱에 바로 반영(라이브 사이트). 앱 재출시 불필요.
- 앱 껍데기(`app/`, Capacitor·플러그인, 아이콘, Info.plist)를 바꾸면 `app/package.json` 의 `version` 을 올리고(안드로이드와 함께) `release-ios` 를 다시 실행 → TestFlight 확인 → App Store Connect 에서 '+ 버전' 으로 새 버전을 만들고 그 빌드를 골라 제출.
- 쿠팡 최종승인 뒤 쇼핑 버튼은 `config.js` 의 `appShopping: true` 사이트 배포만으로 켜진다.

## 10. 문제 해결

- **"Cloud signing permission error"**: API 키 역할이 Admin 이 아님 → 2절에서 Admin 키를 새로 만들고 3절 Secrets 세 개(`ASC_KEY_ID`·`ASC_ISSUER_ID`·`ASC_PRIVATE_KEY_BASE64`)를 다시 등록.
- **"Your team has no devices from which to generate a provisioning profile" + "No profiles … iOS App Development"**(10-21 첫 실행에서 발생): 자동 서명으로 아카이브하면 Xcode 가 개발용 프로파일을 만들려 한다(배포용 ID 를 직접 지정하면 "conflicting provisioning settings"). 워크플로는 아카이브를 서명 없이 만들고 IPA 내보내기 단계의 자동 서명(App Store 프로파일, 기기 불필요)으로 서명하도록 고쳤고 10-21 세 번째 실행(run #8)에서 TestFlight 업로드까지 성공했다. 그래도 같은 오류면 developer.apple.com → Devices → + 로 아이폰을 등록한다(UDID 는 윈도우의 'Apple Devices' 앱에서 아이폰을 연결하고 기기 정보의 일련번호를 클릭하면 보인다).
- **"No profiles for 'kr.yeongyangje.app' were found" / "doesn't include signing certificate"**: 4절의 App ID 등록 확인 뒤 다시 실행(자동 서명이 프로파일을 만든다).
- **altool "no suitable application records were found"**: 4절 2번의 App Store Connect 앱 레코드가 없음.
- **altool 자체가 거부될 때**(애플이 업로드 도구를 바꾸는 경우): `release-ios.yml` 의 ExportOptions 에서 `destination` 을 `upload` 로 바꾸면 `xcodebuild -exportArchive` 가 같은 API 키 플래그로 직접 올린다(IPA 아티팩트는 안 남으므로 필요하면 `export` 실행을 따로). 또는 `xcrun iTMSTransporter` 로 전환.
- **"ITMS-90xxx Missing Privacy Manifest"**: `build-ios` 의 번들 검사가 `PrivacyInfo.xcprivacy` 포함을 확인하므로 보통 나지 않음. 나면 `app/ios/App/App.xcodeproj/project.pbxproj` 의 참조를 확인.
- **지침 4.2(최소 기능) 거절**: 7절 메모를 보강하고 알림·복용 기록·오프라인 화면 캡처를 첨부해 회신. 그래도 거절되면 앱 전용 기능을 더하는 쪽으로 계획.
- **같은 빌드 번호 거부**: 실행을 Re-run 하지 말고 새로 Run workflow(실행 번호가 커진다).
- **Xcode 버전 오류**: Capacitor 8 은 Xcode 26 이상. `macos-latest` 러너 이미지가 바뀌면 워크플로의 `runs-on` 을 `macos-26` 처럼 명시.
- **`.p8` 분실**: 2절에서 키를 새로 만들어(기존 키는 폐기) Secrets 재등록.
