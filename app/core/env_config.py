from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALGORITHM: str

    model_config = SettingsConfigDict(env_file=".env")


env = EnvSettings()  # type: ignore
