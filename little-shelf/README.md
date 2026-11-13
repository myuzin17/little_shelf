# 🌷 Little Shelf

친구들이 직접 꾸민 화분·꽃병을 선물하면 나만의 작은 선반(4×5, 20칸)이 채워지는 Streamlit 웹사이트.
로그인 없이 링크 하나로 동작합니다.

## 파일 구조
```
little-shelf/
├─ app.py                  # 화면(홈 · 선반 · 식물 만들기 · 선물 보기)과 라우팅
├─ art.py                  # 식물 이미지 합성 (assets PNG 우선, 없으면 Pillow로 직접 그림)
├─ db.py                   # SupabaseStore(실서비스) / DemoStore(임시 데모)
├─ requirements.txt
├─ supabase_schema.sql     # 테이블·제약조건·보안 설정
├─ .streamlit/
│  ├─ config.toml          # 파스텔 테마
│  └─ secrets.toml.example # 비밀 키 예시 (실제 값 없음)
└─ assets/                 # (선택) containers/, flowers/ PNG — assets/README.md 참고
```

## 로컬 실행 (데모 모드)
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
secrets가 없으면 자동으로 **데모 모드**가 켜지고 화면 상단에 안내가 표시됩니다.
데모 데이터는 서버 메모리에만 있어 재시작하면 사라지며, 실제 공유·영구 저장은 지원하지 않습니다.

## Supabase 연결 (실제 저장·공유)
1. [supabase.com](https://supabase.com)에서 프로젝트를 만듭니다.
2. **SQL Editor**에 `supabase_schema.sql` 전체를 붙여넣고 Run 합니다.
3. **Project Settings → API**에서 Project URL과 `service_role`(또는 secret) 키를 복사합니다.
4. `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사해 값을 채웁니다.
5. `streamlit run app.py` — 데모 안내가 사라지면 Supabase에 연결된 것입니다.

보안 구조: 테이블에 RLS를 켜고 정책을 만들지 않아 공개(anon) 키로는 접근할 수 없습니다.
서버(Streamlit)만 service_role 키로 접근하고, 키는 브라우저나 URL로 나가지 않습니다.
코드에는 조회와 등록만 있어 기존 선물을 수정·삭제하는 경로가 없습니다.
같은 칸 중복 등록은 `UNIQUE (shelf_id, slot_number)`로 막고, 충돌하면 “다른 친구가 먼저 채웠어요”로 안내합니다.

## Streamlit Community Cloud 배포
1. 이 폴더를 GitHub 저장소로 올립니다. (`secrets.toml`은 `.gitignore`에 있어 올라가지 않아요)
2. [share.streamlit.io](https://share.streamlit.io) → **Create app** → 저장소·브랜치, 메인 파일 `app.py` 선택
3. **Advanced settings → Secrets**에 `secrets.toml.example`의 내용을 값과 함께 붙여넣습니다.
4. Deploy 후 나온 주소를 `APP_URL`로 secrets에 추가하면 공유 링크가 항상 전체 주소로 표시됩니다.

## 알아둘 점
- 남용 방지는 접속자(IP)별 횟수·간격 제한을 서버 메모리에 두는 기본 수준입니다. 서버를 재시작하면 초기화되고,
  선반 생성 수에는 전체 상한이 없습니다. 공개 규모가 커지면 Supabase Edge Function이나 Cloudflare 등을 앞에 두세요.
- 링크를 아는 사람은 누구나 선반과 메시지를 볼 수 있습니다. 화면에 개인정보 입력 금지 안내가 있습니다.
- 선반 칸은 링크(`?shelf=…&slot=…`)로 이동하므로 칸을 누를 때 페이지가 새로 로드됩니다.
  링크가 막히는 환경을 위해 선반 아래에 “칸 번호로 직접 고르기”도 넣어 두었습니다.
