import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = '/whisper-api';

interface Segment {
  start: number;
  end: number;
  text: string;
  words?: Word[];
}

interface Word {
  word: string;
  start: number;
  end: number;
}

interface TranscriptionResult {
  text: string;
  segments: Segment[];
  language: string;
  language_probability: number;
  duration: number;
  total_characters: number;
  characters_per_second: number;
  model_size: string;
}

interface ServerStatus {
  status: string;
  message?: string;
  current_model?: string;
  device?: string;
}

interface Language {
  code: string;
  name: string;
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [transcribing, setTranscribing] = useState<boolean>(false);
  const [transcribeProgress, setTranscribeProgress] = useState<string>('');
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    // localStorage에서 저장된 모델 로드, 없으면 'base'
    return localStorage.getItem('whisper_selected_model') || 'base';
  });
  const [language, setLanguage] = useState<string>('');
  const [wordTimestamps, setWordTimestamps] = useState<boolean>(false);
  const [beamSize, setBeamSize] = useState<number>(5);
  const [vadFilter, setVadFilter] = useState<boolean>(true);
  const [serverStatus, setServerStatus] = useState<ServerStatus | null>(null);
  const [downloadFormat, setDownloadFormat] = useState<string>('txt');
  const [txtIncludeTimestamps, setTxtIncludeTimestamps] = useState<boolean>(false);
  const [transcriptionTime, setTranscriptionTime] = useState<number | null>(null);



  const languages: Language[] = [
    { code: '', name: '자동 감지' },
    { code: 'ko', name: '한국어' },
    { code: 'en', name: '영어' },
    { code: 'ja', name: '일본어' },
    { code: 'zh', name: '중국어' },
    { code: 'es', name: '스페인어' },
    { code: 'fr', name: '프랑스어' },
    { code: 'de', name: '독일어' },
    { code: 'it', name: '이탈리아어' },
    { code: 'pt', name: '포르투갈어' },
    { code: 'ru', name: '러시아어' }
  ];

  // 모델 변경시 localStorage에 저장
  useEffect(() => {
    if (selectedModel) {
      localStorage.setItem('whisper_selected_model', selectedModel);
      console.log(`모델 선택 저장: ${selectedModel}`);
    }
  }, [selectedModel]);

  useEffect(() => {
    checkServerStatus();
    fetchModels();
  }, []);



  useEffect(() => {
    const changeServerModel = async () => {
      if (selectedModel && models.includes(selectedModel)) {
        try {
          console.log(`서버 모델 변경 시도: ${selectedModel}`);
          const response = await axios.post(`${API_BASE_URL}/change_model?model_size=${selectedModel}`);
          console.log('서버 모델 변경 응답:', response.data);
          // 모델 변경 후 상태 갱신하지 않음 (무한 루프 방지)
        } catch (error: any) {
          console.error('서버 모델 변경 실패:', error);
          alert('서버 모델 변경 중 오류가 발생했습니다: ' + 
                (error.response?.data?.detail || error.message));
        }
      } else if (selectedModel && !models.includes(selectedModel)) {
        console.warn(`선택된 모델 ${selectedModel}이(가) 유효한 모델 목록에 없습니다.`);
      }
    };

    // 모델이 선택되고 모델 목록이 로드되면 즉시 실행
    if (selectedModel && models.length > 0 && models.includes(selectedModel)) {
      // 서버 상태에서 가져온 모델이 아닌 경우에만 API 호출
      if (serverStatus?.current_model !== selectedModel) {
        changeServerModel();
      }
    }

  }, [selectedModel, models]); // serverStatus 제거하여 무한 루프 방지

  const checkServerStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/status`);
      setServerStatus(response.data);
      
      // localStorage에 저장된 모델이 없거나 'base'이고, 서버에 다른 모델이 설정되어 있는 경우에만 업데이트
      const savedModel = localStorage.getItem('whisper_selected_model');
      if (!savedModel || savedModel === 'base') {
        if (response.data.current_model && response.data.current_model !== 'base') {
          console.log(`서버에서 현재 모델 로드: ${response.data.current_model}`);
          setSelectedModel(response.data.current_model);
        } else if (response.data.saved_model && response.data.saved_model !== 'base') {
          console.log(`서버에서 저장된 모델 로드: ${response.data.saved_model}`);
          setSelectedModel(response.data.saved_model);
        }
      }
    } catch (error) {
      console.error('서버 상태 확인 실패:', error);
      setServerStatus({ status: 'error', message: '서버에 연결할 수 없습니다' });
    }
  };

  const fetchModels = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/models`);
      setModels(response.data.models);
    } catch (error) {
      console.error('모델 목록 가져오기 실패:', error);
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
      // 비디오 파일이면 자동으로 SRT 형식 선택
      if (selectedFile.type.startsWith('video/')) {
        setDownloadFormat('srt');
      }
    }
  };



  const handleTranscribe = async () => {
    if (!file) {
      alert('음성 또는 영상 파일을 선택해주세요.');
      return;
    }

    setTranscribing(true);
    setResult(null);
    setTranscriptionTime(null);
    setProgressPercent(0);

    try {
      // 파일 크기에 따른 진행률 비율 계산
      const fileSizeMB = file.size / (1024 * 1024);
      let uploadRatio, modelRatio, transcribeRatio, resultRatio;
      
      if (fileSizeMB < 5) {
        // 작은 파일: 업로드 빠름, 변환 비중 높음
        uploadRatio = 5;
        modelRatio = 5;
        transcribeRatio = 85;
        resultRatio = 5;
      } else if (fileSizeMB < 25) {
        // 중간 파일: 균형잡힌 비율
        uploadRatio = 10;
        modelRatio = 5;
        transcribeRatio = 80;
        resultRatio = 5;
      } else if (fileSizeMB < 100) {
        // 큰 파일: 업로드 시간 증가
        uploadRatio = 15;
        modelRatio = 5;
        transcribeRatio = 75;
        resultRatio = 5;
      } else {
        // 매우 큰 파일: 업로드 최대 15%
        uploadRatio = 15;
        modelRatio = 10;
        transcribeRatio = 70;
        resultRatio = 5;
      }

      // 1단계: 파일 준비
      setTranscribeProgress(`📁 업로드 준비 중... (${fileSizeMB.toFixed(1)}MB)`);
      setProgressPercent(2);

      const formData = new FormData();
      formData.append('file', file);
      formData.append('language', language);
      formData.append('word_timestamps', wordTimestamps.toString());
      formData.append('beam_size', beamSize.toString());
      formData.append('vad_filter', vadFilter.toString());

      const startTime = Date.now();

      const response = await axios.post(`${API_BASE_URL}/transcribe`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000, // 5분 타임아웃
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            // 동적 업로드 비율 적용
            const uploadPercent = Math.round((progressEvent.loaded * uploadRatio) / progressEvent.total);
            setProgressPercent(2 + uploadPercent);
            
            const uploadedMB = (progressEvent.loaded / (1024 * 1024)).toFixed(1);
            const totalMB = (progressEvent.total / (1024 * 1024)).toFixed(1);
            setTranscribeProgress(`📤 파일 업로드 중... (${uploadedMB}/${totalMB}MB)`);
            
            // 업로드 완료시 변환 시작
            if (progressEvent.loaded === progressEvent.total) {
              const modelStartPercent = 2 + uploadRatio;
              const transcribeStartPercent = modelStartPercent + modelRatio;
              
              setTimeout(() => {
                setTranscribeProgress('🤖 모델 준비 중...');
                setProgressPercent(modelStartPercent);
                
                setTimeout(() => {
                  setTranscribeProgress('🎤 음성을 텍스트로 변환 중...');
                  setProgressPercent(transcribeStartPercent);
                  
                  // 변환 시간 예상 (파일 크기 기반)
                  const estimatedTranscribeTime = Math.max(3000, fileSizeMB * 200); // 최소 3초
                  const transcribeEndPercent = transcribeStartPercent + transcribeRatio;
                  
                  // 변환 중 진행률 시뮬레이션
                  const interval = setInterval(() => {
                    setProgressPercent(prev => {
                      if (prev >= transcribeEndPercent) {
                        clearInterval(interval);
                        return transcribeEndPercent;
                      }
                      return prev + 1;
                    });
                  }, estimatedTranscribeTime / transcribeRatio);
                }, 300);
              }, 100);
            }
          }
        },
        onDownloadProgress: (progressEvent) => {
          // 다운로드 진행시 (응답 받는 중)
          const resultStartPercent = 2 + uploadRatio + modelRatio + transcribeRatio;
          setTranscribeProgress('📝 변환 결과 수신 중...');
          if (progressEvent.total) {
            const downloadPercent = Math.round((progressEvent.loaded * resultRatio) / progressEvent.total);
            setProgressPercent(resultStartPercent + downloadPercent);
          } else {
            setProgressPercent(resultStartPercent + Math.floor(resultRatio / 2));
          }
        },
      });

      // 완료
      setTranscribeProgress('✅ 변환 완료!');
      setProgressPercent(100);

      const endTime = Date.now();
      setResult(response.data);
      setTranscriptionTime((endTime - startTime) / 1000);

      // 완료 메시지 잠시 표시 후 초기화
      setTimeout(() => {
        setTranscribeProgress('');
        setProgressPercent(0);
      }, 1500);

    } catch (error: any) {
      console.error('변환 실패:', error);
      setTranscribeProgress('❌ 변환 실패');
      setProgressPercent(0);
      alert('음성 변환 중 오류가 발생했습니다: ' + (error.response?.data?.detail || error.message));
      setTranscriptionTime(null);
      
      setTimeout(() => {
        setTranscribeProgress('');
      }, 2000);
    } finally {
      setTranscribing(false);
    }
  };

  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      alert('클립보드에 복사되었습니다!');
    });
  };

  const handleDownload = async () => {
    if (!result) {
      alert('먼저 음성 변환을 실행해주세요.');
      return;
    }

    try {
      const payload = {
        segments: result.segments,
        full_text: result.text,
        file_format: downloadFormat,
        txt_include_timestamps: downloadFormat === 'txt' ? txtIncludeTimestamps : false,
        original_filename: file?.name || 'transcription'
      };

      const response = await axios.post(`${API_BASE_URL}/download`, payload, {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const contentDisposition = response.headers['content-disposition'];
      let filename = `transcription.${downloadFormat}`;
      
      if (contentDisposition) {
        // RFC 5987 표준에 따른 파일명 파싱
        // filename*=UTF-8''encoded_filename 형식을 우선 처리
        const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (utf8Match && utf8Match[1]) {
          try {
            filename = decodeURIComponent(utf8Match[1]);
          } catch (e) {
            console.warn('UTF-8 파일명 디코딩 실패:', e);
          }
        } else {
          // fallback: filename="..." 형식 처리
          const asciiMatch = contentDisposition.match(/filename="([^"]+)"/i);
          if (asciiMatch && asciiMatch[1]) {
            filename = asciiMatch[1];
          }
        }
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

    } catch (error: any) {
      console.error('다운로드 실패:', error);
      alert('파일 다운로드 중 오류가 발생했습니다: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <h1>🎤 Faster Whisper 음성 인식</h1>
          <p>고품질 AI 음성을 텍스트로 변환해보세요</p>
          {serverStatus && (
            <div className={`status ${serverStatus.status}`}>
              <span className="status-indicator"></span>
              서버 상태: {serverStatus.status === 'running' ? '실행 중' : '오류'}
              {serverStatus.current_model && ` | 현재 모델: ${serverStatus.current_model}`}
              {serverStatus.device && ` | 장치: ${serverStatus.device.toUpperCase()}`}
            </div>
          )}
        </header>

        <div className="upload-section">
          <div className="file-input-compact">
            <input
              type="file"
              id="audioFile"
              accept=".mp3,.mp4,.wav,.m4a,.aac,.ogg,.flac,.wma,.avi,.mov,.mkv,.wmv,.webm,.flv,.3gp,.m4v,.mpg,.mpeg,.ogv,.ts,.mts,.m2ts,.vob,.divx,.xvid,.rm,.rmvb,.asf"
              onChange={handleFileChange}
              className="file-input"
            />
            <label htmlFor="audioFile" className="file-label-compact">
              📁 파일 선택
            </label>
            {file && (
              <div className="file-info-compact">
                <span className="file-name">{file.name}</span>
                <span className="file-size">({(file.size / 1024 / 1024).toFixed(1)}MB)</span>
              </div>
            )}
          </div>
        </div>

        <div className="options-section">
          <div className="options-grid">
            <div className="option-group">
              <label>모델 선택:</label>
              <select 
                value={selectedModel} 
                onChange={(e) => setSelectedModel(e.target.value)}
                className="select-input"
              >
                {models.map(model => (
                  <option key={model} value={model}>
                    {model}{model.startsWith('distil') ? ' (영어 전용)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="option-group">
              <label>언어:</label>
              <select 
                value={language} 
                onChange={(e) => setLanguage(e.target.value)}
                className="select-input"
              >
                {languages.map(lang => (
                  <option key={lang.code} value={lang.code}>{lang.name}</option>
                ))}
              </select>
            </div>

            <div className="option-group">
              <label>빔 크기:</label>
              <input
                type="number"
                min="1"
                max="10"
                value={beamSize}
                onChange={(e) => setBeamSize(parseInt(e.target.value))}
                className="number-input"
              />
            </div>

            <div className="option-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={wordTimestamps}
                  onChange={(e) => setWordTimestamps(e.target.checked)}
                />
                단어별 타임스탬프
              </label>
            </div>

            <div className="option-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={vadFilter}
                  onChange={(e) => setVadFilter(e.target.checked)}
                />
                음성 감지 필터
              </label>
            </div>
          </div>
        </div>

        <div className="action-section">
          <button
            onClick={handleTranscribe}
            disabled={!file || transcribing}
            className="transcribe-button"
          >
            {transcribing ? '🔄 변환 중...' : '🚀 음성 변환 시작'}
          </button>
          
          {transcribing && (
            <div className="progress-section">
              <div className="progress-text">
                {transcribeProgress || '변환 준비 중...'}
              </div>
              <div className="progress-bar-container">
                <div 
                  className="progress-bar"
                  style={{ width: `${progressPercent}%` }}
                ></div>
              </div>
              <div className="progress-percent">
                {progressPercent}%
              </div>
            </div>
          )}
        </div>

        {result && (
          <div className="result-section">
            <div className="result-header">
              <h2>📝 변환 결과</h2>
              <button
                onClick={() => copyToClipboard(result.text)}
                className="copy-button"
              >
                📋 전체 텍스트 복사
              </button>
            </div>

            <div className="download-options">
              <h3>결과 다운로드:</h3>
              <div className="option-group">
                <label htmlFor="downloadFormat">파일 형식:</label>
                <select 
                  id="downloadFormat"
                  value={downloadFormat} 
                  onChange={(e) => setDownloadFormat(e.target.value)}
                  className="select-input"
                >
                  <option value="txt">TXT (텍스트)</option>
                  <option value="srt">SRT (자막)</option>
                  <option value="vtt">VTT (자막)</option>
                </select>
              </div>
              {downloadFormat === 'txt' && (
                <div className="option-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={txtIncludeTimestamps}
                      onChange={(e) => setTxtIncludeTimestamps(e.target.checked)}
                    />
                    시간 정보 포함 (TXT)
                  </label>
                </div>
              )}
              <button
                onClick={handleDownload}
                className="download-button"
              >
                💾 다운로드
              </button>
            </div>

            <div className="result-info">
              <div className="info-grid">
                <div>언어: <strong>{result.language}</strong></div>
                <div>신뢰도: <strong>{(result.language_probability * 100).toFixed(1)}%</strong></div>
                <div>음성 길이: <strong>{result.duration.toFixed(1)}초</strong></div>
                <div>총 글자 수: <strong>{result.total_characters}자</strong></div>
                <div>초당 변환: <strong>{result.characters_per_second}자/초</strong></div>
                <div>모델: <strong>{result.model_size}</strong></div>
                {transcriptionTime !== null && (
                  <div>총 소요 시간: <strong>{transcriptionTime.toFixed(1)}초</strong></div>
                )}
              </div>
            </div>

            <div className="result-text">
              <h3>전체 텍스트:</h3>
              <div className="text-content">
                {result.text}
              </div>
            </div>

            {result.segments && result.segments.length > 0 && (
              <div className="segments-section">
                <h3>구간별 텍스트:</h3>
                <div className="segments-list">
                  {result.segments.map((segment, index) => (
                    <div key={index} className="segment-item">
                      <div className="segment-time">
                        {formatTime(segment.start)} - {formatTime(segment.end)}
                      </div>
                      <div className="segment-text">{segment.text}</div>
                      {wordTimestamps && segment.words && (
                        <div className="words-list">
                          {segment.words.map((word, wordIndex) => (
                            <span key={wordIndex} className="word-item">
                              {word.word}
                              <small>({formatTime(word.start)}-{formatTime(word.end)})</small>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
