# bump_version.ps1 — 버전 일괄 업데이트 + GitHub Release 생성
# 사용법:
#   .\bump_version.ps1          # patch 자동 증가 (1.0.2 → 1.0.3)
#   .\bump_version.ps1 1.1.0    # 버전 직접 지정

param(
    [string]$NewVersion = "",
    [switch]$NoCommit
)

$ErrorActionPreference = "Stop"
$gh = "C:\Program Files\GitHub CLI\gh.exe"
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

# ── 현재 버전 읽기 (pyproject.toml 기준) ─────────────────────────────────
$toml = Get-Content "pyproject.toml" -Raw
if ($toml -notmatch 'version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
    Write-Error "pyproject.toml에서 버전을 찾을 수 없습니다."
    exit 1
}
$current = $Matches[1]
Write-Host "현재 버전: $current"

# ── 새 버전 결정 ──────────────────────────────────────────────────────────
if ($NewVersion -eq "") {
    $parts = $current.Split(".")
    $parts[2] = [string]([int]$parts[2] + 1)
    $NewVersion = $parts -join "."
}

if ($NewVersion -notmatch '^\d+\.\d+\.\d+$') {
    Write-Error "버전 형식이 잘못되었습니다. (예: 1.0.3)"
    exit 1
}

Write-Host "새 버전:   $NewVersion"
Write-Host ""

# ── 파일 업데이트 ─────────────────────────────────────────────────────────
function Update-File($path, $pattern, $replacement) {
    $content = Get-Content $path -Raw -Encoding UTF8
    $updated = $content -replace $pattern, $replacement
    if ($content -eq $updated) {
        Write-Warning "$path — 변경 없음 (패턴 불일치)"
    } else {
        [System.IO.File]::WriteAllText((Resolve-Path $path), $updated, [System.Text.Encoding]::UTF8)
        Write-Host "  OK  $path"
    }
}

Update-File "pyproject.toml" `
    '(version\s*=\s*")[0-9]+\.[0-9]+\.[0-9]+"' `
    "`${1}$NewVersion`""

Update-File "SlideMemo.iss" `
    '(#define MyAppVersion\s*")[0-9]+\.[0-9]+\.[0-9]+"' `
    "`${1}$NewVersion`""

Update-File "src\main.py" `
    '(APP_VERSION\s*=\s*")[0-9]+\.[0-9]+\.[0-9]+"' `
    "`${1}$NewVersion`""

# ── Git 커밋 + 태그 + 릴리즈 ─────────────────────────────────────────────
Write-Host ""
if ($NoCommit) {
    $answer = "n"
} else {
    $answer = Read-Host "git commit + tag + GitHub Release 생성할까요? (y/n)"
}
if ($answer -ne "y" -and $answer -ne "Y") {
    Write-Host ""
    Write-Host "완료! 파일만 수정됨. 커밋은 직접 해주세요."
    exit 0
}

git add pyproject.toml SlideMemo.iss src/main.py
git commit -m "release: v$NewVersion"
git tag "v$NewVersion"
git push origin master --tags
Write-Host ""

# ── 인스톨러 빌드 ─────────────────────────────────────────────────────────
$installer = "installer\SlideMemo-Setup.exe"
$buildAnswer = Read-Host "인스톨러 빌드도 할까요? (PyInstaller + Inno Setup) (y/n)"
if ($buildAnswer -eq "y" -or $buildAnswer -eq "Y") {
    Write-Host "PyInstaller 빌드 중..."
    uv run pyinstaller SlideMemo.spec --noconfirm
    Write-Host "Inno Setup 빌드 중..."
    & $iscc SlideMemo.iss
    Write-Host "  OK  인스톨러 빌드 완료"
}

# ── GitHub Release 생성 + 인스톨러 첨부 ──────────────────────────────────
Write-Host ""
if ((Test-Path $installer) -and ($buildAnswer -eq "y" -or $buildAnswer -eq "Y")) {
    & $gh release create "v$NewVersion" --title "v$NewVersion" --generate-notes $installer
    Write-Host ""
    Write-Host "완료! GitHub Release v$NewVersion + 인스톨러 업로드됨."
} else {
    & $gh release create "v$NewVersion" --title "v$NewVersion" --generate-notes
    Write-Host ""
    Write-Host "완료! GitHub Release v$NewVersion 생성됨."
    if (Test-Path $installer) {
        Write-Host "인스톨러 첨부하려면: & `"$gh`" release upload v$NewVersion $installer"
    }
}
