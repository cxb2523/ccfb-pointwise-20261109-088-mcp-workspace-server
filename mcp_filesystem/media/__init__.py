"""媒体探测与缩略图包。

对外入口仅两个函数：``MediaOperations.probe_file`` 与
``MediaOperations.make_thumbnail``。
"""

from .operations import MediaError, MediaOperations

__all__ = ["MediaOperations", "MediaError"]
