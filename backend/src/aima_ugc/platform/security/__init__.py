"""Secret 文件与稳定引用边界。"""

from .secrets import (
    SecretFileError,
    read_secret_file,
    read_secret_ref,
    validate_secret_ref,
    write_secret_ref,
)

__all__ = [
    "SecretFileError",
    "read_secret_file",
    "read_secret_ref",
    "validate_secret_ref",
    "write_secret_ref",
]
