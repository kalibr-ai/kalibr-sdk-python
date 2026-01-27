"""KalibrApp - Advanced app framework with async, file uploads, sessions"""

from typing import Callable, List, Optional

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
from kalibr.kalibr import Kalibr
from kalibr.types import FileUpload, Session


class KalibrApp(Kalibr):
    """Advanced Kalibr app with file uploads, sessions, and streaming"""

    def __init__(self, title: str = "Kalibr API", version: str = "1.0.0"):
        super().__init__(title=title, version=version)
        self.sessions = {}  # In-memory session store

    def file_handler(self, name: str, allowed_extensions: List[str]):
        """Decorator for file upload handlers"""

        def decorator(func: Callable):
            @self.app.post(f"/proxy/{name}")
            async def file_endpoint(file: UploadFile = File(...)):
                # Validate file extension
                if allowed_extensions:
                    ext = f".{file.filename.split('.')[-1]}"
                    if ext not in allowed_extensions:
                        return {"error": f"File type not allowed. Allowed: {allowed_extensions}"}

                # Create FileUpload object
                content = await file.read()
                file_obj = FileUpload(
                    filename=file.filename,
                    content_type=file.content_type,
                    size=len(content),
                    content=content,
                )

                # Call handler
                result = await func(file_obj)
                return result

            return func

        return decorator

    def session_action(self, name: str, description: str = ""):
        """Decorator for session-based actions"""

        def decorator(func: Callable):
            @self.app.post(f"/proxy/{name}")
            async def session_endpoint(session_id: str, **kwargs):
                # Get or create session
                if session_id not in self.sessions:
                    self.sessions[session_id] = Session(session_id)

                session = self.sessions[session_id]

                # Call handler
                result = await func(session, **kwargs)
                return result

            return func

        return decorator

    def stream_action(self, name: str):
        """Decorator for streaming responses"""

        def decorator(func: Callable):
            @self.app.post(f"/proxy/{name}")
            async def stream_endpoint(**kwargs):
                async def generate():
                    async for chunk in func(**kwargs):
                        yield chunk

                return StreamingResponse(generate(), media_type="text/event-stream")

            return func

        return decorator
