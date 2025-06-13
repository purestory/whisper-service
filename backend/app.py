# type: ignore
# pyright: ignore
from fastapi import FastAPI, File, UploadFile, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from faster_whisper import WhisperModel
import os
import tempfile
import shutil
import logging
from typing import Optional, List, Dict, Any
import torch
import io
import gc
import time
import threading
import json
from pydantic import BaseModel
import re
import urllib.parse

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Faster Whisper API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모델 초기화 (전역 변수)
model = None
current_model_size = None
model_loading = False  # 모델 로딩 중인지 여부
loading_lock = threading.Lock()  # 동시 로딩 방지

# GPU 메모리 관리를 위한 타이머 변수들
model_unload_timer = None
last_activity_time = time.time()
UNLOAD_DELAY = 3600  # 1시간 (초 단위)

# 설정 파일 경로
SETTINGS_FILE = "/home/purestory/whisper/backend/whisper_settings.json"

def load_settings():
    """설정 파일에서 마지막 모델 설정을 로드합니다."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings.get('last_model', 'base')
    except Exception as e:
        logger.warning(f"Failed to load settings: {e}")
    return 'base'  # 기본값

def save_settings(model_size: str):
    """현재 모델 설정을 파일에 저장합니다."""
    try:
        settings = {'last_model': model_size}
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        logger.info(f"Settings saved: last_model = {model_size}")
    except Exception as e:
        logger.warning(f"Failed to save settings: {e}")

def unload_model():
    """모델을 GPU 메모리에서 언로드합니다."""
    global model, current_model_size, model_loading
    
    with loading_lock:
        if model is not None:
            logger.info("Unloading Whisper model from GPU memory...")
            
            # GPU 메모리 사용량 체크 (언로드 전)
            if torch.cuda.is_available():
                before_memory = torch.cuda.memory_allocated()/1024**3
                before_reserved = torch.cuda.memory_reserved()/1024**3
                logger.info(f"언로드 전 GPU 메모리 사용량: {before_memory:.2f}GB")
                logger.info(f"언로드 전 GPU 예약 메모리: {before_reserved:.2f}GB")
            
            model = None
            current_model_size = None
            model_loading = False
            
            # 강화된 GPU 메모리 정리
            if torch.cuda.is_available():
                # 강제 가비지 컬렉션
                gc.collect()
                
                # GPU 메모리 정리 (여러 번 실행)
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # GPU 작업 완료 대기
                torch.cuda.empty_cache()  # 한 번 더 실행
                
                # 추가적인 GPU 메모리 해제 시도
                if hasattr(torch.cuda, 'reset_peak_memory_stats'):
                    torch.cuda.reset_peak_memory_stats()
                if hasattr(torch.cuda, 'reset_accumulated_memory_stats'):
                    torch.cuda.reset_accumulated_memory_stats()
                
                # 강제 가비지 컬렉션 한 번 더
                gc.collect()
                torch.cuda.empty_cache()
                
                # GPU 메모리 사용량 체크 (언로드 후)
                after_memory = torch.cuda.memory_allocated()/1024**3
                after_reserved = torch.cuda.memory_reserved()/1024**3
                freed_memory = before_memory - after_memory
                freed_reserved = before_reserved - after_reserved
                logger.info(f"언로드 후 GPU 메모리 사용량: {after_memory:.2f}GB")
                logger.info(f"언로드 후 GPU 예약 메모리: {after_reserved:.2f}GB")
                logger.info(f"해제된 GPU 메모리: {freed_memory:.2f}GB")
                logger.info(f"해제된 예약 메모리: {freed_reserved:.2f}GB")
            
            logger.info("Whisper model unloaded successfully")

def schedule_model_unload():
    """모델 언로드를 예약합니다."""
    global model_unload_timer
    
    # 기존 타이머가 있다면 취소
    if model_unload_timer is not None:
        model_unload_timer.cancel()
    
    # 새 타이머 시작
    model_unload_timer = threading.Timer(UNLOAD_DELAY, unload_model)
    model_unload_timer.start()
    logger.info(f"Model unload scheduled for {UNLOAD_DELAY} seconds from now")

def reset_activity_timer():
    """활동 타이머를 리셋하고 언로드 스케줄을 갱신합니다."""
    global last_activity_time
    last_activity_time = time.time()
    
    # 모델이 로드되어 있다면 언로드 타이머 재설정
    if model is not None:
        schedule_model_unload()

def load_model(model_size: str = "base", device: str = "auto", compute_type: str = "auto"):
    """모델을 로드합니다."""
    global model, current_model_size, model_loading
    
    # 이미 로드된 모델이 요청된 모델과 같으면 바로 반환
    if model is not None and current_model_size == model_size:
        reset_activity_timer()
        return model
    
    # 로딩 락 획득 (다른 요청이 로딩 중이면 대기)
    with loading_lock:
        # 락을 획득한 후 다시 확인 (다른 스레드가 이미 로드했을 수 있음)
        if model is not None and current_model_size == model_size:
            reset_activity_timer()
            return model
        
        # 이미 로딩 중이면 대기 (실제로는 이 상황이 발생하지 않아야 함)
        if model_loading:
            logger.warning("Model is already loading, this should not happen")
            return None
        
        try:
            model_loading = True
            logger.info(f"Starting to load model: {model_size}")
            
            # 장치 설정
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # 컴퓨트 타입 설정
            if compute_type == "auto":
                if device == "cuda":
                    compute_type = "float16"
                else:
                    compute_type = "int8"
            
            logger.info(f"Loading model: {model_size} on {device} with {compute_type}")
            
            # 기존 모델 언로드
            if model is not None:
                logger.info("Unloading previous model")
                model = None
                current_model_size = None
                
            # 강화된 GPU 메모리 정리
            if torch.cuda.is_available():
                gc.collect()
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                gc.collect()
            
            # 새 모델 로드
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
            current_model_size = model_size
            model_loading = False
            
            logger.info(f"Model {model_size} loaded successfully")
            
            # 모델 설정 저장
            save_settings(model_size)
            
            # 모델 로드 후 언로드 타이머 시작
            schedule_model_unload()
            
            # 활동 타이머 리셋
            reset_activity_timer()
            
            return model
            
        except Exception as e:
            model_loading = False
            logger.error(f"Error loading model: {str(e)}")
            
            # 로드 실패 시 더 작은 모델로 폴백 (재귀 호출 방지)
            if model_size.startswith('large') and not model_size.endswith('_fallback'):
                logger.info("Falling back to medium model due to loading error")
                return load_model("medium_fallback", device, compute_type)
            elif model_size.startswith('medium') and not model_size.endswith('_fallback'):
                logger.info("Falling back to small model due to loading error")
                return load_model("small_fallback", device, compute_type)
            else:
                raise HTTPException(status_code=500, detail=f"Error loading model: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    # 저장된 설정 로드
    last_model = load_settings()
    logger.info(f"Whisper STT server started - last used model: {last_model} (will be loaded on first access)")

@app.get("/")
async def root():
    """API 상태 확인"""
    # 웹페이지 접속은 활동으로 간주하지만 모델은 실제 사용시에만 로드
    # 단순히 활동 시간만 갱신
    global last_activity_time
    last_activity_time = time.time()
    
    return {"message": "Faster Whisper API is running", "status": "ok"}

@app.get("/models")
async def get_available_models():
    """사용 가능한 모델 목록 반환"""
    models = [
        "tiny", "tiny.en", 
        "base", "base.en", 
        "small", "small.en", 
        "medium", "medium.en", 
        "large-v1", "large-v2", "large-v3", "large-v3-turbo",
        "distil-large-v2", "distil-large-v3"
    ]
    return {"models": models}

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    model_size: Optional[str] = None,
    language: Optional[str] = None,
    word_timestamps: bool = False,
    beam_size: int = 5,
    vad_filter: bool = True
):
    # 활동 타이머 리셋
    reset_activity_timer()
    
    effective_model_size = model_size if model_size else current_model_size
    if not effective_model_size:
        # 저장된 설정에서 마지막 모델 사용
        effective_model_size = load_settings()

    logger.info(f"Received /transcribe request. Requested model_size: {model_size}, Effective model_size: {effective_model_size}")
    
    # content_type이 None인 경우를 처리
    if not file.content_type or not (file.content_type.startswith('audio/') or file.content_type.startswith('video/')):
        raise HTTPException(status_code=400, detail="업로드된 파일이 음성 또는 영상 파일이 아닙니다.")
    
    # filename이 None인 경우를 처리
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")
    
    # 임시 파일로 저장
    temp_dir = tempfile.mkdtemp()
    temp_file_path = None
    
    try:
        # 파일 확장자 추출
        file_extension = os.path.splitext(file.filename)[1]
        temp_file_path = os.path.join(temp_dir, f"audio{file_extension}")
        
        # 파일 저장
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Audio file saved: {temp_file_path}")
        
        # 모델 로드 (load_model에서 중복 체크 처리)
        loaded_model = load_model(effective_model_size)
        
        if loaded_model is None:
            raise HTTPException(status_code=500, detail="모델 로드에 실패했습니다")
        
        # 변환 옵션 설정
        transcribe_options = {
            "beam_size": beam_size,
            "word_timestamps": word_timestamps,
            "vad_filter": vad_filter
        }
        
        if language:
            transcribe_options["language"] = language
        
        logger.info(f"Starting transcription with model {effective_model_size}, options: {transcribe_options}")
        
        # 음성 변환 실행
        segments, info = loaded_model.transcribe(temp_file_path, **transcribe_options)
        
        # 결과 수집
        result_segments = []
        full_text = ""
        total_characters = 0
        
        for segment in segments:
            segment_data = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            }
            
            if word_timestamps and hasattr(segment, 'words') and segment.words:
                segment_data["words"] = [
                    {
                        "start": word.start,
                        "end": word.end,
                        "word": word.word,
                        "probability": getattr(word, 'probability', None)
                    }
                    for word in segment.words
                ]
            
            result_segments.append(segment_data)
            full_text += segment.text.strip() + " "
            total_characters += len(segment.text.strip())
        
        # 초당 변환 글자 개수 계산
        characters_per_second = total_characters / info.duration if info.duration > 0 else 0
        
        # 응답 데이터 구성
        response_data = {
            "text": full_text.strip(),
            "segments": result_segments,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
            "total_characters": total_characters,
            "characters_per_second": round(characters_per_second, 2),
            "model_size": effective_model_size,
            "options": transcribe_options
        }
        
        logger.info(f"Transcription completed. Language: {info.language}, Duration: {info.duration}s, Characters: {total_characters}, CPS: {characters_per_second:.2f}, Model: {effective_model_size}")
        
        return JSONResponse(content=response_data)
    
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"변환 중 오류가 발생했습니다: {str(e)}")
    
    finally:
        # 임시 파일 정리
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

@app.post("/change_model")
async def change_model(model_size: str):
    """모델 변경"""
    try:
        # 활동 타이머 리셋
        reset_activity_timer()
        
        load_model(model_size)
        return {"message": f"Model changed to {model_size}", "current_model": model_size}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error changing model: {str(e)}")

@app.get("/status")
async def get_status():
    """서버 상태 및 현재 모델 정보"""
    # status 요청은 단순 조회이므로 타이머 리셋하지 않음
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # GPU 메모리 사용량 정보 추가
    gpu_memory_info = {}
    if torch.cuda.is_available():
        gpu_memory_info = {
            "allocated": torch.cuda.memory_allocated() // (1024**2),  # MB 단위
            "cached": torch.cuda.memory_reserved() // (1024**2),      # MB 단위
            "total": torch.cuda.get_device_properties(0).total_memory // (1024**2)  # MB 단위
        }
    
    return {
        "status": "running",
        "current_model": current_model_size,
        "saved_model": load_settings(),
        "device": device,
        "cuda_available": torch.cuda.is_available(),
        "gpu_memory": gpu_memory_info,
        "model_loaded": model is not None,
        "model_loading": model_loading,
        "last_activity": last_activity_time,
        "unload_scheduled": model_unload_timer is not None and model_unload_timer.is_alive()
    }

# --- 다운로드 기능 추가 ---
def format_timestamp(seconds: float, srt_format: bool = True) -> str:
    """초 단위를 HH:MM:SS,mmm 또는 HH:MM:SS.mmm 형식으로 변환"""
    assert seconds >= 0, "음수가 아닌 시간 값이 필요합니다"
    milliseconds = round(seconds * 1000.0)

    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000

    minutes = milliseconds // 60_000
    milliseconds %= 60_000

    seconds = milliseconds // 1_000
    milliseconds %= 1_000
    
    separator = "," if srt_format else "."
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{milliseconds:03d}"

def generate_txt_content(segments: List[Dict[str, Any]], full_text: str, include_timestamps: bool) -> str:
    if not include_timestamps:
        return full_text
    
    lines = []
    for segment in segments:
        start_time = format_timestamp(segment["start"], srt_format=False)
        end_time = format_timestamp(segment["end"], srt_format=False)
        lines.append(f"[{start_time} --> {end_time}] {segment['text']}")
    return "\n".join(lines)

def generate_srt_content(segments: List[Dict[str, Any]]) -> str:
    lines = []
    for i, segment in enumerate(segments):
        start_time = format_timestamp(segment["start"], srt_format=True)
        end_time = format_timestamp(segment["end"], srt_format=True)
        lines.append(str(i + 1))
        lines.append(f"{start_time} --> {end_time}")
        lines.append(segment["text"])
        lines.append("")  # 빈 줄 추가
    return "\n".join(lines)

def generate_vtt_content(segments: List[Dict[str, Any]]) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        start_time = format_timestamp(segment["start"], srt_format=False)
        end_time = format_timestamp(segment["end"], srt_format=False)
        lines.append(f"{start_time} --> {end_time}")
        lines.append(segment["text"])
        lines.append("")  # 빈 줄 추가
    return "\n".join(lines)

class SegmentData(BaseModel):
    start: float
    end: float
    text: str
    words: Optional[List[Dict[str, Any]]] = None

class DownloadRequest(BaseModel):
    segments: List[SegmentData]
    full_text: str
    file_format: str  # "txt", "srt", "vtt"
    txt_include_timestamps: Optional[bool] = False # txt 형식일 경우 타임스탬프 포함 여부
    original_filename: Optional[str] = None # 원본 파일명

def sanitize_filename(filename: str) -> str:
    """파일명에서 위험한 문자만 제거하고 안전한 파일명으로 변환"""
    if not filename:
        return "transcription"
    
    # 위험한 문자들만 제거 (파일시스템에서 문제가 되는 문자들)
    # 제거할 문자: / \ : * ? " < > |
    dangerous_chars = r'[/\\:*?"<>|]'
    safe_filename = re.sub(dangerous_chars, '', filename)
    
    # 제어 문자 제거 (ASCII 0-31)
    safe_filename = re.sub(r'[\x00-\x1f]', '', safe_filename)
    
    # 연속된 공백을 하나로 변경
    safe_filename = re.sub(r'\s+', ' ', safe_filename)
    
    # 앞뒤 공백과 점 제거 (Windows에서 문제가 될 수 있음)
    safe_filename = safe_filename.strip(' .')
    
    # 파일명이 너무 길면 자르기 (확장자 제외하고 150자로 제한)
    if len(safe_filename) > 150:
        safe_filename = safe_filename[:150].strip()
    
    # 빈 문자열이면 기본값 반환
    if not safe_filename:
        return "transcription"
    
    return safe_filename

@app.post("/download")
async def download_transcription(request_data: DownloadRequest = Body(...)):
    file_format = request_data.file_format.lower()
    segments_as_dict = [segment.model_dump() for segment in request_data.segments]

    content = ""
    media_type = "text/plain"
    
    # 디버깅을 위한 로그 추가
    logger.info(f"Download request - original_filename: {request_data.original_filename}")
    
    # 원본 파일명에서 확장자만 변경하여 다운로드 파일명 생성
    if request_data.original_filename:
        # 확장자 제거
        base_name = os.path.splitext(request_data.original_filename)[0]
        logger.info(f"Base name after removing extension: {base_name}")
        # 파일명 안전하게 처리
        safe_base_name = sanitize_filename(base_name)
        logger.info(f"Safe base name after sanitization: {safe_base_name}")
        filename = f"{safe_base_name}.{file_format}"
    else:
        filename = f"transcription.{file_format}"
    
    logger.info(f"Final filename: {filename}")

    if file_format == "txt":
        content = generate_txt_content(segments_as_dict, request_data.full_text, request_data.txt_include_timestamps or False)
    elif file_format == "srt":
        content = generate_srt_content(segments_as_dict)
        media_type = "application/x-subrip"
    elif file_format == "vtt":
        content = generate_vtt_content(segments_as_dict)
        media_type = "text/vtt"
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")

    if not content:
        raise HTTPException(status_code=500, detail="파일 내용 생성에 실패했습니다.")
        
    # 문자열을 바이트 스트림으로 변환
    stream = io.BytesIO(content.encode("utf-8"))
    
    # 파일명을 안전하게 처리 (RFC 5987 표준 준수)
    # ASCII 안전한 파일명 생성 (fallback용)
    ascii_filename = re.sub(r'[^\x20-\x7E]', '_', filename)
    # UTF-8 인코딩된 파일명
    encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
    
    logger.info(f"ASCII filename: {ascii_filename}")
    logger.info(f"Encoded filename: {encoded_filename}")
    
    return StreamingResponse(
        stream,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
        }
    )
# --- 다운로드 기능 추가 완료 ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 