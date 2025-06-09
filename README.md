# 🎤 Faster Whisper 음성 인식 서비스

## 📖 프로젝트 개요

SYSTRAN의 faster-whisper를 기반으로 한 고성능 음성-텍스트 변환 웹 서비스입니다.
OpenAI Whisper 대비 최대 4배 빠른 성능으로 실시간 음성 인식을 제공합니다.

### 주요 기능
- **고속 음성 인식**: OpenAI Whisper 대비 4배 빠른 처리 속도
- **다양한 모델 지원**: tiny부터 large-v3까지 성능/속도 최적화 모델
- **실시간 웹 인터페이스**: 직관적이고 반응형 UI/UX
- **다국어 지원**: 100+ 언어 자동 감지 및 인식
- **고급 옵션**: 단어별 타임스탬프, VAD 필터, 빔 서치 최적화
- **GPU 가속**: CUDA 지원으로 초고속 처리

## 🏗️ 시스템 구조

```
whisper/
├── backend/                    # FastAPI Python 백엔드
│   ├── app.py                 # 메인 API 서버
│   └── __pycache__/           # Python 캐시
├── vite-frontend/             # React + Vite 프론트엔드
│   ├── src/                   # 소스 코드
│   ├── dist/                  # 빌드된 정적 파일
│   ├── public/                # 정적 리소스
│   └── package.json           # 의존성 설정
├── .venv/                     # Python 가상환경 (현재 사용중)
├── tmp/                       # nginx 설정 백업
├── requirements.txt           # Python 의존성
└── README.md                  # 프로젝트 문서
```

## 🚀 서비스 운영 상태

### 현재 운영 중인 서비스
- **백엔드 서버**: systemd로 관리되는 서비스
  - **서비스명**: `whisper-backend.service`
  - **포트**: 3401 (FastAPI + uvicorn)
  - **상태**: active (running)
  - **자동 시작**: enabled (부팅 시 자동 시작)
  
- **프론트엔드**: nginx가 정적 파일 직접 서빙
  - **빌드 파일**: `/home/purestory/whisper/vite-frontend/dist/`
  - **nginx 설정**: `/whisper/` 경로로 접근

### 웹 접근 주소
- **외부 접근**: `http://itsmyzone.iptime.org/whisper/`
- **API 엔드포인트**: `http://itsmyzone.iptime.org/whisper-api/`
- **헬스 체크**: `http://itsmyzone.iptime.org/whisper-api/status`

## 🔧 시스템 관리 명령어

### 백엔드 서비스 관리
```bash
# 서비스 상태 확인
systemctl status whisper-backend.service

# 서비스 재시작
sudo systemctl restart whisper-backend.service

# 서비스 중지
sudo systemctl stop whisper-backend.service

# 서비스 로그 확인
sudo journalctl -u whisper-backend.service -f
```

### 프론트엔드 서비스 관리
```bash
# 서비스 상태 확인
systemctl status whisper-frontend.service

# 서비스 재시작
sudo systemctl restart whisper-frontend.service
```

### 포트 사용 확인
```bash
# 백엔드 포트 확인
lsof -i :3401

# 프로세스 확인
ps aux | grep whisper
```

## 🛠️ 개발 및 배포

### 프론트엔드 수정 시
1. **코드 수정**: `/home/purestory/whisper/vite-frontend/src/` 에서 수정
2. **빌드**: 
   ```bash
   cd /home/purestory/whisper/vite-frontend
   npm run build
   ```
3. **자동 반영**: nginx가 `/home/purestory/whisper/vite-frontend/dist/` 를 직접 서빙하므로 빌드만 하면 됨
4. **⚠️ 주의**: 수동 복사 작업 금지!

### 백엔드 수정 시
1. **코드 수정**: `/home/purestory/whisper/backend/` 에서 수정
2. **서비스 재시작**: 
   ```bash
   sudo systemctl restart whisper-backend.service
   ```
3. **동작 확인**: 
   ```bash
   curl http://localhost:3401/status
   ```

### 새 모델 추가
```bash
# 가상환경 활성화
cd /home/purestory/whisper
source .venv/bin/activate

# Python에서 모델 다운로드 (자동)
python3 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3')"
```

## 🌐 nginx 설정

### 현재 nginx 설정
- **정적 파일**: `/whisper/` → `/home/purestory/whisper/vite-frontend/dist/`
- **API 프록시**: `/whisper-api/` → `http://localhost:5173/`

### nginx 설정 파일 위치
- **메인 설정**: `/etc/nginx/sites-available/purestory`
- **백업**: `/home/purestory/tmp/purestory_nginx_updated.conf`

## 📊 지원하는 모델

| 모델 | 크기 | 메모리 요구량 | 특징 |
|------|------|-------------|------|
| `tiny` | 39MB | ~1GB | 초고속, 기본 품질 |
| `base` | 74MB | ~1GB | 빠름, 양호한 품질 |
| `small` | 244MB | ~2GB | 균형잡힌 성능 |
| `medium` | 769MB | ~5GB | 높은 품질 |
| `large-v1` | 1550MB | ~10GB | 최고 품질 |
| `large-v2` | 1550MB | ~10GB | 개선된 품질 |
| `large-v3` | 1550MB | ~10GB | 최신 버전, 최고 성능 |
| `distil-large-v2` | 756MB | ~6GB | 경량화된 large 모델 |
| `distil-large-v3` | 756MB | ~6GB | 최신 경량화 모델 |

## 🌍 지원하는 언어

- **한국어** (ko) - 주요 지원 언어
- **영어** (en) - 최적화 모델 있음
- **일본어** (ja) - 동아시아 언어
- **중국어** (zh) - 간체/번체
- **스페인어** (es) - 라틴 언어
- **프랑스어** (fr) - 유럽 언어  
- **독일어** (de) - 게르만 언어
- **이탈리아어** (it) - 로망스 언어
- **포르투갈어** (pt) - 브라질/포르투갈
- **러시아어** (ru) - 슬라브 언어
- **아랍어** (ar) - 셈족 언어
- **힌디어** (hi) - 인도 언어
- **기타 90+ 언어** - 자동 감지 지원

## 📁 지원하는 오디오 형식

### 입력 형식
- **MP3**: 가장 널리 사용되는 형식
- **WAV**: 무손실 오디오
- **MP4**: 비디오에서 오디오 추출
- **M4A**: Apple 오디오 형식  
- **FLAC**: 무손실 압축
- **OGG**: 오픈소스 형식
- **최대 크기**: 200MB

### 출력 형식
- **텍스트**: 순수 텍스트
- **SRT**: 자막 파일 (타임스탬프 포함)
- **VTT**: WebVTT 형식
- **JSON**: API 응답 형식

## 🔧 API 엔드포인트

### GET `/status`
서버 상태 및 현재 로드된 모델 정보
```json
{
  "status": "healthy",
  "current_model": "large-v3",
  "gpu_available": true,
  "memory_usage": "1.4GB"
}
```

### GET `/models`
사용 가능한 모델 목록
```json
{
  "models": ["tiny", "base", "small", "medium", "large-v3"],
  "current": "large-v3"
}
```

### POST `/transcribe`
음성 파일을 텍스트로 변환
```bash
curl -X POST "http://localhost:3401/transcribe" \
  -F "file=@audio.mp3" \
  -F "model_size=large-v3" \
  -F "language=ko" \
  -F "word_timestamps=true"
```

**Parameters:**
- `file`: 음성 파일 (multipart/form-data)
- `model_size`: 모델 크기 (기본값: "large-v3")
- `language`: 언어 코드 (선택사항, 자동 감지)
- `word_timestamps`: 단어별 타임스탬프 (기본값: false)
- `beam_size`: 빔 크기 (기본값: 5)
- `vad_filter`: VAD 필터 (기본값: true)

### POST `/change_model`
사용할 모델 변경
```bash
curl -X POST "http://localhost:3401/change_model" \
  -H "Content-Type: application/json" \
  -d '{"model_size": "base"}'
```

## 🚨 트러블슈팅

### 서비스 시작 실패
1. **포트 충돌 확인**: `lsof -i :3401`
2. **프로세스 종료**: `kill -15 <PID>`
3. **서비스 재시작**: `sudo systemctl restart whisper-backend.service`

### CUDA/GPU 문제
1. **GPU 상태 확인**: `nvidia-smi`
2. **CUDA 설치 확인**: `nvcc --version`
3. **메모리 부족**: 더 작은 모델 사용 (base, small)

### 메모리 부족 오류
1. **현재 메모리**: `free -h`
2. **모델 변경**: large → medium → small → base
3. **서비스 재시작**: 메모리 정리

### 인식 품질 문제
1. **오디오 품질 확인**: 16kHz 이상 권장
2. **노이즈 제거**: VAD 필터 활성화
3. **모델 업그레이드**: large-v3 사용
4. **언어 명시**: 자동 감지 대신 언어 코드 지정

### API 응답 없음
1. **서비스 상태**: `systemctl status whisper-backend.service`
2. **로그 확인**: `sudo journalctl -u whisper-backend.service -n 50`
3. **헬스 체크**: `curl http://localhost:3401/status`

## ⚙️ 시스템 요구사항

### 최소 요구사항
- **CPU**: Intel i5 또는 AMD Ryzen 5 이상
- **RAM**: 8GB (tiny/base 모델)
- **저장공간**: 10GB 여유 공간
- **Python**: 3.8 이상
- **Node.js**: 16 이상

### 권장 요구사항  
- **CPU**: Intel i7 또는 AMD Ryzen 7 이상
- **RAM**: 32GB (large 모델용)
- **GPU**: NVIDIA RTX 3060 이상 (8GB VRAM)
- **저장공간**: 50GB SSD
- **CUDA**: 11.8 이상

## ⚠️ 중요 주의사항

### 하지 말아야 할 것들
1. **모델 파일 직접 삭제 금지** - 재다운로드에 시간 소요
2. **가상환경 삭제 금지** - `.venv` 폴더 보존
3. **포트 3401 변경 금지** - 시스템 설정과 연관
4. **CUDA 드라이버 임의 업데이트 금지**
5. **대용량 파일 동시 처리 금지** - 메모리 부족 위험

### 권장 작업 순서
1. **코드 수정**
2. **해당 서비스만 재시작** (프론트엔드: 빌드, 백엔드: systemctl restart)
3. **동작 확인** (curl 테스트 또는 웹 접속)
4. **로그 확인** (문제 시)
5. **GPU 메모리 모니터링** (nvidia-smi)

## 📈 성능 모니터링

### 처리 통계
- **실시간 진행률**: 오디오 청크별 처리 상태
- **성능 지표**: 처리 속도 (실시간 배수), 정확도
- **언어 감지**: 자동 언어 감지 확률
- **품질 측정**: 신뢰도 점수

### 시스템 리소스
```bash
# GPU 사용률 및 메모리
nvidia-smi

# CPU 및 메모리 사용량
htop

# 디스크 사용량
df -h /home/purestory/whisper/

# 네트워크 연결 상태
netstat -tulpn | grep 3401
```

### 모델 성능 비교
| 모델 | 속도 | 정확도 | 메모리 | 용도 |
|------|------|--------|--------|------|
| tiny | 10x | 80% | 1GB | 실시간 처리 |
| base | 7x | 85% | 1GB | 일반 용도 |
| small | 4x | 90% | 2GB | 품질 중시 |
| medium | 2x | 95% | 5GB | 높은 품질 |
| large-v3 | 1x | 98% | 10GB | 최고 품질 |

## 🔧 가상환경 관리

### Python 의존성
```bash
# 가상환경 활성화
cd /home/purestory/whisper
source .venv/bin/activate

# 의존성 확인
pip list

# 의존성 업데이트 (주의!)
pip install --upgrade faster-whisper
```

### Node.js 의존성
```bash
# 프론트엔드 의존성 확인
cd /home/purestory/whisper/vite-frontend
npm list

# 의존성 업데이트
npm update
```

## 📞 개발자 노트

이 서비스는 GPU 리소스를 집약적으로 사용하므로 메모리 관리가 중요합니다.
대용량 오디오 파일 처리 시 시스템 모니터링을 통해 리소스 사용량을 확인하세요.

모델 변경 시 GPU 메모리 정리를 위해 서비스 재시작이 필요할 수 있습니다.
품질과 성능의 균형을 위해 용도에 맞는 모델을 선택하세요.

**최종 업데이트**: 2025-06-05
**서비스 버전**: 2.0.0  
**운영 환경**: Ubuntu 20.04, Python 3.10, CUDA 11.8, faster-whisper 1.0.0 