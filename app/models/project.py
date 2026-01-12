import uuid
import enum
from sqlalchemy import Column, String, Text, DateTime, Enum, JSON
from sqlalchemy.sql import func
from app.database import Base


class ProjectType(str, enum.Enum):
    """Project type classification."""
    RPC = "rpc"      # Backend RPC service
    WEB = "web"      # Frontend web application
    IDL = "idl"      # Interface Definition Language repository
    SDK = "sdk"      # SDK/library project
    OTHER = "other"  # Other project types


class Project(Base):
    """
    Project configuration model.

    Searchable fields are stored as columns.
    Non-searchable configuration is stored in the `config` JSON field.

    Config JSON structure:
    {
        "context": "Description/context for Claude",
        "idl": {
            "repo": "/path/to/idl/repo",
            "file": "api/service.thrift",
            "psm": "oec.reverse.strategy"
        },
        "test": {
            "dir": "./...",
            "tags": "-tags local"
        },
        "overpass_module": "code.byted.org/oec/rpcv2_oec_reverse_config"  # For RPC/Web/SDK after IDL change
    }
    """
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=False, index=True)  # Owner of the project config

    # Searchable fields
    name = Column(String(200), nullable=False)
    path = Column(String(500), nullable=False)  # Comma-separated repo paths
    project_type = Column(String(20), nullable=True, default="other")  # Project type: rpc, web, idl, sdk, other
    default_branch = Column(String(200), nullable=False)  # Required - branch for release/integration testing

    # Non-searchable configuration (JSON)
    config = Column(JSON, nullable=True)  # Flexible config: context, idl, test, overpass_module, etc.

    # Legacy fields (kept for backward compatibility, will migrate to config)
    default_context = Column(Text, nullable=True)
    idl_repo = Column(String(500), nullable=True)
    idl_file = Column(String(300), nullable=True)
    psm = Column(String(200), nullable=True)
    test_dir = Column(String(200), nullable=True)
    test_tags = Column(String(200), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def get_config(self, key: str, default=None):
        """Get a config value by key (supports nested keys with dot notation)."""
        if not self.config:
            return default
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set_config(self, key: str, value):
        """Set a config value by key (supports nested keys with dot notation)."""
        if self.config is None:
            self.config = {}
        keys = key.split('.')
        target = self.config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
