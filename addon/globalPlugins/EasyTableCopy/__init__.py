# -*- coding: utf-8 -*-
# EasyTableCopy v2026.4.0
# Author: Çağrı Doğan

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
from typing import List, Tuple, Optional, Set
import gc

# Start translation system
addonHandler.initTranslation()
user32 = ctypes.windll.user32

BLOCKED_APPS = ["excel", "calc", "soffice"]

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

    marked_rows = [] 
    marked_col_indices = set()

    def get_context_tree_interceptor(self):
        obj = api.getFocusObject()
        if hasattr(obj, "treeInterceptor") and obj.treeInterceptor:
            return obj.treeInterceptor
        return None

    def is_web_context(self):
        """Check if current context is web (has tree interceptor)"""
        return self.get_context_tree_interceptor() is not None

    def is_explorer_context(self):
        """Check if current context is Windows Explorer"""
        focus = api.getFocusObject()
        return (focus.appModule and focus.appModule.appName.lower() == "explorer")

    def is_desktop_list_context(self):
        """Check if current context is a desktop list (not web, not explorer)"""
        if self.is_web_context() or self.is_explorer_context():
            return False
        focus = api.getFocusObject()
        return focus.role in self.TABLE_ROLES or self.find_object_by_role(focus, self.TABLE_ROLES) is not None

    def find_object_by_role(self, start_obj, target_roles):
        obj = start_obj
        for _loop in range(50): 
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
            except: pass
        try:
            if hasattr(cell_obj, "columnNumber"):
                val = cell_obj.columnNumber
                if val > 0: return val - 1
        except: pass
        return -1

    def _restore_focus(self, hwnd):
        try:
            if hwnd:
                if winUser.getForegroundWindow() != hwnd:
                    winUser.setForegroundWindow(hwnd)
                winUser.setFocus(hwnd)
                time.sleep(0.05) 
        except: pass

    # =========================================================================
    # SIMPLE TEXT EXTRACTION - NO FORMATTING ATTEMPTS
    # =========================================================================
    def get_cell_text(self, obj, depth=0) -> Tuple[str, str]:
        """
        EXTREMELY FAST - Only extracts text, no formatting
        Returns (html_text, plain_text)
        """
        # Prevent deep recursion
        if depth > 10:
            return "", ""
        
        # Fast path for empty objects
        if obj is None:
            return "", ""
        
        # Handle objects with children
        if obj.childCount > 0:
            # Process children in batch
            text_parts = []
            for child in obj.children:
                if child.role in self.CONTENT_ROLES or child.childCount > 0:
                    h, t = self.get_cell_text(child, depth + 1)
                    if t:
                        text_parts.append(t)
            
            if text_parts:
                plain_text = " ".join(text_parts)
                # Simple HTML - just the text, no formatting
                html_text = plain_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                return html_text, plain_text
            return "", ""
        else:
            # Leaf node
            raw = (obj.name or obj.value or "").strip()
            if raw:
                # Simple escape for HTML
                html = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                return html, raw
            return "", ""

    def copy_manual_safe(self, html, text):
        """Fast clipboard handling"""
        if not wx.TheClipboard.Open(): 
            return False
        try:
            d = wx.DataObjectComposite()
            h = wx.HTMLDataObject()
            
            # Minimal HTML structure
            full = f"<html><body>{html}</body></html>"
            h.SetHTML(full)
            d.Add(h, True)
            
            t = wx.TextDataObject()
            t.SetText(text)
            d.Add(t, False)
            
            result = wx.TheClipboard.SetData(d)
            wx.TheClipboard.Close()
            return result
        except: 
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
        Get accurate row and column counts from any table
        Uses sampling for large tables to avoid performance issues
        Returns (row_count, column_count)
        """
        # First get total rows (fast)
        all_rows = self.collect_rows_fast(table_obj)
        total_rows = len(all_rows)
        
        if total_rows == 0:
            return 0, 0
        
        # For column count, sample first few rows
        sample_rows = all_rows[:min(sample_size, total_rows)]
        max_cols = 0
        
        for row in sample_rows:
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if cells:
                max_cols = max(max_cols, len(cells))
        
        return total_rows, max_cols

    def process_table_fast(self, rows, selected_indices=None) -> Tuple[str, str]:
        """
        FAST table processing - no formatting overhead
        Returns (html_output, text_output)
        """
        html_parts = ["<table border='1' cellpadding='2' cellspacing='0'>"]
        text_parts = []
        
        for row in rows:
            # Get cells
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if not cells:
                cells = list(row.children)
            
            # Filter columns if needed
            if selected_indices:
                filtered_cells = []
                for idx in selected_indices:
                    if 0 <= idx < len(cells):
                        filtered_cells.append(cells[idx])
                cells = filtered_cells
            
            # Process row
            row_html = "<tr>"
            row_text = []
            
            for cell in cells:
                # Get text only - NO FORMATTING
                h, t = self.get_cell_text(cell)
                
                if not h:
                    h = "&nbsp;"
                if not t:
                    t = " "
                
                row_html += f"<td>{h}</td>"
                row_text.append(t)
            
            row_html += "</tr>"
            html_parts.append(row_html)
            text_parts.append("\t".join(row_text))
        
        html_parts.append("</table>")
        return "".join(html_parts), "\n".join(text_parts)

    # =========================================================================
    # ENGINE A: NATIVE COPY
    # =========================================================================
    def perform_native_copy(self, obj, label, original_hwnd):
        try:
            self._restore_focus(original_hwnd)
            
            count_info = ""
            if obj.role in self.TABLE_ROLES:
                rows = self.collect_rows_fast(obj)
                count = len(rows)
                if count == 1: count_info = _(" (1 row)")
                elif count > 1: count_info = _(" ({count} rows)").format(count=count)
            elif obj.role in self.ROW_ROLES:
                cells = [c for c in obj.children if c.role in self.CELL_ROLES]
                count = len(cells)
                if count == 1: count_info = _(" (1 cell)")
                elif count > 1: count_info = _(" ({count} cells)").format(count=count)

            info = obj.makeTextInfo(textInfos.POSITION_ALL)
            info.updateSelection()
            
            winsound.Beep(440, 100) 
            keyboardHandler.KeyboardInputGesture.fromName("control+c").send()
            
            wx.CallLater(300, self._retry_clipboard_repair, label, count_info, 1)
        except Exception:
            ui.message(_("Selection failed."))

    def _retry_clipboard_repair(self, label, count_info, attempt):
        if not wx.TheClipboard.Open():
            if attempt < 15:
                wx.CallLater(200, self._retry_clipboard_repair, label, count_info, attempt + 1)
                return
            else:
                ui.message(_("{label} copied{count} (Raw).").format(label=label, count=count_info))
                return

        try:
            if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_HTML)):
                data_obj = wx.HTMLDataObject()
                if wx.TheClipboard.GetData(data_obj):
                    raw_html = data_obj.GetHTML()
                    modified = False
                    
                    cell_pattern = re.compile(r'(<td\b[^>]*>)([\s\r\n]*(?:<br\s*/?>)?[\s\r\n]*)(</td>)', re.IGNORECASE)
                    if cell_pattern.search(raw_html):
                        raw_html = cell_pattern.sub(r'\1&nbsp;\3', raw_html)
                        modified = True
                    
                    if "border=" not in raw_html.lower() and "border:" not in raw_html.lower():
                         table_pattern = re.compile(r'(<table\b[^>]*)(>)', re.IGNORECASE)
                         raw_html = table_pattern.sub(r'\1 border="1" cellspacing="0" cellpadding="5"\2', raw_html)
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
                        ui.message(_("{label} copied{count}.").format(label=label, count=count_info))
                    else:
                        winsound.Beep(600, 100)
                        ui.message(_("{label} copied{count}.").format(label=label, count=count_info))
            else:
                ui.message(_("{label} copied{count} (Text).").format(label=label, count=count_info))
        except:
            ui.message(_("Error."))
        finally:
            wx.TheClipboard.Close()

    # =========================================================================
    # ENGINE B: FAST PLAIN TEXT COPY - NO FORMATTING
    # =========================================================================
    def perform_full_table_manual(self, current_obj, original_hwnd):
        """ULTRA FAST - No formatting, just plain text"""
        table = self.find_object_by_role(current_obj, self.TABLE_ROLES)
        if not table:
            ui.message(_("Table not found."))
            return

        winsound.Beep(440, 100)
        
        # Collect rows - super fast
        rows = self.collect_rows_fast(table)
        
        if not rows:
            ui.message(_("Table is empty."))
            return

        # Process table - no formatting overhead
        html_out, text_out = self.process_table_fast(rows)
        
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
            if len(self.marked_rows) > 0:
                ti = self.get_context_tree_interceptor()
                try:
                    obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
                    table = self.find_object_by_role(obj, self.TABLE_ROLES)
                    if not table and self.marked_rows: 
                        table = self.find_object_by_role(self.marked_rows[0], self.TABLE_ROLES)
                    if table:
                        all_rows = self.collect_rows_fast(table)
                        target_rows = [r for r in all_rows if r in self.marked_rows]
                    else: 
                        target_rows = self.marked_rows
                except: 
                    target_rows = self.marked_rows
        
        elif self.marked_col_indices:
            ti = self.get_context_tree_interceptor()
            try:
                obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
                table = self.find_object_by_role(obj, self.TABLE_ROLES)
                target_rows = self.collect_rows_fast(table)
                target_col_indices = sorted(list(self.marked_col_indices))
            except: 
                return

        if not target_rows:
            self._restore_focus(original_hwnd)
            ui.message(_("Error: No items to copy."))
            return

        winsound.Beep(440, 100)
        
        # Process with column filtering
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
        try:
            shell = CreateObject("shell.application")
            folder_view = None
            for window in shell.Windows():
                try: 
                    if window.hwnd == hwnd or user32.IsChild(window.hwnd, hwnd):
                        folder_view = window.Document
                        break
                except: 
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
        except: 
            return False

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
        except Exception:
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
            # Web context
            try:
                obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
                table = self.find_object_by_role(obj, self.TABLE_ROLES)
            except:
                pass
        
        if not table:
            # Desktop context
            if focus.role in self.TABLE_ROLES:
                table = focus
            else:
                temp = focus
                for _ in range(5):
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
        """Copy first column - desktop only"""
        if self.is_web_context():
            # Don't process the hotkey on the web
            return
        self._copy_columns_direct([0], "Column 1")

    @script_description(_("Copies second column from current table (desktop only)."))
    def script_copyColumn2(self, gesture):
        """Copy second column - desktop only"""
        if self.is_web_context():
            return
        self._copy_columns_direct([1], "Column 2")

    @script_description(_("Copies third column from current table (desktop only)."))
    def script_copyColumn3(self, gesture):
        """Copy third column - desktop only"""
        if self.is_web_context():
            return
        self._copy_columns_direct([2], "Column 3")

    @script_description(_("Copies first and second columns from current table (desktop only)."))
    def script_copyColumns1and2(self, gesture):
        """Copy columns 1 and 2 - desktop only"""
        if self.is_web_context():
            return
        self._copy_columns_direct([0, 1], "Columns 1-2")

    @script_description(_("Copies first and third columns from current table (desktop only)."))
    def script_copyColumns1and3(self, gesture):
        """Copy columns 1 and 3 - desktop only"""
        if self.is_web_context():
            return
        self._copy_columns_direct([0, 2], "Columns 1-3")

    @script_description(_("Copies first three columns from current table (desktop only)."))
    def script_copyColumns1to3(self, gesture):
        """Copy columns 1, 2, and 3 - desktop only"""
        if self.is_web_context():
            return
        self._copy_columns_direct([0, 1, 2], "Columns 1-3")

    def _copy_columns_direct(self, column_indices, label):
        """Direct column copying for non-web contexts"""
        table = self._get_current_table()
        if not table:
            ui.message("Not on a table.")
            return
        
        # Special handling for Explorer
        if self.is_explorer_context():
            focus = api.getFocusObject()
            try:
                shell = CreateObject("shell.application")
                folder_view = None
                for window in shell.Windows():
                    try: 
                        if window.hwnd == focus.windowHandle or user32.IsChild(window.hwnd, focus.windowHandle):
                            folder_view = window.Document
                            break
                    except: 
                        continue
                
                if folder_view:
                    items = folder_view.Folder.Items()
                    count = items.Count
                    
                    if count == 0:
                        ui.message("Folder is empty.")
                        return
                    
                    winsound.Beep(440, 100)
                    
                    # Get headers
                    headers = []
                    for i in column_indices:
                        header = folder_view.Folder.GetDetailsOf(None, i)
                        if header:
                            headers.append(header)
                    
                    # Get data
                    text_rows = ["\t".join(headers)] if headers else []
                    data_rows = []
                    
                    for i in range(count):
                        item = items.Item(i)
                        vals = []
                        for idx in column_indices:
                            try:
                                val = str(folder_view.Folder.GetDetailsOf(item, idx)).strip()
                                vals.append(val if val else " ")
                            except:
                                vals.append(" ")
                        if vals:
                            data_rows.append("\t".join(vals))
                    
                    if not data_rows:
                        ui.message("No data found.")
                        return
                    
                    text_rows.extend(data_rows)
                    text_out = "\n".join(text_rows)
                    html_out = "<html><body><pre>" + text_out + "</pre></body></html>"
                    
                    if self.copy_manual_safe(html_out, text_out):
                        winsound.Beep(880, 100)
                        ui.message(f"{label} ({count} items) copied.")
                    return
            except:
                pass
        
        # Generic table handling for desktop lists
        rows = self.collect_rows_fast(table)
        if not rows:
            ui.message("Table is empty.")
            return
        
        winsound.Beep(440, 100)
        
        text_parts = []
        for row in rows:
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if not cells:
                cells = list(row.children)
            
            row_text = []
            for idx in column_indices:
                if 0 <= idx < len(cells):
                    h, t = self.get_cell_text(cells[idx])
                    row_text.append(t if t else " ")
                else:
                    row_text.append(" ")
            
            if any(row_text):
                text_parts.append("\t".join(row_text))
        
        if not text_parts:
            ui.message("No data found.")
            return
        
        text_out = "\n".join(text_parts)
        html_out = "<html><body><pre>" + text_out + "</pre></body></html>"
        
        if self.copy_manual_safe(html_out, text_out):
            winsound.Beep(880, 100)
            ui.message(f"{label} ({len(text_parts)} rows) copied.")

    # =========================================================================
    # FEATURE: TABLE STATISTICS (WORKS EVERYWHERE)
    # =========================================================================
    @script_description(_("Announces table dimensions."))
    def script_tableStats(self, gesture):
        """Announce number of rows and columns in current table"""
        table = self._get_current_table()
        
        if not table:
            ui.message("Not on a table.")
            return
        
        # Special handling for Explorer
        if self.is_explorer_context():
            focus = api.getFocusObject()
            try:
                shell = CreateObject("shell.application")
                folder_view = None
                for window in shell.Windows():
                    try: 
                        if window.hwnd == focus.windowHandle or user32.IsChild(window.hwnd, focus.windowHandle):
                            folder_view = window.Document
                            break
                    except: 
                        continue
                
                if folder_view:
                    items = folder_view.Folder.Items()
                    count = items.Count
                    
                    if count == 0:
                        ui.message("Folder is empty.")
                        return
                    
                    # Count columns
                    col_count = 0
                    for i in range(20):  # Check up to 20 columns
                        if folder_view.Folder.GetDetailsOf(None, i):
                            col_count += 1
                    
                    winsound.Beep(880, 100)
                    if col_count == 0:
                        ui.message(f"Folder has {count} items.")
                    else:
                        ui.message(f"Folder has {count} items and {col_count} columns.")
                    return
            except:
                pass
        
        # Generic table handling for all contexts
        rows, cols = self.get_table_structure(table)
        
        if rows == 0:
            ui.message("Table is empty.")
            return
        
        winsound.Beep(880, 100)
        if cols == 0:
            ui.message(f"Table has {rows} rows.")
        else:
            ui.message(f"Table has {rows} rows and {cols} columns.")

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
            except:
                pass
        else:
            cell = self.find_object_by_role(focus, self.CELL_ROLES)
        
        if not cell:
            ui.message("Not in a cell.")
            return
        
        winsound.Beep(440, 100)
        
        h, t = self.get_cell_text(cell)
        if not t:
            ui.message("Cell is empty.")
            return
        
        if self.copy_manual_safe(f"<html><body>{h}</body></html>", t):
            winsound.Beep(880, 100)
            ui.message("Cell copied.")

    # =========================================================================
    # FEATURE: COPY MARKED ROWS AS TEXT (WEB ONLY)
    # =========================================================================
    @script_description(_("Copies marked rows as plain text without table structure (web only)."))
    def script_copyMarkedAsText(self, gesture):
        """Copy marked rows as plain text lines - WEB ONLY"""
        if not self.is_web_context():
            # If not on the web, don't do anything
            return
        
        if not self.marked_rows:
            ui.message("No rows marked.")
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
            ui.message("No text found.")
            return
        
        text_out = "\n".join(text_lines)
        html_out = "<html><body>" + "<br>".join(text_lines) + "</body></html>"
        
        if self.copy_manual_safe(html_out, text_out):
            winsound.Beep(880, 100)
            count = len(text_lines)
            
            # Clear marks after successful copy
            self.marked_rows = []
            
            if count == 1:
                ui.message("Marked row copied as text.")
            else:
                ui.message(f"Marked rows copied as text ({count} rows).")

    # =========================================================================
    # MENU & INPUT HANDLERS
    # =========================================================================
    def on_menu_select(self, item_id, current_obj, original_hwnd):
        if item_id == 1: # Standard (Native)
            target = self.find_object_by_role(current_obj, self.TABLE_ROLES)
            if target: 
                self.perform_native_copy(target, _("Table"), original_hwnd)
            else: 
                ui.message(_("Target not found."))
        elif item_id == 2: # Current Row
            target = self.find_object_by_role(current_obj, self.ROW_ROLES)
            if target: 
                self.perform_native_copy(target, _("Row"), original_hwnd)
            else: 
                ui.message(_("Target not found."))
        elif item_id == 3: # Reconstructed (Plain Text)
            self.perform_full_table_manual(current_obj, original_hwnd)
        elif item_id == 4: # Current Column
            target = self.find_object_by_role(current_obj, self.CELL_ROLES)
            if target:
                idx = self.get_column_index(target)
                if idx != -1:
                    self.marked_col_indices.add(idx)
                    self.perform_marked_copy_manual(original_hwnd)
                    self.marked_col_indices.discard(idx)
        elif item_id == 5: # Marked
            self.perform_marked_copy_manual(original_hwnd)
        elif item_id == 6:
            if not self.marked_rows and not self.marked_col_indices:
                ui.message(_("No selection to clear."))
            else:
                self.marked_rows = []
                self.marked_col_indices.clear()
                ui.message(_("Selections cleared."))

    def show_phantom_menu(self, current_obj, original_hwnd):
        dummy_frame = wx.Frame(None, -1, "Helper", pos=(0,0), size=(1,1))
        dummy_frame.Show()
        dummy_frame.Raise() 
        dummy_frame.SetFocus()
        try: 
            winUser.setForegroundWindow(dummy_frame.GetHandle())
        except: 
            pass

        menu = wx.Menu()
        menu.Append(1, _("Copy Table (Standard)"))
        menu.Append(2, _("Copy Current Row"))
        menu.Append(3, _("Copy Table (Reconstructed)"))
        menu.Append(4, _("Copy Current Column"))
        
        if self.marked_rows or self.marked_col_indices:
            count = len(self.marked_rows) if self.marked_rows else len(self.marked_col_indices)
            lbl = ""
            if self.marked_rows:
                lbl = _("rows") if count > 1 else _("row")
            else:
                lbl = _("columns") if count > 1 else _("column")
            menu.Append(5, _("Copy Marked ({count} {lbl})").format(count=count, lbl=lbl))
            menu.Append(6, _("Clear Selections"))
        menu.Append(wx.ID_CANCEL, _("Cancel"))
        
        def _cmd(evt):
            id = evt.GetId()
            dummy_frame.Destroy()
            wx.CallLater(10, self.on_menu_select, id, current_obj, original_hwnd)
        
        menu.Bind(wx.EVT_MENU, _cmd)
        dummy_frame.PopupMenu(menu)
        if dummy_frame:
            try: 
                dummy_frame.Destroy()
            except: 
                pass
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
            except: 
                obj = api.getFocusObject()
            if self.find_object_by_role(obj, self.TABLE_ROLES):
                hwnd = winUser.getForegroundWindow()
                wx.CallLater(10, self.show_phantom_menu, obj, hwnd)
            else:
                ui.message(_("Not on a table."))
        else:
            if self.copy_explorer_content(focus.windowHandle): 
                return
            target_list = None
            if focus.role in self.TABLE_ROLES: 
                target_list = focus
            else:
                temp = focus
                for _loop in range(5):
                    if not temp: 
                        break
                    if temp.role in self.TABLE_ROLES:
                        target_list = temp
                        break
                    temp = temp.parent
            if target_list:
                self.perform_list_view_copy_fallback(target_list)
            else:
                ui.message(_("Focus is not on a list or table."))

    @script_description(_("Marks/Unmarks current row."))
    def script_markRow(self, gesture):
        if not self.get_context_tree_interceptor(): 
            # Don't process the key if not on the web
            return
        if self.marked_col_indices:
            ui.message(_("Cannot mark rows while columns are selected."))
            return
        obj = None
        try: 
            obj = self.get_context_tree_interceptor().makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
        except: 
            pass
        row = self.find_object_by_role(obj, self.ROW_ROLES)
        if row:
            if row in self.marked_rows:
                self.marked_rows.remove(row)
                c = len(self.marked_rows)
                if c == 0: 
                    ui.message(_("Row Unmarked."))
                elif c == 1: 
                    ui.message(_("Row Unmarked. Total: 1 row"))
                else: 
                    ui.message(_("Row Unmarked. Total: {count} rows").format(count=c))
            else:
                self.marked_rows.append(row)
                c = len(self.marked_rows)
                if c == 1: 
                    ui.message(_("Row Marked. Total: 1 row"))
                else: 
                    ui.message(_("Row Marked. Total: {count} rows").format(count=c))
        else: 
            ui.message(_("Not a row."))

    @script_description(_("Marks/Unmarks current column."))
    def script_markColumn(self, gesture):
        if not self.get_context_tree_interceptor(): 
            # Don't handle key if not on the web
            return
        if self.marked_rows:
            ui.message(_("Cannot mark columns while rows are selected."))
            return
        obj = None
        try: 
            obj = self.get_context_tree_interceptor().makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
        except: 
            pass
        cell = self.find_object_by_role(obj, self.CELL_ROLES)
        if cell:
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
        if not self.get_context_tree_interceptor(): 
            # Don't handle key if not on web
            return
        if not self.marked_rows and not self.marked_col_indices:
            ui.message(_("No selection to clear."))
            return
        self.marked_rows = []
        self.marked_col_indices.clear()
        ui.message(_("Selections cleared."))

    def terminate(self):
        """Clean up on addon unload"""
        gc.collect()

    __gestures = {
        "kb:alt+nvda+t": "tableMenu",
        "kb:control+alt+space": "markRow",
        "kb:control+alt+shift+space": "markColumn",
        "kb:control+alt+windows+space": "clearAll",
    }