# 🔐 자격증명 암호화 설정 가이드

## 개요

Triflow AI는 ERP/MES 연동 시 사용되는 민감한 자격증명(비밀번호, API Key 등)을 **Fernet 대칭키 암호화**를 사용하여 보호합니다.

이 문서는 암호화 기능을 설정하고 사용하는 방법을 설명합니다.

---

## 1. 암호화 키 생성

### 1.1 Python으로 키 생성

```bash
# 터미널에서 실행
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

출력 예시:
```
gAAAAABf3xKZ8vQ_hJ3YvZ7Q2X1bN8pQ9rK5mT6wL4sC...
```

### 1.2 환경변수 설정

생성된 키를 환경변수에 설정합니다.

#### 개발 환경 (.env 파일)

```bash
# backend/.env
ENCRYPTION_KEY=gAAAAABf3xKZ8vQ_hJ3YvZ7Q2X1bN8pQ9rK5mT6wL4sC...
```

#### 프로덕션 환경

**옵션 1: 환경변수로 설정**

```bash
export ENCRYPTION_KEY="gAAAAABf3xKZ8vQ_hJ3YvZ7Q2X1bN8pQ9rK5mT6wL4sC..."
```

**옵션 2: AWS Secrets Manager (권장)**

```bash
# 키 저장
aws secretsmanager create-secret \
    --name triflow/encryption-key \
    --secret-string "gAAAAABf3xKZ8vQ_hJ3YvZ7Q2X1bN8pQ9rK5mT6wL4sC..."

# 애플리케이션에서 로드
aws secretsmanager get-secret-value \
    --secret-id triflow/encryption-key \
    --query SecretString \
    --output text
```

**옵션 3: Docker/Kubernetes Secrets**

```yaml
# kubernetes-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: triflow-encryption
type: Opaque
data:
  ENCRYPTION_KEY: Z0FBQUFBQmYzeEtaOHZRX2hKM1l2WjdRMlgxYk44cFE5cks1bVQ2d0w0c0M=  # Base64 인코딩
```

---

## 2. Migration 실행 (기존 데이터 암호화)

기존에 평문으로 저장된 자격증명을 암호화하려면 migration을 실행합니다.

### 2.1 사전 준비

```bash
# 1. DB 백업 (필수!)
pg_dump -U postgres triflow > backup_before_encryption.sql

# 2. ENCRYPTION_KEY 환경변수 설정 확인
echo $ENCRYPTION_KEY
```

### 2.2 Migration 실행

```bash
cd backend

# Migration 실행
alembic upgrade head
```

### 2.3 실행 결과 확인

```
📊 Encrypting credentials in core.data_sources...
  ✅ Encrypted credentials for source_id: 123e4567-e89b-12d3-a456-426614174000
  ✅ Encrypted credentials for source_id: 987fcdeb-51a2-3f4d-b567-1234567890ab
  ⏭️  Skipping 456e7890-e12b-34d5-a678-426614174001 (already encrypted)

✅ Migration completed:
   - Encrypted: 2 sources
   - Skipped: 1 sources
```

---

## 3. 검증

### 3.1 DB에서 암호화 확인

```sql
-- PostgreSQL에서 확인
SELECT
    name,
    connection_config->'password' as encrypted_password
FROM core.data_sources
WHERE connection_config ? 'password';
```

**결과:**
```
name              | encrypted_password
-----------------+---------------------------
SAP Production   | "gAAAAABh3xKZ8vQ..."  ✅ 암호화됨
MySQL Dev        | "gAAAAABi4yLa9wR..."  ✅ 암호화됨
```

### 3.2 API로 복호화 확인

```bash
# 데이터 소스 조회
curl -X GET http://localhost:8000/api/v1/erp-mes/sources/{source_id} \
     -H "Authorization: Bearer YOUR_TOKEN"
```

**응답:**
```json
{
  "source_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "SAP Production",
  "connection_config": {
    "host": "sap.example.com",
    "port": 1433,
    "username": "admin",
    "password": "MySecretPassword123!"  // ✅ 복호화되어 반환됨
  }
}
```

### 3.3 연결 테스트

```bash
# 연결 테스트 (복호화가 정상 작동하는지 확인)
curl -X POST http://localhost:8000/api/v1/erp-mes/sources/{source_id}/test \
     -H "Authorization: Bearer YOUR_TOKEN"
```

**응답:**
```json
{
  "success": true,
  "message": "Connection test successful"
}
```

---

## 4. 보안 모범 사례

### 4.1 암호화 키 관리

#### ✅ DO (권장)
- 환경변수 또는 Secrets Manager에 저장
- 프로덕션과 개발 환경에 다른 키 사용
- 주기적인 키 로테이션 (분기별)
- 키를 안전한 곳에 백업 (1Password, LastPass 등)

#### ❌ DON'T (절대 금지)
- 코드에 하드코딩
- Git에 커밋
- 로그에 출력
- 슬랙/이메일로 공유

### 4.2 키 백업

```bash
# 키를 안전한 곳에 백업
echo $ENCRYPTION_KEY > encryption_key_backup.txt

# 암호화된 USB에 저장하거나
# Password Manager에 저장 (1Password, LastPass 등)
```

⚠️ **경고**: 키를 잃어버리면 **모든 암호화된 데이터를 복구할 수 없습니다!**

### 4.3 키 로테이션 (선택적)

키를 변경해야 하는 경우:

```python
# backend/scripts/rotate_encryption_key.py
from app.services.encryption_service import EncryptionService
from cryptography.fernet import Fernet

old_key = "OLD_KEY"
new_key = Fernet.generate_key().decode()

old_fernet = Fernet(old_key.encode())
new_fernet = Fernet(new_key.encode())

# 모든 데이터를 old_key로 복호화 → new_key로 재암호화
# (구현 생략 - 필요시 추가)
```

---

## 5. 트러블슈팅

### 5.1 "ENCRYPTION_KEY not found" 경고

**증상:**
```
WARNING: ENCRYPTION_KEY not found! Using auto-generated key.
This key will change on restart.
```

**해결:**
```bash
# 환경변수 설정
export ENCRYPTION_KEY="your-generated-key"

# 또는 .env 파일에 추가
echo 'ENCRYPTION_KEY=your-generated-key' >> backend/.env
```

### 5.2 "Invalid encrypted data" 에러

**원인:**
- 잘못된 암호화 키 사용
- 키가 변경됨
- 데이터 손상

**해결:**
```bash
# 1. 올바른 키 확인
echo $ENCRYPTION_KEY

# 2. DB 백업에서 복구
psql -U postgres triflow < backup_before_encryption.sql

# 3. 올바른 키로 다시 migration
alembic upgrade head
```

### 5.3 Migration 실패

**증상:**
```
Failed to encrypt source_id: ...
```

**해결:**
```bash
# 1. DB 상태 확인
alembic current

# 2. 문제가 있는 데이터 확인
psql -U postgres triflow -c "SELECT source_id, connection_config FROM core.data_sources WHERE connection_config ? 'password';"

# 3. 수동으로 수정 후 재시도
```

---

## 6. 성능 영향

### 6.1 암호화 오버헤드

- **암호화 시간**: ~0.1ms (1KB 데이터 기준)
- **복호화 시간**: ~0.1ms
- **총 오버헤드**: < 1ms (대부분의 경우 무시 가능)

### 6.2 벤치마크

```python
import time
from app.services.encryption_service import get_encryption_service

encryption = get_encryption_service()

# 1000번 암호화/복호화 테스트
start = time.time()
for _ in range(1000):
    encrypted = encryption.encrypt("MySecretPassword123!")
    decrypted = encryption.decrypt(encrypted)
end = time.time()

print(f"1000 operations: {end - start:.2f}s")  # ~0.2s
print(f"Per operation: {(end - start) / 1000 * 1000:.2f}ms")  # ~0.2ms
```

---

## 7. FAQ

### Q1. 암호화 키를 잃어버리면 어떻게 되나요?

A: **모든 암호화된 데이터를 복구할 수 없습니다.** 반드시 키를 안전한 곳에 백업하세요.

### Q2. 개발 환경에서도 암호화가 필요한가요?

A: 예. 개발 환경에서도 암호화를 사용하여 프로덕션과 동일한 환경을 유지하세요. 다만, 개발용 키와 프로덕션 키는 분리하세요.

### Q3. 이미 암호화된 데이터를 다시 암호화하면 어떻게 되나요?

A: Migration은 자동으로 감지하여 스킵합니다. 중복 암호화는 발생하지 않습니다.

### Q4. 암호화된 데이터를 평문으로 되돌릴 수 있나요?

A: 보안상의 이유로 downgrade는 지원하지 않습니다. 필요시 수동 스크립트를 작성해야 합니다.

### Q5. 어떤 필드가 암호화되나요?

A: 다음 필드가 자동으로 암호화됩니다:
- `password`
- `api_key`
- `secret`
- `token`
- `access_token`
- `refresh_token`
- `client_secret`
- `private_key`
- `ssh_key`

---

## 8. 참고 자료

- [Cryptography 라이브러리 문서](https://cryptography.io/en/latest/fernet/)
- [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

---

## 9. 지원

문제가 발생하면 다음을 확인하세요:

1. [GitHub Issues](https://github.com/your-org/triflow-ai/issues)
2. 내부 Slack 채널: #triflow-support
3. 문서: [docs/](../docs/)
