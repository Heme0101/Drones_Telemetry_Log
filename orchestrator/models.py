from pydantic import BaseModel, Field

class GlobalPosition(BaseModel):
    lat: int = Field(ge=-900_000_000, le=900_000_000)
    lon: int = Field(ge=-1_800_000_000, le=1_800_000_000)
    alt: int
    relative_alt: int