# eBay Sandbox 설정 가이드

## 로컬 테스트를 위한 Sandbox 설정

### 1. Sandbox 키 발급
1. https://developer.ebay.com/ 접속
2. 로그인 후 "My Account" → "Create an App Key"
3. **Environment: Sandbox** 선택
4. Application 이름 입력
5. "Create App" 클릭
6. Sandbox App ID와 Cert ID 확인

### 2. 설정 방법

#### 방법 1: config.py 직접 수정
```python
# app/core/config.py
ebay_app_id: str = "SBX-xxxxx-xxxxx-xxxxx"  # Sandbox App ID
ebay_cert_id: str = "SBX-xxxxx-xxxxx-xxxxx"  # Sandbox Cert ID
ebay_sandbox_mode: bool = True
```

#### 방법 2: .env 파일 사용 (권장)
프로젝트 루트에 `.env` 파일 생성:
```env
EBAY_APP_ID=SBX-xxxxx-xxxxx-xxxxx
EBAY_CERT_ID=SBX-xxxxx-xxxxx-xxxxx
EBAY_SANDBOX_MODE=true
```

### 3. Sandbox vs Production 비교

| 항목 | Sandbox | Production |
|------|---------|------------|
| 용도 | 테스트/개발 | 실제 운영 |
| 데이터 | 테스트 데이터 | 실제 eBay 데이터 |
| 비용 | 무료 | 무료 (제한 있음) |
| API 제한 | 느슨함 | 엄격함 |
| 키 형식 | SBX-... | PRD-... 또는 AppID-... |
| 안전성 | 안전 (실제 영향 없음) | 주의 필요 |

### 4. 로컬 테스트 권장 설정

✅ **권장: Sandbox 사용**
- 안전하게 테스트 가능
- API 제한이 느슨함
- 실제 데이터에 영향 없음

❌ **비권장: Production 사용**
- 실제 데이터 사용
- API 제한이 엄격함
- 과도한 호출 시 제재 가능


