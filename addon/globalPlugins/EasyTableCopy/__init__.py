# -*- coding: utf-8 -*-

import globalPluginHandler
import addonHandler
import api
import ui
import textInfos
import controlTypes
import wx
import winUser
from comtypes.client import CreateObject
import ctypes
import keyboardHandler
import re
import time
import winsound
import speech
from typing import List, Tuple, Optional, Set
from logHandler import log

# Start translation system
addonHandler.initTranslation()
user32 = ctypes.windll.user32

BLOCKED_APPS = ["excel", "calc", "soffice"]

CLIPBOARD_INITIAL_WAIT_MS = 300
CLIPBOARD_RETRY_WAIT_MS = 200
CLIPBOARD_MAX_RETRIES = 15
MAX_PARENT_SEARCH_DEPTH = 10

# copy_manual_safe() writes to the clipboard synchronously (we own the data,
# there's no need to wait for another app to finish writing first, as with
# the native Ctrl+C path above). Contention here is only ever a brief lock
# held by another process, so a handful of short, blocking retries is enough
# and avoids a noticeable freeze in speech.
CLIPBOARD_MANUAL_MAX_RETRIES = 5
CLIPBOARD_MANUAL_RETRY_WAIT_S = 0.03

def script_description(desc):
    def wrapper(func):
        func.__doc__ = desc
        return func
    return wrapper

def safe_str(val):
    if val is None: return ""
    return str(val)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("EasyTableCopy")

    TABLE_ROLES = set()
    ROW_ROLES = set()
    CELL_ROLES = set()
    CONTENT_ROLES = set()
    r = controlTypes.Role
    
    role_map = {
        "TABLE_ROLES": ["TABLE", "GRID", "LISTGRID", "LIST", "TREEVIEW"],
        "ROW_ROLES": ["TABLEROW", "ROW", "LISTITEM", "TREEVIEWITEM", "GROUPING"],
        "CELL_ROLES": ["TABLECELL", "TABLECOLUMNHEADER", "TABLEROWHEADER", "CELL", "GRIDCELL"],
        "CONTENT_ROLES": ["STATICTEXT", "EDITABLETEXT", "TABLECELL", "GRIDCELL", "TEXT", "PARAGRAPH", "LINK", "GROUPING"]
    }

    for target_set, names in role_map.items():
        s = locals()[target_set]
        for name in names:
            if hasattr(r, name): s.add(getattr(r, name))


    #: Marker attribute name used to detect/restore our wrapped browse mode
    #: navigation scripts (list item & table row quick nav).
    _NAV_PATCH_MARKER = "_easyTableCopy_origFunc"

    def __init__(self):
        super().__init__()
        self.marked_rows = []
        self.marked_col_indices = set()
        #: Container (list/table/tree) that the current row marks belong to.
        #: Used to detect when the user has moved to a different list, so
        #: stale marks from the previous list can be cleared automatically.
        self.marked_container = None
        #: Same idea, but for column marks.
        self.marked_col_container = None
        self._patch_navigation_announcements()

    def get_context_tree_interceptor(self):
        obj = api.getFocusObject()
        if hasattr(obj, "treeInterceptor") and obj.treeInterceptor:
            return obj.treeInterceptor
        return None

    # =========================================================================
    # FEATURE: ANNOUNCE "MARKED" WHEN LANDING ON A MARKED ROW/ITEM WHILE
    # NAVIGATING WITH WEB LIST ITEM (I / SHIFT+I) OR TABLE ROW
    # (CONTROL+ALT+DOWNARROW / UPARROW) QUICK NAV COMMANDS.
    #
    # These commands move NVDA's virtual caret without generating a real OS
    # focus event, so event_gainFocus can't be used to detect them. Instead
    # we wrap the actual NVDA core script methods that implement these
    # commands (real, stably-named Python methods on shared base classes),
    # run the original behaviour first, then check whether the caret landed
    # on a marked row/item and announce it if so.
    # =========================================================================
    def _wrap_nav_script(self, cls, method_name):
        """Wrap cls.method_name so our mark-announcement runs after NVDA's
        own behaviour. Safe to call multiple times (idempotent) and safe if
        the method doesn't exist (future NVDA versions may rename things)."""
        orig = getattr(cls, method_name, None)
        if orig is None or hasattr(orig, self._NAV_PATCH_MARKER):
            return
        plugin = self

        def wrapped(ti_self, gesture, _orig=orig):
            _orig(ti_self, gesture)
            try:
                plugin._announce_if_marked(ti_self)
            except Exception as e:
                log.debugWarning(f"EasyTableCopy._wrap_nav_script (announce): {e}")

        wrapped.__name__ = getattr(orig, "__name__", method_name)
        wrapped.__doc__ = getattr(orig, "__doc__", None)
        if hasattr(orig, "resumeSayAllMode"):
            wrapped.resumeSayAllMode = orig.resumeSayAllMode
        if hasattr(orig, "ignoreTreeInterceptorPassThrough"):
            wrapped.ignoreTreeInterceptorPassThrough = orig.ignoreTreeInterceptorPassThrough
        setattr(wrapped, self._NAV_PATCH_MARKER, orig)
        setattr(cls, method_name, wrapped)

    def _unwrap_nav_script(self, cls, method_name):
        current = getattr(cls, method_name, None)
        orig = getattr(current, self._NAV_PATCH_MARKER, None) if current is not None else None
        if orig is not None:
            setattr(cls, method_name, orig)

    def _patch_navigation_announcements(self):
        try:
            import browseMode
            self._wrap_nav_script(browseMode.BrowseModeTreeInterceptor, "script_nextListItem")
            self._wrap_nav_script(browseMode.BrowseModeTreeInterceptor, "script_previousListItem")
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._patch_navigation_announcements (listItem): {e}")
        try:
            import documentBase
            self._wrap_nav_script(documentBase.DocumentWithTableNavigation, "script_nextRow")
            self._wrap_nav_script(documentBase.DocumentWithTableNavigation, "script_previousRow")
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._patch_navigation_announcements (row): {e}")

    def _unpatch_navigation_announcements(self):
        try:
            import browseMode
            self._unwrap_nav_script(browseMode.BrowseModeTreeInterceptor, "script_nextListItem")
            self._unwrap_nav_script(browseMode.BrowseModeTreeInterceptor, "script_previousListItem")
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._unpatch_navigation_announcements (listItem): {e}")
        try:
            import documentBase
            self._unwrap_nav_script(documentBase.DocumentWithTableNavigation, "script_nextRow")
            self._unwrap_nav_script(documentBase.DocumentWithTableNavigation, "script_previousRow")
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._unpatch_navigation_announcements (row): {e}")

    def _speak_marked(self):
        """Announce "marked" ahead of whatever NVDA has just queued (the
        item/row name), rather than after it, by using NOW priority: this
        interrupts the in-progress utterance, speaks immediately, then lets
        the interrupted utterance continue."""
        try:
            from speech.priorities import Spri
            speech.speakMessage(_("marked"), priority=Spri.NOW)
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._speak_marked (priority): {e}")
            ui.message(_("marked"))

    def _announce_if_marked(self, ti):
        """After a list-item or table-row quick nav command has run, check
        whether the browse mode caret landed on a marked row/item and, if
        so, announce it."""
        if not self.marked_rows:
            return
        try:
            obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._announce_if_marked: {e}")
            return
        row = self.find_object_by_role(obj, self.ROW_ROLES)
        if row and row in self.marked_rows:
            # Translators: reported after moving to a row/item that was
            # previously marked with the mark-row command.
            self._speak_marked()

    def is_web_context(self):
        """Check if current context is web (has tree interceptor)"""
        return self.get_context_tree_interceptor() is not None

    def is_explorer_context(self):
        """Check if current context is Windows Explorer"""
        focus = api.getFocusObject()
        return (focus.appModule and focus.appModule.appName.lower() == "explorer")

    def is_syslistview32_obj(self, obj):
        """Check whether the given NVDA object lives inside a SysListView32 window.
        These lists are copied via direct Win32 memory reads (copy_syslistview32),
        which bypasses the object-tree mark system entirely, so marking here would
        silently do nothing useful yet."""
        try:
            return bool(obj and obj.windowClassName and obj.windowClassName.lower() == "syslistview32")
        except Exception:
            return False

    def event_gainFocus(self, obj, nextHandler):
        """Desktop lists (generic UIA/MSAA lists, not web/Explorer/SysListView32)
        move focus with a real OS focus event on every up/down arrow press, so
        unlike the web/table quick-nav commands, this can be detected here
        directly instead of via wrapped scripts."""
        nextHandler()
        if not self.marked_rows:
            return
        try:
            if self.is_web_context() or self.is_explorer_context():
                return
            if self.is_syslistview32_obj(obj):
                return
            row = self.find_object_by_role(obj, self.ROW_ROLES)
            if row and row in self.marked_rows:
                self._speak_marked()
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.event_gainFocus: {e}")

    def is_desktop_list_context(self):
        """Check if current context is a desktop list (not web, not explorer)"""
        if self.is_web_context() or self.is_explorer_context():
            return False
        focus = api.getFocusObject()
        return focus.role in self.TABLE_ROLES or self.find_object_by_role(focus, self.TABLE_ROLES) is not None

    def find_object_by_role(self, start_obj, target_roles):
        obj = start_obj
        for _loop in range(MAX_PARENT_SEARCH_DEPTH):
            if not obj: break
            if obj.role in target_roles: return obj
            obj = obj.parent
        return None

    def get_column_index(self, cell_obj):
        parent = cell_obj.parent
        if parent:
            try:
                siblings = [c for c in parent.children if c.role in self.CELL_ROLES]
                if cell_obj in siblings: return siblings.index(cell_obj)
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.get_column_index (siblings): {e}")
        try:
            if hasattr(cell_obj, "columnNumber"):
                val = cell_obj.columnNumber
                if val > 0: return val - 1
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.get_column_index (columnNumber): {e}")
        return -1

    def _restore_focus(self, hwnd):
        try:
            if hwnd:
                if winUser.getForegroundWindow() != hwnd:
                    winUser.setForegroundWindow(hwnd)
                winUser.setFocus(hwnd)
                time.sleep(0.05) 
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._restore_focus: {e}")

    # =========================================================================
    # SIMPLE TEXT EXTRACTION - NO FORMATTING ATTEMPTS
    # =========================================================================
    def get_cell_text(self, obj, depth=0) -> Tuple[str, str]:
        """
        EXTREMELY FAST - Only extracts text, no formatting
        Returns (html_text, plain_text)
        """
        if depth > 10:
            return "", ""
        
        if obj is None:
            return "", ""

        # Always try to get text from leaf nodes regardless of role
        if obj.childCount == 0:
            raw = (obj.name or obj.value or "").strip()
            if raw:
                html = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                return html, raw
            return "", ""

        # For nodes with children: recurse into all children (not just CONTENT_ROLES)
        # This ensures BUTTON, MENUITEM, etc. are not skipped.
        text_parts = []
        for child in obj.children:
            h, t = self.get_cell_text(child, depth + 1)
            if t:
                text_parts.append(t)

        if text_parts:
            plain_text = " ".join(text_parts)
            html_text = plain_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return html_text, plain_text

        # Fallback: use obj.name/value if no children yielded text
        raw = (obj.name or obj.value or "").strip()
        if raw:
            html = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return html, raw
        return "", ""

    def copy_manual_safe(self, html, text):
        """Fast clipboard handling, with a few short retries if another
        process is briefly holding the clipboard lock (same reasoning as
        _retry_clipboard_repair, but blocking since we write the data
        ourselves rather than waiting on an external app)."""
        opened = False
        for attempt in range(CLIPBOARD_MANUAL_MAX_RETRIES):
            if wx.TheClipboard.Open():
                opened = True
                break
            if attempt < CLIPBOARD_MANUAL_MAX_RETRIES - 1:
                time.sleep(CLIPBOARD_MANUAL_RETRY_WAIT_S)
        if not opened:
            log.debugWarning(f"EasyTableCopy.copy_manual_safe: Clipboard could not be opened after {CLIPBOARD_MANUAL_MAX_RETRIES} attempts.")
            return False
        try:
            d = wx.DataObjectComposite()
            h = wx.HTMLDataObject()
            
            full = f"<html><body>{html}</body></html>"
            h.SetHTML(full)
            d.Add(h, True)
            
            t = wx.TextDataObject()
            t.SetText(text)
            d.Add(t, False)
            
            result = wx.TheClipboard.SetData(d)
            wx.TheClipboard.Close()
            return result
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.copy_manual_safe: {e}")
            wx.TheClipboard.Close()
            return False

    # =========================================================================
    # FAST Table Processing - NO FORMATTING
    # =========================================================================
    def collect_rows_fast(self, table_obj) -> List:
        """Ultra-fast row collection"""
        rows = []
        
        def collect(obj):
            if obj.role in self.ROW_ROLES:
                rows.append(obj)
                return
            if obj.childCount > 0:
                for child in obj.children:
                    collect(child)
        
        collect(table_obj)
        return rows

    def get_table_structure(self, table_obj, sample_size=50) -> Tuple[int, int]:
        """
        Get accurate row and column counts from any table.
        Uses sampling for large tables to avoid performance issues.
        Returns (row_count, column_count)
        """
        all_rows = self.collect_rows_fast(table_obj)
        total_rows = len(all_rows)
        
        if total_rows == 0:
            return 0, 0
        
        sample_rows = all_rows[:min(sample_size, total_rows)]
        max_cols = 0
        
        for row in sample_rows:
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if cells:
                max_cols = max(max_cols, len(cells))
        
        return total_rows, max_cols

    def process_table_fast(self, rows, selected_indices=None, text_separator="\t") -> Tuple[str, str]:
        """Build (html, plain_text) for the given rows.
        text_separator is placed between columns in the plain-text output
        (tab by default; " | " is used by Copy Table (Reconstructed))."""
        grid = {}
        max_col = 0
        total_rows = len(rows)

        for r_idx, row in enumerate(rows):
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if not cells:
                cells = list(row.children)
            
            c_idx = 0
            for cell in cells:
                while (r_idx, c_idx) in grid:
                    c_idx += 1
                
                h, t = self.get_cell_text(cell)
                if not h: h = "&nbsp;"
                if not t: t = " "

                try:
                    rs = int(getattr(cell, "rowSpan", 1))
                    cs = int(getattr(cell, "colSpan", 1))
                except Exception as e:
                    log.debugWarning(f"EasyTableCopy.process_table_fast (span): {e}")
                    rs, cs = 1, 1

                for r_offset in range(rs):
                    for c_offset in range(cs):
                        target_r = r_idx + r_offset
                        target_c = c_idx + c_offset
                        if r_offset == 0 and c_offset == 0:
                            grid[(target_r, target_c)] = (h, t, rs, cs)
                        else:
                            grid[(target_r, target_c)] = ("OCCUPIED", "OCCUPIED", 1, 1)
                
                c_idx += cs
                if c_idx > max_col: max_col = c_idx

        html_parts = ["<table border='1' cellpadding='2' cellspacing='0'>"]
        text_parts = []
        
        target_cols = selected_indices if selected_indices else range(max_col)

        for r_idx in range(total_rows):
            row_html = "<tr>"
            row_text = []
            
            for c_idx in target_cols:
                if (r_idx, c_idx) in grid:
                    h, t, rs, cs = grid[(r_idx, c_idx)]
                    
                    if h == "OCCUPIED":
                        continue
                    
                    rs_attr = f" rowspan='{rs}'" if rs > 1 else ""
                    cs_attr = f" colspan='{cs}'" if cs > 1 else ""
                    row_html += f"<td{rs_attr}{cs_attr}>{h}</td>"
                    row_text.append(t)
                else:
                    row_html += "<td>&nbsp;</td>"
                    row_text.append(" ")
            
            row_html += "</tr>"
            html_parts.append(row_html)
            text_parts.append(text_separator.join(row_text))

        html_parts.append("</table>")
        return "".join(html_parts), "\n".join(text_parts)

    # =========================================================================
    # ENGINE A: NATIVE COPY
    # =========================================================================
    def perform_native_copy(self, obj, label, original_hwnd):
        try:
            self._restore_focus(original_hwnd)
            
            count_info = ""
            first_cell_empty = False
            msg_override = None

            if obj.role in self.TABLE_ROLES:
                rows = self.collect_rows_fast(obj)
                count = len(rows)
                if obj.role == controlTypes.Role.LIST:
                    if count == 1:
                        msg_override = _("List copied (1 item).")
                    elif count > 1:
                        msg_override = _("List copied ({count} items).").format(count=count)
                    else:
                        msg_override = _("List copied.")
                else:
                    if count == 1: 
                        count_info = _(" (1 row)")
                    elif count > 1: 
                        count_info = _(" ({count} rows)").format(count=count)

                if rows:
                    first_row = rows[0]
                    first_row_cells = [c for c in first_row.children if c.role in self.CELL_ROLES]
                    if first_row_cells:
                        first_cell = first_row_cells[0]
                        try:
                            cell_text = first_cell.getText() or ""
                        except Exception as e:
                            log.debugWarning(f"EasyTableCopy.perform_native_copy (getText): {e}")
                            cell_text = ""
                        if not first_cell.name and not cell_text.strip():
                            first_cell_empty = True

            elif obj.role in self.ROW_ROLES:
                cells = [c for c in obj.children if c.role in self.CELL_ROLES]
                count = len(cells)
                if count == 1: 
                    count_info = _(" (1 cell)")
                elif count > 1: 
                    count_info = _(" ({count} cells)").format(count=count)

            info = obj.makeTextInfo(textInfos.POSITION_ALL)
            info.updateSelection()
            
            winsound.Beep(440, 100) 
            keyboardHandler.KeyboardInputGesture.fromName("control+c").send()
            
            wx.CallLater(CLIPBOARD_INITIAL_WAIT_MS, self._retry_clipboard_repair, label, count_info, 1, first_cell_empty, msg_override)
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.perform_native_copy: {e}")
            ui.message(_("Selection failed."))


    def _retry_clipboard_repair(self, label, count_info, attempt, first_cell_empty=False, msg_override=None):
        if not wx.TheClipboard.Open():
            if attempt < CLIPBOARD_MAX_RETRIES:
                wx.CallLater(CLIPBOARD_RETRY_WAIT_MS, self._retry_clipboard_repair, label, count_info, attempt + 1, first_cell_empty, msg_override)
                return
            else:
                log.debugWarning(f"EasyTableCopy._retry_clipboard_repair: Clipboard could not be opened after {CLIPBOARD_MAX_RETRIES} attempts.")
                ui.message(msg_override if msg_override else _("{label} copied{count}.").format(label=label, count=count_info))
                return

        try:
            if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_HTML)):
                data_obj = wx.HTMLDataObject()
                if wx.TheClipboard.GetData(data_obj):
                    raw_html = data_obj.GetHTML()
                    modified = False
                    
                    if first_cell_empty:
                        row_pattern = re.compile(r'(<tr[^>]*>)(.*?)(</tr>)', re.IGNORECASE | re.DOTALL)
                        row_match = row_pattern.search(raw_html)
                        
                        if row_match:
                            tr_start, row_content, tr_end = row_match.groups()
                            insertion = "<td>&nbsp;</td>"
                            repaired_row = f"{tr_start}{insertion}{row_content}{tr_end}"
                            raw_html = raw_html.replace(row_match.group(0), repaired_row, 1)
                            modified = True

                    if "border=" not in raw_html.lower() and "border:" not in raw_html.lower():
                        if "<table" in raw_html.lower():
                            raw_html = re.sub(r'(<table\b[^>]*)(>)', r'\1 border="1" cellspacing="0" cellpadding="5"\2', raw_html, count=1, flags=re.IGNORECASE)
                            modified = True

                    if modified:
                        new_data = wx.DataObjectComposite()
                        new_html_obj = wx.HTMLDataObject()
                        new_html_obj.SetHTML(raw_html)
                        new_data.Add(new_html_obj, True)
                        
                        text_obj = wx.TextDataObject()
                        if wx.TheClipboard.GetData(text_obj):
                            new_data.Add(text_obj, False)
                        
                        wx.TheClipboard.SetData(new_data)
                    
                    winsound.Beep(880, 100)
                    ui.message(msg_override if msg_override else _("{label} copied{count}.").format(label=label, count=count_info))
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._retry_clipboard_repair: {e}")
            ui.message(_("Error."))
        finally:
            wx.TheClipboard.Close()

    # =========================================================================
    # ENGINE B: FAST PLAIN TEXT COPY - NO FORMATTING
    # =========================================================================
    def perform_full_table_manual(self, current_obj, original_hwnd, text_separator="\t"):
        """ULTRA FAST - No formatting, just plain text.
        text_separator: placed between columns in the plain-text version
        (tab by default, " | " for the vertical-bar variant)."""
        table = self.find_object_by_role(current_obj, self.TABLE_ROLES)
        if not table:
            ui.message(_("Table not found."))
            return

        winsound.Beep(440, 100)
        
        rows = self.collect_rows_fast(table)
        
        if not rows:
            ui.message(_("Table is empty."))
            return

        html_out, text_out = self.process_table_fast(rows, text_separator=text_separator)
        
        if self.copy_manual_safe(html_out, text_out):
            self._restore_focus(original_hwnd)
            winsound.Beep(880, 100)
            
            count = len(rows)
            if count == 1:
                msg = _("Table copied (1 row).")
            else:
                msg = _("Table copied ({count} rows).").format(count=count)
            ui.message(msg)
        else:
            ui.message(_("Copy failed."))

    def perform_marked_copy_manual(self, original_hwnd):
        """ULTRA FAST for marked selections"""
        target_rows = []
        target_col_indices = self.marked_col_indices
        
        if self.marked_rows:
            # Use marked_rows directly as the authoritative list of rows to copy.
            # Previously this code re-collected all rows from the table and filtered
            # by identity (r in self.marked_rows), which caused mismatches on dynamic
            # pages (e.g. Tureng) where re-collection may return different object
            # instances or a different ordering, resulting in fewer rows than expected.
            target_rows = self.marked_rows
        
        elif self.marked_col_indices:
            ti = self.get_context_tree_interceptor()
            try:
                obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
                table = self.find_object_by_role(obj, self.TABLE_ROLES)
                target_rows = self.collect_rows_fast(table)
                target_col_indices = sorted(list(self.marked_col_indices))
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.perform_marked_copy_manual (cols): {e}")
                return

        if not target_rows:
            self._restore_focus(original_hwnd)
            ui.message(_("Error: No items to copy."))
            return

        winsound.Beep(440, 100)
        
        html_out, text_out = self.process_table_fast(target_rows, target_col_indices)
        
        if self.copy_manual_safe(html_out, text_out):
            self._restore_focus(original_hwnd)
            winsound.Beep(880, 100)
            
            msg = ""
            if self.marked_rows:
                c = len(target_rows)
                if c == 1: 
                    msg = _("Copied 1 row.")
                else: 
                    msg = _("Copied {count} rows.").format(count=c)
            else:
                c = len(target_col_indices)
                if c == 1: 
                    msg = _("Copied 1 column.")
                else: 
                    msg = _("Copied {count} columns.").format(count=c)
            ui.message(msg)
            self.marked_rows = []
            self.marked_col_indices.clear()
        else:
            self._restore_focus(original_hwnd)
            ui.message(_("Copy failed."))

    # =========================================================================
    # ENGINE C: DESKTOP LISTS
    # =========================================================================
    def copy_explorer_content(self, hwnd):
        shell = None
        try:
            shell = CreateObject("shell.application")
            folder_view = None
            for window in shell.Windows():
                try: 
                    if window.hwnd == hwnd or user32.IsChild(window.hwnd, hwnd):
                        folder_view = window.Document
                        break
                except Exception as e:
                    log.debugWarning(f"EasyTableCopy.copy_explorer_content (window iter): {e}")
                    continue
            
            if not folder_view:
                return False
            
            items = folder_view.Folder.Items()
            count = items.Count
            
            if count == 0:
                ui.message(_("Folder is empty."))
                return True
            
            winsound.Beep(440, 100)
            
            headers = [folder_view.Folder.GetDetailsOf(None, i) for i in range(15) if folder_view.Folder.GetDetailsOf(None, i)]
            text_rows = []
            html_rows = ["<table border='1'><tr>" + "".join([f"<th>{h}</th>" for h in headers]) + "</tr>"]
            text_rows.append("\t".join(headers))
            
            for i in range(count):
                item = items.Item(i)
                vals = [str(folder_view.Folder.GetDetailsOf(item, idx)).strip() for idx in range(len(headers))]
                html_rows.append("<tr>" + "".join([f"<td>{v if v else '&nbsp;'}</td>" for v in vals]) + "</tr>")
                text_rows.append("\t".join(vals))
            
            html_rows.append("</table>")
            
            self.copy_manual_safe("".join(html_rows), "\n".join(text_rows))
            winsound.Beep(880, 100)
            
            if count == 1: 
                ui.message(_("Folder copied (1 item)."))
            else: 
                ui.message(_("Folder copied ({count} items).").format(count=count))
            return True
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.copy_explorer_content: {e}")
            return False
        finally:
            if shell is not None:
                try:
                    del shell
                except Exception:
                    pass

    # =========================================================================
    # FEATURE: HIERARCHICAL TREE COPY (FULL STRUCTURE)
    # =========================================================================
    def get_tree_hierarchy(self, item, level=0, visited=None) -> List[str]:
        """Recursively scans tree items using a hybrid approach to find all nodes."""
        if visited is None:
            visited = set()
        
        try:
            item_id = id(item)
            if item_id in visited:
                return []
            visited.add(item_id)
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.get_tree_hierarchy (visited): {e}")

        lines = []
        indent = "    " * level
        name = (item.name or "").strip()
        
        states = item.states
        status = ""
        if controlTypes.State.COLLAPSED in states:
            status = " [+]"
        elif controlTypes.State.EXPANDED in states:
            status = " [-]"

        if name:
            lines.append(f"{indent}{name}{status}")

        children_to_process = []
        try:
            if item.childCount > 0:
                children_to_process.extend([c for c in item.children if c.role in [controlTypes.Role.TREEVIEWITEM, controlTypes.Role.GROUPING]])
            
            existing_ids = {id(x) for x in children_to_process}
            child = item.firstChild
            while child:
                if child.role in [controlTypes.Role.TREEVIEWITEM, controlTypes.Role.GROUPING]:
                    if id(child) not in existing_ids:
                        children_to_process.append(child)
                        existing_ids.add(id(child))
                child = child.next
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.get_tree_hierarchy (children): {e}")

        for child in children_to_process:
            lines.extend(self.get_tree_hierarchy(child, level + 1, visited))
        
        return lines

    def perform_tree_copy(self, focus_obj):
        """Climbs to the absolute top of the tree and copies everything visible to NVDA."""
        winsound.Beep(440, 100)
        
        root_container = focus_obj
        curr = focus_obj
        while curr:
            if curr.role == controlTypes.Role.TREEVIEW:
                root_container = curr
            parent = curr.parent
            if not parent or parent == curr or parent.role == controlTypes.Role.WINDOW:
                break
            curr = parent
        
        all_lines = []
        global_visited = set()
        
        start_node = None
        try:
            start_node = root_container.firstChild
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.perform_tree_copy (firstChild): {e}")

        if start_node:
            curr_item = start_node
            while curr_item:
                if curr_item.role in [controlTypes.Role.TREEVIEWITEM, controlTypes.Role.GROUPING]:
                    all_lines.extend(self.get_tree_hierarchy(curr_item, 0, global_visited))
                curr_item = curr_item.next
        else:
            all_lines = self.get_tree_hierarchy(root_container, 0, global_visited)

        if not all_lines:
            ui.message(_("No tree items found. Try expanding the branches you wish to copy."))
            return

        text_out = "\n".join(all_lines)
        if self.copy_manual_safe(f"<html><body><pre>{text_out}</pre></body></html>", text_out):
            winsound.Beep(880, 100)
            ui.message(_("Full tree structure copied ({count} items).").format(count=len(all_lines)))

    def perform_list_view_copy_fallback(self, list_obj):
        """Fast list copying"""
        try:
            items = [c for c in list_obj.children if c.role in self.ROW_ROLES]
            count = len(items)
            
            if count == 0:
                ui.message(_("No items found."))
                return
            
            winsound.Beep(440, 100)
            
            text_rows = []
            html_rows = ["<table border='1'>"]
            
            extracted_any = False

            for item in items:
                cols = [c for c in item.children if c.role in self.CONTENT_ROLES] or [item]
                r_html = "<tr>"
                r_txt = []
                
                for col in cols:
                    h, t = self.get_cell_text(col)
                    if t: 
                        extracted_any = True
                    if not h: 
                        h = "&nbsp;"
                    r_html += f"<td>{h}</td>"
                    r_txt.append(t)
                
                r_html += "</tr>"
                html_rows.append(r_html)
                text_rows.append("\t".join(r_txt))
            
            html_rows.append("</table>")
            
            if not extracted_any:
                ui.message(_("No accessible text found."))
                return

            if self.copy_manual_safe("".join(html_rows), "\n".join(text_rows)):
                winsound.Beep(880, 100)
                if count == 1: 
                    ui.message(_("List copied (1 item)."))
                else: 
                    ui.message(_("List copied ({count} items).").format(count=count))
            else:
                ui.message(_("Clipboard error. Try again."))
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.perform_list_view_copy_fallback: {e}")
            ui.message(_("Error processing list."))

    # =========================================================================
    # FEATURE: GET CURRENT TABLE
    # =========================================================================
    def _get_current_table(self):
        """Get current table from any context"""
        focus = api.getFocusObject()
        ti = self.get_context_tree_interceptor()
        
        table = None
        if ti:
            try:
                obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
                table = self.find_object_by_role(obj, self.TABLE_ROLES)
            except Exception as e:
                log.debugWarning(f"EasyTableCopy._get_current_table (web): {e}")
        
        if not table:
            if focus.role in self.TABLE_ROLES:
                table = focus
            else:
                temp = focus
                for _loop in range(5):
                    if not temp: break
                    if temp.role in self.TABLE_ROLES:
                        table = temp
                        break
                    temp = temp.parent
        
        return table

    # =========================================================================
    # FEATURE: COLUMN COPYING (DESKTOP & EXPLORER ONLY)
    # =========================================================================
    @script_description(_("Copies first column from current table (desktop only)."))
    def script_copyColumn1(self, gesture):
        if self.is_web_context():
            return
        self._copy_columns_direct([0], _("Column 1"))

    @script_description(_("Copies second column from current table (desktop only)."))
    def script_copyColumn2(self, gesture):
        if self.is_web_context():
            return
        self._copy_columns_direct([1], _("Column 2"))

    @script_description(_("Copies third column from current table (desktop only)."))
    def script_copyColumn3(self, gesture):
        if self.is_web_context():
            return
        self._copy_columns_direct([2], _("Column 3"))

    @script_description(_("Copies first and second columns from current table (desktop only)."))
    def script_copyColumns1and2(self, gesture):
        if self.is_web_context():
            return
        self._copy_columns_direct([0, 1], _("Columns 1-2"))

    @script_description(_("Copies first and third columns from current table (desktop only)."))
    def script_copyColumns1and3(self, gesture):
        if self.is_web_context():
            return
        self._copy_columns_direct([0, 2], _("Columns 1-3"))

    @script_description(_("Copies first three columns from current table (desktop only)."))
    def script_copyColumns1to3(self, gesture):
        if self.is_web_context():
            return
        self._copy_columns_direct([0, 1, 2], _("Columns 1-3"))

    def _copy_columns_direct(self, column_indices, label):
        """Direct column copying for non-web contexts with proper HTML table structure"""
        table = self._get_current_table()
        if not table:
            ui.message(_("Not on a table."))
            return

        # --- Intercept SysListView32 here ---
        is_syslist = False
        try:
            if table.windowClassName and table.windowClassName.lower() == "syslistview32":
                is_syslist = True
        except Exception:
            pass
        
        if is_syslist and table.windowHandle:
            # If SysListView32 API extraction succeeds, exit the function.
            if self.copy_syslistview32(table.windowHandle, column_indices=column_indices, label=label):
                return
        # ------------------------------------
        
        # --- PART 1: Windows Explorer Handling ---
        if self.is_explorer_context():
            focus = api.getFocusObject()
            shell = None
            try:
                shell = CreateObject("shell.application")
                folder_view = None
                for window in shell.Windows():
                    try: 
                        if window.hwnd == focus.windowHandle or user32.IsChild(window.hwnd, focus.windowHandle):
                            folder_view = window.Document
                            break
                    except Exception as e:
                        log.debugWarning(f"EasyTableCopy._copy_columns_direct (window iter): {e}")
                        continue
                
                if folder_view:
                    items = folder_view.Folder.Items()
                    count = items.Count
                    if count == 0:
                        ui.message(_("Folder is empty."))
                        return
                    
                    winsound.Beep(440, 100)
                    
                    headers = []
                    html_header_parts = []
                    for i in column_indices:
                        header = folder_view.Folder.GetDetailsOf(None, i)
                        if header:
                            headers.append(header)
                            html_header_parts.append(f"<th>{header}</th>")
                    
                    text_rows = ["\t".join(headers)] if headers else []
                    html_rows = ["<table border='1' cellpadding='5' cellspacing='0'>"]
                    if html_header_parts:
                        html_rows.append("<tr>" + "".join(html_header_parts) + "</tr>")
                    
                    for i in range(count):
                        item = items.Item(i)
                        row_vals = []
                        row_html_cells = []
                        for idx in column_indices:
                            val = str(folder_view.Folder.GetDetailsOf(item, idx)).strip()
                            row_vals.append(val if val else " ")
                            row_html_cells.append(f"<td>{val if val else '&nbsp;'}</td>")
                        
                        text_rows.append("\t".join(row_vals))
                        html_rows.append("<tr>" + "".join(row_html_cells) + "</tr>")
                    
                    html_rows.append("</table>")
                    text_out = "\n".join(text_rows)
                    html_out = "".join(html_rows)
                    
                    if self.copy_manual_safe(html_out, text_out):
                        winsound.Beep(880, 100)
                        ui.message(_("{label} ({count} items) copied.").format(label=label, count=count))
                    return
            except Exception as e:
                log.debugWarning(f"EasyTableCopy._copy_columns_direct (explorer): {e}")
            finally:
                if shell is not None:
                    try:
                        del shell
                    except Exception:
                        pass
        
        # --- PART 2: Generic Desktop List Handling ---
        rows = self.collect_rows_fast(table)
        if not rows:
            ui.message(_("Table is empty."))
            return
        
        winsound.Beep(440, 100)
        
        text_parts = []
        html_parts = ["<table border='1' cellpadding='5' cellspacing='0'>"]
        
        for row in rows:
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if not cells:
                cells = list(row.children)
            
            row_text_vals = []
            row_html_cells = []
            has_content = False
            
            for idx in column_indices:
                if 0 <= idx < len(cells):
                    h, t = self.get_cell_text(cells[idx])
                    row_text_vals.append(t if t else " ")
                    row_html_cells.append(f"<td>{h if h else '&nbsp;'}</td>")
                    if t.strip(): has_content = True
                else:
                    row_text_vals.append(" ")
                    row_html_cells.append("<td>&nbsp;</td>")
            
            if has_content:
                text_parts.append("\t".join(row_text_vals))
                html_parts.append("<tr>" + "".join(row_html_cells) + "</tr>")
        
        html_parts.append("</table>")
        
        if not text_parts:
            ui.message(_("No data found."))
            return
        
        text_out = "\n".join(text_parts)
        html_out = "".join(html_parts)
        
        if self.copy_manual_safe(html_out, text_out):
            winsound.Beep(880, 100)
            ui.message(_("{label} ({count} rows) copied.").format(label=label, count=len(text_parts)))

    # =========================================================================
    # FEATURE: TABLE STATISTICS (WORKS EVERYWHERE)
    # =========================================================================
    @script_description(_("Announces table dimensions."))
    def script_tableStats(self, gesture):
        """Announce number of rows and columns in current table"""
        table = self._get_current_table()
        
        if not table:
            ui.message(_("Not on a table."))
            return
        
        if self.is_explorer_context():
            focus = api.getFocusObject()
            shell = None
            try:
                shell = CreateObject("shell.application")
                folder_view = None
                for window in shell.Windows():
                    try: 
                        if window.hwnd == focus.windowHandle or user32.IsChild(window.hwnd, focus.windowHandle):
                            folder_view = window.Document
                            break
                    except Exception as e:
                        log.debugWarning(f"EasyTableCopy.script_tableStats (window iter): {e}")
                        continue
                
                if folder_view:
                    items = folder_view.Folder.Items()
                    count = items.Count
                    
                    if count == 0:
                        ui.message(_("Folder is empty."))
                        return
                    
                    col_count = 0
                    for i in range(20):
                        if folder_view.Folder.GetDetailsOf(None, i):
                            col_count += 1
                    
                    winsound.Beep(880, 100)
                    if col_count == 0:
                        ui.message(_("Folder has {count} items.").format(count=count))
                    else:
                        ui.message(_("Folder has {count} items and {col_count} columns.").format(count=count, col_count=col_count))
                    return
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.script_tableStats (explorer): {e}")
            finally:
                if shell is not None:
                    try:
                        del shell
                    except Exception:
                        pass
        
        rows, cols = self.get_table_structure(table)
        
        if rows == 0:
            ui.message(_("Table is empty."))
            return
        
        winsound.Beep(880, 100)
        if cols == 0:
            ui.message(_("Table has {rows} rows.").format(rows=rows))
        else:
            ui.message(_("Table has {rows} rows and {cols} columns.").format(rows=rows, cols=cols))

    # =========================================================================
    # FEATURE: COPY CURRENT CELL (WORKS EVERYWHERE)
    # =========================================================================
    @script_description(_("Copies current cell content quickly."))
    def script_copyCurrentCell(self, gesture):
        """Copy only the current cell content"""
        focus = api.getFocusObject()
        ti = self.get_context_tree_interceptor()
        
        cell = None
        if ti:
            try:
                obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
                cell = self.find_object_by_role(obj, self.CELL_ROLES)
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.script_copyCurrentCell (web): {e}")
        else:
            cell = self.find_object_by_role(focus, self.CELL_ROLES)
        
        if not cell:
            ui.message(_("Not in a cell."))
            return
        
        winsound.Beep(440, 100)
        
        h, t = self.get_cell_text(cell)
        if not t:
            ui.message(_("Cell is empty."))
            return
        
        if self.copy_manual_safe(f"<html><body>{h}</body></html>", t):
            winsound.Beep(880, 100)
            ui.message(_("Cell copied."))

    # =========================================================================
    # FEATURE: COPY MARKED ROWS AS TEXT (WEB ONLY)
    # =========================================================================
    @script_description(_("Copies marked rows as plain text without table structure (web only)."))
    def script_copyMarkedAsText(self, gesture):
        """Copy marked rows as plain text lines - WEB ONLY"""
        if not self.is_web_context():
            return
        
        if not self.marked_rows:
            ui.message(_("No rows marked."))
            return
        
        winsound.Beep(440, 100)
        
        text_lines = []
        for row in self.marked_rows:
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if not cells:
                cells = list(row.children)
            
            row_texts = []
            for cell in cells:
                h, t = self.get_cell_text(cell)
                if t:
                    row_texts.append(t)
            
            if row_texts:
                text_lines.append(" ".join(row_texts))
        
        if not text_lines:
            ui.message(_("No text found."))
            return
        
        text_out = "\n".join(text_lines)
        html_out = "<html><body>" + "<br>".join(text_lines) + "</body></html>"
        
        if self.copy_manual_safe(html_out, text_out):
            winsound.Beep(880, 100)
            count = len(text_lines)
            
            self.marked_rows = []
            
            if count == 1:
                ui.message(_("Marked row copied as text."))
            else:
                ui.message(_("Marked rows copied as text ({count} rows).").format(count=count))

    # =========================================================================
    # MENU & INPUT HANDLERS
    # =========================================================================
    def on_menu_select(self, item_id, current_obj, original_hwnd):
        if item_id == 1:
            target = self.find_object_by_role(current_obj, self.TABLE_ROLES)
            if target:
                if target.role == controlTypes.Role.LIST:
                    # Web navigation lists: native Ctrl+C is unreliable because
                    # Chrome does not reliably translate the NVDA virtual-buffer
                    # selection into a clipboard write for <ul>/<nav> structures.
                    # Use the manual object-tree approach with HTML table output.
                    self.copy_web_list_formatted(target, original_hwnd)
                else:
                    self.perform_native_copy(target, _("Table"), original_hwnd)
            else: 
                ui.message(_("Target not found."))
        elif item_id == 2:
            target = self.find_object_by_role(current_obj, self.ROW_ROLES)
            if target: 
                self.perform_native_copy(target, _("Row"), original_hwnd)
            else: 
                ui.message(_("Target not found."))
        elif item_id == 3:
            self.perform_full_table_manual(current_obj, original_hwnd)
        elif item_id == 10:
            self.perform_full_table_manual(current_obj, original_hwnd, text_separator=" | ")
        elif item_id == 4:
            target = self.find_object_by_role(current_obj, self.CELL_ROLES)
            if target:
                idx = self.get_column_index(target)
                if idx != -1:
                    self.marked_col_indices.add(idx)
                    self.perform_marked_copy_manual(original_hwnd)
                    self.marked_col_indices.discard(idx)
        elif item_id == 5:
            self.perform_marked_copy_manual(original_hwnd)
        elif item_id == 6:
            if not self.marked_rows and not self.marked_col_indices:
                ui.message(_("No selection to clear."))
            else:
                self.marked_rows = []
                self.marked_col_indices.clear()
                ui.message(_("Selections cleared."))
        elif item_id == 7:
            self.copy_web_list_plain(current_obj)
        elif item_id == 8:
            self.copy_marked_list_items()
        elif item_id == 9:
            if not self.marked_rows:
                ui.message(_("No selection to clear."))
            else:
                self.marked_rows = []
                ui.message(_("Selections cleared."))

    # Real table roles for web — LIST intentionally excluded
    _WEB_TABLE_ROLE_NAMES = ["TABLE", "GRID", "LISTGRID"]
    WEB_TABLE_ROLES = {getattr(controlTypes.Role, n) for n in _WEB_TABLE_ROLE_NAMES if hasattr(controlTypes.Role, n)}

    def copy_web_list_formatted(self, list_obj, original_hwnd):
        """Copy web list as an HTML table (one row per list item) + plain text.
        Uses the same manual NVDA-object approach as copy_web_list_plain so it
        works reliably even for navigation lists where native Ctrl+C fails."""
        items = []

        # Strategy 1: iterate direct LISTITEM children
        try:
            for child in list_obj.children:
                if child.role == controlTypes.Role.LISTITEM:
                    t = (child.name or "").strip()
                    if not t:
                        _unused, t = self.get_cell_text(child)
                    if t:
                        items.append(t)
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.copy_web_list_formatted (direct-iter): {e}")

        if not items:
            # Strategy 2: IAccessible accChild fallback (e.g. display:none lists)
            try:
                ia_obj = list_obj.IAccessibleObject
                child_count = ia_obj.accChildCount
                for i in range(1, child_count + 1):
                    try:
                        name = ia_obj.accName(i)
                        if name and name.strip():
                            items.append(name.strip())
                    except Exception:
                        continue
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.copy_web_list_formatted (ia-fallback): {e}")

        if not items:
            ui.message(_("No items found."))
            return

        esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_parts = ["<table border='1' cellpadding='2' cellspacing='0'>"]
        for item in items:
            html_parts.append(f"<tr><td>{esc(item)}</td></tr>")
        html_parts.append("</table>")
        html_out = "".join(html_parts)
        text_out = "\n".join(items)

        winsound.Beep(440, 100)
        if self.copy_manual_safe(html_out, text_out):
            self._restore_focus(original_hwnd)
            winsound.Beep(880, 100)
            count = len(items)
            if count == 1:
                ui.message(_("List copied (1 item)."))
            else:
                ui.message(_("List copied ({count} items).").format(count=count))
        else:
            ui.message(_("Copy failed."))

    def copy_web_list_plain(self, list_obj):
        """Copy list as plain <ul><li> HTML + newline-separated text, no original formatting."""
        items = []

        # Strategy 1: iterate direct children non-recursively.
        # A recursive collect() would hit Python's recursion limit on large lists
        # (e.g. 1233 items). Direct iteration is safe and sufficient because
        # <select> option nodes are always direct children of the LIST node.
        try:
            for child in list_obj.children:
                if child.role == controlTypes.Role.LISTITEM:
                    # Prefer name (always populated for <option> elements) over
                    # get_cell_text which recurses into children and may return
                    # empty for leaf nodes with no sub-children.
                    t = (child.name or "").strip()
                    if not t:
                        _unused, t = self.get_cell_text(child)
                    if t:
                        items.append(t)
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.copy_web_list_plain (direct-iter): {e}")

        if not items:
            # Strategy 2: IAccessible accChild enumeration.
            # Used when NVDA child iteration returns nothing (e.g. display:none
            # lists with IA2_STATE_OPAQUE where children are not wrapped as
            # NVDAObjects). accName(i) on the raw COM object always works here.
            try:
                ia_obj = list_obj.IAccessibleObject
                child_count = ia_obj.accChildCount
                for i in range(1, child_count + 1):
                    try:
                        name = ia_obj.accName(i)
                        if name and name.strip():
                            items.append(name.strip())
                    except Exception:
                        continue
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.copy_web_list_plain (ia-fallback): {e}")

        if not items:
            ui.message(_("No items found."))
            return
        esc = lambda s: s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        html_out = "<html><body><ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul></body></html>"
        text_out = "\n".join(items)
        winsound.Beep(440, 100)
        count = len(items)
        if self.copy_manual_safe(html_out, text_out):
            winsound.Beep(880, 100)
            if count == 1:
                ui.message(_("List copied (1 item)."))
            else:
                ui.message(_("List copied ({count} items).").format(count=count))
        else:
            ui.message(_("Copy failed."))

    def copy_marked_list_items(self):
        """Copy only the marked list items as plain text + HTML list.
        Context-agnostic: works for both web lists and generic desktop UIA lists,
        since it only ever reads from self.marked_rows."""
        if not self.marked_rows:
            ui.message(_("No items marked."))
            return
        esc = lambda s: s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        items = []
        for node in self.marked_rows:
            _unused, t = self.get_cell_text(node)
            if t:
                items.append(t)
        if not items:
            ui.message(_("No text found in marked items."))
            return
        html_out = "<html><body><ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul></body></html>"
        text_out = "\n".join(items)
        winsound.Beep(440, 100)
        count = len(items)
        if self.copy_manual_safe(html_out, text_out):
            winsound.Beep(880, 100)
            self.marked_rows = []
            if count == 1:
                ui.message(_("Marked item copied (1 item)."))
            else:
                ui.message(_("Marked items copied ({count} items).").format(count=count))
        else:
            ui.message(_("Copy failed."))

    def copy_syslistview32(self, hwnd, column_indices=None, label=None):
        """
        Copy a SysListView32 control completely using Win32 LVM_* messages.
        Bypasses NVDA's virtualized object tree for complete 64-bit safe extraction.
        Now supports column filtering.
        """
        import ctypes.wintypes as wintypes

        LVM_FIRST           = 0x1000
        LVM_GETITEMCOUNT    = LVM_FIRST + 4
        HDM_GETITEMCOUNT    = 0x1200
        LVM_GETHEADER       = LVM_FIRST + 31
        LVM_GETCOLUMNW      = LVM_FIRST + 95
        LVM_GETITEMTEXTW    = LVM_FIRST + 115
        LVCF_TEXT           = 0x0004
        LVIF_TEXT           = 0x0001

        PROCESS_VM_OPERATION = 0x0008
        PROCESS_VM_READ      = 0x0010
        PROCESS_VM_WRITE     = 0x0020
        MEM_COMMIT           = 0x1000
        MEM_RELEASE          = 0x8000
        PAGE_READWRITE       = 0x04

        class LVCOLUMN(ctypes.Structure):
            _fields_ = [
                ("mask",       ctypes.c_uint),
                ("fmt",        ctypes.c_int),
                ("cx",         ctypes.c_int),
                ("pszText",    ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int),
                ("iSubItem",   ctypes.c_int),
                ("iImage",     ctypes.c_int),
                ("iOrder",     ctypes.c_int),
            ]

        class LVITEM(ctypes.Structure):
            _fields_ = [
                ("mask",       ctypes.c_uint),
                ("iItem",      ctypes.c_int),
                ("iSubItem",   ctypes.c_int),
                ("state",      ctypes.c_uint),
                ("stateMask",  ctypes.c_uint),
                ("pszText",    ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int),
                ("iImage",     ctypes.c_int),
                ("lParam",     ctypes.c_void_p),
            ]

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # 64-bit safe signatures
        OpenProcess = ctypes.WINFUNCTYPE(wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)(("OpenProcess", kernel32))
        VirtualAllocEx = ctypes.WINFUNCTYPE(ctypes.c_void_p, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD)(("VirtualAllocEx", kernel32))
        VirtualFreeEx = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD)(("VirtualFreeEx", kernel32))
        ReadProcessMemory = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))(("ReadProcessMemory", kernel32))
        WriteProcessMemory = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))(("WriteProcessMemory", kernel32))
        SendMessageW = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, ctypes.c_void_p)(("SendMessageW", user32))

        TEXT_BUF_SIZE = 512

        # Get total items
        item_count = SendMessageW(hwnd, LVM_GETITEMCOUNT, 0, None)
        if item_count <= 0:
            return False

        # Get total columns
        header_hwnd = SendMessageW(hwnd, LVM_GETHEADER, 0, None)
        col_count = 0
        if header_hwnd:
            col_count = SendMessageW(header_hwnd, HDM_GETITEMCOUNT, 0, None)
        if col_count <= 0:
            col_count = 8 # Fallback

        # Open target process
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = OpenProcess(PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE, False, pid.value)
        
        if not process:
            # ERROR_ACCESS_DENIED (5) here almost always means the target window
            # belongs to a process running at a higher integrity level than NVDA
            # (e.g. an elevated/admin app), which the OS will never let us open
            # a handle to. This is expected and not fixable from here; we still
            # return False so the caller falls back to the normal NVDA-object
            # based copy path, but log distinctly to make this diagnosable.
            err = ctypes.windll.kernel32.GetLastError()
            if err == 5:
                log.debugWarning("EasyTableCopy: OpenProcess failed (Access Denied - target process is likely running elevated/as administrator).")
            else:
                log.debugWarning(f"EasyTableCopy: OpenProcess failed (error code {err}).")
            return False

        remote_text = None
        remote_struct = None

        try:
            # Allocate memory in target process
            remote_text = VirtualAllocEx(process, None, TEXT_BUF_SIZE * 2, MEM_COMMIT, PAGE_READWRITE)
            remote_struct = VirtualAllocEx(process, None, 512, MEM_COMMIT, PAGE_READWRITE)
            
            if not remote_text or not remote_struct:
                log.debugWarning("EasyTableCopy: VirtualAllocEx failed.")
                return False

            def read_remote_text():
                local_buf = ctypes.create_unicode_buffer(TEXT_BUF_SIZE)
                bytes_read = ctypes.c_size_t(0)
                ReadProcessMemory(process, remote_text, ctypes.byref(local_buf), TEXT_BUF_SIZE * 2, ctypes.byref(bytes_read))
                return local_buf.value

            def write_lvitem(item_idx, sub_idx):
                lvi = LVITEM()
                lvi.mask = LVIF_TEXT
                lvi.iItem = item_idx
                lvi.iSubItem = sub_idx
                lvi.pszText = remote_text
                lvi.cchTextMax = TEXT_BUF_SIZE
                written = ctypes.c_size_t(0)
                WriteProcessMemory(process, remote_struct, ctypes.byref(lvi), ctypes.sizeof(lvi), ctypes.byref(written))

            # Fetch headers
            headers = []
            for col_idx in range(col_count):
                lvc = LVCOLUMN()
                lvc.mask = LVCF_TEXT
                lvc.pszText = remote_text
                lvc.cchTextMax = TEXT_BUF_SIZE
                written = ctypes.c_size_t(0)
                
                zero_buf = (ctypes.c_byte * (TEXT_BUF_SIZE * 2))()
                WriteProcessMemory(process, remote_text, ctypes.byref(zero_buf), TEXT_BUF_SIZE * 2, ctypes.byref(written))
                WriteProcessMemory(process, remote_struct, ctypes.byref(lvc), ctypes.sizeof(lvc), ctypes.byref(written))
                
                SendMessageW(hwnd, LVM_GETCOLUMNW, col_idx, remote_struct)
                h = read_remote_text()
                headers.append(h if h else f"Col{col_idx+1}")

            # Trim empty headers at the end
            while headers and not headers[-1].strip():
                headers.pop()
            if not headers:
                headers = [f"Col{i+1}" for i in range(col_count)]
            col_count = len(headers)

            # Filter indices based on user request
            if column_indices is not None:
                valid_indices = [i for i in column_indices if i < col_count]
                if not valid_indices:
                    ui.message(_("Selected columns do not exist."))
                    return True # Handled, don't fall back to standard NVDA objects
                target_cols = valid_indices
            else:
                target_cols = list(range(col_count))

            filtered_headers = [headers[i] for i in target_cols]

            # Fetch rows and cells for target columns
            winsound.Beep(440, 100)
            text_rows = ["\t".join(filtered_headers)]
            esc = lambda s: s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            html_rows = ["<table border='1' cellpadding='2' cellspacing='0'><tr>" + "".join(f"<th>{esc(h)}</th>" for h in filtered_headers) + "</tr>"]

            for item_idx in range(item_count):
                row_vals = []
                for sub_idx in target_cols:
                    zero_buf = (ctypes.c_byte * (TEXT_BUF_SIZE * 2))()
                    written = ctypes.c_size_t(0)
                    WriteProcessMemory(process, remote_text, ctypes.byref(zero_buf), TEXT_BUF_SIZE * 2, ctypes.byref(written))
                    
                    write_lvitem(item_idx, sub_idx)
                    SendMessageW(hwnd, LVM_GETITEMTEXTW, item_idx, remote_struct)
                    row_vals.append(read_remote_text())

                text_rows.append("\t".join(row_vals))
                html_rows.append("<tr>" + "".join(f"<td>{esc(v) if v else '&nbsp;'}</td>" for v in row_vals) + "</tr>")

            html_rows.append("</table>")

        finally:
            if remote_text:
                VirtualFreeEx(process, remote_text, 0, MEM_RELEASE)
            if remote_struct:
                VirtualFreeEx(process, remote_struct, 0, MEM_RELEASE)
            if process:
                kernel32.CloseHandle(process)

        # Send to clipboard
        html_out = "".join(html_rows)
        text_out = "\n".join(text_rows)
        if self.copy_manual_safe(html_out, text_out):
            winsound.Beep(880, 100)
            
            # Use label if provided (for column specific copying)
            if label:
                ui.message(_("{label} ({count} items) copied.").format(label=label, count=item_count))
            else:
                if item_count == 1:
                    ui.message(_("List copied (1 item)."))
                else:
                    ui.message(_("List copied ({count} items).").format(count=item_count))
            return True
        return False

    def show_phantom_menu(self, current_obj, original_hwnd, is_list=False):
        dummy_frame = wx.Frame(None, -1, "Helper", pos=(0,0), size=(1,1))
        dummy_frame.Show()
        dummy_frame.Raise() 
        dummy_frame.SetFocus()
        try: 
            winUser.setForegroundWindow(dummy_frame.GetHandle())
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.show_phantom_menu (setForeground): {e}")

        menu = wx.Menu()
        if is_list:
            menu.Append(1, _("Copy List (With Formatting)"))
            menu.Append(7, _("Copy List (Plain)"))
            if self.marked_rows:
                count = len(self.marked_rows)
                lbl = _("item") if count == 1 else _("items")
                menu.Append(8, _("Copy Marked ({count} {lbl})").format(count=count, lbl=lbl))
                menu.Append(9, _("Clear Selections"))
        else:
            menu.Append(1, _("Copy Table (Standard)"))
            menu.Append(2, _("Copy Current Row"))
            menu.Append(3, _("Copy Table (Reconstructed)"))
            menu.Append(10, _("Copy Table (Reconstructed, with Vertical Bars)"))
            menu.Append(4, _("Copy Current Column"))
            if self.marked_rows or self.marked_col_indices:
                count = len(self.marked_rows) if self.marked_rows else len(self.marked_col_indices)
                lbl = (_("rows") if count > 1 else _("row")) if self.marked_rows else (_("columns") if count > 1 else _("column"))
                menu.Append(5, _("Copy Marked ({count} {lbl})").format(count=count, lbl=lbl))
                menu.Append(6, _("Clear Selections"))
        
        def _cmd(evt):
            id = evt.GetId()
            dummy_frame.Destroy()
            wx.CallLater(10, self.on_menu_select, id, current_obj, original_hwnd)
        
        menu.Bind(wx.EVT_MENU, _cmd)
        dummy_frame.PopupMenu(menu)
        if dummy_frame:
            try: 
                dummy_frame.Destroy()
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.show_phantom_menu (destroy): {e}")
            self._restore_focus(original_hwnd)

    @script_description(_("Opens Copy Menu (Web) or Copies List (Desktop)."))
    def script_tableMenu(self, gesture):
        focus = api.getFocusObject()
        if focus.appModule:
            app_name = focus.appModule.appName.lower()
            for blocked in BLOCKED_APPS:
                if blocked in app_name:
                    ui.message(_("Use standard copy (Ctrl+C) in this application."))
                    return

        ti = self.get_context_tree_interceptor()
        if ti:
            try: 
                obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.script_tableMenu (caret): {e}")
                obj = api.getFocusObject()
            hwnd = winUser.getForegroundWindow()
            # Real table → Table menu
            if self.find_object_by_role(obj, self.WEB_TABLE_ROLES):
                wx.CallLater(10, self.show_phantom_menu, obj, hwnd, False)
                return
            # Web list → List menu (caret-based search)
            list_obj = self.find_object_by_role(obj, {controlTypes.Role.LIST})
            if list_obj:
                wx.CallLater(10, self.show_phantom_menu, list_obj, hwnd, True)
                return
            # Secondary search via focus object: handles open <select> dropdowns where
            # the focused LISTITEM lives outside the virtual buffer (display:none list),
            # so the caret-based NVDAObjectAtStart does not reach it.
            list_obj = self.find_object_by_role(focus, {controlTypes.Role.LIST})
            if list_obj:
                wx.CallLater(10, self.show_phantom_menu, list_obj, hwnd, True)
                return
            ui.message(_("Not on a table."))
        else:
            if self.copy_explorer_content(focus.windowHandle): 
                return
            tree_obj = self.find_object_by_role(focus, [controlTypes.Role.TREEVIEW, controlTypes.Role.TREEVIEWITEM])
            if tree_obj:
                self.perform_tree_copy(tree_obj)
                return
            target_list = None
            if focus.role in self.TABLE_ROLES: 
                target_list = focus
            else:
                temp = focus
                for _loop in range(MAX_PARENT_SEARCH_DEPTH):
                    if not temp:
                        break
                    if temp.role in self.TABLE_ROLES:
                        target_list = temp
                        break
                    temp = temp.parent
            if target_list:
                # --- Interrupting: If the list is a SysListView32, run the Win32 memory read method ---
                is_syslist = False
                try:
                    if target_list.windowClassName and target_list.windowClassName.lower() == "syslistview32":
                        is_syslist = True
                except Exception:
                    pass
                
                if is_syslist and target_list.windowHandle:
                    # Exit the function if successful
                    if self.copy_syslistview32(target_list.windowHandle):
                        return

                # --- If not SysListView32 or fails, continue normal process ---
                if target_list.role == controlTypes.Role.LIST:
                    if self.marked_rows:
                        self.copy_marked_list_items()
                    else:
                        self.copy_web_list_plain(target_list)
                else:
                    self.perform_list_view_copy_fallback(target_list)
            else:
                ui.message(_("Focus is not on a list or table."))

    @script_description(_("Marks/Unmarks current row or list item."))
    def script_markRow(self, gesture):
        if self.marked_col_indices:
            ui.message(_("Cannot mark rows while columns are selected."))
            return
        ti = self.get_context_tree_interceptor()
        obj = None
        if ti:
            try:
                obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
            except Exception as e:
                log.debugWarning(f"EasyTableCopy.script_markRow: {e}")
        else:
            # Desktop: generic UIA/MSAA lists only. Explorer has its own native
            # selection concept, and SysListView32 lists are copied via a
            # separate Win32 memory-read path that never consults marked_rows.
            if self.is_explorer_context():
                ui.message(_("Use native selection (Ctrl+Click / Shift+Arrow) in Explorer."))
                return
            obj = api.getFocusObject()
            if self.is_syslistview32_obj(obj):
                ui.message(_("Marking is not supported in this list yet."))
                return
        row = self.find_object_by_role(obj, self.ROW_ROLES)
        if row:
            if row.role == controlTypes.Role.TREEVIEWITEM:
                ui.message(_("Marking is not supported in tree views."))
                return
            # If marks exist from a different list/table, they no longer
            # apply here - drop them before marking in the current one.
            container = self.find_object_by_role(row.parent, self.TABLE_ROLES) if row.parent else None
            if self.marked_rows and container is not None and container != self.marked_container:
                self.marked_rows = []
            self.marked_container = container
            # Use "item" label for list items, "row" for table rows
            is_list_item = (row.role == controlTypes.Role.LISTITEM)
            lbl_single = _("item") if is_list_item else _("row")
            lbl_plural = _("items") if is_list_item else _("rows")
            if row in self.marked_rows:
                self.marked_rows.remove(row)
                c = len(self.marked_rows)
                if c == 0: 
                    ui.message(_("{lbl} Unmarked.").format(lbl=lbl_single.capitalize()))
                elif c == 1: 
                    ui.message(_("{lbl} Unmarked. Total: 1 {lbl}").format(lbl=lbl_single.capitalize()))
                else: 
                    ui.message(_("{lbl} Unmarked. Total: {count} {lbl_pl}").format(lbl=lbl_single.capitalize(), count=c, lbl_pl=lbl_plural))
            else:
                self.marked_rows.append(row)
                c = len(self.marked_rows)
                if c == 1: 
                    ui.message(_("{lbl} Marked. Total: 1 {lbl}").format(lbl=lbl_single.capitalize()))
                else: 
                    ui.message(_("{lbl} Marked. Total: {count} {lbl_pl}").format(lbl=lbl_single.capitalize(), count=c, lbl_pl=lbl_plural))
        else: 
            ui.message(_("Not a row or list item."))

    @script_description(_("Marks/Unmarks current column."))
    def script_markColumn(self, gesture):
        if not self.get_context_tree_interceptor(): 
            return
        if self.marked_rows:
            ui.message(_("Cannot mark columns while rows are selected."))
            return
        obj = None
        try: 
            obj = self.get_context_tree_interceptor().makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
        except Exception as e:
            log.debugWarning(f"EasyTableCopy.script_markColumn: {e}")
        cell = self.find_object_by_role(obj, self.CELL_ROLES)
        if cell:
            # If marks exist from a different table, they no longer apply
            # here - drop them before marking a column in the current one.
            table = self.find_object_by_role(cell.parent, self.TABLE_ROLES) if cell.parent else None
            if self.marked_col_indices and table is not None and table != self.marked_col_container:
                self.marked_col_indices.clear()
            self.marked_col_container = table
            idx = self.get_column_index(cell)
            if idx != -1:
                if idx in self.marked_col_indices:
                    self.marked_col_indices.remove(idx)
                    c = len(self.marked_col_indices)
                    if c == 0: 
                        ui.message(_("Column Unmarked."))
                    elif c == 1: 
                        ui.message(_("Column Unmarked. Total: 1 column"))
                    else: 
                        ui.message(_("Column Unmarked. Total: {count} columns").format(count=c))
                else:
                    self.marked_col_indices.add(idx)
                    c = len(self.marked_col_indices)
                    if c == 1: 
                        ui.message(_("Column Marked. Total: 1 column"))
                    else: 
                        ui.message(_("Column Marked. Total: {count} columns").format(count=c))
            else: 
                ui.message(_("Index error."))
        else: 
            ui.message(_("Not a cell."))

    @script_description(_("Clears selections."))
    def script_clearAll(self, gesture):
        if not self.marked_rows and not self.marked_col_indices:
            ui.message(_("No selection to clear."))
            return
        self.marked_rows = []
        self.marked_col_indices.clear()
        ui.message(_("Selections cleared."))

    # =========================================================================
    # FEATURE: STANDALONE COMMANDS FOR EVERY MENU ENTRY (WEB ONLY)
    # Unassigned by default; users can bind gestures in
    # NVDA Menu > Preferences > Input gestures > EasyTableCopy.
    # They reuse on_menu_select so behaviour is identical to the menu.
    # =========================================================================
    def _web_command_context(self):
        """Return (caret_obj, focus_obj, hwnd) in browse mode, else None."""
        ti = self.get_context_tree_interceptor()
        if not ti:
            ui.message(_("This command works only in web browse mode."))
            return None
        focus = api.getFocusObject()
        try:
            obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
        except Exception as e:
            log.debugWarning(f"EasyTableCopy._web_command_context: {e}")
            obj = focus
        return obj, focus, winUser.getForegroundWindow()

    def _call_after_keys_released(self, func, *args, _attempt=0):
        """Run func once the modifier keys of the user's gesture are released.
        Commands that synthesize Ctrl+C (standard table/row copy) would
        otherwise send it while e.g. NVDA/Shift/Alt are still physically held,
        so the application sees a different key combination and nothing is
        copied. Gives up waiting after ~2 seconds and runs anyway."""
        held = bool(getattr(keyboardHandler, "currentModifiers", None))
        if not held:
            held = any(
                winUser.getKeyState(vk) & 0x8000
                for vk in (winUser.VK_CONTROL, winUser.VK_MENU, winUser.VK_SHIFT, winUser.VK_LWIN, winUser.VK_RWIN)
            )
        if held and _attempt < 40:
            wx.CallLater(50, self._call_after_keys_released, func, *args, _attempt=_attempt + 1)
            return
        func(*args)

    def _run_table_command(self, item_id):
        ctx = self._web_command_context()
        if not ctx:
            return
        obj, _focus, hwnd = ctx
        if not self.find_object_by_role(obj, self.WEB_TABLE_ROLES):
            ui.message(_("Not on a table."))
            return
        wx.CallLater(10, self._call_after_keys_released, self.on_menu_select, item_id, obj, hwnd)

    def _run_list_command(self, item_id):
        ctx = self._web_command_context()
        if not ctx:
            return
        obj, focus, hwnd = ctx
        list_obj = (self.find_object_by_role(obj, {controlTypes.Role.LIST})
                    or self.find_object_by_role(focus, {controlTypes.Role.LIST}))
        if not list_obj:
            ui.message(_("Not on a list."))
            return
        wx.CallLater(10, self._call_after_keys_released, self.on_menu_select, item_id, list_obj, hwnd)

    @script_description(_("Copies the whole table (standard copy)."))
    def script_copyTableStandard(self, gesture):
        self._run_table_command(1)

    @script_description(_("Copies the current table row."))
    def script_copyCurrentRow(self, gesture):
        self._run_table_command(2)

    @script_description(_("Copies the whole table (reconstructed)."))
    def script_copyTableReconstructed(self, gesture):
        self._run_table_command(3)

    @script_description(_("Copies the whole table (reconstructed, with vertical bars between columns)."))
    def script_copyTableReconstructedBars(self, gesture):
        self._run_table_command(10)

    @script_description(_("Copies the current table column."))
    def script_copyCurrentColumn(self, gesture):
        self._run_table_command(4)

    @script_description(_("Copies the marked table rows or columns."))
    def script_copyMarkedTable(self, gesture):
        ctx = self._web_command_context()
        if not ctx:
            return
        if not self.marked_rows and not self.marked_col_indices:
            ui.message(_("No rows marked."))
            return
        obj, _focus, hwnd = ctx
        wx.CallLater(10, self._call_after_keys_released, self.on_menu_select, 5, obj, hwnd)

    @script_description(_("Copies the current list (with formatting)."))
    def script_copyListFormatted(self, gesture):
        self._run_list_command(1)

    @script_description(_("Copies the current list (plain)."))
    def script_copyListPlain(self, gesture):
        self._run_list_command(7)

    @script_description(_("Copies the marked list items."))
    def script_copyMarkedListItems(self, gesture):
        if not self._web_command_context():
            return
        wx.CallLater(10, self._call_after_keys_released, self.copy_marked_list_items)

    def terminate(self):
        """Clean up on addon unload"""
        self.marked_rows = []
        self.marked_col_indices.clear()
        self._unpatch_navigation_announcements()

    __gestures = {
        "kb:alt+nvda+t": "tableMenu",
        "kb:control+alt+space": "markRow",
        "kb:control+alt+shift+space": "markColumn",
        "kb:control+alt+windows+space": "clearAll",
    }