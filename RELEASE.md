# 릴리즈 가이드

## 사전 준비

- [GitHub CLI](https://cli.github.com/) 설치 (`C:\Program Files\GitHub CLI\gh.exe`)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) 설치 (`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`)
- `gh auth login` 으로 GitHub 로그인 완료

---

## 릴리즈 방법

PowerShell에서 프로젝트 폴더로 이동 후 실행:

```powershell
cd C:\Users\choiy\Desktop\SlideMemo
.\bump_version.ps1
```

### 버전 자동 증가 (patch)
```powershell
.\bump_version.ps1          # 1.0.4 → 1.0.5
```

### 버전 직접 지정
```powershell
.\bump_version.ps1 1.1.0
```

---

## 실행 흐름

1. `pyproject.toml`, `SlideMemo.iss`, `src/main.py` 버전 일괄 수정
2. **git commit + tag + push + GitHub Release 생성할까요?** (y/n)
3. **인스톨러 빌드도 할까요?** (y/n)
   - `y` → PyInstaller + Inno Setup 빌드 후 Release에 자동 첨부
   - `n` → Release만 생성 (인스톨러는 나중에 수동 업로드)

---

## 인스톨러 수동 업로드

빌드 후 따로 올리고 싶을 때:

```powershell
& "C:\Program Files\GitHub CLI\gh.exe" release upload v1.0.5 installer\SlideMemo-Setup.exe
```
