import pytest
from fastapi.testclient import TestClient
from ollama_exec_shim.cli import app, extract_command
import os
import stat

client = TestClient(app)

def test_extract_command():
    assert extract_command("EXEC[/bin/ls -la]") == ["/bin/ls", "-la"]
    assert extract_command("[cron] EXEC[/usr/bin/python3 script.py] timestamp") == ["/usr/bin/python3", "script.py"]
    assert extract_command("/bin/echo hello") == ["/bin/echo", "hello"]

def test_get_tags():
    response = client.get("/api/tags")
    assert response.status_code == 200
    data = response.json()
    assert data["models"][0]["name"] == "exec"

def test_generate_endpoint(tmp_path):
    # Create a dummy script
    script = tmp_path / "hello.sh"
    script.write_text("#!/bin/bash\necho 'hello world'")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    
    response = client.post("/api/generate", json={
        "model": "exec",
        "prompt": f"EXEC[{str(script)}]",
        "stream": False
    })
    
    assert response.status_code == 200
    assert "hello world" in response.json()["response"]

def test_chat_endpoint(tmp_path):
    # Create a dummy script
    script = tmp_path / "hello.sh"
    script.write_text("#!/bin/bash\necho 'hello world'")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    
    response = client.post("/api/chat", json={
        "model": "exec",
        "messages": [{"role": "user", "content": f"EXEC[{str(script)}]"}]
    })
    
    assert response.status_code == 200
    assert "hello world" in response.json()["message"]["content"]

def test_allowlist(tmp_path, monkeypatch):
    # Setup allowlist
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()
    
    monkeypatch.setenv("OLLAMA_EXEC_ALLOWLIST", str(allowed_dir))
    
    # Create script in allowed dir
    allowed_script = allowed_dir / "test.sh"
    allowed_script.write_text("#!/bin/bash\necho 'ok'")
    allowed_script.chmod(allowed_script.stat().st_mode | stat.S_IEXEC)
    
    # Create script in blocked dir
    blocked_script = blocked_dir / "test.sh"
    blocked_script.write_text("#!/bin/bash\necho 'bad'")
    blocked_script.chmod(blocked_script.stat().st_mode | stat.S_IEXEC)
    
    # Test allowed
    response = client.post("/api/chat", json={
        "model": "exec",
        "messages": [{"role": "user", "content": f"EXEC[{str(allowed_script)}]"}]
    })
    assert "ok" in response.json()["message"]["content"]
    
    # Test blocked
    response = client.post("/api/chat", json={
        "model": "exec",
        "messages": [{"role": "user", "content": f"EXEC[{str(blocked_script)}]"}]
    })
    assert "Error: Path not in allowlist" in response.json()["message"]["content"]
