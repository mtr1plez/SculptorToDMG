from pydantic import BaseModel
from typing import List, Optional

class IngestRequest(BaseModel):
    file_path: str
    alias: str
    fullname: str

class BuildRequest(BaseModel):
    project_name: str
    sources: List[str] # Список алиасов (["Dragon", "SocialNetwork"])
    audio_path: str

class ProjectCreateRequest(BaseModel):
    name: str