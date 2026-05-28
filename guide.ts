export const guideContent = `
## 설치하기

<Steps>
  <Step title="설치 파일 다운로드">
    릴리즈 페이지에서 \`SlideMemo-Setup.exe\`를 다운로드합니다.
  </Step>
  <Step title="설치 실행">
    설치 파일을 실행합니다. 관리자 권한은 필요하지 않습니다.

    ![설치 화면](./1.%20설치창.png)
  </Step>
  <Step title="실행">
    설치 완료 후 바탕화면 아이콘 또는 시스템 트레이에서 실행됩니다.

    ![설치 완료](./2.%20설치완료.png)
  </Step>
</Steps>

<Callout type="tip">
  제거할 때는 제어판 → 앱 → Slide Memo에서 제거하면 됩니다.
</Callout>

---

## 기본 사용법

화면 오른쪽(또는 왼쪽) 가장자리에 세로 탭 열이 표시됩니다.
탭을 클릭하면 메모 본문이 펼쳐지고, 다시 클릭하거나 <Shortcut>Esc</Shortcut> 를 누르면 접힙니다.

![사이드바 설명](./11.%20사이드바%20설명.png)

- **새 메모**: 탭 열 하단 **＋** 버튼 또는 <Shortcut>Ctrl+N</Shortcut>
- **메모 고정 / 삭제**: 탭 우클릭

![메모 우클릭 메뉴](./6.%20메모인덱스%20오른쪽마우스하면%20휴지통%2C%20고정.png)

- **색상 변경**: 본문 상단 색상 점 클릭

![사용자 지정 메모색](./10.%20사용자%20지정%20메모색.png)

- **정렬**: 본문 상단 정렬 드롭다운

![정렬](./7.%20정렬.png)

- **검색**: <Shortcut>Ctrl+F</Shortcut> 또는 검색창에서 제목·본문 검색

![제목 본문 검색](./9.%20제목%2C%20본문%20검색.png)

- **가장자리 전환**: 시스템 트레이 아이콘 우클릭 → 왼쪽/오른쪽 전환

![시스템 트레이](./시스템트레이.png)

<Callout type="tip">
  입력 후 0.6초 뒤 자동으로 저장됩니다. 즉시 저장하려면 <Shortcut>Ctrl+S</Shortcut>.
</Callout>

---

## 단축키 모음

### 메모 관리

| 단축키 | 기능 |
|--------|------|
| <Shortcut>Ctrl+N</Shortcut> | 새 메모 생성 |
| <Shortcut>Ctrl+S</Shortcut> | 즉시 저장 |
| <Shortcut>Ctrl+F</Shortcut> | 메모 검색 |
| <Shortcut>Ctrl+Shift+C</Shortcut> | 메모 전체 텍스트 복사 |
| <Shortcut>Ctrl+Shift+D</Shortcut> | 현재 메모 휴지통으로 이동 |
| <Shortcut>Esc</Shortcut> | 메모 접기 / AI 작업 취소 |

### 서식

| 단축키 | 기능 |
|--------|------|
| <Shortcut>Ctrl+B</Shortcut> | 굵게 |
| <Shortcut>Ctrl+I</Shortcut> | 기울임 |
| <Shortcut>Ctrl+U</Shortcut> | 밑줄 |
| <Shortcut>Ctrl+K</Shortcut> | 링크 삽입 |

### 날짜/시간 삽입

| 단축키 | 형식 | 예시 |
|--------|------|------|
| <Shortcut>F5</Shortcut> | 메모장 포맷 | 오전 09:30 2025-05-26 |
| <Shortcut>Ctrl+;</Shortcut> | 날짜만 | 2025-05-26 |
| <Shortcut>Ctrl+Shift+;</Shortcut> | 시간만 | 09:30 |
| <Shortcut>Ctrl+Alt+;</Shortcut> | ISO 형식 | 2025-05-26T09:30:00 |
| <Shortcut>Ctrl+Shift+H</Shortcut> | 한국식 | 2025년 05월 26일 월요일 |

### AI 기능

| 단축키 | 기능 |
|--------|------|
| <Shortcut>Ctrl+Alt+S</Shortcut> | 요약 |
| <Shortcut>Ctrl+Alt+T</Shortcut> | 번역 (한↔영) |
| <Shortcut>Ctrl+Alt+P</Shortcut> | 맞춤법 교정 |
| <Shortcut>Ctrl+Alt+H</Shortcut> | 제목 자동 생성 |
| <Shortcut>Ctrl+Alt+K</Shortcut> | 키워드 추출 |

---

## AI 기능 사용하기

<Steps>
  <Step title="API 키 입력">
    설정(⚙)을 열고 AI 탭에서 사용할 제공자의 API 키를 입력합니다.

    ![AI 기능 설정 창](./5.%20ai기능%20설정%20창.png)
  </Step>
  <Step title="AI 기능 활성화">
    **AI 기능 사용** 체크박스를 활성화하면 에디터 하단에 기능 버튼이 나타납니다.

    ![AI 기능 버튼](./8.%20ai%20기능%20선택시%20하단%20기능버튼%20생성%20.png)
  </Step>
  <Step title="기능 실행">
    버튼 클릭, 단축키, 또는 에디터 우클릭 → ✨ AI 메뉴에서 실행합니다.
  </Step>
</Steps>

**지원 기능:**

| 기능 | 설명 |
|------|------|
| 요약 | 메모 내용을 간결하게 요약합니다. |
| 번역 (한↔영) | 한국어↔영어 자동 감지 후 번역합니다. |
| 맞춤법 교정 | 철자·문법 오류를 수정합니다. |
| 제목 생성 | 내용 기반으로 제목을 자동 생성합니다. |
| 키워드 추출 | 핵심 키워드 5~10개를 추출합니다. |

<Callout type="tip">
  진행 중인 AI 작업을 취소하려면 <Shortcut>Esc</Shortcut> 를 누르세요.
</Callout>

---

## 음성 녹음 사용하기

<Steps>
  <Step title="설정 활성화">
    설정 → AI 탭에서 **음성 녹음 기능 사용**을 체크하고 OpenAI API 키를 입력합니다.
  </Step>
  <Step title="녹음 시작">
    서식바의 🎙 버튼을 눌러 녹음을 시작합니다.

    ![녹음 버튼](./녹음%20버튼.png)
  </Step>
  <Step title="녹음 종료 및 변환">
    다시 버튼을 누르면 녹음이 종료되고, Whisper가 음성을 텍스트로 변환해 에디터에 삽입합니다.
  </Step>
</Steps>

<Callout type="warning">
  마이크 권한이 필요합니다. 최대 녹음 시간은 설정에서 조절할 수 있습니다 (기본 60초).
</Callout>

---

## 휴지통

삭제한 메모는 30일간 휴지통에 보관됩니다. 탭 열 하단 🗑 버튼으로 열 수 있습니다.

![휴지통 설명](./12.휴지통%20설명.png)

복원하거나 영구 삭제하려면 휴지통 항목을 우클릭하세요.

---

## 클립보드 연동

![클립보드 설정](./3.%20클립보드%20설정된%20모습.png)

---

## 문제 해결

**앱이 화면에 보이지 않아요**
시스템 트레이(우측 하단 시계 근처) 아이콘을 클릭하거나 더블클릭하세요.

**탭 열이 너무 좁거나 넓어요**
설정 → 인덱스 탭 폭 슬라이더에서 조절하세요.

**AI 기능 버튼이 보이지 않아요**
설정 → AI 탭에서 API 키를 입력하고 AI 기능을 활성화하세요.

<Callout type="tip">
  메모 데이터는 \`%LOCALAPPDATA%\\SlideMemo\` 폴더에 SQLite 파일로 저장됩니다.
</Callout>

---

## 릴리즈 노트

### v1.0.2
- 붙여넣기 시 서식 자동 제거 — 워드·웹페이지·PDF에서 복사한 텍스트를 붙여넣을 때 폰트·색상 등 서식 없이 순수 텍스트만 입력됩니다.
- 창 앞으로 나오기 개선 — 마우스를 앱 위에 올리면 다른 창에 가려졌던 메모가 자동으로 앞으로 나옵니다.

### v1.0.1
- 부트로더 스플래시 화면 잔류 문제 수정

### v1.0.0
- 최초 릴리즈
`
