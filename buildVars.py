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
	addon_version="2026.5.4",
	
	# Brief changelog for this version
	# Translators: what's new content for the add-on version
	addon_changelog=_("""
* Fix COM object leak: `shell.application` COM objects in `copy_explorer_content`, `_copy_columns_direct`, and `script_tableStats` are now explicitly released via `del shell` in `finally` blocks.
* Fix duplicate node detection in tree traversal: `get_tree_hierarchy` was using `hash(item)` for visited-set deduplication, which is prone to collisions. Replaced with `id(item)` (memory address) for reliable identity checks within a session.
* Refactor magic numbers into named constants: Hardcoded values like `300`, `200`, and `15` extracted into `CLIPBOARD_INITIAL_WAIT_MS`, `CLIPBOARD_RETRY_WAIT_MS`, and `CLIPBOARD_MAX_RETRIES`.
* Fix `terminate` cleanup: Removed unnecessary `gc.collect()` call; now properly clears instance state on addon unload.
* Added hierarchical TreeView copy support (e.g., Input Gestures) with root-to-bottom scanning and indentation.
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