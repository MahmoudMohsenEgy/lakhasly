from pathlib import Path
from explainer.config import Config
from explainer.interfaces import CloudUploader
from explainer.uploaders.null_uploader import NullUploader
from explainer.uploaders.google_drive import GoogleDriveUploader


def build_uploader(config: Config) -> CloudUploader:
    secrets = config.google_oauth_client_secrets
    if secrets and Path(secrets).exists():
        token = config.gdrive_token_path or str(Path(config.output_dir) / ".gdrive_token.json")
        return GoogleDriveUploader(secrets, token, config.gdrive_folder_name)
    return NullUploader()
