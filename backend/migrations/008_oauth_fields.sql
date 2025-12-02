-- V1 Sprint 4: OAuth2 Support
-- User 테이블에 OAuth 관련 필드 추가

-- ============================================
-- 1. User 테이블에 OAuth 필드 추가
-- ============================================

-- OAuth 제공자 (google, github, microsoft 등)
ALTER TABLE core.users
ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50);

-- OAuth 제공자별 고유 ID
ALTER TABLE core.users
ADD COLUMN IF NOT EXISTS oauth_provider_id VARCHAR(255);

-- 프로필 이미지 URL
ALTER TABLE core.users
ADD COLUMN IF NOT EXISTS profile_image_url VARCHAR(500);

-- 표시 이름 (이미 있을 수 있으므로 IF NOT EXISTS)
ALTER TABLE core.users
ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);

-- password_hash를 nullable로 변경 (OAuth 사용자는 비밀번호 없음)
ALTER TABLE core.users
ALTER COLUMN password_hash DROP NOT NULL;

-- ============================================
-- 2. 인덱스 추가
-- ============================================

-- OAuth 제공자 + ID로 빠른 조회
CREATE INDEX IF NOT EXISTS idx_users_oauth
ON core.users(oauth_provider, oauth_provider_id)
WHERE oauth_provider IS NOT NULL;

-- 이메일 유니크 인덱스 (이미 있을 수 있음)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
ON core.users(email);
