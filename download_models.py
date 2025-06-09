#!/usr/bin/env python3
"""
Faster Whisper 모델들을 미리 다운로드하는 스크립트
"""

import os
import sys
import torch
from faster_whisper import WhisperModel
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_model(model_size: str, device: str = "auto", compute_type: str = "auto"):
    """특정 모델을 다운로드"""
    try:
        # 장치 설정
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 컴퓨트 타입 설정
        if compute_type == "auto":
            if device == "cuda":
                compute_type = "float16"
            else:
                compute_type = "int8"
        
        logger.info(f"📥 다운로드 중: {model_size} (device: {device}, compute_type: {compute_type})")
        
        # 모델 로드 (자동으로 다운로드됨)
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        
        logger.info(f"✅ 완료: {model_size}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 실패: {model_size} - {str(e)}")
        return False

def main():
    """메인 함수"""
    print("🎤 Faster Whisper 모델 다운로드 시작")
    print("=" * 50)
    
    # 시스템 정보 출력
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🖥️  장치: {device.upper()}")
    if device == "cuda":
        print(f"🔥 GPU: {torch.cuda.get_device_name()}")
        print(f"💾 VRAM: {torch.cuda.get_device_properties(0).total_memory // 1024**3}GB")
    
    print("\n📦 다운로드할 모델들:")
    
    # 다운로드할 모델들 (용량 순서)
    models_to_download = [
        "tiny",      # ~39MB
        "tiny.en",   # ~39MB  
        "base",      # ~74MB
        "base.en",   # ~74MB
        "small",     # ~244MB
        "small.en",  # ~244MB
        "medium",    # ~769MB
        "medium.en", # ~769MB
        "large-v3",  # ~1550MB
        "large-v3-turbo", # ~1550MB (더 빠른 처리속도)
    ]
    
    # 선택적 다운로드 (큰 모델들)
    optional_models = [
        "large-v1",     # ~1550MB
        "large-v2",     # ~1550MB
        "distil-large-v2",  # ~756MB
        "distil-large-v3",  # ~756MB
    ]
    
    print("기본 모델들:")
    for model in models_to_download:
        if model == "large-v3-turbo":
            print(f"  - {model} (⚡ 터보 - 빠른 처리)")
        else:
            print(f"  - {model}")
    
    print("\n선택적 모델들 (용량이 큼):")
    for model in optional_models:
        print(f"  - {model}")
    
    # 사용자 선택
    download_all = input("\n🤔 모든 모델을 다운로드하시겠습니까? (y/N): ").lower().strip()
    
    if download_all == 'y':
        all_models = models_to_download + optional_models
    else:
        all_models = models_to_download
    
    print(f"\n🚀 {len(all_models)}개 모델 다운로드 시작...")
    print("=" * 50)
    
    # 모델 다운로드
    success_count = 0
    failed_models = []
    
    for i, model_size in enumerate(all_models, 1):
        print(f"\n[{i}/{len(all_models)}] {model_size}")
        if model_size == "large-v3-turbo":
            print("  ⚡ 터보 모델 - 더 빠른 처리 속도!")
        
        if download_model(model_size):
            success_count += 1
        else:
            failed_models.append(model_size)
    
    # 결과 출력
    print("\n" + "=" * 50)
    print("📊 다운로드 완료!")
    print(f"✅ 성공: {success_count}/{len(all_models)}")
    
    if failed_models:
        print(f"❌ 실패: {len(failed_models)}")
        print("실패한 모델들:")
        for model in failed_models:
            print(f"  - {model}")
    
    print("\n🎉 모든 모델이 준비되었습니다!")
    print("💡 추천: large-v3-turbo 모델은 정확도는 large-v3와 비슷하지만 더 빠릅니다!")
    print("이제 웹 애플리케이션에서 빠르게 모델을 사용할 수 있습니다.")

if __name__ == "__main__":
    main() 