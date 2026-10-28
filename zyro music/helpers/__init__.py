# ==============================================================================
# HasiiMusic.helpers
# ==============================================================================
# Exports all the helper singletons (buttons, thumb, utils, etc) so plugins
# can grab them easily.
# ==============================================================================

from ._admins import admin_check, can_manage_vc, is_admin, reload_admins
from ._dataclass import Media, Track
from ._inline import Inline
from ._queue import Queue
from ._thumbnails import Thumbnail
from ._utilities import Utilities

buttons = Inline()
thumb = Thumbnail()
utils = Utilities()
