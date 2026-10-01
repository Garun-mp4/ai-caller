import asyncio, shutil
from .base import LLMProvider
from app.core.config import get_settings
from app.services.settings_service import runtime_setting

class CodexCLIProvider(LLMProvider):
    def __init__(self):
        self.settings = get_settings()
        self.binary = shutil.which(self.settings.codex_binary)
        self.model = runtime_setting("llm_model", self.settings.codex_model)
        self.reasoning_effort = runtime_setting("reasoning_effort", self.settings.codex_reasoning_effort)

    async def health(self) -> dict:
        if not self.binary:
            return {"ok": False, "detail": "Codex CLI not found in PATH"}
        try:
            proc = await asyncio.create_subprocess_exec(self.binary, "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode != 0:
                return {"ok": False, "detail": (err or out).decode(errors="ignore").strip()[:300]}
            login_detail = "authorization status not checked"
            try:
                p2 = await asyncio.create_subprocess_exec(self.binary, "login", "status", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                o2, e2 = await asyncio.wait_for(p2.communicate(), timeout=5)
                login_detail = (o2 or e2).decode(errors="ignore").strip()[:300]
                login_ok = p2.returncode == 0
            except Exception:
                login_ok = True
            return {"ok": bool(login_ok), "detail": f"{out.decode(errors='ignore').strip()} | {login_detail}"[:500]}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    async def generate(self, system_prompt, history, user_text):
        if not self.binary:
            raise RuntimeError("Codex CLI not found. Install and log in with the official Codex CLI first.")
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history[-8:])
        prompt = f"{system_prompt}\nConversation:\n{transcript}\nuser: {user_text}\nReturn JSON only."
        args = [self.binary, "exec", "--skip-git-repo-check", "-c", f'model_reasoning_effort="{self.reasoning_effort}"']
        if self.model:
            args += ["--model", self.model]
        # Prompt is passed as a process argument, never through a shell.
        args += [prompt]
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.settings.llm_timeout_seconds)
        except TimeoutError:
            proc.kill(); await proc.wait()
            raise RuntimeError("Codex CLI timed out")
        if proc.returncode != 0:
            raise RuntimeError(f"Codex CLI failed: {err.decode(errors='ignore')[-500:]}")
        return out.decode(errors="ignore").strip()
