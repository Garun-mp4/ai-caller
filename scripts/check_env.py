from pathlib import Path
import os, shutil, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.chdir(ROOT/'backend')
from app.core.config import get_settings
s=get_settings()
checks={
    'codex_cli': bool(shutil.which(s.codex_binary)),
    'piper_binary': bool(shutil.which(s.piper_binary)),
    'vosk_model': Path(s.vosk_model_path).expanduser().exists(),
    'piper_model': Path(s.piper_model_path).expanduser().exists(),
    'twilio_configured': bool(s.twilio_account_sid and s.twilio_auth_token and s.twilio_phone_number),
}
print('Optional/live provider checks:')
for k,v in checks.items(): print(f'  {k}: {"OK" if v else "not configured"}')
print(f'Default modes: AUTH_MODE={s.auth_mode}, LLM_PROVIDER={s.llm_provider}, TELEPHONY_PROVIDER={s.telephony_provider}')
if s.llm_provider=='mock' and s.telephony_provider=='mock': print('Mock MVP is ready without live providers.')
