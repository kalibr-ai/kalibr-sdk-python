"""Advanced Kalibr example - Document processing with file uploads"""

from kalibr import KalibrApp, FileUpload, Session

app = KalibrApp(title="Document Processing API")


@app.file_handler("analyze_document", [".pdf", ".docx", ".txt"])
async def analyze_document(file: FileUpload) -> dict:
    """
    Analyze an uploaded document.
    
    Args:
        file: Uploaded document file
    
    Returns:
        Analysis results
    """
    # Mock analysis
    return {
        "filename": file.filename,
        "size": file.size,
        "content_type": file.content_type,
        "word_count": len(file.content.decode('utf-8', errors='ignore').split()),
        "analysis": "Document processed successfully"
    }


@app.session_action("save_preferences", "Save user preferences")
async def save_preferences(session: Session, theme: str, language: str) -> dict:
    """
    Save user preferences in session.
    
    Args:
        session: User session
        theme: UI theme preference
        language: Language preference
    
    Returns:
        Confirmation
    """
    session.set("theme", theme)
    session.set("language", language)
    
    return {
        "status": "saved",
        "preferences": {
            "theme": theme,
            "language": language
        }
    }


@app.session_action("get_preferences", "Get user preferences")
async def get_preferences(session: Session) -> dict:
    """
    Retrieve user preferences from session.
    
    Args:
        session: User session
    
    Returns:
        User preferences
    """
    return {
        "theme": session.get("theme", "light"),
        "language": session.get("language", "en")
    }


if __name__ == "__main__":
    app.run()
