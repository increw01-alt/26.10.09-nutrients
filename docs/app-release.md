# 안드로이드 앱 출시 절차 (구글 플레이)

영양제.kr 안드로이드 앱(`app/`, 앱 ID `kr.yeongyangje.app`)을 서명된 앱 번들(AAB)로 만들어 플레이 콘솔에 올리고, 비공개 테스트를 거쳐 정식 출시하는 순서다. 코드·워크플로·그래픽은 저장소에 있고, 키 생성·콘솔 입력은 사용자가 한다. 절 번호는 워크플로 오류 메시지가 가리키므로 바꾸지 않는다. iOS 는 별도 계획(계획 5).

설계 문서: `docs/superpowers/specs/2026-10-20-mobile-app-reminders-design.md` 6절 · 계획: `docs/superpowers/plans/2026-10-20-play-release.md`

## 1. 업로드 키 만들기 (한 번만, 사용자)

플레이는 Play App Signing 을 쓴다. 여기서 만드는 키는 '업로드 키'이고, 앱에 실제 서명하는 '앱 서명 키'는 구글이 만들어 보관한다. 업로드 키를 잃어버려도 콘솔에서 재설정을 요청할 수 있다(10절).

이 앱의 터미널(PowerShell)이나 Git Bash 어디서든 같은 명령이다. 먼저 `keytool -version` 이 답하는지 본다(이 PC 에는 JDK 21 이 있다). keytool 은 키스토어 비밀번호만 묻는다(두 번 입력). 요즘 JDK 의 기본 형식(PKCS12)은 키 비밀번호를 따로 두지 못해 키 비밀번호는 자동으로 같은 값이 된다. 비밀번호는 비밀번호 관리자에 보관한다.

```bash
keytool -genkeypair -v -keystore "$HOME/yeongyangje-upload.jks" -alias upload -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=yeongyangje.kr, O=yeongyangje.kr, C=KR"
```

- 만들어진 `~/yeongyangje-upload.jks`(Windows 는 `C:\Users\<이름>\yeongyangje-upload.jks`)를 클라우드 드라이브 등 두 곳에 백업한다.
- 저장소 폴더 안에 두지 않는다. 실수로 복사해도 `.gitignore`(`*.jks`·`*.keystore`·`*.b64`)가 커밋을 막는다.
- 키 값·비밀번호를 채팅, 문서, 이슈에 적지 않는다.

## 2. GitHub Secrets 4개 등록 (사용자)

워크플로가 읽는 이름은 정확히 `ANDROID_KEYSTORE_BASE64`·`ANDROID_KEYSTORE_PASSWORD`·`ANDROID_KEY_ALIAS`·`ANDROID_KEY_PASSWORD` 다(`tests/test_store_listing.py` 가 워크플로와 이 문서의 이름을 대조한다). 저장소 폴더에서 한 블록씩 실행한다(PowerShell·Git Bash 공통, `gh` 는 이미 로그인돼 있음).

키스토어 파일을 base64 텍스트로 바꿔 Secret 으로 올린다(임시 파일 없이 한 번에).

```bash
python -c "import base64,pathlib,subprocess;subprocess.run(['gh','secret','set','ANDROID_KEYSTORE_BASE64'],input=base64.b64encode((pathlib.Path.home()/'yeongyangje-upload.jks').read_bytes()),check=True)"
```

키스토어 비밀번호(명령이 값을 물으면 붙여 넣고 Enter).

```bash
gh secret set ANDROID_KEYSTORE_PASSWORD
```

키 별칭(1절 명령의 `-alias` 값).

```bash
gh secret set ANDROID_KEY_ALIAS --body upload
```

키 비밀번호 — `ANDROID_KEY_PASSWORD` 에는 `ANDROID_KEYSTORE_PASSWORD` 와 같은 값을 넣는다(1절의 PKCS12 키스토어는 두 비밀번호가 같다. 다른 값을 넣으면 워크플로의 Gradle 빌드가 키를 못 읽어 실패한다).

```bash
gh secret set ANDROID_KEY_PASSWORD
```

확인.

```bash
gh secret list
```

`ANDROID_` 로 시작하는 이름 4개가 보이면 된다. 값을 잘못 넣었으면 같은 명령을 다시 실행하면 덮어쓴다.

## 3. AAB 만들기

GitHub 저장소 → Actions → 왼쪽 `release-android` → Run workflow → Run workflow. 5분 안팎 뒤 성공하면 실행 페이지 아래 Artifacts 의 `app-release-aab-<실행 번호>` 를 내려받아 압축을 풀면 `app-release.aab` 가 나온다. 이 파일을 콘솔에 올린다.

- versionCode 는 워크플로 실행 번호라 실행할 때마다 커진다(플레이는 전보다 큰 번호만 받는다). versionName 은 `app/package.json` 의 `version`(지금 1.0.0).
- 워크플로는 빌드 뒤 서명(jarsigner), versionCode, 정확 알람 권한이 없는지, 네이티브 라이브러리(.so)가 없는지 검사하고 실패하면 로그에 이유를 적는다.
- Secrets 가 빠져 있으면 첫 단계에서 `GitHub Secrets 가 없음: …` 으로 멈춘다 → 2절.
- 명령으로 하려면: `gh workflow run release-android.yml` → `gh run list --workflow=release-android.yml --limit 1` → `gh run download <실행 ID> -n app-release-aab-<실행 번호>`.

## 4. 플레이 개발자 계정 (사용자)

[play.google.com/console](https://play.google.com/console) 에서 개인 개발자 계정을 만든다(등록비 25달러 1회, 신분증 본인 확인, 전화·이메일 확인). 

- 2023년 11월 13일 이후 만든 개인 계정은 **비공개 테스트에 12명 이상이 참여한 상태로 연속 14일**을 채운 뒤 '프로덕션 액세스'를 신청해야 정식 출시 트랙이 열린다([구글 안내](https://support.google.com/googleplay/android-developer/answer/14151465)). 테스터는 Gmail 주소가 필요하고, 도중에 12명 아래로 떨어지면 기간이 다시 시작되므로 15명 이상 모아 둔다.
- 개발자 이름은 스토어에 공개된다. 이메일도 공개되므로 개인정보처리방침의 문의 주소와 같은 것을 권한다.

## 5. 앱 만들기와 '앱 콘텐츠' 신고 답안

콘솔 → 앱 만들기: 앱 이름 `영양제.kr`, 기본 언어 한국어, 앱(게임 아님), 무료, 개발자 프로그램 정책·미국 수출법 동의.

왼쪽 메뉴 정책 → 앱 콘텐츠 의 각 항목에 아래처럼 답한다. 항목 이름은 콘솔 개편으로 조금 다를 수 있다.

| 항목 | 답 |
|---|---|
| 개인정보처리방침 | `https://xn--og5b1hx9c.kr/privacy` (한글 주소 `영양제.kr` 은 입력란이 거부할 수 있어 퓨니코드로) |
| 광고 | 광고 없음 |
| 앱 액세스 | 모든 기능을 제한 없이 이용 가능(로그인 없음) |
| 콘텐츠 등급 | 설문 시작 → 카테고리 '참고 자료, 뉴스 또는 교육용' → 폭력·성적 내용·욕설·마약·도박 묘사 없음, 사용자 간 상호작용 없음, 위치 공유 없음, 디지털 구매 없음 → 전체 이용가로 산정됨 |
| 타겟층 및 콘텐츠 | 대상 연령 18세 이상 → 어린이 대상 아님, 어린이의 관심을 끌 가능성 없음 |
| 뉴스 앱 | 아니요 |
| 데이터 보안(데이터 안전) | 수집 '예'(방문 통계 Google Analytics) · 공유 '아니요' · 전송 중 암호화 '예' · 삭제 요청 방법 제공 '예'(개인정보처리방침 제8조의 이메일) · 데이터 유형: **앱 활동 › 앱 상호작용**(수집, 필수, 용도 분석)과 **기기 또는 기타 ID**(수집, 필수, 용도 분석) · 그 밖 항목 없음. 내 영양제·알림 설정은 기기 안에만 있어 '수집'이 아니다(개인정보처리방침 제5조) |
| 정부 앱 | 아니요 |
| 금융 기능 | 없음 |
| 건강 앱 | 건강 기능 있음 → **건강 및 피트니스 › 영양 및 체중 관리**(영양제 성분 정보·복용 시간표·복용 알림). '의료 › 약물 및 치료 관리'는 의약품 복약용이라 선택하지 않는다 — 양식의 설명문에 식이보충제(dietary supplement)가 '약물' 쪽에 적혀 있으면 그쪽으로 바꾸고 알려 주기 |
| 광고 ID | 사용 안 함(번들에 `AD_ID` 권한 없음) |

## 6. 스토어 등록정보

왼쪽 메뉴 스토어 설정 → 기본 스토어 등록정보.

- 문구: `app/store/listing.ko.md` 의 앱 이름·짧은 설명·전체 설명을 복사. 앱 카테고리 '건강/운동', 태그는 영양·건강 정도.
- 연락처: 이메일(공개됨), 웹사이트 `https://xn--og5b1hx9c.kr`.
- 그래픽: 앱 아이콘 `app/store/play-icon-512.png`(512×512), 피처 그래픽 `app/store/feature-graphic.png`(1024×500). 두 파일은 `python scripts/build_store_assets.py` 로 다시 만들 수 있다.
- 휴대전화 스크린샷: 2~8장(4장 이상 권장). 규격은 PNG/JPEG, 각 변 320~3840px, **긴 변이 짧은 변의 2배를 넘으면 거부**된다. 요즘 폰 캡처(1080×2400)는 그대로 올릴 수 없으므로 캡처를 한 폴더에 모아 아래를 실행하면 `app/store/screenshots/01.png…`(1080×1920, 여백은 브랜드 색)로 맞춰진다.

```bash
python scripts/build_store_assets.py --screens "C:/Users/<이름>/Pictures/app-shots"
```

촬영 목록(앱에서, 이 순서로 파일 이름을 01~07 로):

1. 내 영양제 목록(성분 3~4개 담긴 상태)
2. 오늘 복용 시간표
3. 휴대폰 알림 설정(시각·평일/주말)
4. 복용 기록(연속 일수와 7일 보기)
5. 링크·QR 로 옮기기 화면
6. 궁합 체크 결과(주의 조합이 하나 보이는 예)
7. 성분 상세 페이지

7인치·10인치 태블릿 스크린샷은 선택 사항이다(없어도 출시 가능, 콘솔이 경고만 한다).

## 7. 비공개 테스트

왼쪽 메뉴 테스트 → 비공개 테스트 → 트랙 만들기(이름 '비공개 테스트 1').

1. 테스터 탭: 이메일 목록 만들기 → 테스터 Gmail 주소 12명 이상(15명 이상 권장) 입력. 국가는 대한민국.
2. 버전 탭: 새 버전 만들기 → 3절의 `app-release.aab` 업로드 → 첫 업로드 때 'Play 앱 서명' 동의(구글이 앱 서명 키를 생성·보관) → 출시 노트에 `listing.ko.md` 의 출시 노트 → 검토 → 출시 시작.
3. 5·6절의 앱 콘텐츠·스토어 등록정보가 모두 완료 상태여야 출시 검토가 통과된다. 첫 검토는 보통 1~3일.
4. 출시되면 테스터 탭의 '참여 링크'를 테스터에게 보낸다. 테스터는 링크에서 '테스터 되기' → 플레이 스토어에서 설치 → 14일 동안 삭제하지 않고 둔다(옵트인 유지).
5. 14일이 지나면 대시보드에 '프로덕션 액세스 신청'이 나타난다. 설문(테스트에서 무엇을 확인했는지, 피드백을 어떻게 반영했는지)을 적어 제출하면 보통 며칠 안에 프로덕션 트랙이 열린다.

## 8. 정식 출시

프로덕션 → 새 버전 만들기 → 같은 AAB(비공개 테스트에 올린 것) 또는 새 실행의 AAB → 출시 노트 → 검토 → 출시 시작. 심사(보통 1~7일) 뒤 스토어에 공개된다.

검토 메모(콘솔이 심사 참고 사항을 물을 때):

> 영양제.kr 은 식품의약품안전처 공개 자료를 바탕으로 한 영양제 성분 정보·궁합 안내 앱입니다. 앱 전용 기능은 '내 영양제'(복용 시간표), 복용 알림(로컬 알림, 비정확 예약이라 정확 알람 권한을 쓰지 않음), 복용 기록(선택), 오프라인 안내입니다. 회원가입·로그인이 없어 계정 없이 모든 기능을 쓸 수 있습니다. 콘텐츠는 WebView 로 라이브 사이트(https://xn--og5b1hx9c.kr)를 표시하며, 건강 기능성 표현은 식약처 인정 범위만 씁니다. 1차 출시에는 쇼핑 링크가 없습니다.

## 9. 이후 업데이트

- 사이트(성분·가이드·디자인)를 고치면 앱에 바로 반영된다(앱은 라이브 사이트를 연다). 앱을 다시 올릴 필요 없음.
- 앱 껍데기(`app/`, Capacitor·플러그인 버전, 아이콘, 매니페스트)를 바꿨을 때만 `app/package.json` 의 `version` 을 올리고(예: 1.0.1) 3절대로 `release-android` 를 실행해 새 AAB 를 프로덕션에 올린다.
- 쿠팡 파트너스 최종승인 뒤 앱 안 쇼핑 버튼을 켜는 것은 `assets/js/config.js` 의 `appShopping: true` 로 사이트만 배포하면 되고 앱 재출시는 필요 없다.

## 10. 문제 해결

- **업로드 키·비밀번호 분실**: 콘솔 → 설정 → 앱 서명 → '업로드 키 재설정 요청'. 새 키(1절)를 만들어 인증서(`keytool -export -rfc -keystore … -alias upload -file upload.pem`)를 올리면 며칠 뒤 교체된다. 그 뒤 2절의 Secrets 를 새 값으로 다시 등록.
- **워크플로 파일명을 바꾸지 말 것**: versionCode 가 실행 번호라 파일명이 바뀌면 1부터 다시 시작해 플레이가 "이미 사용된 버전 코드"로 거부한다. 꼭 바꿔야 하면 워크플로에 번호 오프셋을 더한다.
- **"16KB 페이지 크기" 경고**: 네이티브 라이브러리가 있는 앱만 해당한다. 이 앱은 WebView 만 쓰고 워크플로의 번들 검사가 `.so` 파일이 없음을 확인하므로 해당 없음.
- **정확 알람 권한 질문**: 알림은 모두 비정확 예약(`assets/js/reminders.js` 의 `isExactNotification: false`)이라 `SCHEDULE_EXACT_ALARM` 을 매니페스트에서 제거했고(`app/android/app/src/main/AndroidManifest.xml` 의 `tools:node="remove"`), 번들 검사가 남아 있지 않음을 확인한다.
- **Secrets 오류로 멈춤**: 2절의 이름 4개가 정확한지 `gh secret list` 로 확인.
- **빌드 실패**: 실행 로그의 'Gradle 빌드' 단계를 본다. 디버그 빌드(`build-android.yml`)는 서명 없이 돌므로 먼저 그쪽이 성공하는지 보면 서명 문제인지 코드 문제인지 가릴 수 있다.
