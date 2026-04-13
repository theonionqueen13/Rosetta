# src/rendering package
# Re-exports are intentionally deferred to avoid circular imports
# (calc_v2 → profiles_v2 → rendering.__init__ → drawing_v2 → patterns_v2 → calc_v2).
# Import directly from the submodules you need, e.g.:
#   from src.rendering.drawing_v2 import RenderResult
#   from src.rendering.profiles_v2 import format_object_profile_html

