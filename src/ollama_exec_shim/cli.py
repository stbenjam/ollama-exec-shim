import os
import subprocess
import json
import asyncio
import re
import shlex
from typing import List, Optional, AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime, timezone

app = FastAPI(title="Ollama Exec Shim")

# Get allowlist from environment
ALLOWLIST = os.environ.get("OLLAMA_EXEC_ALLOWLIST")

def is_allowed(script_path: str) -> bool:
    if not ALLOWLIST:
        return True
    
    allowed_dirs = ALLOWLIST.split(":")
    abs_script_path = os.path.realpath(script_path)
    
    for allowed_dir in allowed_dirs:
        abs_allowed_dir = os.path.realpath(allowed_dir)
        if abs_script_path.startswith(abs_allowed_dir):
            return True
    return False

# Get token from environment
EXEC_TOKEN = os.environ.get("OLLAMA_EXEC_TOKEN")

async def verify_token(authorization: Optional[str] = Header(None)):
    if not EXEC_TOKEN:
        return
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization.split(" ")[1]
    if token != EXEC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/", dependencies=[Depends(verify_token)])
@app.head("/", dependencies=[Depends(verify_token)])
async def root():
    return {"status": "ok"}

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: bool = False

class ChatResponse(BaseModel):
    model: str
    created_at: str
    message: Message
    done: bool

class ModelInfo(BaseModel):
    name: str
    modified_at: str
    size: int
    digest: str

class TagsResponse(BaseModel):
    models: List[ModelInfo]

def get_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

@app.get("/api/tags", dependencies=[Depends(verify_token)])
async def get_tags():
    return TagsResponse(
        models=[
            ModelInfo(
                name="exec",
                modified_at=get_timestamp(),
                size=0,
                digest="exec-shim-digest"
            )
        ]
    )

@app.post("/api/show", dependencies=[Depends(verify_token)])
async def show(request: dict):
    return {
        "modelfile": "FROM exec",
        "parameters": "",
        "template": "{{ .Prompt }}",
        "details": {
            "format": "gguf",
            "family": "exec",
            "families": ["exec"],
            "parameter_size": "0B",
            "quantization_level": "None"
        }
    }

@app.post("/api/pull", dependencies=[Depends(verify_token)])
async def pull(request: dict):
    # Just yield success immediately
    async def pull_stream():
        yield json.dumps({"status": "pulling manifest", "done": False}) + "\n"
        yield json.dumps({"status": "success", "done": True}) + "\n"
    return StreamingResponse(pull_stream(), media_type="application/x-ndjson")

async def run_script_streaming(args: List[str]) -> AsyncGenerator[str, None]:
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def stream_pipe(pipe, is_stderr=False):
            while True:
                line = await pipe.readline()
                if not line:
                    break
                content = line.decode().rstrip()
                if is_stderr:
                    content = f"\nSTDERR: {content}"
                
                yield json.dumps({
                    "model": "exec",
                    "created_at": get_timestamp(),
                    "message": {"role": "assistant", "content": content + "\n"},
                    "done": False
                }) + "\n"

        # Stream stdout and then stderr
        async for chunk in stream_pipe(process.stdout):
            yield chunk
        async for chunk in stream_pipe(process.stderr, is_stderr=True):
            yield chunk

        await process.wait()
        
        yield json.dumps({
            "model": "exec",
            "created_at": get_timestamp(),
            "message": {"role": "assistant", "content": ""},
            "done": True
        }) + "\n"

    except Exception as e:
        yield json.dumps({
            "model": "exec",
            "created_at": get_timestamp(),
            "message": {"role": "assistant", "content": f"Error executing script: {str(e)}"},
            "done": True
        }) + "\n"

def extract_command(text: str) -> List[str]:
    # Try to find EXEC[/path/to/script --args]
    match = re.search(r'EXEC\[(.*?)\]', text)
    if match:
        return shlex.split(match.group(1).strip())
    # Fallback to the original behavior (treating the whole message as a path)
    return shlex.split(text.strip())

@app.post("/api/generate", dependencies=[Depends(verify_token)])
async def generate(request: dict):
    model = request.get("model")
    if model != "exec":
        raise HTTPException(status_code=404, detail=f"Model '{model}' not found.")

    prompt = request.get("prompt", "")
    args = extract_command(prompt)
    stream = request.get("stream", False)

    if not args:
        raise HTTPException(status_code=400, detail="No command provided.")

    script_path = args[0]

    if not os.path.exists(script_path):
        error_msg = f"Error: File not found: {script_path}"
        return {"model": "exec", "created_at": get_timestamp(), "response": error_msg, "done": True}

    if not os.access(script_path, os.X_OK):
        error_msg = f"Error: File is not executable: {script_path}"
        return {"model": "exec", "created_at": get_timestamp(), "response": error_msg, "done": True}

    if stream:
        async def generate_stream():
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            while True:
                line = await process.stdout.readline()
                if not line: break
                yield json.dumps({"model": "exec", "created_at": get_timestamp(), "response": line.decode(), "done": False}) + "\n"
            while True:
                line = await process.stderr.readline()
                if not line: break
                yield json.dumps({"model": "exec", "created_at": get_timestamp(), "response": f"\nSTDERR: {line.decode()}", "done": False}) + "\n"
            await process.wait()
            yield json.dumps({"model": "exec", "created_at": get_timestamp(), "response": "", "done": True}) + "\n"
        return StreamingResponse(generate_stream(), media_type="application/x-ndjson")

    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        output = result.stdout
        if result.stderr:
            output += f"\n\nSTDERR:\n{result.stderr}"
        return {"model": "exec", "created_at": get_timestamp(), "response": output.strip() or "(no output)", "done": True}
    except Exception as e:
        return {"model": "exec", "created_at": get_timestamp(), "response": f"Error: {str(e)}", "done": True}

@app.post("/api/chat", dependencies=[Depends(verify_token)])
async def chat(request: ChatRequest):
    if request.model != "exec":
        raise HTTPException(status_code=404, detail=f"Model '{request.model}' not found. Only 'exec' is supported.")

    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    args = extract_command(request.messages[-1].content)
    if not args:
        raise HTTPException(status_code=400, detail="No command provided.")

    script_path = args[0]

    if not os.path.exists(script_path):
        error_msg = f"Error: File not found: {script_path}"
        if request.stream:
            return StreamingResponse(
                (json.dumps({
                    "model": "exec",
                    "created_at": get_timestamp(),
                    "message": {"role": "assistant", "content": error_msg},
                    "done": True
                }) + "\n" for _ in range(1)),
                media_type="application/x-ndjson"
            )
        return ChatResponse(
            model="exec",
            created_at=get_timestamp(),
            message=Message(role="assistant", content=error_msg),
            done=True
        )

    if not os.access(script_path, os.X_OK):
        error_msg = f"Error: File is not executable: {script_path}"
        if request.stream:
            return StreamingResponse(
                (json.dumps({
                    "model": "exec",
                    "created_at": get_timestamp(),
                    "message": {"role": "assistant", "content": error_msg},
                    "done": True
                }) + "\n" for _ in range(1)),
                media_type="application/x-ndjson"
            )
        return ChatResponse(
            model="exec",
            created_at=get_timestamp(),
            message=Message(role="assistant", content=error_msg),
            done=True
        )

    if not is_allowed(script_path):
        error_msg = f"Error: Path not in allowlist: {script_path}"
        if request.stream:
            return StreamingResponse(
                (json.dumps({
                    "model": "exec",
                    "created_at": get_timestamp(),
                    "message": {"role": "assistant", "content": error_msg},
                    "done": True
                }) + "\n" for _ in range(1)),
                media_type="application/x-ndjson"
            )
        return ChatResponse(
            model="exec",
            created_at=get_timestamp(),
            message=Message(role="assistant", content=error_msg),
            done=True
        )

    if request.stream:
        return StreamingResponse(run_script_streaming(args), media_type="application/x-ndjson")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\n\nSTDERR:\n{result.stderr}"
            
        return ChatResponse(
            model="exec",
            created_at=get_timestamp(),
            message=Message(role="assistant", content=output.strip() or "(no output)"),
            done=True
        )
    except Exception as e:
        return ChatResponse(
            model="exec",
            created_at=get_timestamp(),
            message=Message(role="assistant", content=f"Error executing script: {str(e)}"),
            done=True
        )

def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=11434)

if __name__ == "__main__":
    main()

def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=11434)

if __name__ == "__main__":
    main()
