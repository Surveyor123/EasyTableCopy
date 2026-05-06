# Build customizations
# Change this file instead of sconstruct or manifest files, whenever possible.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _

# Add-on information variables
addon_info = AddonInfo(
	# add-on Name/identifier, internal for NVDA
	addon_name="easyTableCopy",
	
	# Add-on summary/title, usually the user visible name of the add-on
	# Translators: Summary/title for this add-on
	addon_summary=_("Easy Table Copy"),
	
	# Add-on description
	# Translators: Long description to be shown for this add-on
	addon_description=_("""EasyTableCopy is an NVDA add-on designed to solve a common frustration: copying tables from the Web or lists from Windows into documents (like Word, Excel, or Outlook) without losing formatting or layout."""),
	
	# version
	addon_version="2026.6.5",
	
	# Brief changelog for this version
	# Translators: what's new content for the add-on version
	addon_changelog=_("""
- `copy_web_list_formatted()`: Copies web lists (`<ul>`, `<nav>`, `<select>`) as an HTML table with reliable object-tree traversal. Solves the issue where native Ctrl+C fails in Chrome for navigation lists.
- Secondary search for list objects in `script_tableMenu` using `focus` object, enabling detection of open `<select>` dropdowns where the caret-based `NVDAObjectAtStart` does not reach.
- **`perform_marked_copy_manual`**: Now uses `self.marked_rows` directly instead of re-collecting all rows and filtering by identity. Fixes missing rows on dynamic pages (e.g., Tureng) where object identity differs between marking and copying.
- **`copy_web_list_plain`**: Replaced recursive `collect()` with direct child iteration to avoid recursion limit errors on very large lists (1200+ items). Added IAccessible `accChild` fallback for display:none lists (IA2_STATE_OPAQUE).
- **`on_menu_select` (item_id == 1)**: For `LIST`-role objects, now calls `copy_web_list_formatted` instead of `perform_native_copy`. This ensures formatting and reliability for web navigation lists.
- **`script_tableMenu` (web context)**: Now also searches `focus` object for `LIST` role when caret-based search fails, improving dropdown list detection.
- Marked rows copy now correctly copies all user-selected rows on dynamically updated tables (object identity mismatch resolved).
- Potential recursion crash when copying extremely long web lists (e.g., 1233 items) – fixed by eliminating recursion in `copy_web_list_plain`.
- Web lists with `display:none` (e.g., hidden `<select>` options) now copy correctly via IAccessible fallback.
"""),
	
	# Author(s)
	addon_author="Çağrı Doğan <cagrid@hotmail.com>",
	
	# URL for the add-on documentation support
	addon_url="https://github.com/Surveyor123/EasyTableCopy",
	
	# URL for the add-on repository where the source code can be found
	addon_sourceURL="https://github.com/Surveyor123/EasyTableCopy",
	
	# Documentation file name
	addon_docFileName="readme.html",
	
	# Minimum NVDA version supported
	addon_minimumNVDAVersion="2022.1.0",
	
	# Last NVDA version supported/tested
	addon_lastTestedNVDAVersion="2026.1.0",
	
	# Add-on update channel (None denotes stable releases)
	addon_updateChannel=None,
	
	# Add-on license
	addon_license="GPL-2.0",
	addon_licenseURL=None,
)

# Define the python files that are the sources of your add-on.
# We point to the specific directory where your code lives.
pythonSources: list[str] = ["addon/globalPlugins/EasyTableCopy/*.py"]

# Files that contain strings for translation. Usually your python sources
i18nSources: list[str] = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
excludedFiles: list[str] = []

# Base language for the NVDA add-on
# Since your code strings (e.g. _("Table")) are in English, we keep this as "en".
baseLanguage: str = "en"

# Markdown extensions for add-on documentation
markdownExtensions: list[str] = []

# Custom braille translation tables
brailleTables: BrailleTables = {}

# Custom speech symbol dictionaries
symbolDictionaries: SymbolDictionaries = {}